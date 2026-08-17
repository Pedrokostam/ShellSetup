from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from python import app_group, target_os
from python.app_group import AppGroup
from python.app_request import AppRequest, AppRequestStem
from python.context import paths, system
from python.error import (
    AppInstallError,
    InstallScriptError,
    JsonSyntaxError,
)
from python.filters import ComplexFilter, Filters
from python.installation import (
    Command,
    Installer,
    InstallInstruction,
    Script,
    cache_sudo,
)
from python.printing import timed

from .report import Report, Status
from .target_os import *


def is_elevated() -> bool:
    if os.name == "nt":
        import ctypes

        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except OSError:
            return False
    return os.geteuid() == 0


K_DEF_GROUP = "defaultGroup"
K_PLT_INST = "platformInstallers"
K_INST = "installers"
K_PLT_DEF = "default"
K_APP = "apps"
K_GROUP = "group"


def _assert_no_duplicates(items: list[dict[str, Any]], kind: str):
    by_name: dict[str, list[str]] = {}
    for item in items:
        by_name.setdefault(item["name"], []).append(item.get("_file", "?"))
    dupes = {name: files for name, files in by_name.items() if len(files) > 1}
    if dupes:
        details = "; ".join(
            f"{name!r} declared in {', '.join(files)}" for name, files in dupes.items()
        )
        raise InstallScriptError(f"Duplicate {kind}: {details}")


def _merge_nodes(file_path: Path, merged: dict[str, Any]):
    json_data = json.loads(file_path.read_text(encoding="utf-8"))
    if K_DEF_GROUP in json_data:
        default_group_name = str(json_data[K_DEF_GROUP])
    else:
        default_group_name = re.sub(
            "^apps[-_]*", "", file_path.stem, flags=re.IGNORECASE
        )

    # platformInstallers
    if K_PLT_INST in json_data:
        assert isinstance(json_data[K_PLT_INST], dict)
        curr_plt_inst: dict[str, Any] = json_data[K_PLT_INST]
        merged_plt_inst: dict[str, Any] = merged.setdefault(K_PLT_INST, {})

        # arbitrary platform
        for curr_plt_key, current_platform in curr_plt_inst.items():
            current_platform: dict[str, Any]
            merged_platform: dict[str, Any] = merged_plt_inst.setdefault(
                curr_plt_key, {}
            )

            # default installer for platform
            if K_PLT_DEF in current_platform:
                if K_PLT_DEF not in merged_platform:
                    merged_platform[K_PLT_DEF] = current_platform[K_PLT_DEF]
                else:
                    raise InstallScriptError(
                        f"Multiple default installers for a {curr_plt_key}"
                    )
            # installer list
            if K_INST in current_platform:
                assert isinstance(current_platform[K_INST], list)
                current_platform_installers: list[dict[str, Any]] = current_platform[
                    K_INST
                ]
                for inst in current_platform_installers:
                    inst["_file"] = file_path.stem
                merged_platform.setdefault(K_INST, []).extend(current_platform[K_INST])
                _assert_no_duplicates(
                    merged_platform[K_INST], f"installer for {curr_plt_key}"
                )

    # apps
    merged.setdefault(K_APP, [])
    if K_APP in json_data:
        assert isinstance(json_data[K_APP], list)
        current_apps: list[dict[str, Any]] = json_data[K_APP]
        for x in current_apps:
            x["_file"] = file_path.stem
            if K_GROUP not in x and default_group_name:
                x[K_GROUP] = default_group_name
        merged[K_APP].extend(json_data[K_APP])
        _assert_no_duplicates(merged[K_APP], "app")


