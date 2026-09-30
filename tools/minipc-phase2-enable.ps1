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
$canaryInstaller = Join-Path $repo "tools\install-minipc-kraken-canary.ps1"
$healthState = Join-Path $TradingRoot "State\minipc-health.json"

foreach ($p in @($repo,$canaryInstaller)) {
  if (-not (Test-Path $p)) { throw "Required path missing: $p" }
}

function Wait-FreshHealth([datetime]$After,[int]$TimeoutSeconds=35) {
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 2
    if (Test-Path $healthState) {
      try {
        $h = Get-Content $healthState -Raw | ConvertFrom-Json
        $t = [datetime]$h.checked_at_local
        if ($t -ge $After) { return $h }
      } catch {}
    }
  }
  throw "No fresh health state observed within $TimeoutSeconds seconds."
}

Write-Host "[PHASE2] 1/4 Verify existing health task with current watchdog code"
$before = Get-Date
Start-ScheduledTask -TaskName "CryptoMiniPC-Health" -ErrorAction Stop
$healthBefore = Wait-FreshHealth -After $before

$gitIssue = @($healthBefore.issues | Where-Object { $_.check -in @("git_repo_check","git_available","git_branch","git_origin","git_head") })
if ($gitIssue.Count -gt 0) {
  throw ("Watchdog Git check still reports an issue: " + (($gitIssue | ForEach-Object { $_.detail }) -join " | "))
}

Write-Host "[PHASE2] 2/4 Install/start continuous public Kraken canary"
& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $canaryInstaller -TradingRoot $TradingRoot
if ($LASTEXITCODE -ne 0) { throw "Kraken canary installer failed with exit code $LASTEXITCODE" }

Write-Host "[PHASE2] 3/4 Re-run watchdog against the live canary"
$before2 = Get-Date
Start-ScheduledTask -TaskName "CryptoMiniPC-Health" -ErrorAction Stop
$healthAfter = Wait-FreshHealth -After $before2

$canaryCheck = $healthAfter.checks.kraken_canary_heartbeat
if (-not $canaryCheck -or $canaryCheck.ok -ne $true) {
  throw ("Watchdog did not accept Kraken canary heartbeat: " + $(if ($canaryCheck) { $canaryCheck.detail } else { "check missing" }))
}

Write-Host "[PHASE2] 4/4 Final summary"
$task = Get-ScheduledTask -TaskName "CryptoMiniPC-KrakenCanary" -ErrorAction Stop
$taskInfo = $task | Get-ScheduledTaskInfo
$hbPath = Join-Path $TradingRoot "State\kraken-canary-heartbeat.json"
$hb = Get-Content $hbPath -Raw | ConvertFrom-Json

Write-Host ""
Write-Host "=== MINI-PC PHASE2 ENABLE SUMMARY ==="
Write-Host ("Health before canary: " + $healthBefore.status)
Write-Host ("Kraken canary task: " + $task.State + " | last_result=" + $taskInfo.LastTaskResult)
Write-Host ("Canary heartbeat: " + $hb.status + " | events=" + $hb.events_total + " | book=" + $hb.book_events + " | trade=" + $hb.trade_events)
Write-Host ("Canary gaps=" + $hb.gaps + " | subscription_errors=" + $hb.subscription_errors)
Write-Host ("Watchdog after canary: " + $healthAfter.status)
Write-Host ("Watchdog canary check: " + $canaryCheck.ok + " | " + $canaryCheck.detail)
Write-Host "Safety: PUBLIC DATA ONLY / NO ACCOUNT / NO ORDERS / NO STRATEGY ACTION"
Write-Host "=== END ==="
