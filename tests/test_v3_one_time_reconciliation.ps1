# Targeted offline regression of the existing Gate-B owner. No Cloud/host calls.
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$root=Split-Path $PSScriptRoot -Parent
Import-Module (Join-Path $root 'tools/v3-one-time-release-authorization.psm1') -Force
$t=$null;$e=$null
$ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path $root 'tools/v3-one-time-originalhost-release.psm1'),[ref]$t,[ref]$e)
if($e.Count){throw 'RECONCILE_AST_INVALID'}
foreach($name in @('Assert-V3ReleaseReconciliationIdentity','Assert-V3ReleaseReconciliationOriginals',
 'Complete-V3ReleaseExistingAttempt','Complete-V3ReleasePreArchiveInterrupted','Enable-V3ReleaseIntakeDefinition','Read-V3ReleaseContinuingIntakes',
 'Read-V3ReleaseReconciliationHeartbeat','Wait-V3ReleaseReconciliationHealth','Wait-V3ReleaseReconciliationTerminal',
 'Test-V3Pr515DisabledOnlyXmlDifference','Write-V3ReleaseImmutableReceipt','Write-V3ReleaseArchiveCheckpoint',
 'Assert-V3ReleasePostArchiveBoundary','Get-V3ReleasePostArchiveBoundary','Complete-V3ReleasePostArchive')){
 $defs=@($ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -ceq $name},$true))
 if($defs.Count -ne 1){throw ('RECONCILE_HELPER_MISSING_'+$name)}
 . ([scriptblock]::Create($defs[0].Extent.Text))
}
$checks=0
function Check([bool]$Ok,[string]$Label){if(-not $Ok){throw ('RECONCILE_TEST_FAILED_'+$Label)};$script:checks++}
function Deny([scriptblock]$Action,[string]$Label){$denied=$false;try{& $Action|Out-Null}catch{$denied=$true};Check $denied $Label}
function DenyWith([scriptblock]$Action,[string]$ErrorId,[string]$Label){
 $actual='';try{& $Action|Out-Null}catch{$actual=$_.Exception.Message}
 Check ($actual -ceq $ErrorId) ($Label+'_EXACT_ERROR')
}
function Clone($Value){return ($Value|ConvertTo-Json -Depth 15 -Compress|ConvertFrom-Json)}
$names=@('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait')
$bindings=[ordered]@{epoch_id=('V3CAS-AUDIT-'+('a'*32));source_sha256=('a'*64);fence_sha256=('b'*64)
 caller_acl_sha256=('c'*64);reader_certificate_sha256=('d'*64);reader_source_sha256=('e'*64)
 pr515_sha256=('f'*64);backup_manifest_sha256=('1'*64);successor_series_id='PAPER-V3-20261104T133710Z'
 bundle_sha256=('2'*64);strategy_sha256=('3'*64);candidate_repo_sha=('4'*40)
 lifecycle_xml_sha256=('5'*64);cloudsync_xml_sha256=('6'*64);v3_writer_xml_sha256=('7'*64)
 install_readback_sha256=('8'*64);install_release_commit=('9'*40);policy='TERMINAL_ABORT_BEFORE_STOP_NO_CAS_V1'}
$inventory=Get-V3OneTimeReleaseArtifactInventory $root
$original=[ordered]@{kind='V3_ONE_TIME_RELEASE_AUTHORIZATION_V1';release_id=('V3-ONETIME-'+('0'*32))
 scope='ORIGINALHOST_ABORT_RESTORE';base_commit='5b1789e349b157d06d3109c5f0ff10d95154bf81';release_commit=('1'*40)
 not_before_utc=[datetimeoffset]::UtcNow.AddHours(-2).ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
 expires_at_utc=[datetimeoffset]::UtcNow.AddHours(-1).ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
 project_ref='nlgzjmqgwueojlyqmoru';computer_name='MINI-PC';trading_root='C:\Users\ADMIN\Trading';artifacts=$inventory;bindings=$bindings}
$original=Clone $original
$claim=Clone $original;$claim.scope='ORIGINALHOST_ABORT_RECONCILE';$claim.release_commit=('2'*40)
$claim.not_before_utc=[datetimeoffset]::UtcNow.AddSeconds(-5).ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
$claim.expires_at_utc=[datetimeoffset]::UtcNow.AddMinutes(10).ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
foreach($p in @{journal_sha256=('a'*64);original_approval_sha256=('b'*64);evidence_sha256=('c'*64)
 reconciliation_policy='ENABLED_ONLY_CONTINUING_ORIGINALS_NO_STOP_V1'}.GetEnumerator()){
 $claim.bindings|Add-Member -NotePropertyName $p.Key -NotePropertyValue $p.Value
}
$journal=[pscustomobject]@{kind='V3_ONE_TIME_ORIGINALHOST_ATTEMPT_V1';release_id=$claim.release_id
 approval_sha256=$claim.bindings.original_approval_sha256;epoch_id=$bindings.epoch_id
 state='ATTEMPTED_RECONCILIATION_REQUIRED_UNTIL_FINAL_ACK'}
$evidence=[pscustomobject]@{kind='V3_GATE_B_EXISTING_ATTEMPT_READONLY_RECONCILIATION_V1';release_id=$claim.release_id
 native_mutations_performed=$false;gate_b_completed=$false;approved_bindings=(Clone $original.bindings);approved_artifacts=(Clone $inventory)
 journal=[pscustomobject]@{sha256=$claim.bindings.journal_sha256;approval_sha256=$journal.approval_sha256;completion_present=$false}
 archive_present=$false;fence=[pscustomobject]@{present=$true;phase='ARMED';sha256=$bindings.fence_sha256}
 original_approval=[pscustomobject]@{cms_valid=$true;release_commit=$original.release_commit}
 tasks=@(foreach($name in $names){[pscustomobject]@{name=$name;enabled=$false;state='Running';running_instances=1
  saved_xml_sha256=('d'*64);current_xml_sha256=('e'*64)
  effective_config=[pscustomobject]@{classification='ONLY_ENABLED_FIELD_DIFFERS';original_disabled_only_contract_matches=$true}
  current_matching_processes=@([pscustomobject]@{pid=42;parent_pid=1;created_at_utc='2026-11-04T18:39:06.1900610Z';created_before_window=$true})}})}
