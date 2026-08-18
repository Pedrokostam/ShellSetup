from __future__ import annotations

import datetime
import json
import os
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from enum import Enum, StrEnum, auto
from pathlib import Path
from typing import Any

from python.color import Color, wrap_color
from python.error import AppInstallError, InstallScriptError
from python.filters import ComplexFilter
from python.json_converter import JsonConverter

from .app_request import AppRequest, AppRequestStem


class Status(StrEnum):
    FAILED = auto()
    FAILED_ELEVATION_REQUIRED = auto()
    FAILED_ELEVATION_FORBIDDEN = auto()
    FAILED_INSTALLER_UNAVAILABLE = auto()
    SKIPPED_PLATFORM = auto()
    SKIPPED_CHOICE = auto()
    PREINSTALLED = auto()
    INSTALLED = auto()

    def is_failure(self) -> bool:
        return (
            self == Status.FAILED
            or self == Status.FAILED_ELEVATION_FORBIDDEN
            or self == Status.FAILED_ELEVATION_REQUIRED
            or self == Status.FAILED_INSTALLER_UNAVAILABLE
        )

    def is_skipped(self) -> bool:
        return self == Status.SKIPPED_CHOICE or self == Status.SKIPPED_PLATFORM

    def is_installed(self) -> bool:
        return not self.is_failure() and not self.is_skipped()

    def short_form(self) -> str:
        if self.is_failure():
            return "X"
        if self.is_skipped():
            return "·"
        return "✓"

    def details(self) -> str | None:
        if self == Status.FAILED_ELEVATION_FORBIDDEN:
            return "Elevation prohibited"
        if self == Status.FAILED_ELEVATION_REQUIRED:
            return "Requires elevation"
        if self == Status.FAILED_INSTALLER_UNAVAILABLE:
            return "Installer unavailable"
        if self == Status.INSTALLED:
            return "Installed succesfully"
        if self == Status.PREINSTALLED:
            return "Already installed"
        if self == Status.SKIPPED_CHOICE:
            return "Manually skipped by user"
        if self == Status.SKIPPED_PLATFORM:
            return "Not compatible with current platform"
        if self == Status.FAILED:
            return "App installation failed"
        return None


@dataclass
class AppLog:
    index: int
    app: AppRequestStem
    status: Status
    details: str
    process_output: str | None
    date:datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(tz=datetime.timezone.utc)
    )

    @property
    def app_group(self) -> str:
        return str(self.app.group)

    @property
    def app_name(self) -> str:
        return self.app.app_name

    @property
    def app_pretty_name(self) -> str:
        return self.app.pretty_name

    @property
    def app_description(self) -> str | None:
        return self.app.description

    def to_json(self)->dict[str,Any]:
        d = asdict(self)
        d['date'] = self.date.isoformat()
        return d



def remove_newline(s: str) -> str:
    return " ".join(s.splitlines())


class LinePos(Enum):
    TOP = auto()
    BOT = auto()
    SEP = auto()


def crop_word(word: str, limit: int) -> str:
    if len(word) == 1:
        return word
    if len(word) > (limit - 3):
        return word[: (limit - 3)] + "…"
    return word


def print_cells(cells: Sequence[tuple[str, int]], color: Color | None = None):
    box = "│"
    contents = [f"{w:^{l}}" for w, l in cells[:-1]] + [
        f"{w:<{l}}" for w, l in cells[-1:]
    ]
    if color:
        no_borders = box.join(wrap_color(x, color) for x in contents)
    else:
        no_borders = box.join(contents)
    line = f"{box}{no_borders}{box}"
    print(line)


def print_border(typ: LinePos, widths: Sequence[int]):
    fill = "─"
    if typ == LinePos.TOP:
        left = "╭"
        mid = "┬"
        right = "╮"
    elif typ == LinePos.BOT:
        left = "╰"
        mid = "┴"
        right = "╯"
    else:
        left = "├"
        mid = "┼"
        right = "┤"
    parts = [fill * x for x in widths]
    no_borders = mid.join(parts)
    line = f"{left}{no_borders}{right}"
    print(line)


def crop_last_item_if_needed(items: Sequence[str], last_limit: int | None):
    if last_limit is None or last_limit <= 0:
        return tuple(items[:-1]) + (items[-1],)
    return tuple(items[:-1]) + (crop_word(items[-1], last_limit),)


