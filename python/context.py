import os
import sys
from pathlib import Path
from time import strftime

from python.app_query import (
    which,
)
from python.target_os import *
from python.target_os import detect_platform, is_windows

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SHELL_SETUP_DIR = Path(__file__).resolve().parent.parent
APP_JSON_PATH = SHELL_SETUP_DIR / "apps" / "apps.json"
AUXILIARY_INSTALL_SCRIPT_DIR = SHELL_SETUP_DIR / "apps" / "scripts"

IS_REDIRECTED = not (sys.stdout.isatty() and sys.stderr.isatty())
NO_COLOR = IS_REDIRECTED
ELEVATION_PROHIBITION_DISABLED = False
SILENT: bool = False

__PWSH_KEY = "NEWEST_POWERSHELL"

__PREPARED_INSTALLERS: set[str] = set()


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------


def report_json_path() -> Path:
    return SHELL_SETUP_DIR / "reports" / f"report_{strftime('%Y%m%d%H%M%S')}.json"


def __is_elevated() -> bool:
    if is_windows():
        import ctypes

        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except OSError:
            return False
    # on linux, this script cannot be run as root
    return False


def conditional_print(msg: str, *args, **kwargs):
    if SILENT:
        return
    print(msg, *args, **kwargs, flush=True)


def is_prepared(installer: "str | Installer") -> bool:
    from python.installer import Installer

    if isinstance(installer, Installer):
        installer = installer.name
    return installer.casefold() in __PREPARED_INSTALLERS


def report_prepared(installer: "str | Installer"):
    from python.installer import Installer

    if isinstance(installer, Installer):
        installer = installer.name
    __PREPARED_INSTALLERS.add(installer.casefold())


# ---------------------------------------------------------------------------
# Module initialization (derived state)
# ---------------------------------------------------------------------------

IS_ELEVATED: bool = __is_elevated()
CURRENT_PLATFORM = detect_platform()

if p7 := which("pwsh"):
    pwsh_exe = p7
elif p5 := which("powershell"):
    pwsh_exe = p5
else:
    pwsh_exe = "THERE_IS_NO_POWERSHELL_ON_THIS_SYSTEM"
os.environ[__PWSH_KEY] = pwsh_exe
