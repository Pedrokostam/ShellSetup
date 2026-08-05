from dataclasses import dataclass

from .app_request import AppRequest
from .color import Color, wrap_color


@dataclass
class NotInstalled:
    app: AppRequest
    reason: str

    def name(self) -> str:
        return self.app.app_name

    def __str__(self) -> str:
        return f"{wrap_color(self.name(), Color.BRIGHT_MAGENTA)} - {wrap_color(self.reason, Color.RED)}"
