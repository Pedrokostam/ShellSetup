#!/usr/bin/env python3
"""Machine setup: git config, oh-my-posh, fonts, pwsh + modules, shell profiles, apps.

This script is stdlib only and requires at least Python 3.9
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from python import context
from python.color import Color, wrap_color
from python.context import SHELL_SETUP_DIR


def pwsh_exe() -> str | None:
    return context.which("pwsh") or (
        context.which("powershell") if context.is_windows() else None
    )


def run(
    cmd, capture: bool = False, shell: bool = False
) -> subprocess.CompletedProcess[str]:
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


def append_once(file: Path, line: str, marker: str | None = None) -> bool:
    marker = marker or line
    file.parent.mkdir(parents=True, exist_ok=True)
    current_lines = file.read_text().splitlines()
    if file.exists() and any(marker in ln for ln in current_lines):
        return False
    with file.open("a", encoding="utf-8") as f:
        f.write(f"\n{line}\n")
    return True


def setup_git() -> None:
    if not context.which("git"):
        print("Git is not installed! Aliases will not be added!", file=sys.stderr)
        return
    custom_config_path = str((SHELL_SETUP_DIR / "git" / "myconfig.gitconfig").resolve())
    output = run(
        ["git", "config", "--global", "--get-all", "include.path"], capture=True
    )
    existing = [
        os.path.normcase(os.path.normpath(e.strip()))
        for e in output.stdout.splitlines()
        if e.strip()
    ]
    if os.path.normcase(os.path.normpath(custom_config_path)) in existing:
        print(
            f"File '{custom_config_path}' already included in the global git configuration"
        )
        return
    print(f"Including file '{custom_config_path}' in the global git configuration...")
    run(["git", "config", "--global", "--add", "include.path", custom_config_path])


def setup_font() -> None:
    font = "FantasqueSansMono"
    if context.is_windows():
        ps = pwsh_exe()
        out = run(
            [
                ps,
                "-NoProfile",
                "-Command",
                (
                    "(New-Object System.Drawing.Text.InstalledFontCollection).Families | "
                    "Where-Object { $_.Name -ilike '*FantasqueSans*' }"
                ),
            ],
            capture=True,
        )
        found = bool(out.stdout.strip())
    else:
        out = run("fc-list | grep -i FantasqueSans", capture=True, shell=True)
        found = bool(out.stdout.strip())
    if found:
        print(wrap_color("Font is already installed", Color.CYAN))
        return
    if not context.which("oh-my-posh"):
        print("Cannot install font (oh-my-posh missing)", file=sys.stderr)
        return
    print("Installing font...")
    run(["oh-my-posh", "font", "install", font])


def setup_pwsh_modules(no_modules: bool) -> None:
    if no_modules:
        return
    pwsh = context.which("pwsh")
    if not pwsh:
        print("pwsh not available; skipping module installation.", file=sys.stderr)
        return
    script_path = str((SHELL_SETUP_DIR / "pwsh" / "Install-Modules.ps1").resolve())
    run([pwsh, "-NoProfile", "-File", script_path])


def add_to_powershell_profile(powershell_exe: str):
    pwsh = context.which(powershell_exe)
    if not pwsh:
        print(
            f"{powershell_exe} not available; skipping {powershell_exe} profile setup.",
            file=sys.stderr,
        )
        return
    profile_path = run(
        [pwsh, "-NoProfile", "-Command", "$PROFILE"], capture=True
    ).stdout.strip()
    custom = (SHELL_SETUP_DIR / "pwsh" / "Profile_Kostam.ps1").resolve()
    append_once(Path(profile_path), f". '{custom}'", marker="Profile_Kostam.ps1")


def setup_profiles() -> None:
    home = Path.home()
    if not context.is_windows():
        bashrc_path = SHELL_SETUP_DIR / "bash" / "bashrc_kostam.sh"
        if bashrc_path.exists():
            append_once(
                home / ".bashrc",
                f'source "{bashrc_path}"',
            )

        local_bin_path = home / ".local" / "bin"
        append_once(home / ".profile", f'export PATH="$PATH:{local_bin_path}"')
        profile_path = SHELL_SETUP_DIR / "bash" / "profile_kostam.sh"
        if profile_path.exists():
            append_once(home / ".profile", f'source "{profile_path}"')

        if context.which("fish"):
            append_once(
                home / ".config" / "fish" / "config.fish",
                f'source "{SHELL_SETUP_DIR / "fish" / "profile_kostam.fish"}"',
            )

    if context.is_windows():
        add_to_powershell_profile("powershell")
    add_to_powershell_profile("pwsh")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "-y", "--yes", action="store_true", help="assume yes for all prompts"
    )
    ap.add_argument(
        "--no-modules", action="store_true", help="skip pwsh module installation"
    )
    args = ap.parse_args()
    git_exists = context.which("git")
    omp_exists = context.which("oh-my-posh")
    fish_exists = context.which("fish")

    setup_git()
    setup_oh_my_posh()
    setup_font()
    setup_pwsh_modules(args.no_modules)
    setup_profiles()
    install_apps(args.yes)


if __name__ == "__main__":
    main()
