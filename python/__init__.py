from __future__ import annotations

import os
import re
import sys

from python.color import wrap_color

if sys.version_info < (3, 9):  # noqa: UP036
    sys.exit("Python 3.9+ required")


import inspect
import subprocess
from functools import wraps
from time import perf_counter
from typing import TypeVar

if os.name != "nt":
    if os.geteuid() == 0:
        sys.exit("This script cannot be run as root")
    result = subprocess.run(["sudo", "-Nnv"], capture_output=True)
    if result.returncode != 0:
        print("Sudo credentials are NOT cached. Prompting...")
        subprocess.run(["sudo", "-v"])
    print("Sudo credentials are cached. Proceeding...")

if os.name == "nt":
    sys.stdout.reconfigure(encoding="utf-8")  # pyright: ignore[reportAttributeAccessIssue]
    sys.stderr.reconfigure(encoding="utf-8")  # pyright: ignore[reportAttributeAccessIssue]


T = TypeVar("T")


def raise_if_none(val: T | None, name: str = "Value") -> T:
    if val is None:
        raise ValueError(f"{name} missing")
    return val


DEBUG = False


def timed(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        sig = inspect.signature(func)
        start = perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            if DEBUG:
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
            from python import context
            from python.color import Color

            ok_msg = ok or Color.GREEN.wrap("SUCCESS")
            nok_msg = nok or Color.RED.wrap("FAILURE")
            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            arguments = dict(bound.arguments)
            placeholders = PLACEHOLDER_FIND.findall(initial_msg)
            formatting_values = [__get_atrs(p, arguments) for p in placeholders]
            msg = initial_msg.format(*formatting_values)
            context.conditional_print(msg, end="")
            try:
                r = func(*args, **kwargs)
                context.conditional_print(ok_msg)
                return r
            except:
                context.conditional_print(nok_msg)
                raise

        return wrapper

    return decorator
