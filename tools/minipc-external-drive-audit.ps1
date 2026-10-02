# Read-only audit for deferred external drive maintenance.
param(
  [string]$TradingRoot = "",
  [string]$DriveLetter = "D",
  [switch]$Execute,
  [string]$Confirm = ""
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

if([string]::IsNullOrWhiteSpace($TradingRoot)){
  $homeRoot=if($env:USERPROFILE){$env:USERPROFILE}else{$HOME}
  if([string]::IsNullOrWhiteSpace($homeRoot)){throw "Unable to resolve user home directory."}
  $TradingRoot=Join-Path $homeRoot "Trading"
}
$DriveLetter=$DriveLetter.TrimEnd(':').ToUpperInvariant()
$ExpectedConfirm="AUDIT_EXTERNAL_DRIVE_"+$DriveLetter
$root=$DriveLetter+":\"
$logs=Join-Path $TradingRoot "Logs"

$plan=[ordered]@{
  kind="MINIPC_EXTERNAL_DRIVE_READONLY_AUDIT_V1"
  status=$(if($Execute){"READY_TO_EXECUTE"}else{"PLAN_ONLY"})
  drive=$root
  writes_to_target_drive=$false
  repair=$false
  format=$false
  delete=$false
  chkdsk_fix=$false
  output_location=$logs
}
if(-not $Execute){$plan|ConvertTo-Json -Depth 5;exit 0}
if($Confirm -ne $ExpectedConfirm){throw "Execution blocked. Re-run with -Confirm $ExpectedConfirm"}
if(-not(Test-Path -LiteralPath $root)){throw "Drive not mounted: $root"}

New-Item -ItemType Directory -Force -Path $logs|Out-Null

$vol=Get-Volume -DriveLetter $DriveLetter -ErrorAction Stop
$part=Get-Partition -DriveLetter $DriveLetter -ErrorAction Stop
$disk=Get-Disk -Number $part.DiskNumber -ErrorAction Stop
$logical=Get-CimInstance Win32_LogicalDisk -Filter ("DeviceID='"+$DriveLetter+":'")

$physical=$null
try{
  $physical=Get-PhysicalDisk | Where-Object {
    $_.FriendlyName -eq $disk.FriendlyName -or $_.SerialNumber -eq $disk.SerialNumber
  } | Select-Object -First 1
}catch{}

$items=@()
$totalFiles=0L
$totalDirs=0L
$totalBytes=0L
$errors=@()

try{
  $top=Get-ChildItem -LiteralPath $root -Force -ErrorAction Stop
  foreach($item in $top){
    $entry=[ordered]@{
      name=$item.Name
      full_name=$item.FullName
      type=$(if($item.PSIsContainer){"directory"}else{"file"})
      bytes=0L
      files=0L
      directories=0L
      last_write_utc=$item.LastWriteTimeUtc.ToString("o")
      enumeration_status="PASS"
    }
    try{
      if($item.PSIsContainer){
        $children=Get-ChildItem -LiteralPath $item.FullName -Force -Recurse -ErrorAction SilentlyContinue
        $files=@($children|Where-Object{-not $_.PSIsContainer})
        $dirs=@($children|Where-Object{$_.PSIsContainer})
        $entry.files=$files.Count
        $entry.directories=$dirs.Count
        $sum=($files|Measure-Object -Property Length -Sum).Sum
        if($null -eq $sum){$sum=0}
        $entry.bytes=[int64]$sum
        $totalFiles+=$files.Count
        $totalDirs+=1+$dirs.Count
        $totalBytes+=$entry.bytes
      }else{
        $entry.files=1
        $entry.bytes=[int64]$item.Length
        $totalFiles+=1
        $totalBytes+=$entry.bytes
      }
    }catch{
      $entry.enumeration_status="PARTIAL"
      $errors+=("Inventory error: "+$item.FullName+" :: "+$_.Exception.Message)
    }
    $items+=[pscustomobject]$entry
  }
}catch{
  $errors+=("Top-level inventory failed: "+$_.Exception.Message)
}

$largest=@()
try{
  $largest=Get-ChildItem -LiteralPath $root -Force -Recurse -File -ErrorAction SilentlyContinue |
    Sort-Object Length -Descending |
    Select-Object -First 20 @{n='path';e={$_.FullName}},@{n='bytes';e={[int64]$_.Length}},@{n='last_write_utc';e={$_.LastWriteTimeUtc.ToString("o")}}
}catch{
  $errors+=("Largest-file inventory failed: "+$_.Exception.Message)
}

$chkdskText=""
$chkdskExit=$null
try{
  $chkdskText=(& chkdsk.exe ($DriveLetter+":") 2>&1 | Out-String)
  $chkdskExit=$LASTEXITCODE
}catch{
  $chkdskText=$_.Exception.Message
  $chkdskExit=-1
}

$cDrive=Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"

$report=[ordered]@{
  schema_version=1
  kind="MINIPC_EXTERNAL_DRIVE_READONLY_AUDIT_V1"
  status=$(if($errors.Count -eq 0){"PASS"}else{"PASS_WITH_INVENTORY_WARNINGS"})
  checked_at_utc=[DateTime]::UtcNow.ToString("o")
  target=[ordered]@{
    drive=$root
    label=$vol.FileSystemLabel
    filesystem=$vol.FileSystem
    health_status=[string]$vol.HealthStatus
    operational_status=@($vol.OperationalStatus|ForEach-Object{[string]$_})
    size_bytes=[int64]$vol.Size
    size_remaining_bytes=[int64]$vol.SizeRemaining
    disk_number=[int]$part.DiskNumber
    disk_friendly_name=$disk.FriendlyName
    disk_serial_number=$disk.SerialNumber
    disk_bus_type=[string]$disk.BusType
    disk_partition_style=[string]$disk.PartitionStyle
    disk_is_read_only=[bool]$disk.IsReadOnly
    disk_is_offline=[bool]$disk.IsOffline
    physical_health=$(if($physical){[string]$physical.HealthStatus}else{$null})
    physical_media_type=$(if($physical){[string]$physical.MediaType}else{$null})
  }
  inventory=[ordered]@{
    total_files=$totalFiles
    total_directories=$totalDirs
    total_bytes=$totalBytes
    top_level=$items
    largest_files=$largest
    errors=$errors
  }
  backup_capacity_context=[ordered]@{
    c_total_bytes=[int64]$cDrive.Size
    c_free_bytes=[int64]$cDrive.FreeSpace
    target_inventory_bytes=$totalBytes
    c_free_exceeds_inventory_bytes=([int64]$cDrive.FreeSpace -gt $totalBytes)
  }
  chkdsk_readonly=[ordered]@{
    command=("chkdsk "+$DriveLetter+":")
    repair_switch_used=$false
    exit_code=$chkdskExit
    output=$chkdskText
  }
  guardrails=[ordered]@{
    wrote_to_target_drive=$false
    repair_performed=$false
    format_performed=$false
    delete_performed=$false
    strategy_changed=$false
    orders=$false
    real_money_actions=$false
  }
}

$stamp=Get-Date -Format "yyyyMMdd-HHmmss"
$out=Join-Path $logs ("external-drive-"+$DriveLetter.ToLowerInvariant()+"-audit-"+$stamp+".json")
[System.IO.File]::WriteAllText($out,($report|ConvertTo-Json -Depth 12),(New-Object System.Text.UTF8Encoding($false)))

Write-Host ""
Write-Host "=== EXTERNAL DRIVE READ-ONLY AUDIT COMPLETE ==="
Write-Host ("Drive: "+$root+" Label="+$vol.FileSystemLabel+" FS="+$vol.FileSystem+" VolumeHealth="+$vol.HealthStatus)
Write-Host ("Disk: "+$disk.FriendlyName+" Bus="+$disk.BusType+" PhysicalHealth="+$(if($physical){$physical.HealthStatus}else{"UNKNOWN"}))
Write-Host ("Inventory: files="+$totalFiles+" dirs="+$totalDirs+" bytes="+$totalBytes)
Write-Host ("C: free bytes="+[int64]$cDrive.FreeSpace+" / enough for inventory="+([int64]$cDrive.FreeSpace -gt $totalBytes))
Write-Host ("CHKDSK read-only exit="+$chkdskExit)
Write-Host ("Report: "+$out)
Write-Host "NO REPAIR / NO FORMAT / NO DELETE / NO WRITE TO TARGET DRIVE"
