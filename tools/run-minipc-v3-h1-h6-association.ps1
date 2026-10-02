param(
  [string]$TradingRoot = "",
  [switch]$Execute,
  [string]$Confirm = ""
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
if([string]::IsNullOrWhiteSpace($TradingRoot)){
  $homeRoot=if($env:USERPROFILE){$env:USERPROFILE}else{$HOME}
  if([string]::IsNullOrWhiteSpace($homeRoot)){throw "Unable to resolve user home directory."}
  $TradingRoot=Join-Path $homeRoot "Trading"
}
$ExpectedConfirm="RUN_V3_H1_H6_ASSOC_001"
$repo=Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$python=Join-Path $TradingRoot "Runtime\kraken-eur-scanner-venv\Scripts\python.exe"
$normalized=Join-Path $TradingRoot "Historical\normalized\kraken\eur\15m"
$catalog=Join-Path $TradingRoot "Historical\catalog\kraken-eur15-normalization.json"
$reports=Join-Path $TradingRoot "Historical\reports"
$ledger=Join-Path $TradingRoot "Historical\trials\trial-ledger.sqlite3"
$ledgerTool=Join-Path $repo "tools\historical-trial-ledger.py"
$h6tool=Join-Path $repo "tools\v3-h6-association-trial.py"
$h1tool=Join-Path $repo "tools\v3-h1-association-trial.py"
$h6spec=Join-Path $repo "research\v3\h6-price-volume-association-trial-v1.json"
$h1spec=Join-Path $repo "research\v3\h1-breadth-association-trial-v1.json"
$h6record=Join-Path $repo "research\v3\h6-association-trial-ledger-record-v1.json"
$h1record=Join-Path $repo "research\v3\h1-association-trial-ledger-record-v1.json"

$plan=[ordered]@{
  kind="V3_H1_H6_ASSOCIATION_PHYSICAL_GATE_V1"
  status=$(if($Execute){"READY_TO_EXECUTE"}else{"PLAN_ONLY"})
  trials=@("V3-H6-ASSOC-001","V3-H1-ASSOC-001")
  development_only=$true
  holdout_opened=$false
  threshold_search=$false
  winner_selection=$false
  network=$false
  orders=$false
  real_money_actions=$false
}
if(-not $Execute){$plan|ConvertTo-Json -Depth 6;exit 0}
if($Confirm -ne $ExpectedConfirm){throw "Execution blocked. Re-run with -Confirm $ExpectedConfirm"}
foreach($p in @($repo,$python,$normalized,$catalog,$ledgerTool,$h6tool,$h1tool,$h6spec,$h1spec,$h6record,$h1record)){
  if(-not(Test-Path -LiteralPath $p)){throw "Required path missing: $p"}
}
Push-Location $repo
try{
  $dirty=git status --porcelain
  if($LASTEXITCODE -ne 0 -or $dirty){throw "Repository must be clean before immutable association trials."}
  $head=(git rev-parse HEAD).Trim()
  New-Item -ItemType Directory -Force -Path $reports|Out-Null
  $stamp=Get-Date -Format "yyyyMMdd-HHmmss"

  function Register-Trial([string]$source,[string]$tmpName){
    $obj=Get-Content $source -Raw|ConvertFrom-Json
    $obj.code_fingerprint=$head
    $tmp=Join-Path $env:TEMP $tmpName
    $json=$obj|ConvertTo-Json -Depth 30
    $utf8NoBom=New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($tmp,$json,$utf8NoBom)
    & $python $ledgerTool --db $ledger append --record $tmp
    if($LASTEXITCODE -ne 0){throw "Immutable trial ledger append failed for "+$obj.trial_id}
  }

  Write-Host "=== V3 H6 ASSOCIATION 001 ==="
  Register-Trial $h6record "v3-h6-assoc-001-ledger.json"
  $h6out=Join-Path $reports ("v3-h6-association-001-"+$stamp+".json")
  & $python $h6tool $normalized --spec $h6spec --catalog $catalog --output $h6out
  if($LASTEXITCODE -ne 0){throw "H6 association trial failed"}
  $r6=Get-Content $h6out -Raw|ConvertFrom-Json
  if($r6.status -ne "PASS" -or $r6.guardrails.holdout_opened -ne $false -or $r6.interpretation.automatic_winner_selected -ne $false){throw "H6 association guard failed"}

  Write-Host "=== V3 H1 ASSOCIATION 001 ==="
  Register-Trial $h1record "v3-h1-assoc-001-ledger.json"
  $h1out=Join-Path $reports ("v3-h1-association-001-"+$stamp+".json")
  & $python $h1tool $normalized --spec $h1spec --catalog $catalog --output $h1out
  if($LASTEXITCODE -ne 0){throw "H1 association trial failed"}
  $r1=Get-Content $h1out -Raw|ConvertFrom-Json
  if($r1.status -ne "PASS" -or $r1.guardrails.holdout_opened -ne $false -or $r1.interpretation.automatic_winner_selected -ne $false){throw "H1 association guard failed"}

  & $python $ledgerTool --db $ledger verify
  if($LASTEXITCODE -ne 0){throw "Trial ledger verify failed"}
}finally{Pop-Location}

Write-Host ""
Write-Host "=== V3 H1/H6 ASSOCIATION GATE COMPLETE ==="
Write-Host ("H6 report: "+$h6out)
Write-Host ("H6 SHA: "+$r6.deterministic_summary_sha256)
Write-Host ("H1 report: "+$h1out)
Write-Host ("H1 SHA: "+$r1.deterministic_summary_sha256)
Write-Host "Holdout CLOSED / no threshold search / no winner / no network / no orders / no real-money action"
