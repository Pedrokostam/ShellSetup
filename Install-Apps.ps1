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
param (
   [Parameter()]
   [Switch]
   [Alias('Quiet')]
   $NoSummary
)
################################
####### global vars
################################
$existingApplications = [System.Collections.ArrayList]::new()
$notInstalled = [System.Collections.ArrayList]::new()
$installed = [System.Collections.ArrayList]::new()
$installedBefore = [System.Collections.ArrayList]::new()
$elevationRequiredError = 'Elevation required'
$elevationForbiddenError = 'Non-elevated user required'
$availablePlatforms=@()

################################
####### global functions
################################
function Test-IsElevated
{
   if ($PSVersionTable.Platform -eq 'Win32NT')
   {
      # Windows check
      $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
      return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
   } elseif ($PSVersionTable.Platform -eq 'Unix')
   {
      # Linux/macOS check
      # 'id -u' returns the User ID, '0' indicates the root user
      return (id -u) -eq 0
   } else
   {
      # Other platforms/unknown
      Write-Warning 'Unable to determine elevation status on this platform.'
      return $false
   }
}

# adds node to notinstalled
function report_fail($node, [string]$reason)
{
   Write-Host $reason -ForegroundColor Yellow
   $null = $notInstalled.Add([PSCustomObject]@{
         Name   = $node.name
         Reason = $reason
      })
}

function report_skip($node )
{
   Write-Host  "Different platform" -ForegroundColor Yellow
   $null = $notInstalled.Add([PSCustomObject]@{
         Name   = $node.name
         Reason = "Different platform"
      })
}

function report_preinstalled($node)
{
   Write-Host 'Already installed' -ForegroundColor Green
   $null = $installedBefore.Add($node.name)
}

# adds node to installed
function report_success($node)
{
   $null = $installed.Add($node.name)
}

# writes closing error if condition is TRUE
function fail_if($condition, [string]$errorMsg)
{
   if ($condition)
   {
      Write-Error $errorMsg -ErrorAction Stop
   }
}

# writes red message, but continues
function fail_soft([string]$msg)
{
   Write-Host $msg -ForegroundColor Red
}

# appends app list to alreadyInstalled
function add_installed($items)
{
   $null = $existingApplications.AddRange($items)
}


################################
####### establish platform
################################
$os = $PSVersionTable.OS
if ($PSVersionTable.PSVersion.Major -le 5 -or  $PSVersionTable.OS -like '*window*')
{
   $availablePlatforms = @('windows')
   # install winget cli
   $wingetClient = Get-Module -ListAvailable | Where-Object Name -EQ  'Microsoft.WinGet.Client'
   if(-not $wingetClient)
   {
      Install-Module -Name 'Microsoft.WinGet.Client' -AcceptLicense
   }
   $null = $existingApplications.AddRange( (Get-WinGetPackage -Source winget | ForEach-Object id))
   $scoopInstalled = Get-Command scoop -ea SilentlyContinue
   if ($scoopInstalled)
   {
      add_installed (scoop list | ForEach-Object name)
   }
} elseif ($PSVersionTable.Platform -like '*unix*')
{
   $etc = Get-Content /etc/os-release | ConvertFrom-StringData
   $idlike = $etc.id_like
   if ($idlike -like '*ubuntu*' -or $idlike -like '*debian*')
   {
      $availablePlatforms = @('ubuntu', 'debian')   
      add_installed (dpkg-query -f '${binary:Package}\n' -W)
   } elseif ($idlike -like '*arch*')
   {
      $availablePlatforms = @('arch')
      add_installed (pacman -Qq)
   } else
   {
      fail_if $true "Unrecognized Linux OS"
   }
}
$existingApplications = $existingApplications | Select-Object -Unique
#
fail_if (-not $availablePlatforms) "Unrecognized OS $($PSVersionTable.Platform) - $($PSVersionTable.OS)"
#
$isCurrentScriptElevated = Test-IsElevated

################################
####### get apps to install
################################
$json = Get-Content $PSScriptRoot/apps/apps.json | ConvertFrom-Json 
$defaultInstallersForSystem = foreach ($system in $availablePlatforms)
{
   $conf = $json.defaults."$system"
   if ($conf)
   {
      $conf
      $os = $system
      break
   }
}

#
fail_if (-not $defaultInstallersForSystem) "No defaults for $os"
#

