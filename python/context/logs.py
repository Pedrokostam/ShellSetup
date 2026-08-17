from dataclasses import dataclass
import datetime
from typing import Any


@dataclass
class TimeLog:
    function_name: str
    arguments: dict[str, Any]
    time_ms: float
    date: datetime.datetime


_TIME_LOG: list[TimeLog] = []


def add_time_log(function_name: str, arguments: dict[str, Any], time_seconds: float):
    _TIME_LOG.append(
        TimeLog(
            function_name=function_name,
            arguments=arguments,
            time_ms=time_seconds * 1000,
            date=datetime.datetime.now(tz=datetime.timezone.utc),
        )
    )


def get_time_logs() -> list[TimeLog]:
    return _TIME_LOG


def print_time_logs():
    for l in _TIME_LOG:
        args = ", ".join(f"{k}={v}" for k, v in l.arguments)
        print(f"{l.function_name}({args}) => {l.time_ms:.0f}ms")
