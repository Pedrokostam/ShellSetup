import argparse
from dataclasses import dataclass
from enum import StrEnum, auto
import sys

from python.context import flags
from python.filters import (
    Filters,
    GroupFilter,
    InstallerFilter,
    NameFilter,
    NotGroupFilter,
    NotInstallerFilter,
    NotNameFilter,
)
from python import target_os


class ListType(StrEnum):
    STEMS = auto()
    PARSABLE = auto()
    INSTALLABLE = auto()


def _list_type(s: str) -> ListType:
    try:
        return ListType[s.upper()]
    except KeyError:
        choices = ", ".join(t.name.lower() for t in ListType)
        raise argparse.ArgumentTypeError(
            f"invalid choice: {s!r} (choose from {choices})"
        )


def _add_list_parser_Args(parser: argparse.ArgumentParser):
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "type",
        nargs="?",
        type=_list_type,
        default=ListType.INSTALLABLE,
        help="specify which apps to select",
    )
    parser.add_argument("--override-os", type=str, help="override detected platform")
    return parser


def _common_parser() -> argparse.ArgumentParser:
    """Shared flags/filters, usable as a `parents=` base for sub-parsers."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--no-color", action="store_true", help="Disable coloring")
    parser.add_argument("-q", "--quiet", action="store_true")
    filter_group = parser.add_argument_group(
        "filters", "optional filtering based on name, group or installer"
    )
    filter_group.add_argument(
        "--groups",
        "-g",
        nargs="*",
        default=[],
        help="list of group names to choose, if a group is prepended with '!' the group is excluded instead",
    )
    filter_group.add_argument(
        "--names",
        "-n",
        nargs="*",
        default=[],
        help="list of filter names to choose; if a name is prepended with '!' the app is excluded instead",
    )
    filter_group.add_argument(
        "--installers",
        "-i",
        nargs="*",
        default=[],
        help="list of installer names to choose, if a group is prepended with '!' the group is excluded instead; also accepts 'script' and 'command'",
    )
    parser.add_argument(
        "--debug",
        nargs="*",
        default=[],
        choices=[flags.DEBUG_MOCK_INSTALL, flags.DEBUG_TIME],
    )
    return parser


def get_filters(namespace: argparse.Namespace) -> Filters:
    def _inner(items: list[str], good: type, bad: type, output: list[Filters]):
        for x in items:
            if x.startswith("!"):
                output.append(bad(x[1:]))
            else:
                output.append(good(x))

    output = []
    _inner(namespace.names, NameFilter, NotNameFilter, output)
    _inner(namespace.groups, GroupFilter, NotGroupFilter, output)
    _inner(namespace.installers, InstallerFilter, NotInstallerFilter, output)
    return output


def _get_parser(description: str | None) -> argparse.ArgumentParser:
    argus = {"description": description, "parents": [_common_parser()]}
    if sys.version_info[:2] >= (3, 14):
        argus["suggest_on_error"] = True
    return argparse.ArgumentParser(**argus)


@dataclass
class ListArgs:
    filters: Filters
    mode: ListType
    json: bool


def apply_flags(namespace: argparse.Namespace):
    if namespace.debug and isinstance(namespace.debug, list):
        flags.set_debug(namespace.debug)
    if namespace.quiet:
        flags.SILENT = True
    if namespace.no_color:
        flags.NO_COLOR = True
    if hasattr(namespace, "override_os") and namespace.override_os:
        target_os.CURRENT_PLATFORM = target_os.get_system_from_string(
            namespace.override_os
        )
    if hasattr(namespace, "json") and namespace.json:
        flags.PARSABLE_OUTPUT=True


def parse_install_app(description: str | None) -> Filters | ListArgs:
    base_parser = _get_parser(description)
    subs = base_parser.add_subparsers()
    _add_list_parser_Args(subs.add_parser("list", parents=[_common_parser()]))
    namespace = base_parser.parse_args()
    apply_flags(namespace)
    filters = get_filters(namespace)
    if hasattr(namespace, "type"):
        return ListArgs(filters=filters, mode=namespace.type, json=bool(namespace.json))
    return filters


def parse_setup(description: str|None) -> Filters:
    parser = _get_parser(description)
    namespace = parser.parse_args()
    apply_flags(namespace)
    return get_filters(namespace)
