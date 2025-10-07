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
function report($node, [string]$reason) {
    $null = $notInstalled.Add([PSCustomObject]@{
            Name   = $node.name
            Reason = $reason
        })
}
$os = $PSVersionTable.OS
$availablePlatforms = if ($os -like '*window*') { @('windows') }elseif ($os -like '*ubuntu*') { @('ubuntu', 'debian') }else { @() }
if (-not $availablePlatforms) {
    Write-Error "Unrecognized OS $os" -ErrorAction Stop
}
$json = Get-Content $PSScriptRoot/apps.json | ConvertFrom-Json -Depth 10
$defaultInstallersForSystem = foreach ($system in $availablePlatforms) {
    $conf = $json.defaults."$system"
    if ($conf) {
        $conf
        $os = $system
        break
    }
}
if (-not $defaultInstallersForSystem) {
    Write-Error "No defaults for $os" -ErrorAction Stop
}
$defaultInstaller = if ($defaultInstallersForSystem.default) { 
    $defaultConf = $defaultInstallersForSystem.default
    $defaultInstallersForSystem.installers | Where-Object name -EQ "$defaultConf" 
} else {
    $defaultInstallersForSystem.installers[0] 
}

if (-not $defaultInstaller -or -not $defaultInstaller.command) {
    Write-Error "No installer for $os" -ErrorAction Stop
}
$apps = $json.apps

function install ($node) {
    Write-Host "`nProcessing $($node.name)..." -NoNewline
    $matching = $false 
    foreach ($platform in $availablePlatforms) {
        $val = $node."$platform"
        if ([bool]$val) {
            $matching = $val
            break
        }
    }
    if (-not $matching) {
        Write-Host 'Skipped (platform)' -ForegroundColor Yellow
        report $node 'Different platform'
        return
    }
    $name = if ($matching.name) { $matching.name } else { $node.name }
    $installer = if ($matching.installer) {
        if ($defaultInstallersForSystem."$($matching.installer)") {
            $defaultInstallersForSystem."$($matching.installer)"
        } else {
            Write-Error "Invalid installer for $($node.name) - $($matching.installer)" -ErrorAction Continue
            report $node 'No installer'
            return
        }
    } elseif ($matching.command) {
        [PSCustomObject]@{
            command  = $matching.command
            elevated = if ($matching.elevated) { $matching.elevated }else { $false }
        }
    } else {
        $defaultInstaller
    }
    $elevated = if ($matching.elevated -is [bool]) {
        $matching.elevated
    } else {
        $installer.elevated
    }

    if ($elevated -ne (Test-IsElevated)) {
        Write-Host 'Skipped (elevation)' -ForegroundColor Yellow
        $msg = if ($elevated) { 'Elevation required' }else { 'Non-elevated user required' }
        report $node $msg
        return
    }
    $cmd = if ($matching.command) { $matching.command }else { $installer.command }
    $cmd = $cmd -replace '\$name', $name
    Write-Host 'Installing' -ForegroundColor Green
    Write-Host 'Executing ' -ForegroundColor Cyan -NoNewline
    Write-Host $cmd -ForegroundColor Magenta
    try {
        #$cmd | Invoke-Expression -ErrorAction SilentlyContinue
    } catch {
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Could not install $($node.name)" -ErrorAction Continue
    }
}

foreach ($app in $apps) {
    install($app)
}
if ($notInstalled) {
    Write-Host "`nThe following applications were not installed:"
    $notInstalled | Sort-Object Reason
}