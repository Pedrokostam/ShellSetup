from __future__ import annotations

from functools import total_ordering


@total_ordering
class AppGroup:
    def __init__(self, name: str):
        self.name = name.casefold().replace("-", "_")
        if self.name == "core":
            weight = 0
        elif "core" in self.name:
            weight = 100 + len(self.name.split("_"))
        elif "package" in self.name or "manager" in self.name:
            weight = 1000
        elif self.name == "test":
            weight = 1e100
        else:
            a = self.name.split("_")
            weight = 10000 + len(a)

        self._weight = weight

    def __eq__(self, value: object) -> bool:
        if isinstance(value, AppGroup):
            return self.name == value.name
        return False

    def __lt__(self, other: AppGroup) -> bool:
        return (self._weight, self.name) < (other._weight, other.name)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"{self.name} [{self._weight}]"

    def to_json(self) -> str:
        return self.name


DEFAULT_GROUP = AppGroup("unspecified")
