#!/usr/bin/env pwsh
# Thin bootstrapper: ensure Python 3.9+, then hand off to setup.py.
# Kept Windows PowerShell 5.1 compatible so it runs on a fresh machine (no pwsh 7 yet).
[CmdletBinding()]
param (
   [Parameter()]
   [Switch]
   $root,
   [Parameter(ValueFromRemainingArguments)]
   $remaining
)

if ($PSVersionTable.PSVersion.Major -ge 7 -and $PSVersionTable.Platform -notlike '*win*')
{
   Write-Error "Detected non-windows platform and this script is designed for Windows only. Run the other setup script (.sh or .py)" -ErrorAction Stop
}

if ($root.IsPresent)
{
   $env:INSTALL_SCRIPT_OVERRIDE_ROOT = '1'
}

function Test-Python39
{
   foreach ($exe in 'python', 'python3', 'py')
   {
      if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
      $ver = & $exe -c 'import sys;print(f"{sys.version_info[0]}.{sys.version_info[1]}")' 2>$null
      if ($ver -and [version]$ver -ge [version]'3.9') { return $exe }
   }
   return $null
}

$python = Test-Python39
if (-not $python)
{
   if (winget -v)
   {
      # Python Install Manager (pymanager) - the new official installer; legacy .exe ends with 3.16.
      Write-Host 'Installing Python via Python Install Manager...' -ForegroundColor Green
      winget install 9NQ7512CXL7T -e --accept-package-agreements --accept-source-agreements --disable-interactivity --source winget
      if ($LASTEXITCODE -eq 0)
      {
         Write-Host "Python has been installed" -ForegroundColor Green
         if (py -V)
         {
            Write-Host "Python is available in the current session, proceeding with setup"
         }
         else
         {
            Write-Host "Python has been installed, but this shell session cannot see it. Restart the shell and run the setup again." -ForegroundColor Magenta
            exit 
         }
      }
   }
   else
   {
      Write-Error "Winget not found - download the python installer manually" -ErrorAction Stop
   }
   py install default
}

if (-not $python)
{
   Write-Error 'Python 3.9+ is required but is not available in this session. Open a new shell and re-run.'
   exit 1
}
& $python "$PSScriptRoot/setup.py" @remaining
