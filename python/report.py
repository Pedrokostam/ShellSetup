from dataclasses import dataclass, field

from python.error import AppInstallError

from .app_request import AppRequest
from .not_installed import NotInstalled


@dataclass
class Report:
    installed: list[AppRequest] = field(default_factory=list)
    preinstalled: list[AppRequest] = field(default_factory=list)
    not_installed: list[NotInstalled | AppInstallError] = field(default_factory=list)
    was_elevated: bool = False
    redo_without_elevation: bool = False
    redo_with_elevation: bool = False

    def fail(self, app: AppRequest, reason: str) -> None:
        ni = NotInstalled(app=app, reason=reason)
        self.not_installed.append(ni)

    def skip(self, app: AppRequest) -> None:
        ni = NotInstalled(app=app, reason="Different platform")
        self.not_installed.append(ni)

    def preinstall(self, app: AppRequest) -> None:
        self.preinstalled.append(app)

    def succeed(self, app: AppRequest) -> None:
        self.installed.append(app)
