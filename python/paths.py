from pathlib import Path


SHELL_SETUP_DIR = Path(__file__).resolve().parent.parent

APP_JSON_PATH = SHELL_SETUP_DIR / "apps" / "apps.json"

REPORT_JSON_PATH = SHELL_SETUP_DIR / "apps" / "report.json"

AUXILIARY_INSTALL_SCRIPT_DIR = SHELL_SETUP_DIR / "apps" / "scripts"
