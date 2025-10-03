$gitconfigPath = Get-Item $psscriptroot/myconfig.gitconfig | % FullName
Write-Host "Including file '$gitconfigPath' in the global git configuration."
git config --global include.path $gitconfigPath
