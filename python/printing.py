from __future__ import annotations

import inspect
import re
from functools import wraps
from string import Formatter
from time import perf_counter
from typing import Any


def timed(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        from python.context import flags

        sig = inspect.signature(func)
        start = perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            if flags.DEBUG:
                duration = perf_counter() - start
                bound = sig.bind(*args, **kwargs)
                bound.apply_defaults()
                arguments = dict(bound.arguments)
                arguments.pop("self", None)
                arguments.pop("cls", None)
                print(func.__name__, arguments, f" => {duration:.3f}s")

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
    parts = []
    for literal, field, format_specifier, conversion in Formatter().parse(
        format_string
    ):
        parts.append(literal)
        if field:
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
                final_format = ("{" + "".join(subparts) + "}").format(value)
                parts.append(final_format)
            else:
                parts.append(str(value))
    return "".join(parts)


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

            ok_msg = ok or Color.GREEN.wrap("SUCCESS")
            nok_msg = nok or Color.RED.wrap("FAILURE")
            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            arguments = dict(bound.arguments)
            msg = __rebuild_format(initial_msg, arguments)
            conditional_print(msg, end="")
            start = perf_counter()
            try:
                r = func(*args, **kwargs)
                function_passed = True
                return r
            except:
                function_passed=False
                raise
            finally:
                end = perf_counter()
                status_message = ok_msg if function_passed else nok_msg
                conditional_print(f"{status_message} [{end - start:.3f}s]")

        return wrapper

    return decorator


def conditional_print(msg: str, *args, **kwargs):
    from python.context import flags

    if flags.SILENT:
        return
    print(msg, *args, **kwargs, flush=True)
