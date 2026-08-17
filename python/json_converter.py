import dataclasses
import json
from typing import Any


class JsonConverter(json.JSONEncoder):
    def default(self, o) -> str | dict[str, Any]:
        if hasattr(o, "to_json"):
            return o.to_json()
        if dataclasses.is_dataclass(o) and not isinstance(o, type):
            return dataclasses.asdict(o)

        raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")
