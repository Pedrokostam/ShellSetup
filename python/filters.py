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


class Group(_Filter):
    pass


class Name(_Filter):
    pass


class NotGroup(_Filter):
    pass


class NotName(_Filter):
    pass


Filters: TypeAlias = Sequence[Name | Group | NotName | NotGroup]


class ComplexFilter:
    def __init__(self, filters: Filters):
        self.names = {str(x) for x in filters if isinstance(x, Name)}
        self.groups = {str(x) for x in filters if isinstance(x, Group)}
        self.not_names = {str(x) for x in filters if isinstance(x, NotName)}
        self.not_groups = {str(x) for x in filters if isinstance(x, NotGroup)}

    @classmethod
    def coerce(cls, f: "Filters|ComplexFilter|None") -> "ComplexFilter":
        if isinstance(f, ComplexFilter):
            return f
        if isinstance(f, list):
            return ComplexFilter(f)
        return ComplexFilter([])

    def filter(self, app: AppRequest | AppRequestStem) -> bool:
        if self.names and app.app_name not in self.names:
            return False
        if self.groups and app.group_name not in self.groups:
            return False
        if self.not_names and app.app_name in self.not_names:
            return False
        return not (self.not_groups and app.group_name in self.not_groups)
