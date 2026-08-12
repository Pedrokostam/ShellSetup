from __future__ import annotations

import os
import subprocess
import sys
from typing import TypeVar

if sys.version_info < (3, 9):  # noqa: UP036
    sys.exit("Python 3.9+ required")
if os.name != "nt":
    if os.geteuid() == 0:
        sys.exit("This script cannot be run as root")
    result = subprocess.run(["sudo", "-Nnv"], capture_output=True)
    if result.returncode != 0:
        print("Sudo credentials are NOT cached. Prompting...")
        subprocess.run(["sudo", "-v"])
    print("Sudo credentials are cached. Proceeding...")

if os.name == "nt":
    sys.stdout.reconfigure(encoding="utf-8")  # pyright: ignore[reportAttributeAccessIssue]
    sys.stderr.reconfigure(encoding="utf-8")  # pyright: ignore[reportAttributeAccessIssue]






DEBUG = False


