from typing import Any


def raise_if_none(val: Any, name: str = "Value"):
    if val is None:
        raise ValueError(f"{name} missing")
