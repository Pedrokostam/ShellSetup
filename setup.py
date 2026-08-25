#!/usr/bin/env python3
"""Machine setup: git config, oh-my-posh, fonts, pwsh + modules, shell profiles, apps.

This script is stdlib only and requires at least Python 3.9
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from install_apps import install
from python import extprocess
from python.arguments import parse_setup
from python.color import Color, wrap_color
from python.context import flags, logs, paths, system
from python.context.system import NEWEST_POWERSHELL_ENV, is_windows, which
from python.filters import ComplexFilter, GroupFilter, NameFilter


def pwsh_exe() -> str | None:
    return os.getenv(NEWEST_POWERSHELL_ENV)


def run(cmd, shell: bool = False, **kwargs) -> subprocess.CompletedProcess[str]:
    if shell:
        return extprocess.run_shell(cmd, **kwargs)
    return extprocess.run(cmd, **kwargs)


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
    if file.exists():
        current_lines = file.read_text().splitlines()
    else:
        current_lines = []
    if not any(marker in ln for ln in current_lines):
        file.write_text(f"\n{line}\n")
        return True
    return False


def setup_git() -> None:
    if not which("git"):
        print("Git is not installed! Aliases will not be added!", file=sys.stderr)
        return
    custom_config_path = str(
        (paths.SHELL_SETUP_DIR / "git" / "myconfig.gitconfig").resolve()
    )
    output = run(["git", "config", "--global", "--get-all", "include.path"])
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
    if is_windows():
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
        )
        found = bool(out.stdout.strip())
    else:
        out = run("fc-list | grep -i FantasqueSans", shell=True)
        found = bool(out.stdout.strip())
    if found:
        print(wrap_color("Font is already installed", Color.CYAN))
        return
    if not which("oh-my-posh"):
        print("Cannot install font (oh-my-posh missing)", file=sys.stderr)
        return
    print("Installing font...")
    run(["oh-my-posh", "font", "install", font])


def setup_omp():
    if not which("oh-my-posh"):
        print("Cannot setup oh-my-posh (missing)", file=sys.stderr)
        return


def setup_pwsh_modules(no_modules: bool = False) -> None:
    if no_modules:
        return
    pwsh = which("pwsh")
    if not pwsh:
        print("pwsh not available; skipping module installation.", file=sys.stderr)
        return
    script_path = str(
        (paths.SHELL_SETUP_DIR / "pwsh" / "Install-Modules.ps1").resolve()
    )
    run([pwsh, "-NoProfile", "-File", script_path])


def add_to_powershell_profile(powershell_exe: str):
    pwsh = which(powershell_exe)
    if not pwsh:
        print(
            f"{powershell_exe} not available; skipping {powershell_exe} profile setup.",
            file=sys.stderr,
        )
        return
    profile_path = run([pwsh, "-NoProfile", "-Command", "$PROFILE"]).stdout.strip()
    custom = (paths.SHELL_SETUP_DIR / "pwsh" / "Profile_Kostam.ps1").resolve()
    append_once(Path(profile_path), f". '{custom}'", marker="Profile_Kostam.ps1")


def setup_profiles() -> None:
    home = Path.home()
    # bash and fish are not on windows
    # or rather they maybe can be there, but you should prefer to use them via WSL
    if not system.is_windows():
        bashrc_path = paths.SHELL_SETUP_DIR / "bash" / "bashrc_kostam.sh"
        if bashrc_path.exists():
            append_once(
                home / ".bashrc",
                f'source "{bashrc_path}"',
            )

        local_bin_path = home / ".local" / "bin"
        append_once(home / ".profile", f'export PATH="$PATH:{local_bin_path}"')
        profile_path = paths.SHELL_SETUP_DIR / "bash" / "profile_kostam.sh"
        if profile_path.exists():
            append_once(home / ".profile", f'source "{profile_path}"')

        if which("fish"):
            append_once(
                home / ".config" / "fish" / "config.fish",
                f'source "{paths.SHELL_SETUP_DIR / "fish" / "profile_kostam.fish"}"',
            )

    if system.is_windows():
        add_to_powershell_profile("powershell")
    add_to_powershell_profile("pwsh")


def main() -> None:
    filters = parse_setup(__doc__)
    arg_filter = ComplexFilter.coerce(filters)
    first_filters = ComplexFilter.coerce(
        [
            GroupFilter(x)
            for x in ["core", "core_linux", "package_managers", "shells", "languages"]
        ]
    ).subtract(arg_filter)
    print(first_filters)
    initial_report = install(filters=first_filters)
    print("\nRefreshing environment")
    system.refresh_PATH()
    system.refresh_manager_apps()
    print()
    setup_git()
    setup_profiles()
    setup_pwsh_modules()
    setup_font()
    second_report = install(filters)
    initial_report.merge_reports(second_report).print()
    if flags.is_debug(flags.DEBUG_TIME):
        logs.print_time_logs()


if __name__ == "__main__":
    main()
