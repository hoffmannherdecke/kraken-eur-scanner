param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading"),
  [string]$CsvPath = "",
  [string]$EventTs = "",
  [int]$PreSeconds = 60,
  [int]$PostSeconds = 60,
  [switch]$Execute,
  [string]$Confirm = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedConfirm = "RUN_TARGETED_TRADES_SMOKE"
$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$python = Join-Path $TradingRoot "Runtime\kraken-eur-scanner-venv\Scripts\python.exe"
$tool = Join-Path $repo "tools\kraken-trades-targeted-smoke.py"
$historicalRoot = Join-Path $TradingRoot "Historical"
$reportDir = Join-Path $historicalRoot "reports"

$plan = [ordered]@{
  kind = "MINIPC_KRAKEN_TRADES_TARGETED_SMOKE_V1"
  status = $(if ($Execute) { "READY_TO_EXECUTE" } else { "PLAN_ONLY" })
  execute = [bool]$Execute
  csv_path = $CsvPath
  event_ts = $EventTs
  pre_seconds = $PreSeconds
  post_seconds = $PostSeconds
  network_used = $false
  download_performed = $false
  full_archive_download_authorized = $false
  guardrails = [ordered]@{
    existing_local_csv_only = $true
    performance_selection = $false
    holdout_opened = $false
    active_strategy_change = $false
    paper_shadow_runtime_change = $false
    private_exchange_api = $false
    orders = $false
    real_money_actions = $false
  }
}

if (-not $Execute) {
  $plan | ConvertTo-Json -Depth 8
  exit 0
}

if ($Confirm -ne $ExpectedConfirm) {
  throw "Execution blocked. Re-run with -Confirm $ExpectedConfirm"
}
if ([string]::IsNullOrWhiteSpace($CsvPath)) {
  throw "CsvPath is required in execute mode."
}
if ([string]::IsNullOrWhiteSpace($EventTs)) {
  throw "EventTs is required in execute mode."
}
if ($PreSeconds -le 0 -or $PostSeconds -le 0) {
  throw "PreSeconds and PostSeconds must be positive."
}
if (-not (Test-Path -LiteralPath $repo)) {
  throw "Repository missing: $repo"
}
if (-not (Test-Path -LiteralPath $python)) {
  throw "Python runtime missing: $python"
}
if (-not (Test-Path -LiteralPath $tool)) {
  throw "Targeted trades tool missing: $tool"
}

$csv = [System.IO.Path]::GetFullPath($CsvPath)
$hist = [System.IO.Path]::GetFullPath($historicalRoot)
if (-not (Test-Path -LiteralPath $csv -PathType Leaf)) {
  throw "CSV file missing: $csv"
}
if (-not $csv.StartsWith($hist, [System.StringComparison]::OrdinalIgnoreCase)) {
  throw "Execution blocked: CSV must live under $historicalRoot"
}

New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$out = Join-Path $reportDir ("kraken-trades-targeted-smoke-" + $stamp + ".json")

$hash = (Get-FileHash -LiteralPath $csv -Algorithm SHA256).Hash.ToLowerInvariant()

& $python $tool $csv --event-ts $EventTs --pre-seconds $PreSeconds --post-seconds $PostSeconds --output $out
if ($LASTEXITCODE -ne 0) {
  throw "Targeted Kraken trades smoke failed."
}

$result = Get-Content $out -Raw | ConvertFrom-Json
if ($result.status -ne "PASS") {
  throw "Targeted Kraken trades smoke did not return PASS."
}
if (-not [bool]$result.event_record_frozen_before_post_labels) {
  throw "Point-in-time freeze assertion failed."
}
if ([bool]$result.guardrails.download_performed) {
  throw "Guardrail violation: download_performed=true"
}
if ([bool]$result.guardrails.active_strategy_changed) {
  throw "Guardrail violation: active_strategy_changed=true"
}
if ([bool]$result.guardrails.real_money_actions) {
  throw "Guardrail violation: real_money_actions=true"
}

$summary = [ordered]@{
  kind = "MINIPC_KRAKEN_TRADES_TARGETED_SMOKE_V1"
  status = "PASS"
  source_csv = $csv
  source_sha256 = $hash
  report = $out
  event_ts = $EventTs
  pre_seconds = $PreSeconds
  post_seconds = $PostSeconds
  pre_trade_count = $result.pre_event_metrics.trade_count
  post_trade_count = $result.post_event_metrics.trade_count
  arrival_to_next_public_trade_seconds = $result.arrival_to_next_public_trade_seconds
  network_used = $false
  download_performed = $false
  guardrails = $plan.guardrails
  next_gate = "REVIEW_METHOD_ONLY_THEN_STORAGE_BENEFIT_DECISION"
}

Write-Host ""
Write-Host "=== MINI-PC TARGETED KRAKEN TRADES SMOKE SUMMARY ==="
$summary | ConvertTo-Json -Depth 8
Write-Host "=== END ==="
