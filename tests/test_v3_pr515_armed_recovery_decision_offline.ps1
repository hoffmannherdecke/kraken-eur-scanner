# Offline PR515 ARMED/QUIESCED policy test: ONLY extracted pure AST functions.
# No live operator, Windows Task, network, secrets or real CAS invocation.
$ErrorActionPreference='Stop'
$src=Join-Path (Split-Path $PSScriptRoot -Parent) 'tools/minipc-v3-paper-cutover-operator-INACTIVE.ps1'
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile(
 (Resolve-Path -LiteralPath $src),[ref]$tokens,[ref]$errors)
if(@($errors).Count){throw 'V3_PR515_AST_FAILED'}
$names=@('Test-V3ScopedIntakeTaskSet','Test-V3ScopedOriginalBackupContract',
 'Test-V3Pr515FreshRecoveryIdentity','Test-V3Pr515QuiescedRecoveryIdentity',
 'Test-V3Pr515ArmedRecoveryIdentity','Test-V3Pr515CurrentOriginalBackupManifest',
  'Test-V3Pr515DisabledOnlyXmlDifference','Test-V3PrecommitCurrentCloudInventory',
 'Get-V3Pr515TwoSourceCloudSnapshotReview','Read-V3ScopedPrecommitSnapshotFile',
 'Resolve-V3ScopedCutoverRecovery','Get-V3Pr515DisabledRestoreXmlForNativeValidation',
 'Test-V3IndependentOriginalHostCmsSignature','Test-V3Pr515SignedCurrentNoCasCustody',
 'Get-V3Pr515SignedCasAndCloudSeriesReview')
$fn=@($ast.FindAll({param($n)
 $n -is [Management.Automation.Language.FunctionDefinitionAst]},$true))
