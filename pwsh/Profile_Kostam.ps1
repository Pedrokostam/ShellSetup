oh-my-posh init pwsh --config "$PSScriptRoot/../oh-my-posh/kostamfive.omp.json" | Invoke-Expression
$global:IdleEventCounter = 0
$global:EventCommands = @(
  'Set-PSReadLineKeyHandler -Chord tab -Function MenuComplete'
  'Import-Module -Name Terminal-Icons -Global'
  'Import-Module -Name Posh -Global'
)
Register-EngineEvent -SourceIdentifier 'PowerShell.OnIdle' -MaxTriggerCount $global:EventCommands.Count -Action {
  $cmd = $global:EventCommands[$global:IdleEventCounter]
  $cmd | Invoke-Expression
  $global:IdleEventCounter = $global:IdleEventCounter + 1
  if ($global:IdleEventCounter -ge $eventCommands.Count) {
    Remove-Variable -Scope Global -Name 'IdleEventCounter'
    Remove-Variable -Scope Global -Name 'EventCommands'
  }
} | Out-Null
$env:POSH_GIT_ENABLED = $false
function Measure-Profile([string]$path = $profile) { Import-Module PSProfiler; Write-Host "Measuring $path"; pwsh -NoProfile -Command "measure-Script -Path $path" }
function touch { [CmdletBinding()] param ([Parameter(Mandatory)][ValidateLength(1, [int]::MaxValue)][Alias('Path')][string]$LiteralPath, [Parameter()][switch]$AccessOnly, [Parameter()][switch]$ModificationOnly ) if (-not (Test-Path $LiteralPath)) { $null = New-Item -ItemType File -Path $LiteralPath }; $item = Get-Item $LiteralPath; if (-not $ModificationOnly.IsPresent) { $item.LastAccessTime = [datetime]::now }; if (-not $AccessOnly.IsPresent) { $item.LastWriteTime = [datetime]::now }; Get-Item $LiteralPath }
function y { $tmp = [System.IO.Path]::GetTempFileName(); yazi $args --cwd-file="$tmp"; $cwd = Get-Content -Path $tmp -Encoding UTF8; if (-not [String]::IsNullOrEmpty($cwd) -and $cwd -ne $PWD.Path) { Set-Location -LiteralPath ([System.IO.Path]::GetFullPath($cwd)) }; Remove-Item -Path $tmp }
function qq { if ($env:YAZI_LEVEL) { exit } else { Write-Error 'No Yazi instance detected' } }
function Get-PoshUpdates { Push-Location $profile/..; git pull; oh-my-posh upgrade; Pop-Location }
if (Get-Command zoxide -ea SilentlyContinue) {
  Invoke-Expression (& { (zoxide init powershell | Out-String) })
}
