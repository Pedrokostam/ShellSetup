function Measure-Profile([string]$path = $profile)
{
   Import-Module PSProfiler
   Write-Host "Measuring $path"
   pwsh -NoProfile -Command "measure-Script -Path $path" 
}

function touch
{ [CmdletBinding()] param ([Parameter(Mandatory)][ValidateLength(1, [int]::MaxValue)][Alias('Path')][string]$LiteralPath, [Parameter()][switch]$AccessOnly, [Parameter()][switch]$ModificationOnly )
   if (-not (Test-Path $LiteralPath))
   {
      $null = New-Item -ItemType File -Path $LiteralPath 
   }
   $item = Get-Item $LiteralPath
   if (-not $ModificationOnly.IsPresent)
   {
      $item.LastAccessTime = [datetime]::now 
   }
   if (-not $AccessOnly.IsPresent)
   { 
      $item.LastWriteTime = [datetime]::now 
   }
   Get-Item $LiteralPath 
}

function y
{ 
   $tmp = [System.IO.Path]::GetTempFileName()
   yazi $args --cwd-file="$tmp"
   $cwd = Get-Content -Path $tmp -Encoding UTF8
   if (-not [String]::IsNullOrEmpty($cwd) -and $cwd -ne $PWD.Path)
   {
      Set-Location -LiteralPath ([System.IO.Path]::GetFullPath($cwd)) 
   }
   Remove-Item -Path $tmp 
}

function qq
{ 
   if ($env:YAZI_LEVEL)
   {
      exit 
   } else
   { 
      Write-Error 'No Yazi instance detected' 
   } 
}

function Get-PoshUpdates
{
   Push-Location $profile/..
   git pull
   oh-my-posh upgrade
   Pop-Location 
}

function Watch-Command
{
   [CmdletBinding()]
   param(
      [Parameter(Mandatory, HelpMessage="Name of application, command, or script block.")]
      [string]
      $Command,
      [Parameter(HelpMessage="How long to wait before calling the command again, in seconds.")]
      [double]
      $Period = 1.0
   )
   $startTime = Get-Date
   $sum = 0
   $secForm = if ($Period -eq 1.0)
   { 
      "(every second)" 
   } else
   { 
      "(every $period seconds)"
   }
   while ($true)
   {
      $output = ""
      Invoke-Expression $command *>&1  | Tee-Object -Variable output
      foreach ($a in $output)
      {
         $sum += $a.ToString().split("`n").Length
      }
      $ts = [int]((get-date) - $startTime).TotalSeconds
      Write-Host "`nWatched for $ts seconds $secForm" -ForegroundColor Cyan
      $sum=$sum+2 # add 2 lines for timestamp
      # sleep immediately after command
      # this way cancelling when sleeping will leave cursor at the end
      Start-Sleep -Seconds $period
      $currVert = [System.Console]::CursorTop
      $newPos = $currVert - $sum
      if($newPos -ge 0)
      {
         [System.Console]::SetCursorPosition(0,$newPos)
      }
      $sum = 0
   }
}
New-Alias -Name watch -Value Watch-Command -ErrorAction SilentlyContinue

function Get-ShortcutTarget
{
   param(
      [Parameter(Mandatory, ValueFromPipeline)]
      [string]
      $Path,
      [Parameter()]
      [Alias("gi")]
      [Alias("Get-Item")]
      [switch]
      $AsFileSystemInfo
   )
   begin
   {
      $sh = New-Object -COM WScript.Shell
   }
   process
   {
      foreach($P in $Path)
      {
         $targetPath =  $sh.CreateShortcut($P).TargetPath
         if($AsFileSystemInfo.IsPresent)
         {
            Get-Item $targetPath
         } else
         {
            $targetPath
         }
      }
   } 
}
