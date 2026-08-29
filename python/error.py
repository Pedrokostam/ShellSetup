import traceback


class ManualAbortError(Exception):
    pass


class InstallScriptError(Exception):
    def message(self) -> str:
        raise NotImplementedError("Subclasses must implement message()")


class JsonSyntaxError(InstallScriptError):
    problem: str

    def __init__(self, problem: str):
        super().__init__(f"Malformed JSON: {problem}")
        self.problem = problem

    def message(self) -> str:
        return f"malformed JSON: {self.problem}"


class InstallerError(InstallScriptError):
    installer: str
    problem: str

    def __init__(self, installer: str, problem: str):
        super().__init__(f"{installer} error: {problem}")
        self.installer = installer
        self.problem = problem

    def message(self) -> str:
        return f"{self.installer} error: {self.problem}"


class ExecutionSkippedError(InstallScriptError):
    stdout: str
    stderr: str

    def __init__(self, stdout:str, stderr:str):
        self.stderr=stderr
        self.stdout=stdout
        super().__init__("App skipped during installation")

    def message(self) -> str:
        return "App skipped during installation"


class AppInstallError(InstallScriptError):
    problem: str

    def __init__(self, problem: str):
        super().__init__(f"Install error: {problem}")
        self.problem = problem

    def message(self) -> str:
        return f"installation error: {self.problem}"
