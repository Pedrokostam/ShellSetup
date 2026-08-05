#!/usr/bin/env python3
"""Machine setup: git config, oh-my-posh, fonts, pwsh + modules, shell profiles, apps.

Run under Python 3.9+.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from python.color import Color, wrap_color

if sys.version_info < (3, 9):  # noqa: UP036
    sys.exit("Python 3.9+ required")

SCRIPT_DIR = Path(__file__).resolve().parent
INSTALL_APPS = str(SCRIPT_DIR / "install_apps.py")
REPORT_JSON = SCRIPT_DIR / "install_report.json"

ELEVATION_REQUIRED = "Elevation required"
ELEVATION_FORBIDDEN = "Non-elevated user required"


def is_windows() -> bool:
    return platform.system() == "Windows"


def pwsh_exe() -> str | None:
    return shutil.which("pwsh") or (
        shutil.which("powershell") if is_windows() else None
    )


def run(cmd, capture: bool = False, shell: bool = False):
    return subprocess.run(
        cmd, capture_output=capture, text=True, shell=shell, check=False
    )


def confirm(prompt: str, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    try:
        ans = input(prompt + " ").strip().lower()
    except EOFError:
        return False
    return ans == "" or ans.startswith("y")


def append_once(file: Path, line: str, marker: str | None = None) -> None:
    marker = marker or line
    file.parent.mkdir(parents=True, exist_ok=True)
    if file.exists() and any(marker in ln for ln in file.read_text().splitlines()):
        print(f"Already present in {file}")
        return
    with file.open("a", encoding="utf-8") as f:
        f.write(f"\n{line}\n")
    print(f"Added to {file}: {line}")


def setup_git() -> None:
    if not shutil.which("git"):
        print("Git is not installed! Aliases will not be added!", file=sys.stderr)
        return
    cfg = str((SCRIPT_DIR / "git" / "myconfig.gitconfig").resolve())
    out = run(["git", "config", "--global", "--get-all", "include.path"], capture=True)
    existing = [
        os.path.normcase(os.path.normpath(e.strip()))
        for e in out.stdout.splitlines()
        if e.strip()
    ]
    if os.path.normcase(os.path.normpath(cfg)) in existing:
        print(f"File '{cfg}' already included in the global git configuration")
        return
    print(f"Including file '{cfg}' in the global git configuration...")
    run(["git", "config", "--global", "--add", "include.path", cfg])


def ensure_pwsh() -> None:
    if shutil.which("pwsh"):
        return
    print("Installing PowerShell 7...")
    if is_windows():
        if not shutil.which("winget"):
            print("winget not found; cannot install PowerShell.", file=sys.stderr)
            return
        run(
            [
                "winget",
                "install",
                "--id",
                "Microsoft.PowerShell",
                "-e",
                "--accept-package-agreements",
                "--accept-source-agreements",
                "--disable-interactivity",
                "--source",
                "winget",
            ]
        )
    elif shutil.which("yay"):
        # powershell-bin is an AUR package, so an AUR helper is required here.
        run(["yay", "-Sy", "--noconfirm", "powershell-bin"])
    elif shutil.which("apt"):
        run(["sudo", str(SCRIPT_DIR / "bash" / "ubuntu_pwsh_install_script.sh")])
    elif shutil.which("dnf"):
        # pwsh is not in Fedora repos; register the Microsoft RHEL repo. Writing the .repo
        # file directly avoids the dnf4/dnf5 config-manager syntax split.
        run(
            "sudo rpm --import https://packages.microsoft.com/keys/microsoft.asc",
            shell=True,
        )
        run(
            "curl -sSL https://packages.microsoft.com/config/rhel/9.0/prod.repo "
            "| sudo tee /etc/yum.repos.d/microsoft-prod.repo > /dev/null",
            shell=True,
        )
        run(["sudo", "dnf", "install", "-y", "powershell"])
    elif shutil.which("zypper"):
        run(
            "sudo rpm --import https://packages.microsoft.com/keys/microsoft.asc",
            shell=True,
        )
        run(
            [
                "sudo",
                "zypper",
                "--non-interactive",
                "addrepo",
                "--refresh",
                "https://packages.microsoft.com/config/opensuse/15/prod.repo",
                "microsoft",
            ]
        )
        run(
            [
                "sudo",
                "zypper",
                "--non-interactive",
                "--gpg-auto-import-keys",
                "install",
                "powershell",
            ]
        )
    else:
        print("No supported installer for PowerShell found.", file=sys.stderr)


def setup_oh_my_posh() -> None:
    if shutil.which("oh-my-posh"):
        print("Upgrading oh-my-posh...")
        run(["oh-my-posh", "upgrade"])
        return
    print("Installing oh-my-posh...")
    if is_windows():
        ps = pwsh_exe()
        run(
            [
                ps,
                "-NoProfile",
                "-Command",
                "Set-ExecutionPolicy Bypass -Scope Process -Force; "
                "Invoke-Expression ((New-Object System.Net.WebClient)."
                "DownloadString('https://ohmyposh.dev/install.ps1'))",
            ]
        )
    else:
        run("curl -s https://ohmyposh.dev/install.sh | bash -s", shell=True)


def setup_font() -> None:
    font = "FantasqueSansMono"
    if is_windows():
        ps = pwsh_exe()
        out = run(
            [
                ps,
                "-NoProfile",
                "-Command",
                ("(New-Object System.Drawing.Text.InstalledFontCollection).Families | "
                "Where-Object { $_.Name -ilike '*FantasqueSans*' }"),
            ],
            capture=True,
        )
        found = bool(out.stdout.strip())
    else:
        out = run("fc-list | grep -i FantasqueSans", capture=True, shell=True)
        found = bool(out.stdout.strip())
    if found:
        print(wrap_color("Font is already installed",Color.CYAN))
        return
    print("Installing font...")
    run(["oh-my-posh", "font", "install", font])


def setup_pwsh_modules(no_modules: bool) -> None:
    if no_modules:
        return
    pwsh = shutil.which("pwsh")
    if not pwsh:
        print("pwsh not available; skipping module installation.", file=sys.stderr)
        return
    modules = ["Terminal-Icons", "Posh", "PSProfiler", "WriteProgressPlus"]
    module_list = ", ".join(f"'{m}'" for m in modules)
    script = f"""
