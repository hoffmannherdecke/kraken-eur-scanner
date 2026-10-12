param(
 [string]$TradingRoot=(Join-Path $env:USERPROFILE 'Trading'),
 [switch]$Execute
)
# Narrow repair for ONE installed 28h V3-only observation task.
# Does NOT reinstall/extend the task, enable orders, consume AI or change V2R4.
$ErrorActionPreference='Stop'
$taskName='CryptoMiniPC-V3CanaryObservation28h'
$repo=Join-Path $TradingRoot 'Repos\kraken-eur-scanner'
$stateDir=Join-Path $TradingRoot 'State'
$manifestPath=Join-Path $stateDir 'v3-canary-observer-28h-plan.json'
$heartbeatPath=Join-Path $stateDir 'v3-canary-observer-28h-heartbeat.json'
$backupPath=Join-Path $stateDir 'v3-canary-observer-28h-plan.pre-health-repair.json'
$receiptPath=Join-Path $stateDir 'v3-canary-observer-28h-health-repair-receipt.json'
$targetRelative='tools\minipc-v3-bounded-canary-observer-task.ps1'
$target=Join-Path $repo $targetRelative
if(-not $Execute){
 [pscustomobject]@{status='PLAN_ONLY_NO_TASK_OR_MANIFEST_CHANGE'
    operation='REPINS_ONLY_KNOWN_V3_OBSERVER_HEALTH_SCRIPT'
    same_expiration=$true;no_new_task=$true
    model_calls=0;orders=$false;v2r4_unchanged=$true
 }|ConvertTo-Json
 exit 0
}
$id=[Security.Principal.WindowsIdentity]::GetCurrent()
$pr=[Security.Principal.WindowsPrincipal]::new($id)
if(-not $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){
 throw 'Administrator PowerShell required to verify existing SYSTEM task'
}
foreach($p in @($repo,$stateDir,$manifestPath,$heartbeatPath,$target)){
 if(!(Test-Path -LiteralPath $p)){throw "Required old V3-only artifact missing: $p"}
}
$task=Get-ScheduledTask -TaskName $taskName -ErrorAction Stop
if(-not $task -or @($task.Actions).Count -ne 1 -or
   [string]$task.Actions[0].Execute -notmatch 'powershell' -or
   [string]$task.Actions[0].Arguments -notlike '*minipc-v3-bounded-canary-observer-task.ps1*' -or
   ([string]$task.Principal.UserId -notin @('SYSTEM','S-1-5-18'))){
 throw 'Existing original isolated V3 SYSTEM task identity mismatch'
}
$branch=(& git -C $repo branch --show-current).Trim()
$head=(& git -C $repo rev-parse HEAD).Trim()
$remote=(& git -C $repo rev-parse origin/main).Trim()
$dirty=@(& git -C $repo status --porcelain)
if($LASTEXITCODE -ne 0 -or $branch -ne 'main' -or $head -ne $remote -or $dirty.Count -gt 0){
 throw 'Require clean fast-forwarded GitHub main; no risky V3 code repin'
}
$heartbeat=Get-Content -LiteralPath $heartbeatPath -Raw|ConvertFrom-Json
if($heartbeat.kind -ne 'V3_LOCAL_READONLY_CANARY_OBSERVER_HEARTBEAT_V1' -or
   $heartbeat.status -ne 'ERROR' -or
   [string]$heartbeat.last_run_detail -notmatch 'No complete cloud ACK / observer completion marker' -or
   [string]$heartbeat.last_run_detail -notmatch 'NO_UNSYNCED_V3_RECEIPTS'){
 throw 'Different failure: do not repin arbitrary task or call a recovery restart'
}
$oldBytes=[System.IO.File]::ReadAllBytes($manifestPath)
$manifest=[System.Text.Encoding]::UTF8.GetString($oldBytes)|ConvertFrom-Json
$now=(Get-Date).ToUniversalTime()
$expires=[datetime]::Parse([string]$manifest.until_utc).ToUniversalTime()
$created=[datetime]::Parse([string]$manifest.created_at_utc).ToUniversalTime()
if($manifest.kind -ne 'V3_LOCAL_READONLY_CANARY_28H_PLAN_V1' -or
   $manifest.task_name -ne $taskName -or
   $manifest.paper_only -ne $true -or $manifest.orders -ne $false -or
   $manifest.v2r4_unchanged -ne $true -or
   $manifest.model_http_calls_authorized -ne 0 -or
   $manifest.max_original_canary_candidates -ne 2 -or
   $manifest.repetition_minutes -ne 5 -or
   $manifest.human_confirmation -ne 'RUN_V3_CANARY_READONLY_28H' -or
   ($expires-$created).TotalHours -gt 29 -or
   $expires -le $now){
 throw 'Original V3-only 28h plan expired or invalid; no duration extension'
}
if([string]$task.Actions[0].Arguments -notlike ('*'+[string]$manifest.until_utc+'*')){
 throw 'Existing SYSTEM task deadline differs from immutable original plan'
}
$entries=@($manifest.pinned_file_hashes)
if($entries.Count -ne 9){throw 'Unexpected V3 protected source set'}
$targets=@($entries|Where-Object{$_.relative_path -eq $targetRelative})
if($targets.Count -ne 1){throw 'Exactly one pinned V3 observer runner required'}
foreach($item in $entries){
 $relative=[string]$item.relative_path
 if($relative -match '(^[\\/]|\.{2}|:)' -or $item.sha256 -notmatch '^[0-9a-f]{64}$'){
  throw 'Invalid hash-protected V3 program identity'
 }
 $path=Join-Path $repo $relative
 if(!(Test-Path -LiteralPath $path -PathType Leaf)){throw 'Previously protected program missing'}
 if($relative -ne $targetRelative){
  $got=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
  if($got -cne $item.sha256){throw 'Another protected program changed: NO AUTOMATIC REPIN'}
 }
}
$contents=[System.IO.File]::ReadAllText($target)
if(-not ($contents.Contains('HEALTHY_NO_NEW_CLOUD_EVENTS') -and
         $contents.Contains('V3_RECEIPTS_CLOUD_ACK_VERIFIED') -and
         $contents.Contains('V3_PAPER_EXISTING_SUPERVISOR_SELECTIVE_TICK_V1') -and
         $contents.Contains('$plan.model_http_calls_authorized -ne 0'))){
 throw 'Expected new V3-only fix absent; cannot repin'
}
$newHash=(Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
$oldHash=[string]$targets[0].sha256
if($oldHash -ceq $newHash){
 [pscustomobject]@{status='ALREADY_PINNED_NO_CHANGE';expires_at_utc=$manifest.until_utc}|ConvertTo-Json
 exit 0
}
if((Test-Path $backupPath) -or (Test-Path $receiptPath)){
 throw 'Repair attempted before: never overwrite an existing repair audit'
}
# First preserve the original plan bytes in a CREATE_NEW backup, never
# change created_at_utc/until_utc/Windows task cadence or any other hash.
$stream=[System.IO.File]::Open($backupPath,[System.IO.FileMode]::CreateNew,
 [System.IO.FileAccess]::Write,[System.IO.FileShare]::None)
try{$stream.Write($oldBytes,0,$oldBytes.Length);$stream.Flush($true)}
finally{$stream.Dispose()}
$targets[0].sha256=$newHash
$temp=$manifestPath+'.'+[guid]::NewGuid().ToString('N')+'.tmp'
try{
 $patched=[System.Text.UTF8Encoding]::new($false).GetBytes(
  ($manifest|ConvertTo-Json -Depth 12))
 $stream=[System.IO.File]::Open($temp,[System.IO.FileMode]::CreateNew,
   [System.IO.FileAccess]::Write,[System.IO.FileShare]::None)
 try{$stream.Write($patched,0,$patched.Length);$stream.Flush($true)}
 finally{$stream.Dispose()}
 Move-Item -LiteralPath $temp -Destination $manifestPath -Force
}finally{Remove-Item $temp -ErrorAction SilentlyContinue}
$receipt=[ordered]@{
 kind='V3_28H_ONLY_HEALTH_SIGNAL_FIX_REPIN_V1'
 repaired_at_utc=(Get-Date).ToUniversalTime().ToString('o')
 original_created_at_utc=$manifest.created_at_utc
 original_expiration_utc=$manifest.until_utc
 existing_task_name=$taskName
 old_runner_sha256=$oldHash;new_runner_sha256=$newHash
 changes_to_other_pins=0;duration_extended=$false
 v2r4_changed=$false;model_calls=0;orders=$false
}
$out=[System.Text.UTF8Encoding]::new($false).GetBytes(
 ($receipt|ConvertTo-Json -Depth 5))
$stream=[System.IO.File]::Open($receiptPath,[System.IO.FileMode]::CreateNew,
 [System.IO.FileAccess]::Write,[System.IO.FileShare]::None)
try{$stream.Write($out,0,$out.Length);$stream.Flush($true)}
finally{$stream.Dispose()}
# One user-triggered verification tick on the SAME existing task only;
# it does not reschedule or lengthen the 28h original task.
Start-ScheduledTask -TaskName $taskName -ErrorAction Stop
[pscustomobject]@{
 status='V3_28H_EXISTING_TASK_HEALTH_FIX_REPINNED_ONE_VERIFY_TICK_REQUESTED'
 unchanged_expires_at_utc=$manifest.until_utc
 existing_task=$taskName
 user_checks_file=$heartbeatPath
 no_new_tasks=$true;no_model=$true;orders=$false;v2r4_unchanged=$true
}|ConvertTo-Json
