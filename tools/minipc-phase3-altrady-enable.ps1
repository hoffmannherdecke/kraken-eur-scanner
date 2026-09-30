param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading")
)

$ErrorActionPreference = "Stop"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw "Bitte dieses Skript in einer als Administrator gestarteten PowerShell ausführen."
}

$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$installer = Join-Path $repo "tools\install-minipc-altrady-transport.ps1"
$smoke = Join-Path $repo "tools\minipc-altrady-e2e-smoke.py"
$python = Join-Path $TradingRoot "Runtime\kraken-eur-scanner-venv\Scripts\python.exe"

foreach ($p in @($installer,$smoke,$python)) {
  if (-not (Test-Path $p)) { throw "Required path missing: $p" }
}

Write-Host "[PHASE3] 1/3 Install/start Altrady transport poller"
& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $installer -TradingRoot $TradingRoot
if ($LASTEXITCODE -ne 0) { throw "Altrady transport installer failed with exit code $LASTEXITCODE" }

Write-Host "[PHASE3] 2/3 Run synthetic relay -> MINI-PC -> ack smoke"
& $python $smoke --trading-root $TradingRoot
if ($LASTEXITCODE -ne 0) { throw "Altrady E2E transport smoke failed with exit code $LASTEXITCODE" }

Write-Host "[PHASE3] 3/3 Re-run local watchdog"
$before = Get-Date
Start-ScheduledTask -TaskName "CryptoMiniPC-Health" -ErrorAction Stop
$healthPath = Join-Path $TradingRoot "State\minipc-health.json"
$deadline = (Get-Date).AddSeconds(35)
$health = $null
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Seconds 2
  if (Test-Path $healthPath) {
    try {
      $candidate = Get-Content $healthPath -Raw | ConvertFrom-Json
      if ([datetime]$candidate.checked_at_local -ge $before) {
        $health = $candidate
        break
      }
    } catch {}
  }
}
if (-not $health) { throw "No fresh health state observed after Altrady activation." }

$altradyCheck = $health.checks.altrady_trigger_heartbeat
if (-not $altradyCheck -or $altradyCheck.ok -ne $true) {
  throw ("Watchdog did not accept Altrady heartbeat: " + $(if ($altradyCheck) { $altradyCheck.detail } else { "check missing" }))
}

$task = Get-ScheduledTask -TaskName "CryptoMiniPC-AltradyTrigger" -ErrorAction Stop
$info = $task | Get-ScheduledTaskInfo
$hb = Get-Content (Join-Path $TradingRoot "State\altrady-trigger-heartbeat.json") -Raw | ConvertFrom-Json

Write-Host ""
Write-Host "=== MINI-PC PHASE3 ALTRADY TRANSPORT SUMMARY ==="
Write-Host ("Task: " + $task.State + " | last_result=" + $info.LastTaskResult)
Write-Host ("Heartbeat: " + $hb.status + " | received=" + $hb.events_received + " | acknowledged=" + $hb.events_acknowledged)
Write-Host ("Watchdog: " + $health.status + " | Altrady check=" + $altradyCheck.ok)
Write-Host ("Strategy action: " + $hb.strategy_action)
Write-Host "Safety: TRANSPORT ONLY / NO ACCOUNT / NO ORDERS / NO STRATEGY ACTION"
Write-Host "=== END ==="
