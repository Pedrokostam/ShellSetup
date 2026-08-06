from __future__ import annotations

from functools import wraps
from pathlib import Path
from time import perf_counter
from typing import TypeVar

T = TypeVar("T")


SCRIPT_FOLDER:Path=Path(".")


def raise_if_none(val: T | None, name: str = "Value") -> T:
    if val is None:
        raise ValueError(f"{name} missing")
    return val



def timed(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            print(f"{func.__name__}: {perf_counter() - start:.3f}s")
    return wrapper
