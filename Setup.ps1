#!/usr/bin/env pwsh
# Thin bootstrapper: ensure Python 3.9+, then hand off to setup.py.
# Kept Windows PowerShell 5.1 compatible so it runs on a fresh machine (no pwsh 7 yet).
[CmdletBinding()]
param (
   [Alias('Yes')]
   [switch]$Confirm,
   [switch]$NoModules
)

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
   # Python Install Manager (pymanager) - the new official installer; legacy .exe ends with 3.16.
   Write-Host 'Installing Python via Python Install Manager...' -ForegroundColor Green
   winget install 9NQ7512CXL7T -e --accept-package-agreements --accept-source-agreements --disable-interactivity --source winget
   # 'py' may not be on PATH in this session yet; a fresh shell picks it up.
   py install
   $python = Test-Python39
}

if (-not $python)
{
   Write-Error 'Python 3.9+ is required but is not available in this session. Open a new shell and re-run.'
   exit 1
}

$argsList = @()
if ($Confirm.IsPresent) { $argsList += '--yes' }
if ($NoModules.IsPresent) { $argsList += '--no-modules' }

& $python "$PSScriptRoot/setup.py" @argsList
