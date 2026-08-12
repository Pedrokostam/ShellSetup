import sys

SILENT = False
DEBUG = False

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