Assert-V3ReleaseReconciliationIdentity $claim $original $journal $evidence;Check $true 'KNOWN_PARTIAL_STATE_ACCEPTED'
foreach($mutation in @(
 {param($x) $x.scope='ORIGINALHOST_ABORT_RESTORE'},
 {param($x) $x.release_id=('V3-ONETIME-'+('1'*32))},
 {param($x) $x.bindings.epoch_id=('V3CAS-AUDIT-'+('1'*32))},
 {param($x) $x.bindings.reconciliation_policy='REPLAY_STOP'},
 {param($x) $x.bindings.original_approval_sha256=('f'*64)},
 {param($x) $x.bindings|Add-Member -NotePropertyName unexpected -NotePropertyValue $true}
)){$x=Clone $claim;& $mutation $x;Deny {Assert-V3ReleaseReconciliationIdentity $x $original $journal $evidence} 'WRONG_IDENTITY'}
foreach($mutation in @(
 {param($x) $x.journal.completion_present=$true},
 {param($x) $x.journal.sha256=('f'*64)},
 {param($x) $x.archive_present=$true},
 {param($x) $x.fence.phase='QUIESCED'},
 {param($x) $x.tasks[0].enabled=$true},
 {param($x) $x.tasks[0].state='Disabled'},
 {param($x) $x.tasks[0].running_instances=0},
 {param($x) $x.tasks[0].current_matching_processes[0].created_before_window=$false},
 {param($x) $x.tasks[0].current_matching_processes[0].created_at_utc=[datetimeoffset]::UtcNow.ToString('o')},
 {param($x) $x.tasks[0].current_matching_processes=@($x.tasks[0].current_matching_processes[0],$x.tasks[0].current_matching_processes[0])},
 {param($x) $x.tasks[0].effective_config.original_disabled_only_contract_matches=$false},
 {param($x) $x.tasks[0].effective_config.classification='OTHER_FIELDS_DIFFER_REVIEW_REQUIRED'},
 {param($x) $x.approved_bindings.bundle_sha256=('f'*64)},
 {param($x) $x.approved_artifacts.'tools/v3-one-time-release.ps1'=('f'*64)},
 {param($x) $x.tasks=@($x.tasks[0],$x.tasks[0])}
)){$x=Clone $evidence;& $mutation $x;Deny {Assert-V3ReleaseReconciliationIdentity $claim $original $journal $x} 'UNKNOWN_OR_CHANGED_EVIDENCE'}
# Real detached CMS: new scope needs its OWN valid signature and clock window.
Add-Type -AssemblyName System.Security.Cryptography.Pkcs
$rsa=[Security.Cryptography.RSA]::Create(2048)
$request=[Security.Cryptography.X509Certificates.CertificateRequest]::new('CN=RECONCILIATION-CI-ONLY',$rsa,
 [Security.Cryptography.HashAlgorithmName]::SHA256,[Security.Cryptography.RSASignaturePadding]::Pkcs1)
