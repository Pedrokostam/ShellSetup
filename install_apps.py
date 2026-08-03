#!/usr/bin/env python3
"""Install apps declared in apps/apps.json across windows / debian / arch.

Port of Install-Apps.ps1. Stdlib only. Run under the newest available Python;
3.9 is the supported floor.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from python.color import Color, wrap_color, color_print

if sys.version_info < (3, 9):  # noqa: UP036
    sys.exit("Python 3.9+ required")

SCRIPT_DIR = Path(__file__).resolve().parent
APPS_JSON = SCRIPT_DIR / "apps" / "apps.json"
REPORT_JSON = SCRIPT_DIR / "install_report.json"

ELEVATION_REQUIRED = "Elevation required"
ELEVATION_FORBIDDEN = "Non-elevated user required"

_INSTALLER_KEYS = {"name", "command", "elevated", "prepare"}


@dataclass
class Installer:
    name: str
    command: str | None = None
    elevated: bool | None = False
    prepare: str | None = None


@dataclass
class Report:
    installed: list[str] = field(default_factory=list)
    preinstalled: list[str] = field(default_factory=list)
    not_installed: list[dict] = field(default_factory=list)
    was_elevated: bool = False
    redo_without_elevation: bool = False
    redo_with_elevation: bool = False


@dataclass
class Ctx:
    platforms: list[str]
    existing: set[str]
    is_elevated: bool
    installers: list[Installer]
    default_installer: Installer
    prepared: set[str] = field(default_factory=set)
    report: Report = field(default_factory=Report)


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


def detect_platforms() -> list[str]:
    if platform.system() == "Windows":
        return ["windows"]
    osrel = parse_os_release()
    # original only checked ID_LIKE, which is absent on pure debian/arch; include ID.
    ident = f"{osrel.get('ID', '')} {osrel.get('ID_LIKE', '')}".lower()
    if "ubuntu" in ident or "debian" in ident:
        return ["ubuntu", "debian"]
    if "arch" in ident or "cachy" in ident:
        return ["arch"]
    # RHEL clones carry "rhel" in ID_LIKE; exclude them (their repos lack many of these apps).
    if "fedora" in ident and "rhel" not in ident:
        return ["fedora"]
    if "suse" in ident:
        return ["opensuse"]
    sys.exit(f"Unrecognized Linux OS: {osrel.get('ID', '?')}")


def run_lines(cmd: list[str]) -> list[str]:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]


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


def existing_apps(platforms: list[str]) -> set[str]:
    if "windows" in platforms:
        return windows_existing()
    if "arch" in platforms:
        return set(run_lines(["pacman", "-Qq"]))
    if "fedora" in platforms or "opensuse" in platforms:
        return set(run_lines(["rpm", "-qa", "--qf", "%{NAME}\n"]))
    return set(run_lines(["dpkg-query", "-f", "${binary:Package}\n", "-W"]))


def run_command(cmd: str) -> int:
    # windows manifest commands are powershell snippets (e.g. scoop bootstrap).
    try:
        if os.name == "nt":
            return subprocess.run(
                ["pwsh", "-NoProfile", "-Command", cmd], check=False
            ).returncode
        return subprocess.run(cmd, shell=True, check=False).returncode
    except OSError as e:
        # e.g. the interpreter (pwsh) or program isn't on PATH; treat as a failed install.
        print(f"Could not run command: {e}")
        return 1


def make_installer(d: dict) -> Installer:
    return Installer(**{k: v for k, v in d.items() if k in _INSTALLER_KEYS})


def resolve_defaults(
    data: dict, platforms: list[str]
) -> tuple[list[Installer], Installer]:
    conf = None
    chosen = None
    for system in platforms:
        c = data.get("defaults", {}).get(system)
        if c:
            conf, chosen = c, system
            break
    if not conf:
        sys.exit(f"No defaults for {platforms}")
    installers = [make_installer(i) for i in conf["installers"]]
    if conf.get("default"):
        default = next((i for i in installers if i.name == conf["default"]), None)
    else:
        default = installers[0]
    if not default or not default.command:
        sys.exit(f"No installer for {chosen}")
    return installers, default


def get_installer(name: str, ctx: Ctx) -> Installer | None:
    return next((i for i in ctx.installers if i.name == name), None)


def report_fail(ctx: Ctx, node: dict, reason: str) -> None:
    print(reason)
    ctx.report.not_installed.append({"Name": node["name"], "Reason": reason})


def report_skip(ctx: Ctx, node: dict) -> None:
    print("Different platform")
    ctx.report.not_installed.append(
        {"Name": node["name"], "Reason": "Different platform"}
    )


def report_preinstalled(ctx: Ctx, node: dict) -> None:
    print(f"Already installed - {node['name']}")
    ctx.report.preinstalled.append(node["name"])


def report_success(ctx: Ctx, node: dict) -> None:
    ctx.report.installed.append(node["name"])


def install(node: dict, ctx: Ctx) -> None:
    print(f"Processing {node['name']}...", end="")

    request = None
    for p in ctx.platforms:
        if p in node:
            if node[p]:
                request = node[p]
            break
    else:
        # no distro-specific key present; fall back to a shared "linux" entry (never on windows).
        # a distro key set to false breaks the loop above, so it skips without hitting the fallback.
        if "windows" not in ctx.platforms and node.get("linux"):
            request = node["linux"]
        # check for the match-all node
        elif node.get("any"):
            request = node["any"]

    req = request if isinstance(request, dict) else {}
    name = req.get("name") or node["name"]

    is_existing = any(
        name.lower() == e.lower() or name.lower() in e.lower() for e in ctx.existing
    )
    check = node.get("checkName")
    if not is_existing and check:
        check_name = check if isinstance(check, str) else node["name"]
        is_existing = shutil.which(check_name) is not None
    if is_existing:
        report_preinstalled(ctx, node)
        return
    if not request:
        report_skip(ctx, node)
        return

    if req.get("installer"):
        inst = get_installer(req["installer"], ctx)
        if inst is None:
            print(f"Invalid installer for {node['name']} - {req['installer']}")
            report_fail(ctx, node, "No installer")
            return
    elif req.get("command"):
        inst = Installer(
            name="__custom__",
            command=req["command"],
            elevated=req.get("elevated", False),
        )
    else:
        inst = ctx.default_installer

    # elevation policy: True = must be elevated, False = must be non-elevated, None = don't check.
    # key absent = inherit the installer's policy; key present (incl. null) = use it verbatim.
    policy = req.get("elevated", inst.elevated)
    if policy is True and not ctx.is_elevated:
        report_fail(ctx, node, ELEVATION_REQUIRED)
        return
    if policy is False and ctx.is_elevated:
        report_fail(ctx, node, ELEVATION_FORBIDDEN)
        return

    if inst.prepare and inst.name not in ctx.prepared:
        print(f"Preparing installer {inst.name}")
        run_command(inst.prepare)
        ctx.prepared.add(inst.name)

    cmd = (req.get("command") or inst.command).replace("$name", name)
    print(f"Executing {cmd}")
    if run_command(cmd) != 0:
        print(f"Could not install {node['name']}")
        report_fail(ctx, node, "Install command failed")
    else:
        report_success(ctx, node)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-q", "--no-summary", action="store_true")
    args = ap.parse_args()

    data = json.loads(APPS_JSON.read_text(encoding="utf-8"))
    platforms = detect_platforms()
    installers, default = resolve_defaults(data, platforms)
    ctx = Ctx(platforms, existing_apps(platforms), is_elevated(), installers, default)

    for app in data["apps"]:
        try:
            install(app, ctx)
        except Exception as e:
            print(f"Error while processing {app['name']}: {e}")
            report_fail(ctx, app, str(e))

    r = ctx.report
    if not args.no_summary and r.installed:
        color_print("\nThe following applications were installed:", Color.BRIGHT_GREEN)
        for n in r.installed:
            print(n)
    if not args.no_summary and r.not_installed:
        color_print(
            "\nThe following applications were NOT installed during this script:",
            Color.YELLOW,
        )
        for n in sorted(r.not_installed, key=lambda x: x["Reason"]):
            print(f"{n['Name']} - {n['Reason']}")

    r.was_elevated = ctx.is_elevated
    r.redo_without_elevation = any(
        n["Reason"] == ELEVATION_FORBIDDEN for n in r.not_installed
    )
    r.redo_with_elevation = any(
        n["Reason"] == ELEVATION_REQUIRED for n in r.not_installed
    )
    REPORT_JSON.write_text(json.dumps(asdict(r), indent=2))


if __name__ == "__main__":
    main()
