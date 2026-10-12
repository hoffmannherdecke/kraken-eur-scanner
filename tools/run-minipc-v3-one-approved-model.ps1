param(
 [string]$TradingRoot=(Join-Path $env:USERPROFILE 'Trading'),
 [switch]$Execute
)
# One user-approved V3-PAPER HTTP attempt max. No scheduler or real orders.
$ErrorActionPreference='Stop'
$repo=Join-Path $TradingRoot 'Repos\kraken-eur-scanner'
$venv=Join-Path $TradingRoot 'Runtime\kraken-eur-scanner-venv\Scripts\python.exe'
$ps=Join-Path $repo 'tools\run-minipc-v3-paper-stage.ps1'
$approval=Join-Path $repo 'research\v3\v3-paper-approved-one-model-http-20261012.json'
$secret=Join-Path $TradingRoot 'Secrets\openai-api-key.txt'
$relay=Join-Path $TradingRoot 'Secrets\v3-paper-relay-token.txt'
$root=Join-Path $TradingRoot 'Research\V3Paper'
if(-not $Execute){
 [pscustomobject]@{
  status='PLAN_ONLY_NO_API';one_http_attempt=1
  estimated_usd_ceiling=0.15;v2r4_unchanged=$true;orders=$false
 } | ConvertTo-Json
 exit 0
}
foreach($f in @($venv,$ps,$approval,$relay)){
 if(!(Test-Path -LiteralPath $f -PathType Leaf)){
  throw "Required preflight file unavailable: $f"
 }
}
if(!(Test-Path -LiteralPath $secret -PathType Leaf)){
 throw 'OPENAI_API_KEY_FILE_MISSING; no HTTP request made'
}
$body=Get-Content -LiteralPath $approval -Raw | ConvertFrom-Json
if($body.max_model_http_attempts_including_retries -ne 1 -or
   $body.max_candidates -ne 1 -or $body.model -ne 'gpt-5.6-terra' -or
   $body.estimated_usd_ceiling -ne 0.15){
 throw 'Immutable one-shot approval contract mismatch'
}
Write-Host 'V3 One-shot: select next unjournaled fresh V2R4 handoff read-only.'
Write-Host 'Up to 1 model HTTP request, no retry; no Paper/real order.'
$stageError=$null
try{
 & $ps -TradingRoot $TradingRoot -OneApprovedModelCall -ApprovalJson $approval
 if(!$?){throw 'V3 stage failed'}
}catch{
 $stageError=$_
 Write-Host 'V3 model stage stopped; one-shot budget may be consumed.'
}finally{
 if(Test-Path -LiteralPath $venv -PathType Leaf){
  Push-Location $repo
  try{
   $argsV3=@('-m','paper_evaluator.v3_paper_cloud_receipt_sync_v1',
       '--journal',(Join-Path $root 'journal'),
       '--series','PAPER-V3-CANARY-20261011',
       '--ack-file',(Join-Path $root 'cloud-ack.json'),
       '--relay-secret-file',$relay,'--execute-cloud-sync')
   & $venv @argsV3
   if($LASTEXITCODE -ne 0){Write-Warning 'Cloud ACK not yet verified; local original receipts retained'}
  }finally{Pop-Location}
 }
}
if($stageError){throw $stageError}
Write-Host 'V3 one-shot canary ended. V2R4 active, V3 Paper NOT activated.'
