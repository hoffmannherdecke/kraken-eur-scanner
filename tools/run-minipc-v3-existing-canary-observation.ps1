param(
 [string]$TradingRoot=(Join-Path $env:USERPROFILE 'Trading'),
 [switch]$Execute,
 [int]$MaxCandidates=2
)
# One prospective source-only Paper CANARY observation: consumes NO API budget.
# Designed for later reuse by the existing single Mini-PC owner. No task is
# created/registered by this tool. V2R4 runtime source is READ ONLY.
$ErrorActionPreference='Stop'
if($MaxCandidates -lt 1 -or $MaxCandidates -gt 5){throw 'Max 1..5 existing cases per invocation'}
$repo=Join-Path $TradingRoot 'Repos\kraken-eur-scanner'
$venv=Join-Path $TradingRoot 'Runtime\kraken-eur-scanner-venv\Scripts\python.exe'
$root=Join-Path $TradingRoot 'Research\V3Paper'
$journal=Join-Path $root 'journal'
$capture=Join-Path $root 'capture'
$series='PAPER-V3-CANARY-20261011'
$old='PAPER-V2R4-20261009T110135Z'
if(-not $Execute){
 [pscustomobject]@{status='PLAN_ONLY_NO_NETWORK_OR_WRITE'
   select_max=$MaxCandidates;no_model=$true;no_orders=$true;v2r4_untouched=$true
 } | ConvertTo-Json
 exit 0
}
foreach($file in @($venv,$repo,$journal,$capture)){
 if(!(Test-Path -LiteralPath $file)){throw "Existing verified V3 path missing: $file"}
}
$oldApps=@(Get-ChildItem (Join-Path $TradingRoot 'Runtime') -Directory |
 Where-Object {Test-Path (Join-Path $_.FullName 'paper_runtime_control.json')} |
 Where-Object {
  try{
   (Get-Content (Join-Path $_.FullName 'paper_runtime_control.json') -Raw |
    ConvertFrom-Json).series_id -eq $old
  }catch{$false}
 })
if($oldApps.Count -ne 1){throw 'Exactly one old frozen Paper runtime source required'}
$queue=Join-Path $oldApps[0].FullName 'handoff_queue'
if(!(Test-Path $queue)){throw 'Old original candidate handoff archive missing'}
# The V3 journal, not the V2R4 scanner stream, is the sole followup registry.
$orig=@{}
foreach($f in @(Get-ChildItem $journal -File -Filter '*.json')){
 try{
  $r=Get-Content $f.FullName -Raw | ConvertFrom-Json
  if($r.series_id -eq $series -and $r.phase -eq 'SCANNER_CAPTURE' -and
     $r.candidate_id -and $r.pair -and $r.event_time_utc){
   $orig[[string]$r.candidate_id]=$r
  }
 }catch{throw 'Immutable original V3 journal corrupt: no retrospective recovery'}
}
if($orig.Count -eq 0){
 Write-Host 'NO_ORIGINAL_V3_CANARY_CANDIDATE_IN_JOURNAL'
 exit 0
}
$targets=New-Object System.Collections.ArrayList
foreach($file in @(Get-ChildItem $queue -File -Filter '*.json' |
                    Sort-Object LastWriteTimeUtc -Descending)){
 try{
  $c=Get-Content $file.FullName -Raw | ConvertFrom-Json
  $cid=[string]$c.candidate_id
  if($orig.ContainsKey($cid) -and
     $c.pair -eq $orig[$cid].pair -and
     $c.event_time_utc -eq $orig[$cid].event_time_utc -and
     $c.pair.EndsWith('/EUR') -and
     $c.altname -match '^[A-Za-z0-9]+$'){
   [void]$targets.Add($file.FullName)
   $orig.Remove($cid)
   if($targets.Count -ge $MaxCandidates){break}
  }
 }catch{}
}
if($targets.Count -eq 0){
 Write-Host 'NO_EXACT_ORIGINAL_HANDOFF_FOR_KNOWN_V3_CANARY_FOLLOWUPS'
 Write-Host 'No fake retrospective WAIT or Paper result was produced.'
 exit 0
}
Push-Location $repo
try{
 foreach($candidatePath in $targets){
  Write-Host '[V3] Selective prospective public Kraken WAIT/6h24h source observation'
  $argsV3=@('-m','paper_evaluator.v3_paper_minipc_selective_tick_v1',
     '--original-candidate-file',$candidatePath,'--series',$series,
     '--journal',$journal,'--capture-dir',$capture,
     '--execute-public-kraken-tick')
  & $venv @argsV3
  if($LASTEXITCODE -ne 0){throw 'V3 Paper observational tick failed; do not claim success'}
 }
 $token=Join-Path $TradingRoot 'Secrets\v3-paper-relay-token.txt'
 if(!(Test-Path -LiteralPath $token -PathType Leaf)){
  throw 'V3 cloud token unavailable; local receipts kept and remain unsynced'
 }
 $syncArgs=@('-m','paper_evaluator.v3_paper_cloud_receipt_sync_v1',
  '--journal',$journal,'--series',$series,
  '--ack-file',(Join-Path $root 'cloud-ack.json'),
  '--relay-secret-file',$token,'--execute-cloud-sync')
 & $venv @syncArgs
 if($LASTEXITCODE -ne 0){throw 'Cloud receipt ACK failed, local immutable originals retained'}
}finally{Pop-Location}
Write-Host 'V3 Paper observation cycle finished; NO MODEL, NO PAPER ACTIVATION, V2R4 unchanged.'
