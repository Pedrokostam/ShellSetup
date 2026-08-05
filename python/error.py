class InstallScriptError(Exception):
    pass


class JsonSyntaxError(InstallScriptError):
    problem: str

    def __init__(self, problem: str):
        super().__init__(f"Malformed JSON: {problem}")
        self.problem = problem


class InstallerError(InstallScriptError):
    installer: str
    problem: str

    def __init__(self, installer: str, problem: str):
        super().__init__(f"{installer} error: {problem}")
        self.installer = installer
        self.problem = problem


class AppInstallError(InstallScriptError):
    app: str
    problem: str

    def __init__(self, app: str, problem: str):
        super().__init__(f"{app} install error: {problem}")
        self.app = app
        self.problem = problem
