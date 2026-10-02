param(
  [string]$TradingRoot = "",
  [string]$Output = ""
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
if ([string]::IsNullOrWhiteSpace($TradingRoot)) {
  $homeRoot = if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }
  if ([string]::IsNullOrWhiteSpace($homeRoot)) { throw "Unable to resolve user home directory." }
  $TradingRoot = Join-Path $homeRoot "Trading"
}
$repo=Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$python=Join-Path $TradingRoot "Runtime\kraken-eur-scanner-venv\Scripts\python.exe"
$tool=Join-Path $repo "tools\collect-v3-physical-gate-evidence.py"
if([string]::IsNullOrWhiteSpace($Output)){
  $Output=Join-Path $TradingRoot "Historical\reports\v3-physical-gate-bundle-evidence-latest.json"
}
foreach($p in @($repo,$python,$tool)){if(-not(Test-Path -LiteralPath $p)){throw "Required path missing: $p"}}
& $python $tool --trading-root $TradingRoot --output $Output
if($LASTEXITCODE -ne 0){throw "V3 physical-gate evidence collector failed"}
$r=Get-Content $Output -Raw|ConvertFrom-Json
if($r.status -ne "PASS"){throw "collector result not PASS"}
Write-Host ""
Write-Host "=== V3 PHYSICAL GATE EVIDENCE COLLECTED ==="
Write-Host ("Output: "+$Output)
Write-Host ("H6 rows: "+$r.h6.rows_processed_before_holdout+" | sha: "+$r.h6.deterministic_summary_sha256)
Write-Host ("H1 rows: "+$r.h1.feature_rows_processed_before_holdout+" | cutoffs: "+$r.h1.cutoffs_processed+" | sha: "+$r.h1.deterministic_summary_sha256)
Write-Host ("H3 updates/checksum: "+$r.h3.updates+"/"+$r.h3.checksum_pass+" | fail="+$r.h3.checksum_fail)
Write-Host ("H9 trades/aligned: "+$r.h9.trades+"/"+$r.h9.aligned_preceding_book_trades)
Write-Host ("Binance: "+$r.binance.status)
Write-Host "No tests re-run / no network / no orders / no strategy mutation"
