#!/usr/bin/env python3
"""Install apps declared in ./apps/apps.json across several platforms.

This script is stdlib only and requires at least Python 3.9
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from pprint import pprint
from unittest.mock import patch

# importing ./python.__init__.py automatically checks the python version and elevation status
from python.app_request import AppRequest, AppRequestStem
from python.arguments import ListArgs, ListType, parse_install_app
from python.context import paths
from python.filters import (
    ComplexFilter,
    Filters,
)
from python.overseer import Overseer
from python.target_os import CONCRETE_OS


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
    as_json: bool = False,
):
    overseer = Overseer.create_context(paths.APP_JSON_PATH, filters)
    match list_type:
        case ListType.STEMS:
            all_apps: Sequence[AppRequest | AppRequestStem] = []
            all_apps.extend(overseer.all_parsable_apps())
            anames = {x.app_name for x in all_apps}
            for s in overseer.all_parsable_stems():
                if s.app_name not in anames:
                    all_apps.append(s)
            title = "all apps in the JSON"
        case ListType.PARSABLE:
            all_apps = overseer.all_parsable_apps()
            title = "all valid apps for the system"
        case ListType.INSTALLABLE:
            all_apps = overseer.all_installable_apps()
            title = "all apps that can be installed"
        case _:
            all_apps = overseer.apps_to_install()
            title = "all apps that would be installed"
    all_apps = sorted(all_apps, key=lambda x: x.app_name)
    print("Listing " + title, file=sys.stderr)
    if as_json:
        print(json.dumps([x.simple_dict() for x in all_apps], indent=3))
    else:
        print(*(x.pretty_form() for x in all_apps), sep="\n")


def install(filters: Filters | ComplexFilter | None = None, no_report: bool = False):
    overseer = Overseer.create_context(paths.APP_JSON_PATH, filters)
    overseer.install()
    if not no_report:
        overseer.print_report()


if __name__ == "__main__":
    parse_res = parse_install_app(__doc__)
    if isinstance(parse_res, ListArgs):
        print_apps(parse_res.filters, parse_res.mode, parse_res.json)
        sys.exit(0)
    install(filters=parse_res)
