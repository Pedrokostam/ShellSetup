from __future__ import annotations

import inspect
import re
import sys
import threading
from functools import wraps
from string import Formatter
from time import perf_counter
from typing import Any

from python import color
from python.color import AnsiColor, ColorCombination, _Color
from python.context import flags, logs
from python.stream_sink import StreamSink

INDICATORS = [
    "[=   ]",
    "[ =  ]",
    "[  = ]",
    "[   =]",
    "[  = ]",
    "[ =  ]",
]

_LAST_LENGTH = 0


def timed(func):
    @wraps(func)
    def wrapper(*args, **kwargs):

        sig = inspect.signature(func)
        start = perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            duration = perf_counter() - start
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            arguments = dict(bound.arguments)
            arguments.pop("self", None)
            arguments.pop("cls", None)
            logs.add_time_log(func.__name__, arguments, duration)
            # print(func.__name__, arguments, f" => {duration:.3f}s")

    return wrapper


PLACEHOLDER_FIND = re.compile(
    r"{([\w\.\, \(\)]+)}",
)

__NORMALIZER = re.compile(r"[\(\)\.:]")


def __normalize_name(s: str) -> str:
    return __NORMALIZER.sub(s, "_")


def __get_root(s: str) -> str:
    parts = s.split(".")
    main = parts[0]
    return main


def __get_atrs(expr: str, root_val: Any):
    root = __get_root(expr)
    expr_dict = {}
    expr_dict[root] = root_val

    res = eval(expr, {}, expr_dict)
    return res


def _find_color(color_name: str) -> _Color | None:
    color_name = color_name.upper()
    if c := getattr(color, color_name, None):
        return c
    return AnsiColor.__members__.get(color_name)


def __rebuild_format(format_string: str, val_dict: dict):

    parts = []
    for literal, field, format_specifier, conversion in Formatter().parse(
        format_string
    ):
        parts.append(literal)
        if field:
            field_col = field.split(";")
            field = field_col[0]
            format_color = field_col[1] if len(field_col) > 1 else None
            format_colors = (
                [_find_color(x) for x in format_color.split("|")]
                if format_color
                else None
            )
            if format_colors:
                format_colors = [x for x in format_colors if x]
                format_color = ColorCombination(*format_colors)
            else:
                format_color = None

            root_name = __get_root(field)
            if root_name not in val_dict:
                parts.append(f"[ERROR: MISSING KEY {field}]")
                continue
            value = __get_atrs(field, val_dict[root_name])

            subparts = []
            if format_specifier:
                subparts.append(":" + format_specifier)
            if conversion:
                subparts.append("!" + conversion)
            if subparts:
                final_final_value = ("{" + "".join(subparts) + "}").format(value)
            else:
                final_final_value = str(value)
            if format_color:
                final_final_value = format_color.wrap(value)
            parts.append(final_final_value)
    return "".join(parts)


class Lock:
    def __init__(self):
        self.locked = False


__LOCK = Lock()


class RepeatingTask:
    def __init__(
        self,
        message: str,
        start_point: float,
        interval=1.0,
    ):
        self.initial_message = message
        self.start_point = start_point
        self.interval = interval
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run)
        self.sink = StreamSink()
        self._last_message: str | None = None

    def _run(self):
        if flags.SILENT:
            return
        sys.stdout.write("\033[?25l")  # hide cursor
        sys.stdout.flush()
        try:
            while not self.stop_event.wait(self.interval):
                point = perf_counter()
                duration = point - self.start_point
                line = f"{self.initial_message}"
                if self.sink.is_started():
                    line = "{} {} {}".format(
                        self.initial_message,
                        color.TIME_COLOR.wrap(f"{duration:.1f}s"),
                        color.INDICATOR_COLOR.wrap(self.sink.indicator()),
                    )
                else:
                    line = "{} {}".format(
                        self.initial_message,
                        color.TIME_COLOR.wrap(f"{duration:.1f}s"),
                    )
                self._last_message = line
                sys.stdout.write("\r" + line)
                sys.stdout.flush()
        finally:
            sys.stdout.write("\033[?25h")  # show cursor
            sys.stdout.flush()

    def start(self):
        self.thread.start()

    def stop(self) -> int:
        self.stop_event.set()
        self.thread.join()
        return len(self._last_message) if self._last_message else 1


def one_line_report(
    initial_msg: str,
    ok: str | None = None,
    nok: str | None = None,
):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            from python.printing import conditional_print

            if flags.PARSABLE_OUTPUT:
                file = sys.stderr
            else:
                file = sys.stdout

            if __LOCK.locked:
                return func(*args, **kwargs)

            __LOCK.locked = True
            ok_msg = ok if ok is not None else color.STATUS_OK_COLOR.wrap("SUCCESS")
            nok_msg = nok if nok is not None else color.STATUS_NG_COLOR.wrap("FAILURE")
            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            arguments = dict(bound.arguments)
            msg = __rebuild_format(initial_msg, arguments)
            # conditional_print(msg, end="", file=file)
            start = perf_counter()
            live_print = RepeatingTask(start_point=start, interval=0.1, message=msg)
            # if the func accepts kwargs
            if any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
            ):
                kwargs["sink"] = live_print.sink
            live_print.start()
            function_status = nok_msg
            try:
                r = func(*args, **kwargs)
                function_status = ok_msg
                return r
            except KeyboardInterrupt:
                function_status = color.STATUS_NG_COLOR.wrap("INTERRUPTED")
                return None
            except Exception:
                function_status = nok_msg
                raise
            finally:
                end = perf_counter()
                padding = live_print.stop()
                line = "{} {} {}".format(
                    msg,
                    color.TIME_COLOR.wrap(f"{end - start:.1f} s"),
                    function_status,
                )
                line = f"\r{line:>{padding}}"
                conditional_print(line, file=file)
                __LOCK.locked = False
                logs.add_time_log(func.__name__, arguments, end - start)

        return wrapper

    return decorator


def conditional_print(msg: str, *args, **kwargs):
    from python.context import flags

    if flags.SILENT:
        return
    print(msg, *args, **kwargs, flush=True)
