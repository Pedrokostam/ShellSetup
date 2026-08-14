from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from time import sleep
from typing import Literal, TypeVar

# from python import context
from python import printing, target_os
from python.cmd_parts import CmdParts
from python.color import Color, wrap_color
from python.context import flags, paths, system
from python.error import AppInstallError
from python.printing import one_line_report
from python.target_os import AnyOs

T = TypeVar("T")


def _raise_if_none(val: T | None, name: str = "Value") -> T:
    if val is None:
        # exe = ready_cmd[0]
        # args = ", ".join(f'"{x}"' for x in ready_cmd[1:])
        # ps_cmd = f'Start-Process "{exe}" -Verb RunAs -Wait -ArgumentList {args}'
        # ready_cmd = ["powershell","-NoProfile", "-Command", ps_cmd]
        raise ValueError(f"{name} missing")
    return val


def is_sudo_cached() -> bool:
    return (
        subprocess.run(["sudo", "-Nnv"], capture_output=True, check=False).returncode
        == 0
    )


def cache_sudo(caller: str | None = None):
    if system.is_windows():
        return
    if is_sudo_cached():
        return
    sudo_cached_result = subprocess.run(
        ["sudo", "-Nnv"], capture_output=True, check=False
    )
    if sudo_cached_result.returncode != 0:
        if caller:
            print(f"{Color.YELLOW.wrap(caller)} requires sudo")
        try:
            subprocess.run(["sudo", "-v"], check=True)  # sudo validate
        except subprocess.CalledProcessError:
            raise AppInstallError(problem="Sudo authentication failed")


def debug_skip() -> str | None:
    import random

    if not flags.is_debug(flags.DEBUG_MOCK_INSTALL):
        return None
    sleep(0.5 + random.random())
    if random.random() > 0.4:
        return "Randomly passed"
    raise AppInstallError(problem="Randomly failed")


def _get_per_system_elevation(node: dict, platform: AnyOs) -> bool | None:
    val = node.get("elevated")
    if val == None:
        return None
    if isinstance(val, bool):
        return val
    if not isinstance(val, dict):
        return None
    fallback = "MISSING"
    plats = platform.get_more_generic_installers(include_self=True)
    for p in plats:
        platform_val: bool | None | str = val.get(str(p), fallback)
        if isinstance(platform_val, bool) or platform_val == None:
            break
    else:
        platform_val = val["default"]
    if platform_val != None:
        platform_val = bool(platform_val)
    return platform_val


