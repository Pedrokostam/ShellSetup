from collections.abc import Sequence
from typing import TypeAlias

from python.app_request import AppRequest, AppRequestStem


class _Filter:
    def __init__(self, value: str):
        self.value = value.casefold().strip()

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"{type(self).__name__}: {self.value}"


class GroupFilter(_Filter):
    pass


class NameFilter(_Filter):
    pass


class NotGroupFilter(_Filter):
    pass


class NotNameFilter(_Filter):
    pass


class InstallerFilter(_Filter):
    pass


class NotInstallerFilter(_Filter):
    pass


Filters: TypeAlias = Sequence[
    NameFilter
    | GroupFilter
    | InstallerFilter
    | NotNameFilter
    | NotGroupFilter
    | NotInstallerFilter
]


class ComplexFilter:
    def __init__(self, filters: Filters):
        self.names = {str(x).casefold() for x in filters if isinstance(x, NameFilter)}
        self.groups = {str(x).casefold() for x in filters if isinstance(x, GroupFilter)}
        self.installers = {
            str(x).casefold() for x in filters if isinstance(x, InstallerFilter)
        }
        self.not_names = {
            str(x).casefold() for x in filters if isinstance(x, NotNameFilter)
        }
        self.not_groups = {
            str(x).casefold() for x in filters if isinstance(x, NotGroupFilter)
        }
        self.not_installers = {
            str(x).casefold() for x in filters if isinstance(x, NotInstallerFilter)
        }

    @classmethod
    def coerce(cls, f: "Filters|ComplexFilter|None") -> "ComplexFilter":
        if isinstance(f, ComplexFilter):
            return f
        if isinstance(f, list):
            return ComplexFilter(f)
        return ComplexFilter([])

    def filter(self, app: AppRequest | AppRequestStem) -> bool:
        if self.names and app.app_name.casefold() not in self.names:
            return False
        if self.groups and app.group.casefold() not in self.groups:
            return False
        if self.not_names and app.app_name.casefold() in self.not_names:
            return False
        if self.not_groups and app.group.casefold() in self.not_groups:
            return False
        inst_name = (
            app.instructions.installer_name().casefold()
            if isinstance(app, AppRequest)
            else None
        )
        if self.installers and inst_name not in self.installers:
            return False
        return not (self.not_installers and inst_name in self.not_installers)