foreach($name in $names){
 $one=@($fn|Where-Object{$_.Name -ceq $name})
 if($one.Count -ne 1){throw "PURE_FUNCTION_MISSING: $name"}
 . ([scriptblock]::Create($one[0].Extent.Text))
}
# Existing signed/current and old-only snapshot sources must never be promoted
# to authenticated cloud authority or PRECOMMIT restore, even when both agree.
$fakeSigned=[pscustomobject]@{
 kind='V3_PR515_SIGNED_CURRENT_CAS_UNAVAILABLE_REVIEW_V1'
 status='SIGNED_CURRENT_NO_CAS_CAPABILITY_MATCH_NOT_RELEASE'
 signature_and_current_fence_match=$true
 current_notebook_reader_no_cas_capability_observed=$true
 previous_cas_attempts_excluded=$false
 authenticated_observed_at_utc=([datetimeoffset]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ss.ffffffZ'))
 precommit_task_restore_authorized=$false
}
$fencePin=('a'*64)
$cloudShape=[pscustomobject]@{
 kind='V3_PRECOMMIT_CURRENT_CLOUD_INVENTORY_V1'
 observed_at_utc=$fakeSigned.authenticated_observed_at_utc
 historically_cas_never_invoked_proven=$false
 precommit_restore_authorized=$false
 active_series_count=1
 exact_original_active_count=1
 recorded_v3_series_count=0
 recorded_v3_rotation_count=0
 recorded_v3_release_decision_count=0
 installed_v3_cas_function_count=0
 valid_single_active_index_count=1
}
$near=Get-V3Pr515SignedCasAndCloudSeriesReview -SignedCas $fakeSigned -Cloud $cloudShape -CurrentOriginalFenceSha256 $fencePin
if($near.observations_within_30_seconds -ne $true -or
 $near.disposition -cne 'REVIEW_ONLY_SIGNED_CAS_PLUS_UNAUTHENTICATED_PUBLIC_CLOUD_NOT_RELEASE' -or
 $near.native_stop_or_restore_authorized -ne $false){throw 'V3_CLOUD_NEAR_CAS_CLOCK_JOIN_REGRESSION'}
$oldCloud=$cloudShape.PSObject.Copy()
$oldCloud.observed_at_utc=([datetimeoffset]::UtcNow.AddSeconds(-40).ToString('yyyy-MM-ddTHH:mm:ss.ffffffZ'))
$skew=Get-V3Pr515SignedCasAndCloudSeriesReview -SignedCas $fakeSigned -Cloud $oldCloud -CurrentOriginalFenceSha256 $fencePin
if($skew.observations_within_30_seconds -ne $false -or
 $skew.disposition -cne 'HOLD_SIGNED_CAS_OR_CLOUD_INVENTORY_DRIFT'){throw 'V3_CLOUD_SKEW_ACCEPTED'}
$join=Get-V3Pr515SignedCasAndCloudSeriesReview -SignedCas $fakeSigned -Cloud $null -CurrentOriginalFenceSha256 $fencePin
if($join.disposition -cne 'HOLD_SIGNED_CAS_OR_CLOUD_INVENTORY_DRIFT' -or
 $join.native_stop_or_restore_authorized -ne $false -or
 $join.independent_public_cloud_origin_authenticated -ne $false){
 throw 'V3_SIGNED_CAS_PUBLIC_CLOUD_JOIN_FAILCLOSED_REGRESSION'
}
$wrongSigned=$fakeSigned.PSObject.Copy()
$wrongSigned.status='HOLD_SIGNED_CUSTODY_UNVERIFIED'
$join=Get-V3Pr515SignedCasAndCloudSeriesReview -SignedCas $wrongSigned -Cloud $null -CurrentOriginalFenceSha256 $fencePin
if($join.signed_current_cas_matched -ne $false -or $join.v3_paper_release_authorized -ne $false){
 throw 'V3_SIGNED_CAS_INVALID_SIGNATURE_ACCEPTED'
}
function Need($caseName,$actual,$expected){
 if([string]$actual -cne [string]$expected){
  throw "CASE $caseName got=$actual want=$expected"
 }
}
function Clone($o){$o|ConvertTo-Json -Depth 18 -Compress|ConvertFrom-Json}
# Real CMS signature, independently pinned public X509 SHA256 and current
# negative CAS posture are pure assertions. Positive SIGNED does NOT authorize
# restore; wrong hash, tampered bytes or timeout always HOLD.
$rsa=[Security.Cryptography.RSA]::Create(2048)
try {
 $request=[Security.Cryptography.X509Certificates.CertificateRequest]::new(
  'CN=V3-PR515-CI-Only', $rsa,
  [Security.Cryptography.HashAlgorithmName]::SHA256,
  [Security.Cryptography.RSASignaturePadding]::Pkcs1)
 $cert=$request.CreateSelfSigned([datetimeoffset]::UtcNow.AddMinutes(-2),
                                 [datetimeoffset]::UtcNow.AddMinutes(10))
 try{
  $sha=[Security.Cryptography.SHA256]::Create()
  try{
   $pin=([BitConverter]::ToString($sha.ComputeHash([byte[]]$cert.RawData))).Replace('-','').ToLowerInvariant()
  }finally{$sha.Dispose()}
  $fenceSha='a'*64
  $wire=[ordered]@{
   kind='V3_NOTEBOOK_CURRENT_NO_CAS_CAPABILITY_CUSTODY_V1'
   observed_at_utc=([datetimeoffset]::UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'",
     [Globalization.CultureInfo]::InvariantCulture))
   actor='v3_cas_audit_reader_actor';role='v3_cas_audit_reader'
   epochs=0;intents=0;installed_cas_rpc_count=0
   executor_login=$false;operator_can_set_executor=$false
   reader_writer_set_role=$false;reader_can_append=$false
   historical_cas_never_proven=$false;restore_authorized=$false
   original_fence_sha256=$fenceSha
  }
  $payload=[Text.UTF8Encoding]::new($false).GetBytes(($wire|ConvertTo-Json -Compress))
  $cms=[Security.Cryptography.Pkcs.SignedCms]::new(
   [Security.Cryptography.Pkcs.ContentInfo]::new([byte[]]$payload),$true)
  $signer=[Security.Cryptography.Pkcs.CmsSigner]::new($cert)
  $signer.DigestAlgorithm=[Security.Cryptography.Oid]::new('2.16.840.1.101.3.4.2.1')
  $cms.ComputeSignature($signer);$signature=[byte[]]$cms.Encode()
  $review=Test-V3Pr515SignedCurrentNoCasCustody -Payload $payload -Cms $signature -ReviewedCertSha256 $pin -CurrentOriginalFenceSha256 $fenceSha
  if($review.status -cne 'SIGNED_CURRENT_NO_CAS_CAPABILITY_MATCH_NOT_RELEASE' -or
     $review.signature_and_current_fence_match -ne $true -or
     $review.current_notebook_reader_no_cas_capability_observed -ne $true -or
     $review.previous_cas_attempts_excluded -ne $false -or
     $review.precommit_task_restore_authorized -ne $false -or
     $review.native_stop_authorized -ne $false){
   throw 'PR515_SIGNED_CUSTODY_AUTHENTIC_NEGATIVE_NOT_ACCEPTED_OR_FALSE_RELEASE'
  }
  foreach($variant in @(
   @{bytes=$payload;sig=$signature;pin=$pin;fence=('b'*64)},
   @{bytes=$payload;sig=$signature;pin=('c'*64);fence=$fenceSha},
   @{bytes=$payload;sig=([byte[]]@(0,1,2));pin=$pin;fence=$fenceSha},
   @{bytes=([Text.UTF8Encoding]::new($false).GetBytes(($wire|ConvertTo-Json -Compress).Replace(
    '"installed_cas_rpc_count":0','"installed_cas_rpc_count":1')));sig=$signature;pin=$pin;fence=$fenceSha}
  )){
   $bad=Test-V3Pr515SignedCurrentNoCasCustody -Payload $variant.bytes -Cms $variant.sig -ReviewedCertSha256 $variant.pin -CurrentOriginalFenceSha256 $variant.fence
   if($bad.status -cne 'HOLD_SIGNED_CUSTODY_UNVERIFIED'){
    throw 'PR515_SIGNED_CUSTODY_REPLAY_TAMPER_OR_WRONG_CERT_ACCEPTED'
   }
  }
  foreach($flip in @('executor_login','operator_can_set_executor',
                     'reader_writer_set_role','reader_can_append','restore_authorized')){
   $neg=[ordered]@{}
   foreach($k in $wire.Keys){$neg[$k]=$wire[$k]}
   $neg[$flip]=$true
   $bytes=[Text.UTF8Encoding]::new($false).GetBytes(($neg|ConvertTo-Json -Compress))
   $signed=[Security.Cryptography.Pkcs.SignedCms]::new(
    [Security.Cryptography.Pkcs.ContentInfo]::new([byte[]]$bytes),$true)
   $signed.ComputeSignature($signer)
   $bad=Test-V3Pr515SignedCurrentNoCasCustody -Payload $bytes -Cms ([byte[]]$signed.Encode()) -ReviewedCertSha256 $pin -CurrentOriginalFenceSha256 $fenceSha
   if($bad.status -cne 'HOLD_SIGNED_CUSTODY_UNVERIFIED'){
    throw ('PR515_SIGNED_CUSTODY_UNSAFE_NEGATIVE_POSTURE_ACCEPTED_'+$flip)
   }
  }
  Write-Output 'V3_PR515_SIGNED_CURRENT_CAS_CUSTODY_CRYPTO_NEGATIVE_TESTS_PASS_NO_RESTORE'
 }finally{$cert.Dispose()}
}finally{$rsa.Dispose()}

