param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading")
)

$ErrorActionPreference = "Stop"
$backupDir = Join-Path $TradingRoot "Backup"
$latest = Get-ChildItem $backupDir -File -Filter "minipc-state-*.zip" -ErrorAction SilentlyContinue |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1

if (-not $latest) { throw "No MINI-PC state backup found in $backupDir" }

$testDir = Join-Path $env:TEMP ("minipc-restore-smoke-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $testDir | Out-Null
try {
  Expand-Archive -LiteralPath $latest.FullName -DestinationPath $testDir -Force
  $manifestPath = Join-Path $testDir "manifest.json"
  if (-not (Test-Path $manifestPath)) { throw "manifest.json missing from backup" }
  $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
  if ($manifest.kind -ne "MINIPC_STATE_BACKUP_V1") { throw "unexpected backup manifest kind" }
  $statePath = Join-Path $testDir "State"
  if (-not (Test-Path $statePath)) { throw "State folder missing from backup" }

  $restored = @(Get-ChildItem $statePath -File -Recurse -ErrorAction SilentlyContinue).Count
  if ($restored -ne [int]$manifest.file_count) {
    throw "restore file count mismatch: restored=$restored manifest=$($manifest.file_count)"
  }

  [ordered]@{
    kind = "MINIPC_RESTORE_SMOKE_V1"
    backup = $latest.FullName
    backup_age_hours = [math]::Round(((Get-Date) - $latest.LastWriteTime).TotalHours,2)
    manifest_file_count = [int]$manifest.file_count
    restored_file_count = $restored
    result = "PASS"
    live_state_modified = $false
  } | ConvertTo-Json -Depth 4
} finally {
  Remove-Item -LiteralPath $testDir -Recurse -Force -ErrorAction SilentlyContinue
}