$defaultInstaller = if ($defaultInstallersForSystem.default)
{ 
   $defaultConf = $defaultInstallersForSystem.default
   $defaultInstallersForSystem.installers | Where-Object name -EQ "$defaultConf" 
} else
{
   $defaultInstallersForSystem.installers[0] 
}
#
fail_if (-not $defaultInstaller -or -not $defaultInstaller.command)"No installer for $os"
#

$apps = $json.apps

### available installers for the current platform
$config = [PSCustomObject]@{
   DefaultInstaller = $defaultInstaller
   Installers       = $defaultInstallersForSystem
}

function get-installer([string]$name)
{
   $config.Installers | Where-Object name -EQ $name | Select-Object -First 1
}

function install ($node)
{
   Write-Host "Processing $($node.name)..." -NoNewline
   ### installation instruction for the given platform
   $installRequest = $null
   foreach ($platform in $availablePlatforms)
   {
      $val = $node."$platform"
      if ([bool]$val)
      {
         $installRequest = $val
         break
      }
   }
   ### names is either the general name or the custom name from the request
   $name = if ($installRequest.name)
   { 
      $installRequest.name 
   } else
   {
      $node.name 
   }
   ### Check if the app is already installed
   $isExistingApplication =[bool]($existingApplications | Where-Object { $name -ilike "*$_*" -or $_ -ilike "*$name*"})
   if ((-not $isExistingApplication) -and $node.checkName)
   {
      $checkName = if ($node.checkName -is [string])
      {
         $node.checkName
      } else
      {
         $node.name
      }
      $isExistingApplication = [bool](Get-Command $checkName -ErrorAction SilentlyContinue)
   }
   if ($isExistingApplication)
   {
      report_preinstalled $node
      return
   }
   if (-not $installRequest)
   {
      report_skip $node
      return
   }
   ### Installer is either custom, a command, or default
   $installer = if ($installRequest.installer)
   {
      $installRequestInstaller = get-installer $matching.installer
      if ($installRequestInstaller)
      {
         $installRequestInstaller
      } else
      {
         fail_soft "Invalid installer for $($node.name) - $($installRequest.installer)"
         report_fail $node 'No installer'
         return
      }
   } elseif ($installRequest.command)
   {
      [PSCustomObject]@{
         command  = $installRequest.command
         elevated = if ($installRequest.elevated)
         {
            $installRequest.elevated 
         } else
         { 
            $false 
         }
      }
   } else
   {
      $config.DefaultInstaller
   }

   $elevationRequired = if ($installRequest.elevated -is [bool])
   {
      $installRequest.elevated
   } else
   {
      $installer.elevated
   }
   if ($elevationRequired -ne $isCurrentScriptElevated)
   {
      $msg = if ($elevationRequired)
      {
         $elevationRequiredError 
      } else
      { 
         $elevationForbiddenError
      }
      report_fail $node $msg
      return
   }

   $cmd = if ($installRequest.command)
   {
      $installRequest.command 
   } else
   {
      $installer.command 
   }

   $cmd = $cmd -replace '\$name', $name

   Write-Host 'Executing ' -ForegroundColor Cyan -NoNewline
   Write-Host $cmd -ForegroundColor Magenta
   $errorOutput = @()
   try
   {
      $cmd | Invoke-Expression -ErrorAction Continue -ErrorVariable +errorOutput
   } catch
   {
      $errorOutput = $_
   }
   if (-not $errorOutput)
   {
      $errorOutput = 'See red line'
   }
   # winget return 0 if it succeeds
   if ($LASTEXITCODE -ne 0)
   {
      fail_soft "Could not install $($node.name)"
      report_fail $node $errorOutput
   } else
   {
      report_success $node
   }
}

################################
####### MAIN LOOP
################################
foreach ($app in $apps)
{
   install($app)
}

################################
####### report success
################################
if ((-not $NoSummary.IsPresent) -and $installed)
{
   Write-Host "`nThe following applications were installed:" -ForegroundColor Green
   $installed
}

################################
####### report failed
################################
if ((-not $NoSummary.IsPresent) -and  $notInstalled)
{
   Write-Host "`nThe following applications were NOT installed during this script:" -ForegroundColor red
   $notInstalled | Sort-Object Reason | Write-Output -NoEnumerate
}

################################
####### file report
################################
@{
   installed = $installed
   preinstalled = $installedBefore
   not_installed = $notInstalled
   was_elevated = $isCurrentScriptElevated
   redo_without_elevation = [bool]($notInstalled | Where-Object Reason -eq $elevationForbiddenError)
   redo_with_elevation = [bool]($notInstalled | Where-Object Reason -eq $elevationRequiredError)
} | ConvertTo-Json > "$PSScriptRoot/install_report.json"
