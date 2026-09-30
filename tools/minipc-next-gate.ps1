param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading"),
  [int]$MarketSeconds = 45
)

$ErrorActionPreference = "Stop"

if ($MarketSeconds -lt 10 -or $MarketSeconds -gt 120) {
  throw "MarketSeconds must be between 10 and 120"
}

$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$logDir = Join-Path $TradingRoot "Logs"
$selftest = Join-Path $repo "tools\minipc-selftest.ps1"
$marketSmoke = Join-Path $repo "tools\minipc-marketdata-smoke.ps1"

foreach ($p in @($repo,$selftest,$marketSmoke)) {
  if (-not (Test-Path $p)) { throw "Required path missing: $p" }
}
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$bundleReport = Join-Path $logDir "minipc-next-gate-$stamp.json"

Write-Host "=== MINI-PC NEXT GATE ==="
Write-Host "1/2 Machine self-test..."

& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $selftest
$selftestExit = $LASTEXITCODE
if ($selftestExit -ne 0) {
  throw "Machine self-test process failed with exit code $selftestExit"
}

$latestSelftest = Get-ChildItem $logDir -File -Filter "minipc-selftest-*.txt" |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1
if (-not $latestSelftest) { throw "Self-test report not found" }

Write-Host "2/2 Kraken public market-data smoke..."

& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $marketSmoke -TradingRoot $TradingRoot -Seconds $MarketSeconds
$marketExit = $LASTEXITCODE
if ($marketExit -ne 0) {
  throw "Kraken market-data smoke failed with exit code $marketExit"
}

$latestMarket = Get-ChildItem $logDir -File -Filter "minipc-marketdata-smoke-*.json" |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1
if (-not $latestMarket) { throw "Market-data smoke report not found" }
$market = Get-Content $latestMarket.FullName -Raw | ConvertFrom-Json

$os = Get-CimInstance Win32_OperatingSystem
$disk = Get-PhysicalDisk -ErrorAction SilentlyContinue | Select-Object -First 1
$cpu = Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average
$ramUsedPct = [math]::Round((1-($os.FreePhysicalMemory/$os.TotalVisibleMemorySize))*100,1)

$tasks = @()
Get-ScheduledTask -TaskName "CryptoMiniPC-*" -ErrorAction SilentlyContinue | Sort-Object TaskName | ForEach-Object {
  $info = $_ | Get-ScheduledTaskInfo
  $tasks += [ordered]@{
    name = $_.TaskName
    state = [string]$_.State
    last_result = [int]$info.LastTaskResult
    last_run = $info.LastRunTime.ToString("o")
    next_run = $info.NextRunTime.ToString("o")
  }
}

$backupDir = Join-Path $TradingRoot "Backup"
$latestBackup = Get-ChildItem $backupDir -File -Filter "minipc-state-*.zip" -ErrorAction SilentlyContinue |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1
$backupAgeHours = if ($latestBackup) {
  [math]::Round(((Get-Date)-$latestBackup.LastWriteTime).TotalHours,2)
} else { $null }

$issues = @()
if ($market.status -ne "PASS") { $issues += "marketdata_not_pass" }
if ([int]$market.data_gap -gt 0) { $issues += "marketdata_gap" }
if ([int]$market.subscription_error -gt 0) { $issues += "marketdata_subscription_error" }
if ($tasks.Count -lt 3) { $issues += "scheduled_tasks_missing" }
# Task Scheduler uses 267011 (0x41303) for "task has not yet run".
# A freshly installed future-scheduled task is therefore not a failure.
$badTaskResults = @($tasks | Where-Object {
  $_.last_result -notin @(0,267011)
})
if ($badTaskResults.Count -gt 0) {
  $issues += "scheduled_task_last_result_nonzero"
}
if (-not $latestBackup) { $issues += "backup_missing" }
elseif ($backupAgeHours -ge 168) { $issues += "backup_stale_7d" }
if ($disk -and [string]$disk.HealthStatus -notin @("Healthy","Unknown")) { $issues += "disk_health_$($disk.HealthStatus)" }

$result = [ordered]@{
  kind = "MINIPC_NEXT_GATE_V1"
  checked_at_local = (Get-Date).ToString("o")
  status = if ($issues.Count -eq 0) { "PASS" } else { "REVIEW" }
  issues = $issues
  windows = [ordered]@{
    caption = $os.Caption
    version = $os.Version
    build = $os.BuildNumber
    architecture = $os.OSArchitecture
  }
  base_load = [ordered]@{
    cpu_load_pct = [math]::Round([double]$cpu.Average,1)
    ram_used_pct = $ramUsedPct
  }
  disk = if ($disk) {
    [ordered]@{
      friendly_name = $disk.FriendlyName
      media_type = [string]$disk.MediaType
      health = [string]$disk.HealthStatus
      operational = [string]($disk.OperationalStatus -join ",")
      size_gb = [math]::Round($disk.Size/1GB,1)
    }
  } else { $null }
  scheduled_tasks = $tasks
  backup = [ordered]@{
    latest = if ($latestBackup) { $latestBackup.Name } else { $null }
    age_hours = $backupAgeHours
  }
  marketdata = [ordered]@{
    status = $market.status
    seconds = [int]$market.seconds
    book_verified = [int]$market.book_verified
    trade_observed = [int]$market.trade_observed
    data_gap = [int]$market.data_gap
    subscription_error = [int]$market.subscription_error
  }
  reports = [ordered]@{
    selftest = $latestSelftest.FullName
    marketdata = $latestMarket.FullName
    combined = $bundleReport
  }
  guardrails = [ordered]@{
    public_data_only = $true
    real_money_actions = $false
    order_api = $false
    strategy_changes = $false
  }
}

[System.IO.File]::WriteAllText(
  $bundleReport,
  ($result | ConvertTo-Json -Depth 8) + [Environment]::NewLine,
  [System.Text.UTF8Encoding]::new($false)
)

Write-Host ""
Write-Host "=== FINAL SUMMARY ==="
Write-Host ("Status: " + $result.status)
Write-Host ("Windows: " + $result.windows.caption + " | Build " + $result.windows.build)
if ($result.disk) {
  Write-Host ("Disk: " + $result.disk.friendly_name + " | Health=" + $result.disk.health + " | " + $result.disk.size_gb + " GB")
}
Write-Host ("CPU snapshot: " + $result.base_load.cpu_load_pct + "% | RAM used: " + $result.base_load.ram_used_pct + "%")
Write-Host ("Tasks: " + $tasks.Count + " | Backup age: " + $backupAgeHours + " h")
Write-Host ("Kraken WS: " + $result.marketdata.status + " | books=" + $result.marketdata.book_verified + " | trades=" + $result.marketdata.trade_observed + " | gaps=" + $result.marketdata.data_gap + " | sub_errors=" + $result.marketdata.subscription_error)
if ($issues.Count -gt 0) {
  Write-Host ("Issues: " + ($issues -join ", "))
} else {
  Write-Host "Issues: none"
}
Write-Host ("Combined report: " + $bundleReport)
Write-Host "=== END ==="
