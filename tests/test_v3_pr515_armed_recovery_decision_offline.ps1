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
 'Test-V3Pr515ArmedRecoveryIdentity','Test-V3PrecommitCurrentCloudInventory',
 'Resolve-V3ScopedCutoverRecovery')
$fn=@($ast.FindAll({param($n)
 $n -is [Management.Automation.Language.FunctionDefinitionAst]},$true))
foreach($name in $names){
 $one=@($fn|Where-Object{$_.Name -ceq $name})
 if($one.Count -ne 1){throw "PURE_FUNCTION_MISSING: $name"}
 . ([scriptblock]::Create($one[0].Extent.Text))
}
function Need($caseName,$actual,$expected){
 if([string]$actual -cne [string]$expected){
  throw "CASE $caseName got=$actual want=$expected"
 }
}
function Clone($o){$o|ConvertTo-Json -Depth 18 -Compress|ConvertFrom-Json}
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
 kind='V3_OLD_INTAKE_BACKUP_PROPOSAL_V1'
 predecessor_series_id='PAPER-V2R4-20261009T110135Z'
 old_stage_release_sha='c'*40;paper_only=$true
 real_money_actions=$false;task_records=$entries
}
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
Need 'ARMED fully stopped' (Resolve-V3ScopedCutoverRecovery $r).disposition 'PRE_CAS_ARMED_MANUAL_RESTORE_REVIEW_CANDIDATE_NOT_EXECUTABLE'
$x=Clone $r;$x.native_intake_tasks_disabled_ack=$false
Need 'partial STOP' (Resolve-V3ScopedCutoverRecovery $x).disposition 'HOLD_ARMED_PARTIAL_STOP_MANUAL_INCIDENT_NO_REARM'
$x=Clone $r;$x.cloud_cas_outcome='UNKNOWN'
Need 'unknown CAS' (Resolve-V3ScopedCutoverRecovery $x).disposition 'HOLD_CAS_ATTEMPTED_MANUAL_CLOUD_RECONCILIATION'
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
Need 'QUIESCED backwards compatible' (Resolve-V3ScopedCutoverRecovery $x).disposition 'PRE_CAS_MANUAL_ROLLBACK_REVIEW_CANDIDATE'
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
Write-Output 'V3_PR515_NINE_ISOLATED_STATE_CASES_PASS_NO_HOST_IO_NO_RELEASE'