if ((Get-PSRepository -Name PSGallery).InstallationPolicy -ne 'Trusted') {{
    Write-Host 'Trusting PSGallery...'
    Set-PSRepository -Name PSGallery -InstallationPolicy Trusted
}}
$scope = 'CurrentUser'
if ($IsLinux -and (id -u) -eq 0) {{ $scope = 'AllUsers' }}
$available = Get-Module -ListAvailable | Select-Object -ExpandProperty Name -Unique
foreach ($m in @({module_list})) {{
    if ($available -notcontains $m) {{
        Write-Host "Installing $m..."
        Install-Module -Name $m -AcceptLicense -Scope $scope
    }}
}}
"""
    run([pwsh, "-NoProfile", "-Command", script])


def setup_profiles() -> None:
    home = Path.home()
    if not is_windows():
        append_once(home / ".profile", f'export PATH="$PATH:{home / ".local" / "bin"}"')
        append_once(
            home / ".bashrc", f'source "{SCRIPT_DIR / "bash" / "bashrc_kostam.sh"}"'
        )
        append_once(
            home / ".profile", f'source "{SCRIPT_DIR / "bash" / "profile_kostam.sh"}"'
        )
        if shutil.which("fish"):
            append_once(
                home / ".config" / "fish" / "config.fish",
                f'source "{SCRIPT_DIR / "fish" / "profile_kostam.fish"}"',
            )

    pwsh = shutil.which("pwsh")
    if not pwsh:
        print("pwsh not available; skipping pwsh profile setup.", file=sys.stderr)
        return
    profile_path = run(
        [pwsh, "-NoProfile", "-Command", "$PROFILE"], capture=True
    ).stdout.strip()
    custom = (SCRIPT_DIR / "pwsh" / "Profile_Kostam.ps1").resolve()
    append_once(Path(profile_path), f". '{custom}'", marker="Profile_Kostam.ps1")


def run_installer(cmd) -> dict:
    subprocess.run(cmd, check=False)
    try:
        return json.loads(REPORT_JSON.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def print_summary(reports: list[dict]) -> None:
    installed = sorted({a for r in reports for a in r.get("installed", [])})
    preinstalled = sorted({a for r in reports for a in r.get("preinstalled", [])})
    present = set(installed) | set(preinstalled)

    not_installed = []
    seen = set()
    for r in reports:
        for n in r.get("not_installed", []):
            key = (n["Name"], n["Reason"])
            if n["Name"] in present or key in seen:
                continue
            seen.add(key)
            not_installed.append(n)

    if installed:
        print("\nInstalled apps")
        for a in installed:
            print(f"  {a}")
    if preinstalled:
        print("\nApps that were already installed")
        for a in preinstalled:
            print(f"  {a}")
    if not_installed:
        print("\nNot installed apps")
        for n in sorted(not_installed, key=lambda x: (x["Reason"], str(x["Name"]))):
            if n["Name"]:
                print(f"  {n['Name']} - {n['Reason']}")


def install_apps(assume_yes: bool) -> None:
    if not confirm("Do you want to proceed with app installation? [Y/n]", assume_yes):
        return
    reports = [run_installer([sys.executable, INSTALL_APPS, "-q"])]

    # elevation retries mirror the original sudo/runuser dance (POSIX only).
    if (
        not is_windows()
        and reports[-1].get("redo_with_elevation")
        and not reports[-1].get("was_elevated")
    ):
        if confirm(
            "Some apps require elevation to install. Attempt sudo? [Y/n]", assume_yes
        ):
            reports.append(
                run_installer(["sudo", "-E", sys.executable, INSTALL_APPS, "-q"])
            )

    if (
        not is_windows()
        and reports[-1].get("redo_without_elevation")
        and reports[-1].get("was_elevated")
    ):
        sudo_user = os.environ.get("SUDO_USER")
        if sudo_user and confirm(
            "Some apps require a non-elevated user. Install them? [Y/n]", assume_yes
        ):
            reports.append(
                run_installer(
                    [
                        "runuser",
                        "-u",
                        sudo_user,
                        "--",
                        sys.executable,
                        INSTALL_APPS,
                        "-q",
                    ]
                )
            )

    print_summary(reports)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "-y", "--yes", action="store_true", help="assume yes for all prompts"
    )
    ap.add_argument(
        "--no-modules", action="store_true", help="skip pwsh module installation"
    )
    args = ap.parse_args()

    setup_git()
    ensure_pwsh()
    setup_oh_my_posh()
    setup_font()
    setup_pwsh_modules(args.no_modules)
    setup_profiles()
    install_apps(args.yes)


if __name__ == "__main__":
    main()
