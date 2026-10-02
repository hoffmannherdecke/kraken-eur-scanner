param(
  [string]$TradingRoot = "",
  [string]$Output = ""
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
if([string]::IsNullOrWhiteSpace($TradingRoot)){
  $homeRoot=if($env:USERPROFILE){$env:USERPROFILE}else{$HOME}
  if([string]::IsNullOrWhiteSpace($homeRoot)){throw "Unable to resolve user home directory."}
  $TradingRoot=Join-Path $homeRoot "Trading"
}
$repo=Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$python=Join-Path $TradingRoot "Runtime\kraken-eur-scanner-venv\Scripts\python.exe"
$tool=Join-Path $repo "tools\collect-v3-h1-h6-association-evidence.py"
if([string]::IsNullOrWhiteSpace($Output)){
  $Output=Join-Path $TradingRoot "Historical\reports\v3-h1-h6-association-evidence-latest.json"
}
foreach($p in @($repo,$python,$tool)){if(-not(Test-Path -LiteralPath $p)){throw "Required path missing: $p"}}
& $python $tool --trading-root $TradingRoot --output $Output
if($LASTEXITCODE -ne 0){throw "H1/H6 association evidence collector failed"}
$r=Get-Content $Output -Raw|ConvertFrom-Json
if($r.status -ne "PASS"){throw "collector result not PASS"}
Write-Host ""
Write-Host "=== V3 H1/H6 ASSOCIATION EVIDENCE COLLECTED ==="
Write-Host ("Output: "+$Output)
Write-Host ("H1 summary SHA: "+$r.source_reports.h1.deterministic_summary_sha256)
Write-Host ("H6 summary SHA: "+$r.source_reports.h6.deterministic_summary_sha256)
Write-Host ("Trial ledger count: "+$r.trial_ledger.verify.trial_count+" | corrupt="+$r.trial_ledger.verify.corrupt_trial_ids.Count)
Write-Host "No tests re-run / holdout closed / no threshold search / no winner / no network / no orders"
