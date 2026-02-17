oh-my-posh init pwsh --config "$PSScriptRoot/../oh-my-posh/kostamfive.omp.json" | Invoke-Expression
$global:IdleEventCounter = 0
$global:EventCommands = @(
   (& { (zoxide init powershell | Out-String) })
   'Set-PSReadLineKeyHandler -Chord tab -Function MenuComplete'
   'Import-Module -Name Terminal-Icons -Global'
   'Import-Module -Name Posh -Global'
)
Register-EngineEvent -SourceIdentifier 'PowerShell.OnIdle' -MaxTriggerCount $global:EventCommands.Count -Action {
   $cmd = $global:EventCommands[$global:IdleEventCounter]
   $cmd | Invoke-Expression 
   $global:IdleEventCounter = $global:IdleEventCounter + 1
   if ($global:IdleEventCounter -ge $eventCommands.Count)
   {
      Remove-Variable -Scope Global -Name 'IdleEventCounter'
      Remove-Variable -Scope Global -Name 'EventCommands'
   }
} | Out-Null
$env:POSH_GIT_ENABLED = $false
# load odd functions
. $PSScriptRoot/Kostam_functions.ps1