$names2=@('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait')
$xml=@(('a'*64),('b'*64))
$entries=@()
foreach($i in 0,1){
 $entries+=([pscustomobject]@{
  task_name=$names2[$i];xml_sha256=$xml[$i];action_sha256='f'*64
  original_enabled=$true;original_running=$true;original_principal_system=$true
  one_original_boot_trigger=$true;restart_count=3
  restart_interval='PT1M';multiple_instances='IgnoreNew'
 })
}
$backup=[pscustomobject]@{
 kind='V3_PRECAS_NATIVE_XML_BACKUP_ORIGINALHOST_V1'
 status='ORIGINAL_TASK_XML_BACKUP_ONLY_NOT_RELEASED'
 predecessor_series_id='PAPER-V2R4-20261009T110135Z'
 checked_at_utc=[datetimeoffset]::UtcNow.ToString('o')
 backup_directory=('C:\Users\ADMIN\Trading\State\V3Paper-PreCAS-Backup-'+'1'*32)
 native_task_count=2;original_tasks_still_running=$true
 scheduler_task_mutations=$false;original_v2r4_changed=$false
 cloud_cas_invoked=$false;new_v3_writer_started=$false
 original_cloud_series_independently_checked=$false
 v3_release_or_six_proofs_credited=0
 task_records=@(
  [pscustomobject]@{task_name=$names2[0];xml_file='Candidates.task.xml';xml_sha256=$xml[0];action_sha256='f'*64},
  [pscustomobject]@{task_name=$names2[1];xml_file='WAIT.task.xml';xml_sha256=$xml[1];action_sha256='e'*64}
 )
}
if(-not(Test-V3Pr515CurrentOriginalBackupManifest $backup)){throw 'ACTUAL_PR515_BACKUP_NOT_ACCEPTED'}
foreach($bad in @(
 @{key='kind';value='V3_OLD_INTAKE_BACKUP_PROPOSAL_V1'},
 @{key='native_task_count';value=3},
 @{key='backup_directory';value='C:\Other\backup'},
 @{key='original_v2r4_changed';value=$true}
)){
 $negative=Clone $backup
 $negative.($bad.key)=$bad.value
 if(Test-V3Pr515CurrentOriginalBackupManifest $negative){
  throw ('ACTUAL_PR515_BACKUP_FOREIGN_ACCEPTED_'+$bad.key)
 }
}
$negative=Clone $backup;$negative.task_records[1].xml_file='../wrong.xml'
if(Test-V3Pr515CurrentOriginalBackupManifest $negative){throw 'BACKUP_TRAVERSAL_ACCEPTED'}
$negative=Clone $backup;$negative.task_records[1].xml_sha256=$xml[0]
if(Test-V3Pr515CurrentOriginalBackupManifest $negative){throw 'BACKUP_DUPLICATE_XML_SHA_ACCEPTED'}

