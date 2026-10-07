param(
  [string]$TradingRoot = "",
  [switch]$Execute
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ([string]::IsNullOrWhiteSpace($TradingRoot)) {
  $homeRoot = if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }
  if ([string]::IsNullOrWhiteSpace($homeRoot)) { throw "Unable to resolve user home directory." }
  $TradingRoot = Join-Path $homeRoot "Trading"
}

$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$app = Join-Path $TradingRoot "Runtime\v2r4-paper-app"
$python = Join-Path $TradingRoot "Runtime\kraken-eur-scanner-venv\Scripts\python.exe"
$apiKey = Join-Path $TradingRoot "Secrets\openai-api-key.txt"
$tool = Join-Path $repo "tools\v3-h3-shadow-e2e.py"
$logs = Join-Path $TradingRoot "Logs"

foreach($p in @($repo,$app,$python,$apiKey,$tool)){
  if(-not(Test-Path -LiteralPath $p)){ throw "Required path missing: $p" }
}
New-Item -ItemType Directory -Force -Path $logs | Out-Null

if(-not $Execute){
  [pscustomobject]@{
    kind='V3_H3_PHYSICAL_SHADOW_E2E_PLAN_V1'
    status='PLAN_ONLY'
    physical_ws_smoke_reused=$true
    active_v2r4_mutation=$false
    orders=$false
    real_money_actions=$false
  } | ConvertTo-Json -Depth 6
  exit 0
}

$control = Get-Content (Join-Path $app 'paper_runtime_control.json') -Raw | ConvertFrom-Json
if($control.enabled -ne $true){ throw "Active V2R4 app is disabled." }
if($control.paper_only -ne $true -or $control.real_money_actions_enabled -ne $false){
  throw "Unsafe V2R4 control flags."
}
if($control.strategy_revision -ne 'V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION'){
  throw "Unexpected active V2R4 revision: $($control.strategy_revision)"
}

$physical = @(Get-ChildItem $logs -Filter 'v3-h3-ws-book-smoke-*.json' | Sort-Object LastWriteTime -Descending)
if($physical.Count -lt 1){ throw "No prior H3 physical WS smoke report found." }
$p = Get-Content $physical[0].FullName -Raw | ConvertFrom-Json
if($p.status -ne 'PASS' -or [int]$p.totals.checksum_fail -ne 0 -or $p.interpretation.bounded_reconnect_resubscribe_proven -ne $true){
  throw "Latest physical H3 smoke is not a clean PASS."
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$out = Join-Path $logs ("v3-h3-shadow-e2e-" + $stamp + ".json")

Write-Host "=== V3 H3 PHYSICAL SHADOW E2E ==="
Write-Host ("Baseline series: " + $control.series_id)
Write-Host ("Reusing physical PASS: " + $physical[0].Name)
Write-Host "Scope: isolated synthetic candidate -> V2R4 baseline -> +H3 context shadow"
Write-Host "Safety: no active candidate/decision/position write; no orders; no real money"

& $python $tool --app-root $app --trading-root $TradingRoot --api-key-file $apiKey --output $out --capture-seconds 8
if($LASTEXITCODE -ne 0){ throw "V3 H3 physical shadow E2E failed." }

$r = Get-Content $out -Raw | ConvertFrom-Json
if($r.status -ne 'PASS'){ throw "H3 E2E report is not PASS." }
if($r.active_baseline.series_id -ne $control.series_id){ throw "H3 E2E baseline series mismatch." }
if($r.physical_prerequisite.checksum_fail -ne 0){ throw "H3 physical checksum guard failed." }
if($r.routing_checks.noneligible -ne 'BASELINE_PASSTHROUGH_NONELIGIBLE_PAIR'){ throw "Noneligible passthrough failed." }
if($r.routing_checks.missing -ne 'BASELINE_PASSTHROUGH_H3_CONTEXT_MISSING'){ throw "Missing-state passthrough failed." }
if($r.routing_checks.duplicate -ne 'DUPLICATE_SKIPPED'){ throw "Duplicate guard failed." }
if($r.guardrails.active_v2r4_strategy_changed -ne $false -or $r.guardrails.orders -ne $false -or $r.guardrails.real_money_actions -ne $false){
  throw "H3 E2E safety guard failed."
}

Write-Host ""
Write-Host ("PASS baseline=" + $r.baseline_decision.decision + " h3=" + $r.h3_shadow_decision.decision + " diverged=" + $r.decision_diverged)
Write-Host ("Physical updates=" + $r.physical_prerequisite.updates + " checksum_pass=" + $r.physical_prerequisite.checksum_pass + " checksum_fail=0")
Write-Host ("Report: " + $out)
Write-Host "V2R4 unchanged / no orders / no real-money action"
