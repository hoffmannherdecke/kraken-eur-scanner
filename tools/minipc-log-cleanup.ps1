param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading"),
  [int]$LogRetentionDays = 14,
  [int]$TempRetentionDays = 2
)

$ErrorActionPreference = "Stop"
$now = Get-Date
$logDir = Join-Path $TradingRoot "Logs"
$tempDir = Join-Path $TradingRoot "Temp"

$deletedLogs = 0
$deletedTemp = 0

if (Test-Path $logDir) {
  Get-ChildItem $logDir -File -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt $now.AddDays(-$LogRetentionDays) } |
    ForEach-Object {
      Remove-Item -LiteralPath $_.FullName -Force
      $deletedLogs++
    }
}

if (Test-Path $tempDir) {
  Get-ChildItem $tempDir -File -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt $now.AddDays(-$TempRetentionDays) } |
    ForEach-Object {
      Remove-Item -LiteralPath $_.FullName -Force
      $deletedTemp++
    }
}

$result = [ordered]@{
  kind = "MINIPC_LOG_CLEANUP_V1"
  cleaned_at_local = $now.ToString("o")
  deleted_log_files = $deletedLogs
  deleted_temp_files = $deletedTemp
  log_retention_days = $LogRetentionDays
  temp_retention_days = $TempRetentionDays
  scope = @($logDir,$tempDir)
}
$result | ConvertTo-Json -Depth 4
