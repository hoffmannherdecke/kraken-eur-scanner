# Guarded in-place FAT32 -> NTFS conversion for D:/MISTRAL_450.
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
$ExpectedConfirm="CONVERT_"+$DriveLetter+"_FAT32_TO_NTFS_PRESERVE_DATA"
$logs=Join-Path $TradingRoot "Logs"

$plan=[ordered]@{
  kind="MINIPC_EXTERNAL_DRIVE_FAT32_TO_NTFS_CONVERSION_V1"
  status=$(if($Execute){"READY_TO_EXECUTE"}else{"PLAN_ONLY"})
  drive=$root
  expected_label=$ExpectedLabel
  required_filesystem_before="FAT32"
  target_filesystem="NTFS"
  format=$false
  preserve_existing_files=$true
  require_prior_repair_pass=$true
}
if(-not $Execute){$plan|ConvertTo-Json -Depth 5;exit 0}
if($Confirm -ne $ExpectedConfirm){throw "Execution blocked. Re-run with -Confirm $ExpectedConfirm"}
if(-not(Test-Path -LiteralPath $root)){throw "Drive not mounted: $root"}

$vol=Get-Volume -DriveLetter $DriveLetter -ErrorAction Stop
if([string]$vol.FileSystem -ne "FAT32"){throw "Expected FAT32, found "+[string]$vol.FileSystem}
if([string]$vol.FileSystemLabel -ne $ExpectedLabel){throw "Expected volume label $ExpectedLabel, found "+[string]$vol.FileSystemLabel}

$repairReports=Get-ChildItem -LiteralPath $logs -Filter ("external-drive-"+$DriveLetter.ToLowerInvariant()+"-repair-report-*.json") -File -ErrorAction Stop |
  Sort-Object LastWriteTimeUtc -Descending
if(-not $repairReports){throw "No prior preservation repair report found on C:"}
$repair=Get-Content -LiteralPath $repairReports[0].FullName -Raw | ConvertFrom-Json
if($repair.status -ne "PASS_READY_FOR_SEPARATE_NTFS_CONVERSION"){throw "Latest repair report is not conversion-ready: "+$repair.status}
if(@($repair.missing_preexisting_files).Count -ne 0){throw "Repair report contains missing pre-existing files"}
if(@($repair.size_changed_preexisting_files).Count -ne 0){throw "Repair report contains size-changed pre-existing files"}
if([int]$repair.post_repair_readonly_chkdsk_exit -ne 0){throw "Repair report does not contain clean post-repair CHKDSK"}

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

$stamp=Get-Date -Format "yyyyMMdd-HHmmss"
$prePath=Join-Path $logs ("external-drive-"+$DriveLetter.ToLowerInvariant()+"-pre-ntfs-manifest-"+$stamp+".csv")
$postPath=Join-Path $logs ("external-drive-"+$DriveLetter.ToLowerInvariant()+"-post-ntfs-manifest-"+$stamp+".csv")
$reportPath=Join-Path $logs ("external-drive-"+$DriveLetter.ToLowerInvariant()+"-ntfs-conversion-report-"+$stamp+".json")

Write-Host "=== PRE-CONVERSION MANIFEST ==="
$pre=Get-Manifest $root $prePath
Write-Host ("Files="+$pre.Count)
Write-Host ("Manifest: "+$prePath)
Write-Host ""
Write-Host "Starting supported Windows in-place FAT32 -> NTFS conversion."
Write-Host "If Windows asks for the current volume label, enter: $ExpectedLabel"
Write-Host "If any other unexpected prompt appears, cancel and send a screenshot instead of guessing."
Write-Host ""

& convert.exe ($DriveLetter+":") /fs:ntfs /v
$convertExit=$LASTEXITCODE
if($convertExit -ne 0){throw "NTFS conversion did not complete successfully; exit code $convertExit"}

Start-Sleep -Seconds 3
$after=Get-Volume -DriveLetter $DriveLetter -ErrorAction Stop
if([string]$after.FileSystem -ne "NTFS"){throw "Conversion command returned success but filesystem is "+[string]$after.FileSystem}

Write-Host ""
Write-Host "=== POST-CONVERSION CHKDSK ==="
$verifyText=(& chkdsk.exe ($DriveLetter+":") 2>&1 | Out-String)
$verifyExit=$LASTEXITCODE
Write-Host $verifyText
if($verifyExit -ne 0){throw "Post-conversion CHKDSK is not clean; exit code $verifyExit"}

Write-Host "=== POST-CONVERSION MANIFEST ==="
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

# Reversible write/read/delete smoke after conversion.
$smokeName=".chatgpt-minipc-ntfs-smoke-"+$stamp+".txt"
$smokePath=Join-Path $root $smokeName
$smokeContent="NTFS_SMOKE_"+[guid]::NewGuid().ToString("N")
[System.IO.File]::WriteAllText($smokePath,$smokeContent,(New-Object System.Text.UTF8Encoding($false)))
$readBack=[System.IO.File]::ReadAllText($smokePath)
if($readBack -ne $smokeContent){throw "Post-conversion readback mismatch"}
Remove-Item -LiteralPath $smokePath -Force
if(Test-Path -LiteralPath $smokePath){throw "Post-conversion cleanup failed"}

$status=if($missing.Count -eq 0 -and $sizeChanged.Count -eq 0 -and $verifyExit -eq 0){"PASS_NTFS_VERIFIED"}else{"FAIL_REVIEW_REQUIRED"}
$report=[ordered]@{
  schema_version=1
  kind="MINIPC_EXTERNAL_DRIVE_NTFS_CONVERSION_RESULT_V1"
  status=$status
  completed_at_utc=[DateTime]::UtcNow.ToString("o")
  drive=$root
  label=$after.FileSystemLabel
  filesystem_before="FAT32"
  filesystem_after=[string]$after.FileSystem
  prior_repair_report=$repairReports[0].FullName
  pre_manifest=$prePath
  post_manifest=$postPath
  pre_files=$pre.Count
  post_files=$post.Count
  missing_preexisting_files=$missing
  size_changed_preexisting_files=$sizeChanged
  post_conversion_chkdsk_exit=$verifyExit
  reversible_write_read_delete_smoke=$true
  guardrails=[ordered]@{
    format_performed=$false
    existing_file_delete_performed=$false
    project_runtime_moved_to_d=$false
    orders=$false
    real_money_actions=$false
  }
}
[System.IO.File]::WriteAllText($reportPath,($report|ConvertTo-Json -Depth 12),(New-Object System.Text.UTF8Encoding($false)))

Write-Host ""
Write-Host "=== NTFS CONVERSION COMPLETE ==="
Write-Host ("Status: "+$status)
Write-Host ("Filesystem: "+$after.FileSystem)
Write-Host ("Pre files: "+$pre.Count+" / Post files: "+$post.Count)
Write-Host ("Missing pre-existing files: "+$missing.Count)
Write-Host ("Size-changed pre-existing files: "+$sizeChanged.Count)
Write-Host "Read/write/delete smoke: PASS"
Write-Host ("Report: "+$reportPath)
Write-Host "NO FORMAT / EXISTING DATA PRESERVATION VERIFIED"
