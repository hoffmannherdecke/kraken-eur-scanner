param(
 [string]$TradingRoot=(Join-Path $env:USERPROFILE 'Trading'),
 [string]$SuccessorReleaseSha='',
 [switch]$Execute,
 [string]$Confirm=''
)
# One-shot technical PAPER cutover. Default: READ ONLY.
# Never reuse first-series activation or silently roll back an uncertain RPC.
$ErrorActionPreference='Stop'
$oldId='PAPER-V2R4-20261007T184255Z'
$oldSha='3c6729a6c548d169f56a97f07f75892f37211636'
$repo=Join-Path $TradingRoot 'Repos\kraken-eur-scanner'
$oldApp=Join-Path $TradingRoot 'Runtime\v2r4-paper-app'
$state=Join-Path $TradingRoot 'State'
$python=Join-Path $TradingRoot 'Runtime\kraken-eur-scanner-venv\Scripts\python.exe'
$endpoint='https://nlgzjmqgwueojlyqmoru.supabase.co/functions/v1/v2r4-technical-cutover'
$marker=Join-Path $state 'v2r4-technical-cutover-maintenance.json'
$complete=Join-Path $state 'v2r4-technical-cutover-completed.json'
$lock=Join-Path $state 'v2r4-technical-cutover-operator-lock.json'
$taskNames=@('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait','CryptoMiniPC-V2R4PaperLifecycle','CryptoMiniPC-V2R4PaperCloudSync','CryptoMiniPC-V3H3Shadow001')
$supervisorName='CryptoMiniPC-RuntimeSupervisor'
$phase='READ_ONLY'
function Need([bool]$Ok,[string]$Message){if(-not $Ok){throw $Message}}
function Atomic([string]$Path,[object]$Data){
 $tmp=$Path+'.tmp'
 [IO.File]::WriteAllText($tmp,(ConvertTo-Json $Data -Depth 16)+[Environment]::NewLine,[Text.UTF8Encoding]::new($false))
 Move-Item -LiteralPath $tmp -Destination $Path -Force
}
function Edge([string]$Action,[object]$Manifest=$null,[switch]$Commit){
 $t1=(Get-Content (Join-Path $TradingRoot 'Secrets\shadow-evidence-token.txt') -Raw).Trim()
 $t2=(Get-Content (Join-Path $TradingRoot 'Secrets\minipc-status-token.txt') -Raw).Trim()
 Need ($t1.Length -ge 24 -and $t2.Length -ge 24) 'Missing relay tokens'
 $headers=@{'X-Shadow-Evidence-Token'=$t1;'X-MiniPC-Status-Token'=$t2}
 if($Commit){$headers['X-Cutover-Confirm']='CUTOVER_V2R4_TECHNICAL_PAPER_ONLY'}
 $p=if($Manifest){@{action=$Action;manifest=$Manifest}}else{@{action=$Action}}
 Invoke-RestMethod -Uri $endpoint -Method Post -Headers $headers -ContentType 'application/json' -Body (ConvertTo-Json $p -Depth 16 -Compress) -TimeoutSec 40
}
function Stop-TaskBounded([string]$Name){
 Stop-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
 $deadline=(Get-Date).AddSeconds(20)
 do{$t=Get-ScheduledTask -TaskName $Name; if([string]$t.State -ne 'Running'){break};Start-Sleep -Milliseconds 250}while((Get-Date)-lt $deadline)
 Need ([string](Get-ScheduledTask -TaskName $Name).State -ne 'Running') "Could not stop $Name"
 Disable-ScheduledTask -TaskName $Name|Out-Null
 Need ([string](Get-ScheduledTask -TaskName $Name).State -eq 'Disabled') "Could not disable $Name"
}
function Restore-Old([string]$Backup){
 # Restore the exact original task enabled/running state, not an invented
 # all-enabled/all-running approximation. An already failed/Ready task should
 # NOT silently be turned into a fresh active old-series writer.
 $originalStateFile=Join-Path $Backup 'original-task-states.json'
 Need (Test-Path $originalStateFile) 'Original task state manifest missing; fail closed'
 $original=Get-Content $originalStateFile -Raw|ConvertFrom-Json
 # Failed scheduled task stop can leave children alive. A blind restart
 # would create a second writer on the immutable old PAPER series.
 Need-No-Old-Writers
 foreach($n in @($taskNames)+@($supervisorName)){
   $path=Join-Path $Backup ('tasks\'+$n+'.xml')
   Need (Test-Path $path) "Missing task backup: $n"
   $record=$original.PSObject.Properties[$n]
   Need ($null -ne $record) "Missing saved state for $n"
   Register-ScheduledTask -TaskName $n -Xml (Get-Content $path -Raw) -Force|Out-Null
   if($record.Value.enabled -eq $true){Enable-ScheduledTask -TaskName $n|Out-Null}
   else{Disable-ScheduledTask -TaskName $n|Out-Null}
 }
 foreach($n in @($taskNames)+@($supervisorName)){
   $saved=$original.PSObject.Properties[$n].Value
   if($saved.enabled -eq $true -and $saved.running -eq $true){
     Start-ScheduledTask -TaskName $n
   }
 }
}
function Old-Ids{
 $ids=[System.Collections.Generic.List[string]]::new()
 foreach($file in @(Get-ChildItem (Join-Path $oldApp 'paper_decisions') -File -Filter '*.json')){
   $d=Get-Content $file.FullName -Raw|ConvertFrom-Json
   Need ($d.series_id -eq $oldId -and $d.candidate_id) "Invalid old candidate file: $($file.Name)"
   $ids.Add([string]$d.candidate_id)
 }
 [string[]]$ordered=$ids.ToArray();[Array]::Sort($ordered,[StringComparer]::Ordinal)
 for($i=1;$i -lt $ordered.Count;$i++){Need ($ordered[$i] -cne $ordered[$i-1]) 'Duplicate local candidate ID'}
 $s=[Security.Cryptography.SHA256]::Create()
 try{$hex=([BitConverter]::ToString($s.ComputeHash([Text.Encoding]::UTF8.GetBytes(($ordered -join [char]10))))).Replace('-','').ToLowerInvariant()}
 finally{$s.Dispose()}
 [pscustomobject]@{count=$ordered.Length;sha=$hex}
}
function Old-Writer-Processes{
 # Stopping a Windows scheduled task does not prove every nested evaluator or
 # H3 child process has exited. A late writer can corrupt final ACK/snapshot.
 $patterns=@([regex]::Escape($oldApp+'\\'),[regex]::Escape((Join-Path $TradingRoot 'Runtime\\v3-h3-shadow-001')+'\\'))
 @(Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" -ErrorAction Stop |
   Where-Object {
     $line=[string]$_.CommandLine
     $line -and (($line -match $patterns[0]) -or ($line -match $patterns[1]))
   } | Select-Object ProcessId,CommandLine)
}
function Need-No-Old-Writers([int]$TimeoutSeconds=20){
 $deadline=(Get-Date).AddSeconds($TimeoutSeconds)
 do{
   $remaining=@(Old-Writer-Processes)
   if($remaining.Count -eq 0){return}
   Start-Sleep -Milliseconds 400
 }while((Get-Date)-lt $deadline)
 Need $false ("Old PAPER/H3 child process still alive; fail closed: "+(@($remaining|ForEach-Object{$_.ProcessId}) -join ','))
}
function New-Paper-Task([string]$Name,[string[]]$Args){
 $q=($Args|ForEach-Object{'"'+[string]$_+'"'}) -join ' '
 $act=New-ScheduledTaskAction -Execute $python -Argument $q
 $trg=New-ScheduledTaskTrigger -AtStartup
 $set=New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
 Register-ScheduledTask -TaskName $Name -Action $act -Trigger $trg -Settings $set -User SYSTEM -RunLevel Highest -Force|Out-Null
 Start-ScheduledTask -TaskName $Name
}
try{
 $sha=$SuccessorReleaseSha.ToLowerInvariant()
 Need ($sha -match '^[0-9a-f]{40}$') 'Reviewed successor SHA required'
 Need (-not(Test-Path $marker) -and -not(Test-Path $lock) -and -not(Test-Path $complete)) 'Existing cutover marker: do not blindly retry'
 Need ((git -C $repo branch --show-current).Trim() -eq 'main') 'Repository must be on main'
 Need (@(git -C $repo status --porcelain).Count -eq 0) 'Repository dirty'
 Need ((git -C $repo rev-parse HEAD).Trim().ToLowerInvariant() -eq $sha) 'Reviewed SHA does not match local main'
 $app=Join-Path $TradingRoot ('Runtime\v2r4-paper-stage-'+$sha.Substring(0,12))
 $manifestPath=Join-Path $app 'technical-stage-manifest.json'
 Need (Test-Path $manifestPath) 'Final isolated staging missing'
 $stage=Get-Content $manifestPath -Raw|ConvertFrom-Json
 Need ($stage.source_repo_sha -eq $sha -and $stage.status -eq 'STAGED_INERT_NO_ACTIVATION') 'Invalid staged release'
 Need (-not(Test-Path (Join-Path $app 'paper_runtime_control.json'))) 'Stage is not inert'
 $old=Get-Content (Join-Path $oldApp 'paper_runtime_control.json') -Raw|ConvertFrom-Json
 Need ($old.series_id -eq $oldId -and $old.release_repo_sha -eq $oldSha -and $old.paper_only -eq $true -and $old.real_money_actions_enabled -eq $false) 'Old series drift or unsafe control'
 Need ($stage.strategy_fingerprint_sha256 -eq $old.strategy_fingerprint_sha256 -and [double]$old.scout_notional_eur -eq 50 -and [double]$old.stage2_notional_eur -eq 50) 'Strategy/sizing changed'
 foreach($n in @($taskNames)+@($supervisorName)){$null=Get-ScheduledTask -TaskName $n -ErrorAction Stop}
 $gateRaw=& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File (Join-Path $repo 'tools\minipc-v2r4-technical-cutover-readiness.ps1') -TradingRoot $TradingRoot -SuccessorReleaseSha $sha
 $gate=($gateRaw -join [Environment]::NewLine)|ConvertFrom-Json
 Need ($gate.status -eq 'READ_ONLY_GATE_PASS_NOT_CUTOVER') 'Physical staged file hash or old baseline preflight blocked'
 $ready=Edge 'readiness'
 Need ($ready.ok -eq $true -and $ready.old_series_status -eq 'active' -and $ready.source_gate.ok -eq $true) 'Cloud readiness blocked, no tasks touched'
 $cloudStatus=Edge 'status'
 Need ($cloudStatus.ok -eq $true -and -not $cloudStatus.rotation) 'Unexpected prior rotation'
 Need (@($cloudStatus.paper_series|Where-Object{$_.status -eq 'active' -and $_.series_id -eq $oldId}).Count -eq 1) 'Cloud predecessor not singly active'
 if(-not $Execute){
   [pscustomobject]@{kind='V2R4_TECHNICAL_OPERATOR_PLAN_V1';status='CLOUD_STAGE_READY_NO_MUTATION';sha=$sha;paper_only=$true;orders=$false}|ConvertTo-Json
   return
 }
 Need ($Confirm -ceq 'EXECUTE_APPROVED_V2R4_TECHNICAL_PAPER_ONLY') 'Explicit cutover confirmation required'
 $admin=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
 Need ($admin.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) 'Admin PowerShell required'
 Need (Test-Path $python) 'Python venv missing'
 $phase='BACKUP_PREPARATION'
 $started=[datetime]::UtcNow
 $backup=Join-Path $TradingRoot ('Backups\v2r4-technical-'+$started.ToString('yyyyMMddTHHmmssZ'))
 Need (-not(Test-Path $backup)) 'Backup path already exists'
 New-Item -ItemType Directory -Force (Join-Path $backup 'tasks')|Out-Null
 $originalTaskStates=[ordered]@{}
 foreach($n in @($taskNames)+@($supervisorName)){
   $t=Get-ScheduledTask -TaskName $n -ErrorAction Stop
   $originalTaskStates[$n]=[ordered]@{
     enabled=([bool]$t.Settings.Enabled)
     running=([string]$t.State -eq 'Running')
     state=[string]$t.State
   }
   [IO.File]::WriteAllText((Join-Path $backup ('tasks\'+$n+'.xml')),(Export-ScheduledTask -TaskName $n),[Text.UTF8Encoding]::new($false))
 }
 Atomic (Join-Path $backup 'original-task-states.json') $originalTaskStates
 foreach($n in @($taskNames)+@($supervisorName)){
   Need (Test-Path (Join-Path $backup ('tasks\'+$n+'.xml'))) "Task XML not safely exported: $n"
 }
 Need (Test-Path (Join-Path $backup 'original-task-states.json')) 'Task state snapshot missing'
 # This is the first persisted mutation intended to affect recovery flow.
 # Before this point failed XML export leaves running services unchanged.
 Atomic $lock ([ordered]@{kind='V2R4_TECHNICAL_LOCK_V1';started_at=$started.ToString('o');orders=$false;sha=$sha})
 $phase='PRE_COMMIT'
 $lease=[ordered]@{kind='V2R4_TECHNICAL_MAINTENANCE_V1';phase='ARMING';created_at_utc=$started.ToString('o');expires_at_utc=$started.AddMinutes(10).ToString('o');predecessor_series_id=$oldId;successor_repo_sha=$sha;task_names=@($taskNames);orders_enabled=$false}
 Atomic $marker $lease
 # The running supervisor may otherwise race with the old tasks during
 # quiescence. Stop its timer BEFORE stopping the old Paper and H3 tasks;
 # its exact XML was captured above for bounded pre-commit recovery.
 Stop-TaskBounded $supervisorName
 foreach($n in $taskNames){Stop-TaskBounded $n}
 Need-No-Old-Writers
 $lease.phase='QUIESCED';Atomic $marker $lease
 $syncOutput=& $python (Join-Path $oldApp 'v2r4-paper-cloud-sync.py') --app-root $oldApp --trading-root $TradingRoot --once
 Need ($LASTEXITCODE -eq 0) 'Final old cloud sync failed'
 $ack=($syncOutput|Select-Object -Last 1)|ConvertFrom-Json
 Need ($ack.status -eq 'HEALTHY' -and $ack.series_id -eq $oldId) 'Final sync not acknowledged'
 $ids=Old-Ids;$cloud=Edge 'checkpoint'
 Need ($cloud.ok -eq $true -and $cloud.cloud.old_series_id -eq $oldId) 'Cloud checkpoint missing'
 Need ([long]$ids.count -eq [long]$cloud.cloud.candidate_count -and $ids.sha -ceq $cloud.cloud.candidate_ids_sha256) 'Cloud/local candidate identity mismatch'
 Need ($null -ne $cloud.cloud.last_outcome_updated_at) 'No cloud timestamp'
 # Provenance: old 6h/24h follow-up horizons that have not matured
 # before this technical stop must NOT silently become 0% or a fake NO_TRADE.
 # The frozen old app is snapshotted intact; a compact censorship summary
 # records the boundary without rewriting any past decision or horizon.
 $followupDir=Join-Path $oldApp 'paper_followups'
 $summary=[ordered]@{
   kind='PAPER_TECHNICAL_CUTOVER_CENSOR_V1'
   predecessor_series_id=$oldId
   recorded_at_utc=[datetime]::UtcNow.ToString('o')
   total_candidates=[long]$ids.count
   opportunity_horizons_minutes=@(15,60,240,720,1440)
   completed_opportunity_horizons=[ordered]@{}
   unmeasured_opportunity_horizons=[ordered]@{}
   archive_source='immutable_old_app_snapshot'
   outcome_imputation='FORBIDDEN'
   decision_rewrite='FORBIDDEN'
   future_followup_state='CENSORED_AT_TECHNICAL_CUTOVER_UNLESS_SEPARATELY_VERIFIED'
 }
 $followups=@{}
 if(Test-Path $followupDir){
   foreach($file in @(Get-ChildItem $followupDir -Filter '*.json' -File)){
     $f=Get-Content $file.FullName -Raw|ConvertFrom-Json
     if($f.series_id -eq $oldId -and $f.candidate_id){
       $followups[[string]$f.candidate_id]=$f
     }
   }
 }
 foreach($h in @(15,60,240,720,1440)){
   $complete=0
   foreach($f in $followups.Values){
     if(-not $f.opportunity_audit -or -not $f.opportunity_audit.horizons){continue}
     $detail=$f.opportunity_audit.horizons.PSObject.Properties[[string]$h]
     if($detail -and $detail.Value.complete -eq $true){$complete++}
   }
   $summary.completed_opportunity_horizons[[string]$h]=$complete
   $summary.unmeasured_opportunity_horizons[[string]$h]=[math]::Max(0,([long]$ids.count-$complete))
 }
 Atomic (Join-Path $backup 'cutover-followup-censor-summary.json') $summary
 $snapshotInputs=Join-Path $backup 'snapshot-inputs'
 New-Item -ItemType Directory -Force $snapshotInputs|Out-Null
 Copy-Item -LiteralPath $oldApp -Destination (Join-Path $snapshotInputs 'old-paper') -Recurse
 $stateCopies=Join-Path $snapshotInputs 'state';New-Item -ItemType Directory -Force $stateCopies|Out-Null
 Copy-Item -LiteralPath (Join-Path $backup 'tasks') -Destination (Join-Path $snapshotInputs 'scheduled-task-xml') -Recurse
 Copy-Item -LiteralPath (Join-Path $backup 'original-task-states.json') -Destination (Join-Path $snapshotInputs 'original-task-states.json')
 Copy-Item -LiteralPath (Join-Path $backup 'cutover-followup-censor-summary.json') -Destination (Join-Path $snapshotInputs 'cutover-followup-censor-summary.json')
 foreach($pat in @('v2r4-paper-*.json','v2r4-wait-*.json','v3-h3-*.json')){
   Get-ChildItem $state -Filter $pat -File|ForEach-Object{Copy-Item $_.FullName (Join-Path $stateCopies $_.Name)}
 }
 $h3App=Join-Path $TradingRoot 'Runtime\v3-h3-shadow-001'
 if(Test-Path $h3App){Copy-Item -LiteralPath $h3App -Destination (Join-Path $snapshotInputs 'h3-001') -Recurse}
 $snapshot=Join-Path $backup 'old-paper-h3-state.zip'
 Compress-Archive -Path (Join-Path $snapshotInputs '*') -DestinationPath $snapshot -CompressionLevel Optimal
 Need ((Get-Item $snapshot).Length -gt 1000) 'Snapshot incomplete'
 # Hash-validate every archived evidence/config/task file against its
 # stopped original. A readable zip and a zip digest alone do not prove
 # that all old decisions, positions and restart task definitions survived.
 Add-Type -AssemblyName System.IO.Compression
 Add-Type -AssemblyName System.IO.Compression.FileSystem
 $archive=[IO.Compression.ZipFile]::OpenRead($snapshot)
 try {
   $allSource=@(Get-ChildItem -LiteralPath $snapshotInputs -Recurse -File)
   $entries=@($archive.Entries|Where-Object{-not [string]::IsNullOrEmpty($_.Name)})
   Need ($entries.Count -eq $allSource.Count) 'Archive omitted or duplicated original files'
   $entryMap=@{}
   foreach($e in $entries){
     Need (-not $entryMap.ContainsKey($e.FullName)) "Duplicate zip entry: $($e.FullName)"
     $entryMap[$e.FullName]=$e
   }
   $hash=[Security.Cryptography.SHA256]::Create()
   try {
     foreach($f in $allSource){
       $rel=$f.FullName.Substring($snapshotInputs.Length).TrimStart([char]'\',[char]'/').Replace('\','/')
       Need ($entryMap.ContainsKey($rel)) "Snapshot file missing: $rel"
       $entry=$entryMap[$rel]
       Need ($entry.Length -eq $f.Length) "Snapshot size differs: $rel"
       $reader=$entry.Open()
       try{$inArchive=([BitConverter]::ToString($hash.ComputeHash($reader))).Replace('-','').ToLowerInvariant()}
       finally{$reader.Dispose()}
       $onDisk=(Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
       Need ($inArchive -ceq $onDisk) "Snapshot byte mismatch: $rel"
     }
   }finally{$hash.Dispose()}
 }finally{$archive.Dispose()}
 $backupSha=(Get-FileHash $snapshot -Algorithm SHA256).Hash.ToLowerInvariant()
 & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'tools\minipc-runtime-supervisor.ps1') -TradingRoot $TradingRoot|Out-Null
 & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'tools\minipc-watchdog.ps1') -TradingRoot $TradingRoot|Out-Null
 & $python (Join-Path $repo 'tools\minipc-status-sync.py') --trading-root $TradingRoot --once|Out-Null
 Need ($LASTEXITCODE -eq 0) 'Health not synced'
 $utc=[datetime]::UtcNow;$utc=[datetime]::new($utc.Year,$utc.Month,$utc.Day,$utc.Hour,$utc.Minute,$utc.Second,[DateTimeKind]::Utc)
 $newId='PAPER-V2R4-'+$utc.ToString('yyyyMMddTHHmmssZ')
 $newTest='PAPER-V2R4-TECH-'+$utc.ToString('yyyyMMdd')
 $cutTime=$utc.ToString('yyyy-MM-ddTHH:mm:ssZ')
 $cfg=$old|ConvertTo-Json -Depth 16|ConvertFrom-Json
 foreach($v in @(
   @{k='series_id';v=$newId},@{k='test_id';v=$newTest},@{k='predecessor_series_id';v=$oldId},
   @{k='series_started_at_utc';v=$cutTime},@{k='release_repo_sha';v=$sha},
   @{k='runtime_bundle_fingerprint_sha256';v=$stage.proposed_runtime_bundle_fingerprint_sha256},
   @{k='technical_change_id';v='V2R4_TECHNICAL_RECOVERY_20261009'},
   @{k='technical_change_approved';v=$true}
 )){$cfg|Add-Member -NotePropertyName $v.k -NotePropertyValue $v.v -Force}
 $request=[ordered]@{old_series_id=$oldId;expected_old_release_sha=$oldSha;new_series_id=$newId;new_test_id=$newTest;cutover_at_utc=$cutTime;new_config=$cfg;expected_old_outcomes=[long]$cloud.cloud.candidate_count;expected_old_candidate_ids_sha256=$cloud.cloud.candidate_ids_sha256;expected_old_trades=[long]$cloud.cloud.trade_count;expected_old_last_updated_at=$cloud.cloud.last_outcome_updated_at;physical_proof=[ordered]@{old_paper_tasks_stopped=$true;h3_001_stopped=$true;last_old_sync_acknowledged=$true;snapshot_verified=$true;staged_app_still_inert=$true;orders_disabled=$true;snapshot_sha256=$backupSha;old_candidate_ids_sha256=$ids.sha;staged_manifest_sha256=(Get-FileHash $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant();staged_code_bundle_sha256=$stage.proposed_runtime_bundle_fingerprint_sha256;strategy_fingerprint_sha256=$old.strategy_fingerprint_sha256}}
 Need ([datetime]::UtcNow -lt ([datetime]$lease.expires_at_utc)) 'MAINTENANCE_LEASE_EXPIRED_BEFORE_RPC: no cloud mutation'
 $phase='CLOUD_OUTCOME_UNKNOWN'
 $commit=$null
 try{$commit=Edge 'cutover' $request -Commit}
 catch{
   # Never retry the RPC. Inspect a read-only committed rotation instead.
   $seen=Edge 'status'
   Need ($seen.ok -eq $true -and $seen.rotation -and $seen.rotation.successor_series_id -eq $newId) 'UNKNOWN_CLOUD_OUTCOME: leave tasks stopped; manual recovery needed'
   $commit=[pscustomobject]@{ok=$true;successor_series_id=$newId}
 }
 Need ($commit.ok -eq $true -and $commit.successor_series_id -eq $newId) 'UNKNOWN_CLOUD_OUTCOME: no automatic rollback'
 $phase='CLOUD_COMMITTED';$lease.phase='CLOUD_COMMITTED';Atomic $marker $lease
 Atomic (Join-Path $backup 'committed-manifest.json') $request
 Atomic (Join-Path $app 'paper_runtime_control.json') $cfg
 foreach($dir in @('paper_decisions','paper_positions','paper_rechecks','paper_revalidations','paper_followups','paper_trigger_receipts','handoff_queue')){
   New-Item -ItemType Directory -Force (Join-Path $app $dir)|Out-Null
 }
 $nextState=Join-Path $state ('paper-v2r4-'+$newId)
 New-Item -ItemType Directory -Force $nextState|Out-Null
 $api=Join-Path $TradingRoot 'Secrets\openai-api-key.txt'
 New-Paper-Task 'CryptoMiniPC-V2R4PaperCandidates' @((Join-Path $app 'v2r4-paper-local-runtime.py'),'--mode','candidates','--app-root',$app,'--trading-root',$TradingRoot,'--api-key-file',$api,'--paper-state-dir',$nextState,'--interval-seconds','2')
 New-Paper-Task 'CryptoMiniPC-V2R4PaperWait' @((Join-Path $app 'paper_evaluator\v2r4_wait_runtime.py'),'--decision-dir',(Join-Path $app 'paper_decisions'),'--recheck-dir',(Join-Path $app 'paper_rechecks'),'--candidate-dir',(Join-Path $app 'handoff_queue'),'--receipt-dir',(Join-Path $app 'paper_trigger_receipts'),'--state',(Join-Path $nextState 'wait-state.json'),'--heartbeat',(Join-Path $state 'v2r4-paper-wait-runtime-heartbeat.json'),'--altrady-log',(Join-Path $TradingRoot 'Logs\altrady-trigger-events.jsonl'),'--spec',(Join-Path $app 'paper_strategy_spec.json'),'--control',(Join-Path $app 'paper_runtime_control.json'),'--api-key-file',$api,'--fallback-seconds','10','--loop-seconds','1','--execute-recheck')
 New-Paper-Task 'CryptoMiniPC-V2R4PaperLifecycle' @((Join-Path $app 'v2r4-paper-local-runtime.py'),'--mode','lifecycle','--app-root',$app,'--trading-root',$TradingRoot,'--interval-seconds','60')
 New-Paper-Task 'CryptoMiniPC-V2R4PaperCloudSync' @((Join-Path $app 'v2r4-paper-cloud-sync.py'),'--app-root',$app,'--trading-root',$TradingRoot,'--paper-state-dir',$nextState,'--interval-seconds','60')
 $heartbeats=@('v2r4-paper-candidate-runtime-heartbeat.json','v2r4-paper-wait-runtime-heartbeat.json','v2r4-paper-lifecycle-heartbeat.json','v2r4-paper-cloud-sync-heartbeat.json')
 $deadline=(Get-Date).AddSeconds(120);$healthy=$false
 do{
   Start-Sleep -Seconds 2;$healthy=$true
   foreach($name in $heartbeats){
     try{$hb=Get-Content (Join-Path $state $name) -Raw|ConvertFrom-Json
       if($hb.status -ne 'HEALTHY' -or ([datetime]$hb.checked_at_utc).ToUniversalTime() -lt $utc){$healthy=$false}
     }catch{$healthy=$false}
   }
 }while(-not $healthy -and (Get-Date)-lt $deadline)
 Need $healthy 'SUCCESSOR_NOT_HEALTHY: cloud committed; old runtime remains frozen'
 $post=Edge 'status'
 Need ($post.ok -eq $true -and $post.rotation.successor_series_id -eq $newId -and
   @($post.paper_series|Where-Object{$_.status -eq 'active' -and $_.series_id -eq $newId}).Count -eq 1) 'Cloud successor not uniquely active'
 Need ((Get-ScheduledTask -TaskName 'CryptoMiniPC-V3H3Shadow001').State -eq 'Disabled') 'Old H3 did not remain disabled'
 Atomic $complete ([ordered]@{kind='V2R4_TECHNICAL_CUTOVER_COMPLETED_V1';completed_at_utc=[datetime]::UtcNow.ToString('o');predecessor_series_id=$oldId;successor_series_id=$newId;h3_001_retired=$true;orders=$false;real_money_actions=$false;snapshot_sha256=$backupSha;release_repo_sha=$sha})
 # Only after the verified H3-001 retirement marker exists, restore the
 # independent runtime supervisor. New code skips permanently retired H3.
 Enable-ScheduledTask -TaskName $supervisorName|Out-Null
 Start-ScheduledTask -TaskName $supervisorName
 Remove-Item $marker,$lock -Force
 [pscustomobject]@{status='CUTOVER_COMPLETED_PAPER_ONLY';successor_series_id=$newId;h3_001='FROZEN';orders=$false;real_money_actions=$false}|ConvertTo-Json
}catch{
 $problem=$_.Exception.Message
 if($phase -eq 'CLOUD_COMMITTED'){
   # The SQL rotation has committed; never resurrect the predecessor.
   # Stop any partially started successor when post-cutover verification fails.
   foreach($n in $taskNames){
     if($n -eq 'CryptoMiniPC-V3H3Shadow001'){continue}
     Stop-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue
     Disable-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue|Out-Null
   }
   $phase='POST_COMMIT_FAIL_CLOSED_SUCCESSOR_STOPPED'
 }
 if($phase -eq 'PRE_COMMIT'){
   try{
     if($backup -and (Test-Path (Join-Path $backup 'tasks'))){
       Restore-Old $backup
       Remove-Item $marker,$lock -Force -ErrorAction SilentlyContinue
       $phase='PRE_COMMIT_RESTORED'
     }
   }catch{$phase='RESTORE_FAILED_FAIL_CLOSED';$problem+=' | restore failed: '+$_.Exception.Message}
 }
 [pscustomobject]@{status='BLOCKED';phase=$phase;reason=$problem;blind_retry_allowed=$false;orders=$false;real_money_actions=$false}|ConvertTo-Json -Depth 6
 if(-not $Execute){return}
 exit 2
}
