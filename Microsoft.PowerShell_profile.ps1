# slightly faster than the intended method of calling oh-my-posh init --config
# possibly could be fater by storing the result of the here-string without inner Invoke-Expression
@"
(@(& 'oh-my-posh.exe' init pwsh --config="$profile/../kostamfive.omp.yaml" --print) -join "`n") | Invoke-Expression
"@ | invoke-expression

Register-EngineEvent -SourceIdentifier 'PowerShell.OnIdle' -MaxTriggerCount 1 -Action {
  Import-Module -Name Posh -Global
    Import-Module -Name Terminal-Icons -Global
} | Out-Null

# Don't show Python venv (posh already does it)
$env:VIRTUAL_ENV_DISABLE_PROMPT = 1

$env:POSH_GIT_ENABLED = $true

set-psreadlinekeyhandler -chord tab -function menucomplete

function Measure-Profile([string]$path = $profile) {
  Write-Host "Measuring $path"
    pwsh -NoProfile -Command "measure-Script -Path $path"
}
function touch {
  [CmdletBinding()]
    param (
        [Parameter(Mandatory)]
        [ValidateLength(1, [int]::MaxValue)]
        [Alias('Path')]
        [string]
        $LiteralPath,
        [Parameter()]
        [switch]
        $AccessOnly,
        [Parameter()]
        [switch]
        $ModificationOnly
        )
      if (-not (Test-Path $LiteralPath)) {
        $null = New-Item -ItemType File -Path $LiteralPath
      }
  $item = Get-Item $LiteralPath
    if (-not $ModificationOnly.IsPresent) {
      $item.LastAccessTime = [datetime]::now
    }
  if (-not $AccessOnly.IsPresent) {
    $item.LastWriteTime = [datetime]::now
  }
  Get-Item $LiteralPath
}

function killff {
  Stop-Process -name firefox
}

function y {
  $tmp = [System.IO.Path]::GetTempFileName()
    yazi $args --cwd-file="$tmp"
    $cwd = Get-Content -Path $tmp -Encoding UTF8
    if (-not [String]::IsNullOrEmpty($cwd) -and $cwd -ne $PWD.Path) {
      Set-Location -LiteralPath ([System.IO.Path]::GetFullPath($cwd))
    }
  Remove-Item -Path $tmp
}

function qq {
  if ($env:YAZI_LEVEL) {
    exit
  }
  else {
    Write-error "No Yazi instance detected"
  }
}

# Load custom stuff for current host
$private:currentUserCurrentHost = "$psscriptroot/Microsoft.Powershell_profile_custom.ps1"
if((Test-Path $private:currentUserCurrentHost) -and ((Get-Item $private:currentUserCurrentHost | % Length) -gt 0)){
  . $private:currentUserCurrentHost
}


