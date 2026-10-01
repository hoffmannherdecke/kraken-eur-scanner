param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading"),
  [int]$Seconds = 30
)

$ErrorActionPreference = "Stop"

if ($Seconds -lt 10 -or $Seconds -gt 90) {
  throw "Seconds must be between 10 and 90."
}

$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$python = Join-Path $TradingRoot "Runtime\kraken-eur-scanner-venv\Scripts\python.exe"
$snapshot = Join-Path $TradingRoot "State\kraken-eur-ticker-latest.json"
$tempRoot = Join-Path $TradingRoot "Temp"
$logDir = Join-Path $TradingRoot "Logs"

foreach ($p in @($repo,$python,$snapshot)) {
  if (-not (Test-Path $p)) { throw "Required path missing: $p" }
}

New-Item -ItemType Directory -Force -Path $tempRoot,$logDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$worktree = Join-Path $tempRoot ("v2r4-ws-shadow-code-" + $stamp)
$runtime = Join-Path $tempRoot ("v2r4-ws-shadow-run-" + $stamp)
New-Item -ItemType Directory -Force -Path $runtime | Out-Null

$state = Join-Path $runtime "state.json"
$events = Join-Path $runtime "events"
$ledger = Join-Path $runtime "ledger.jsonl"
$heartbeat = Join-Path $runtime "heartbeat.json"
$report = Join-Path $logDir ("minipc-v2r4-ws-shadow-smoke-" + $stamp + ".json")
$branch = "prep/v2r4-fast-trigger-minipc-20260929"

Write-Host "=== V2R4 WS SHADOW PHYSICAL SMOKE ==="
Write-Host "1/4 Fetch inactive V2R4 prep branch..."

Push-Location $repo
try {
  git fetch origin $branch
  if ($LASTEXITCODE -ne 0) { throw "git fetch failed" }

  git worktree add --detach $worktree ("origin/" + $branch)
  if ($LASTEXITCODE -ne 0) { throw "git worktree add failed" }
} finally {
  Pop-Location
}

