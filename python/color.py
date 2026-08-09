from collections.abc import Sequence
from enum import Enum

from python import context


class Color(Enum):
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Style Modifiers
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"

    # Reset Sequence
    RESET = "\033[0m"

    def __str__(self):
        """Allows direct usage in f-strings without typing '.value'."""
        if context.NO_COLOR:
            return ""
        return self.value

    def wrap(self, s: str) -> str:
        return wrap_color(s, self)

    def print(self, s: str, *args, **kwargs):
        color_print(s, self, *args, **kwargs)


def wrap_colors(s: str, colors: Sequence[Color]) -> str:
    return f"{''.join(str(x) for x in colors)}{s}{Color.RESET}"


def wrap_color(s: str, color: Color) -> str:
    return f"{color}{s}{Color.RESET}"


def color_print(s: str, color: Color, *args, **kwargs):
    print(wrap_color(s, color), *args, **kwargs)
