param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading")
)

$ErrorActionPreference = "Stop"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw "Bitte dieses Installationsskript in einer als Administrator gestarteten PowerShell ausführen."
}

$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$python = Join-Path $TradingRoot "Runtime\kraken-eur-scanner-venv\Scripts\python.exe"
$tool = Join-Path $repo "tools\minipc-github-cadence-guard.py"
$watchdog = Join-Path $repo "tools\minipc-watchdog.ps1"
$token = Join-Path $TradingRoot "Secrets\github-actions-dispatch-token.txt"
$state = Join-Path $TradingRoot "State\github-cadence-guard.json"
$taskName = "CryptoMiniPC-GitHubCadenceGuard"

foreach ($p in @($repo,$python,$tool,$watchdog,$token)) {
  if (-not (Test-Path $p)) { throw "Required path missing: $p" }
}

Write-Host "=== MINI-PC GITHUB CADENCE GUARD INSTALL ==="
Write-Host "1/5 Compile + deterministic self-test..."
& $python -m py_compile $tool
if ($LASTEXITCODE -ne 0) { throw "Cadence guard compile failed." }
& $python $tool --self-test
if ($LASTEXITCODE -ne 0) { throw "Cadence guard self-test failed." }

Write-Host "2/5 Verify least-privilege Actions-write via NO-OP workflow..."
& $python $tool --trading-root $TradingRoot --verify-dispatch-auth
if ($LASTEXITCODE -ne 0) {
  if (Test-Path $state) {
    try {
      $failed = Get-Content $state -Raw | ConvertFrom-Json
      Write-Host ("Guard status: " + $failed.status + " | detail=" + $failed.detail)
    } catch {}
  }
  throw "GitHub dispatch auth smoke failed. No persistent cadence task was installed."
}
$auth = Get-Content $state -Raw | ConvertFrom-Json
if ($auth.action -ne "AUTH_SMOKE_DISPATCHED") {
  throw "Actions-write verification did not reach the no-op dispatch."
}

Write-Host "3/5 Run recovery decision once against current scanner state..."
& $python $tool --trading-root $TradingRoot
if ($LASTEXITCODE -ne 0) {
  $failed = Get-Content $state -Raw | ConvertFrom-Json
  throw ("Initial cadence guard run failed: " + $failed.detail)
}
$first = Get-Content $state -Raw | ConvertFrom-Json
if ($first.status -ne "HEALTHY") { throw "Initial cadence guard run did not finish HEALTHY." }

Write-Host "4/5 Register recovery-only task every 5 minutes + at startup..."
$args = @(
  ('"' + $tool + '"'),
  "--trading-root",('"' + $TradingRoot + '"'),
  "--stale-after-seconds","1200",
  "--failed-grace-seconds","300",
  "--min-dispatch-interval-seconds","900"
) -join " "
$action = New-ScheduledTaskAction -Execute $python -Argument $args
$triggerStartup = New-ScheduledTaskTrigger -AtStartup
$triggerRepeat = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 2)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger @($triggerStartup,$triggerRepeat) -Settings $settings -User "SYSTEM" -RunLevel Highest -Force | Out-Null

Start-ScheduledTask -TaskName $taskName
Start-Sleep -Seconds 5

Write-Host "5/5 Verify heartbeat + refresh local watchdog..."
if (-not (Test-Path $state)) { throw "Cadence guard state file missing after task start." }
$latest = Get-Content $state -Raw | ConvertFrom-Json
$age = [math]::Round(((Get-Date).ToUniversalTime() - ([datetime]$latest.checked_at_utc).ToUniversalTime()).TotalSeconds,1)
if ($latest.status -ne "HEALTHY" -or $age -gt 60) {
  throw ("Cadence guard task did not produce a fresh HEALTHY heartbeat. status=" + $latest.status + " age_sec=" + $age)
}

& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $watchdog -TradingRoot $TradingRoot | Out-Null
$watchdogCode = $LASTEXITCODE
$healthPath = Join-Path $TradingRoot "State\minipc-health.json"
$health = if (Test-Path $healthPath) { Get-Content $healthPath -Raw | ConvertFrom-Json } else { $null }

Write-Host ""
Write-Host "=== MINI-PC GITHUB CADENCE GUARD INSTALL SUMMARY ==="
Write-Host "Status: HEALTHY"
Write-Host ("Task: " + $taskName + " | every 5 min + startup")
Write-Host ("Current guard action: " + $latest.action)
Write-Host ("Scanner recovery threshold: " + $latest.stale_after_seconds + "s")
Write-Host ("Minimum dispatch backoff: " + $latest.min_dispatch_interval_seconds + "s")
Write-Host "Nominal scan.yml schedule remains unchanged at 10 minutes."
Write-Host "GitHub schedule remains independent fallback; MINI-PC only repairs missing/delayed scanner cadence."
if ($health) { Write-Host ("Local watchdog after install: " + $health.status + " / " + $health.health_state) }
Write-Host "Safety: RECOVERY DISPATCH ONLY / NO STRATEGY CHANGE / NO DIRECT EVALUATOR / NO ACCOUNT / NO ORDER API / NO REAL-MONEY ACTION"
Write-Host "=== END ==="

# Do not fail installation solely because another pre-existing watchdog warning exists.
if ($watchdogCode -eq 2) {
  Write-Host "NOTE: local watchdog currently has at least one CRITICAL issue unrelated or broader than this installer; inspect minipc-health.json."
}
