#Requires -RunAsAdministrator

powercfg -devicequery wake_armed | % {powercfg -devicedisablewake $_}
