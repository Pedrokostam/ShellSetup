#oh-my-posh init pwsh --config 'https://gist.githubusercontent.com/Pedrokostam/b5b3516b534349047a4dfcfa0d3e2369/raw/b254389643ec033fb3f47b6ffcb99d7ae6ebb2c6/kostam.omp.yaml' | Invoke-Expression
oh-my-posh init pwsh --config "$Profile/../gist_config/kostamfive.omp.yaml" | Invoke-Expression


Import-Module -Name Terminal-Icons
Import-Module -Name Posh
# Dont show Python env (posh does it)
$env:VIRTUAL_ENV_DISABLE_PROMPT = 1

# Tab to autocomplete
set-psreadlinekeyhandler -chord tab -function menucomplete

$env:POSH_GIT_ENABLED = $true

Import-Module -Name Microsoft.WinGet.CommandNotFound

function touch {
    [CmdletBinding()]
    param (
        [Parameter(Mandatory)]
        [ValidateLength(1,[int]::MaxValue)]
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

function Measure-Profile([string]$path=$profile){
	Write-Host "Measuring $path"
	pwsh -NoProfile -Command "measure-Script -Path $path"
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

function qq{
	if($env:YAZI_LEVEL){
		exit
	}else{
		Write-Error "No Yazi instance detected"
	}
}

# Load custom stuff for current host
$private:currentUserCurrentHost = "$psscriptroot/Microsoft.Powershell_profile_custom.ps1"
if(Test-Path $private:currentUserCurrentHost){
		. $private:currentUserCurrentHost
}
