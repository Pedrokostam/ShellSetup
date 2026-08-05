import json
import os
import platform
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from python.app_request import AppRequest, SkippedApp
from python.error import (
    AppInstallError,
    InstallScriptError,
    InstallerError,
    JsonSyntaxError,
)

from .installer import Command, InstallInstruction, Installer
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


def windows_existing() -> set[str]:
    ids: set[str] = set()
    if shutil.which("winget"):
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
    if shutil.which("scoop"):
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
    existing: set[str] = field(repr=False)
    is_elevated: bool
    installers: list[Installer]
    default_installer: Installer
    prepared: set[str] = field(default_factory=set)
    report: Report = field(default_factory=Report)

    @classmethod
    def create_context(cls, apps_json: Path) -> Overseer:
        json_data = json.loads(apps_json.read_text(encoding="utf-8"))
        defaults = json_data["defaults"]

        _platform = detect_platform()
        _is_elevated = is_elevated()

        current_defaults = defaults[str(_platform)]

        _installers = [Installer.parse(n) for n in current_defaults["installers"]]
        _default_installer = _installers[0]
        if default_id := current_defaults.get("default"):
            _default_installer = next(
                (x for x in _installers if x.name == default_id), _default_installer
            )
        _existing = existing_apps(_platform)

        return Overseer(
            platform=_platform,
            existing=_existing,
            is_elevated=_is_elevated,
            installers=_installers,
            default_installer=_default_installer,
            _source_json=json_data,
        )

    def parse_install_instruction(
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
        elevated_key: bool | None = node.get("elevated")
        command_key: str | None = node.get("command")
        package_name: str = node.get("name") or app_name
        # if the node has only name for the app, treat it as using the default installer
        if package_name and not installer_key:
            installer_key = self.default_installer.name

        if command_key:
            return InstallInstruction(
                installer=Command(cmd=command_key, elevated=elevated_key),
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
        print(node)
        print(command_key)
        print(installer_key)
        raise JsonSyntaxError(problem="app node contains too little information")

    def _parse_app_request(self, node: dict) -> AppRequest | SkippedApp:
        app_name: str = node["name"]
        check_name: list[str] | None = None
        check_name_value = node.get("checkName")
        if isinstance(check_name_value, bool) and bool(check_name_value):
            check_name = [app_name]
        elif isinstance(check_name_value, str):
            check_name = [check_name_value]

        matching_key = self.platform.find_most_concrete_system(
            [get_system_from_string(k) for k in node if k != "name"]
        )

        if matching_key == None:
            return SkippedApp(
                app_name=app_name, reason=f"Installer for {self.platform} not found"
            )
        try:
            instruction = self.parse_install_instruction(
                app_name, node[str(matching_key)]
            )
            if not instruction:
                return SkippedApp(
                    app_name=app_name, reason="Disabled for this platform"
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

    def parse_requests(self) -> list[AppRequest | SkippedApp]:
        app_node = self._source_json["apps"]
        assert isinstance(app_node, list)

        apps = [self._parse_app_request(n) for n in app_node]

        return apps
