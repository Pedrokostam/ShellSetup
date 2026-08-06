from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path

from python import timed
from python.app_request import AppRequest, SkippedApp
from python.color import Color, color_print, wrap_color
from python.error import (
    AppInstallError,
    InstallScriptError,
    JsonSyntaxError,
)

from .installer import Command, Installer, InstallInstruction, Script
from .not_installed import NotInstalled
from .report import Report
from .target_os import *


def is_elevated() -> bool:
    if os.name == "nt":
        import ctypes

        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except OSError:
            return False
    return os.geteuid() == 0


def parse_os_release() -> dict[str, str]:
    data: dict[str, str] = {}
    p = Path("/etc/os-release")
    if not p.exists():
        return data
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k] = v.strip().strip('"').strip("'")
    return data


def run_lines(cmd: list[str]) -> list[str]:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]


def detect_platform() -> AnyOs:
    if platform.system() == "Windows":
        return Windows()
    osrel = parse_os_release()
    # original only checked ID_LIKE, which is absent on pure debian/arch; include ID.
    ident = f"{osrel.get('ID', '')} {osrel.get('ID_LIKE', '')}".lower()
    if "ubuntu" in ident or "debian" in ident:
        return Debian()
    if "arch" in ident or "cachy" in ident:
        return Arch()
    # RHEL clones carry "rhel" in ID_LIKE; exclude them (their repos lack many of these apps).
    if "fedora" in ident and "rhel" not in ident:
        return Fedora()
    if "suse" in ident:
        return OpenSuse()
    raise OSError(f"Unrecognized Linux OS: {osrel.get('ID', '?')}")


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
        with ThreadPoolExecutor() as executor:
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


def existing_apps(platform: AnyOs) -> set[str]:
    if platform == Windows():
        return windows_existing()
    if platform == Arch():
        return set(run_lines(["pacman", "-Qq"]))
    if platform == Fedora() or platform == OpenSuse():
        return set(run_lines(["rpm", "-qa", "--qf", "%{NAME}\n"]))
    if platform == Debian():
        return set(run_lines(["dpkg-query", "-f", "${binary:Package}\n", "-W"]))
    return set()


