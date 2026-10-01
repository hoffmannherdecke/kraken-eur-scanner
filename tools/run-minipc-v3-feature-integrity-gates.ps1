param(
  [string]$TradingRoot = "",
  [switch]$Execute
)
$ErrorActionPreference="Stop"
if ([string]::IsNullOrWhiteSpace($TradingRoot)) {
  $homeRoot = if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }
  if ([string]::IsNullOrWhiteSpace($homeRoot)) { throw "Unable to resolve user home directory." }
  $TradingRoot = Join-Path $homeRoot "Trading"
}
$repo=Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$python=Join-Path $TradingRoot "Runtime\kraken-eur-scanner-venv\Scripts\python.exe"
$normalized=Join-Path $TradingRoot "Historical\normalized\kraken\eur\15m"
$catalog=Join-Path $TradingRoot "Historical\catalog\kraken-eur15-normalization.json"
$reports=Join-Path $TradingRoot "Historical\reports"
foreach($p in @($repo,$python,$normalized,$catalog)){if(-not(Test-Path $p)){throw "Required path missing: $p"}}
New-Item -ItemType Directory -Force -Path $reports|Out-Null
$stamp=Get-Date -Format "yyyyMMdd-HHmmss"
$h6out=Join-Path $reports ("v3-h6-feature-integrity-"+$stamp+".json")
$h1out=Join-Path $reports ("v3-h1-breadth-feature-integrity-"+$stamp+".json")
$h6=@((Join-Path $repo "tools\v3-h6-eur15-feature-integrity.py"),$normalized,"--catalog",$catalog,"--output",$h6out)
$h1=@((Join-Path $repo "tools\v3-h1-eur15-breadth-feature-integrity.py"),$normalized,"--catalog",$catalog,"--output",$h1out)
Write-Host "=== V3 LOCAL FEATURE-INTEGRITY GATE ==="
Write-Host "Mode: " ($(if($Execute){"EXECUTE"}else{"PLAN ONLY"}))
Write-Host "H6 output: $h6out"
Write-Host "H1 output: $h1out"
Write-Host "Safety: local historical files only / pre-2026 development / no network / no labels / no strategy mutation"
if(-not $Execute){
  Write-Host "No trial executed. Re-run with -Execute at the physical gate."
  exit 0
}
Push-Location $repo
try{
  & $python @h6
  if($LASTEXITCODE -ne 0){throw "H6 feature-integrity execution failed"}
  $r6=Get-Content $h6out -Raw|ConvertFrom-Json
  if($r6.status -ne "PASS" -or $r6.guardrails.holdout_opened -ne $false){throw "H6 report guard failed"}

  & $python @h1
  if($LASTEXITCODE -ne 0){throw "H1 feature-integrity execution failed"}
  $r1=Get-Content $h1out -Raw|ConvertFrom-Json
  if($r1.status -ne "PASS" -or $r1.guardrails.holdout_opened -ne $false){throw "H1 report guard failed"}
}finally{Pop-Location}
Write-Host "=== V3 FEATURE-INTEGRITY SUMMARY ==="
Write-Host ("H6 PASS rows="+$r6.dataset.rows_processed_before_holdout+" sha="+$r6.deterministic_summary_sha256)
Write-Host ("H1 PASS rows="+$r1.dataset.feature_rows_processed_before_holdout+" cutoffs="+$r1.cutoffs_processed+" sha="+$r1.deterministic_summary_sha256)
Write-Host "Holdout: CLOSED | V2R3/V2R4: UNCHANGED | Orders: NONE"
