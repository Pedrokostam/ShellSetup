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

from python.printing import timed

# Mutable caches, populated in a background thread and at runtime.
__EXISTING_APPS_CALLABLE: dict[str, str | None] = {}


def is_windows() -> bool:
    return os.name == "nt"


def run_lines(cmd: list[str]) -> set[str]:
    if not which(cmd[0]):
        return set()
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"{cmd[0]} error: {e}", file=sys.stderr)
        return set()
    return {ln.strip() for ln in out.stdout.splitlines() if ln.strip()}


@timed
def pacman_existing() -> set[str]:
    return set(run_lines(["pacman", "-Qq"]))


@timed
def rpm_existing() -> set[str]:
    return set(run_lines(["rpm", "-qa", "--qf", "%{NAME}\n"]))


@timed
def dpkg_existing() -> set[str]:
    return set(run_lines(["dpkg-query", "-f", "${binary:Package}\n", "-W"]))


@timed
def npm_existing() -> set[str]:
    if not which("npm"):
        return set()
    try:
        out = subprocess.run(
            "npm list --global --depth=0 --json",
            shell=True,
            capture_output=True,
            check=True,
            text=True,
        )
        npm_json: dict = json.loads(out.stdout)
        return set(npm_json.get("dependencies", {}).keys())
    except Exception as e:  # noqa: BLE001
        print(f"npm error: {e}", file=sys.stderr)
        return set()


@timed
def scoop_existing() -> set[str]:
    if not which("scoop"):
        return set()
    # scoop is a shim on Windows; shell=True resolves it via PATHEXT.
    out = subprocess.run(
        "scoop export", capture_output=True, text=True, shell=True, check=False
    )
    try:
        data = json.loads(out.stdout)
        return {a["Name"] for a in data.get("apps", [])}
    except (json.JSONDecodeError, KeyError) as e:
        print(f"scoop error: {e}", file=sys.stderr)
        return {ln.split()[0] for ln in out.stdout.splitlines() if ln.strip()}


@timed
def winget_existing() -> set[str]:
    if not which("winget"):
        return set()
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
    except (json.JSONDecodeError, OSError) as e:
        print(f"winget error: {e}", file=sys.stderr)
    finally:
        tmp.unlink(missing_ok=True)
    return ids


@timed
def get_apps_from_managers() -> set[str]:
    from python import target_os

    pool: list[collections.abc.Callable[[], set[str]]] = [npm_existing]
    platform = target_os.CURRENT_PLATFORM
    if isinstance(platform, target_os.Windows):
        pool.append(winget_existing)
        pool.append(scoop_existing)
    if isinstance(platform, target_os.Arch):
        pool.append(pacman_existing)
    if isinstance(platform, (target_os.Fedora, target_os.OpenSuse)):
        pool.append(rpm_existing)
    if isinstance(platform, target_os.Debian):
        pool.append(dpkg_existing)

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(f) for f in pool]
        return set().union(*[f.result() for f in futures])


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


__EXISTING_APPS_MANAGERS = LazySet(get_apps_from_managers)


def refresh_PATH():
    from python import target_os

    if target_os.is_windows():
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
    none_keys = [k for k, v in __EXISTING_APPS_CALLABLE.items() if v is None]
    for key in none_keys:
        del __EXISTING_APPS_CALLABLE[key]


def which(app: str, refresh: bool = False) -> str | None:
    if refresh:
        refresh_PATH()
    dict_val = __EXISTING_APPS_CALLABLE.get(app, -13)
    if not isinstance(dict_val, int):
        return dict_val
    new_val = shutil.which(app)
    __EXISTING_APPS_CALLABLE[app] = new_val
    return new_val


def is_app_installed(app: str) -> bool:
    if which(app):
        return True
    return app in __EXISTING_APPS_MANAGERS


def refresh_manager_apps():
    __EXISTING_APPS_MANAGERS.refresh()

NEWEST_POWERSHELL_ENV = "NEWEST_POWERSHELL"
if p7 := which("pwsh"):
    pwsh_exe = p7
elif p5 := which("powershell"):
    pwsh_exe = p5
else:
    pwsh_exe = "THERE_IS_NO_POWERSHELL_ON_THIS_SYSTEM"
os.environ[NEWEST_POWERSHELL_ENV] = pwsh_exe
