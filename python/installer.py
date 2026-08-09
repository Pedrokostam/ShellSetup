from __future__ import annotations

from pathlib import Path
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from typing import Literal

from python import context
from python.error import AppInstallError
from python.target_os import AnyOs, is_windows

from . import raise_if_none


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


def __parts(cmd: str) -> list[str]:
    return [x.strip() for x in cmd.split(" ") if x.strip()]


@dataclass
class Installer:
    name: str
    command: str
    check_name: str
    elevation_required: bool | None = False
    prepare: str | None = None
    _available: bool | None = None

    @classmethod
    def parse(cls, node: dict):
        _name: str = raise_if_none(node.get("name"), "Installer name")
        _command: str = raise_if_none(node.get("command"), "Command string")
        _elevated = _get_per_system_elevation(node, context.CURRENT_PLATFORM)
        _prepare: str | None = node.get("prepare")
        _check_name: str = node.get("executableToCheck") or _name
        return Installer(
            name=_name,
            command=_command,
            elevation_required=_elevated,
            prepare=_prepare,
            check_name=_check_name,
        )

    def is_available(self):
        if self._available == None:
            self._available = bool(shutil.which(self.check_name))
        return self._available

    def execute(self, app_name: str) -> str:
        cmd_parts = shlex.split(self.command, posix=not context.is_windows())
        ready_cmd = [part.replace("$name", app_name) for part in cmd_parts]
        print(ready_cmd)
        if context.is_windows():
            full_exe_path = context.which(ready_cmd[0])
            if not full_exe_path:
                raise AppInstallError(problem=f"installer {self.name} is not in PATH")
            # extension = Path(full_exe_path).suffix.lower()
            # if extension in [".cmd", ".bat"]:
            #     ready_cmd = ["cmd.exe", "/c"] + ready_cmd+[]
            # else:
            ready_cmd[0] = full_exe_path
        if self.elevation_required and not context.IS_ELEVATED:
            if context.is_windows():
                # look like its too complicate to bother
                raise AppInstallError(
                    problem="Cannot elevate a Windows installer. Rerun the script with elevation.",
                )

                # exe = ready_cmd[0]
                # args = ", ".join(f'"{x}"' for x in ready_cmd[1:])
                # ps_cmd = f'Start-Process "{exe}" -Verb RunAs -Wait -ArgumentList {args}'
                # ready_cmd = ["powershell","-NoProfile", "-Command", ps_cmd]
            else:
                sudo_cached_result = subprocess.run(
                    ["sudo", "-Nnv"], capture_output=True, check=False
                )
                if sudo_cached_result.returncode != 0:
                    try:
                        subprocess.run(["sudo", "-v"], check=True)  # sudo validate
                    except subprocess.CalledProcessError:
                        raise AppInstallError(problem="Sudo authentication failed")
                ready_cmd = ["sudo", "-n"] + ready_cmd  # add sudo non-interactive
        elif self.elevation_required == False and context.IS_ELEVATED:
            raise AppInstallError(
                problem="Installing the app requires non-elevated user"
            )

        print(*ready_cmd)
        result = subprocess.run(
            ready_cmd,
            shell=False,
            capture_output=True,
            text=True,
            check=False,
        )
        print(f"exit code:{result.returncode}")
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
    elevation_required: bool | None

    def is_available(self) -> Literal[True]:
        return True

    def execute(self):
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
    elevation_required: bool | None

    def is_available(self) -> Literal[True]:
        return True

    def execute(self) -> str:
        abs_path = context.AUXILIARY_INSTALL_SCRIPT_DIR / self.script_path
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
            return self.installer.execute(app_name=self.package_name)
        return self.installer.execute()
