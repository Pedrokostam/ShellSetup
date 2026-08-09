import subprocess
import sys
from pathlib import Path

scoop_cmd = str(Path.home() / "scoop" / "shims" / "scoop.cmd")
scoop_ps1 = str(Path.home() / "scoop" / "shims" / "scoop.ps1")

scoop_args = ["install", "nonexistingmodule2000"]

cmd_args = [scoop_cmd] + scoop_args

cmd_res = subprocess.run(cmd_args, capture_output=True, text=True, check=False)
if cmd_res.returncode != 0:
    print("Scoop.cmd DOES forward the return code! No need for workarounds!")
else:
    print("Scoop.cmd DOES NOT forward the return code! Checking workaround...")
print(f"Command used: {cmd_args}")
print(f"Return code: {cmd_res.returncode}")
print(f"Std output: {cmd_res.stdout}")
print(f"Std error: {cmd_res.stderr}")
if cmd_res.returncode != 0:
    sys.exit(0)

ps1_args = ["powershell", "-f", scoop_ps1] + scoop_args
ps1_res = subprocess.run(ps1_args, capture_output=True, check=False, text=True)
print()
if ps1_res.returncode != 0:
    print(
        "Calling via PowerShell DOES forward the return code! At least the workaround works..."
    )
else:
    print(
        "Calling via PowerShell DOES NOT forward the return code! Nothing works ;(",
        file=sys.stderr,
    )

print(f"Command used: {ps1_args}")
print(f"Return code: {ps1_res.returncode}")
print(f"Std output: {ps1_res.stdout}")
print(f"Std error: {ps1_res.stderr}")

sys.exit(0 if ps1_res.returncode != 0 else 1)