@dataclass
class Overseer:
    _merged_source_json: dict[str, Any] = field(repr=False)
    app_filter: ComplexFilter
    installers: list[Installer]
    default_installer: Installer
    report: Report = field(default_factory=Report)
    _all_parsable_stems: list[AppRequestStem] | None = field(repr=False, default=None)
    _all_parsable_apps: list[AppRequest] | None = field(repr=False, default=None)
    _all_installable_apps: list[AppRequest] | None = field(repr=False, default=None)

    def all_parsable_apps(self):
        """
        All app requests that have valid install instruction for the current platform.
        """
        if self._all_parsable_apps is None:
            default_group = self._merged_source_json.get("defaultGroup")
            app_node = self._merged_source_json["apps"]
            assert isinstance(app_node, list)
            apps = [
                self.__stem_to_full(self.__parse_app_request_stem(n, default_group), n)
                for n in app_node
            ]
            self._all_parsable_apps = sorted(
                [a for a in apps if a and self.app_filter.filter(a)],
                key=lambda x: (x.group, x.app_name),
            )
        return self._all_parsable_apps

    def all_parsable_stems(self):
        """
        All app request stems that are syntactically correct
        """
        if self._all_parsable_stems is None:
            default_group = self._merged_source_json.get("defaultGroup")
            app_node = self._merged_source_json["apps"]
            assert isinstance(app_node, list)
            stems = [self.__parse_app_request_stem(n, default_group) for n in app_node]
            self._all_parsable_stems = sorted(
                [s for s in stems if self.app_filter.filter(s)],
                key=lambda x: (x.group, x.app_name),
            )
        return self._all_parsable_stems

    def all_installable_apps(self):
        """
        All app requests that are not already installed and have available installers
        """
        if self._all_installable_apps is None:
            reqs = self.all_parsable_apps()
            installable = [r for r in reqs if self.__is_app_installable(r)]
            self._all_installable_apps = installable
        return self._all_installable_apps

    @classmethod
    def create_context(
        cls,
        *,
        apps_json: Path | None = None,
        filters: Filters | ComplexFilter | None = None,
    ) -> Overseer:
        cpl_filter = ComplexFilter.coerce(filters)

        apps_json = apps_json or paths.APP_JSONS_PATH
        matching_files = sorted(
            f
            for f in apps_json.parent.glob(apps_json.name)
            if not f.name.lower().startswith("schema")
        )
        if not matching_files:
            print(f"No app json files matching {apps_json}", file=sys.stderr)
            sys.exit(1)
        json_data: dict[str, Any] = {}
        for file_path in matching_files:
            _merge_nodes(file_path, json_data)

        if K_PLT_INST not in json_data:
            raise InstallScriptError(
                f"No {K_PLT_INST!r} declared in any of: "
                + ", ".join(f.name for f in matching_files)
            )
        defaults = json_data[K_PLT_INST]

        _platform = target_os.CURRENT_PLATFORM
        _generic_platforms = _platform.get_more_generic_installers(include_self=True)
        current_platform_installers = None
        matched_platform = None
        for gen in _generic_platforms:
            current_platform_installers = defaults.get(str(gen))
            if current_platform_installers:
                matched_platform = gen
                break
        if current_platform_installers is None:
            chain = "->".join(str(x) for x in _generic_platforms)
            print(
                f"Could not find defaults for the following chain: {chain}",
                file=sys.stderr,
            )
            sys.exit(1)

        _installers = [Installer.parse(n) for n in current_platform_installers[K_INST]]
        _default_installer = _installers[0]
        if default_id := current_platform_installers.get(K_PLT_DEF):
            _default_installer = next(
                (x for x in _installers if x.name == default_id), _default_installer
            )
        for get_plat in _generic_platforms:
            if get_plat == matched_platform:
                continue
            if generic_installer := defaults.get(str(get_plat)):
                _installers.extend(
                    Installer.parse(n) for n in generic_installer[K_INST]
                )
        return Overseer(
            installers=_installers,
            app_filter=cpl_filter,
            default_installer=_default_installer,
            _merged_source_json=json_data,
        )

    def _parse_install_instruction(
        self, app: AppRequestStem, node: dict | bool
    ) -> InstallInstruction | None:
        assert node != None
        if isinstance(node, bool):
            if not node:
                return None
            return InstallInstruction(
                installer=self.default_installer, package_name=app.app_name
            )

        installer_key: str | None = node.get("installer")
        script_key: str | None = node.get("script")
        elevated_key: bool | None = node.get("elevated")
        command_key: str | None = node.get("command")
        package_name: str = node.get("name") or app.app_name
        # if the node has only name for the app, treat it as using the default installer
        if package_name and not installer_key:
            installer_key = self.default_installer.name

        if command_key:
            return InstallInstruction(
                installer=Command(
                    cmd=command_key,
                    elevation_required=elevated_key,
                    app_name=app.app_name,
                ),
                package_name=package_name,
            )

        if script_key:
            return InstallInstruction(
                installer=Script(
                    script_path=script_key,
                    elevation_required=elevated_key,
                    app_name=app.app_name,
                ),
                package_name=package_name,
            )

        if installer_key:
            matching_installer = self.get_installer(installer_key)

            if not matching_installer:
                raise AppInstallError(problem=f"installer {installer_key} not found")
            return InstallInstruction(
                installer=matching_installer, package_name=package_name
            )

        raise JsonSyntaxError(problem="app node contains too little information")

    def __parse_app_request_stem(
        self, node: dict, default_group: AppGroup | None
    ) -> AppRequestStem:
        """
        Parses the JSON node and outputs stems of app request
        No report are done
        """
        default_group = default_group or app_group.DEFAULT_GROUP
        app_name: str = node["name"]
        pretty_name: str = node.get("prettyName", app_name)
        check_name: list[str] | None = None
        group_name: str = node.get("group") or default_group.name
        description: str = node.get("description") or ""
        check_name_value = node.get("checkName", True)

        if check_name_value is True:
            check_name = [app_name]
        elif isinstance(check_name_value, str):
            check_name = [check_name_value]

        return AppRequestStem(
            app_name=app_name,
            pretty_name=pretty_name,
            description=description,
            group=AppGroup(group_name),
            check_name=check_name,
        )

    def __stem_to_full(self, ars: AppRequestStem, node: dict) -> AppRequest | None:
        """
        Upgrades a stem to full app request if the installer for the current platform is specified.
        Outputs None if not, or if the install instructions are invalid.
        Fails are reported.
        """
        matching_key = target_os.CURRENT_PLATFORM.find_most_concrete_system(
            [target_os.get_system_from_string(k) for k in node if k != "name"]
        )

        if matching_key is None:
            self.report.report_skip(app=ars, status=Status.SKIPPED_PLATFORM)
            return None
        try:
            instruction = self._parse_install_instruction(ars, node[str(matching_key)])
            if not instruction:
                self.report.report_skip(app=ars, status=Status.SKIPPED_PLATFORM)
                return None
            request = AppRequest.from_stem(ars, instructions=instruction)
            # also check the install-instruction name  against installed packages, unless
            # checkName disabled it entirely
            if (
                request.check_name is not None
                and instruction.package_name not in request.check_name
            ):
                request.check_name = [*request.check_name, instruction.package_name]
            return request
        except InstallScriptError as e:
            self.report.report_fail(app=ars, details=e, status=Status.FAILED)
            return None

    def __is_app_installable(self, app: AppRequest) -> bool:
        """
        Tests the request, checking if the app is already installed and whether the installer is available.
        Fails are reported
        """
        if app.check_name and any(system.is_app_installed(x) for x in app.check_name):
            self.report.report_preinstall(app)
            return False
        if not app.instructions.installer.is_available():
            self.report.report_fail(app=app, status=Status.FAILED_INSTALLER_UNAVAILABLE)
            return False
        return True

    def get_installer(self, name: str) -> Installer | None:
        name = name.casefold()
        return next((i for i in self.installers if i.name.casefold() == name), None)

    def _install_app(self, app: AppRequest):
        try:
            output = app.instructions.execute()
            self.report.report_success(app, output)
        except AppInstallError as a:
            self.report.report_fail(app=app, details=a, status=Status.FAILED)
        except Exception as e:  # noqa: BLE001
            self.report.report_fail(
                app=app,
                details=f"Exception {type(e).__qualname__} - {e}",
                status=Status.FAILED,
            )

    @timed
    def install(self):
        app_requests = self.all_installable_apps()
        needs_sudo = any(x.instructions.elevation_required for x in app_requests)
        if needs_sudo:
            cache_sudo()
        to_prepare = list(
            {
                x.instructions.instruction_name(): x.instructions
                for x in app_requests
                if x.instructions.preparable()
            }.values()
        )

        for prep_inst in to_prepare:
            prep_inst.prepare()

        for app in app_requests:
            self._install_app(app)

        self.report.save_report(paths.report_json_path())

    @timed
    def print_report(self):
        self.report.print(self.app_filter)
