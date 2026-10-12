param(
 [string]$TradingRoot=(Join-Path $env:USERPROFILE 'Trading'),
 [Parameter(Mandatory=$true)][string]$UntilUtc
)
# ONLY used by a separately approved 28h local Windows Task.
# No V2R4 modifications, no model/paid HTTP, no trading/activation.
$ErrorActionPreference='Stop'
$stateDir=Join-Path $TradingRoot 'State'
$logs=Join-Path $TradingRoot 'Logs'
$repo=Join-Path $TradingRoot 'Repos\kraken-eur-scanner'
$planPath=Join-Path $stateDir 'v3-canary-observer-28h-plan.json'
$statePath=Join-Path $stateDir 'v3-canary-observer-28h-heartbeat.json'
$logPath=Join-Path $logs 'v3-canary-observer-28h.log'
$scriptPath=Join-Path $repo 'tools\run-minipc-v3-existing-canary-observation.ps1'
$mutex=[System.Threading.Mutex]::new($false,'Global\CryptoMiniPC_V3Canary28hOnce')
$acquired=$false
try{
 try{$acquired=$mutex.WaitOne(0)}catch [System.Threading.AbandonedMutexException]{$acquired=$true}
 if(-not $acquired){Write-Output 'V3_OBSERVER_DUPLICATE_SKIPPED';exit 0}
 if(-not (Test-Path -LiteralPath $planPath -PathType Leaf)){throw 'No local V3-only timed task manifest'}
 $plan=Get-Content -LiteralPath $planPath -Raw|ConvertFrom-Json
 $now=(Get-Date).ToUniversalTime()
 $expires=[datetime]::Parse($UntilUtc).ToUniversalTime()
 if($plan.kind -ne 'V3_LOCAL_READONLY_CANARY_28H_PLAN_V1' -or
    $plan.paper_only -ne $true -or $plan.orders -ne $false -or
    $plan.model_http_calls_authorized -ne 0 -or
    $plan.v2r4_unchanged -ne $true -or
    $plan.until_utc -ne $UntilUtc -or
    $expires -le $now -or
    ($expires-$now).TotalHours -gt 30){
  Write-Output 'V3_OBSERVER_EXPIRED_OR_MANIFEST_INVALID_NO_KRAKEN_IO'
  exit 0
 }
 foreach($entry in @($plan.pinned_file_hashes)){
  if([string]::IsNullOrWhiteSpace($entry.relative_path) -or
     $entry.relative_path -match '(^[\\/]|\.{2}|:)'){
   throw 'Malformed pinned V3-only file identity'
  }
  $file=Join-Path $repo $entry.relative_path
  if(!(Test-Path -LiteralPath $file -PathType Leaf)){throw 'V3 source changed or missing; fail closed'}
  $hash=(Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
  if($hash -cne $entry.sha256){throw 'V3 observed code differs from install-time pinned hash'}
 }
 if(!(Test-Path -LiteralPath $scriptPath -PathType Leaf)){throw 'V3 execution source missing'}
 $status='UNKNOWN'
 $details=''
 try{
  $result=@(& $scriptPath -TradingRoot $TradingRoot -Execute -MaxCandidates 2 2>&1)
  $details=($result|Out-String).Trim()
  if($details -match 'NO_EXACT_ORIGINAL_HANDOFF|NO_ORIGINAL_V3_CANARY_CANDIDATE'){
   $status='NO_VERIFIED_ORIGINALS'
  }elseif($details -match 'V3 Paper observation cycle finished; NO MODEL, NO PAPER ACTIVATION, V2R4 unchanged'){
   $status='HEALTHY'
  }else{
   throw 'No complete cloud ACK / observer completion marker'
  }
 }catch{
  $status='ERROR'
  $details=("EXCEPTION: "+$_.Exception.Message+[Environment]::NewLine+$details)
 }
 $heartbeat=[ordered]@{
  kind='V3_LOCAL_READONLY_CANARY_OBSERVER_HEARTBEAT_V1'
  checked_at_utc=(Get-Date).ToUniversalTime().ToString('o')
  status=$status;expires_at_utc=$UntilUtc
  no_real_money=$true;model_http_calls=0
  paper_activated=$false;v2r4_unchanged=$true
  source=(Split-Path $scriptPath -Leaf)
  last_run_detail=($details|Select-Object -First 1)
 }
 if(!(Test-Path -LiteralPath $stateDir -PathType Container) -or
    !(Test-Path -LiteralPath $logs -PathType Container)){
   throw 'Preexisting state/log root required'
 }
 $tmp=$statePath+'.'+([guid]::NewGuid().ToString('N'))+'.tmp'
 try{
  [System.IO.File]::WriteAllText($tmp,($heartbeat|ConvertTo-Json -Depth 7),
    [System.Text.UTF8Encoding]::new($false))
  Move-Item -LiteralPath $tmp -Destination $statePath -Force
 }finally{Remove-Item -LiteralPath $tmp -ErrorAction SilentlyContinue}
 Add-Content -LiteralPath $logPath -Value ('['+$heartbeat.checked_at_utc+'] '+$status+' '+($details -replace "\r?\n",' ')) -Encoding UTF8
 $heartbeat|Select-Object kind,status,checked_at_utc,expires_at_utc,no_real_money,model_http_calls,paper_activated|ConvertTo-Json
 if($status -eq 'ERROR'){exit 1}
}finally{
 if($acquired){$mutex.ReleaseMutex()}
 $mutex.Dispose()
}
