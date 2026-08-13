from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from python import target_os
from python.app_request import AppRequest, AppRequestStem
from python.context import paths, system
from python.error import (
    AppInstallError,
    InstallScriptError,
    JsonSyntaxError,
)
from python.filters import ComplexFilter, Filters
from python.installation import Command, Installer, InstallInstruction, Script
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
    _source_json: dict = field(repr=False)
    app_filter: ComplexFilter
    report: Report
    installers: list[Installer]
    default_installer: Installer

    @classmethod
    def create_context(
        cls, apps_json: Path, filters: Filters | ComplexFilter | None = None
    ) -> Overseer:
        cpl_filter = ComplexFilter.coerce(filters)
        json_data = json.loads(apps_json.read_text(encoding="utf-8"))
        defaults = json_data["defaults"]

        _platform = target_os.CURRENT_PLATFORM
        _generic_platforms = _platform.get_more_generic_installers()

        current_defaults = defaults[str(_platform)]

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
            report=Report(),
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

    def _test_app_installed(self, app: AppRequest) -> bool:
        if app.check_name and any(system.is_app_installed(x) for x in app.check_name):
            self.report.report_preinstall(app)
            return False
        return True

    def _test_installer(self, app: AppRequest) -> bool:
        appinst = app.instructions
        if (
            isinstance(appinst.installer, Installer)
            and not appinst.installer_available()
        ):
            self.report.report_fail(app=app, status=Status.FAILED_INSTALLER_UNAVAILABLE)
            return False
        return True

    def _parse_app_request(self, node: dict) -> AppRequest | None:
        """
        Parses the JSON node and tests whether it's already installed and whether the installer is available
        Outputs None if any of the stages fails.
        """
        app_name: str = node["name"]
        pretty_name: str = node.get("prettyName", app_name)
        check_name: list[str] | None = None
        group_name: str = node.get("group") or "core"
        description: str = node.get("description") or ""
        check_name_value = node.get("checkName") or True

        if isinstance(check_name_value, bool) and bool(check_name_value):
            check_name = [app_name]
        elif isinstance(check_name_value, str):
            check_name = [check_name_value]

        ars = AppRequestStem(
            app_name=app_name,
            pretty_name=pretty_name,
            description=description,
            group_name=group_name,
        )

        if not self.app_filter.filter(ars):
            self.report.report_skip(ars, status=Status.SKIPPED_CHOICE)
            return None

        matching_key = target_os.CURRENT_PLATFORM.find_most_concrete_system(
            [target_os.get_system_from_string(k) for k in node if k != "name"]
        )

        if matching_key == None:
            self.report.report_skip(app=ars, status=Status.SKIPPED_PLATFORM)
            return None
        try:
            instruction = self._parse_install_instruction(ars, node[str(matching_key)])
            if not instruction:
                self.report.report_skip(app=ars, status=Status.SKIPPED_PLATFORM)
                return None
            if check_name and instruction.package_name not in check_name:
                check_name.append(instruction.package_name)
            request = AppRequest.from_stem(
                ars, instructions=instruction, check_name=check_name
            )
            if self._test_app_installed(request) and self._test_installer(request):
                return request
            return None

        except InstallScriptError as e:
            self.report.report_fail(app=ars, details=e, status=Status.FAILED)
            return None

    def get_installer(self, name: str) -> Installer | None:
        name = name.casefold()
        return next((i for i in self.installers if i.name.casefold() == name), None)

    def _parse_requests(self) -> list[AppRequest]:
        app_node = self._source_json["apps"]
        assert isinstance(app_node, list)

        apps = [self._parse_app_request(n) for n in app_node]

        return [a for a in apps if a]

    def _install_app(self, app: AppRequest):
        try:
            output = app.instructions.execute()
            # output = "mock"
            self.report.report_success(app, output)
        except AppInstallError as a:
            self.report.report_fail(app=app, details=a, status=Status.FAILED)
        except Exception as e:  # noqa: BLE001
            self.report.report_fail(
                app=app, details=f"Exception {type(e).__qualname__} - {e}", status=Status.FAILED
            )

    @timed
    def install(self):
        app_requests = self._parse_requests()

        apps_to_install = [a for a in app_requests if self.app_filter.filter(a)]

        for app in apps_to_install:
            self._install_app(app)

        self.report.save_report(paths.report_json_path())

    @timed
    def print_report(self):
        self.report.print(self.app_filter)
