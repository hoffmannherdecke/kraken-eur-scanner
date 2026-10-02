# Resume-only post-verification after a successful FAT32 -> NTFS conversion.
# Does NOT run filesystem conversion and does NOT format the volume.
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
$logs=Join-Path $TradingRoot "Logs"
$ExpectedConfirm="VERIFY_"+$DriveLetter+"_NTFS_PRESERVED_DATA"

$plan=[ordered]@{
  kind="MINIPC_EXTERNAL_DRIVE_NTFS_POSTVERIFY_V1"
  status=$(if($Execute){"READY_TO_EXECUTE"}else{"PLAN_ONLY"})
  drive=$root
  expected_label=$ExpectedLabel
  required_filesystem="NTFS"
  runs_filesystem_conversion=$false
  format=$false
  deletes_existing_files=$false
  verifies_preconversion_manifest=$true
  ignores_ntfs_system_metadata_only=$true
}
if(-not $Execute){$plan|ConvertTo-Json -Depth 5;exit 0}
if($Confirm -ne $ExpectedConfirm){throw "Execution blocked. Re-run with -Confirm $ExpectedConfirm"}
if(-not(Test-Path -LiteralPath $root)){throw "Drive not mounted: $root"}

$vol=Get-Volume -DriveLetter $DriveLetter -ErrorAction Stop
if([string]$vol.FileSystem -ne "NTFS"){throw "Expected NTFS, found "+[string]$vol.FileSystem}
if([string]$vol.FileSystemLabel -ne $ExpectedLabel){throw "Expected volume label $ExpectedLabel, found "+[string]$vol.FileSystemLabel}

$preManifests=Get-ChildItem -LiteralPath $logs -Filter ("external-drive-"+$DriveLetter.ToLowerInvariant()+"-pre-ntfs-manifest-*.csv") -File -ErrorAction Stop |
  Sort-Object LastWriteTimeUtc -Descending
if(-not $preManifests){throw "No pre-conversion NTFS manifest found on C:"}
$prePath=$preManifests[0].FullName
$pre=@(Import-Csv -LiteralPath $prePath)
if($pre.Count -eq 0){throw "Pre-conversion manifest is empty"}

$systemPrefixes=@('System Volume Information\','$RECYCLE.BIN\')
$checked=0
$skippedSystem=0
$missing=@()
$sizeChanged=@()
$accessErrors=@()
$verified=@()

foreach($x in $pre){
  $rel=[string]$x.relative_path
  if([string]::IsNullOrWhiteSpace($rel)){continue}
  if([System.IO.Path]::IsPathRooted($rel) -or $rel.StartsWith("..")){throw "Unsafe relative path in pre-manifest: $rel"}

  $isSystem=$false
  foreach($prefix in $systemPrefixes){
    if($rel.StartsWith($prefix,[System.StringComparison]::OrdinalIgnoreCase)){
      $isSystem=$true
      break
    }
  }
  if($isSystem){
    $skippedSystem++
    continue
  }

  $checked++
  $p=Join-Path $root $rel
  try{
    if(-not(Test-Path -LiteralPath $p -PathType Leaf)){
      $missing+=$rel
      continue
    }
    $item=Get-Item -LiteralPath $p -Force -ErrorAction Stop
    $actual=[int64]$item.Length
    $expected=[int64]$x.bytes
    if($actual -ne $expected){
      $sizeChanged+=[pscustomobject]@{relative_path=$rel;before_bytes=$expected;after_bytes=$actual}
    }
    $verified+=[pscustomobject]@{relative_path=$rel;bytes=$actual;status=$(if($actual -eq $expected){"MATCH"}else{"SIZE_CHANGED"})}
  }catch{
    $accessErrors+=[pscustomobject]@{relative_path=$rel;error=$_.Exception.Message}
  }
}

Write-Host "=== NTFS POST-CONVERSION CHKDSK ==="
$verifyText=(& chkdsk.exe ($DriveLetter+":") 2>&1 | Out-String)
$verifyExit=$LASTEXITCODE
Write-Host $verifyText

$stamp=Get-Date -Format "yyyyMMdd-HHmmss"
$verifiedPath=Join-Path $logs ("external-drive-"+$DriveLetter.ToLowerInvariant()+"-ntfs-verified-manifest-"+$stamp+".csv")
$reportPath=Join-Path $logs ("external-drive-"+$DriveLetter.ToLowerInvariant()+"-ntfs-postverify-"+$stamp+".json")
$verified | Export-Csv -LiteralPath $verifiedPath -NoTypeInformation -Encoding UTF8

$smokeName=".chatgpt-minipc-ntfs-smoke-"+$stamp+".txt"
$smokePath=Join-Path $root $smokeName
$smokeContent="NTFS_SMOKE_"+[guid]::NewGuid().ToString("N")
[System.IO.File]::WriteAllText($smokePath,$smokeContent,(New-Object System.Text.UTF8Encoding($false)))
$readBack=[System.IO.File]::ReadAllText($smokePath)
if($readBack -ne $smokeContent){throw "Post-conversion readback mismatch"}
Remove-Item -LiteralPath $smokePath -Force
if(Test-Path -LiteralPath $smokePath){throw "Post-conversion cleanup failed"}

$status=if(
  $verifyExit -eq 0 -and
  $missing.Count -eq 0 -and
  $sizeChanged.Count -eq 0 -and
  $accessErrors.Count -eq 0
){"PASS_NTFS_VERIFIED"}else{"FAIL_REVIEW_REQUIRED"}

$report=[ordered]@{
  schema_version=1
  kind="MINIPC_EXTERNAL_DRIVE_NTFS_POSTVERIFY_RESULT_V1"
  status=$status
  completed_at_utc=[DateTime]::UtcNow.ToString("o")
  drive=$root
  label=$vol.FileSystemLabel
  filesystem=[string]$vol.FileSystem
  source_preconversion_manifest=$prePath
  pre_manifest_rows=$pre.Count
  checked_preexisting_files=$checked
  skipped_ntfs_system_metadata_rows=$skippedSystem
  missing_preexisting_files=$missing
  size_changed_preexisting_files=$sizeChanged
  access_errors=$accessErrors
  post_conversion_chkdsk_exit=$verifyExit
  reversible_write_read_delete_smoke=$true
  verified_manifest=$verifiedPath
  guardrails=[ordered]@{
    filesystem_conversion_rerun=$false
    format_performed=$false
    existing_file_delete_performed=$false
    system_metadata_ignored_only=$true
    project_runtime_moved_to_d=$false
    orders=$false
    real_money_actions=$false
  }
}
[System.IO.File]::WriteAllText($reportPath,($report|ConvertTo-Json -Depth 12),(New-Object System.Text.UTF8Encoding($false)))

Write-Host ""
Write-Host "=== NTFS POST-VERIFY COMPLETE ==="
Write-Host ("Status: "+$status)
Write-Host ("Filesystem: "+$vol.FileSystem)
Write-Host ("Pre-manifest rows: "+$pre.Count)
Write-Host ("Checked pre-existing files: "+$checked)
Write-Host ("Skipped NTFS system metadata rows: "+$skippedSystem)
Write-Host ("Missing pre-existing files: "+$missing.Count)
Write-Host ("Size-changed pre-existing files: "+$sizeChanged.Count)
Write-Host ("Access errors on user-data paths: "+$accessErrors.Count)
Write-Host "Read/write/delete smoke: PASS"
Write-Host ("Report: "+$reportPath)
Write-Host "NO CONVERSION RERUN / NO FORMAT / EXISTING DATA VERIFICATION ONLY"
