from __future__ import annotations

from dataclasses import dataclass

from .installer import InstallInstruction, Installer, Command


@dataclass
class AppRequest:
    app_name: str
    check_name: list[str] | None
    group_name:str
    instructions: InstallInstruction


@dataclass
class SkippedApp:
    app_name: str
    group_name:str
    reason: str

    def name(self) -> str:
        return self.app_name

    @classmethod
    def not_requested(cls, app: str) -> "SkippedApp":
        return SkippedApp(app_name=app, reason="Not requested for this platform")
