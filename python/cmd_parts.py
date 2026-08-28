import os
import re
import shlex
from collections.abc import Sequence
from pathlib import Path

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


def _bieda_escape(x: str) -> str:
    x = x.replace('"', '\\"')
    if " " in x:
        x = '"' + x + '"'
    return x


class CmdParts:
    def __init__(self, cmd: str | Sequence[str]):
        from python.context import system

        if isinstance(cmd, str):
            self.parts = [
                _normalize_part(p) for p in shlex.split(cmd, posix=system.is_windows())
            ]
        else:
            self.parts = [_normalize_part(p) for p in cmd]

    def is_dynamic(self):
        return any(NAME_FIND.match(x) for x in self.parts)

    def substiture_name(self, name: str) -> list[str]:
        if not self.is_dynamic():
            return list(self.parts)
        return [NAME_FIND.sub(name, part) for part in self.parts]

    def prepend(self, value: "str|CmdParts|Sequence[str]"):
        match value:
            case str():
                self.parts.insert(0, value)
            case CmdParts() as other:
                self.parts = other.parts + self.parts
            case _:
                self.parts = list(value) + self.parts

    def to_list(self):
        return self.parts.copy()

    def to_single_string(self):
        return " ".join(_bieda_escape(x) for x in self.parts)

    def __str__(self) -> str:
        return " ".join(self.parts)
