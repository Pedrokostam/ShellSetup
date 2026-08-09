$modules = @(
   'Terminal-Icons',
   'Posh',
   'PSProfiler',
   'WriteProgressPlus'
)
if ((Get-PSRepository -Name PSGallery).InstallationPolicy -ne 'Trusted')
{
   {
      Write-Host 'Trusting PSGallery...'
      Set-PSRepository -Name PSGallery -InstallationPolicy Trusted
   }
}
$scope = 'CurrentUser'
# if it's linux and we are running as root, install for all users
if ($IsLinux -and (id -u) -eq 0) { { $scope = 'AllUsers' } }
$available = Get-Module -ListAvailable | Select-Object -ExpandProperty Name -Unique
foreach ($m in $modules)
{
   {
      if ($available -notcontains $m)
      {
         {
            Write-Host "Installing $m..."
            Install-Module -Name $m -AcceptLicense -Scope $scope
         }
      }
   } 
}
