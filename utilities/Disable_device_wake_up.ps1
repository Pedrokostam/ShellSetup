#Requires -RunAsAdministrator

$devices = powercfg -devicequery wake_armed | ForEach-Object { $_.Trim() } | Where-Object Length

if ($devices)
{
   $counter = 0;
   foreach ($device in $devices)
   {
      if ($device -eq 'NONE')
      {
         continue
      }
      Write-Host "Disabling ".. -NoNewline
      Write-Host $device -NoNewline -ForegroundColor Cyan
      Write-Host "... " -NoNewline
      powercfg -devicedisablewake $device
      Write-Host "DONE" -ForegroundColor Green
      $counter = $counter + 1
   }
   if ($counter -eq 0)
   {
      Write-Host "No devices can wake-up the computer" -ForegroundColor Green
   }
}
else
{
   Write-Host "No devices can wake-up the computer" -ForegroundColor Green
}
