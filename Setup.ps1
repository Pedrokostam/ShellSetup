#!/usr/bin/env -S pwsh -NoProfile
$git = Get-Command git
if (-not $git)
{
   Write-Error 'Git is not installed! Aliases will not be added!'
} else
{
   $gitconfigPath = Get-Item $psscriptroot/git/myconfig.gitconfig | ForEach-Object FullName
   Write-Host "Including file '$gitconfigPath' in the global git configuration... " -NoNewline -Foreground Green
   git config --global include.path $gitconfigPath
   Write-Host 'DONE' -Foreground Green
}
$omp = Get-Command oh-my-posh -ea SilentlyContinue
if (-not $omp)
{
   Write-Host 'Installing oh-my-posh...' -Foreground Green
   if ($PSVersionTable.OS -like '*windows*')
   {
      Set-ExecutionPolicy Bypass -Scope Process -Force; Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://ohmyposh.dev/install.ps1'))
   } else
   {
      curl -s https://ohmyposh.dev/install.sh | bash -s
   }
} else
{
   Write-Host 'Upgrading oh-my-posh...' -Foreground Green
   oh-my-posh upgrade
}
Write-Host 'Installing font...' -Foreground Green

$font = 'FantasqueSansMono'
$isFontInstalled = if ($PSVersionTable.platform -like '*nix*')
{
   fc-list | grep $font -i
} else
{
   (New-Object System.Drawing.Text.InstalledFontCollection).Families | Where-Object { $_.Name -ilike "*$font*" }
}
if(-not $isFontInstalled)
{
   oh-my-posh font install $font
}
if (-not (Get-PSRepository -name PSGallery).InstalltionPolicy -eq 'Trusted')
{
   Write-Host 'Trusting PSGallery...' -Foreground Green
   Set-PSRepository -Name PSGallery -InstallationPolicy Trusted
}
$modules = @('Terminal-Icons', 'Posh', 'PSProfiler', "Microsoft.WinGet.Client")
foreach ($mod in $modules)
{
   if(-not (Get-Module -Name $mod))
   {
      Write-Host "Installing $mod..." -Foreground Green
      Install-Module -Name $mod
   }
}
$profileCustomPath = Get-Item "$PSScriptRoot/pwsh/Profile_Kostam.ps1" | ForEach-Object fullname
$line = ". '$profileCustomPath'"
if (Test-Path $Profile)
{
   if ((Get-Content $Profile -Raw) -notmatch 'Profile_Kostam\.ps1')
   {
      Write-Host "Adding line to user's profile"
      Add-Content -Path $Profile -Value "`n$line"
   } else
   {
      Write-Host "Custom profile already added to user's profile"
   }
} else
{
   Write-Host "Creating default user's profile"
   New-Item -Path (Split-Path $profile) -ItemType Directory -Force
   $line > $Profile
}

$inst = Read-Host "Do you want to proceed with app installation? [Y/n]"

if ($inst.Length -eq 0 -or $inst -match '^y.*')
{
   . $PSScriptRoot/Install-Apps.ps1
   $output = Get-Content "$PSScriptRoot/install_report.json" | ConvertFrom-Json
   $finishedInstalled = $output.installed
   $finishedNotInstalled = $output.not_installed
   if ($output.redo_with_elevation)
   {
      $inst =  Read-Host "Some app require elevation to install. Attempt sudo? [Y/n]"
      if ($inst.Length -eq 0 -or $inst -match '^y.*')
      {
         sudo pwsh -noprofile $PSScriptRoot/Install-Apps.ps1
         $elevatedOutput = Get-Content "$PSScriptRoot/install_report.json" | ConvertFrom-Json
         $finishedInstalled += $elevatedOutput.installed
         $finishedNotInstalled = $finishedInstalled | Where-Object {$_.Name -inotin $elevatedOutput.installed}
      }
   }
   write-host "All installed apps:" -ForegroundColor Green
   $finishedInstalled | ForEach-Object {Write-host "  $_"}
   write-host "Not installed apps:" -ForegroundColor Yellow
   $finishedNotInstalled | ForEach-Object {Write-host "  $_"}
}
