import argparse

from install_apps import ListType


def _add_list_parser_Args(parser: argparse.ArgumentParser):
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "list-type",
        type=lambda s: ListType[s.upper()],
        default=ListType.TO_INSTALL,
        help="specify which apps to select",
    )


def _get_parser(description: str):
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument("-P", "--plain", action="store_true", help="Disable coloring")
    parser.add_argument("-q", "--quiet", action="store_true")
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--group", "-g", nargs="*", default=[])
    parser.add_argument("--name", "-n", nargs="*", default=[])
    parser.add_argument("--installer", "-i", nargs="*", default=[])
    parser.add_argument("--not-group", "-G", nargs="*", default=[])
    parser.add_argument("--not-name", "-N", nargs="*", default=[])
    parser.add_argument("--not-installer", "-I", nargs="*", default=[])
    parser.add_argument("--debug", nargs="*", default=[])
    parser.add_argument(
        "--list",
        type=lambda s: ListType[s.upper()],
        choices=list(ListType),
        default=None,
        help="Print all parserps that match given criterion and filters.",
    )
    parser.add_argument(
        "--list-json",
        type=lambda s: ListType[s.upper()],
        choices=list(ListType),
        default=None,
        help="Output a simplified JSON of all parserps that match given criterion and filters.",
    )
    parser.add_argument(
        "--disable-elevation-prohibition",
        action="store_true",
        help="Disables checks guarding against running installer with elevation==False when elevated.",
    )


def apply_flags():
    pass
