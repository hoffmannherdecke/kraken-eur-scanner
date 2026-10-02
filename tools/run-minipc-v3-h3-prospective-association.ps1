param(
  [string]$TradingRoot = "",
  [switch]$Execute,
  [string]$Confirm = "",
  [int]$Seconds = 1800,
  [switch]$Evaluate
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

if([string]::IsNullOrWhiteSpace($TradingRoot)){
  $homeRoot=if($env:USERPROFILE){$env:USERPROFILE}else{$HOME}
  if([string]::IsNullOrWhiteSpace($homeRoot)){throw "Unable to resolve user home directory."}
  $TradingRoot=Join-Path $homeRoot "Trading"
}

$ExpectedConfirm="RUN_V3_H3_ASSOC_001"
$repo=Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$python=Join-Path $TradingRoot "Runtime\kraken-eur-scanner-venv\Scripts\python.exe"
$reports=Join-Path $TradingRoot "Historical\reports"
$trials=Join-Path $TradingRoot "Historical\trials"
$ledger=Join-Path $trials "trial-ledger.sqlite3"
$ledgerTool=Join-Path $repo "tools\historical-trial-ledger.py"
$runner=Join-Path $repo "tools\v3-h3-prospective-association.py"
$spec=Join-Path $repo "research\v3\h3-prospective-state-association-trial-v1.json"
$record=Join-Path $repo "research\v3\h3-association-trial-ledger-record-v1.json"
$freeze=Join-Path $trials "v3-h3-assoc-001-freeze.json"

$plan=[ordered]@{
  kind="V3_H3_PROSPECTIVE_ASSOCIATION_MINIPC_GATE_V1"
  status=$(if($Execute){"READY_TO_EXECUTE"}else{"PLAN_ONLY"})
  trial_id="V3-H3-ASSOC-001"
  mode=$(if($Evaluate){"EVALUATE"}else{"CAPTURE"})
  seconds=$Seconds
  symbols=@("BTC/EUR","ETH/EUR","SOL/EUR")
  sampling_seconds=5
  horizons_seconds=@(60,300,900)
  min_sessions=3
  min_distinct_utc_dates=2
  min_valid_feature_rows_per_symbol=1000
  public_endpoint_only=$true
  active_v2r3_changed=$false
  v2r4_changed=$false
  holdout_opened=$false
  orders=$false
  real_money_actions=$false
}
if(-not $Execute){$plan|ConvertTo-Json -Depth 6;exit 0}
if($Confirm -ne $ExpectedConfirm){throw "Execution blocked. Re-run with -Confirm $ExpectedConfirm"}
if(-not $Evaluate -and ($Seconds -lt 1800 -or $Seconds -gt 3600)){throw "Physical collection sessions must be 1800..3600 seconds."}

foreach($p in @($repo,$python,$ledgerTool,$runner,$spec,$record)){
  if(-not(Test-Path -LiteralPath $p)){throw "Required path missing: $p"}
}
New-Item -ItemType Directory -Force -Path $reports,$trials|Out-Null

Push-Location $repo
try{
  $dirty=git status --porcelain
  if($LASTEXITCODE -ne 0 -or $dirty){throw "Repository must be clean before V3-H3 immutable prospective capture."}
  $head=(git rev-parse HEAD).Trim()
  if([string]::IsNullOrWhiteSpace($head)){throw "Unable to resolve repository HEAD."}

  & $python $runner --self-test
  if($LASTEXITCODE -ne 0){throw "H3 association runner self-test failed"}

  $runnerSha=(Get-FileHash -Algorithm SHA256 -LiteralPath $runner).Hash.ToLowerInvariant()
  $specSha=(Get-FileHash -Algorithm SHA256 -LiteralPath $spec).Hash.ToLowerInvariant()

  if(Test-Path -LiteralPath $freeze){
    $f=Get-Content $freeze -Raw|ConvertFrom-Json
    if($f.trial_id -ne "V3-H3-ASSOC-001"){throw "Unexpected H3 freeze trial id"}
    if($f.runner_sha256 -ne $runnerSha){throw "H3 runner changed after first prospective session; new trial id required"}
    if($f.spec_sha256 -ne $specSha){throw "H3 spec changed after first prospective session; new trial id required"}
  } else {
    $f=[ordered]@{
      schema_version=1
      trial_id="V3-H3-ASSOC-001"
      frozen_at_utc=[DateTime]::UtcNow.ToString("o")
      first_execution_head=$head
      runner_sha256=$runnerSha
      spec_sha256=$specSha
      holdout_opened=$false
      orders=$false
      real_money_actions=$false
    }
    $utf8NoBom=New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($freeze,($f|ConvertTo-Json -Depth 8),$utf8NoBom)
  }

  $ledgerList=& $python $ledgerTool --db $ledger list
  if($LASTEXITCODE -ne 0){throw "Unable to inspect immutable trial ledger"}
  $prefix="HISTORICAL_TRIAL_LEDGER "
  $line=($ledgerList|Select-Object -Last 1)
  if(-not $line.StartsWith($prefix)){throw "Unexpected trial ledger output"}
  $ledgerObj=$line.Substring($prefix.Length)|ConvertFrom-Json
  $registered=@($ledgerObj.trials|Where-Object {$_.trial_id -eq "V3-H3-ASSOC-001"}).Count -gt 0
  if(-not $registered){
    $obj=Get-Content $record -Raw|ConvertFrom-Json
    $obj.code_fingerprint=$head
    $tmp=Join-Path $env:TEMP "v3-h3-assoc-001-ledger.json"
    $utf8NoBom=New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($tmp,($obj|ConvertTo-Json -Depth 30),$utf8NoBom)
    & $python $ledgerTool --db $ledger append --record $tmp
    if($LASTEXITCODE -ne 0){throw "Immutable trial ledger append failed for V3-H3-ASSOC-001"}
  }

  & $python $ledgerTool --db $ledger verify
  if($LASTEXITCODE -ne 0){throw "Trial ledger verify failed"}

  if($Evaluate){
    $inputs=@(Get-ChildItem -LiteralPath $reports -Filter "v3-h3-assoc-001-session-*.json"|Sort-Object Name|ForEach-Object {$_.FullName})
    if($inputs.Count -lt 1){throw "No H3 session reports found"}
    $stamp=Get-Date -Format "yyyyMMdd-HHmmss"
    $out=Join-Path $reports ("v3-h3-association-001-"+$stamp+".json")
    $args=@($runner,"--spec",$spec,"evaluate")+@($inputs)+@("--output",$out)
    & $python @args
    if($LASTEXITCODE -ne 0){throw "H3 association evaluation failed"}
    $r=Get-Content $out -Raw|ConvertFrom-Json
    Write-Host ""
    Write-Host "=== V3 H3 ASSOCIATION EVALUATION COMPLETE ==="
    Write-Host ("Status: "+$r.status)
    Write-Host ("Report: "+$out)
    Write-Host ("SHA256: "+(Get-FileHash -Algorithm SHA256 -LiteralPath $out).Hash.ToLowerInvariant())
  } else {
    $stamp=Get-Date -Format "yyyyMMdd-HHmmss"
    $sid="V3-H3-ASSOC-001-"+([DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ"))
    $out=Join-Path $reports ("v3-h3-assoc-001-session-"+$stamp+".json")
    & $python $runner --spec $spec capture --seconds $Seconds --session-id $sid --output $out
    if($LASTEXITCODE -ne 0){throw "H3 prospective capture failed"}
    $r=Get-Content $out -Raw|ConvertFrom-Json
    if($r.status -ne "PASS" -or $r.guardrails.holdout_opened -ne $false -or $r.guardrails.orders -ne $false){throw "H3 capture guard failed"}
    Write-Host ""
    Write-Host "=== V3 H3 PROSPECTIVE SESSION COMPLETE ==="
    Write-Host ("Session: "+$r.session_id)
    Write-Host ("Counts: BTC="+$r.counts.'BTC/EUR'+" ETH="+$r.counts.'ETH/EUR'+" SOL="+$r.counts.'SOL/EUR')
    Write-Host ("Report: "+$out)
    Write-Host ("SHA256: "+(Get-FileHash -Algorithm SHA256 -LiteralPath $out).Hash.ToLowerInvariant())
    Write-Host "Need >=3 x >=1800s sessions across >=2 UTC dates and >=1000 valid feature rows/symbol before effect-size review."
  }
} finally {
  Pop-Location
}
