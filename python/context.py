import collections.abc
import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from time import strftime

from python import timed
from python.installer import Installer
from python.target_os import *
from python.target_os import detect_platform, is_windows

SHELL_SETUP_DIR = Path(__file__).resolve().parent.parent


def report_json_path() -> Path:
    return SHELL_SETUP_DIR / "reports" / f"report_{strftime('%Y%m%d%H%M%S')}.json"


APP_JSON_PATH = SHELL_SETUP_DIR / "apps" / "apps.json"

AUXILIARY_INSTALL_SCRIPT_DIR = SHELL_SETUP_DIR / "apps" / "scripts"

IS_REDIRECTED = not (sys.stdout.isatty() and sys.stderr.isatty())

NO_COLOR = IS_REDIRECTED


def run_lines(cmd: list[str]) -> list[str]:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]


@timed
def scoop_existing() -> set[str]:
    # scoop is a shim on Windows; shell=True resolves it via PATHEXT.
    out = subprocess.run(
        "scoop export", capture_output=True, text=True, shell=True, check=False
    )
    try:
        data = json.loads(out.stdout)
        return {a["Name"] for a in data.get("apps", [])}
    except (json.JSONDecodeError, KeyError):
        return {ln.split()[0] for ln in out.stdout.splitlines() if ln.strip()}


@timed
def winget_existing() -> set[str]:
    ids = set()
    tmp = Path(tempfile.gettempdir()) / "winget_export.json"
    subprocess.run(
        [
            "winget",
            "export",
            "-o",
            str(tmp),
            "--source",
            "winget",
            "--disable-interactivity",
            "--accept-source-agreements",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        if tmp.exists():
            # winget writes a UTF-8 BOM.
            data = json.loads(tmp.read_text(encoding="utf-8-sig"))
            for src in data.get("Sources", []):
                for pkg in src.get("Packages", []):
                    pid = pkg.get("PackageIdentifier")
                    if pid:
                        ids.add(pid)
    except (json.JSONDecodeError, OSError):
        pass
    finally:
        tmp.unlink(missing_ok=True)
    return ids


def windows_existing() -> set[str]:
    is_winget = shutil.which("winget")
    is_scoop = shutil.which("scoop")
    ids: set[str] = set()
    if is_winget and is_scoop:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            winget = executor.submit(winget_existing)
            scoop = executor.submit(scoop_existing)
            ids |= winget.result()
            ids |= scoop.result()
    else:
        if is_winget:
            ids |= winget_existing()
        if is_scoop:
            ids |= scoop_existing()
    return ids


@timed
def get_apps_from_managers(platform: AnyOs | None = None) -> set[str]:
    platform = platform or CURRENT_PLATFORM
    if platform == Windows():
        return windows_existing()
    if platform == Arch():
        return set(run_lines(["pacman", "-Qq"]))
    if platform == Fedora() or platform == OpenSuse():
        return set(run_lines(["rpm", "-qa", "--qf", "%{NAME}\n"]))
    if platform == Debian():
        return set(run_lines(["dpkg-query", "-f", "${binary:Package}\n", "-W"]))
    return set()


class LazySet(collections.abc.Set):
    def __init__(self, target_function):
        self._data: set[str] = set()
        self._thread = threading.Thread(
            target=self._populate, args=(target_function,), daemon=True
        )
        self._thread.start()

    def _populate(self, task):
        self._data = set(task())

    def _wait(self):
        if self._thread.is_alive():
            self._thread.join()

    def __contains__(self, item):
        self._wait()
        return item in self._data

    def __iter__(self):
        self._wait()
        return iter(self._data)

    def __len__(self):
        self._wait()
        return len(self._data)

    def refresh(self):
        self._thread.start()


def __is_elevated() -> bool:
    if is_windows():
        import ctypes

        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except OSError:
            return False
    # on linux, this script cannot be run as root
    return False


IS_ELEVATED: bool = __is_elevated()
ELEVATION_PROHIBITION_DISABLED = False
SILENT: bool = True
CURRENT_PLATFORM = detect_platform()

__EXISTING_APPS_CALLABLE: dict[str, str | None] = {}
__EXISTING_APPS_MANAGERS = LazySet(get_apps_from_managers)


def refresh_PATH():
    if is_windows():
        import winreg

        # Read System PATH
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        ) as key:
            system_path, _ = winreg.QueryValueEx(key, "Path")

        # Read User PATH
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
            try:
                user_path, _ = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                user_path = ""
        os.environ["PATH"] = f"{system_path};{user_path}"
    else:
        shell = os.environ.get("SHELL", "/bin/bash")
        new_path = subprocess.check_output(
            [shell, "-lc", "echo $PATH"], text=True
        ).strip()
        os.environ["PATH"] = new_path
    none_keys = [k for k, v in __EXISTING_APPS_CALLABLE.items() if v == None]
    for key in none_keys:
        del __EXISTING_APPS_CALLABLE[key]


def is_app_installed(app: str) -> bool:
    if which(app):
        return True
    return app in __EXISTING_APPS_MANAGERS


__fallback = 13


def which(app: str, refresh: bool = False) -> str | None:
    if refresh:
        refresh_PATH()
    dict_val = __EXISTING_APPS_CALLABLE.get(app, __fallback)
    if not isinstance(dict_val, int):
        return dict_val
    new_val = shutil.which(app)
    __EXISTING_APPS_CALLABLE[app] = new_val
    return new_val


def refresh_manager_apps():
    __EXISTING_APPS_MANAGERS.refresh()


__PWSH_KEY = "NEWEST_POWERSHELL"

if p7 := which("pwsh"):
    pwsh_exe = p7
elif p5 := which("powershell"):
    pwsh_exe = p5
else:
    pwsh_exe = "THERE_IS_NO_POWERSHELL_ON_THIS_SYSTEM"
os.environ[__PWSH_KEY] = pwsh_exe


__PREPARED_INSTALLERS: set[str] = set()


def is_prepared(installer: str | Installer) -> bool:
    if isinstance(installer, Installer):
        installer = installer.name
    return installer.casefold() in __PREPARED_INSTALLERS


def report_prepared(installer: str | Installer):
    if isinstance(installer, Installer):
        installer = installer.name
    __PREPARED_INSTALLERS.add(installer.casefold())
