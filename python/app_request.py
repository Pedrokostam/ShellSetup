from dataclasses import dataclass

from .installer import InstallInstruction, Installer, Command

@dataclass
class AppRequest:
    app_name: str
    check_name: list[str] | None
    instructions: InstallInstruction

@dataclass
class SkippedApp:
    app_name:str
    reason:str
