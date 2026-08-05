from dataclasses import dataclass

from . import raise_if_none


@dataclass
class Installer:
    name: str
    command: str | None = None
    elevated: bool | None = False
    prepare: str | None = None

    @classmethod
    def parse(cls, node: dict):
        _name: str | None = node.get("name")
        raise_if_none(_name, "Installer name")
        _command: str | None = node.get("command")
        raise_if_none(_command, "Command string")
        _elevated: bool | None = node.get("elevated")
        _prepare: str | None = node.get("prepare")
        return Installer(
            name=_name or "", command=_command, elevated=_elevated, prepare=_prepare
        )

    def install(self, app_name:str):
        pass



@dataclass
class Command:
    cmd: str
    elevated: bool | None

    def execute(self):
        pass


@dataclass
class InstallInstruction:
    package_name: str
    installer: Installer | Command

    def execute(self):
        if isinstance(self.installer, Installer):
            self.installer.install(self.package_name)
        else:
            self.installer.execute()

