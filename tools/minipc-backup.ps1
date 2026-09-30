param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading"),
  [int]$RetentionDays = 14
)

$ErrorActionPreference = "Stop"
$now = Get-Date
$backupDir = Join-Path $TradingRoot "Backup"
$stateDir = Join-Path $TradingRoot "State"
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

if (-not (Test-Path $stateDir)) {
  throw "State directory missing: $stateDir"
}

$stamp = $now.ToString("yyyyMMdd-HHmmss")
$zip = Join-Path $backupDir "minipc-state-$stamp.zip"
$manifest = Join-Path $env:TEMP "minipc-backup-manifest-$stamp.json"

$files = @(Get-ChildItem $stateDir -File -Recurse -ErrorAction SilentlyContinue)
$manifestObj = [ordered]@{
  kind = "MINIPC_STATE_BACKUP_V1"
  created_at_local = $now.ToString("o")
  computer_name = $env:COMPUTERNAME
  source = $stateDir
  file_count = $files.Count
  files = @($files | ForEach-Object {
    [ordered]@{
      relative_path = $_.FullName.Substring($stateDir.Length).TrimStart('\')
      length = $_.Length
      last_write_time = $_.LastWriteTime.ToString("o")
    }
  })
  guardrails = [ordered]@{
    secrets_included = $false
    logs_included = $false
    repo_included = $false
  }
}
[System.IO.File]::WriteAllText($manifest, ($manifestObj | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))

$stage = Join-Path $env:TEMP "minipc-backup-stage-$stamp"
New-Item -ItemType Directory -Force -Path $stage | Out-Null
try {
  $stageState = Join-Path $stage "State"
  New-Item -ItemType Directory -Force -Path $stageState | Out-Null
  if ($files.Count -gt 0) {
    Copy-Item -Path (Join-Path $stateDir "*") -Destination $stageState -Recurse -Force
  }
  Copy-Item -LiteralPath $manifest -Destination (Join-Path $stage "manifest.json") -Force
  Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zip -CompressionLevel Optimal -Force
} finally {
  Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $manifest -Force -ErrorAction SilentlyContinue
}

# Bounded retention only inside Trading\Backup and only our own backup naming pattern.
Get-ChildItem $backupDir -File -Filter "minipc-state-*.zip" -ErrorAction SilentlyContinue |
  Where-Object { $_.LastWriteTime -lt $now.AddDays(-$RetentionDays) } |
  Remove-Item -Force

$result = [ordered]@{
  kind = "MINIPC_STATE_BACKUP_RESULT_V1"
  created_at_local = $now.ToString("o")
  backup_path = $zip
  size_bytes = (Get-Item $zip).Length
  source_file_count = $files.Count
  retention_days = $RetentionDays
}
$result | ConvertTo-Json -Depth 4
