#!/usr/bin/env -S pwsh -NoProfile
#requires -Version 7.0
[CmdletBinding()]
param (
   [Parameter()]
   [Switch]
   [Alias("Yes")]
   $Confirm,
   [Parameter()]
   [Switch]
   $NoModuleInstallation
)

function read_or_skip($skip, $prompt)
{
   if ($skip)
   {
      $true
   }
   else
   {
      Read-Host $prompt
   }
}

function check_input($inst)
{
   $inst -eq $true -or $inst.Length -eq 0 -or $inst -match '^y.*'
}

################################
####### set up git
################################
$git = Get-Command git
if (-not $git)
{
   Write-Error 'Git is not installed! Aliases will not be added!'
}
else
{
   $gitconfigPath = Get-Item $psscriptroot/git/myconfig.gitconfig | ForEach-Object FullName
   Write-Host "Including file '$gitconfigPath' in the global git configuration... " -NoNewline -Foreground Green
   git config --global include.path $gitconfigPath
   Write-Host 'DONE' -Foreground Green
}
################################
####### set up oh-my-posh
################################
$omp = Get-Command oh-my-posh -ea SilentlyContinue
if (-not $omp)
{
   Write-Host 'Installing oh-my-posh...' -Foreground Green
   if ($PSVersionTable.OS -like '*windows*')
   {
      Set-ExecutionPolicy Bypass -Scope Process -Force; Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://ohmyposh.dev/install.ps1'))
   }
   else
   {
      curl -s https://ohmyposh.dev/install.sh | bash -s
   }
}
else
{
   Write-Host 'Upgrading oh-my-posh...' -Foreground Green
   oh-my-posh upgrade
}
################################
####### install font
################################
$font = 'FantasqueSansMono'
$searchFont = 'FantasqueSans'
$isFontInstalled = if ($PSVersionTable.platform -like '*nix*')
{
   fc-list | grep $searchFont -i
}
else
{
   (New-Object System.Drawing.Text.InstalledFontCollection).Families | Where-Object { $_.Name -ilike "*$searchFont*" }
}
if (-not $isFontInstalled)
{
   Write-Host 'Installing font...' -Foreground Green
   oh-my-posh font install $font
}
else
{
   Write-Host "Font is already installed"
}

$isUnixAndRoot = if ($PSVersionTable.Platform -like '*nix*')
{
   ( id -u ) -eq 0
}
else
{
   $false
}


################################
####### trust PSGallery
################################
if (-not ((Get-PSRepository -Name PSGallery).InstallationPolicy -eq 'Trusted'))
{
   Write-Host 'Trusting PSGallery...' -Foreground Green
   Set-PSRepository -Name PSGallery -InstallationPolicy Trusted
}
################################
####### Install pwsh modules
################################
$modules = @('Terminal-Icons', 'Posh', 'PSProfiler', 'WriteProgressPlus')
$availableModules = Get-Module -ListAvailable | Select-Object -ExpandProperty Name
foreach ($mod in $modules)
{
   if ($availableModules -notcontains $mod)
   {
      $scope = 'CurrentUser'
      if ($isUnixAndRoot)
      {
         $scope = 'AllUsers'
      }
      Write-Host "Installing $mod..." -Foreground Green
      Install-Module -Name $mod -AcceptLicense -Scope $scope
   }
}
################################
####### Update pwsh profile
################################
$profileCustomPath = Get-Item "$PSScriptRoot/pwsh/Profile_Kostam.ps1" | ForEach-Object fullname
$line = ". '$profileCustomPath'"
if (Test-Path $Profile)
{
   if ((Get-Content $Profile -Raw) -notmatch 'Profile_Kostam\.ps1')
   {
      Write-Host "Adding line to user's profile"
      Add-Content -Path $Profile -Value "`n$line"
   }
   else
   {
      Write-Host "Custom profile already added to user's profile"
   }
}
else
{
   Write-Host "Creating default user's profile"
   New-Item -Path (Split-Path $profile) -ItemType Directory -Force
   $line > $Profile
}
################################
####### install apps
################################

$finInstalled = [System.Collections.ArrayList]::new()
$finPreinstalled = [System.Collections.ArrayList]::new()
$finNotInstalled = [System.Collections.ArrayList]::new()

function add_results()
{
   $outputJson = Get-Content "$PSScriptRoot/install_report.json" -ErrorAction SilentlyContinue | ConvertFrom-Json -ErrorAction SilentlyContinue
   $null = $finInstalled.AddRange(($outputJson.installed ?? $()))
   $null = $finPreinstalled.AddRange(($outputJson.preinstalled ?? $()))
   $null = $finNotInstalled.AddRange(($outputJson.not_installed ?? $()))
   $outputJson
}

$inst = read_or_skip $Confirm.IsPresent "Do you want to proceed with app installation? [Y/n]"
if (check_input $inst)
{
   . $PSScriptRoot/Install-Apps.ps1 -NoSummary
   $output = add_results

   if ($output.redo_with_elevation -and (-not $output.was_elevated))
   {
      $inst = read_or_skip $Confirm.IsPresent "Some app require elevation to install. Attempt sudo? [Y/n]"
      if (check_input $inst)
      {
         sudo -E pwsh -noprofile $PSScriptRoot/Install-Apps.ps1 -NoSummary
         $output = add_results
      }
   }
   if ($output.redo_without_elevation -and $output.was_elevated)
   {
      $inst = read_or_skip $Confirm.IsPresent "Some app require non-elevated user to install. Install them? [Y/n]"

      if (check_input $inst)
      {
         runuser -u $env:SUDO_USER -- pwsh -noprofile $PSScriptRoot/Install-Apps.ps1 -NoSummary
         $output = add_results
      }
   }
   $allPresent = $finInstalled + $finPreinstalled | Select-Object -Unique
   $finalNotInstalled = $finNotInstalled | Where-Object { $_.Name -inotin $allPresent }
   $finalpreinstalled = $finPreinstalled | Where-Object { ($finInstalled -inotcontains $_) } | Select-Object -Unique
   $finalInstalled = $finInstalled | Select-Object -Unique

   if ($finInstalled)
   {
      Write-Host "`nInstalled apps" -ForegroundColor Green
      $finalInstalled | ForEach-Object { Write-Host $_ -ForegroundColor DarkGreen }
   }
   if ($finalpreinstalled)
   {
      Write-Host "`nApps that were already installed" -ForegroundColor Green
      $finPreinstalled | Select-Object -Unique | ForEach-Object { Write-Host $_ -ForegroundColor DarkGreen }
   }
   if ($finalNotInstalled)
   {
      Write-Host "`nNot installed apps" -ForegroundColor Yellow
      $finNotInstalled | Sort-Object -Property Reason, Name |
         Where-Object { $_.Name } |
         ForEach-Object { "$($_Name) - $($_.Reason)" } |
         Select-Object -Unique |
         ForEach-Object { Write-Host $_ -ForegroundColor DarkYellow }
   }



   # write-host "All installed apps:" -ForegroundColor Green
   # $finishedInstalled | ForEach-Object {Write-host "  $_"}
   # write-host "Not installed apps:" -ForegroundColor Yellow
   # $finishedNotInstalled | ForEach-Object {Write-host "  $_"}
}
