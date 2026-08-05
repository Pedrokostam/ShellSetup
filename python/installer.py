from dataclasses import dataclass
import shutil
import subprocess
from typing import Literal

from python import paths
from python.error import AppInstallError

from . import raise_if_none


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
        _elevated: bool | None = node.get("elevated")
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
        ready_cmd = self.command.replace("$name", app_name)
        result = subprocess.run(
            ready_cmd, shell=True, capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            if result.stderr:
                raise AppInstallError(app=app_name, problem=str(result.stderr))
            else:
                raise AppInstallError(app=app_name, problem=str(result.stdout))
        return str(result.stdout)


@dataclass
class Command:
    cmd: str
    elevation_required: bool | None

    def is_available(self) -> Literal[True]:
        return True

    def execute(self, app_name: str):
        result = subprocess.run(
            self.cmd, shell=True, capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            if result.stderr:
                raise AppInstallError(app=app_name, problem=str(result.stderr))
            else:
                raise AppInstallError(app=app_name, problem=str(result.stdout))
        return str(result.stdout)


@dataclass
class Script:
    script_path: str
    elevation_required: bool | None

    def is_available(self) -> Literal[True]:
        return True

    def execute(self, app_name: str) -> str:
        abs_path = paths.AUXILIARY_INSTALL_SCRIPT_DIR / self.script_path
        result = subprocess.run(
            str(abs_path.resolve()), shell=True, capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            if result.stderr:
                raise AppInstallError(app=app_name, problem=str(result.stderr))
            else:
                raise AppInstallError(app=app_name, problem=str(result.stdout))
        return str(result.stdout)


@dataclass
class InstallInstruction:
    package_name: str
    installer: Installer | Command | Script
    
    def installer_name(self)->str:
        if isinstance(self.installer,Installer):
            return self.installer.name
        if isinstance(self.installer,Script):
            return f"script {self.installer.script_path}"
        else:
            return "command"

    def installer_available(self) ->bool:
        return self.installer.is_available()

    def elevation_required(self) -> bool | None:
        return self.installer.elevation_required

    def execute(self):
        return self.installer.execute(self.package_name)
