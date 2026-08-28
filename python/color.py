from enum import Enum
from typing import TypeAlias

from python.context import flags


class AnsiColor(Enum):
    BLACK = 30
    RED = 31
    GREEN = 32
    YELLOW = 33
    BLUE = 34
    MAGENTA = 35
    CYAN = 36
    WHITE = 37

    BRIGHT_BLACK = 90
    BRIGHT_RED = 91
    BRIGHT_GREEN = 92
    BRIGHT_YELLOW = 93
    BRIGHT_BLUE = 94
    BRIGHT_MAGENTA = 95
    BRIGHT_CYAN = 96
    BRIGHT_WHITE = 97

    # Style Modifiers
    BOLD = 1
    UNDERLINE = 4

    # Reset Sequence
    RESET = 0

    def _command(self) -> str:
        return str(self)[2:]

    def __str__(self):
        if flags.NO_COLOR:
            return ""
        return f"\033[{self.value}m"

    def _unwrap(self) -> "list[AnsiColor]":
        return [self]

    def wrap(self, s: str) -> str:
        return wrap_color(s, self)

    def print(self, s: str, *args, **kwargs):
        color_print(s, self, *args, **kwargs)

    def __or__(self, value):
        if isinstance(value, AnsiColor):
            return ColorCombination(self, value)
        if isinstance(value, ColorCombination):
            return ColorCombination(self, *value.colors)
        return NotImplemented


class ColorCombination:
    def __init__(self, *colors: "AnsiColor|ColorCombination"):
        self.colors: list[AnsiColor] = [z for x in colors for z in x._unwrap()]

    def __str__(self):
        if flags.NO_COLOR:
            return ""
        return f"\033[{';'.join(str(c.value) for c in self.colors)}m"

    def __or__(self, other):
        if isinstance(other, AnsiColor):
            return ColorCombination(*self.colors, other)
        if isinstance(other, ColorCombination):
            return ColorCombination(*self.colors, *other.colors)
        return NotImplemented

    def wrap(self, s: str) -> str:
        return wrap_color(s, self)

    def _unwrap(self) -> list[AnsiColor]:
        return self.colors

    def print(self, s: str, *args, **kwargs):
        color_print(s, self, *args, **kwargs)


_Color: TypeAlias = AnsiColor | ColorCombination


def wrap_color(s: str, color: _Color) -> str:
    return f"{color}{s}{AnsiColor.RESET}"


def color_print(s: str, color: _Color, *args, **kwargs):
    print(wrap_color(s, color), *args, **kwargs)


INSTALLER_COLOR = AnsiColor.MAGENTA
TIME_COLOR = AnsiColor.BRIGHT_YELLOW
STATUS_OK_COLOR = AnsiColor.GREEN
STATUS_NG_COLOR = AnsiColor.RED
STATUS_UK_COLOR = AnsiColor.RED
INDICATOR_COLOR = AnsiColor.BRIGHT_CYAN
APP_COLOR = AnsiColor.MAGENTA
WARNING_COLOR = AnsiColor.YELLOW
