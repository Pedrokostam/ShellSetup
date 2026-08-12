from pathlib import Path
from time import strftime

SHELL_SETUP_DIR = Path(__file__).resolve().parent.parent.parent
APP_JSON_PATH = SHELL_SETUP_DIR / "apps" / "apps.json"
AUXILIARY_INSTALL_SCRIPT_DIR = SHELL_SETUP_DIR / "apps" / "scripts"

def report_json_path() -> Path:
    return SHELL_SETUP_DIR / "reports" / f"report_{strftime('%Y%m%d%H%M%S')}.json"