$cert=$request.CreateSelfSigned([datetimeoffset]::UtcNow.AddMinutes(-1),[datetimeoffset]::UtcNow.AddMinutes(20))
$pin=Get-V3ReleaseSha256 $cert.RawData
function Sign([object]$Value){
 $bytes=[Text.Encoding]::UTF8.GetBytes(($Value|ConvertTo-Json -Depth 15 -Compress))
 $cms=[Security.Cryptography.Pkcs.SignedCms]::new([Security.Cryptography.Pkcs.ContentInfo]::new($bytes),$true)
 $signer=[Security.Cryptography.Pkcs.CmsSigner]::new($cert);$signer.DigestAlgorithm=[Security.Cryptography.Oid]::new('2.16.840.1.101.3.4.2.1')
 $cms.ComputeSignature($signer);return @{Payload=$bytes;Cms=[byte[]]$cms.Encode()}
}
$signed=Sign $claim
$authArgs=@{ReviewedAuthorityCertificateSha256=$pin;Scope='ORIGINALHOST_ABORT_RECONCILE';ExpectedReleaseCommit=$claim.release_commit;ExpectedArtifacts=$inventory}
$null=Assert-V3OneTimeReleaseAuthorization @signed @authArgs;Check $true 'FRESH_RECONCILIATION_REAL_CMS'
$expired=Clone $claim;$expired.not_before_utc=[datetimeoffset]::UtcNow.AddMinutes(-14).ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
$expired.expires_at_utc=[datetimeoffset]::UtcNow.AddMinutes(-1).ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
$bad=Sign $expired;Deny {Assert-V3OneTimeReleaseAuthorization @bad @authArgs} 'EXPIRED_NEW_AUTHORITY'
$oldSigned=Sign $original
Assert-V3ReleaseCms -Payload $oldSigned.Payload -Cms $oldSigned.Cms -ReviewedAuthorityCertificateSha256 $pin
Check $true 'HISTORICAL_SIGNATURE_VALID_WITHOUT_RENEWAL'
Deny {Assert-V3OneTimeReleaseAuthorization @oldSigned @authArgs} 'OLD_CMS_NOT_NEW_AUTHORIZATION'
# Exercise the REAL continuing-state reader with local data and mock read-only
# OS adapters. No Windows API, command line output or production paths opened.
$temp=Join-Path ([IO.Path]::GetTempPath()) ('V3-Reconciliation-CI-'+[guid]::NewGuid().ToString('N'))
$null=[IO.Directory]::CreateDirectory($temp)
try{
 # Full original-evidence join with real historical CMS and original bytes.
 $originalPath=Join-Path $temp 'original.json';$cmsPath=Join-Path $temp 'original.cms'
 $journalPath=Join-Path $temp 'original-attempt.json';$evidencePath=Join-Path $temp 'evidence.json'
 [IO.File]::WriteAllBytes($originalPath,$oldSigned.Payload);[IO.File]::WriteAllBytes($cmsPath,$oldSigned.Cms)
 $c=Clone $claim;$j=Clone $journal;$ev=Clone $evidence
 $c.bindings.original_approval_sha256=Get-V3ReleaseSha256 $oldSigned.Payload
 $j.approval_sha256=$c.bindings.original_approval_sha256
 [IO.File]::WriteAllText($journalPath,($j|ConvertTo-Json -Compress))
 $c.bindings.journal_sha256=Get-V3ReleaseSha256 ([IO.File]::ReadAllBytes($journalPath))
 $ev.journal.sha256=$c.bindings.journal_sha256;$ev.journal.approval_sha256=$j.approval_sha256
 [IO.File]::WriteAllText($evidencePath,($ev|ConvertTo-Json -Depth 15 -Compress))
 $c.bindings.evidence_sha256=Get-V3ReleaseSha256 ([IO.File]::ReadAllBytes($evidencePath))
 $originalContext=[pscustomobject]@{authorization=[pscustomobject]@{claims=$c};journal_path=$journalPath
  original_approval_path=$originalPath;original_cms_path=$cmsPath;evidence_path=$evidencePath;authority_pin=$pin}
 Assert-V3ReleaseReconciliationOriginals $originalContext;Check $true 'REAL_HISTORICAL_ORIGINALS_ACCEPTED'
 [IO.File]::AppendAllText($journalPath,' ')
 Deny {Assert-V3ReleaseReconciliationOriginals $originalContext} 'JOURNAL_BYTE_DRIFT'
 [IO.File]::WriteAllText($journalPath,($j|ConvertTo-Json -Compress))
 [IO.File]::WriteAllText(($journalPath+'.completed.json'),'completion exists')
 Deny {Assert-V3ReleaseReconciliationOriginals $originalContext} 'EXISTING_COMPLETION'
 [IO.File]::Delete($journalPath+'.completed.json')
 $originalContext.authority_pin=('0'*64)
 Deny {Assert-V3ReleaseReconciliationOriginals $originalContext} 'HISTORICAL_SIGNER_DRIFT'
 $originalContext.authority_pin=$pin
 [IO.File]::AppendAllText($evidencePath,' ')
 Deny {Assert-V3ReleaseReconciliationOriginals $originalContext} 'EVIDENCE_BYTE_DRIFT'
 # Exercise the REAL signed Reader verifier through the real polling helper.
 $readerModule=Import-Module (Join-Path $root 'tools/v3-one-time-originalhost-release.psm1') -Force -PassThru
 Import-Module (Join-Path $root 'tools/v3-one-time-release-authorization.psm1') -Force
 function Test-V3Pr515SignedPreparedAbortReadback {
  param($Payload,$Cms,$ReviewedCertSha256,$ExpectedEpochId,$ExpectedSourceSha256,$ExpectedFenceSha256,$ExpectedAclSha256)
  return (& $readerModule {param($p,$c,$pin,$epoch,$source,$fence,$acl)
   Test-V3Pr515SignedPreparedAbortReadback $p $c $pin $epoch $source $fence $acl
  } $Payload $Cms $ReviewedCertSha256 $ExpectedEpochId $ExpectedSourceSha256 $ExpectedFenceSha256 $ExpectedAclSha256)
 }
 function Start-Sleep {param($Seconds) throw 'TEST_BOUNDED_READER_OBSERVATION_ENDED'}
 $readerClaim=Clone $claim;$readerClaim.bindings.reader_certificate_sha256=$pin
 $readerContext=[pscustomobject]@{authorization=[pscustomobject]@{claims=$readerClaim;expires_at=[datetimeoffset]::UtcNow.AddMinutes(10)}
  abort_json=(Join-Path $temp 'reader.json');abort_cms=(Join-Path $temp 'reader.cms')}
 foreach($readerCase in @('timely','before_archive','wrong_epoch','invalid_cms','missing','stale')){
  $record=[ordered]@{kind='V3_CAS_PREPARED_FENCE_ABORT_READER_RECEIPT_V1'
   epoch_id=$bindings.epoch_id;source_sha256=$bindings.source_sha256;prepared_fence_sha256=$bindings.fence_sha256
   caller_acl_sha256=$bindings.caller_acl_sha256;issuer_actor='v3_cas_inhibit_issuer_actor';receipt_sha256=('d'*64)
   state='ABORT_RECORDED_NOT_RELEASED';created_at_utc=[datetimeoffset]::UtcNow.AddHours(-1).ToString("yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'")
   observed_at_utc=[datetimeoffset]::UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'")
   cloud_observed_at_utc=[datetimeoffset]::UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'")
   cloud_active_series_count=1;cloud_original_active_series_count=1;cloud_cas_rpc_count=0;cloud_executor_can_login=$false}
  if($readerCase -ceq 'wrong_epoch'){$record.epoch_id='V3CAS-AUDIT-'+('f'*32)}
  if($readerCase -ceq 'stale'){
   $record.observed_at_utc=[datetimeoffset]::UtcNow.AddMinutes(-3).ToString("yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'")
   $record.cloud_observed_at_utc=$record.observed_at_utc
  }
  $signedReader=Sign $record
  [IO.File]::WriteAllBytes($readerContext.abort_json,$signedReader.Payload)
  [IO.File]::WriteAllBytes($readerContext.abort_cms,$signedReader.Cms)
  if($readerCase -ceq 'invalid_cms'){[IO.File]::WriteAllBytes($readerContext.abort_cms,[byte[]](1,2,3))}
  if($readerCase -ceq 'missing'){[IO.File]::Delete($readerContext.abort_json)}
  $archiveBoundary=[datetimeoffset]::UtcNow.AddSeconds(-5)
  if($readerCase -ceq 'before_archive'){$archiveBoundary=[datetimeoffset]::UtcNow.AddSeconds(1)}
  if($readerCase -ceq 'timely'){
   $null=Wait-V3ReleaseReconciliationTerminal $readerContext $archiveBoundary;Check $true 'REAL_CMS_POST_ARCHIVE_TIMELY'
  }else{Deny {Wait-V3ReleaseReconciliationTerminal $readerContext $archiveBoundary} ('REAL_CMS_READER_'+$readerCase)}
 }
 # Actual timestamp/freshness helper: unhealthy, stale and future observations
 # cannot become aftercare success. No clock extension from an expired session.
 $heartbeat=Join-Path $temp 'heartbeat.json'
 $after=[datetimeoffset]::UtcNow.AddSeconds(-10)
 foreach($case in @('valid','stale','future','warning','before-action')){
  $at=[datetimeoffset]::UtcNow.AddSeconds(-1);$status='HEALTHY'
  if($case -ceq 'stale'){$at=$at.AddMinutes(-2)}
  if($case -ceq 'future'){$at=$at.AddMinutes(2)}
  if($case -ceq 'warning'){$status='WARNING'}
  if($case -ceq 'before-action'){$at=$after.AddSeconds(-1)}
  [IO.File]::WriteAllText($heartbeat,(@{status=$status;checked_at_utc=$at.ToString('o')}|ConvertTo-Json -Compress))
  if($case -ceq 'valid'){$null=Read-V3ReleaseReconciliationHeartbeat $heartbeat $after;Check $true 'HEALTHY_AFTER_ACTION'}
  else{Deny {Read-V3ReleaseReconciliationHeartbeat $heartbeat $after} ('HEARTBEAT_'+$case)}
 }
 $expiredContext=[pscustomobject]@{authorization=[pscustomobject]@{expires_at=[datetimeoffset]::UtcNow.AddSeconds(-1);claims=$claim}}
 Deny {Wait-V3ReleaseReconciliationHealth $expiredContext $after} 'HEALTH_WAIT_EXPIRED_SESSION'
 Deny {Wait-V3ReleaseReconciliationTerminal $expiredContext $after} 'READER_WAIT_EXPIRED_SESSION'
 $backup=Join-Path $temp 'backup';$null=[IO.Directory]::CreateDirectory($backup)
 $saved='<Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"><Settings></Settings><Actions><Exec><Command>python.exe</Command><Arguments>fixture-runtime.py</Arguments></Exec></Actions></Task>'
 $disabled=$saved.Replace('<Settings></Settings>','<Settings><Enabled>false</Enabled></Settings>')
 $enabled=$saved.Replace('<Settings></Settings>','<Settings><Enabled>true</Enabled></Settings>')
 $e=Clone $evidence
 $records=@();$script:state=@{};$script:xml=@{}
 foreach($name in $names){
  $leaf=if($name -ceq $names[0]){'Candidates.task.xml'}else{'WAIT.task.xml'}
  [IO.File]::WriteAllText((Join-Path $backup $leaf),$saved,[Text.UTF8Encoding]::new($false))
  $sha=Get-V3ReleaseSha256 ([Text.Encoding]::UTF8.GetBytes($saved))
  $records+=@([pscustomobject]@{task_name=$name;xml_file=$leaf;xml_sha256=$sha})
  $row=@($e.tasks|Where-Object name -CEQ $name)[0];$row.saved_xml_sha256=$sha
  $row.current_xml_sha256=Get-V3ReleaseSha256 ([Text.Encoding]::UTF8.GetBytes($disabled))
  # Distinct task arguments and two original PIDs each model launcher/worker
  # pairs. An unrelated Python process must never match either task.
  $row.current_matching_processes=@(foreach($pidValue in $(if($name -ceq $names[0]){@(42,43)}else{@(44,45)})){
   [pscustomobject]@{pid=$pidValue;parent_pid=1;created_at_utc='2026-11-04T18:39:06.1900610Z';created_before_window=$true}
  })
  $script:state[$name]=$false;$script:xml[$name]=$disabled
 }
 [IO.File]::WriteAllText((Join-Path $backup 'backup-manifest.json'),(@{backup_directory=$backup;task_records=$records}|ConvertTo-Json -Depth 6))
 $liveClaim=Clone $claim;$liveClaim.bindings.backup_manifest_sha256=Get-V3ReleaseSha256 ([IO.File]::ReadAllBytes((Join-Path $backup 'backup-manifest.json')))
 $liveCtx=[pscustomobject]@{tasks=$names;backup_root=$backup;evidence=$e;authorization=[pscustomobject]@{claims=$liveClaim}}
 function Test-V3Pr515CurrentOriginalBackupManifest {param($Manifest) return $true} # original validator separately tested
 function New-Object {param($ComObject)
  if($ComObject -cne 'Schedule.Service'){throw 'TEST_FORBIDS_OTHER_COM'}
  $svc=[pscustomobject]@{};$svc|Add-Member ScriptMethod Connect {}
  $svc|Add-Member ScriptMethod GetFolder {
   param($path) $folder=[pscustomobject]@{};$folder|Add-Member ScriptMethod GetTask {
    param($name) $task=[pscustomobject]@{Enabled=$script:state[$name]}
    $task|Add-Member ScriptMethod GetInstances {param($flags) return @([pscustomobject]@{InstanceGuid='{11111111-1111-1111-1111-111111111111}'})}
    return $task
   };return $folder
  };return $svc
 }
 $script:cimMode='stable';$script:cimCalls=0
 function Get-CimInstance {param($Query,$ErrorAction)
  $script:cimCalls++
  Check ($Query -ceq "SELECT ProcessId,ParentProcessId,Name,CreationDate,CommandLine FROM Win32_Process WHERE Name='python.exe' OR Name='pythonw.exe'") 'ORIGINAL_CIM_QUERY'
  $rows=@(foreach($pidValue in @(42,43,44,45,99)){
   $taskArgument=if($pidValue -in @(42,43)){'fixture-candidates-runtime.py'}elseif($pidValue -in @(44,45)){'fixture-wait-runtime.py'}else{'unrelated-runtime.py'}
   [pscustomobject]@{ProcessId=$pidValue;ParentProcessId=$script:parent
    CreationDate=[datetime]::Parse('2026-11-04T18:39:06.1900610Z').ToUniversalTime()
    CommandLine=('python.exe '+$taskArgument)}
  })
  if($script:cimMode -in @('missing','transient') -and ($script:cimMode -ceq 'missing' -or $script:cimCalls -eq 1)){
   return @($rows|Where-Object ProcessId -NE 42)
  }
  if($script:cimMode -ceq 'extra'){
   $extra=Clone $rows[0];$extra.ProcessId=100;return @($rows)+@($extra)
  }
  if($script:cimMode -ceq 'replaced'){$rows[0].ProcessId=100}
  if($script:cimMode -ceq 'reused_pid'){$rows[0].CreationDate=$rows[0].CreationDate.AddTicks(10)}
  if($script:cimMode -ceq 'null_command'){$rows[0].CommandLine=$null}
  return $rows
 }
 function Get-ScheduledTask {param($TaskName,$TaskPath,$ErrorAction)
  $taskArgument=if($TaskName -ceq $names[0]){'fixture-candidates-runtime.py'}else{'fixture-wait-runtime.py'}
  return [pscustomobject]@{State='Running';Actions=@([pscustomobject]@{Arguments=$taskArgument})}
 }
 function Export-ScheduledTask {param($TaskName,$TaskPath,$ErrorAction) return $script:xml[$TaskName]}
 $script:parent=1
 $null=Read-V3ReleaseContinuingIntakes $liveCtx;Check $true 'ENABLED_FALSE_RUNNING_TRUE_ACCEPTED'
 Check ($script:cimCalls -eq 1) 'STABLE_FOUR_ORIGINALS_ONE_SNAPSHOT_WITH_UNRELATED_PYTHON'
 foreach($mode in @('missing','extra','replaced','reused_pid','null_command','transient')){
  $script:cimMode=$mode;$script:cimCalls=0
  $errorId=if($mode -in @('replaced','reused_pid')){'V3_RECONCILE_ORIGINAL_PROCESS_IDENTITY_DRIFT'}else{'V3_RECONCILE_PROCESS_COUNT_DRIFT'}
  DenyWith {Read-V3ReleaseContinuingIntakes $liveCtx} $errorId $mode
  Check ($script:cimCalls -eq 1) ($mode+'_NO_HIDDEN_CIM_RETRY')
  if($mode -ceq 'transient'){
   # The next independent read sees the originals, but the failed call stays
   # HOLD. No snapshot union, process substitution or reconciliation replay.
   $null=Read-V3ReleaseContinuingIntakes $liveCtx
   Check ($script:cimCalls -eq 2) 'TRANSIENT_LATER_READ_IS_SEPARATE'
  }
 }
 $script:cimMode='stable'
 $script:parent=2;Deny {Read-V3ReleaseContinuingIntakes $liveCtx} 'PROCESS_IDENTITY_CHANGED';$script:parent=1
 $script:xml[$names[0]]=$disabled.Replace('python.exe','foreign.exe')
 Deny {Read-V3ReleaseContinuingIntakes $liveCtx} 'ACTION_DRIFT_NO_XML_OVERWRITE';$script:xml[$names[0]]=$disabled
 $script:state[$names[0]]=$true;$script:xml[$names[0]]=$enabled
 $null=Read-V3ReleaseContinuingIntakes -Context $liveCtx -EnabledNames @($names[0]);Check $true 'PARTIALLY_ENABLED_LIVE_READBACK'
 Deny {Read-V3ReleaseContinuingIntakes $liveCtx} 'UNEXPECTED_ENABLED_STATE'
 $script:realContinuingReader=${function:Read-V3ReleaseContinuingIntakes}
 # After the read-only adapter tests, simulate only OS/native boundaries in
 # the REAL completion orchestration. Actual durable latch and result I/O run.
 $script:V3ReleaseRoot=$temp
 $null=[IO.Directory]::CreateDirectory((Join-Path $temp 'State'))
 function Read-V3ReleaseContinuingIntakes {param($Context,$EnabledNames=@())
  if($script:scenario -ceq 'resume_identity_unknown'){throw 'V3_RECONCILE_ORIGINAL_PROCESS_IDENTITY_DRIFT'}
  foreach($n in $Context.tasks){if($script:state[$n] -ne ($n -cin $EnabledNames)){throw 'TEST_STATE_MISMATCH'}}
  if($script:scenario -ceq 'process_drift'){
   foreach($n in $names){$script:xml[$n]=$disabled}
   $script:cimMode='extra'
   return (& $script:realContinuingReader $liveCtx)
  }
  return ,@([pscustomobject]@{name=$names[0];instance_id='one'},[pscustomobject]@{name=$names[1];instance_id='two'})
 }
 function Test-V3Pr661HeldIntakeDefinitionPair {param($Pair,$TaskNames) return $true}
 function Assert-V3ReleaseMutationBoundary {param($Phase)
  if($Phase -ceq 'STOP'){throw 'TEST_FORBIDS_STOP'}
  if([datetimeoffset]::UtcNow -ge $script:V3ReleaseContext.authorization.expires_at){throw 'V3_RELEASE_APPROVAL_EXPIRED_OR_FUTURE_HOLD'}
  if($script:scenario -ceq 'expiry_after_first' -and $script:enables -eq 1){throw 'V3_RELEASE_APPROVAL_EXPIRED_OR_FUTURE_HOLD'}
 }
 function Enable-ScheduledTask {param($TaskName,$TaskPath,$ErrorAction)
  $script:enables++
  if($script:scenario -ceq 'second_enable_unknown' -and $script:enables -eq 2){throw 'ENABLE_UNKNOWN'}
  $script:state[$TaskName]=$true
 }
 function Stop-ScheduledTask {throw 'TEST_FORBIDS_STOP'}
 function Start-ScheduledTask {throw 'TEST_FORBIDS_START'}
 function Wait-V3ReleaseReconciliationHealth {param($Context,$After,[switch]$AfterArchive)
  if(($script:scenario -ceq 'health_unknown' -and -not $AfterArchive) -or
     ($script:scenario -ceq 'aftercare_unknown' -and $AfterArchive)){throw 'HEALTH_UNKNOWN'}
 }
 function Invoke-V3Pr515NativeExclusiveFenceArchiveSOURCE_ONLY {param($Source,$Archive,$ExpectedSha256,$IsolatedRoot,$IsolatedTaskNames)
  $script:archives++
  if($script:scenario -ceq 'archive_unknown_before'){throw 'ARCHIVE_UNKNOWN'}
  [IO.File]::Move($Source,$Archive)
  if($script:scenario -ceq 'archive_unknown_after'){throw 'ARCHIVE_RESULT_UNKNOWN'}
  return [pscustomobject]@{status='ATOMIC_FILE_RENAME_CONFIRMED_NO_CAS_OR_PAPER_RELEASE'}
 }
 function Assert-V3OneTimeReleaseAuthorization {param($Payload,$Cms,$ReviewedAuthorityCertificateSha256,$Scope,$ExpectedReleaseCommit,$ExpectedArtifacts)
  Check ($Scope -ceq 'ORIGINALHOST_ABORT_RECONCILE') 'FINAL_AUTH_SCOPE';return $null
 }
 function Assert-V3ReleaseReconciliationOriginals {param($Context)
  if((Get-V3ReleaseSha256 ([IO.File]::ReadAllBytes($Context.journal_path))) -cne $Context.authorization.claims.bindings.journal_sha256){throw 'JOURNAL_CHANGED'}
 }
 function Assert-V3ReleaseProtectedTasks {param($Bindings)
  if($script:scenario -ceq 'task_drift'){throw 'TASK_DRIFT'}
 }
 function Test-V3ReleaseOriginalhostScope {param($Root,$Tasks)
  return ([datetimeoffset]::UtcNow -lt $script:V3ReleaseContext.authorization.expires_at)
 }
 function Assert-V3ReleaseAuthorityAdmission {param($Bytes,$ExpectedSha256,$ReleaseCommit) return $pin}
 function Assert-V3ReleaseInstalledAbortReadback {param($Path,$Bindings,$ExpectedSourceSha256)}
 function Wait-V3ReleaseReconciliationTerminal {param($Context,$After)
  if($script:scenario -ceq 'reader_missing'){throw 'READER_MISSING'}
  return [pscustomobject]@{payload=[byte[]](1,2);cms=[byte[]](3,4)}}
 function Test-V3Pr515SignedPreparedAbortReadback {param($Payload,$Cms,$ReviewedCertSha256,$ExpectedEpochId,$ExpectedSourceSha256,$ExpectedFenceSha256,$ExpectedAclSha256)
  return [pscustomobject]@{signed_abort_fields_and_pins_match=($script:scenario -cne 'final_reader_unknown')}
 }
 $script:immutableWriter=${function:Write-V3ReleaseImmutableReceipt}
 function Write-V3ReleaseImmutableReceipt {param($Path,$Value)
  if($script:scenario -ceq 'awaiting_persist_crash' -and $Path.EndsWith('.awaiting-post-archive-reader.json')){throw 'SIMULATED_CRASH_BEFORE_AWAITING_PERSIST'}
  & $script:immutableWriter $Path $Value
 }
 $script:archiveLeaf='v3-experimental-paper-old-intake-fence.aborted-'+$bindings.epoch_id+'.json'
 foreach($scenario in @('success','process_drift','second_enable_unknown','expiry_after_first','health_unknown','archive_unknown_before','archive_unknown_after','aftercare_unknown','final_reader_unknown','reader_missing','awaiting_persist_crash','expired_initial')){
  $script:scenario=$scenario;$script:enables=0;$script:archives=0
  $case=Join-Path $temp $scenario;$null=[IO.Directory]::CreateDirectory($case)
  $script:V3ReleaseRoot=$case;$null=[IO.Directory]::CreateDirectory((Join-Path $case 'State'))
  $journalPath=Join-Path $case 'attempt.json';[IO.File]::WriteAllText($journalPath,'original immutable journal')
  $journalSha=Get-V3ReleaseSha256 ([IO.File]::ReadAllBytes($journalPath))
  $fence=Join-Path $case 'State/v3-experimental-paper-old-intake-fence.json';[IO.File]::WriteAllText($fence,'original fence bytes')
  $c=Clone $claim;$c.bindings.journal_sha256=$journalSha;$c.bindings.fence_sha256=Get-V3ReleaseSha256 ([IO.File]::ReadAllBytes($fence))
  $caseSigned=Sign $c
  $ctx=[pscustomobject]@{authorization=[pscustomobject]@{claims=$c;expires_at=[datetimeoffset]::UtcNow.AddMinutes(10);approval_sha256=(Get-V3ReleaseSha256 $caseSigned.Payload)}
   tasks=$names;payload=$caseSigned.Payload;cms=$caseSigned.Cms;authority_pin=$pin;package_root=$root;journal_path=$journalPath
   admission_bytes=[byte[]](1);admission_sha256=('0'*64);catalog_readback='fixture'
   continuation_leases=[Collections.Generic.List[IO.FileStream]]::new()
   enabled_names=@();instance_snapshot=@([pscustomobject]@{name=$names[0];instance_id='one'},[pscustomobject]@{name=$names[1];instance_id='two'})}
  if($scenario -ceq 'expired_initial'){$ctx.authorization.expires_at=[datetimeoffset]::UtcNow.AddSeconds(-1)}
  $script:V3ReleaseContext=$ctx
  foreach($n in $names){$script:state[$n]=$false}
  $stream=[IO.File]::OpenRead($journalPath)
  $pair=[pscustomobject]@{leases=@([pscustomobject]@{readonly_definition_handle=$stream})}
  try{
   if($scenario -ceq 'success'){
    $result=Complete-V3ReleaseExistingAttempt $ctx $pair
    Check ($result.successful_stop_claimed -eq $false -and $result.stop_requested_here -eq $false -and
      $result.new_process_started_here -eq $false -and $result.original_processes_continued -eq $true) 'TRUTHFUL_PARTIAL_COMPLETION'
    Check ($script:enables -eq 2 -and $script:archives -eq 1 -and (Test-Path ($journalPath+'.completed.json'))) 'SINGLE_COMPLETION'
   }else{
    if($scenario -ceq 'process_drift'){
     DenyWith {Complete-V3ReleaseExistingAttempt $ctx $pair} 'V3_RECONCILE_PROCESS_COUNT_DRIFT' 'REAL_READER_BEFORE_ENABLE'
     Check ($script:enables -eq 0 -and $script:archives -eq 0) 'COUNT_DRIFT_NO_NATIVE_MUTATION'
     Check ((Get-V3ReleaseSha256 ([IO.File]::ReadAllBytes($fence))) -ceq $c.bindings.fence_sha256) 'COUNT_DRIFT_FENCE_PRESERVED'
    }else{Deny {Complete-V3ReleaseExistingAttempt $ctx $pair} $scenario}
    Check (-not(Test-Path ($journalPath+'.completed.json'))) 'UNKNOWN_NEVER_COMPLETES'
   }
   Check ((Get-V3ReleaseSha256 ([IO.File]::ReadAllBytes($journalPath))) -ceq $journalSha) 'JOURNAL_PRESERVED'
   if($scenario -ceq 'expired_initial'){
    Check ($script:enables -eq 0 -and -not(Test-Path ($journalPath+'.reconciliation-attempt.json'))) 'EXPIRED_NO_MUTATION'
   }else{
    Check (Test-Path ($journalPath+'.reconciliation-attempt.json')) 'DURABLE_ATTEMPT_PRESERVED'
    $before=$script:enables
    Deny {Complete-V3ReleaseExistingAttempt $ctx $pair} 'REPEATED_RECONCILIATION_DENIED'
    Check ($script:enables -eq $before) 'REPLAY_NO_ENABLE'
   }
   $archived=Test-Path (Join-Path $case ('State/'+$script:archiveLeaf))
   if($scenario -cin @('success','archive_unknown_after','aftercare_unknown','final_reader_unknown','reader_missing','awaiting_persist_crash')){
    Check ($archived -and -not(Test-Path $fence)) 'ARCHIVE_PRESERVED_ON_LATE_UNKNOWN'
   }else{Check ((Test-Path $fence) -and -not $archived) 'ARMED_PRESERVED_BEFORE_ARCHIVE'}
   if($scenario -cin @('archive_unknown_after','aftercare_unknown','final_reader_unknown','reader_missing','awaiting_persist_crash')){
    $beforeEnable=$script:enables;$beforeArchive=$script:archives
    $attemptSha=Get-V3ReleaseSha256 ([IO.File]::ReadAllBytes($journalPath+'.reconciliation-attempt.json'))
    $script:scenario='success'
    # A new process context must recover the original instances from durable
    # evidence, never accept a caller's current snapshot as the old one.
    $ctx.instance_snapshot=$null;$ctx.enabled_names=@()
    $after=Get-V3ReleasePostArchiveBoundary $ctx
    Check (Test-Path ($journalPath+'.awaiting-post-archive-reader.json')) 'DURABLE_AWAITING_STATE'
    $awaiting=Read-V3ReleaseJson ([IO.File]::ReadAllBytes($journalPath+'.awaiting-post-archive-reader.json'))
    Check ($awaiting.state -ceq 'AWAITING_POST_ARCHIVE_READER') 'AWAITING_STATE_NAME'
    # Preserve every byte of the checkpoint across repeated failed calls.
    $checkpointSha=Get-V3ReleaseSha256 ([IO.File]::ReadAllBytes($journalPath+'.pre-archive.json'))
    $savedPayload=$ctx.payload;$savedCms=$ctx.cms;$savedClaim=$ctx.authorization.claims
    foreach($drift in @('epoch_id','journal_sha256','source_sha256')){
     $changed=Clone $savedClaim;$changed.bindings.$drift=('0'*64)
     $ctx.authorization.claims=$changed
     Deny {Get-V3ReleasePostArchiveBoundary $ctx} ('RESUME_BINDING_DRIFT_'+$drift)
    }
    $ctx.authorization.claims=$savedClaim
    $changed=Clone $savedClaim;$changed.release_commit=('0'*40);$ctx.authorization.claims=$changed
    Deny {Get-V3ReleasePostArchiveBoundary $ctx} 'RESUME_RELEASE_DRIFT';$ctx.authorization.claims=$savedClaim
    foreach($drift in @('task_drift','process_drift')){
     $script:scenario=$drift;Deny {Get-V3ReleasePostArchiveBoundary $ctx} ('RESUME_'+$drift)
    }
    $script:scenario='success'
    $ctx.authorization.expires_at=[datetimeoffset]::UtcNow.AddSeconds(-1)
    Deny {Get-V3ReleasePostArchiveBoundary $ctx} 'RESUME_EXPIRED_AUTHORITY'
    $ctx.authorization.expires_at=[datetimeoffset]::UtcNow.AddMinutes(10)
    # A genuinely new signed authority window retains all release and epoch pins.
    $renewed=Clone $savedClaim;$renewed.not_before_utc=[datetimeoffset]::UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
    $renewed|Out-Null
    $renewed.bindings|Add-Member -NotePropertyName post_archive_receipt_sha256 -NotePropertyValue (Get-V3ReleaseSha256 ([IO.File]::ReadAllBytes($journalPath+'.awaiting-post-archive-reader.json')))
    $renewed.expires_at_utc=[datetimeoffset]::UtcNow.AddMinutes(10).ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
    $newSigned=Sign $renewed;$ctx.payload=$newSigned.Payload;$ctx.cms=$newSigned.Cms;$ctx.authorization.claims=$renewed
    $ctx.authorization.approval_sha256=Get-V3ReleaseSha256 $newSigned.Payload
    $after=Get-V3ReleasePostArchiveBoundary $ctx
    $awaitBytes=[IO.File]::ReadAllBytes($journalPath+'.awaiting-post-archive-reader.json')
    Assert-V3ReconciliationResumeReceipt $renewed $awaitBytes;Check $true 'EXACT_CONTINUATION_RECEIPT_AUTHORITY'
    Deny {Assert-V3ReconciliationResumeReceipt $savedClaim $awaitBytes} 'UNPINNED_OLD_AUTHORITY_NO_RESUME'
    Deny {Assert-V3ReconciliationResumeReceipt $renewed ([Text.Encoding]::UTF8.GetBytes('{}'))} 'MODIFIED_CONTINUATION_RECEIPT'
    $result=Complete-V3ReleasePostArchive $ctx $after
    Check ($result.original_processes_continued -eq $true) 'RESTART_FINALIZED_SAME_ORIGINAL_TRANSACTION'
    Check ($script:enables -eq $beforeEnable -and $script:archives -eq $beforeArchive) 'RESUME_NO_NATIVE_MUTATION'
    Check ((Get-V3ReleaseSha256 ([IO.File]::ReadAllBytes($journalPath+'.reconciliation-attempt.json'))) -ceq $attemptSha) 'RESUME_ATTEMPT_UNCHANGED'
    Check ((Get-V3ReleaseSha256 ([IO.File]::ReadAllBytes($journalPath+'.pre-archive.json'))) -ceq $checkpointSha) 'RESUME_CHECKPOINT_UNCHANGED'
    Deny {Complete-V3ReleasePostArchive $ctx $after} 'RESUME_COMPLETION_NO_REPLAY'
   }elseif($scenario -cne 'success'){
    Deny {Get-V3ReleasePostArchiveBoundary $ctx} 'PRE_ARCHIVE_RESTART_HOLD_NO_ENABLE'
   }

  }finally{foreach($leaseStream in $ctx.continuation_leases){$leaseStream.Dispose()};$stream.Dispose()}
 }
 # Recover a real persisted attempt in PRE-ARCHIVE HOLD. No task Enable and
 # no second attempt marker: prior CMS must sign the actual latch hash.
 $script:scenario='success';$script:enables=0;$script:archives=0
 $case=Join-Path $temp 'pre_archive_resume';$null=[IO.Directory]::CreateDirectory($case)
 $script:V3ReleaseRoot=$case;$null=[IO.Directory]::CreateDirectory((Join-Path $case 'State'))
 $journalPath=Join-Path $case 'attempt.json';[IO.File]::WriteAllText($journalPath,'immutable journal')
 $journalSha=Get-V3ReleaseSha256 ([IO.File]::ReadAllBytes($journalPath))
 $fence=Join-Path $case 'State/v3-experimental-paper-old-intake-fence.json'
 [IO.File]::WriteAllText($fence,'original fence bytes')
 $oldClaim=Clone $claim;$oldClaim.bindings.journal_sha256=$journalSha
 $oldClaim.bindings.fence_sha256=Get-V3ReleaseSha256 ([IO.File]::ReadAllBytes($fence))
 $oldSigned=Sign $oldClaim
 $latch=[ordered]@{kind='V3_EXISTING_GATE_B_RECONCILIATION_ATTEMPT_V1'
  release_id=$oldClaim.release_id;journal_sha256=$journalSha
  approval_sha256=(Get-V3ReleaseSha256 $oldSigned.Payload)
  state='RECONCILIATION_ATTEMPTED_UNKNOWN_UNTIL_FINAL_ACK';stop_requested=$false}
 $latchPath=$journalPath+'.reconciliation-attempt.json'
 [IO.File]::WriteAllText($latchPath,($latch|ConvertTo-Json -Compress))
 $latchSha=Get-V3ReleaseSha256 ([IO.File]::ReadAllBytes($latchPath))
 $newClaim=Clone $oldClaim;$newClaim.release_commit=('3'*40)
 foreach($artifact in @('tools/v3-one-time-originalhost-release.psm1','tools/v3-one-time-release.ps1','tools/v3-one-time-release-authorization.psm1')){
  $newClaim.artifacts.$artifact=('e'*64)
 }
 $newClaim.bindings|Add-Member -NotePropertyName pre_archive_attempt_sha256 -NotePropertyValue $latchSha
 $newSigned=Sign $newClaim
 $oldJson=Join-Path $case 'prior.json';$oldCms=Join-Path $case 'prior.cms'
 [IO.File]::WriteAllBytes($oldJson,$oldSigned.Payload)
 [IO.File]::WriteAllBytes($oldCms,$oldSigned.Cms)
 $ctx=[pscustomobject]@{authorization=[pscustomobject]@{claims=$newClaim
   expires_at=[datetimeoffset]::UtcNow.AddMinutes(10)
   approval_sha256=(Get-V3ReleaseSha256 $newSigned.Payload)}
  tasks=$names;payload=$newSigned.Payload;cms=$newSigned.Cms;authority_pin=$pin
  package_root=$root;journal_path=$journalPath
  admission_bytes=[byte[]](1);admission_sha256=('0'*64);catalog_readback='fixture'
  enabled_names=@();instance_snapshot=$null;interrupted_approval_bytes=$null;interrupted_cms_bytes=$null
  continuation_leases=[Collections.Generic.List[IO.FileStream]]::new()}
 $script:V3ReleaseContext=$ctx
 foreach($n in $names){$script:state[$n]=$true}
 function Get-V3Pr515ArmedOnlyRecoveryReadback {param($Root,$ExpectedFenceSha256) return $null}
 Assert-V3ReconciliationPreArchiveAttemptAuthority -InterruptedPayload $oldSigned.Payload -InterruptedCms $oldSigned.Cms -Attempt ([IO.File]::ReadAllBytes($latchPath)) -AuthorityPin $pin -Current $newClaim
 Check $true 'SIGNED_PREARCHIVE_ATTEMPT_PIN_OK'
 $bad=Clone $newClaim;$bad.bindings.pre_archive_attempt_sha256=('0'*64)
 Deny {Assert-V3ReconciliationPreArchiveAttemptAuthority -InterruptedPayload $oldSigned.Payload -InterruptedCms $oldSigned.Cms -Attempt ([IO.File]::ReadAllBytes($latchPath)) -AuthorityPin $pin -Current $bad} 'WRONG_ATTEMPT_PIN_DENIED'
 $script:scenario='resume_identity_unknown'
 Deny {Complete-V3ReleasePreArchiveInterrupted $ctx $oldJson $oldCms} 'ORIGINAL_PROCESS_MISMATCH_HOLD'
 Check ($script:enables -eq 0 -and $script:archives -eq 0) 'PROCESS_HOLD_NO_MUTATION'
 $script:scenario='health_unknown'
 Deny {Complete-V3ReleasePreArchiveInterrupted $ctx $oldJson $oldCms} 'DEGRADED_HEALTH_HOLD'
 Check (-not(Test-Path ($journalPath+'.pre-archive.json'))) 'UNHEALTHY_NEVER_CHECKPOINTS'
 $script:scenario='archive_unknown_before'
 Deny {Complete-V3ReleasePreArchiveInterrupted $ctx $oldJson $oldCms} 'INTERRUPTED_ARCHIVE'
 Check (Test-Path ($journalPath+'.pre-archive.json')) 'CHECKPOINT_DURABLE_ON_ARCHIVE_FAILURE'
 $checkpointSha=Get-V3ReleaseSha256 ([IO.File]::ReadAllBytes($journalPath+'.pre-archive.json'))
 $script:scenario='success'
 $result=Complete-V3ReleasePreArchiveInterrupted $ctx $oldJson $oldCms
 Check ($result.original_processes_continued -eq $true -and $script:enables -eq 0 -and $script:archives -eq 2) 'RECOVER_WITHOUT_TASK_REENABLE'
 Check ((Get-V3ReleaseSha256 ([IO.File]::ReadAllBytes($latchPath)) -ceq $latchSha) -and
   (Get-V3ReleaseSha256 ([IO.File]::ReadAllBytes($journalPath+'.pre-archive.json')) -ceq $checkpointSha)) 'DURABLE_ORIGINALS_UNCHANGED'
 Deny {Complete-V3ReleasePreArchiveInterrupted $ctx $oldJson $oldCms} 'REPLAY_AFTER_ARCHIVE_DENIED'
 Check ($script:enables -eq 0 -and $script:archives -eq 2) 'NO_DOUBLE_ENABLE_OR_ARCHIVE'
 foreach($leaseStream in $ctx.continuation_leases){$leaseStream.Dispose()}
 Write-Output ('V3_EXISTING_GATE_B_RECONCILIATION_OFFLINE_PASS='+$checks)
}finally{[IO.Directory]::Delete($temp,$true);$cert.Dispose();$rsa.Dispose()}