def create_table_payload(app_logs: list[AppLog]):
    # list of tuples of string
    initial = [
        crop_last_item_if_needed(
            (
                a.status.short_form(),
                a.app_pretty_name,
                a.app_group,
                remove_newline(" " + a.details),
            ),
            None,
        )
        for a in app_logs
    ]
    for i in initial:
        sum(len(x) for x in i)

    no_of_cells = len(initial[0])
    # each column has 2 additional spaces as padding, except for the last, which has one
    # the border are 1-char wide and there is 1 more border than colums.
    formatting_padding = (no_of_cells - 1) * 2 + 1 + (no_of_cells + 1) * 1

    lengths = [tuple(len(x) for x in t[:-1]) for t in initial]
    non_details_width = sum([max(zi) for zi in zip(*lengths)])
    space_for_details = (
        os.get_terminal_size().columns - non_details_width - formatting_padding
    )
    return [crop_last_item_if_needed(x, space_for_details) for x in initial]


def print_many(als: list[AppLog], complex_filter: ComplexFilter | None = None):
    complex_filter = ComplexFilter.coerce(complex_filter)
    als = [a for a in als if complex_filter.filter(a.app)]
    if not als:
        print("No apps to list")
        return

    headers = [" ", "App name", "Group", "Details"]
    header_limits = tuple(map(len, headers))

    strings = create_table_payload(als)

    raw_widths = [tuple(len(x) for x in s) for s in strings]
    widths = tuple(
        max(max(x, limit) for x in col) + 2
        for col, limit in zip(zip(*raw_widths), header_limits)
    )
    header_content = tuple(zip(headers, widths))
    print_border(LinePos.TOP, widths)
    print_cells(header_content)
    print_border(LinePos.SEP, widths)
    for s, a in zip(strings, als):
        if a.status.is_installed():
            color = Color.BRIGHT_GREEN
        elif a.status.is_failure():
            color = Color.RED
        else:
            color = Color.CYAN

        cells = tuple(zip(s, widths))
        print_cells(
            cells,
            color,
        )

    print_border(LinePos.BOT, widths)


class Report:
    def __init__(self):
        self.app_logs: dict[str, AppLog] = {}

    def report(
        self,
        app: AppRequest | AppRequestStem,
        status: Status,
        details: str | InstallScriptError | AppInstallError | None,
        process_output: str | None,
    ):
        if isinstance(details, InstallScriptError):
            details = details.message()
        if details is None or len(details.strip()) == 0:
            details = None
        details = details or status.details() or ""

        al = AppLog(
            index=len(self.app_logs),
            status=status,
            app=app.to_stem(),
            details=details,
            process_output=process_output,
        )
        self.app_logs[app.app_name] = al
        return al

    def report_success(self, app: AppRequest, process_output: str | None):
        return self.report(
            app=app,
            status=Status.INSTALLED,
            details=None,
            process_output=process_output,
        )

    def report_fail(
        self,
        app: AppRequest | AppRequestStem,
        process_output: str | None = None,
        status: Status = Status.FAILED,
        details: str | InstallScriptError | AppInstallError | None = None,
    ):
        return self.report(
            app=app, status=status, details=details, process_output=process_output
        )

    def report_preinstall(
        self,
        app: AppRequest | AppRequestStem,
        details: str | None = None,
    ):
        return self.report(
            app=app, status=Status.PREINSTALLED, details=details, process_output=None
        )

    def report_skip(
        self,
        app: AppRequest | AppRequestStem,
        status: Status = Status.SKIPPED_PLATFORM,
        details: str | AppInstallError | None = None,
    ):
        return self.report(app=app, status=status, details=details, process_output=None)

    def get_app_log(self, app: str) -> AppLog | None:
        return self.app_logs.get(app)

    def print(self, complex_filter: ComplexFilter | None = None):
        print_many(list(self.app_logs.values()), complex_filter)

    def merge_reports(self, other_report: Report) -> Report:
        if not self.app_logs:
            return other_report
        if not other_report.app_logs:
            return self
        oldest_date_self = min(x.date for x in self.app_logs.values())
        oldest_date_other = min(x.date for x in other_report.app_logs.values())
        if oldest_date_other is None and oldest_date_self is None:
            # 2 empty reports
            return Report()
        newer_report = self if oldest_date_self > oldest_date_other else other_report
        older_report = self if oldest_date_self < oldest_date_other else other_report

        positive_older = {
            k: v for k, v in older_report.app_logs.items() if v.status.is_installed()
        }

        out = Report()
        out.app_logs = newer_report.app_logs.copy()
        out.app_logs.update(positive_older)

        return Report()

    def save_report(self, target: Path):
        target.parent.mkdir(exist_ok=True, parents=True)
        try:
            with target.open("+w") as f:
                json.dump(
                    list(self.app_logs.values()), f, indent=True, cls=JsonConverter
                )
        except PermissionError:
            print("\nREPORT GENERATION FAILED\n")
            p = json.dumps(list(self.app_logs.values()), indent=True, cls=JsonConverter)
            print(p)
            print()
