param(
  [Parameter(Mandatory=$true)][string]$BackupDirectory,
  [string]$TradingRoot=(Join-Path $env:USERPROFILE 'Trading')
)
# Issue353: original-host PRE-SWAP, rollback-file integrity only.
# SOURCE-ONLY: no task controls, code replacement, data mutation or API calls.
# PASS does not grant authorization for a productive CPU cache update.
$ErrorActionPreference='Stop'
$series='PAPER-V2R4-20261009T110135Z'
$root=[IO.Path]::GetFullPath($TradingRoot)
$backupRoot='D:\Krypto-Sicherungen'
$expected=[ordered]@{
  CANDIDATES=[ordered]@{
    file='CANDIDATES-original.py'
    relative='Runtime\v2r4-paper-stage-d8b35a8ec2e6\v2r4-paper-local-runtime.py'
    sha='8371CAB2D7D18F9651E604DBAB88768F77B2DFF5EB88565122858F6428DC50D0'
  }
  WAIT=[ordered]@{
    file='WAIT-original.py'
    relative='Staging\v2r4-wait-pr326-isolated-c660ebb87a39\v2r4_wait_runtime.py'
    sha='C84533E1042C9D89D6F6EDC31DD22DE6DD3AB3B7AAE2B202EF344495A72BA6A2'
  }
}
$report=[ordered]@{
  kind='ISSUE353_CPU_ROLLBACK_READINESS_V1'
  status='READ_ONLY_BACKUP_GATE_BLOCKED'
  series_id=$series
  mode='READ_ONLY'
  backup_id=$null
  checks=[ordered]@{}
  inspected_files=0
  backup_files_modified=$false
  runtime_mutations=$false
  task_mutations=$false
  next='CPU_ONLY_SUPERVISOR_QUIESCENCE_AND_PROVENANCE_GATE_PENDING'
}
function Need([bool]$Ok,[string]$Code){
  $report.checks[$Code]=$Ok
  if(-not $Ok){throw ('GATE_'+$Code)}
}
function SafeFileHash([string]$Path) {
  Need (Test-Path -LiteralPath $Path -PathType Leaf) 'FILE_EXISTS'
  $item=Get-Item -LiteralPath $Path -Force -ErrorAction Stop
  Need (-not [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) 'NO_FILE_LINKS'
  (Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop).Hash.ToUpperInvariant()
}
try {
  Need (Test-Path -LiteralPath $backupRoot -PathType Container) 'BACKUP_ROOT_EXISTS'
  Need (Test-Path -LiteralPath $root -PathType Container) 'TRADING_ROOT_EXISTS'
  $base=[IO.Path]::GetFullPath($backupRoot).TrimEnd('\')+'\'
  $dest=[IO.Path]::GetFullPath($BackupDirectory).TrimEnd('\')
  Need ($dest.StartsWith($base,[StringComparison]::OrdinalIgnoreCase)) 'BACKUP_WITHIN_ALLOWED_ROOT'
  Need ([IO.Path]::GetFileName($dest) -match '^ISSUE353-CPU-VORHER-20261017-\d{6}-[0-9a-f]{8}$') 'UNIQUE_BACKUP_ID'
  $report.backup_id=[IO.Path]::GetFileName($dest)
  Need (Test-Path -LiteralPath $dest -PathType Container) 'BACKUP_DIR_EXISTS'
  foreach($dir in @($base.TrimEnd('\'),$dest)) {
    $item=Get-Item -LiteralPath $dir -Force -ErrorAction Stop
    Need (-not [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) 'NO_DIRECTORY_LINKS'
  }
  $manifestPath=Join-Path $dest 'manifest.json'
  Need (Test-Path -LiteralPath $manifestPath -PathType Leaf) 'MANIFEST_EXISTS'
  $m=Get-Content -LiteralPath $manifestPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
  Need ([string]$m.Kind -ceq 'ISSUE353_CPU_PRECHANGE_BACKUP_V1' -and [string]$m.Status -ceq 'BACKUP_VERIFIED') 'EXPECTED_MANIFEST'
  Need ([string]$m.Series -ceq $series -and $m.RuntimeModified -eq $false -and $m.TasksModified -eq $false) 'ORIGINAL_PAPER_ONLY_BACKUP'
  $date=$null
  Need ([datetime]::TryParse([string]$m.CreatedAtUtc,[ref]$date) -and $date.ToUniversalTime() -le [datetime]::UtcNow.AddMinutes(3)) 'VALID_BACKUP_TIME'
  $rows=@($m.Files)
  Need ($rows.Count -eq 2) 'EXACTLY_TWO_BACKUP_FILES'
  $seen=@{}
  foreach($rec in $rows) {
    $component=[string]$rec.Component
    Need ($expected.Contains($component) -and -not $seen.ContainsKey($component)) 'UNIQUE_EXPECTED_COMPONENT'
    $seen[$component]=$true
    $e=$expected[$component]
    Need ([string]$rec.File -ceq [string]$e.file -and [string]$rec.SHA256 -ceq [string]$e.sha) 'MANIFEST_ORIGINAL_SHA'
    $copy=Join-Path $dest $e.file
    Need ((SafeFileHash $copy) -ceq [string]$e.sha) 'BACKUP_BYTES_MATCH_PIN'
    $live=Join-Path $root $e.relative
    Need ((SafeFileHash $live) -ceq [string]$e.sha) 'LIVE_ORIGINAL_STILL_PRESENT'
    $report.inspected_files++
  }
  Need ($report.inspected_files -eq 2) 'COMPLETE_BACKUP_INVENTORY'
  # This proves only the two source files can be restored from an intact
  # backup; it does NOT prove supervisor quiescence or a safe source switch.
  $report.status='READ_ONLY_BACKUP_GATE_PASS_MANUAL_RELEASE_BLOCKED'
} catch {
  $reason=[string]$_.Exception.Message
  $report.reason=if($reason -match '^GATE_[A-Z0-9_]+$'){$reason}else{'UNEXPECTED_READ_ERROR'}
}
$report | ConvertTo-Json -Depth 6