$pre=[pscustomobject]@{
 kind='V3_PRECAS_PR515_FRESH_BACKUP_READONLY_COMPATIBILITY_V1'
 status='COMPATIBLE_READONLY_NOT_RELEASED'
 current_backup_directory_leaf=('V3Paper-PreCAS-Backup-'+'1'*32)
 pr515_source_sha256='d'*64;current_native_task_xml_sha256=$xml
 current_backup_valid_while_intakes_running_only=$true
 preview_is_not_poststop_or_independent_cloud_ack=$true
 two_current_native_xml_reread_pass=$true
 pr515_effective_cloudsync_source_consistent=$true
 external_sha_pin_independently_authenticated=$false
 physical_task_restore_tested=$false;scheduler_task_mutations=$false
 cloud_cas_invoked=$false;v3_paper_activated=$false
 technical_release_proofs_credited=0
}
$post=[pscustomobject]@{
 kind='V3_PRECAS_PR515_ARMED_POSTSTOP_READONLY_COMPATIBILITY_V1'
 status='ARMED_DISABLED_NATIVE_SOURCE_MATCH_NOT_RELEASED'
 current_backup_directory_leaf=$pre.current_backup_directory_leaf
 pr515_source_sha256=$pre.pr515_source_sha256
 current_native_task_xml_sha256=$xml
 after_disable_enabled_only_native_xml_comparison=$true
 poststop_disabled_only_native_xml_recheck_pass=$true
 single_local_supervisor_pr515_armed_observation_only=$true
 single_local_supervisor_pr515_quiesced_observation_only=$false
 two_distinct_supervisor_cycles_verified=$false
 old_intake_pid_family_absence_independently_verified=$false
 independent_cloud_cas_never_invoked_verified=$false
 two_current_native_xml_reread_pass=$false
 current_backup_valid_while_intakes_running_only=$false
 preview_is_not_poststop_or_independent_cloud_ack=$false
 local_poststop_snapshot_is_not_independent_cloud_ack=$true
 pr515_effective_cloudsync_source_consistent=$true
 external_sha_pin_independently_authenticated=$false
 physical_task_restore_tested=$false;scheduler_task_mutations=$false
 cloud_cas_invoked=$false;v3_paper_activated=$false
 technical_release_proofs_credited=0
}
$cloud=[pscustomobject]@{
 kind='V3_PRECOMMIT_CURRENT_CLOUD_INVENTORY_V1'
 observed_at_utc=[datetimeoffset]::UtcNow.ToString('o')
 historically_cas_never_invoked_proven=$false;precommit_restore_authorized=$false
 active_series_count=1;exact_original_active_count=1
 recorded_v3_series_count=0;recorded_v3_rotation_count=0
 recorded_v3_release_decision_count=0;installed_v3_cas_function_count=0
 valid_single_active_index_count=1
}
$r=[pscustomobject]@{
 kind='V3_CUTOVER_RECOVERY_SIMULATION_V1'
 predecessor_series_id='PAPER-V2R4-20261009T110135Z'
 task_names=$names2;phase='ARMED';fence_marker_phase='ARMED'
 cloud_cas_invoked=$false;cloud_cas_outcome='NOT_INVOKED'
 v3_writer_started=$false;paper_only=$true;real_money_actions=$false
 native_intake_tasks_disabled_ack=$true
 original_intake_processes_absent_ack=$true
 windows_supervisor_no_rearm_ack=$true
 protected_lifecycle_cloudsync_running_ack=$true
 old_cloud_single_active_readback=$true;new_v3_series_absent_readback=$true
 backup_manifest=$backup;backup_contract_verified=$true
 current_pr515_readonly_preview=$pre;current_pr515_armed_readonly_preview=$post
 pr515_sha_pin_separately_verified=$true
 fresh_current_xml_after_armed_independently_checked=$true
 independent_cloud_precommit_cas_never_invoked_ack=$true
 independent_cloud_old_only_after_armed_ack=$true
 current_prod_cloud_inventory=$cloud
}
Need 'ARMED fully stopped' (Resolve-V3ScopedCutoverRecovery $r).disposition 'HOLD_ARMED_UNAUTHENTICATED_EXTERNAL_CLOUD_CAS_CUSTODY'
$x=Clone $r;$x.native_intake_tasks_disabled_ack=$false
Need 'partial STOP' (Resolve-V3ScopedCutoverRecovery $x).disposition 'HOLD_ARMED_PARTIAL_STOP_MANUAL_INCIDENT_NO_REARM'
$x=Clone $r;$x.cloud_cas_outcome='UNKNOWN'
Need 'unknown CAS' (Resolve-V3ScopedCutoverRecovery $x).disposition 'HOLD_CAS_ATTEMPTED_MANUAL_CLOUD_RECONCILIATION'
$x=Clone $r;$x | Add-Member -NotePropertyName local_predispatch_unknown_latch_present -NotePropertyValue $true
Need 'local persisted UNKNOWN with NOT_INVOKED flag' (Resolve-V3ScopedCutoverRecovery $x).disposition 'HOLD_PERSISTED_PREINVOKE_OR_LOCAL_UNKNOWN_NO_REARM'
$x=Clone $r;$x | Add-Member -NotePropertyName any_committed_preinvoke_intent_observed -NotePropertyValue $true
Need 'already committed intent with NOT_INVOKED flag' (Resolve-V3ScopedCutoverRecovery $x).disposition 'HOLD_PERSISTED_PREINVOKE_OR_LOCAL_UNKNOWN_NO_REARM'
$x=Clone $r;$x.fence_marker_phase='QUIESCED'
Need 'unbound ARMED marker' (Resolve-V3ScopedCutoverRecovery $x).disposition 'HOLD_FENCE_MANUAL_RECONCILIATION'
$x=Clone $r;$x.current_pr515_armed_readonly_preview.status='INVALID'
Need 'wrong backup state' (Resolve-V3ScopedCutoverRecovery $x).disposition 'HOLD_ARMED_CURRENT_BACKUP_OR_INDEPENDENT_CLOUD_ACK'
$x=Clone $r;$x.current_prod_cloud_inventory.observed_at_utc='2024-01-01T00:00:00Z'
Need 'stale Cloud' (Resolve-V3ScopedCutoverRecovery $x).disposition 'HOLD_ARMED_CURRENT_BACKUP_OR_INDEPENDENT_CLOUD_ACK'
$x=Clone $r;$x.independent_cloud_precommit_cas_never_invoked_ack=$false
Need 'external CAS ack absent' (Resolve-V3ScopedCutoverRecovery $x).disposition 'HOLD_ARMED_CURRENT_BACKUP_OR_INDEPENDENT_CLOUD_ACK'
$x=Clone $r;$x.phase='QUIESCED';$x.fence_marker_phase='QUIESCED'
# ConvertFrom-Json may auto-parse ISO timestamps. The live validator expects
# the exact UTC string emitted by the Cloud reader, not local DateTime text.
$x.current_prod_cloud_inventory.observed_at_utc=[datetimeoffset]::UtcNow.ToString('o')
$x | Add-Member -NotePropertyName current_pr515_quiesced_readonly_preview -NotePropertyValue (Clone $post)
$x.current_pr515_quiesced_readonly_preview.kind='V3_PRECAS_PR515_QUIESCED_READONLY_COMPATIBILITY_V1'
$x.current_pr515_quiesced_readonly_preview.status='QUIESCED_NATIVE_SOURCE_MATCH_NOT_RELEASED'
$x.current_pr515_quiesced_readonly_preview.single_local_supervisor_pr515_quiesced_observation_only=$true
$x | Add-Member -NotePropertyName fresh_current_xml_after_quiesce_independently_checked -NotePropertyValue $true
$x | Add-Member -NotePropertyName independent_cloud_old_only_after_quiesce_ack -NotePropertyValue $true
Need 'QUIESCED backwards compatible' (Resolve-V3ScopedCutoverRecovery $x).disposition 'HOLD_QUIESCED_UNAUTHENTICATED_EXTERNAL_CLOUD_CAS_CUSTODY'
$x.fence_marker_phase='ARMED'
Need 'unbound QUIESCED marker' (Resolve-V3ScopedCutoverRecovery $x).disposition 'HOLD_FENCE_MANUAL_RECONCILIATION'
$raw=Get-Content -LiteralPath $src -Raw
$a=$raw.IndexOf('function Invoke-V3Pr515PrecommitRestoreSOURCE_ONLY(')
$b=$raw.IndexOf('# Native TaskScheduler disable may change exactly one XML field:',$a)
if($a -lt 0 -or $b -le $a){throw 'RESTORE_SCOPE_INVALID'}
$restore=$raw.Substring($a,$b-$a)
$first=$restore.IndexOf("throw 'V3_PR515_PRECOMMIT_RESTORE_SOURCE_UNCONDITIONALLY_LOCKED'")
$second=$restore.IndexOf("throw 'V3_PRECOMMIT_INDEPENDENT_CLOUD_CAS_AUTHORITY_NOT_WIRED'")
$write=$restore.IndexOf('Enable-ScheduledTask')
if($first -lt 0 -or $second -le $first -or $write -le $second){
 throw 'RESTORE_EXECUTION_LOCK_DRIFT'
}
# Originalhost PR618 proves Saved Task may omit Settings/Enabled.
# Post-STOP COM XML may add exactly Enabled=false, not change anything else.
$ns='http://schemas.microsoft.com/windows/2004/02/mit/task'
$original='<Task xmlns="'+$ns+'"><Settings><Hidden>false</Hidden></Settings><Actions><Exec><Command>python.exe</Command></Exec></Actions></Task>'
$disabled=$original.Replace('<Hidden>false</Hidden>','<Hidden>false</Hidden><Enabled>false</Enabled>')
if(-not(Test-V3Pr515DisabledOnlyXmlDifference $original $disabled)){
 throw 'PR515_MISSING_OPTIONAL_ENABLED_POSTSTOP_FALSE_FAILURE'
}
$explicit=$original.Replace('<Hidden>false</Hidden>','<Enabled>true</Enabled><Hidden>false</Hidden>')
if(-not(Test-V3Pr515DisabledOnlyXmlDifference $explicit $disabled)){
 throw 'PR515_EXPLICIT_ENABLED_POSTSTOP_FALSE_FAILURE'
}
foreach($bad in @(
 $disabled.Replace('<Command>python.exe</Command>','<Command>other.exe</Command>'),
 $disabled.Replace('<Hidden>false</Hidden>','<Hidden>true</Hidden>'),
 $disabled.Replace('<Enabled>false</Enabled>','<Enabled>true</Enabled>'),
 $disabled.Replace('<Enabled>false</Enabled>','<Enabled>false</Enabled><Enabled>false</Enabled>'),
 $disabled.Replace('<Settings>','<Settings xmlns="urn:foreign">')
)){
 if(Test-V3Pr515DisabledOnlyXmlDifference $original $bad){
  throw 'PR515_NON_ENABLED_XML_CHANGE_ACCEPTED'
 }
}
Write-Output 'V3_PR515_REAL_ORIGINAL_BACKUP_AND_ENABLED_DEFAULT_NEGATIVE_TESTS_PASS'

