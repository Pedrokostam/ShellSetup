#!/usr/bin/env pwsh
$git = Get-Command git
if (-not $git) {
	Write-Error 'Git is not installed!!!'
} else {
	$gitconfigPath = Get-Item $psscriptroot/git/myconfig.gitconfig | ForEach-Object FullName
	Write-Host "Including file '$gitconfigPath' in the global git configuration... " -NoNewline -Foreground Green
	git config --global include.path $gitconfigPath
	Write-Host 'DONE' -Foreground Green
}
$omp = Get-Command oh-my-posh -ea SilentlyContinue
if (-not $omp) {
	Write-Host 'Installing oh-my-posh...' -Foreground Green
	if ($PSVersionTable.OS -like '*windows*') {
		Set-ExecutionPolicy Bypass -Scope Process -Force; Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://ohmyposh.dev/install.ps1'))
	} else {
		curl -s https://ohmyposh.dev/install.sh | bash -s
	}
} else {
	Write-Host 'Upgrading oh-my-posh...' -Foreground Green
	oh-my-posh upgrade
}
Write-Host 'Installing font...' -Foreground Green
oh-my-posh font install FantasqueSansMono
Write-Host 'Trusting PSGallery...' -Foreground Green
Set-PSRepository -Name PSGallery -InstallationPolicy Trusted
$modules = @('Terminal-Icons', 'Posh', 'PSProfiler')
foreach ($mod in $modules) {
	Write-Host "Installing $mod..." -Foreground Green
	Install-Module -Name $mod
}
$profileCustomPath = Get-Item "$PSScriptRoot/pwsh/Profile_Kostam.ps1" | ForEach-Object fullname
$line = ". '$profileCustomPath'"
if (Test-Path $Profile) {
	if ((Get-Content $Profile -Raw) -notmatch 'Profile_Kostam\.ps1') {
		Write-Host "Adding line to user's profile"
		Add-Content -Path $Profile -Value "`n$line"
	} else {
		Write-Host "Custom profile already added to user's profile"
	}
} else {
	Write-Host "Creating default user's profile"
	New-Item -Path (Split-Path $profile) -ItemType Directory -Force
	$line > $Profile
}
