from __future__ import annotations

from dataclasses import asdict, dataclass, field

from python.app_group import DEFAULT_GROUP, AppGroup
from python.color import Color
from python.error import AppInstallError

from .installation import Installer, InstallInstruction


def _pretty_dict(d: dict) -> str:
    l = []
    norm_keys = [x for x in d if x != "name" and not ("app" in x and "name" in x)] + [
        "1"
    ]
    max_l = max(len(x) for x in norm_keys)
    for k, v in d.items():
        if ("app" in k and "name" in k) or k == "name":
            s = Color.CYAN.wrap(v)
            if "installer" not in d:
                s += Color.RED.wrap(" (non-installable)")
            l.append(s)
        elif isinstance(v, str):
            l.append(f"   {k:>{max_l}}: {v}")
        elif isinstance(v, list):
            l.append(f"   {k:>{max_l}}: [ {', '.join(v)} ]")
        else:
            l.append(f"   {k:>{max_l}}: {v}")

    return "\n".join(l)


@dataclass
class AppRequestStem:
    app_name: str
    pretty_name: str
    check_name: list[str] | None
    group: AppGroup = field(default_factory=lambda: DEFAULT_GROUP)
    description: str | None = None

    def to_stem(self) -> AppRequestStem:
        return self

    def simple_dict(self) -> dict:
        dicto = asdict(self)
        if self.app_name == self.pretty_name:
            del dicto["pretty_name"]
        if not self.description:
            del dicto["description"]
        dicto["group"] = str(dicto["group"])
        return dicto

    def pretty_form(self) -> str:
        return _pretty_dict(self.simple_dict())


@dataclass
class AppRequest:
    app_name: str
    pretty_name: str
    check_name: list[str] | None
    instructions: InstallInstruction
    group: AppGroup = field(default_factory=lambda: DEFAULT_GROUP)
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
    ) -> AppRequest:
        return AppRequest(
            app_name=ars.app_name,
            pretty_name=ars.pretty_name,
            description=ars.description,
            check_name=ars.check_name,
            group=ars.group,
            instructions=instructions,
        )

    def to_stem(self) -> AppRequestStem:
        return AppRequestStem(
            app_name=self.app_name,
            pretty_name=self.pretty_name,
            group=self.group,
            description=self.description,
            check_name=self.check_name,
        )

    def simple_dict(self) -> dict:
        dicto = self.to_stem().simple_dict()
        dicto["installer"] = self.instructions.installer_name()
        return dicto

    def pretty_form(self) -> str:
        return _pretty_dict(self.simple_dict())
