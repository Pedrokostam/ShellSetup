#Requires -RunAsAdministrator

$devices = powercfg -devicequery wake_armed | ForEach-Object { $_.Trim()} | Where-Object Length

if ($devices)
{
   $counter = 0;
   foreach ($device in $devices)
   {
      if($device -eq 'NONE')
      {
         continue
      }
      Write-host "Disabling ".. -NoNewline
      Write-host $device -NoNewline -ForegroundColor Cyan
      Write-host "... " -NoNewline
      powercfg -devicedisablewake $device
      Write-host "DONE" -ForegroundColor Green
      $counter=$counter+1
   }
   if($counter -eq 0)
   {
      Write-host "No devices can wake-up the computer" -ForegroundColor Green
   }
} else
{
   Write-host "No devices can wake-up the computer" -ForegroundColor Green
}