@dataclass
class Installer:
    name: str
    command: CmdParts
    check_name: str
    elevation_required: bool | None = False
    prepare: CmdParts | None = None
    dependencies: list[str] | None = None
    _available: bool | None = None

    @classmethod
    def parse(cls, node: dict):
        _name: str = _raise_if_none(node.get("name"), "Installer name")
        _command: str | Sequence[str] = _raise_if_none(
            node.get("command"), "Command string"
        )
        _elevated = _get_per_system_elevation(node, target_os.CURRENT_PLATFORM)
        _prepare: str | Sequence[str] | None = node.get("prepare")
        _deps: list[str] | None = node.get("dependencies")
        _check_name: str = node.get("executableToCheck") or _name
        return Installer(
            name=_name,
            command=CmdParts(_command),
            elevation_required=_elevated,
            prepare=CmdParts(_prepare) if _prepare else None,
            check_name=_check_name,
            dependencies=_deps,
        )

    def is_available(self):
        if self._available == None:
            self._available = bool(shutil.which(self.check_name))
        return self._available

    def is_prepared(self):
        return is_installer_prepared(self.name)

    @one_line_report(initial_msg="Preparing {self.name;YELLOW} - {self.prepare}… ")
    def prepare_installer(self) -> bool:
        if self.prepare == None:
            report_installer_prepared(self)
            return True
        is_prepped = is_installer_prepared(self)
        if is_prepped != None:
            return is_prepped

        if a := debug_skip():
            return bool(a)

        printing.conditional_print(f"Preparing {self.name}... ", end="")
        if not flags.SILENT:
            print(f"Preparing {self.name}... ", end="")
        result = subprocess.run(
            self.prepare.parts, shell=False, check=False, capture_output=True
        )
        success = result.returncode == 0
        report_installer(self, success)
        return success

    @one_line_report(initial_msg="Installing {app_name;MAGENTA} with {self.name}… ")
    def execute(self, app_name: str) -> str:
        if a := debug_skip():
            return a
        elevation_required = flags.get_elevation_setting(
            self.name, self.elevation_required
        )
        if is_installer_prepared(self) == None:
            self.prepare_installer()
        if is_installer_prepared(self) == False:
            raise AppInstallError(
                problem=f"Installer {self.name} could not be prepared"
            )
        ready_cmd = self.command.substiture_name(app_name)
        if target_os.is_windows():
            full_exe_path = system.which(ready_cmd[0])
            if not full_exe_path:
                raise AppInstallError(problem=f"installer {self.name} is not in PATH")
            # extension = Path(full_exe_path).suffix.lower()
            # if extension in [".cmd", ".bat"]:
            #     ready_cmd = ["cmd.exe", "/c"] + ready_cmd+[]
            # else:
            ready_cmd[0] = full_exe_path
        if elevation_required and not system.IS_ELEVATED:
            if target_os.is_windows():
                # look like its too complicate to bother
                raise AppInstallError(
                    problem="Cannot elevate a Windows installer. Rerun the script with elevation.",
                )
            else:
                if not is_sudo_cached():
                    raise AppInstallError(problem="Sudo authentication failed")
                ready_cmd = ["sudo", "-n"] + ready_cmd  # add sudo non-interactive
        elif elevation_required == False and system.IS_ELEVATED:
            raise AppInstallError(
                problem="Installing the app requires non-elevated user"
            )

        result = subprocess.run(
            ready_cmd,
            shell=False,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            err_msg = (
                result.stderr.strip()
                if result.stderr.strip()
                else result.stdout.strip()
            )
            raise AppInstallError(
                problem=err_msg or f"Process exited with code {result.returncode}",
            )
        return str(result.stdout)


@dataclass
class Command:
    cmd: str
    app_name: str
    elevation_required: bool | None

    def is_available(self) -> Literal[True]:
        return True

    @one_line_report(
        initial_msg="Installing {self.app_name;MAGENTA} with custom command… "
    )
    def execute(self) -> str:
        if a := debug_skip():
            return a
        result = subprocess.run(
            self.cmd, shell=True, capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            if result.stderr:
                raise AppInstallError(problem=str(result.stderr))
            else:
                raise AppInstallError(problem=str(result.stdout))
        return str(result.stdout)


@dataclass
class Script:
    script_path: str
    app_name: str
    elevation_required: bool | None

    def is_available(self) -> Literal[True]:
        return True

    @one_line_report(
        initial_msg="Installing {self.app_name;MAGENTA} with script {self.script_path;YELLOW}… "
    )
    def execute(self) -> str:
        if a := debug_skip():
            return a
        abs_path = (paths.AUXILIARY_INSTALL_SCRIPT_DIR / self.script_path).resolve()
        if not abs_path.exists():
            raise AppInstallError(problem=f"script file {self.script_path} not found")
        result = subprocess.run(
            str(abs_path.resolve()),
            shell=True,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            if result.stderr:
                raise AppInstallError(problem=str(result.stderr))
            else:
                raise AppInstallError(problem=str(result.stdout))
        return str(result.stdout)


@dataclass
class InstallInstruction:
    package_name: str
    installer: Installer | Command | Script

    def instruction_name(self) -> str:
        match self.installer:
            case Installer():
                return self.installer.name
            case Command():
                return self.installer.cmd
            case Script():
                return self.installer.script_path

    def installer_name(self) -> str:
        if isinstance(self.installer, Installer):
            return self.installer.name
        if isinstance(self.installer, Script):
            return f"script {self.installer.script_path}"
        else:
            return "command"

    def installer_available(self) -> bool:
        return self.installer.is_available()

    def elevation_required(self) -> bool | None:
        return self.installer.elevation_required

    def execute(self):
        if isinstance(self.installer, Installer):
            if self.installer.elevation_required == True:
                cache_sudo(self.installer.name)
            return self.installer.execute(app_name=self.package_name)
        return self.installer.execute()

    def preparable(self) -> bool:
        if isinstance(self.installer, Installer):
            return bool(self.installer.prepare)
        return False

    def prepare(self) -> bool:
        if isinstance(self.installer, Installer):
            if self.installer.elevation_required == True:
                cache_sudo(self.installer.name)
            return self.installer.prepare_installer()
        return True


__PREPARED_INSTALLERS: dict[str, bool] = {}


def is_installer_prepared(installer: str | Installer) -> bool | None:
    if isinstance(installer, Installer):
        installer = installer.name
    return __PREPARED_INSTALLERS.get(installer.casefold())


def report_installer_prepared(installer: str | Installer):
    if isinstance(installer, Installer):
        installer = installer.name
    __PREPARED_INSTALLERS[installer.casefold()] = True


def report_installer_not_prepared(installer: str | Installer):
    if isinstance(installer, Installer):
        installer = installer.name
    __PREPARED_INSTALLERS[installer.casefold()] = False


def report_installer(installer: str | Installer, status: bool):
    if isinstance(installer, Installer):
        installer = installer.name
    __PREPARED_INSTALLERS[installer.casefold()] = status