@dataclass
class Overseer:
    _source_json: dict = field(repr=False)
    platform: AnyOs  # Never a generic system
    report: Report
    existing: set[str] = field(repr=False)
    is_elevated: bool
    installers: list[Installer]
    default_installer: Installer
    prepared: set[str] = field(default_factory=set)
    _silent: bool = False

    @classmethod
    @timed
    def create_context(cls, apps_json: Path, silent:bool=False) -> 'Overseer':
        json_data = json.loads(apps_json.read_text(encoding="utf-8"))
        defaults = json_data["defaults"]

        _platform = detect_platform()
        _generic_platforms = _platform.get_more_generic_installers()
        _is_elevated = is_elevated()

        current_defaults = defaults[str(_platform)]

        _installers = [Installer.parse(n) for n in current_defaults["installers"]]
        _default_installer = _installers[0]
        if default_id := current_defaults.get("default"):
            _default_installer = next(
                (x for x in _installers if x.name == default_id), _default_installer
            )
        for get_plat in _generic_platforms:
            if generic_installer := defaults.get(get_plat):
                _installers.extend(
                    Installer.parse(n) for n in generic_installer["installers"]
                )

        _existing = existing_apps(_platform)

        return Overseer(
            platform=_platform,
            existing=_existing,
            is_elevated=_is_elevated,
            installers=_installers,
            default_installer=_default_installer,
            _source_json=json_data,
            _silent=silent,
            report=Report(silent=silent)
        )

    def _parse_install_instruction(
        self, app_name: str, node: dict | bool
    ) -> InstallInstruction | None:
        assert node != None
        if isinstance(node, bool):
            if not node:
                return None
            return InstallInstruction(
                installer=self.default_installer, package_name=app_name
            )

        installer_key: str | None = node.get("installer")
        script_key: str | None = node.get("script")
        elevated_key: bool | None = node.get("elevated")
        command_key: str | None = node.get("command")
        package_name: str = node.get("name") or app_name
        # if the node has only name for the app, treat it as using the default installer
        if package_name and not installer_key:
            installer_key = self.default_installer.name

        if command_key:
            return InstallInstruction(
                installer=Command(cmd=command_key, elevation_required=elevated_key),
                package_name=package_name,
            )

        if script_key:
            return InstallInstruction(
                installer=Script(
                    script_path=script_key, elevation_required=elevated_key
                ),
                package_name=package_name,
            )

        if installer_key:
            matching_installer = self.get_installer(installer_key)
            if not matching_installer:
                raise AppInstallError(
                    app=app_name, problem=f"installer {installer_key} not found"
                )
            return InstallInstruction(
                installer=matching_installer, package_name=package_name
            )

        raise JsonSyntaxError(problem="app node contains too little information")

    def _parse_app_request(self, node: dict) -> AppRequest | SkippedApp:
        app_name: str = node["name"]
        check_name: list[str] | None = None
        check_name_value = node.get("checkName") or True
        if isinstance(check_name_value, bool) and bool(check_name_value):
            check_name = [app_name]
        elif isinstance(check_name_value, str):
            check_name = [check_name_value]

        matching_key = self.platform.find_most_concrete_system(
            [get_system_from_string(k) for k in node if k != "name"]
        )

        if matching_key == None:
            return SkippedApp(
                app_name=app_name, reason="Not requested for this platform"
            )
        try:
            instruction = self._parse_install_instruction(
                app_name, node[str(matching_key)]
            )
            if not instruction:
                return SkippedApp(
                    app_name=app_name, reason="Not requested for this platform"
                )

            if check_name and instruction.package_name not in check_name:
                check_name.append(instruction.package_name)

            return AppRequest(
                app_name=app_name, check_name=check_name, instructions=instruction
            )

        except InstallScriptError as e:
            return SkippedApp(app_name=app_name, reason=str(e))

    def get_installer(self, name: str) -> Installer | None:
        name = name.casefold()
        return next((i for i in self.installers if i.name.casefold() == name), None)

    def _parse_requests(self) -> list[AppRequest | SkippedApp]:
        app_node = self._source_json["apps"]
        assert isinstance(app_node, list)

        apps = [self._parse_app_request(n) for n in app_node]

        return apps

    def _filter_apps(self, reqs: list[AppRequest | SkippedApp]) -> list[AppRequest]:
        remaining = []
        for app in reqs:
            if isinstance(app, SkippedApp):
                self.report.skipped(app)
                continue
            if app.check_name:
                if any(c in self.existing for c in app.check_name):
                    self.report.preinstalled(app)
                    continue
                if any(shutil.which(x) for x in app.check_name):
                    self.report.preinstalled(app)
                    continue
            if (
                isinstance(app.instructions.installer, Installer)
                and not app.instructions.installer_available()
            ):
                self.report.failed(NotInstalled.installer_unavailable(app))

            remaining.append(app)
        return remaining

    def _install_app(self, app: AppRequest):
        if not self._silent:
            print(
                f"Installing {wrap_color(app.app_name, Color.CYAN)} with {app.instructions.installer_name()}... ",
                end="",
            )
        if (
            app.instructions.elevation_required() != None
            and app.instructions.elevation_required() != self.is_elevated
        ):
            ni = (
                NotInstalled.elevation_forbiden(app)
                if self.is_elevated
                else NotInstalled.elevation_required(app)
            )
            self.report.failed(ni)
            return
        try:
            output = app.instructions.execute()
            # output = "mock"
            self.report.succeeded(app, output)
            if not self._silent:
                color_print("SUCCESS", Color.GREEN)
        except Exception as e:  # noqa: BLE001
            self.report.failed(NotInstalled(app=app, reason=str(e)))
            if not self._silent:
                color_print("FAILED", Color.RED)

    @timed
    def install(self):
        app_requests = self._parse_requests()
        print(f"Parsed {len(app_requests)} app requests from the file")

        apps_to_install = self._filter_apps(app_requests)
        if self.report.preinstalled_apps:
            color_print("Apps already installed:", Color.YELLOW, end=" ")
            print(*(a.app_name for a in self.report.preinstalled_apps), sep=", ")
        if self.report.not_installed_apps:
            color_print("Apps that won't be installed:", Color.RED)
        for a in self.report.not_installed_apps:
            print(f"   {a.name()} - {wrap_color(a.reason, Color.RED)}")
        if apps_to_install:
            color_print("Apps to install:", Color.GREEN, end="")
            print(*(a.app_name for a in apps_to_install), sep=", ")
        else:
            color_print("No apps to install", Color.GREEN)

        for app in apps_to_install:
            self._install_app(app)

        if not self._silent:
            for f in self.report.failed_apps:
                print(str(f))
