# Productive Paper integration of the existing #99 operator. No new task,
# scheduler, database, writer or credential is created by this module.
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

function Get-V3PaperReleaseInventory([string]$Root) {
 $out=Get-V3OneTimeReleaseArtifactInventory -PackageRoot $Root
 foreach($path in @('tools/v3-one-time-paper-release.ps1',
  'supabase/v3-cas-audit-stage4-followup-release.sql','supabase/v3-cas-audit-stage5-original-epoch-seal-INACTIVE.sql',
  'tools/v3-notebook-cas-audit-original-readonly-witness-INACTIVE.ps1',
  'paper_evaluator/v3_paper_minipc_native_launcher_v1.py',
  'supabase/v3-experimental-paper-atomic-cas-INACTIVE-20261013.sql')){
  $out[$path]=Get-V3ReleaseSha256 (Read-V3ReleaseLocalBytes (Join-Path $Root $path) 1048576)
 }
 return $out
}
function Read-V3PaperPinnedJson([string]$Path,[string]$Sha) {
 $bytes=Read-V3ReleaseLocalBytes $Path
 if($Sha -cnotmatch '^[a-f0-9]{64}$' -or (Get-V3ReleaseSha256 $bytes) -cne $Sha){throw 'V3_PAPER_PINNED_BYTES_HOLD'}
 return ([Text.UTF8Encoding]::new($false,$true).GetString($bytes)|ConvertFrom-Json -ErrorAction Stop)
}
function Assert-V3PaperRuntimeSpec([object]$Spec,[object]$Plan) {
 if([string]$Spec.kind -cne 'V3_NATIVE_RELEASE_RUNTIME_SPEC_V1' -or
    [string]$Spec.series_id -cne [string]$Plan.series_id -or
    [string]$Spec.repo_sha -cne [string]$Plan.repo_sha -or
    [string]$Spec.bundle_sha256 -cne [string]$Plan.bundle_sha256 -or
    [string]$Spec.strategy_sha256 -cne [string]$Plan.strategy_sha256 -or
    [string]$Spec.phase -cnotin @('FIRST_SCANNER_MODEL_P4','FOLLOWUP_6H24H72H','CLOUD_RECEIPT_ACK')){
  throw 'V3_PAPER_RUNTIME_SPEC_BINDING_HOLD'
 }
}
function Write-V3PaperReceipt([string]$Path,[object]$Value) {
 $bytes=[Text.UTF8Encoding]::new($false).GetBytes(($Value|ConvertTo-Json -Depth 24 -Compress))
 $f=[IO.File]::Open($Path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
 try{$f.Write($bytes,0,$bytes.Length);$f.Flush($true)}finally{$f.Dispose()}
}
function Assert-V3PaperDeadline([object]$Context) {
 if([datetimeoffset]::UtcNow -ge $Context.authorization.expires_at){throw 'V3_PAPER_AUTHORIZATION_EXPIRED_FENCE_PRESERVED'}
}
function Read-V3PaperIndependentReceipt([object]$Context,[string]$Json,[string]$Cms) {
 $raw=Read-V3ReleaseLocalBytes $Json
 Assert-V3ReleaseCms $raw (Read-V3ReleaseLocalBytes $Cms 32768) $Context.authorization.claims.bindings.reader_certificate_sha256
 $r=[Text.UTF8Encoding]::new($false,$true).GetString($raw)|ConvertFrom-Json -ErrorAction Stop
 $at=[datetimeoffset]::Parse([string]$r.observed_at_utc,[Globalization.CultureInfo]::InvariantCulture)
 $age=([datetimeoffset]::UtcNow-$at).TotalSeconds
 if($age -lt 0 -or $age -gt 90 -or [string]$r.release_commit -cne $Context.commit -or
    [string]$r.release_id -cne $Context.authorization.claims.release_id -or
    [string]$r.plan_sha256 -cne $Context.authorization.claims.bindings.plan_sha256){throw 'V3_PAPER_INDEPENDENT_CURRENT_RECEIPT_HOLD'}
 return $r
}
function Assert-V3PaperTaskPins([object]$Plan,[switch]$AllowDisabledIntake,[switch]$AllowRunningWriter) {
 $names=@('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait',
  'CryptoMiniPC-V2R4PaperLifecycle','CryptoMiniPC-V2R4PaperCloudSync','CryptoMiniPC-V3PaperSingleWriter')
 if(@($Plan.tasks).Count -ne 5 -or
   (@($Plan.tasks.name|Sort-Object)-join '|') -cne (@($names|Sort-Object)-join '|')){throw 'V3_PAPER_EXACT_EXISTING_TASK_SET_REQUIRED'}
 foreach($row in $Plan.tasks){
  $task=Get-ScheduledTask -TaskName $row.name -TaskPath '\' -ErrorAction Stop
  if(@($task.Actions).Count -ne 1 -or [string]$task.Principal.UserId -notin @('SYSTEM','NT AUTHORITY\SYSTEM','S-1-5-18') -or
     [string]$task.Settings.MultipleInstances -cne 'IgnoreNew'){throw 'V3_PAPER_NATIVE_TASK_SCOPE_HOLD'}
  $xml=Export-ScheduledTask -TaskName $row.name -TaskPath '\'
  $expected=[Text.Encoding]::UTF8.GetString((Read-V3ReleaseLocalBytes $row.xml_path 1048576))
  if((Get-V3ReleaseSha256 ([Text.Encoding]::UTF8.GetBytes($expected))) -cne [string]$row.xml_sha256){throw 'V3_PAPER_TASK_BACKUP_HASH_HOLD'}
  if($xml -cne $expected){
   $isIntake=$row.name -cin @('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait')
   # Reuse the existing XML semantic guard, not a permissive string replace.
   $native=Get-Module v3-one-time-originalhost-release
   $writerMatch=($AllowRunningWriter -and $row.name -ceq 'CryptoMiniPC-V3PaperSingleWriter' -and
    (& $native {param($enabled,$disabled) Test-V3Pr515DisabledOnlyXmlDifference $enabled $disabled} $xml $expected))
   if(-not $writerMatch -and (-not $AllowDisabledIntake -or -not $isIntake -or
      -not (& $native {param($a,$b) Test-V3Pr515DisabledOnlyXmlDifference $a $b} $expected $xml))){
    throw 'V3_PAPER_ORIGINAL_TASK_XML_DRIFT'
   }
  }
  if($row.name -cin @('CryptoMiniPC-V2R4PaperLifecycle','CryptoMiniPC-V2R4PaperCloudSync') -and
     [string]$task.State -cne 'Running'){throw 'V3_PAPER_AFTERCARE_MUST_REMAIN_RUNNING'}
 }
}
function Assert-V3PaperProcesses([object]$Plan,[switch]$Absent) {
 if(@($Plan.intake_processes).Count -lt 2 -or @($Plan.intake_processes).Count -gt 8){throw 'V3_PAPER_ORIGINAL_PROCESS_SET_REQUIRED'}
 $seen=@{}
 foreach($row in $Plan.intake_processes){
  $idValue=[int]$row.pid
  if($idValue -le 0 -or $seen.ContainsKey($idValue)){throw 'V3_PAPER_PROCESS_IDENTITY_HOLD'}
  $seen[$idValue]=$true
  $p=@(Get-CimInstance Win32_Process -Filter "ProcessId=$idValue" -ErrorAction Stop)
  if($Absent){if($p.Count){throw 'V3_PAPER_OLD_PROCESS_REMAINS'};continue}
  if($p.Count -ne 1 -or [string]$p[0].Name -cnotmatch '^pythonw?\.exe$' -or
    ([datetime]$p[0].CreationDate).ToUniversalTime().ToString('o') -cne [string]$row.started_at_utc -or
    (Get-V3ReleaseSha256 ([Text.Encoding]::UTF8.GetBytes([string]$p[0].CommandLine))) -cne [string]$row.command_sha256){
   throw 'V3_PAPER_PROCESS_BIRTH_OR_COMMAND_DRIFT'
  }
 }
 # Also reject orphan/restarted descendants with the exact two original
 # native action signatures. PID absence alone cannot establish quiescence.
 if($Absent){
  foreach($row in @($Plan.tasks|Where-Object {$_.name -cin @('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait')})){
   [xml]$xml=[Text.Encoding]::UTF8.GetString((Read-V3ReleaseLocalBytes $row.xml_path 1048576))
   $signature=[string]$xml.Task.Actions.Exec.Arguments
   if($signature.Length -lt 10){throw 'V3_PAPER_PROCESS_ACTION_AMBIGUOUS'}
   if(@(Get-CimInstance Win32_Process|Where-Object {
      [string]$_.Name -match '^pythonw?\.exe$' -and ([string]$_.CommandLine).Contains($signature)
     }).Count){throw 'V3_PAPER_REPLACEMENT_INTAKE_PROCESS_HOLD'}
  }
 }
}
function Assert-V3PaperFence([object]$Context,[string[]]$Phases) {
 $p=$Context.plan
 $raw=Read-V3ReleaseLocalBytes $Context.fence
 $f=[Text.Encoding]::UTF8.GetString($raw)|ConvertFrom-Json
 if([string]$f.kind -cne 'V3_EXPERIMENTAL_OLD_INTAKE_FENCE_V1' -or
    [string]$f.phase -cnotin $Phases -or
    [string]$f.predecessor_series_id -cne 'PAPER-V2R4-20261009T110135Z' -or
    [string]$f.proposed_successor_series_id -cne [string]$p.series_id -or
    [string]$f.proposed_v3_repo_sha -cne $Context.commit -or
    [string]$f.proposed_v3_bundle_sha256 -cne [string]$p.bundle_sha256 -or
    [string]$f.proposed_v3_strategy_sha256 -cne [string]$p.strategy_sha256 -or
    $f.paper_only -ne $true -or $f.orders_enabled -ne $false -or $f.real_money_actions -ne $false -or
    $f.persistent_until_explicit_owner_release -ne $true -or
    (@($f.task_names|Sort-Object)-join '|') -cne 'CryptoMiniPC-V2R4PaperCandidates|CryptoMiniPC-V2R4PaperWait'){
  throw 'V3_PAPER_ORIGINAL_FENCE_IDENTITY_HOLD'
 }
 $acl=Get-Acl $Context.fence
 if(-not $acl.AreAccessRulesProtected){throw 'V3_PAPER_FENCE_ACL_HOLD'}
 foreach($ace in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])){
  if($ace.AccessControlType -eq 'Allow' -and ([int]$ace.FileSystemRights -band 278) -ne 0 -and
     [string]$ace.IdentityReference.Value -cnotin @('S-1-5-18','S-1-5-32-544')){throw 'V3_PAPER_FENCE_FOREIGN_WRITER_HOLD'}
 }
 return $f
}
function Set-V3PaperFence([object]$Context,[string]$Phase) {
 $f=Assert-V3PaperFence $Context @('ARMED','QUIESCED','CLOUD_COMMITTED')
 Assert-V3PaperDeadline $Context
 $f.phase=$Phase
 if($Phase -eq 'CLOUD_COMMITTED'){$f|Add-Member -NotePropertyName successor_task_name -NotePropertyValue 'CryptoMiniPC-V3PaperSingleWriter' -Force}
 $tmp=$Context.fence+'.'+[guid]::NewGuid().ToString('N')+'.tmp'
 Write-V3PaperReceipt $tmp $f
 Set-Acl $tmp (Get-Acl $Context.fence)
 [IO.File]::Replace($tmp,$Context.fence,($Context.fence+'.'+[guid]::NewGuid().ToString('N')+'.bak'),$true)
}
function Get-V3PaperCasCallSql([object]$Request) {
 $fields=@('expected_old_series_id','expected_old_release_sha','expected_old_strategy_sha256','expected_old_runtime_sha256',
  'expected_old_candidate_count','expected_old_trade_count','expected_old_last_outcome_updated_at','expected_old_last_trade_updated_at',
  'proposed_v3_series_id','proposed_v3_test_id','proposed_v3_revision','cutover_at_utc','new_v3_config',
  'reviewed_new_repo_sha','reviewed_new_bundle_sha256','reviewed_new_strategy_sha256')
 if(@($Request.PSObject.Properties).Count -ne 16 -or @($Request.PSObject.Properties.Name|Where-Object {$_ -cnotin $fields}).Count){throw 'V3_PAPER_CAS_EXACT_16_ARGUMENTS_REQUIRED'}
 $types=@('text','text','text','text','bigint','bigint','timestamptz','timestamptz','text','text','text','timestamptz','jsonb','text','text','text')
 $argsList=@()
 for($i=0;$i -lt 16;$i++){
  $value=$Request.($fields[$i])
  if($null -eq $value){$argsList+=('NULL::'+$types[$i]);continue}
  $wire=if($types[$i] -eq 'jsonb'){$value|ConvertTo-Json -Depth 24 -Compress}else{[string]$value}
  $encoded=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($wire))
  $argsList+=("convert_from(decode('$encoded','base64'),'UTF8')::"+$types[$i])
 }
 return ('SELECT public.rotate_v2r4_to_v3_experimental_paper('+($argsList -join ',')+');')
}
function Assert-V3PaperEpochPlan([object]$Context,[hashtable]$Inventory) {
 $p=$Context.plan
 $e=$p.cas_epoch
 if([string]$e.epoch_id -cnotmatch '^V3CAS-AUDIT-[a-f0-9]{32}$' -or
    [string]$e.source_sha256 -cne $Inventory['supabase/v3-experimental-paper-atomic-cas-INACTIVE-20261013.sql'] -or
    [string]$e.fence_sha256 -cnotmatch '^[a-f0-9]{64}$' -or
    [string]$e.caller_acl_sha256 -cnotmatch '^[a-f0-9]{64}$'){throw 'V3_PAPER_FOLLOWUP_PLAN_EPOCH_PINS_HOLD'}
 $native=Get-Module v3-one-time-originalhost-release
 $marker=& $native {param($plan) New-V3Pr515PreparedArmedMarker $plan.series_id $plan.repo_sha $plan.bundle_sha256 $plan.strategy_sha256} $p
 $bytes=[Text.UTF8Encoding]::new($false).GetBytes(($marker|ConvertTo-Json -Depth 24 -Compress))
 if((Get-V3ReleaseSha256 $bytes) -cne [string]$e.fence_sha256){throw 'V3_PAPER_FOLLOWUP_PREPARED_FENCE_DRIFT'}
 return $e
}
function Assert-V3PaperEpochReceipt([object]$Receipt,[object]$Epoch) {
 if([string]$Receipt.kind -cne 'V3_PAPER_RELEASE_EPOCH_READER_V1'){throw 'V3_PAPER_FOLLOWUP_READER_KIND_HOLD'}
 foreach($field in @('epoch_id','source_sha256','fence_sha256','caller_acl_sha256')){
  if([string]$Receipt.$field -cne [string]$Epoch.$field){throw 'V3_PAPER_FOLLOWUP_READER_EPOCH_DRIFT'}
 }
}
function Get-V3PaperEpochSealSql([string]$Source,[object]$Context,[object]$Epoch,[object]$Receipt,[string]$StopSha) {
 $lock="RAISE EXCEPTION 'V3_STAGE5_EPOCH_SEAL_SOURCE_INACTIVE_APPROVAL_REQUIRED';"
 if(([regex]::Matches($Source,[regex]::Escape($lock))).Count -ne 1){throw 'V3_PAPER_SEAL_SOURCE_LOCK_DRIFT'}
 $config=$Context.plan.cas_request.new_v3_config
 foreach($key in @('preinvoke_epoch_id','preinvoke_intent_id','preinvoke_request_sha256',
    'preinvoke_source_sha256','preinvoke_fence_sha256','preinvoke_inhibit_receipt_sha256')){
  if([string]$Receipt.$key -cne [string]$config.$key){throw 'V3_PAPER_SEAL_SIGNED_REQUEST_DRIFT'}
 }
 $values=[ordered]@{
  EPOCH_ID=[string]$Epoch.epoch_id;INTENT_ID=[string]$Receipt.preinvoke_intent_id
  REQUEST_SHA256=[string]$Receipt.preinvoke_request_sha256;SOURCE_SHA256=[string]$Epoch.source_sha256
  FENCE_SHA256=[string]$Epoch.fence_sha256;CALLER_ACL_SHA256=[string]$Epoch.caller_acl_sha256
 }
 foreach($key in $values.Keys){
  $pattern=@{EPOCH_ID='^V3CAS-AUDIT-[a-f0-9]{32}$';INTENT_ID='^[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}$'}[$key]
  if(-not $pattern){$pattern='^[a-f0-9]{64}$'}
  if($values[$key] -cnotmatch $pattern){throw 'V3_PAPER_SEAL_PARAMETER_HOLD'}
  $Source=$Source.Replace('__'+$key+'__',$values[$key])
 }
 if($StopSha -cnotmatch '^[a-f0-9]{64}$' -or $Context.commit -cnotmatch '^[a-f0-9]{40}$'){throw 'V3_PAPER_SEAL_PINS_HOLD'}
 $deadline=$Context.authorization.expires_at.ToUniversalTime().ToString('o')
 $gate="IF session_user <> 'postgres' OR clock_timestamp() >= '$deadline'::timestamptz THEN RAISE EXCEPTION 'V3_PAPER_SEAL_AUTHORIZATION_HOLD'; END IF; " +
  "PERFORM set_config('v3_stage5.followup','true',true),set_config('v3_stage5.commit','$($Context.commit)',true),set_config('v3_stage5.stop_sha256','$StopSha',true);"
 return $Source.Replace($lock,$gate)
}
function Get-V3PaperCasInstallSql([string]$Source,[object]$Context,[object]$Epoch) {
 # Deterministic release of the existing original, never a copied CAS body.
 # Caller has already verified the independent INSTALL scope and package lease.
 $lock="raise exception 'V3_CAS_INSTALL_SOURCE_INACTIVE_APPROVAL_REQUIRED';"
 if(([regex]::Matches($Source,[regex]::Escape($lock))).Count -ne 1){throw 'V3_PAPER_CAS_ORIGINAL_INSTALL_SEAM_DRIFT'}
 $deadline=$Context.authorization.expires_at.ToUniversalTime().ToString('o')
 $gate="if session_user <> 'postgres' or clock_timestamp() >= '$deadline'::timestamptz then raise exception 'V3_PAPER_INSTALL_AUTHORIZATION_HOLD'; end if;"
 $membership=@'
DO $v3_actor_bind$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='v3_cas_executor_actor'
    AND NOT rolcanlogin AND rolconnlimit=0 AND NOT rolsuper AND NOT rolcreaterole AND NOT rolcreatedb
    AND NOT rolbypassrls AND NOT rolinherit AND NOT rolreplication)
 OR EXISTS (SELECT 1 FROM pg_auth_members WHERE member='v3_cas_executor_actor'::regrole)
 OR EXISTS (SELECT 1 FROM pg_stat_activity WHERE usename IN ('v3_cas_executor_actor','v3_cas_executor'))
 THEN RAISE EXCEPTION 'V3_PAPER_EXECUTOR_ACTOR_SCOPE_HOLD'; END IF;
