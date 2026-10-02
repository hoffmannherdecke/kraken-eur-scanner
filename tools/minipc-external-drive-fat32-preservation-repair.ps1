# Guarded FAT32 repair preserving existing visible files and orphaned chains.
# This stage DOES NOT format or convert the volume.
param(
  [string]$TradingRoot = "",
  [string]$DriveLetter = "D",
  [string]$ExpectedLabel = "MISTRAL_450",
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
$root=$DriveLetter+":\"
$ExpectedConfirm="REPAIR_"+$DriveLetter+"_FAT32_PRESERVE_DATA"
$logs=Join-Path $TradingRoot "Logs"
$backup=Join-Path $TradingRoot ("Backup\external-drive-"+$DriveLetter.ToLowerInvariant()+"-recovered-chains")

$plan=[ordered]@{
  kind="MINIPC_EXTERNAL_DRIVE_FAT32_PRESERVATION_REPAIR_V1"
  status=$(if($Execute){"READY_TO_EXECUTE"}else{"PLAN_ONLY"})
  drive=$root
  expected_label=$ExpectedLabel
  expected_filesystem="FAT32"
  writes_manifest_to_c=$true
  copies_recovered_chk_to_c=$true
  chkdsk_fix=$true
  format=$false
  convert_filesystem=$false
  delete_existing_files=$false
  free_orphaned_chains=$false
  next_stage="ONLY_IF_POST_REPAIR_VERIFY_PASS_THEN_SEPARATE_NTFS_CONVERSION"
}
if(-not $Execute){$plan|ConvertTo-Json -Depth 6;exit 0}
if($Confirm -ne $ExpectedConfirm){throw "Execution blocked. Re-run with -Confirm $ExpectedConfirm"}
if(-not(Test-Path -LiteralPath $root)){throw "Drive not mounted: $root"}

$vol=Get-Volume -DriveLetter $DriveLetter -ErrorAction Stop
if([string]$vol.FileSystem -ne "FAT32"){throw "Expected FAT32, found "+[string]$vol.FileSystem}
if([string]$vol.FileSystemLabel -ne $ExpectedLabel){throw "Expected volume label $ExpectedLabel, found "+[string]$vol.FileSystemLabel}

New-Item -ItemType Directory -Force -Path $logs,$backup|Out-Null
$stamp=Get-Date -Format "yyyyMMdd-HHmmss"
$prePath=Join-Path $logs ("external-drive-"+$DriveLetter.ToLowerInvariant()+"-pre-repair-manifest-"+$stamp+".csv")
$postPath=Join-Path $logs ("external-drive-"+$DriveLetter.ToLowerInvariant()+"-post-repair-manifest-"+$stamp+".csv")
$reportPath=Join-Path $logs ("external-drive-"+$DriveLetter.ToLowerInvariant()+"-repair-report-"+$stamp+".json")

function Get-Manifest([string]$Base,[string]$Out){
  $baseResolved=(Resolve-Path -LiteralPath $Base).Path.TrimEnd('\')
  $rows=Get-ChildItem -LiteralPath $Base -Force -Recurse -File -ErrorAction Stop | ForEach-Object {
    [pscustomobject]@{
      relative_path=$_.FullName.Substring($baseResolved.Length).TrimStart('\')
      bytes=[int64]$_.Length
      last_write_utc=$_.LastWriteTimeUtc.ToString("o")
    }
  }
  $rows | Sort-Object relative_path | Export-Csv -LiteralPath $Out -NoTypeInformation -Encoding UTF8
  return @($rows)
}

Write-Host "=== PRE-REPAIR MANIFEST ==="
$pre=Get-Manifest $root $prePath
$preBytes=[int64](($pre|Measure-Object -Property bytes -Sum).Sum)
Write-Host ("Visible files="+$pre.Count+" bytes="+$preBytes)
Write-Host ("Manifest: "+$prePath)
Write-Host ""
Write-Host "IMPORTANT CHKDSK INPUT:"
Write-Host "If CHKDSK asks whether LOST CHAINS should be converted/saved as files, answer YES (J on German Windows / Y on English Windows)."
Write-Host "Do NOT choose any option that frees/discards orphaned chains."
Write-Host "If an unexpected prompt appears, cancel and send a screenshot instead of guessing."
Write-Host ""

& chkdsk.exe ($DriveLetter+":") /f
$repairExit=$LASTEXITCODE
if($repairExit -gt 1){throw "CHKDSK /F did not complete successfully; exit code $repairExit"}

Write-Host ""
Write-Host "=== POST-REPAIR READ-ONLY CHKDSK ==="
$verifyText=(& chkdsk.exe ($DriveLetter+":") 2>&1 | Out-String)
$verifyExit=$LASTEXITCODE
Write-Host $verifyText
if($verifyExit -ne 0){throw "Post-repair read-only CHKDSK is not clean; exit code $verifyExit. NTFS conversion remains blocked."}

Write-Host "=== POST-REPAIR MANIFEST ==="
$post=Get-Manifest $root $postPath

$preMap=@{}
foreach($x in $pre){$preMap[$x.relative_path]=[int64]$x.bytes}
$postMap=@{}
foreach($x in $post){$postMap[$x.relative_path]=[int64]$x.bytes}

$missing=@()
$sizeChanged=@()
foreach($k in $preMap.Keys){
  if(-not $postMap.ContainsKey($k)){$missing+=$k}
  elseif($postMap[$k] -ne $preMap[$k]){$sizeChanged+=$k}
}

$recovered=@()
$foundDirs=Get-ChildItem -LiteralPath $root -Force -Directory -ErrorAction SilentlyContinue | Where-Object {$_.Name -like "FOUND.*"}
foreach($fd in $foundDirs){
  Get-ChildItem -LiteralPath $fd.FullName -Force -Recurse -File -ErrorAction SilentlyContinue | Where-Object {$_.Extension -ieq ".chk"} | ForEach-Object {
    $destDir=Join-Path $backup $fd.Name
    New-Item -ItemType Directory -Force -Path $destDir|Out-Null
    $dest=Join-Path $destDir $_.Name
    Copy-Item -LiteralPath $_.FullName -Destination $dest -Force
    $recovered += [pscustomobject]@{source=$_.FullName;copied_to=$dest;bytes=[int64]$_.Length}
  }
}
Get-ChildItem -LiteralPath $root -Force -File -ErrorAction SilentlyContinue | Where-Object {$_.Name -like "File*.chk"} | ForEach-Object {
  $dest=Join-Path $backup $_.Name
  Copy-Item -LiteralPath $_.FullName -Destination $dest -Force
  $recovered += [pscustomobject]@{source=$_.FullName;copied_to=$dest;bytes=[int64]$_.Length}
}

$status=if($missing.Count -eq 0 -and $sizeChanged.Count -eq 0 -and $verifyExit -eq 0){"PASS_READY_FOR_SEPARATE_NTFS_CONVERSION"}else{"FAIL_CONVERSION_BLOCKED"}

$report=[ordered]@{
  schema_version=1
  kind="MINIPC_EXTERNAL_DRIVE_FAT32_PRESERVATION_REPAIR_RESULT_V1"
  status=$status
  completed_at_utc=[DateTime]::UtcNow.ToString("o")
  drive=$root
  label=$ExpectedLabel
  filesystem_before="FAT32"
  pre_manifest=$prePath
  post_manifest=$postPath
  pre_visible_files=$pre.Count
  post_visible_files=$post.Count
  pre_visible_bytes=$preBytes
  repair_chkdsk_exit=$repairExit
  post_repair_readonly_chkdsk_exit=$verifyExit
  missing_preexisting_files=$missing
  size_changed_preexisting_files=$sizeChanged
  recovered_chk_copies=$recovered
  recovered_chk_backup_dir=$backup
  guardrails=[ordered]@{
    format_performed=$false
    filesystem_conversion_performed=$false
    free_orphaned_chains_switch_used=$false
    existing_file_delete_performed=$false
    recovered_chk_copied_to_c=$true
    strategy_changed=$false
    orders=$false
    real_money_actions=$false
  }
  next_stage=$(if($status -eq "PASS_READY_FOR_SEPARATE_NTFS_CONVERSION"){"REVIEW_REPORT_THEN_CONVERT_D_TO_NTFS_IN_PLACE"}else{"STOP_AND_REVIEW_DO_NOT_CONVERT"})
}
[System.IO.File]::WriteAllText($reportPath,($report|ConvertTo-Json -Depth 12),(New-Object System.Text.UTF8Encoding($false)))

Write-Host ""
Write-Host "=== FAT32 PRESERVATION REPAIR COMPLETE ==="
Write-Host ("Status: "+$status)
Write-Host ("Pre files: "+$pre.Count+" / Post files: "+$post.Count)
Write-Host ("Missing pre-existing files: "+$missing.Count)
Write-Host ("Size-changed pre-existing files: "+$sizeChanged.Count)
Write-Host ("Recovered .CHK copied to C: "+$recovered.Count)
Write-Host ("Report: "+$reportPath)
Write-Host "NO FORMAT / NO FILESYSTEM CONVERSION / NO EXISTING-FILE DELETE"
