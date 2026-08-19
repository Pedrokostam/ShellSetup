#!/usr/bin/env python3
"""Install apps declared in ./apps/apps.json across several platforms.

This script is stdlib only and requires at least Python 3.9
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pprint import pprint
from unittest.mock import patch

# importing ./python.__init__.py automatically checks the python version and elevation status
from python import target_os
from python.app_request import AppRequest, AppRequestStem
from python.arguments import ListArgs, ListType, parse_install_app
from python.context import flags, logs
from python.filters import (
    ComplexFilter,
    Filters,
)
from python.overseer import Overseer
from python.report import Report
from python.target_os import CONCRETE_OS


def test_parsing():
    for cos in CONCRETE_OS:
        with patch("python.target_os.CURRENT_PLATFORM", cos):
            ctx = Overseer.create_context()
            apps = ctx.all_installable_apps()
            print("=" * 50)
            print(f"Parsed apps for system {cos}:\n")
            for a in apps:
                print(f"   {a}")
            print()
            pprint(ctx)


def print_apps(
    filters: Filters | ComplexFilter | None = None,
    list_type: ListType = ListType.INSTALLABLE,
    as_json: bool = False,
):
    overseer = Overseer.create_context(filters=filters)
    match list_type:
        case ListType.STEMS:
            all_apps: Sequence[AppRequest | AppRequestStem] = []
            all_apps.extend(overseer.all_parsable_apps())
            anames = {x.app_name for x in all_apps}
            for s in overseer.all_parsable_stems():
                if s.app_name not in anames:
                    all_apps.append(s)
            all_apps = sorted(all_apps, key=lambda x: (x.group, x.app_name))
            title = "all apps in the JSON"
        case ListType.PARSABLE:
            all_apps = overseer.all_parsable_apps()
            title = f"all valid apps for {target_os.CURRENT_PLATFORM}"
        case _:
            all_apps = overseer.all_installable_apps()
            title = f"all apps that can be installed on {target_os.CURRENT_PLATFORM}"
    if flags.PARSABLE_OUTPUT:
        file = sys.stderr
    else:
        file = sys.stdout
    print("Listing " + title, file=file)
    if as_json:
        print(json.dumps([x.simple_dict() for x in all_apps], indent=3))
    else:
        print(*(x.pretty_form() for x in all_apps), sep="\n")
    if flags.is_debug(flags.DEBUG_TIME):
        logs.print_time_logs()


def install(
    filters: Filters | ComplexFilter | None = None, no_report: bool = False
) -> Report:
    overseer = Overseer.create_context(filters=filters)
    try:
        overseer.install()
    except KeyboardInterrupt:
        overseer.print_report()
        raise
    if not no_report:
        overseer.print_report()
    return overseer.report


if __name__ == "__main__":
    parse_res = parse_install_app(__doc__)
    if isinstance(parse_res, ListArgs):
        print_apps(parse_res.filters, parse_res.mode, parse_res.json)
        sys.exit(0)
    install(filters=parse_res)
    if flags.is_debug(flags.DEBUG_TIME):
        logs.print_time_logs()
