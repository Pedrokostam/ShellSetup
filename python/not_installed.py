from dataclasses import dataclass

from python.installer import Installer

from .app_request import AppRequest
from .color import Color, wrap_color

ELEVATION_REQUIRED = "Elevated user required"
ELEVATION_FORBIDDEN = "Elevated user prohibited"
DIFFERENT_PLATFORM = "Different platform"


@dataclass
class NotInstalled:
    app: AppRequest
    reason: str

    def name(self) -> str:
        return self.app.app_name

    def __str__(self) -> str:
        return f"{wrap_color(self.name(), Color.BRIGHT_MAGENTA)} - {wrap_color(self.reason, Color.RED)}"

    def should_redo_with_elevation(self) -> bool:
        return self.reason == ELEVATION_REQUIRED

    def should_redo_without_elevation(self) -> bool:
        return self.reason == ELEVATION_FORBIDDEN

    @classmethod
    def installer_unavailable(cls, app: AppRequest) -> "NotInstalled":
        if isinstance(app.instructions.installer, Installer):
            return NotInstalled(
                app=app,
                reason=f"Installer {app.instructions.installer.name} is not available",
            )
        else:
            return NotInstalled(
                app=app,
                reason=f"{type(app.instructions.installer).__name__} is not available",
            )

    @classmethod
    def different_platform(cls, app: AppRequest) -> "NotInstalled":
        return NotInstalled(app=app, reason=DIFFERENT_PLATFORM)

    @classmethod
    def elevation_required(cls, app: AppRequest) -> "NotInstalled":
        return NotInstalled(app=app, reason=ELEVATION_REQUIRED)

    @classmethod
    def elevation_forbiden(cls, app: AppRequest) -> "NotInstalled":
        return NotInstalled(app=app, reason=ELEVATION_FORBIDDEN)
