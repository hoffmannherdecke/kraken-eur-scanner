param(
 [string]$TradingRoot=(Join-Path $env:USERPROFILE 'Trading'),
 [switch]$PrepareOnly,
 [switch]$RealKrakenCanary,
 [switch]$OneApprovedModelCall,
 [string]$ApprovalJson=''
)
$ErrorActionPreference='Stop'
$modeCount=0
if($PrepareOnly){$modeCount++}
if($RealKrakenCanary){$modeCount++}
if($OneApprovedModelCall){$modeCount++}
if($modeCount -gt 1){throw 'Only one mode per invocation'}
$repo=Join-Path $TradingRoot 'Repos\kraken-eur-scanner'
$venv=Join-Path $TradingRoot 'Runtime\kraken-eur-scanner-venv\Scripts\python.exe'
$root=Join-Path $TradingRoot 'Research\V3Paper'
$series='PAPER-V3-CANARY-20261011'
$old='PAPER-V2R4-20261009T110135Z'
if (-not (Test-Path $repo) -or -not (Test-Path $venv)) {
 throw 'Verified repository or existing Python environment unavailable'
}
$oldApps=@(Get-ChildItem (Join-Path $TradingRoot 'Runtime') -Directory -ErrorAction Stop |
 Where-Object { Test-Path (Join-Path $_.FullName 'paper_runtime_control.json') } |
 Where-Object {
  try{
   (Get-Content (Join-Path $_.FullName 'paper_runtime_control.json') -Raw |
     ConvertFrom-Json).series_id -eq $old
  }catch{$false}
 })
if($oldApps.Count -ne 1) {
 throw "Expected EXACTLY one frozen V2R4 input runtime $old; found $($oldApps.Count)"
}
$control=Get-Content (Join-Path $oldApps[0].FullName 'paper_runtime_control.json') -Raw | ConvertFrom-Json
if($control.paper_only -eq $false -or $control.real_money_actions_enabled -ne $false) {
 throw 'Unsafe legacy Paper control'
}
$payload=[ordered]@{
 kind='V3_MINIPC_REAL_PAPER_STAGE_PRECHECK_V1'
 at_utc=(Get-Date).ToUniversalTime().ToString('o')
 active_old_series_expected=$old
 source_app=$oldApps[0].FullName
 v3_series=$series
 real_model_calls_authorized=$false
 v3_paper_active=$false
 no_real_money=$true
 no_v2r4_changes=$true
}
if(-not ($PrepareOnly -or $RealKrakenCanary -or $OneApprovedModelCall)) {
 $payload.status='PLAN_ONLY_NO_NETWORK_NO_WRITE'
 $payload | ConvertTo-Json -Depth 8
 exit 0
}
New-Item -ItemType Directory -Force -Path $root,(Join-Path $root 'journal'),(Join-Path $root 'budgets'),(Join-Path $root 'capture') | Out-Null
if($PrepareOnly) {
 $payload.status='SEPARATE_V3_STAGE_DIRECTORIES_READY_NO_NETWORK_NO_MODEL'
 $payload | ConvertTo-Json -Depth 8
 exit 0
}
# This reads but NEVER consumes/changes the existing V2R4 handoff queue.
$queue=Join-Path $oldApps[0].FullName 'handoff_queue'
if(-not (Test-Path $queue)){throw 'Original handoff queue does not exist'}
$recent=@(Get-ChildItem $queue -Filter '*.json' -File |
 Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 40)
# A prior source-only canary permanently journals its original identity.
# Never silently reuse that candidate for an expensive model attempt.
$seenCandidates=@{}
foreach($receiptFile in @(Get-ChildItem (Join-Path $root 'journal') -Filter '*.json' -File)){
 try{
  $receipt=Get-Content $receiptFile.FullName -Raw | ConvertFrom-Json
  if($receipt.series_id -eq $series -and $receipt.candidate_id){
   $seenCandidates[[string]$receipt.candidate_id]=$true
  }
 }catch{ throw 'Corrupt immutable V3 candidate journal: fail closed before API' }
}
$candidate=$null
foreach($file in $recent){
 try{
  $c=Get-Content $file.FullName -Raw | ConvertFrom-Json
  $age=((Get-Date).ToUniversalTime()-([datetime]$c.event_time_utc).ToUniversalTime()).TotalSeconds
  if($c.kind -eq 'CANONICAL_CANDIDATE_HANDOFF_V1' -and
     $age -ge 0 -and $age -le 600 -and $c.pair.EndsWith('/EUR') -and
     $c.candidate_id -and (-not $seenCandidates.ContainsKey([string]$c.candidate_id))){
   $candidate=$file;break
  }
 }catch{}
}
if($null -eq $candidate){
 $payload.status='NO_FRESH_10M_CANONICAL_HANDOFF_WAIT_FOR_REAL_NEXT_EVENT'
 $payload | ConvertTo-Json -Depth 8
 exit 0
}
# Attach only real, original-source H10 evidence for this exact candidate.
# Never create a second H10 scanner/schedule. A source failure cannot veto
# the pre-existing technical model route.
$ctxDir=Join-Path $root 'context'
New-Item -ItemType Directory -Force -Path $ctxDir | Out-Null
$sourceFile=Join-Path $ctxDir 'latest-verified-sources.json'
$relaySecret=Join-Path $TradingRoot 'Secrets\v3-paper-relay-token.txt'
if(Test-Path -LiteralPath $relaySecret -PathType Leaf){
 try{
  Push-Location $repo
  try{
   $sourceArgs=@('-m','paper_evaluator.v3_paper_h10_context_read_v1',
    '--pair',[string]$c.pair,
    '--relay-secret-file',$relaySecret,
    '--output-context',$sourceFile,
    '--execute-live-read')
   & $venv @sourceArgs
   if($LASTEXITCODE -ne 0){Write-Warning 'H10 Cloud source read unavailable; optional only'}
  }finally{Pop-Location}
 }catch{Write-Warning 'Optional H10 source unavailable; technical V3 path remains'}
}
Push-Location $repo
try{
 $arg=@('-m','paper_evaluator.v3_paper_minipc_one_candidate_v1',
  '--candidate',$candidate.FullName,'--series',$series,
  '--journal',(Join-Path $root 'journal'),
  '--budget-directory',(Join-Path $root 'budgets'))
 if($OneApprovedModelCall){
  if(-not $ApprovalJson -or -not (Test-Path $ApprovalJson)){
   throw 'New exact one-call user-approved budget JSON required; prior PR186 authority expired'
  }
  $secret=Join-Path $TradingRoot 'Secrets\openai-api-key.txt'
  if(-not (Test-Path $secret)){throw 'Existing OpenAI secret unavailable'}
  $arg+=@('--approved-one-model-call',$ApprovalJson,
          '--model-key-file',$secret)
 }
 # Optional PIT source dossier is read-only and never required.
 # The source bridge itself rechecks observed_at <= known_at <= decision.

 if(Test-Path -LiteralPath $sourceFile -PathType Leaf){
  $arg+=@('--optional-sources',$sourceFile)
 }
 & $venv @arg
 if($LASTEXITCODE -ne 0){throw 'V3 canary returned failure'}
}finally{Pop-Location}
$payload.status=if($OneApprovedModelCall){'MODEL_CANARY_OUTPUT_ABOVE_NOT_AN_ACTIVE_PAPER_SERIES'}else{'REAL_KRAKEN_SOURCE_PREFLIGHT_OUTPUT_ABOVE_NO_MODEL'}
$payload | ConvertTo-Json -Depth 8
