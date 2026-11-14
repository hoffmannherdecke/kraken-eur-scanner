[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][ValidateSet('Prepared','PostStop','ExecutorClosed')][string]$Phase,
 [Parameter(Mandatory=$true)][string]$WindowDirectory,
 [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{64}$')][string]$ExpectedFixedInputsSha256,
 [Security.SecureString]$AdminPassword,
 [string]$CaFile
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$utf8=[Text.UTF8Encoding]::new($false,$true)
if($env:COMPUTERNAME -ine 'MINI-PC' -or $WindowDirectory -cnotmatch '^C:\\Users\\ADMIN\\Trading\\Research\\V3Paper\\PR700-Window-[0-9]{8}T[0-9]{6}Z$'){throw 'ORIGINAL_LOCAL_WINDOW_REQUIRED'}
$fixedPath=Join-Path $WindowDirectory 'cutover-fixed-inputs.json'
$fixedHash=$ExpectedFixedInputsSha256
$fixedBytes=[IO.File]::ReadAllBytes($fixedPath)
$sha=[Security.Cryptography.SHA256]::Create()
try{$actualFixedHash=[BitConverter]::ToString($sha.ComputeHash($fixedBytes)).Replace('-','').ToLowerInvariant()}
finally{$sha.Dispose()}
if($actualFixedHash -cne $fixedHash){throw 'PR701_FIXED_INPUT_DRIFT'}
$fixed=$utf8.GetString($fixedBytes)|ConvertFrom-Json
function Hash([string]$Path){(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Write-Once([string]$Path,[byte[]]$Bytes){
 if([IO.File]::Exists($Path)){
  if([Convert]::ToBase64String([IO.File]::ReadAllBytes($Path)) -cne [Convert]::ToBase64String($Bytes)){throw "IMMUTABLE_ORIGINAL_DRIFT $Path"}
  return
 }
 $temp=$Path+'.pending-'+[guid]::NewGuid().ToString('N')
 try{[IO.File]::WriteAllBytes($temp,$Bytes);[IO.File]::Move($temp,$Path)}
 finally{if([IO.File]::Exists($temp)){[IO.File]::Delete($temp)}}
}
function Write-Json([string]$Path,$Value){Write-Once $Path ($utf8.GetBytes(($Value|ConvertTo-Json -Depth 30 -Compress)))}
function Publish([string]$Path){Write-Once (Join-Path $handoff ([IO.Path]::GetFileName($Path))) ([IO.File]::ReadAllBytes($Path))}
$planLeaf=@{Prepared='plan.stage4.json';PostStop='plan.stop.json';ExecutorClosed='plan.cas.json'}[$Phase]
$planPath=Join-Path $WindowDirectory $planLeaf
$plan=Get-Content -LiteralPath $planPath -Raw|ConvertFrom-Json -ErrorAction Stop
if($plan.kind -cne 'V3_ONE_TIME_PAPER_RELEASE_PLAN_V1' -or $plan.repo_sha -cne $fixed.repo_sha -or
 $plan.bundle_sha256 -cne $fixed.bundle_sha256 -or $plan.strategy_sha256 -cne $fixed.strategy_sha256 -or
 $plan.cas_epoch.epoch_id -cnotmatch '^V3CAS-AUDIT-[a-f0-9]{32}$' -or $plan.series_id -cnotmatch '^PAPER-V3-[0-9]{8}T[0-9]{6}Z$' -or
 -not $WindowDirectory.EndsWith(('PR700-Window-'+$plan.series_id.Substring(9)),[StringComparison]::Ordinal)){throw 'ORIGINAL_PLAN_DRIFT'}
$id='V3-ONETIME-'+$plan.cas_epoch.epoch_id.Substring(12)
$stateBase='C:\Users\ADMIN\Trading\State\'+$id
$handoff='D:\V3-PR682-Authority-Handoff\PR700-Window-'+$plan.series_id.Substring(9)
if(-not (Test-Path -LiteralPath $handoff -PathType Container)){throw 'ORIGINAL_WINDOW_HANDOFF_MISSING'}
if($Phase -eq 'Prepared'){
 $prepare=Get-Content -LiteralPath ($stateBase+'.prepare.attempted.json') -Raw|ConvertFrom-Json
 if($prepare.approval_sha256 -cnotmatch '^[a-f0-9]{64}$'){throw 'PREPARE_ORIGINAL_ATTEMPT_REQUIRED'}
 $xml=$stateBase+'.v3-disabled.xml'
 $xmlBytes=[IO.File]::ReadAllBytes($xml)
 $task=Get-ScheduledTask -TaskPath '\' -TaskName 'CryptoMiniPC-V3PaperSingleWriter'
 if($task.State -cne 'Disabled' -or @($task.Actions).Count -ne 1 -or
  ($utf8.GetString($xmlBytes)) -cne (Export-ScheduledTask -TaskName $task.TaskName -TaskPath '\')){throw 'PREPARED_DISABLED_TASK_DRIFT'}
 $match=@($plan.tasks|Where-Object {$_.name -ceq 'CryptoMiniPC-V3PaperSingleWriter'})
 if($match.Count -ne 1){throw 'EXACT_WRITER_TASK_REQUIRED'}
 $match[0].xml_path=$xml
 $match[0].xml_sha256=Hash $xml
 $next=Join-Path $WindowDirectory 'plan.stop.json'
 Write-Json $next $plan
 $action=$task.Actions[0]
 $sha=[Security.Cryptography.SHA256]::Create()
 try{
  $actionBytes=$utf8.GetBytes([string]$action.Execute+[char]0+[string]$action.Arguments+[char]0+[string]$action.WorkingDirectory)
  $actionHash=[BitConverter]::ToString($sha.ComputeHash($actionBytes)).Replace('-','').ToLowerInvariant()
 }finally{$sha.Dispose()}
 $actionReceipt=Join-Path $WindowDirectory 'prepared-task-action.json'
 Write-Json $actionReceipt ([ordered]@{kind='PR701_PREPARED_TASK_ACTION_V1';release_commit=$fixed.repo_sha;
  series_id=$plan.series_id;epoch_id=$plan.cas_epoch.epoch_id;task_xml_sha256=$match[0].xml_sha256;
  native_task_action_sha256=$actionHash;native_task_launcher_file_sha256=$fixed.artifacts.'paper_evaluator/v3_paper_minipc_native_launcher_v1.py'})
 Publish $xml
 Publish $actionReceipt
 Publish $next
 Write-Output 'PR701_STOP_PLAN_BOUND'
 return
}
if($null -eq $AdminPassword){throw 'LOCAL_EXISTING_PG_ADMIN_SECURESTRING_REQUIRED'}
$stage='C:\Users\ADMIN\Trading\Staging\V3Paper-INACTIVE-'+$fixed.repo_sha.Substring(0,12)
$operator=Join-Path $stage 'tools\v3-one-time-release.ps1'
$module=Join-Path $stage 'tools\v3-one-time-release-authorization.psm1'
if((Hash $operator) -cne $fixed.artifacts.'tools/v3-one-time-release.ps1' -or
 (Hash $module) -cne $fixed.artifacts.'tools/v3-one-time-release-authorization.psm1'){throw 'ORIGINAL_PSQL_TRANSPORT_SOURCE_HOLD'}
Import-Module $module -Scope Local
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($operator,[ref]$tokens,[ref]$errors)
$functions=@($ast.FindAll({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq 'Invoke-V3ReleasePg'},$false))
if($errors.Count -ne 0 -or $functions.Count -ne 1){throw 'ORIGINAL_PSQL_TRANSPORT_AST_HOLD'}
. ([scriptblock]::Create($functions[0].Extent.Text))
if($Phase -eq 'ExecutorClosed'){
 $query=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'Executor-Close-Readback.sql.in') -Raw
 $query=$query.Replace('__EPOCH_ID__',$plan.cas_epoch.epoch_id).TrimEnd().TrimEnd(';')
 $wire=Invoke-V3ReleasePg -Sql ("BEGIN READ ONLY; SELECT to_jsonb(x) FROM ("+$query+") AS x; COMMIT;") -Password $AdminPassword -Ca $CaFile
 $row=$wire|ConvertFrom-Json -ErrorAction Stop
 if($row.can_login -ne $false -or $row.password_is_null -ne $true -or $row.connection_limit -ne 0 -or $row.sessions -ne 0){
  throw 'EXECUTOR_CLOSE_UNCONFIRMED_DO_NOT_ACTIVATE'
 }
 $out=Join-Path $WindowDirectory ('executor-closed-'+[guid]::NewGuid().ToString('N')+'.json')
 Write-Once $out ($utf8.GetBytes($wire))
 Publish $out
 if(@($row.active_series).Count -ne 1 -or $row.active_series[0] -cne $plan.series_id -or $row.epoch_attempts -ne 1){
  throw 'EXECUTOR_CLOSED_CAS_OUTCOME_UNCONFIRMED_NO_RETRY'
 }
 Write-Output 'PR701_EXECUTOR_CLOSED_AWAIT_INDEPENDENT_POSTCAS_READER'
 return
}
$stopFile=$stateBase+'.stop.completed.json'
$stop=Get-Content -LiteralPath $stopFile -Raw|ConvertFrom-Json
$stopAt=[DateTimeOffset]::Parse([string]$stop.observed_at_utc)
if($stop.state -cne 'QUIESCED' -or $stop.approval_sha256 -cnotmatch '^[a-f0-9]{64}$'){throw 'ORIGINAL_STOP_REQUIRED_NO_RETRY'}
$previous=@('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait')
$aftercare=@('CryptoMiniPC-V2R4PaperLifecycle','CryptoMiniPC-V2R4PaperCloudSync')
foreach($name in $previous){
 if((Get-ScheduledTask -TaskPath '\' -TaskName $name).State -cne 'Disabled'){throw 'ORIGINAL_OLD_INTAKE_FENCE_HOLD'}
}
foreach($name in $aftercare){
 if((Get-ScheduledTask -TaskPath '\' -TaskName $name).State -cne 'Running'){throw 'ORIGINAL_AFTERCARE_HOLD'}
}
$superPath='C:\Users\ADMIN\Trading\State\minipc-runtime-supervisor.json'
$super=Get-Content -LiteralPath $superPath -Raw|ConvertFrom-Json
$superAt=[DateTimeOffset]::Parse([string]$super.checked_at_utc)
$age=([DateTimeOffset]::UtcNow-$superAt).TotalSeconds
if($super.v3_paper_old_intake_fence.mode -cne 'QUIESCED' -or $superAt -lt $stopAt -or $age -lt 0 -or $age -gt 150){
 throw 'WAIT_FOR_ORIGINAL_SUPERVISOR_ACK_DO_NOT_REPEAT_STOP'
}
$reviewPath=Join-Path $WindowDirectory 'Sechs-Nachweise-zur-unabhaengigen-Freigabe.json'
$review=Get-Content -LiteralPath $reviewPath -Raw|ConvertFrom-Json
if($review.release_commit -cne $fixed.repo_sha -or $review.series_id -cne $plan.series_id -or
 @($review.verified_content_envelopes).Count -ne 6){throw 'SIX_ORIGINALS_SERIES_DRIFT'}
$stage4Path=Join-Path $WindowDirectory 'stage4-owner-approved.json'
$stage4=Get-Content -LiteralPath $stage4Path -Raw|ConvertFrom-Json
$dry=@($review.verified_content_envelopes|Where-Object {$_.id -ceq 'V3_SINGLE_WRITER_FENCE_CLOUD_CAS_DRYRUN'})
if($dry.Count -ne 1 -or $stage4.release_commit -cne $fixed.repo_sha -or $stage4.successor_series_id -cne $plan.series_id -or
 $stage4.scope -cne 'CLOUD_STAGE4_EPOCH_OPEN' -or $stage4.plan_sha256 -cne $review.stage4_plan_sha256 -or
 $stage4.dry_run_sha256 -cne $dry[0].sha256 -or $stage4.decision -cne 'ISSUED_FOR_EXACT_RUNTIME_RELEASE'){
 throw 'STAGE4_OWNER_ORIGINAL_DRIFT'
}
$stage4Plan=Join-Path $WindowDirectory 'plan.stage4.json'
if((Hash $stage4Plan) -cne $stage4.plan_sha256){throw 'STAGE4_PLAN_HASH_DRIFT'}
foreach($proof in $review.verified_content_envelopes){
 if($proof.evidence_path -cnotmatch '^research/pr(?:699|700)-[A-Za-z0-9.-]+\.json$' -or
  (Hash (Join-Path $WindowDirectory $proof.evidence_path)) -cne $proof.sha256){throw 'REVIEWED_PROOF_BYTES_DRIFT'}
}
$facts=[ordered]@{kind='PR700_REVIEWED_CAS_INPUT_FACTS_V1';series_id=$plan.series_id;epoch_id=$plan.cas_epoch.epoch_id;
 original_stop_sha256=(Hash $stopFile);explicit_human_release_decision='APPROVED_EXPERIMENTAL_PAPER';
 old_followup_owner_preserved=$true;physical_v2r4_writer_fence_verified=$true;
 supervisor_old_intake_rearm_blocked=$true;independent_six_e2e_proofs_verified=$true}
# These are request contents. The distinct V3_PAPER_CAS CMS is still required.
$factsPath=Join-Path $WindowDirectory ('cas-facts-'+[guid]::NewGuid().ToString('N')+'.json')
Write-Json $factsPath $facts
$sql=(Get-Content -LiteralPath (Join-Path $PSScriptRoot 'pr700-production-single-writer-readonly.sql') -Raw).Replace('__PROPOSED_SERIES__',$plan.series_id).TrimEnd().TrimEnd(';')
$cloud=Invoke-V3ReleasePg -Sql ("BEGIN READ ONLY; SELECT jsonb_agg(to_jsonb(x)) FROM ("+$sql+") AS x; COMMIT;") -Password $AdminPassword -Ca $CaFile
$cloudFile=Join-Path $WindowDirectory ('poststop-cloud-'+[guid]::NewGuid().ToString('N')+'.json')
Write-Once $cloudFile ($utf8.GetBytes($cloud))
$output=Join-Path $WindowDirectory ('request-'+[guid]::NewGuid().ToString('N'))
$python='C:\Users\ADMIN\Trading\Runtime\kraken-eur-scanner-venv\Scripts\python.exe'
& $python -I -B (Join-Path $PSScriptRoot 'Bind-PostStop.py') $planPath $stopFile ($stateBase+'.v3-disabled.xml') $cloudFile $factsPath $output --fixed-inputs $fixedPath --fixed-inputs-sha256 $fixedHash
if($LASTEXITCODE -ne 0){throw 'POSTSTOP_EXACT_REQUEST_BINDING_HOLD'}
$digestSql=Get-Content -LiteralPath (Join-Path $output 'request-digest-readonly.sql') -Raw
$digest=Invoke-V3ReleasePg -Sql ("BEGIN READ ONLY; "+$digestSql+" COMMIT;") -Password $AdminPassword -Ca $CaFile
if($digest -cnotmatch '^[a-f0-9]{64}$'){throw 'PG17_EXACT_REQUEST_DIGEST_HOLD'}
$final=Get-Content -LiteralPath (Join-Path $output 'poststop-plan-pending-postgres-digest.json') -Raw|ConvertFrom-Json
$final.cas_request.new_v3_config|Add-Member NoteProperty preinvoke_request_sha256 $digest
$finalPath=Join-Path $WindowDirectory 'plan.cas.json'
Write-Json $finalPath $final
Publish $stopFile
Publish $superPath
Publish $cloudFile
Publish $finalPath
Write-Output 'PR701_POSTSTOP_PLAN_BOUND'
