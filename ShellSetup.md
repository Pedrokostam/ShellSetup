# ShellConfig
## PowerShell

You can add your own per-system scripts in the following files:
`Microsoft.PowerShell_profile_custom.ps1` and `profile_custom.ps1`

Those are not tracked in the repo.

Those files are not required.

## Git

The file `myconfig.gitconfig` should be manually included in your main `.gitconfig` file (`~\.gitconfig`).

To include add the following section:
```
[include]
	path = <path to myconfig>
```
or using default path (Windows):
```
[include]
	path = ~/Documents/PowerShell/myconfig.gitconfig
```
the easiest way to do this is to run the following command
```
git config --global include.path ~/Documents/PowerShell/myconfig.gitconfig
```
or run `Setup.ps1`
