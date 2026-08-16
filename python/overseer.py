from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AnyStr

from python import target_os
from python import app_group
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


@dataclass
class Overseer:
    _source_json: list[dict[str, Any]] = field(repr=False)
    app_filter: ComplexFilter
    installers: list[Installer]
    default_installer: Installer
    report: Report = field(default_factory=Report)
    _all_parsable_stems: list[AppRequestStem] | None = field(repr=False, default=None)
    _all_parsable_apps: list[AppRequest] | None = field(repr=False, default=None)
    _all_installable_apps: list[AppRequest] | None = field(repr=False, default=None)
    _apps_to_install: list[AppRequest] | None = field(repr=False, default=None)

    def all_parsable_apps(self):
        """
        All app requests that have valid install instruction for the current platform.
        """
        if self._all_parsable_apps is None:
            interim = []
            for full_node in self._source_json:
                default_group = full_node.get("defaultGroup")
                app_node = full_node["apps"]
                assert isinstance(app_node, list)
                apps = [
                    self.__stem_to_full(
                        self.__parse_app_request_stem(n, default_group), n
                    )
                    for n in app_node
                ]
                interim.extend(apps)

            self._all_parsable_apps = sorted(
                [a for a in interim if a], key=lambda x: (x.group, x.app_name)
            )
        return self._all_parsable_apps

    def all_parsable_stems(self):
        """
        All app request stems that are syntactically correct
        """
        if self._all_parsable_stems is None:
            interim = []
            for full_node in self._source_json:
                default_group = full_node.get("defaultGroup")
                app_node = full_node["apps"]
                assert isinstance(app_node, list)
                stems = [
                    self.__parse_app_request_stem(n, default_group) for n in app_node
                ]
                interim.extend(stems)
            self._all_parsable_stems = sorted(
                interim, key=lambda x: (x.group, x.app_name)
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

    def apps_to_install(self):
        """
        All app request that are installable and were not filtered out
        """
        if self._apps_to_install is None:
            installable = self.all_installable_apps()
            self._apps_to_install = [
                a for a in installable if self.app_filter.filter(a)
            ]
        return self._apps_to_install

    @classmethod
    def create_context(
        cls, apps_json: Path, filters: Filters | ComplexFilter | None = None
    ) -> Overseer:
        cpl_filter = ComplexFilter.coerce(filters)
        # TODO: Add grepping for multiple jsons
        json_data = json.loads(apps_json.read_text(encoding="utf-8"))
        defaults = json_data["defaults"]

        _platform = target_os.CURRENT_PLATFORM
        _generic_platforms = _platform.get_more_generic_installers(include_self=True)
        current_defaults = None
        for gen in _generic_platforms:
            current_defaults = defaults.get(str(gen))
            if current_defaults:
                break
        if current_defaults is None:
            chain = "->".join(str(x) for x in _generic_platforms)
            print(
                f"Could not find defaults for the following chain: {chain}",
                file=sys.stderr,
            )
            sys.exit(1)

        _installers = [Installer.parse(n) for n in current_defaults["installers"]]
        _default_installer = _installers[0]
        if default_id := current_defaults.get("default"):
            _default_installer = next(
                (x for x in _installers if x.name == default_id), _default_installer
            )
        for get_plat in _generic_platforms:
            if generic_installer := defaults.get(get_plat):
                _installers.extend(
                    Installer.parse(n) for n in generic_installer["installers"]
                )
        return Overseer(
            installers=_installers,
            app_filter=cpl_filter,
            default_installer=_default_installer,
            _source_json=json_data,
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
        check_name_value = node.get("checkName") or True

        if isinstance(check_name_value, bool) and bool(check_name_value):
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
        app_requests = self.apps_to_install()
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

        apps_to_install = [a for a in app_requests if self.app_filter.filter(a)]

        for app in apps_to_install:
            self._install_app(app)

        self.report.save_report(paths.report_json_path())

    @timed
    def print_report(self):
        self.report.print(self.app_filter)
