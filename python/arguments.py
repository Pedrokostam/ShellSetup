import argparse
from dataclasses import dataclass
from enum import StrEnum, auto

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


class ListType(StrEnum):
    STEMS = auto()
    PARSABLE = auto()
    INSTALLABLE = auto()
    TO_INSTALL = auto()


def _add_list_parser_Args(parser: argparse.ArgumentParser):
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "type",
        nargs='?',
        type=lambda s: ListType[s.upper()],
        default=ListType.TO_INSTALL,
        help="specify which apps to select",
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


def _get_parser(description: str|None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description, suggest_on_error=True)

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


def parse_install_app(description: str|None):
    base_parser = _get_parser(description)
    subs = base_parser.add_subparsers()
    _add_list_parser_Args(subs.add_parser("list"))
    namespace = base_parser.parse_args()
    apply_flags(namespace)
    filters = get_filters(namespace)
    if hasattr(namespace,'type'):
        return ListArgs(
            filters=filters, mode=namespace.type, json=bool(namespace.json)
        )
    return filters


def parse_setup(description: str):
    parser = _get_parser(description)
    namespace = parser.parse_args()
    apply_flags(namespace)
    return get_filters(namespace)
