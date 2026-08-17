from __future__ import annotations

import os
from pathlib import Path
from python.context.system import is_windows

__all__ = [
    "AnyOs",
    "Arch",
    "Debian",
    "Fedora",
    "Linux",
    "OpenSuse",
    "Ubuntu",
    "Windows",
]


class AnyOs:
    def __str__(self) -> str:
        return "any" if type(self) is AnyOs else type(self).__name__.lower()

    def __repr__(self) -> str:
        return str(self)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AnyOs):
            return NotImplemented
        return str(self) == str(other)

    def __hash__(self) -> int:
        return hash(str(self))

    def get_more_generic_installers(self, include_self: bool = False) -> list[str]:
        """
        Returns names of all ancestor classes, except for the one in question
        """
        if include_self:
            return [str(x()) for x in self._get_matching_system_classes()]

        return [
            str(x()) for x in self._get_matching_system_classes() if x != type(self)
        ]

    def _get_matching_system_classes(self):
        """
        Get all ancestor classes excluding object
        """
        return [cls for cls in type(self).mro() if cls is not object]

    def find_most_concrete_system(
        self, available_systems: list[AnyOs | None]
    ) -> AnyOs | None:
        for applicable_os in self._get_matching_system_classes():
            for system_for_app in available_systems:
                if isinstance(applicable_os(), type(system_for_app)):
                    return system_for_app
        return None


class Linux(AnyOs):
    pass


class Windows(AnyOs):
    pass


class Arch(Linux):
    pass


class Fedora(Linux):
    pass


class OpenSuse(Linux):
    pass


class Debian(Linux):
    pass


class Ubuntu(Debian):
    pass


__ALL_OS = [
    Ubuntu(),
    Debian(),
    OpenSuse(),
    Fedora(),
    Arch(),
    Windows(),
    Linux(),
    AnyOs(),
]
CONCRETE_OS = [Ubuntu(), Debian(), OpenSuse(), Fedora(), Arch(), Windows()]


def get_system_from_string(s: str) -> AnyOs | None:
    s = s.lower()
    for os in __ALL_OS:
        if str(os) == s:
            return os
    return None


def __parse_os_release() -> dict[str, str]:
    data: dict[str, str] = {}
    p = Path("/etc/os-release")
    if not p.exists():
        return data
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k] = v.strip().strip('"').strip("'")
    return data


def __detect_platform() -> AnyOs:
    if is_windows():
        return Windows()
    osrel = __parse_os_release()
    ident = f"{osrel.get('ID', '')} {osrel.get('ID_LIKE', '')}".lower()
    if "ubuntu" in ident:
        return Ubuntu()
    if "debian" in ident:
        return Debian()
    if "arch" in ident or "cachy" in ident:
        return Arch()
    # RHEL clones carry "rhel" in ID_LIKE; exclude them
    if "fedora" in ident and "rhel" not in ident:
        return Fedora()
    if "suse" in ident:
        return OpenSuse()
    raise OSError(f"Unrecognized Linux OS: {osrel.get('ID', '?')}")


CURRENT_PLATFORM = __detect_platform()