END $v3_actor_bind$;
GRANT v3_cas_executor TO v3_cas_executor_actor WITH INHERIT FALSE, SET TRUE, ADMIN FALSE;
'@
 $inhibit=''
 $transaction='BEGIN;'
 if($null -ne $Epoch){
  $transaction='BEGIN ISOLATION LEVEL SERIALIZABLE;'
  # The values were validated against the exact signed Originalhost plan.
  $inhibit=@"
DO `$v3_install_inhibit`$
BEGIN
 PERFORM 1 FROM v3_cas_audit.epoch_v1 e
 JOIN v3_cas_audit.executor_inhibit_v1 i ON i.epoch_id=e.epoch_id
 WHERE e.epoch_id='$($Epoch.epoch_id)' AND e.paper_release_commit='$($Context.commit)'
 AND e.source_sha256='$($Epoch.source_sha256)' AND e.original_fence_sha256='$($Epoch.fence_sha256)'
 AND e.approved_caller_acl_sha256='$($Epoch.caller_acl_sha256)'
 AND i.source_sha256=e.source_sha256 AND i.original_fence_sha256=e.original_fence_sha256
 AND i.caller_acl_sha256=e.approved_caller_acl_sha256 AND i.issuer_id='v3_cas_inhibit_issuer_actor'
 AND i.state='INHIBITED' AND i.native_stop_at_utc IS NULL AND i.acknowledged_at_utc IS NULL
 AND i.receipt_sha256 IS NULL AND NOT e.sealed AND e.next_ordinal=1;
 IF NOT FOUND OR EXISTS (SELECT FROM v3_cas_audit.prepared_fence_abort_v1 WHERE epoch_id='$($Epoch.epoch_id)')
  OR EXISTS (SELECT FROM v3_cas_audit.intent_v1) OR EXISTS (SELECT FROM v3_cas_audit.attempt_v1)
  OR (SELECT count(*) FROM public.paper_series WHERE status='active') <> 1
  OR NOT EXISTS (SELECT FROM public.paper_series WHERE status='active' AND series_id='PAPER-V2R4-20261009T110135Z')
 THEN RAISE EXCEPTION 'V3_PAPER_INSTALL_CURRENT_INHIBIT_HOLD'; END IF;
END `$v3_install_inhibit`$;
"@
 }
 return $transaction+"`n"+$inhibit+"`n"+$Source.Replace($lock,$gate)+"`n"+$membership+"`nCOMMIT;"
}
function Open-V3PaperIntakePair {
 $native=Get-Module v3-one-time-originalhost-release
 return (& $native {Open-V3Pr661DisabledIntakeLeasePairSOURCE_ONLY @('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait')})
}
function Assert-V3PaperOriginalHost([string]$Mode,[string]$PackageRoot,[string]$ExpectedReleaseCommit) {
 if($ExpectedReleaseCommit -cnotmatch '^[a-f0-9]{40}$'){throw 'V3_PAPER_RELEASE_COMMIT_REQUIRED'}
 if($env:OS -cne 'Windows_NT' -or $env:COMPUTERNAME -cne 'MINI-PC' -or $env:GITHUB_ACTIONS -eq 'true'){
  throw 'V3_PAPER_ORIGINALHOST_REQUIRED'
 }
 if($Mode -eq 'PaperHostReadback'){
  if([Security.Principal.WindowsIdentity]::GetCurrent().User.Value -cne 'S-1-5-18'){throw 'V3_PAPER_NATIVE_SYSTEM_TASK_REQUIRED'}
 }else{Assert-V3OriginalInteractiveOwner}
 if([IO.Path]::GetFullPath($PackageRoot).TrimEnd('\') -cne ('C:\Users\ADMIN\Trading\Staging\V3Paper-INACTIVE-'+$ExpectedReleaseCommit.Substring(0,12))){throw 'V3_PAPER_PINNED_STAGE_REQUIRED'}
}
function Get-V3PaperNativeActionPrefix([string]$PackageRoot) {
 $launcher=Join-Path $PackageRoot 'paper_evaluator\v3_paper_minipc_native_launcher_v1.py'
 return ('-I -B "'+$launcher+'" --released-one-shot')
}
function Get-V3PaperStateBase([string]$ReleaseId) {
 return ('C:\Users\ADMIN\Trading\State\'+$ReleaseId)
}
function Get-V3PaperFencePath {return 'C:\Users\ADMIN\Trading\State\v3-experimental-paper-old-intake-fence.json'}
function Invoke-V3OneTimePaperRelease {
 [CmdletBinding()]
 param([string]$Mode,[string]$PackageRoot,[string]$ApprovalJson,[string]$ApprovalCms,
 [string]$AuthorityAdmissionJson,[string]$ExpectedAuthorityAdmissionSha256,[string]$ExpectedReleaseCommit,
 [string]$PaperPlanJson,[string]$RuntimeSpecJson,[string]$HostReceiptJson,[string]$HostReceiptCms,
 [Security.SecureString]$PostgresPassword,[string]$CaFile)
 $scope=@{PaperOpenEpoch='CLOUD_STAGE4_EPOCH_OPEN';PaperSealEpoch='CLOUD_STAGE5_EPOCH_SEAL';PaperPrepare='V3_PAPER_PREPARE';PaperStop='V3_PAPER_STOP';PaperCas='V3_PAPER_CAS';InstallPaperCas='V3_PAPER_CAS_INSTALL';
  PaperActivate='V3_PAPER_ACTIVATE';PaperRollback='V3_PAPER_ROLLBACK';PaperHostReadback='V3_PAPER_RUNTIME';PaperResume='V3_PAPER_RESUME'}[$Mode]
 if(-not $scope){throw 'V3_PAPER_UNKNOWN_MODE'}
 Assert-V3PaperOriginalHost $Mode $PackageRoot $ExpectedReleaseCommit
 $inventory=Get-V3PaperReleaseInventory $PackageRoot
 $leases=Open-V3ReleasePackageReadLease $PackageRoot $inventory
 $mutex=$null;$held=$false;$intakePair=$null
 try{
  $pin=Assert-V3ReleaseAuthorityAdmission (Read-V3ReleaseLocalBytes $AuthorityAdmissionJson) $ExpectedAuthorityAdmissionSha256 $ExpectedReleaseCommit
  $auth=Assert-V3OneTimeReleaseAuthorization -Payload (Read-V3ReleaseLocalBytes $ApprovalJson) -Cms (Read-V3ReleaseLocalBytes $ApprovalCms 32768) `
   -ReviewedAuthorityCertificateSha256 $pin -Scope $scope -ExpectedReleaseCommit $ExpectedReleaseCommit -ExpectedArtifacts $inventory
  $b=$auth.claims.bindings
  if([string]$b.reader_certificate_sha256 -cnotmatch '^[a-f0-9]{64}$'){throw 'V3_PAPER_INDEPENDENT_READER_PIN_REQUIRED'}
  $ctx=[pscustomobject]@{authorization=$auth;commit=$ExpectedReleaseCommit;plan=$null;
   fence=(Get-V3PaperFencePath)}
  $receipt=if($Mode -ne 'PaperOpenEpoch'){Read-V3PaperIndependentReceipt $ctx $HostReceiptJson $HostReceiptCms}
  if($Mode -eq 'PaperHostReadback'){
   $spec=Read-V3PaperPinnedJson $RuntimeSpecJson $b.runtime_spec_sha256
   $plan=Read-V3PaperPinnedJson $spec.paper_plan $b.plan_sha256;$ctx.plan=$plan
   Assert-V3PaperRuntimeSpec $spec $plan
   if([string]$receipt.kind -cne 'V3_NATIVE_ONE_OWNER_POST_CAS_ORIGINALHOST_READBACK_V1' -or
      [string]$receipt.release_repo_sha -cne $ExpectedReleaseCommit){throw 'V3_PAPER_HOST_RECEIPT_KIND_HOLD'}
   Import-Module (Join-Path $PSScriptRoot 'v3-one-time-originalhost-release.psm1') -Force
   Import-Module (Join-Path $PSScriptRoot 'v3-one-time-release-authorization.psm1') -Scope Local
   Assert-V3PaperTaskPins $plan -AllowDisabledIntake -AllowRunningWriter
   Assert-V3PaperProcesses $plan -Absent
   $null=Assert-V3PaperFence $ctx @('CLOUD_COMMITTED')
   # Actual independently executing PowerShell observer, not caller JSON.
   # It observes its invoking Python PID/birth only AFTER the Task starts,
   # avoiding a demand to sign a not-yet-existing process in advance.
   $wire=@(& (Join-Path $PSScriptRoot 'check-minipc-v3-physical-writer-readiness.ps1') -TradingRoot 'C:\Users\ADMIN\Trading')
   $observed=($wire -join "`n")|ConvertFrom-Json
   $local=$observed.physical_v3_postcas_local_inventory
   if([string]$local.native_task_state -cne 'Running' -or
      $local.native_task_has_one_action -ne $true -or $local.native_task_principal_system -ne $true -or
      $local.native_python_parent_matches_task_action_hint -ne $true -or
      $local.native_powershell_process_token_is_system -ne $true -or
      $local.old_intake_tasks_disabled -ne $true -or $local.protected_old_aftercare_running -ne $true -or
      [string]$local.native_task_action_sha256 -cne [string]$receipt.native_task_action_sha256 -or
      [string]$local.native_task_launcher_file_sha256 -cne [string]$receipt.native_task_launcher_file_sha256){
    throw 'V3_PAPER_ACTUAL_NATIVE_TASK_PROCESS_SOURCE_HOLD'
   }
   $super=[Text.Encoding]::UTF8.GetString((Read-V3ReleaseLocalBytes 'C:\Users\ADMIN\Trading\State\minipc-runtime-supervisor.json' 131072))|ConvertFrom-Json
   $age=([datetimeoffset]::UtcNow-[datetimeoffset]::Parse([string]$super.checked_at_utc)).TotalSeconds
   if($age -lt 0 -or $age -gt 150 -or [string]$super.v3_paper_old_intake_fence.mode -cne 'CLOUD_COMMITTED'){
    throw 'V3_PAPER_CURRENT_SUPERVISOR_NO_REARM_ACK_REQUIRED'
   }
   # Only live observations replace these fields. Six-proof, maintenance,
   # exact compiled bundle/strategy, issuance and independent CAS facts stay
   # the signed original authority's claims and are checked by Python too.
   foreach($key in @('native_python_parent_pid','native_python_parent_started_at_utc')){
    $receipt|Add-Member -NotePropertyName $key -NotePropertyValue $local.$key -Force
   }
   $receipt|Add-Member -NotePropertyName observed_at_utc -NotePropertyValue ([datetimeoffset]::UtcNow.ToString('o')) -Force
   return $receipt
  }
  $plan=Read-V3PaperPinnedJson $PaperPlanJson $b.plan_sha256;$ctx.plan=$plan
  if([string]$plan.kind -cne 'V3_ONE_TIME_PAPER_RELEASE_PLAN_V1' -or [string]$plan.repo_sha -cne $ExpectedReleaseCommit -or
     [string]$plan.series_id -cnotmatch '^PAPER-V3-[0-9]{8}T[0-9]{6}Z$' -or
     [string]$plan.bundle_sha256 -cnotmatch '^[a-f0-9]{64}$' -or [string]$plan.strategy_sha256 -cnotmatch '^[a-f0-9]{64}$'){
   throw 'V3_PAPER_PLAN_IDENTITY_HOLD'
  }
  Import-Module (Join-Path $PSScriptRoot 'v3-one-time-originalhost-release.psm1') -Force
  Import-Module (Join-Path $PSScriptRoot 'v3-one-time-release-authorization.psm1') -Scope Local
  # The imported existing module reloads authorization; re-importing it must
  # not discard the already verified original payload/expiry held in $ctx.
  $mutex=[Threading.Mutex]::new($false,'Global\V3Pr661OriginalhostOneShotOperator')
  try{$held=$mutex.WaitOne(0)}catch [Threading.AbandonedMutexException]{throw 'V3_PAPER_ABANDONED_OPERATOR_HOLD'}
  if(-not $held){throw 'V3_PAPER_CONCURRENT_OPERATOR_HOLD'}
  $base=Get-V3PaperStateBase $auth.claims.release_id
  $casLatch=$base+'.cas.attempted.json'
  Assert-V3PaperDeadline $ctx
  Assert-V3PaperTaskPins $plan -AllowDisabledIntake
  if($Mode -eq 'PaperResume'){
   # Read-only recovery never redispatches STOP/CAS/activation. A fresh signed
   # independent result permits the next separately authorized phase only.
   return [pscustomobject]@{kind='V3_PAPER_RESUME_READBACK_V1';cas_attempted=[IO.File]::Exists($casLatch);
    independent_state=$receipt.state;automatic_retry=$false;paper_operational_claimed=$false}
  }
  if($Mode -in @('PaperOpenEpoch','PaperSealEpoch','InstallPaperCas','PaperPrepare','PaperStop','PaperCas')){
   $epoch=Assert-V3PaperEpochPlan $ctx $inventory
   if($Mode -ne 'PaperOpenEpoch'){Assert-V3PaperEpochReceipt $receipt $epoch}
  }
  if($Mode -eq 'PaperOpenEpoch'){
   if($null -eq $PostgresPassword){throw 'V3_PAPER_EXISTING_ADMIN_CREDENTIAL_REQUIRED'}
   if([IO.File]::Exists($ctx.fence) -or [IO.File]::Exists($casLatch) -or
      [string](Get-ScheduledTask -TaskName 'CryptoMiniPC-V3PaperSingleWriter' -TaskPath '\').State -cne 'Disabled'){
    throw 'V3_PAPER_OPEN_EPOCH_EXISTING_FENCE_ATTEMPT_OR_WRITER_HOLD'
   }
   $sql=[Text.Encoding]::UTF8.GetString((Read-V3ReleaseLocalBytes (Join-Path $PackageRoot 'supabase/v3-cas-audit-stage4-followup-release.sql') 1048576))
   $settings=@{
    scope='CLOUD_STAGE4_EPOCH_OPEN';commit=$ctx.commit;approval_sha256=$auth.approval_sha256
    epoch_id=[string]$epoch.epoch_id;source_sha256=[string]$epoch.source_sha256
    fence_sha256=[string]$epoch.fence_sha256;caller_acl_sha256=[string]$epoch.caller_acl_sha256
    expires_at=$auth.expires_at.ToUniversalTime().ToString('o')
   }
   $prefix=@(foreach($key in $settings.Keys){"SELECT set_config('v3_followup.$key','$($settings[$key])',false);"}) -join "`n"
   Write-V3PaperReceipt ($base+'.epoch.attempted.json') @{approval_sha256=$auth.approval_sha256}
   $null=Invoke-V3ReleasePg -Sql ($prefix+"`n"+$sql) -Password $PostgresPassword -Ca $CaFile
   return @{kind='V3_PAPER_EPOCH_OPEN_RETURNED_INDEPENDENT_ISSUER_AND_READBACK_REQUIRED';epoch_id=$epoch.epoch_id}
  }
  if($Mode -eq 'InstallPaperCas'){
   if([string]$receipt.state -cne 'INSTALL_APPROVED_OLD_ONLY_NO_ATTEMPTS'){throw 'V3_PAPER_CAS_INSTALL_READER_HOLD'}
   $source=[Text.Encoding]::UTF8.GetString((Read-V3ReleaseLocalBytes (Join-Path $PackageRoot 'supabase/v3-experimental-paper-atomic-cas-INACTIVE-20261013.sql') 1048576))
   if($null -eq $PostgresPassword){throw 'V3_PAPER_EXISTING_ADMIN_CREDENTIAL_REQUIRED'}
   $sql=Get-V3PaperCasInstallSql $source $ctx -Epoch $epoch
   Write-V3PaperReceipt ($base+'.install.attempted.json') @{approval_sha256=$auth.approval_sha256}
   $null=Invoke-V3ReleasePg -Sql $sql -Password $PostgresPassword -Ca $CaFile
   return @{kind='V3_PAPER_CAS_INSTALL_RETURNED_INDEPENDENT_READBACK_REQUIRED';paper_activated=$false}
  }
  if($Mode -eq 'PaperPrepare'){
   if([string]$receipt.state -cne 'PRESTOP_INHIBITED_OLD_ONLY_NO_ATTEMPTS' -or
      [IO.File]::Exists($ctx.fence) -or [IO.File]::Exists($casLatch)){
    throw 'V3_PAPER_PREPARE_EXISTING_FENCE_OR_UNSAFE_READER_HOLD'
   }
   $spec=Read-V3PaperPinnedJson $RuntimeSpecJson $b.runtime_spec_sha256
   Assert-V3PaperRuntimeSpec $spec $plan
   $r=$plan.runtime_bootstrap
   $pairs=[ordered]@{'runtime-spec'=$RuntimeSpecJson;'approval-json'=$r.approval_json;
    'approval-cms'=$r.approval_cms;'admission-json'=$r.admission_json;
    'admission-sha256'=$ExpectedAuthorityAdmissionSha256;'expected-source-sha'=$ExpectedReleaseCommit;
    'host-receipt'=$r.host_receipt;'host-cms'=$r.host_cms}
   $arguments=Get-V3PaperNativeActionPrefix $PackageRoot
   foreach($key in $pairs.Keys){
    $value=[string]$pairs[$key]
    if($key -notin @('admission-sha256','expected-source-sha')){
     $null=Read-V3ReleaseLocalBytes $value
     if(-not $value.StartsWith('C:\Users\ADMIN\Trading\',[StringComparison]::OrdinalIgnoreCase)){
      throw 'V3_PAPER_BOOTSTRAP_LOCAL_TRADING_PATH_REQUIRED'
     }
    }
    if($value.Contains('"') -or $value.Contains("`r") -or $value.Contains("`n")){throw 'V3_PAPER_BOOTSTRAP_ARGUMENT_HOLD'}
    $arguments+=' --'+$key+' "'+$value+'"'
   }
   $task=Get-ScheduledTask -TaskName 'CryptoMiniPC-V3PaperSingleWriter'
   if([string]$task.State -cne 'Disabled'){throw 'V3_PAPER_PREPARE_WRITER_MUST_BE_DISABLED'}
   Write-V3PaperReceipt ($base+'.prepare.attempted.json') @{approval_sha256=$auth.approval_sha256}
   $action=New-ScheduledTaskAction -Execute 'C:\Users\ADMIN\Trading\Runtime\kraken-eur-scanner-venv\Scripts\python.exe' -Argument $arguments -WorkingDirectory $PackageRoot
   Set-ScheduledTask -TaskName 'CryptoMiniPC-V3PaperSingleWriter' -Action $action|Out-Null
   if([string](Get-ScheduledTask -TaskName 'CryptoMiniPC-V3PaperSingleWriter').State -cne 'Disabled'){
    throw 'V3_PAPER_PREPARE_DISABLED_ACK_REQUIRED'
   }
   $taskXml=Export-ScheduledTask -TaskName 'CryptoMiniPC-V3PaperSingleWriter'
   $xmlPath=$base+'.v3-disabled.xml'
   $xmlBytes=[Text.Encoding]::UTF8.GetBytes($taskXml)
   $xmlFile=[IO.File]::Open($xmlPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
   try{$xmlFile.Write($xmlBytes,0,$xmlBytes.Length);$xmlFile.Flush($true)}finally{$xmlFile.Dispose()}
   $native=Get-Module v3-one-time-originalhost-release
   $marker=& $native {param($sid,$sha,$bundle,$strategy) New-V3Pr515PreparedArmedMarker $sid $sha $bundle $strategy} $plan.series_id $ctx.commit $plan.bundle_sha256 $plan.strategy_sha256
   Write-V3PaperReceipt $ctx.fence $marker
   $acl=Get-Acl $ctx.fence
   $acl.SetAccessRuleProtection($true,$false)
   foreach($sid in @('S-1-5-18','S-1-5-32-544')){
    $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($sid),'FullControl','Allow'))
   }
   Set-Acl $ctx.fence $acl
   return @{kind='V3_PAPER_DISABLED_BOOTSTRAP_AND_ARMED_FENCE_PREPARED';writer_started=$false;
    v3_xml_path=$xmlPath;v3_xml_sha256=(Get-V3ReleaseSha256 $xmlBytes)}
  }
  $f=Assert-V3PaperFence $ctx @('ARMED','QUIESCED','CLOUD_COMMITTED')
  if($Mode -eq 'PaperStop'){
   if([string]$f.phase -cne 'ARMED' -or [string]$receipt.state -cne 'PRESTOP_INHIBITED_OLD_ONLY_NO_ATTEMPTS'){
    throw 'V3_PAPER_PRESTOP_INDEPENDENT_INHIBIT_REQUIRED'
   }
   if((Get-V3ReleaseSha256 (Read-V3ReleaseLocalBytes $ctx.fence)) -cne [string]$epoch.fence_sha256){
    throw 'V3_PAPER_PRESTOP_FENCE_EPOCH_DRIFT'
   }
   # The installed CAS uses the timestamp in the issued series ID and
   # rejects it once it is older than ten minutes. Detect that before STOP.
   $seriesTime=[datetimeoffset]::ParseExact($plan.series_id.Substring('PAPER-V3-'.Length),
    "yyyyMMdd'T'HHmmss'Z'",[Globalization.CultureInfo]::InvariantCulture,[Globalization.DateTimeStyles]::AssumeUniversal)
   if($seriesTime -lt [datetimeoffset]::UtcNow.AddMinutes(-10)){throw 'V3_PAPER_STOP_SUCCESSOR_SERIES_EXPIRED'}
   Assert-V3PaperProcesses $plan
   Write-V3PaperReceipt ($base+'.stop.attempted.json') @{approval_sha256=$auth.approval_sha256}
   $intakes=@('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait')
   foreach($name in $intakes){
    Assert-V3PaperDeadline $ctx
    Disable-ScheduledTask -TaskName $name -TaskPath '\'|Out-Null
   }
   $intakePair=Open-V3PaperIntakePair
   Assert-V3PaperTaskPins $plan -AllowDisabledIntake
   foreach($name in $intakes){
    Assert-V3PaperDeadline $ctx
    Stop-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction Stop
   }
   # Wait only for the already requested scheduler stop; never redispatch it.
   # Orphan/replacement processes keep the fence and eventually HOLD.
   $stopDeadline=[datetimeoffset]::UtcNow.AddSeconds(30)
   do{
    Assert-V3PaperDeadline $ctx
    $quiet=$false
    try{Assert-V3PaperProcesses $plan -Absent;$quiet=$true}catch{
     if([datetimeoffset]::UtcNow -ge $stopDeadline){throw}
     Start-Sleep -Milliseconds 500
    }
   }while(-not $quiet)
   Assert-V3PaperTaskPins $plan -AllowDisabledIntake
   Set-V3PaperFence $ctx 'QUIESCED'
   $stopPath=$base+'.stop.completed.json'
   Write-V3PaperReceipt $stopPath @{state='QUIESCED';approval_sha256=$auth.approval_sha256;
     observed_at_utc=[datetimeoffset]::UtcNow.ToString('o')}
   return @{kind='V3_PAPER_STOP_QUIESCED_LOCAL_ACK';independent_reader_required=$true;stop_receipt_path=$stopPath}
  }
  Assert-V3PaperProcesses $plan -Absent
  if($Mode -in @('PaperCas','PaperActivate')){
   $intakePair=Open-V3PaperIntakePair
   Assert-V3PaperTaskPins $plan -AllowDisabledIntake
  }
  foreach($name in @('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait')){
   if([string](Get-ScheduledTask -TaskName $name).State -cne 'Disabled'){throw 'V3_PAPER_OLD_INTAKE_NOT_DISABLED'}
  }
  if($Mode -eq 'PaperSealEpoch'){
   if([string]$f.phase -cne 'QUIESCED' -or [string]$receipt.state -cne 'STOP_CONFIRMED_INTENT_COMMITTED'){
    throw 'V3_PAPER_FOLLOWUP_SEAL_READER_OR_FENCE_HOLD'
   }
   if($null -eq $PostgresPassword){throw 'V3_PAPER_EXISTING_ADMIN_CREDENTIAL_REQUIRED'}
   $stop=Read-V3ReleaseLocalBytes ($base+'.stop.completed.json')
   $stopSha=Get-V3ReleaseSha256 $stop
   if([string](Read-V3ReleaseJson $stop).state -cne 'QUIESCED' -or
      [string]$receipt.preinvoke_inhibit_receipt_sha256 -cne $stopSha){throw 'V3_PAPER_FOLLOWUP_SEAL_ORIGINAL_STOP_DRIFT'}
   $sql=[Text.Encoding]::UTF8.GetString((Read-V3ReleaseLocalBytes (Join-Path $PackageRoot 'supabase/v3-cas-audit-stage5-original-epoch-seal-INACTIVE.sql') 1048576))
   $sql=Get-V3PaperEpochSealSql $sql $ctx $epoch $receipt $stopSha
   $intakePair=Open-V3PaperIntakePair
   Assert-V3PaperTaskPins $plan -AllowDisabledIntake
   Assert-V3PaperDeadline $ctx
   Write-V3PaperReceipt ($base+'.seal.attempted.json') @{approval_sha256=$auth.approval_sha256}
   $null=Invoke-V3ReleasePg -Sql $sql -Password $PostgresPassword -Ca $CaFile
   return @{kind='V3_PAPER_EPOCH_SEAL_RETURNED_INDEPENDENT_READBACK_REQUIRED';epoch_id=$epoch.epoch_id}
  }
  if($Mode -eq 'PaperCas'){
   if([string]$f.phase -cne 'QUIESCED' -or [string]$receipt.state -cne 'SEALED_INTENT_INHIBIT_STOP_CONFIRMED'){
    throw 'V3_PAPER_PRECAS_INDEPENDENT_READER_HOLD'
   }
   $request=$plan.cas_request
   if([string]$request.proposed_v3_series_id -cne [string]$plan.series_id -or
      [string]$request.reviewed_new_repo_sha -cne $ctx.commit -or
      [string]$request.reviewed_new_bundle_sha256 -cne [string]$plan.bundle_sha256 -or
      [string]$request.reviewed_new_strategy_sha256 -cne [string]$plan.strategy_sha256 -or
      [string]$request.expected_old_series_id -cne 'PAPER-V2R4-20261009T110135Z'){throw 'V3_PAPER_CAS_RUNTIME_BINDING_HOLD'}
   foreach($key in @('preinvoke_epoch_id','preinvoke_intent_id','preinvoke_request_sha256','preinvoke_source_sha256','preinvoke_fence_sha256','preinvoke_inhibit_receipt_sha256')){
    if([string]$receipt.$key -cne [string]$request.new_v3_config.$key){throw 'V3_PAPER_CAS_INDEPENDENT_REQUEST_DRIFT'}
   }
   $call=Get-V3PaperCasCallSql $request
   $config=$request.new_v3_config
   foreach($key in @('preinvoke_request_sha256','preinvoke_source_sha256','preinvoke_fence_sha256')){
    if([string]$config.$key -cnotmatch '^[a-f0-9]{64}$'){throw 'V3_PAPER_CAS_AUDIT_PIN_HOLD'}
   }
   if([string]$config.preinvoke_epoch_id -cnotmatch '^V3CAS-AUDIT-[a-f0-9]{32}$' -or
      [string]$config.preinvoke_intent_id -cnotmatch '^[a-f0-9-]{36}$'){throw 'V3_PAPER_CAS_AUDIT_ID_HOLD'}
   if($null -eq $PostgresPassword){throw 'V3_PAPER_EXISTING_EXECUTOR_CREDENTIAL_REQUIRED'}
   Write-V3PaperReceipt $casLatch @{state='DISPATCH_UNKNOWN';approval_sha256=$auth.approval_sha256}
   # Deliberately two commits: UNKNOWN is durable even if rotation rolls back.
   $unknown="SELECT v3_cas_audit.append_dispatch_unknown_v1('$($config.preinvoke_epoch_id)','$($config.preinvoke_intent_id)','$($config.preinvoke_request_sha256)','$($config.preinvoke_source_sha256)','$($config.preinvoke_fence_sha256)');"
   $null=Invoke-V3ReleasePg -Sql $unknown -Password $PostgresPassword -Ca $CaFile -Actor v3_cas_executor_actor
   Assert-V3PaperDeadline $ctx
   $remaining=[math]::Floor(($auth.expires_at-[datetimeoffset]::UtcNow).TotalMilliseconds)
   if($remaining -lt 1 -or $remaining -gt 900000){throw 'V3_PAPER_CAS_DEADLINE_HOLD'}
   $result=Invoke-V3ReleasePg -Sql ("BEGIN; SET LOCAL statement_timeout = '$($remaining)ms'; SET LOCAL ROLE v3_cas_executor;`n"+$call+"`nCOMMIT;") -Password $PostgresPassword -Ca $CaFile -Actor v3_cas_executor_actor
   $row=$result|ConvertFrom-Json
   if($row.ok -ne $true -or [string]$row.kind -cne 'V3_EXPERIMENTAL_PAPER_ATOMIC_CAS_V1' -or
      [string]$row.successor_series_id -cne [string]$plan.series_id){throw 'V3_PAPER_CAS_RESULT_UNKNOWN_NO_RETRY'}
   Write-V3PaperReceipt ($base+'.cas.returned.json') $row
   return @{kind='V3_PAPER_CAS_RETURNED_INDEPENDENT_COMMIT_READER_REQUIRED';retry_authorized=$false}
  }
  if($Mode -eq 'PaperActivate'){
   if(-not [IO.File]::Exists($casLatch) -or [string]$receipt.state -cne 'CAS_COMMITTED_EXACT_SUCCESSOR_SINGLE_ACTIVE' -or
      [string]$receipt.successor_series_id -cne [string]$plan.series_id -or
      [string]$receipt.repo_sha -cne $ctx.commit -or [string]$receipt.bundle_sha256 -cne [string]$plan.bundle_sha256 -or
      [string]$receipt.strategy_sha256 -cne [string]$plan.strategy_sha256){throw 'V3_PAPER_COMMITTED_INDEPENDENT_READER_REQUIRED'}
   $epoch=Assert-V3PaperEpochPlan $ctx $inventory
   Assert-V3PaperEpochReceipt $receipt $epoch
   foreach($key in @('preinvoke_epoch_id','preinvoke_intent_id','preinvoke_request_sha256','preinvoke_source_sha256',
     'preinvoke_fence_sha256','preinvoke_inhibit_receipt_sha256')){
    $expected=[string]$plan.cas_request.new_v3_config.$key
    if(-not $expected -or [string]$receipt.$key -cne $expected){throw 'V3_PAPER_ACTIVATION_REQUEST_DRIFT'}
   }
   $spec=Read-V3PaperPinnedJson $RuntimeSpecJson $b.runtime_spec_sha256
   Assert-V3PaperRuntimeSpec $spec $plan
   # The pre-reviewed existing disabled V3 definition must already contain
   # the exact -I -B retained-snapshot action. No task installation here.
   $v3=Get-ScheduledTask -TaskName 'CryptoMiniPC-V3PaperSingleWriter'
   $expectedArguments=Get-V3PaperNativeActionPrefix $PackageRoot
   $actualArguments=[string]$v3.Actions[0].Arguments
   if([string]$v3.State -cne 'Disabled' -or
      -not ($actualArguments -ceq $expectedArguments -or $actualArguments.StartsWith($expectedArguments+' ',[StringComparison]::Ordinal))){
    throw 'V3_PAPER_REVIEWED_DISABLED_NATIVE_ACTION_REQUIRED'
   }
   Write-V3PaperReceipt ($base+'.activate.attempted.json') @{approval_sha256=$auth.approval_sha256}
   Set-V3PaperFence $ctx 'CLOUD_COMMITTED'
   Assert-V3PaperDeadline $ctx
   Enable-ScheduledTask -TaskName 'CryptoMiniPC-V3PaperSingleWriter'|Out-Null
   Start-ScheduledTask -TaskName 'CryptoMiniPC-V3PaperSingleWriter'
   return @{kind='V3_PAPER_TASK_START_REQUESTED_RUNTIME_ACK_PENDING';paper_operational_claimed=$false}
  }
  if($Mode -eq 'PaperRollback'){
   if([IO.File]::Exists($casLatch)){
    # After a possible CAS, safe rollback is V3 HOLD; never revive old intake.
    Disable-ScheduledTask -TaskName 'CryptoMiniPC-V3PaperSingleWriter'|Out-Null
    Stop-ScheduledTask -TaskName 'CryptoMiniPC-V3PaperSingleWriter'
    return @{kind='V3_PAPER_POST_CAS_SAFE_HOLD_REQUESTED';old_intake_rearmed=$false;cloud_reverse_cas=$false}
   }
   if([string]$receipt.state -cne 'PRECAS_ABORT_SEALED_OLD_ONLY_ZERO_ATTEMPTS'){
    throw 'V3_PAPER_ROLLBACK_INDEPENDENT_TERMINAL_ABORT_REQUIRED'
   }
   $rollbackEpoch=Assert-V3PaperEpochPlan $ctx $inventory
   Assert-V3PaperEpochReceipt $receipt $rollbackEpoch
   Write-V3PaperReceipt ($base+'.rollback.attempted.json') @{approval_sha256=$auth.approval_sha256}
   # Archive exact fence before the two original IgnoreNew tasks can restart.
   # All task XMLs have just been checked against their original backups.
   [IO.File]::Move($ctx.fence,($ctx.fence+'.'+$auth.claims.release_id+'.rollback'))
   foreach($name in @('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait')){
    Assert-V3PaperDeadline $ctx
    Enable-ScheduledTask -TaskName $name|Out-Null
    Start-ScheduledTask -TaskName $name
   }
   return @{kind='V3_PAPER_PRECAS_RESTORE_REQUESTED_AFTERCARE_ACK_PENDING';paper_activated=$false}
  }
 }finally{
  if($null -ne $intakePair){foreach($lease in $intakePair.leases){$lease.readonly_definition_handle.Dispose()}}
  if($held){$mutex.ReleaseMutex()};if($null -ne $mutex){$mutex.Dispose()}
  foreach($stream in $leases){$stream.Dispose()}
 }
}
