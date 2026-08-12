from __future__ import annotations

import inspect
import re
from functools import wraps
from time import perf_counter


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


def __get_root(s: str) -> str:
    parts = s.split(".")
    main = parts[0]
    return main


def __get_atrs(expr: str, val_dict: dict):
    root = __get_root(expr)
    root_val = val_dict[root]
    expr_dict = {}
    expr_dict[root] = root_val

    res = eval(expr, {}, expr_dict)
    return res


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
            placeholders = PLACEHOLDER_FIND.findall(initial_msg)
            formatting_values = [__get_atrs(p, arguments) for p in placeholders]
            msg = initial_msg.format(*formatting_values)
            conditional_print(msg, end="")
            try:
                r = func(*args, **kwargs)
                conditional_print(ok_msg)
                return r
            except:
                conditional_print(nok_msg)
                raise

        return wrapper

    return decorator


def conditional_print(msg: str, *args, **kwargs):
    from python.context import flags

    if flags.SILENT:
        return
    print(msg, *args, **kwargs, flush=True)
