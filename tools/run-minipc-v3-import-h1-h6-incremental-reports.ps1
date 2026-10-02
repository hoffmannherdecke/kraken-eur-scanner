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

$ExpectedConfirm="IMPORT_V3_H1_H6_INCR_REPORTS"
$repo=Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$python=Join-Path $TradingRoot "Runtime\kraken-eur-scanner-venv\Scripts\python.exe"
$reports=Join-Path $TradingRoot "Historical\reports"
$h1=Join-Path $reports "v3-h1-incremental-001-20261002-095841.json"
$h6=Join-Path $reports "v3-h6-incremental-001-20261002-095841.json"
$dest=Join-Path $repo "research\v3\incremental-reports"

$plan=[ordered]@{
  kind="V3_H1_H6_INCREMENTAL_REPORT_IMPORT_V1"
  status=$(if($Execute){"READY_TO_EXECUTE"}else{"PLAN_ONLY"})
  source_reports=@($h1,$h6)
  destination=$dest
  exact_payload_copy=$true
  report_mutation=$false
  holdout_opened=$false
  strategy_change=$false
  orders=$false
  real_money_actions=$false
}
if(-not $Execute){$plan|ConvertTo-Json -Depth 6;exit 0}
if($Confirm -ne $ExpectedConfirm){throw "Execution blocked. Re-run with -Confirm $ExpectedConfirm"}

foreach($p in @($repo,$python,$h1,$h6)){
  if(-not(Test-Path -LiteralPath $p)){throw "Required path missing: $p"}
}

Push-Location $repo
try{
  git pull --ff-only
  if($LASTEXITCODE -ne 0){throw "git pull --ff-only failed"}
  $dirty=git status --porcelain
  if($LASTEXITCODE -ne 0 -or $dirty){throw "Repository must be clean before importing immutable reports."}

  New-Item -ItemType Directory -Force -Path $dest|Out-Null

  $validator=@'
import hashlib,json,sys
from pathlib import Path

expected={
 "V3-H1-INCR-001":"V3_H1_INCREMENTAL_RELATIVE_CONTEXT_RESULT_V1",
 "V3-H6-INCR-001":"V3_H6_INCREMENTAL_VOLUME_CONTRIBUTION_RESULT_V1",
}
for name in sys.argv[1:]:
    p=Path(name)
    x=json.loads(p.read_text("utf-8"))
    tid=x.get("trial_id")
    if tid not in expected: raise SystemExit(f"unexpected trial_id {tid!r} in {p}")
    if x.get("kind")!=expected[tid]: raise SystemExit(f"unexpected kind in {p}")
    if x.get("status")!="PASS": raise SystemExit(f"status not PASS in {p}")
    g=x.get("guardrails") or {}
    i=x.get("interpretation") or {}
    if g.get("holdout_opened") is not False: raise SystemExit(f"holdout guard failed in {p}")
    if g.get("orders") is not False or g.get("real_money_actions") is not False: raise SystemExit(f"action guard failed in {p}")
    if i.get("automatic_winner_selected") is not False: raise SystemExit(f"winner guard failed in {p}")
    claimed=x.get("deterministic_summary_sha256")
    if not isinstance(claimed,str) or len(claimed)!=64: raise SystemExit(f"missing deterministic summary hash in {p}")
    y=dict(x);y.pop("deterministic_summary_sha256",None)
    raw=json.dumps(y,sort_keys=True,separators=(",",":"))
    actual=hashlib.sha256(raw.encode()).hexdigest()
    if actual!=claimed: raise SystemExit(f"deterministic summary hash mismatch in {p}: {actual} != {claimed}")
    file_sha=hashlib.sha256(p.read_bytes()).hexdigest()
    print(json.dumps({"trial_id":tid,"file":p.name,"status":"PASS","deterministic_summary_sha256":claimed,"file_sha256":file_sha},sort_keys=True))
'@
  $tmp=Join-Path $env:TEMP "validate-v3-h1-h6-incr-import.py"
  [System.IO.File]::WriteAllText($tmp,$validator,(New-Object System.Text.UTF8Encoding($false)))

  $validation=& $python $tmp $h1 $h6
  if($LASTEXITCODE -ne 0){throw "Incremental report validation failed"}

  Copy-Item -LiteralPath $h1 -Destination (Join-Path $dest (Split-Path $h1 -Leaf)) -Force
  Copy-Item -LiteralPath $h6 -Destination (Join-Path $dest (Split-Path $h6 -Leaf)) -Force

  $manifest=[ordered]@{
    schema_version=1
    kind="V3_H1_H6_INCREMENTAL_REPORT_IMPORT_MANIFEST_V1"
    imported_at_utc=[DateTime]::UtcNow.ToString("o")
    source_platform="MINI_PC"
    exact_payload_copy=$true
    reports=@()
    guardrails=[ordered]@{
      holdout_opened=$false
      strategy_change=$false
      orders=$false
      real_money_actions=$false
    }
  }
  foreach($line in $validation){
    $r=$line|ConvertFrom-Json
    $manifest.reports += $r
  }
  $manifestPath=Join-Path $dest "v3-h1-h6-incremental-import-manifest-20261002.json"
  [System.IO.File]::WriteAllText($manifestPath,($manifest|ConvertTo-Json -Depth 10),(New-Object System.Text.UTF8Encoding($false)))

  git add -- "research/v3/incremental-reports/"
  if($LASTEXITCODE -ne 0){throw "git add failed"}
  $staged=git diff --cached --name-only
  $allowed=@(
    "research/v3/incremental-reports/v3-h1-incremental-001-20261002-095841.json",
    "research/v3/incremental-reports/v3-h6-incremental-001-20261002-095841.json",
    "research/v3/incremental-reports/v3-h1-h6-incremental-import-manifest-20261002.json"
  )
  foreach($p in $staged){ if($allowed -notcontains $p){ throw "Unexpected staged path: $p" } }
  if(@($staged).Count -ne 3){throw "Expected exactly 3 staged files; got "+@($staged).Count}

  git commit -m "v3: import exact H1 H6 incremental report payloads"
  if($LASTEXITCODE -ne 0){throw "git commit failed"}
  git push origin main
  if($LASTEXITCODE -ne 0){throw "git push failed"}

  Write-Host ""
  Write-Host "=== V3 H1/H6 REPORT IMPORT COMPLETE ==="
  foreach($line in $validation){Write-Host $line}
  Write-Host ("Manifest: "+$manifestPath)
  Write-Host "Exact payloads imported; no holdout, strategy, order or real-money action."
} finally {
  Pop-Location
}