Write-Output 'V3_PR515_ELEVEN_ISOLATED_STATE_CASES_PASS_NO_HOST_IO_NO_RELEASE'


# NEW existing originalhost CLI entry; exercise real script path on temporary
# read-only inputs. Never Windows Tasks, Admin, Cloud, DPAPI or real CAS.
$root=Join-Path ([IO.Path]::GetTempPath()) ('v3-pr515-two-source-ci-'+[guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($root)
try{
 $readerPath=Join-Path $root 'notebook-reader.json'
 $cloudPath=Join-Path $root 'cloud-inventory.json'
 $utc=[datetimeoffset]::UtcNow.ToString(
  "yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'",
  [Globalization.CultureInfo]::InvariantCulture)
 $reader=[ordered]@{
  kind='V3_CAS_READER_CURRENT_PRIVATE_AUDIT_SNAPSHOT_V1'
  status='AUTHENTICATED_READER_CURRENT_EMPTY_NOT_HISTORICAL_NEVER'
  observed_at_utc=$utc;epoch_count=0;intent_count=0
  actor='v3_cas_audit_reader_actor';role='v3_cas_audit_reader'
  independent_tls_certificate_verified=$false
  independent_attempt_history_complete=$false
  historical_cas_never_proven=$false
  public_old_only_series_verified_here=$false
  native_rearm_authorized=$false;precommit_restore_authorized=$false
  cloud_cas_authorized=$false;v3_paper_release_authorized=$false
 }
 $cloud=[ordered]@{
  kind='V3_PRECOMMIT_CURRENT_CLOUD_INVENTORY_V1'
  observed_at_utc=$utc
  historically_cas_never_invoked_proven=$false
  precommit_restore_authorized=$false
  active_series_count=1;exact_original_active_count=1
  recorded_v3_series_count=0;recorded_v3_rotation_count=0
  recorded_v3_release_decision_count=0
  installed_v3_cas_function_count=0
  valid_single_active_index_count=1
 }
 [IO.File]::WriteAllText($readerPath,($reader|ConvertTo-Json -Compress),
  [Text.UTF8Encoding]::new($false))
 [IO.File]::WriteAllText($cloudPath,($cloud|ConvertTo-Json -Compress),
  [Text.UTF8Encoding]::new($false))
 # Running this normal READONLY CLI is safe even on CI Linux: the new mode
 # returns before Get-ScheduledTask, WMI, source file installation or secrets.
 $out=@(& $src -TradingRoot $root -ReviewExistingTwoSourcePrecommit -ExistingNotebookReaderJson $readerPath -ExistingCloudInventoryJson $cloudPath)
 if($out.Count -ne 1){throw 'V3_TWO_SOURCE_ORIGINALHOST_CLI_NOT_SINGLE_STATUS'}
 $ack=$out[0]|ConvertFrom-Json
 if($ack.disposition -cne 'REVIEW_ONLY_CURRENT_OLD_ONLY_AND_READER_EMPTY_CAS_HISTORY_UNKNOWN' -or
    $ack.independently_authenticated_here -ne $false -or
    $ack.complete_historical_cas_never_proven -ne $false -or
    $ack.originalhost_quiesced_or_precommit_restore_authorized -ne $false -or
    $ack.native_rearm_or_cloud_cas_authorized -ne $false -or
    $ack.v3_paper_release_authorized -ne $false){
  throw 'V3_TWO_SOURCE_REVIEW_NOT_FAIL_CLOSED'
 }
 # All negative controls are local files. The pure parser rejects injection
 # and unsigned sources; the policy review refuses stale and non-empty rows.
 $original=[IO.File]::ReadAllText($readerPath)
 foreach($bad in @(
  $original.Replace('"intent_count":0','"intent_count":1'),
  $original.Replace('"role":"v3_cas_audit_reader"','"role":"v3_cas_executor"'),
  $original.Replace('"kind":','"release_authorized":true,"kind":'),
  $original.Replace('"epoch_count":0','"epoch_count":0,"epoch_count":0'),
  $original.Replace($utc,'2026-10-01T00:00:00.000000Z')
 )){
  [IO.File]::WriteAllText($readerPath,$bad,[Text.UTF8Encoding]::new($false))
  try{
   $parsed=Read-V3ScopedPrecommitSnapshotFile -Path $readerPath -ExactKeys @($reader.Keys)
   $v=Get-V3Pr515TwoSourceCloudSnapshotReview -Reader $parsed -Cloud (
     Read-V3ScopedPrecommitSnapshotFile -Path $cloudPath -ExactKeys @($cloud.Keys))
   if($v.disposition -ceq 'REVIEW_ONLY_CURRENT_OLD_ONLY_AND_READER_EMPTY_CAS_HISTORY_UNKNOWN'){
    throw 'V3_TWO_SOURCE_BAD_READER_ACCEPTED'
   }
  }catch{
   if($_.Exception.Message -eq 'V3_TWO_SOURCE_BAD_READER_ACCEPTED'){throw}
  }
 }
 [IO.File]::WriteAllText($readerPath,$original,[Text.UTF8Encoding]::new($false))
 $old=[IO.File]::ReadAllText($cloudPath)
 [IO.File]::WriteAllText($cloudPath,$old.Replace('"installed_v3_cas_function_count":0','"installed_v3_cas_function_count":1'),[Text.UTF8Encoding]::new($false))
 $changed=Read-V3ScopedPrecommitSnapshotFile -Path $cloudPath -ExactKeys @($cloud.Keys)
 $review=Get-V3Pr515TwoSourceCloudSnapshotReview -Reader (
   Read-V3ScopedPrecommitSnapshotFile -Path $readerPath -ExactKeys @($reader.Keys)) -Cloud $changed
 if($review.disposition -ceq 'REVIEW_ONLY_CURRENT_OLD_ONLY_AND_READER_EMPTY_CAS_HISTORY_UNKNOWN'){
  throw 'V3_TWO_SOURCE_INSTALLED_CAS_RISK_ACCEPTED'
 }
 Write-Output 'V3_PR515_TWO_EXISTING_CLOUD_SOURCES_ACTUAL_READONLY_CLI_PASS_NO_RELEASE'
} finally {
 if([IO.Directory]::Exists($root)){[IO.Directory]::Delete($root,$true)}
}



# Physical failure regression from 28 October PR617: the Windows Task Scheduler
# settingsType schema has xs:all/Enabled minOccurs=0 default=true. A missing
# explicit Enabled MUST still derive disabled XML for native validate-only;
# a real explicitly disabled original, duplicate or alien namespace fails shut.
$ns='http://schemas.microsoft.com/windows/2004/02/mit/task'
$xmlOriginal='<Task xmlns="'+$ns+'" version="1.4"><Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><Hidden>false</Hidden></Settings></Task>'
$derived=Get-V3Pr515DisabledRestoreXmlForNativeValidation -OriginalXml $xmlOriginal
if($xmlOriginal.Contains('<Enabled>') -or
   @($derived|Select-String -Pattern '<Enabled>false</Enabled>').Count -ne 1){
 throw 'V3_RESTORE_OPTIONAL_ENABLED_DEFAULT_NOT_HANDLED'
}
$asXml=[xml]$derived
$settingNodes=@($asXml.SelectNodes('/*[local-name()="Task"]/*[local-name()="Settings"]/*[local-name()="Enabled"]'))
if($settingNodes.Count -ne 1 -or [string]$settingNodes[0].InnerText -cne 'false'){
 throw 'V3_RESTORE_OPTIONAL_ENABLED_DERIVED_INCORRECTLY'
}
foreach($value in @('true','1')){
 $explicit=$xmlOriginal.Replace('<Hidden>false</Hidden>',"<Enabled>$value</Enabled><Hidden>false</Hidden>")
 $tested=Get-V3Pr515DisabledRestoreXmlForNativeValidation -OriginalXml $explicit
 if($tested -notmatch '<Enabled>false</Enabled>'){
  throw 'V3_RESTORE_EXPLICIT_ENABLED_TRUE_REJECTED'
 }
}
foreach($invalid in @(
 $xmlOriginal.Replace('<Hidden>false</Hidden>','<Enabled>false</Enabled><Hidden>false</Hidden>'),
 $xmlOriginal.Replace('<Hidden>false</Hidden>','<Enabled>true</Enabled><Enabled>true</Enabled><Hidden>false</Hidden>'),
 $xmlOriginal.Replace('<Settings>','<Settings xmlns="urn:foreign">'),
 $xmlOriginal.Replace('<Settings>','<OtherSettings>').Replace('</Settings>','</OtherSettings>')
)){
 $rejected=$false
 try{[void](Get-V3Pr515DisabledRestoreXmlForNativeValidation -OriginalXml $invalid)}
 catch{$rejected=$true}
 if(-not $rejected){throw 'V3_RESTORE_EXPLICITLY_DISABLED_DUPLICATE_OR_FOREIGN_XML_ACCEPTED'}
}
Write-Output 'V3_PR617_OPTIONAL_ENABLED_DEFAULT_REAL_XML_REGRESSION_PASS'

# PR515 native Scheduler XML VALIDATE_ONLY integration: source/static CI is
# not a physical Windows ACK. Exact mode is opt-in, no Task register/update.
$full=Get-Content -LiteralPath $src -Raw -ErrorAction Stop
$validateStart=$full.IndexOf('if($ValidatePr515RestoreXml) {', $full.IndexOf('$completeWaitSnapshot='))
$nextMode=$full.IndexOf('if($PreviewPr515ArmedTwoCycle) {', $validateStart)
if($validateStart -lt 0 -or $nextMode -le $validateStart){
 throw 'PR515_SCHEDULER_VALIDATION_ENTRY_NOT_CONNECTED'
}
$validation=$full.Substring($validateStart,$nextMode-$validateStart)
if(@([regex]::Matches($validation,[regex]::Escape('.RegisterTask('))).Count -ne 2 -or
   @([regex]::Matches($validation,',1,\$null,\$null,5\)')).Count -ne 2 -or
   $validation -notmatch 'Test-V3FreshBackupFileBytes' -or
   $validation -notmatch 'Test-V3Pr515FreshRecoveryIdentity' -or
   $validation -notmatch 'REAL_SCHEDULER_XML_VALIDATION_PASS_NO_RESTORE' -or
   $validation -notmatch 'actual_restore_executed=\$false' -or
   $validation -notmatch 'independent_cloud_cas_custody_proven=\$false' -or
   $validation -match 'Enable-ScheduledTask|Disable-ScheduledTask|Stop-ScheduledTask|Start-ScheduledTask|Register-ScheduledTask|Unregister-ScheduledTask|Remove-Item'){
 throw 'PR515_SCHEDULER_VALIDATE_ONLY_BOUNDARY_DRIFT'
}
Write-Output 'V3_PR515_TASK_SCHEDULER_VALIDATE_ONLY_SOURCE_GUARD_PASS_NO_RUNTIME_ACK'
