import sys
from collections.abc import Sequence

SILENT = False
__DEBUG = []

DEBUG_TIME = "time"
DEBUG_MOCK_INSTALL = "install"


def set_debug(key: str | Sequence[str]):
    if isinstance(key, str):
        __DEBUG.append(key.lower())
    else:
        __DEBUG.extend(x.lower() for x in key)


def is_debug(key: str):
    return key in __DEBUG or "*" in __DEBUG


__IS_REDIRECTED = not (sys.stdout.isatty() and sys.stderr.isatty())
NO_COLOR = __IS_REDIRECTED

__OVERRIDE_ELEVATION_SETTING: dict[str, bool | None] = {}


def override_elevation_setting(name: str, new_val: bool | None):
    __OVERRIDE_ELEVATION_SETTING[name] = new_val


def get_elevation_setting(name: str, current_val: bool | None) -> bool | None:
    if "*" in __OVERRIDE_ELEVATION_SETTING:
        return __OVERRIDE_ELEVATION_SETTING["*"]

    if name in __OVERRIDE_ELEVATION_SETTING:
        return __OVERRIDE_ELEVATION_SETTING[name]

    return current_val
