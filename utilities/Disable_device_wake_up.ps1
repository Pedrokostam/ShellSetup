#Requires -RunAsAdministrator

$devices = powercfg -devicequery wake_armed | ForEach-Object { $_.Trim()} | Where-Object Length

if ($devices){
   foreach ($device in $devices){
      Write-host "Disabling ".. -NoNewline
      Write-host $device -NoNewline -ForegroundColor Cyan
      Write-host "... " -NoNewline
      powercfg -devicedisablewake $device
      Write-host "DONE" -ForegroundColor Green
   }
}
else{
   Write-host "No devices can wake-up the computer" -ForegroundColor Green
}
