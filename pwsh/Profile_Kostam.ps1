if (Get-Command oh-my-posh)
{
  oh-my-posh init pwsh --config "$PSScriptRoot/../oh-my-posh/kostamfive.omp.json" | Invoke-Expression
}
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
  if ($global:IdleEventCounter -ge $eventCommands.Count)
  {
    Remove-Variable -Scope Global -Name 'IdleEventCounter'
    Remove-Variable -Scope Global -Name 'EventCommands'
  }
} | Out-Null
$env:POSH_GIT_ENABLED = $false
# load odd functions
. $PSScriptRoot/Kostam_functions.ps1
if (Get-Command zoxide)
{
  if (Get-Command oh-my-posh -ErrorAction Ignore)
  {
    # oh-my-posh init is lazy and replaces `prompt` on first render; init zoxide after so its hook wraps the real prompt
    # reset zoxide's guard: on profile reload oh-my-posh has already discarded the previous zoxide wrapper
    Remove-Variable __zoxide_hooked -Scope Global -ErrorAction Ignore
    $global:__omp_lazy_prompt = $function:prompt
    function global:prompt 
    {
      & $global:__omp_lazy_prompt
      (zoxide init powershell | Out-String) | Invoke-Expression
      Remove-Variable __omp_lazy_prompt -Scope Global
    }
  }
  else
  {
    (zoxide init powershell | Out-String) | Invoke-Expression
  }
}
