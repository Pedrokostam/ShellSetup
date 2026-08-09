from __future__ import annotations

from dataclasses import dataclass

from python.error import AppInstallError

from .installer import InstallInstruction, Installer

DEFAULT_GROUP = "core"


@dataclass
class AppRequestStem:
    app_name: str
    pretty_name: str
    group_name: str = DEFAULT_GROUP
    description: str | None = None

    def to_stem(self) -> AppRequestStem:
        return self


@dataclass
class AppRequest:
    app_name: str
    pretty_name: str
    check_name: list[str] | None
    instructions: InstallInstruction
    group_name: str = DEFAULT_GROUP
    description: str | None = None

    def prepare(self, prepared_set: set[str]):
        if not isinstance(self.instructions.installer, Installer):
            return
        inst = self.instructions.installer
        if inst.name in prepared_set:
            return
        print(f"Preparing {inst.name} - {inst.prepare}")
        if inst.prepare_installer():
            prepared_set.add(inst.name)
        else:
            raise AppInstallError(
                problem=f"installer {inst.name} could not be prepared"
            )

    @classmethod
    def from_stem(
        cls,
        ars: AppRequestStem,
        instructions: InstallInstruction,
        check_name: list[str] | None,
    ) -> AppRequest:
        return AppRequest(
            app_name=ars.app_name,
            pretty_name=ars.pretty_name,
            description=ars.description,
            check_name=check_name,
            group_name=ars.group_name,
            instructions=instructions,
        )

    def to_stem(self) -> AppRequestStem:
        return AppRequestStem(
            app_name=self.app_name,
            pretty_name=self.pretty_name,
            group_name=self.group_name,
            description=self.description,
        )
