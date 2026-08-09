from __future__ import annotations

import os
import sys

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
            print(func.__name__, arguments, f" => {duration:.3f}s")

    return wrapper
