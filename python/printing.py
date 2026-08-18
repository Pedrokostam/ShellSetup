from __future__ import annotations

import inspect
import re
from functools import wraps
from string import Formatter
import sys
import threading
from time import perf_counter
from typing import Any

from python.color import Color
from python.context import flags, logs


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


def __rebuild_format(format_string: str, val_dict: dict):
    from python.color import Color

    parts = []
    for literal, field, format_specifier, conversion in Formatter().parse(
        format_string
    ):
        parts.append(literal)
        if field:
            field_col = field.split(";")
            field = field_col[0]
            color = field_col[1] if len(field_col) > 1 else None
            if color:
                color = Color.__members__.get(color.upper())

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
            if color:
                final_final_value = color.wrap(value)
            parts.append(final_final_value)
    return "".join(parts)


class Lock:
    def __init__(self):
        self.locked = False


__LOCK = Lock()


class RepeatingTask:
    def __init__(
        self,
        start_point: float,
        interval=1.0,
    ):
        self.start_point = start_point
        self.interval = interval
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run)

    def _run(self):
        if flags.SILENT:
            return
        sys.stderr.write("\033[?25l")
        sys.stderr.flush()
        try:
            while not self.stop_event.wait(self.interval):
                point = perf_counter()
                s = f"{(point - self.start_point):.2f} s"
                sys.stderr.write(Color.BOLD.wrap(f"{s}{'\b' * len(s)}"))
                sys.stderr.flush()
        finally:
            sys.stderr.write("\033[?25h")  # show cursor
            sys.stderr.flush()

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.thread.join()


def one_line_report(
    initial_msg: str,
    ok: str | None = None,
    nok: str | None = None,
):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            from python.color import Color
            from python.printing import conditional_print

            if flags.PARSABLE_OUTPUT:
                file = sys.stderr
            else:
                file = sys.stdout

            if __LOCK.locked:
                return func(*args, **kwargs)
            __LOCK.locked = True

            ok_msg = ok if ok is not None else Color.GREEN.wrap("SUCCESS")
            nok_msg = nok if nok is not None else Color.RED.wrap("FAILURE")
            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            arguments = dict(bound.arguments)
            msg = __rebuild_format(initial_msg, arguments)
            conditional_print(msg, end="", file=file)
            start = perf_counter()
            live_print = RepeatingTask(start_point=start, interval=0.1)
            live_print.start()
            try:
                r = func(*args, **kwargs)
                function_passed = True
                return r
            except:
                function_passed = False
                raise
            finally:
                end = perf_counter()
                live_print.stop()
                status_message = ok_msg if function_passed else nok_msg
                dur = f"{end-start:.2f} s"
                conditional_print(
                    f"{status_message} {Color.BRIGHT_CYAN.wrap(dur)}", file=file
                )
                __LOCK.locked = False
                logs.add_time_log(func.__name__, arguments, end - start)

        return wrapper

    return decorator


def conditional_print(msg: str, *args, **kwargs):
    from python.context import flags

    if flags.SILENT:
        return
    print(msg, *args, **kwargs, flush=True)
