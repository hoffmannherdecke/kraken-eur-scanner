param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading"),
  [int]$OfflineSeconds = 20
)

$ErrorActionPreference = "Stop"

if ($OfflineSeconds -lt 10 -or $OfflineSeconds -gt 45) {
  throw "OfflineSeconds must be between 10 and 45."
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw "Bitte dieses Skript in einer als Administrator gestarteten PowerShell ausführen."
}

$stateDir = Join-Path $TradingRoot "State"
$logDir = Join-Path $TradingRoot "Logs"
$tempDir = Join-Path $TradingRoot "Temp"
$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$watchdog = Join-Path $repo "tools\minipc-watchdog.ps1"

foreach ($p in @($stateDir,$logDir,$tempDir,$repo,$watchdog)) {
  if (-not (Test-Path $p)) { throw "Required path missing: $p" }
}

function Read-Json([string]$Path) {
  if (-not (Test-Path $Path)) { return $null }
  return (Get-Content $Path -Raw | ConvertFrom-Json)
}
function Age-Sec([string]$Timestamp) {
  return [math]::Round(((Get-Date).ToUniversalTime() - ([datetime]$Timestamp).ToUniversalTime()).TotalSeconds,1)
}

$canaryPath = Join-Path $stateDir "kraken-canary-heartbeat.json"
$universePath = Join-Path $stateDir "kraken-eur-universe-heartbeat.json"
$altradyPath = Join-Path $stateDir "altrady-trigger-heartbeat.json"

$beforeCanary = Read-Json $canaryPath
$beforeUniverse = Read-Json $universePath
$beforeAltrady = Read-Json $altradyPath

if (-not $beforeCanary -or -not $beforeUniverse -or -not $beforeAltrady) {
  throw "One or more required pre-test heartbeats are missing."
}
if ($beforeCanary.status -notin @("HEALTHY","CONNECTED")) { throw "Kraken canary is not healthy before outage test." }
if ($beforeUniverse.status -notin @("HEALTHY","CONNECTED")) { throw "Kraken universe feed is not healthy before outage test." }
if ($beforeAltrady.status -ne "HEALTHY") { throw "Altrady transport is not healthy before outage test." }

$defaultRoute = Get-NetRoute -AddressFamily IPv4 -DestinationPrefix "0.0.0.0/0" -ErrorAction Stop |
  Where-Object { $_.State -eq "Alive" } |
  Sort-Object RouteMetric,InterfaceMetric |
  Select-Object -First 1
if (-not $defaultRoute) { throw "No active IPv4 default route found." }

$adapter = Get-NetAdapter -InterfaceIndex $defaultRoute.InterfaceIndex -ErrorAction Stop
if (-not $adapter) { throw "Default-route network adapter not found." }
if ($adapter.Status -ne "Up") { throw "Selected adapter is not Up: $($adapter.Name) / $($adapter.Status)" }

$adapterName = [string]$adapter.Name
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$reportPath = Join-Path $logDir "minipc-internet-recovery-$stamp.json"

