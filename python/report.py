from __future__ import annotations

from dataclasses import dataclass, field

from python.color import Color, color_print, wrap_color
from python.error import AppInstallError, InstallScriptError

from .app_request import AppRequest, SkippedApp
from .not_installed import NotInstalled


@dataclass
class InstalledApp:
    app: AppRequest
    log: str


@dataclass
class Report:
    installed_apps: list[InstalledApp] = field(default_factory=list)
    preinstalled_apps: list[AppRequest] = field(default_factory=list)
    not_installed_apps: list[NotInstalled | SkippedApp] = field(default_factory=list)
    failed_apps:list[NotInstalled|InstallScriptError] = field(default_factory=list)
    was_elevated: bool = False
    silent: bool = False

    def failed(self, app: NotInstalled|InstallScriptError) -> None:
        self.failed_apps.append(app)

    def skipped(self, app: SkippedApp) -> None:
        self.not_installed_apps.append(app)

    def preinstalled(self, app: AppRequest) -> None:
        self.preinstalled_apps.append(app)

    def succeeded(self, app: AppRequest, log: str) -> None:
        self.installed_apps.append(InstalledApp(app=app, log=log))

    def redo_with_elevation(self) -> bool:
        for notinstalled in self.not_installed_apps:
            if (
                isinstance(notinstalled, NotInstalled)
                and notinstalled.should_redo_with_elevation()
            ):
                return True
        return False

    def redo_without_elevation(self) -> bool:
        for notinstalled in self.not_installed_apps:
            if (
                isinstance(notinstalled, NotInstalled)
                and notinstalled.should_redo_without_elevation()
            ):
                return True
        return False

    def notify_before(self, apps_to_install: list[AppRequest]):
        if self.silent:
            return
        if self.preinstalled_apps:
            color_print("Apps already installed:", Color.YELLOW, end=" ")
            print(*(a.app_name for a in self.preinstalled_apps), sep=", ")
        if self.not_installed_apps:
            color_print("Apps that won't be installed:", Color.RED)
        for a in self.not_installed_apps:
            print(f"   {a.name()} - {wrap_color(a.reason, Color.RED)}")
        if apps_to_install:
            color_print("Apps to install:", Color.GREEN, end="")
            print(*(a.app_name for a in apps_to_install), sep=", ")
        else:
            color_print("No apps to install", Color.GREEN)