try {
  Write-Host "2/4 Compile + focused tests..."
  Push-Location $worktree
  try {
    & $python -m py_compile ".\paper_evaluator\v2r4_precandidate_discovery.py" ".\paper_evaluator\v2r4_ws_shadow_watcher.py"
    if ($LASTEXITCODE -ne 0) { throw "V2R4 WS shadow compile failed" }

    & $python -m unittest "tests.test_v2r4_ws_shadow_watcher" -v
    if ($LASTEXITCODE -ne 0) { throw "V2R4 WS shadow unit tests failed" }

    Write-Host "3/4 Consume the real local Kraken WS snapshot for $Seconds seconds..."
    $shadowArgs = @(
      ".\paper_evaluator\v2r4_ws_shadow_watcher.py",
      "--snapshot", $snapshot,
      "--state", $state,
      "--event-dir", $events,
      "--ledger", $ledger,
      "--heartbeat", $heartbeat,
      "--poll-seconds", "1",
      "--max-runtime-seconds", [string]$Seconds,
      "--cooldown-seconds", "0"
    )
    & $python @shadowArgs
    if ($LASTEXITCODE -ne 0) { throw "V2R4 WS shadow bounded run failed" }
  } finally {
    Pop-Location
  }

  Write-Host "4/4 Validate feed consumption + timing ledger..."

  if (-not (Test-Path $state)) { throw "shadow state missing" }
  if (-not (Test-Path $ledger)) { throw "shadow timing ledger missing" }
  if (-not (Test-Path $heartbeat)) { throw "shadow heartbeat missing" }

  $s = Get-Content $state -Raw | ConvertFrom-Json
  $h = Get-Content $heartbeat -Raw | ConvertFrom-Json
  $source = Get-Content $snapshot -Raw | ConvertFrom-Json

  $cycles = @()
  Get-Content $ledger | ForEach-Object {
    if (-not [string]::IsNullOrWhiteSpace($_)) {
      $row = $_ | ConvertFrom-Json
      if ($row.record_type -eq "cycle" -and $row.status -eq "HEALTHY") {
        $cycles += $row
      }
    }
  }

  $processed = [int]$s.counters.snapshots_processed
  $duplicates = [int]$s.counters.duplicates_skipped
  $stale = [int]$s.counters.stale_inputs
  $gapRecoveries = [int]$s.counters.gap_recoveries
  $eventsEmitted = [int]$s.counters.events_emitted
  $pairCount = [int]$source.pair_count
  $observedCount = [int]$source.observed_pair_count

  if ($processed -lt 2) { throw "Expected at least 2 fresh WS snapshots, got $processed" }
  if ($cycles.Count -lt 2) { throw "Expected at least 2 HEALTHY ledger cycles, got $($cycles.Count)" }
  if ($stale -ne 0) { throw "Unexpected stale input cycles: $stale" }
  if ($gapRecoveries -ne 0) { throw "Unexpected feed gap during bounded smoke: $gapRecoveries" }
  if ($pairCount -lt 100) { throw "Unexpectedly small Kraken EUR universe: $pairCount" }
  if ($observedCount -lt [math]::Floor($pairCount * 0.80)) {
    throw "Observed universe below 80%: $observedCount / $pairCount"
  }

  $latencies = @($cycles | ForEach-Object { [double]$_.source_age_seconds })
  $avgLatency = if ($latencies.Count -gt 0) {
    [math]::Round((($latencies | Measure-Object -Average).Average),3)
  } else { $null }
  $maxLatency = if ($latencies.Count -gt 0) {
    [math]::Round((($latencies | Measure-Object -Maximum).Maximum),3)
  } else { $null }

  $result = [ordered]@{
    kind = "MINIPC_V2R4_WS_SHADOW_SMOKE_V1"
    checked_at_local = (Get-Date).ToString("o")
    status = "PASS"
    source_kind = $source.kind
    source_pair_count = $pairCount
    source_observed_pair_count = $observedCount
    snapshots_processed = $processed
    duplicates_skipped = $duplicates
    stale_inputs = $stale
    gap_recoveries = $gapRecoveries
    shadow_events_emitted = $eventsEmitted
    healthy_ledger_cycles = $cycles.Count
    source_age_seconds_avg = $avgLatency
    source_age_seconds_max = $maxLatency
    final_heartbeat_status = $h.status
    guardrails = [ordered]@{
      v2r3_changed = $false
      evaluator_invoked = $false
      strategy_action = "NONE_SHADOW_ONLY"
      order_api = $false
      real_money_actions = $false
    }
  }

  [System.IO.File]::WriteAllText(
    $report,
    ($result | ConvertTo-Json -Depth 8) + [Environment]::NewLine,
    [System.Text.UTF8Encoding]::new($false)
  )

  Write-Host ""
  Write-Host "=== V2R4 WS SHADOW SMOKE SUMMARY ==="
  Write-Host "Status: PASS"
  Write-Host ("Kraken EUR snapshot: " + $observedCount + "/" + $pairCount)
  Write-Host ("Fresh snapshots consumed: " + $processed + " | duplicates skipped=" + $duplicates)
  Write-Host ("Stale inputs: " + $stale + " | gap recoveries=" + $gapRecoveries)
  Write-Host ("Healthy ledger cycles: " + $cycles.Count + " | source age avg=" + $avgLatency + "s | max=" + $maxLatency + "s")
  Write-Host ("Shadow discovery events: " + $eventsEmitted + " (observation only; no evaluator/order action)")
  Write-Host ("Report: " + $report)
  Write-Host "Safety: V2R3 UNCHANGED / SHADOW ONLY / NO EVALUATOR / NO ORDERS / NO REAL-MONEY ACTION"
  Write-Host "=== END ==="
} finally {
  Push-Location $repo
  try {
    if (Test-Path $worktree) {
      git worktree remove --force $worktree | Out-Null
    }
    git worktree prune | Out-Null
  } finally {
    Pop-Location
  }
}