# Safety first: arm an independent SYSTEM one-shot network re-enable before disabling anything.
$safetyTaskName = "CryptoMiniPC-NetworkRecoverySafety"
$safetyScript = Join-Path $tempDir ("minipc-network-reenable-" + [guid]::NewGuid().ToString("N") + ".ps1")
$safetyRunAt = (Get-Date).AddSeconds($OfflineSeconds + 20)
$escapedAdapter = $adapterName.Replace("'","''")
$safetyBody = '$ErrorActionPreference = ''SilentlyContinue''' + [Environment]::NewLine +
  ('Enable-NetAdapter -Name ''' + $escapedAdapter + ''' -Confirm:$false')
[System.IO.File]::WriteAllText($safetyScript,$safetyBody,[System.Text.UTF8Encoding]::new($false))

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument ('-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + $safetyScript + '"')
$trigger = New-ScheduledTaskTrigger -Once -At $safetyRunAt
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName $safetyTaskName -Action $action -Trigger $trigger -Settings $settings -User "SYSTEM" -RunLevel Highest -Force | Out-Null

Write-Host ""
Write-Host "=== CONTROLLED INTERNET OUTAGE TEST ==="
Write-Host ("Adapter: " + $adapterName)
Write-Host ("Offline window: " + $OfflineSeconds + " seconds")
Write-Host ("Safety re-enable task armed for: " + $safetyRunAt.ToString("HH:mm:ss"))
Write-Host "The network/RDP connection may drop briefly. Automatic recovery is armed."
Write-Host ""

$disabledObserved = $false
$reEnabledByPrimary = $false
$krakenDuringOutageFailed = $false
$issues = New-Object System.Collections.Generic.List[string]
$notes = New-Object System.Collections.Generic.List[string]

try {
  Disable-NetAdapter -Name $adapterName -Confirm:$false -ErrorAction Stop
  Start-Sleep -Seconds 2

  $adapterAfterDisable = Get-NetAdapter -Name $adapterName -ErrorAction Stop
  if ($adapterAfterDisable.Status -ne "Up") {
    $disabledObserved = $true
  } else {
    $issues.Add("adapter_disable_not_observed")
  }

  try {
    Invoke-WebRequest -UseBasicParsing -Uri "https://api.kraken.com/0/public/Time" -TimeoutSec 4 | Out-Null
  } catch {
    $krakenDuringOutageFailed = $true
  }
  if (-not $krakenDuringOutageFailed) {
    $notes.Add("kraken_probe_did_not_fail_during_outage_window")
  }

  Start-Sleep -Seconds ([math]::Max(1,$OfflineSeconds-2))

  Enable-NetAdapter -Name $adapterName -Confirm:$false -ErrorAction Stop
  $reEnabledByPrimary = $true
} finally {
  try { Enable-NetAdapter -Name $adapterName -Confirm:$false -ErrorAction SilentlyContinue } catch {}
}

Write-Host "Network adapter re-enable requested. Waiting for transport recovery..."

$deadline = (Get-Date).AddSeconds(120)
$afterCanary = $null
$afterUniverse = $null
$afterAltrady = $null
$krakenHttp = $null
$adapterRecovered = $false

while ((Get-Date) -lt $deadline) {
  Start-Sleep -Seconds 3

  try {
    $a = Get-NetAdapter -Name $adapterName -ErrorAction Stop
    $adapterRecovered = ($a.Status -eq "Up")
  } catch {
    $adapterRecovered = $false
  }

  try {
    $r = Invoke-WebRequest -UseBasicParsing -Uri "https://api.kraken.com/0/public/Time" -TimeoutSec 5
    $krakenHttp = [int]$r.StatusCode
  } catch {
    $krakenHttp = $null
  }

  $afterCanary = Read-Json $canaryPath
  $afterUniverse = Read-Json $universePath
  $afterAltrady = Read-Json $altradyPath

  $canaryGood = (
    $afterCanary -and
    $afterCanary.status -in @("HEALTHY","CONNECTED") -and
    (Age-Sec $afterCanary.checked_at_utc) -le 45 -and
    [int]$afterCanary.events_total -gt [int]$beforeCanary.events_total
  )
  $universeGood = (
    $afterUniverse -and
    $afterUniverse.status -in @("HEALTHY","CONNECTED") -and
    (Age-Sec $afterUniverse.checked_at_utc) -le 45 -and
    [double]$afterUniverse.coverage_pct -ge 80 -and
    [int]$afterUniverse.subscription_errors -eq 0 -and
    [int]$afterUniverse.ticker_rows -gt [int]$beforeUniverse.ticker_rows
  )
  $altradyGood = (
    $afterAltrady -and
    $afterAltrady.status -eq "HEALTHY" -and
    (Age-Sec $afterAltrady.checked_at_utc) -le 90
  )

  if ($adapterRecovered -and $krakenHttp -eq 200 -and $canaryGood -and $universeGood -and $altradyGood) {
    break
  }
}

if (-not $adapterRecovered) { $issues.Add("adapter_not_recovered") }
if ($krakenHttp -ne 200) { $issues.Add("kraken_http_not_recovered") }

if (-not $afterCanary) {
  $issues.Add("kraken_canary_missing_after_recovery")
} else {
  if ($afterCanary.status -notin @("HEALTHY","CONNECTED")) { $issues.Add("kraken_canary_not_healthy_after_recovery") }
  if ((Age-Sec $afterCanary.checked_at_utc) -gt 45) { $issues.Add("kraken_canary_stale_after_recovery") }
  if ([int]$afterCanary.events_total -le [int]$beforeCanary.events_total) { $issues.Add("kraken_canary_not_advancing_after_recovery") }
}

if (-not $afterUniverse) {
  $issues.Add("kraken_universe_missing_after_recovery")
} else {
  if ($afterUniverse.status -notin @("HEALTHY","CONNECTED")) { $issues.Add("kraken_universe_not_healthy_after_recovery") }
  if ((Age-Sec $afterUniverse.checked_at_utc) -gt 45) { $issues.Add("kraken_universe_stale_after_recovery") }
  if ([double]$afterUniverse.coverage_pct -lt 80) { $issues.Add("kraken_universe_low_coverage_after_recovery") }
  if ([int]$afterUniverse.subscription_errors -gt 0) { $issues.Add("kraken_universe_subscription_errors_after_recovery") }
  if ([int]$afterUniverse.ticker_rows -le [int]$beforeUniverse.ticker_rows) { $issues.Add("kraken_universe_not_advancing_after_recovery") }
}

if (-not $afterAltrady) {
  $issues.Add("altrady_missing_after_recovery")
} else {
  if ($afterAltrady.status -ne "HEALTHY") { $issues.Add("altrady_not_healthy_after_recovery") }
  if ((Age-Sec $afterAltrady.checked_at_utc) -gt 90) { $issues.Add("altrady_stale_after_recovery") }
}

& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $watchdog -TradingRoot $TradingRoot | Out-Null
$watchdogCode = $LASTEXITCODE
$health = Read-Json (Join-Path $stateDir "minipc-health.json")
if ($watchdogCode -eq 2 -or ($health -and $health.status -eq "CRITICAL")) {
  $issues.Add("watchdog_critical_after_recovery")
} elseif ($health -and $health.status -eq "WARNING") {
  $notes.Add("watchdog_warning_after_recovery")
}

if ($adapterRecovered) {
  try { Unregister-ScheduledTask -TaskName $safetyTaskName -Confirm:$false -ErrorAction SilentlyContinue } catch {}
  try { Remove-Item -LiteralPath $safetyScript -Force -ErrorAction SilentlyContinue } catch {}
}

$status = if ($issues.Count -gt 0) { "FAIL" } elseif ($notes.Count -gt 0) { "PASS_WITH_NOTES" } else { "PASS" }

$result = [ordered]@{
  schema_version = 1
  kind = "MINIPC_INTERNET_RECOVERY_GATE_V1"
  checked_at_local = (Get-Date).ToString("o")
  status = $status
  adapter = [ordered]@{
    name = $adapterName
    disable_observed = $disabledObserved
    reenabled_by_primary_script = $reEnabledByPrimary
    recovered = $adapterRecovered
    offline_seconds_requested = $OfflineSeconds
  }
  outage_probe = [ordered]@{
    kraken_probe_failed_during_outage = $krakenDuringOutageFailed
  }
  recovery = [ordered]@{
    kraken_http_status = $krakenHttp
    kraken_canary = if ($afterCanary) {
      [ordered]@{
        status = $afterCanary.status
        age_sec = Age-Sec $afterCanary.checked_at_utc
        events_before = [int]$beforeCanary.events_total
        events_after = [int]$afterCanary.events_total
        connections_before = [int]$beforeCanary.connections_started
        connections_after = [int]$afterCanary.connections_started
        gaps_after = [int]$afterCanary.gaps
        subscription_errors_after = [int]$afterCanary.subscription_errors
      }
    } else { $null }
    kraken_universe = if ($afterUniverse) {
      [ordered]@{
        status = $afterUniverse.status
        age_sec = Age-Sec $afterUniverse.checked_at_utc
        pair_count = [int]$afterUniverse.pair_count
        observed_pair_count = [int]$afterUniverse.observed_pair_count
        coverage_pct = [double]$afterUniverse.coverage_pct
        ticker_rows_before = [int]$beforeUniverse.ticker_rows
        ticker_rows_after = [int]$afterUniverse.ticker_rows
        reconnects_before = [int]$beforeUniverse.reconnects
        reconnects_after = [int]$afterUniverse.reconnects
        subscription_errors_after = [int]$afterUniverse.subscription_errors
      }
    } else { $null }
    altrady = if ($afterAltrady) {
      [ordered]@{
        status = $afterAltrady.status
        age_sec = Age-Sec $afterAltrady.checked_at_utc
      }
    } else { $null }
    watchdog = if ($health) { $health.status } else { $null }
  }
  issues = @($issues)
  notes = @($notes)
  guardrails = [ordered]@{
    transport_only = $true
    strategy_action = "NONE_TRANSPORT_ONLY"
    queue_replay = "NOT_APPLICABLE_STRATEGY_NOT_COUPLED"
    real_money_actions = $false
  }
}

[System.IO.File]::WriteAllText(
  $reportPath,
  ($result | ConvertTo-Json -Depth 10) + [Environment]::NewLine,
  [System.Text.UTF8Encoding]::new($false)
)

Write-Host ""
Write-Host "=== MINI-PC INTERNET RECOVERY SUMMARY ==="
Write-Host ("Status: " + $status)
Write-Host ("Adapter: " + $adapterName + " | disable_observed=" + $disabledObserved + " | recovered=" + $adapterRecovered)
Write-Host ("Kraken outage probe failed as expected: " + $krakenDuringOutageFailed)
Write-Host ("Kraken HTTP after recovery: " + $(if ($krakenHttp) { $krakenHttp } else { "failed" }))
if ($afterCanary) {
  Write-Host ("Kraken canary: " + $afterCanary.status + " | events " + $beforeCanary.events_total + " -> " + $afterCanary.events_total + " | connections " + $beforeCanary.connections_started + " -> " + $afterCanary.connections_started)
}
if ($afterUniverse) {
  Write-Host ("Kraken EUR universe: " + $afterUniverse.status + " | " + $afterUniverse.observed_pair_count + "/" + $afterUniverse.pair_count + " | coverage=" + $afterUniverse.coverage_pct + "% | ticker_rows " + $beforeUniverse.ticker_rows + " -> " + $afterUniverse.ticker_rows + " | reconnects " + $beforeUniverse.reconnects + " -> " + $afterUniverse.reconnects)
}
if ($afterAltrady) {
  Write-Host ("Altrady transport: " + $afterAltrady.status + " | age=" + (Age-Sec $afterAltrady.checked_at_utc) + "s")
}
Write-Host ("Watchdog: " + $(if ($health) { $health.status } else { "missing" }))
if ($issues.Count -gt 0) { Write-Host ("Issues: " + ($issues -join ", ")) } else { Write-Host "Issues: none" }
if ($notes.Count -gt 0) { Write-Host ("Notes: " + ($notes -join ", ")) } else { Write-Host "Notes: none" }
Write-Host ("Report: " + $reportPath)
Write-Host "Safety: TRANSPORT-ONLY / STRATEGY NOT COUPLED / NO REAL-MONEY ACTION"
Write-Host "=== END ==="

if ($issues.Count -gt 0) { exit 2 }
exit 0
