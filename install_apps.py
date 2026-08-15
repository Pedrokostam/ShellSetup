#!/usr/bin/env python3
"""Install apps declared in ./apps/apps.json across several platforms.

This script is stdlib only and requires at least Python 3.9
"""

from __future__ import annotations

import argparse
from enum import StrEnum, auto
import os
import sys
from pathlib import Path
from pprint import pprint
from unittest.mock import patch

# importing ./python.__init__.py automatically checks the python version and elevation status
from python.color import Color
from python.context import flags, paths
from python.filters import (
    ComplexFilter,
    Filters,
    GroupFilter,
    InstallerFilter,
    NameFilter,
    NotGroupFilter,
    NotInstallerFilter,
    NotNameFilter,
)
from python.overseer import Overseer
from python.target_os import CONCRETE_OS


class ListType(StrEnum):
    STEMS = auto()
    PARSABLE = auto()
    INSTALLABLE = auto()
    TO_INSTALL = auto()


def test_parsing(json_path: Path):
    for cos in CONCRETE_OS:
        with patch("python.overseer.detect_platform", return_value=cos):
            ctx = Overseer.create_context(json_path)
            apps = ctx.apps_to_install()
            print("=" * 50)
            print(f"Parsed apps for system {os}:\n")
            for a in apps:
                print(f"   {a}")
            print()
            pprint(ctx)


def print_apps(
    filters: Filters | ComplexFilter | None = None,
    list_type: ListType = ListType.TO_INSTALL,
):
    overseer = Overseer.create_context(paths.APP_JSON_PATH, filters)
    match list_type:
        case ListType.STEMS:
            a = overseer.all_parsable_stems()
        case ListType.PARSABLE:
            a = overseer.all_parsable_apps()
        case ListType.INSTALLABLE:
            a = overseer.all_installable_apps()
        case _:
            a = overseer.apps_to_install()
    pprint(a)


def install(filters: Filters | ComplexFilter | None = None, no_report: bool = False):
    overseer = Overseer.create_context(paths.APP_JSON_PATH, filters)
    overseer.install()
    if not no_report:
        overseer.print_report()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-P", "--plain", action="store_true", help="Disable coloring")
    ap.add_argument("-q", "--quiet", action="store_true")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--group", "-g", nargs="*", default=[])
    ap.add_argument("--name", "-n", nargs="*", default=[])
    ap.add_argument("--installer", "-i", nargs="*", default=[])
    ap.add_argument("--not-group", "-G", nargs="*", default=[])
    ap.add_argument("--not-name", "-N", nargs="*", default=[])
    ap.add_argument("--not-installer", "-I", nargs="*", default=[])
    ap.add_argument("--debug", nargs="*", default=[])
    ap.add_argument(
        "--list",
        action="store_true",
        help="Print all apps from json, applicable to current platform",
    )
    ap.add_argument(
        "--disable-elevation-prohibition",
        action="store_true",
        help="Disables checks guarding against running installer with elevation==False when elevated.",
    )
    args = ap.parse_args()
    print(args)
    if args.plain:
        flags.NO_COLOR = True
    if args.debug:
        flags.set_debug(args.debug)
    if args.test:
        test_parsing(paths.APP_JSON_PATH)
        sys.exit(0)
    if args.disable_elevation_prohibition:
        flags.override_elevation_setting("*", None)
    filters = (
        [NameFilter(x) for x in args.name]
        + [GroupFilter(x) for x in args.group]
        + [InstallerFilter(x) for x in args.installer]
        + [NotNameFilter(x) for x in args.not_name]
        + [NotGroupFilter(x) for x in args.not_group]
        + [NotInstallerFilter(x) for x in args.not_installer]
    )
    print(args)
    print(filters)
    if args.list:
        print_apps()
        sys.exit(0)

    # install(filters=filters)
