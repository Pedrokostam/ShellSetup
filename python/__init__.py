from __future__ import annotations

import os
import sys

_ENV_VAR = "INSTALL_SCRIPT_OVERRIDE_ROOT"

if sys.version_info < (3, 9):  # noqa: UP036
    sys.exit("Python 3.9+ required")
if os.name != "nt" and os.geteuid() == 0 and not os.getenv(_ENV_VAR):
    sys.exit(
        f"This script cannot be run as root. To override it set environemt variable {_ENV_VAR}"
    )

if os.name == "nt":
    sys.stdout.reconfigure(encoding="utf-8")  # pyright: ignore[reportAttributeAccessIssue]
    sys.stderr.reconfigure(encoding="utf-8")  # pyright: ignore[reportAttributeAccessIssue]


DEBUG = False
