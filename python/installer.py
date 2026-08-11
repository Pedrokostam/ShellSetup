from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from python import context
from python.color import wrap_color,Color
from python.error import AppInstallError, InstallScriptError
from python.target_os import AnyOs

from . import DEBUG, raise_if_none

ENV_FIND = re.compile(
    r"\$(?!name\b)({(?P<A>\w+)}|(?P<B>\w+))",
    re.IGNORECASE,
)
NAME_FIND = re.compile(
    r"\$({name}|name)",
    re.IGNORECASE,
)


def _replace_regex(match: re.Match[str]) -> str:
    name = match.group("A") or match.group("B")
    return os.getenv(name, match.group(0))


def _normalize_part(s: str) -> str:
    if "~" in s:
        s = str(Path(s).expanduser())
    s = ENV_FIND.sub(_replace_regex, s)
    return s


class CmdParts:
    def __init__(self, cmd: str | Sequence[str]):
        if isinstance(cmd, str):
            self.parts = [
                _normalize_part(p) for p in shlex.split(cmd, posix=context.is_windows())
            ]
        else:
            self.parts = [_normalize_part(p) for p in cmd]

    def is_dynamic(self):
        return any(NAME_FIND.match(x) for x in self.parts)

    def substiture_name(self, name: str) -> list[str]:
        if not self.is_dynamic():
            return list(self.parts)
        return [NAME_FIND.sub(name, part) for part in self.parts]

    def __str__(self) -> str:
        return " ".join(self.parts)


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
    _available: bool | None = None

    @classmethod
    def parse(cls, node: dict):
        _name: str = raise_if_none(node.get("name"), "Installer name")
        _command: str | Sequence[str] = raise_if_none(
            node.get("command"), "Command string"
        )
        _elevated = _get_per_system_elevation(node, context.CURRENT_PLATFORM)
        _prepare: str | Sequence[str] | None = node.get("prepare")
        _check_name: str = node.get("executableToCheck") or _name
        return Installer(
            name=_name,
            command=CmdParts(_command),
            elevation_required=_elevated,
            prepare=CmdParts(_prepare) if _prepare else None,
            check_name=_check_name,
        )

    def is_available(self):
        if self._available == None:
            self._available = bool(shutil.which(self.check_name))
        return self._available

    def prepare_installer(self) -> bool:
        if self.prepare == None:
            return True
        if not context.SILENT:
            print(f"Preparing {self.name}... ",end='')
        result = subprocess.run(
            self.prepare.parts, shell=False, check=False, capture_output=True
        )
        context.report_prepared(self.name)
        if not context.SILENT:
            if result.returncode==0:
                sc = wrap_color("SUCCESS",Color.GREEN)
            else:
                sc = wrap_color("FAIL",Color.RED)
            print(sc)
        return result.returncode == 0

    def execute(self, app_name: str) -> str:
        if self.prepare and not context.is_prepared(self.name):
            self.prepare_installer()

        ready_cmd = self.command.substiture_name(app_name)
        if not context.SILENT:
            print(f"Installing {app_name} with {self.name}... ")
        if DEBUG:
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
        elif (
            not context.ELEVATION_PROHIBITION_DISABLED
            and self.elevation_required == False
            and context.IS_ELEVATED
        ):
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
        abs_path = (context.AUXILIARY_INSTALL_SCRIPT_DIR / self.script_path).resolve()
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
