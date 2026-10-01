param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading"),
  [double]$Hours = 6
)

$ErrorActionPreference = "Stop"

if ($Hours -le 0 -or $Hours -gt 336) {
  throw "Hours must be > 0 and <= 336."
}

$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$python = Join-Path $TradingRoot "Runtime\kraken-eur-scanner-venv\Scripts\python.exe"
$tool = Join-Path $repo "tools\v2r4-ws-shadow-evidence.py"
$ledger = Join-Path $TradingRoot "Logs\v2r4-ws-shadow-ledger.jsonl"
$heartbeat = Join-Path $TradingRoot "State\v2r4-ws-shadow-heartbeat.json"
$manifest = Join-Path $TradingRoot "State\v2r4-ws-shadow-runtime.json"
$out = Join-Path $TradingRoot "Logs\v2r4-ws-shadow-evidence-latest.json"

foreach ($p in @($python,$tool,$heartbeat,$manifest)) {
  if (-not (Test-Path $p)) { throw "Required path missing: $p" }
}

$argList = @($tool, "--ledger", $ledger, "--heartbeat", $heartbeat, "--manifest", $manifest, "--hours", [string]$Hours, "--out", $out)
& $python @argList
if ($LASTEXITCODE -ne 0) {
  throw "V2R4 WS shadow evidence summary failed with exit code $LASTEXITCODE."
}

$s = Get-Content $out -Raw | ConvertFrom-Json
$hb = $s.latest_heartbeat
$source = $s.source_age_seconds
$feed = $s.feed_to_shadow_latency_ms

Write-Host ""
Write-Host "=== V2R4 WS SHADOW EVIDENCE SUMMARY ==="
Write-Host ("Window: " + $Hours + " h")
Write-Host ("Heartbeat: " + $(if ($hb) { $hb.status } else { "missing" }))
Write-Host ("Cycles: " + $s.cycle_count + " | shadow events=" + $s.event_count + " | triggered-pair observations=" + $s.triggered_pairs_total)
Write-Host ("Source age: median=" + $source.median + "s | p90=" + $source.p90 + "s | max=" + $source.max + "s")
Write-Host ("Feed->shadow event latency: median=" + $feed.median + "ms | p90=" + $feed.p90 + "ms | max=" + $feed.max + "ms")
Write-Host ("Stale pair observations: " + $s.stale_pairs_total + " | gap-suppressed cycles=" + $s.gap_suppressed_cycles + " | max recovery epoch=" + $s.max_recovery_epoch)
if ($s.top_event_pairs.Count -gt 0) {
  Write-Host ("Top event pairs: " + (($s.top_event_pairs | ForEach-Object { $_[0] + "=" + $_[1] }) -join ", "))
} else {
  Write-Host "Top event pairs: none yet"
}
if ($s.top_trigger_reasons.Count -gt 0) {
  Write-Host ("Top reasons: " + (($s.top_trigger_reasons | ForEach-Object { $_[0] + "=" + $_[1] }) -join ", "))
} else {
  Write-Host "Top reasons: none yet"
}
Write-Host ("Report: " + $out)
Write-Host "Safety: READ-ONLY SUMMARY / NO EVALUATOR / NO ORDERS / NO REAL-MONEY ACTION"
Write-Host "=== END ==="
