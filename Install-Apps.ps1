#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Powershell script to install all relevant app specified in ./apps/apps.json.
.DESCRIPTION
    Powershell script to install all relevant app specified in ./apps/apps.json.
.NOTES
    Information or caveats about the function e.g. 'This function is not supported in Linux'
.LINK
    Specify a URI to a help page, this will show when Get-Help -Online is used.
.EXAMPLE
    Test-MyTestFunction -Verbose
    Explanation of the function or its result. You can include multiple examples with additional .EXAMPLE lines
#>
[CmdletBinding()]
param ()
function Test-IsElevated {
    if ($PSVersionTable.Platform -eq 'Win32NT') {
        # Windows check
        $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
        return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    } elseif ($PSVersionTable.Platform -eq 'Unix') {
        # Linux/macOS check
        # 'id -u' returns the User ID, '0' indicates the root user
        return (id -u) -eq 0
    } else {
        # Other platforms/unknown
        Write-Warning 'Unable to determine elevation status on this platform.'
        return $false
    }
}

$notInstalled = [System.Collections.ArrayList]::new()
$installed = [System.Collections.ArrayList]::new()
function report_fail($node, [string]$reason) {
    $null = $notInstalled.Add([PSCustomObject]@{
            Name   = $node.name
            Reason = $reason
        })
}
function report_success($node) {
    $null = $installed.Add($node.name)
}
function fail_if($condition, [string]$errorMsg) {
    if ($condition) {
        Write-Error $errorMsg -ErrorAction Stop
    }
}
function fail_soft([string]$msg) {
    Write-Host $msg -ForegroundColor Red
}
$os = $PSVersionTable.OS
$availablePlatforms = if ($os -like '*window*') { @('windows') }elseif ($os -like '*ubuntu*') { @('ubuntu', 'debian') }elseif ($PSVersionTable.PsVersion.Major -le 5 ) { @('windows') } else { @() }
#
fail_if (-not $availablePlatforms) "Unrecognized OS $os"
#
$json = Get-Content $PSScriptRoot/apps/apps.json | ConvertFrom-Json 
$defaultInstallersForSystem = foreach ($system in $availablePlatforms) {
    $conf = $json.defaults."$system"
    if ($conf) {
        $conf
        $os = $system
        break
    }
}

#
fail_if (-not $defaultInstallersForSystem) "No defaults for $os"
#
$defaultInstaller = if ($defaultInstallersForSystem.default) { 
    $defaultConf = $defaultInstallersForSystem.default
    $defaultInstallersForSystem.installers | Where-Object name -EQ "$defaultConf" 
} else {
    $defaultInstallersForSystem.installers[0] 
}
#
fail_if (-not $defaultInstaller -or -not $defaultInstaller.command)"No installer for $os"
#
$apps = $json.apps

$config = [PSCustomObject]@{
    DefaultInstaller = $defaultInstaller
    Installers       = $defaultInstallersForSystem
}

function get-installer([string]$name) {
    $config.Installers | Where-Object name -EQ $name | Select-Object -First 1
}

function install ($node) {
    Write-Host "`nProcessing $($node.name)..." -NoNewline
    $matching = $null
    foreach ($platform in $availablePlatforms) {
        $val = $node."$platform"
        if ([bool]$val) {
            $matching = $val
            break
        }
    }
    if (-not $matching) {
        Write-Host 'Skipped (platform)' -ForegroundColor Yellow
        report_fail $node 'Different platform'
        return
    }
    $name = if ($matching.name) { $matching.name } else { $node.name }
    $installer = if ($matching.installer) {
        $matchingInstaller = get-installer $matching.installer
        if ($matchingInstaller) {
            $matchingInstaller
        } else {
            fail_soft "Invalid installer for $($node.name) - $($matching.installer)"
            report_fail $node 'No installer'
            return
        }
    } elseif ($matching.command) {
        [PSCustomObject]@{
            command  = $matching.command
            elevated = if ($matching.elevated) { $matching.elevated }else { $false }
        }
    } else {
        $config.DefaultInstaller
    }
    
    $elevationRequired = if ($matching.elevated -is [bool]) {
        $matching.elevated
    } else {
        $installer.elevated
    }

    if ($elevationRequired -ne (Test-IsElevated)) {
        Write-Host 'Skipped (elevation)' -ForegroundColor Yellow
        $msg = if ($elevationRequired) { 'Elevation required' } else { 'Non-elevated user required' }
        report_fail $node $msg
        return
    }
    $cmd = if ($matching.command) { $matching.command }else { $installer.command }
    $cmd = $cmd -replace '\$name', $name
    Write-Host 'Installing' -ForegroundColor Green
    Write-Host 'Executing ' -ForegroundColor Cyan -NoNewline
    Write-Host $cmd -ForegroundColor Magenta
    $errorOutput = @()
    try {
       $cmd | Invoke-Expression -ErrorAction Continue -ErrorVariable +errorOutput
    } catch {
        $errorOutput = $_
    }
    if (-not $errorOutput) {
        $errorOutput = 'See red line'
    }
    # winget return 0 if it succeeds
    if ($LASTEXITCODE -ne 0) {
        fail_soft "Could not install $($node.name)"
        report_fail $node $errorOutput
    }else{
        report_success $node
    }
}
# ======================================
# MAIN LOOP
# ======================================
foreach ($app in $apps) {
    install($app)
}
# ======================================
# report_success
# ======================================
if ($installed) {
    Write-Host "`nThe following applications were installed:" -ForegroundColor Green
    $installed
}
# ======================================
# report_fail
# ======================================
if ($notInstalled) {
    Write-Host "`nThe following applications were NOT installed:" -ForegroundColor red
    $notInstalled | Sort-Object Reason
}
