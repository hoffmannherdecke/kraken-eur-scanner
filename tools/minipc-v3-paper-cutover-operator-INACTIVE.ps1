param(
 [string]$TradingRoot=(Join-Path $env:USERPROFILE 'Trading'),
 [switch]$Execute,
 [switch]$BackupOriginalIntake,
 [string]$ExpectedCandidatesActionSha256='',
 [string]$ExpectedWaitActionSha256='',
 [switch]$PreviewPr515PreCas,
 [switch]$PreviewPr515Quiesced,
 [switch]$PreviewPr515Armed,
 [switch]$PreviewPr515ArmedTwoCycle,
 [switch]$ValidatePr515RestoreXml,
 [string]$OriginalBackupDirectory='',
 [string]$ExpectedPr515SourceSha256='',
 [string]$ExpectedArmedFenceSha256='',
 [string]$Confirm='',
 [switch]$VerifyNotebookPrecommitCms,
 [string]$NotebookReaderJson='',
 [string]$NotebookReaderCms='',
 [string]$ReviewedNotebookCertificateSha256='',
 [switch]$ReviewExistingTwoSourcePrecommit,
 [switch]$ReviewSignedCurrentCasCustody,
 [string]$ExpectedCurrentFenceSha256='',
 [string]$ExistingNotebookReaderJson='',
 [string]$ExistingCloudInventoryJson=''
)
# V3 experimental Paper scoped operator: SOURCE PREPARATION ONLY.
# GitHub/CI draft; not an installed cutover, not a stop, not a rollback.
# No host, Task, PID, marker, database, secret, or Cloud writes.
$ErrorActionPreference='Stop'

# Pure readiness policy, executable by existing offline CI without running
# any host commands. These checks are only PRE-CUTOVER discovery.
function Test-V3CutoverPreparationPolicy([object]$Report,[bool]$FenceMarkerPresent,[bool]$MaintenanceMarkerPresent) {
 if($null -eq $Report -or $FenceMarkerPresent -or $MaintenanceMarkerPresent){return $false}
 if([string]$Report.kind -cne 'V3_MINIPC_SINGLE_WRITER_PHYSICAL_READONLY_PREFLIGHT_V1'){return $false}
 if([string]$Report.pre_cutover_expected_predecessor_series_id -cne 'PAPER-V2R4-20261009T110135Z'){return $false}
 if($Report.native_old_intake_precutover_readonly_baseline_pass -ne $true -or
    $Report.native_old_paper_mode_lineage_precutover_readonly_pass -ne $true -or
    $Report.native_old_paper_mode_lineage_snapshot_only_no_stop_authority -ne $true){return $false}
 if($Report.new_v3_writer_started -ne $false -or $Report.v2r4_changed -ne $false){return $false}
 $roles=@{
   'CryptoMiniPC-V2R4PaperCandidates'='v2r4-paper-local-runtime.py'
   'CryptoMiniPC-V2R4PaperWait'='wait_launcher.py'
   'CryptoMiniPC-V2R4PaperLifecycle'='v2r4-paper-local-runtime.py'
   'CryptoMiniPC-V2R4PaperCloudSync'='v2r4-paper-cloud-sync.py'
 }
 $rows=@($Report.physical_v2r4_paper_task_readback)
 if($rows.Count -ne 4){return $false}
 foreach($name in @($roles.Keys)){
   $one=@($rows | Where-Object { [string]$_.task_name -ceq $name })
   if($one.Count -ne 1){return $false}
   $item=$one[0]
   if([string]$item.state -cne 'Running' -or
      [int]$item.action_count -ne 1 -or
      [string]$item.action_script_basename -cne $roles[$name] -or
      $item.documented_script_basename_hint_matches -ne $true -or
      $item.principal_is_system -ne $true -or
      $item.heartbeat_fresh_for_role -ne $true){return $false}
 }
 # Mode lineage is validated by the original PR313 source, NOT re-created.
 # A transient PID record never becomes authority to kill a PID or task.
 return $true
}

# Pure closed-descendants guard. A two-Python-process match alone cannot show
# whether a WAIT root has an unexpected non-Python or deeper child process.
# Snapshot only: NEVER convert these PIDs into a stop list.
function Test-V3WaitCompleteReadOnlyFamily(
 [object[]]$WaitRows,
 [object[]]$AllProcesses,
 [bool]$WaitActionObserved,
 [int[]]$ProtectedRolePids
) {
 if(-not $WaitActionObserved){return $false}
 $wait=@($WaitRows)
 # Windows ProcessId 0 is the kernel Idle pseudo-process, never a WAIT descendant.
 $all=@($AllProcesses | Where-Object {[int]$_.PID -ne 0})
 if($wait.Count -ne 2 -or $all.Count -lt 2){return $false}
 $ids=@($wait | ForEach-Object {[int]$_.PID})
 if(@($ids | Where-Object {$_ -le 0}).Count -ne 0 -or
    @($ids | Select-Object -Unique).Count -ne 2){return $false}
 if(@($wait | Where-Object {$_.OriginalStage -ne $true}).Count -ne 0){return $false}
 if(@($ProtectedRolePids | Where-Object {$_ -in $ids}).Count -gt 0){return $false}
 $allIds=@($all | ForEach-Object {[int]$_.PID})
 if(@($allIds | Where-Object {$_ -le 0}).Count -gt 0 -or
    @($allIds | Select-Object -Unique).Count -ne $all.Count){return $false}
 foreach($w in $wait){
  $edge=@($all | Where-Object {[int]$_.PID -eq [int]$w.PID})
  if($edge.Count -ne 1 -or [int]$edge[0].ParentPID -ne [int]$w.ParentPID){return $false}
 }
 $children=@($wait | Where-Object {[int]$_.ParentPID -in $ids})
 if($children.Count -ne 1){return $false}
 $child=$children[0]
 $root=@($wait | Where-Object {[int]$_.PID -ne [int]$child.PID})
 if($root.Count -ne 1 -or [int]$root[0].ParentPID -le 0 -or
    [int]$root[0].ParentPID -in $ids -or
    [int]$child.ParentPID -ne [int]$root[0].PID){return $false}
 # Reject unknown children by default. The sole exception is ONE console
 # host attested by an independent, live System32/Microsoft signature check.
 # The check must remain scoped to the verified WAIT ROOT (not a child/other role).
 $extras=@($all | Where-Object {
  [int]$_.ParentPID -in $ids -and [int]$_.PID -ne [int]$child.PID
 })
 if($extras.Count -gt 1){return $false}
 if($extras.Count -eq 1){
  $con=$extras[0]
  if([int]$con.PID -le 0 -or
     [string]$con.Name -ine 'conhost.exe' -or
     [int]$con.ParentPID -ne [int]$root[0].PID -or
     $con.TrustedConsoleHost -ne $true -or
     [int]$con.PID -in @($ProtectedRolePids)){return $false}
  if(@($all | Where-Object {[int]$_.ParentPID -eq [int]$con.PID}).Count -gt 0){
   return $false
  }
 }
 return $true
}

# Pure V3 single-writer contract: ONLY original intake Tasks may ever be changed.
# No host operations; return boolean for offline negative tests.
function Test-V3ScopedIntakeTaskSet([object[]]$Names) {
 $expected=@('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait' | Sort-Object)
 $got=@($Names | ForEach-Object {[string]$_} | Sort-Object)
 return ($got.Count -eq 2 -and ($got -join '|') -ceq ($expected -join '|'))
}

# Backup manifest is a PROPOSED contract. These strings/booleans are not
# evidence that files were written or that a real physical backup exists.
function Test-V3ScopedOriginalBackupContract([object]$Manifest) {
 if($null -eq $Manifest -or
    [string]$Manifest.kind -cne 'V3_OLD_INTAKE_BACKUP_PROPOSAL_V1' -or
    [string]$Manifest.predecessor_series_id -cne 'PAPER-V2R4-20261009T110135Z' -or
    [string]$Manifest.old_stage_release_sha -cnotmatch '^[a-f0-9]{40}$' -or
    $Manifest.paper_only -ne $true -or
    $Manifest.real_money_actions -ne $false){return $false}
 $entries=@($Manifest.task_records)
 if(-not(Test-V3ScopedIntakeTaskSet -Names @($entries | ForEach-Object {$_.task_name}))){return $false}
 foreach($entry in $entries){
  if([string]$entry.xml_sha256 -cnotmatch '^[a-f0-9]{64}$' -or
     [string]$entry.action_sha256 -cnotmatch '^[a-f0-9]{64}$' -or
     $entry.original_enabled -ne $true -or
     $entry.original_running -ne $true -or
     $entry.original_principal_system -ne $true -or
     $entry.one_original_boot_trigger -ne $true -or
     [int]$entry.restart_count -ne 3 -or
     [string]$entry.restart_interval -cne 'PT1M' -or
     [string]$entry.multiple_instances -cne 'IgnoreNew'){return $false}
 }
 return $true
}

# Actual originalhost PR515 PRECAS manifest, not historical simulated PR316.
# A caller's shape-only JSON is NEVER trusted for disk, Cloud or task authority.
function Test-V3Pr515CurrentOriginalBackupManifest([object]$Manifest) {
 if($null -eq $Manifest -or
    [string]$Manifest.kind -cne 'V3_PRECAS_NATIVE_XML_BACKUP_ORIGINALHOST_V1' -or
    [string]$Manifest.status -cne 'ORIGINAL_TASK_XML_BACKUP_ONLY_NOT_RELEASED' -or
    [string]$Manifest.predecessor_series_id -cne 'PAPER-V2R4-20261009T110135Z' -or
    [int]$Manifest.native_task_count -ne 2 -or
    $Manifest.original_tasks_still_running -ne $true -or
    $Manifest.scheduler_task_mutations -ne $false -or
    $Manifest.original_v2r4_changed -ne $false -or
    $Manifest.cloud_cas_invoked -ne $false -or
    $Manifest.new_v3_writer_started -ne $false -or
    $Manifest.original_cloud_series_independently_checked -ne $false -or
    [int]$Manifest.v3_release_or_six_proofs_credited -ne 0){return $false}
 if([string]$Manifest.backup_directory -cnotmatch
    '^C:\\Users\\ADMIN\\Trading\\State\\V3Paper-PreCAS-Backup-[a-f0-9]{32}$'){return $false}
 $rows=@($Manifest.task_records)
 if($rows.Count -ne 2 -or
    -not(Test-V3ScopedIntakeTaskSet -Names @($rows|ForEach-Object{[string]$_.task_name}))){return $false}
 $files=@{'CryptoMiniPC-V2R4PaperCandidates'='Candidates.task.xml';'CryptoMiniPC-V2R4PaperWait'='WAIT.task.xml'}
 $shas=@()
 foreach($row in $rows){
  $name=[string]$row.task_name
  if(-not $files.ContainsKey($name) -or
     [string]$row.xml_file -cne $files[$name] -or
     [string]$row.xml_sha256 -cnotmatch '^[a-f0-9]{64}$' -or
     [string]$row.action_sha256 -cnotmatch '^[a-f0-9]{64}$'){return $false}
  $shas+=@([string]$row.xml_sha256)
 }
 return ($shas[0] -cne $shas[1])
}

# Shared ORIGINAL current PR515/fresh two-Task backup read-only identity.
# An externally supplied report is NOT independently authenticated or a live
# stop/restore/CAS receipt. This one policy is reused by both pre-CAS phase
# planning and the separate manual precommit-recovery review.
function Test-V3Pr515FreshRecoveryIdentity([object]$Preview) {
 if($null -eq $Preview){return $false}
 $xml=@($Preview.current_native_task_xml_sha256)
 return (
  [string]$Preview.kind -ceq 'V3_PRECAS_PR515_FRESH_BACKUP_READONLY_COMPATIBILITY_V1' -and
  [string]$Preview.status -ceq 'COMPATIBLE_READONLY_NOT_RELEASED' -and
  [string]$Preview.current_backup_directory_leaf -cmatch '^V3Paper-PreCAS-Backup-[a-f0-9]{32}$' -and
  [string]$Preview.pr515_source_sha256 -cmatch '^[a-f0-9]{64}$' -and
  $xml.Count -eq 2 -and
  @($xml | Where-Object {[string]$_ -cnotmatch '^[a-f0-9]{64}$'}).Count -eq 0 -and
  [string]$xml[0] -cne [string]$xml[1] -and
  $Preview.current_backup_valid_while_intakes_running_only -eq $true -and
  $Preview.preview_is_not_poststop_or_independent_cloud_ack -eq $true -and
  $Preview.two_current_native_xml_reread_pass -eq $true -and
  $Preview.pr515_effective_cloudsync_source_consistent -eq $true -and
  $Preview.external_sha_pin_independently_authenticated -eq $false -and
  $Preview.physical_task_restore_tested -eq $false -and
  $Preview.scheduler_task_mutations -eq $false -and
  $Preview.cloud_cas_invoked -eq $false -and
  $Preview.v3_paper_activated -eq $false -and
  [int]$Preview.technical_release_proofs_credited -eq 0
 )
}

# Join current pre-stop and post-stop PR515 receipts from the SAME
# original backup/source. Caller-provided snapshots are not independent
# authenticity proof; this pure contract authorizes no restoration.
function Test-V3Pr515QuiescedRecoveryIdentity([object]$Before,[object]$After) {
 if(-not(Test-V3Pr515FreshRecoveryIdentity -Preview $Before) -or
    $null -eq $After){return $false}
 $old=@($Before.current_native_task_xml_sha256)
 $new=@($After.current_native_task_xml_sha256)
 return (
  [string]$After.kind -ceq 'V3_PRECAS_PR515_QUIESCED_READONLY_COMPATIBILITY_V1' -and
  [string]$After.status -ceq 'QUIESCED_NATIVE_SOURCE_MATCH_NOT_RELEASED' -and
  [string]$After.current_backup_directory_leaf -ceq [string]$Before.current_backup_directory_leaf -and
  [string]$After.pr515_source_sha256 -ceq [string]$Before.pr515_source_sha256 -and
  $old.Count -eq 2 -and $new.Count -eq 2 -and
  [string]$new[0] -ceq [string]$old[0] -and
  [string]$new[1] -ceq [string]$old[1] -and
  $After.after_disable_enabled_only_native_xml_comparison -eq $true -and
  $After.poststop_disabled_only_native_xml_recheck_pass -eq $true -and
  $After.single_local_supervisor_pr515_quiesced_observation_only -eq $true -and
  $After.two_distinct_supervisor_cycles_verified -eq $false -and
  $After.old_intake_pid_family_absence_independently_verified -eq $false -and
  $After.independent_cloud_cas_never_invoked_verified -eq $false -and
  $After.two_current_native_xml_reread_pass -eq $false -and
  $After.current_backup_valid_while_intakes_running_only -eq $false -and
  $After.preview_is_not_poststop_or_independent_cloud_ack -eq $false -and
  $After.local_poststop_snapshot_is_not_independent_cloud_ack -eq $true -and
  $After.pr515_effective_cloudsync_source_consistent -eq $true -and
  $After.external_sha_pin_independently_authenticated -eq $false -and
  $After.physical_task_restore_tested -eq $false -and
  $After.scheduler_task_mutations -eq $false -and
  $After.cloud_cas_invoked -eq $false -and
  $After.v3_paper_activated -eq $false -and
  [int]$After.technical_release_proofs_credited -eq 0
 )
}

# ARMED is the original native STOP's intentionally retained pre-CAS state.
# A stop failure or crash before QUIESCED must not depend on a QUIESCED-only
# recovery receipt. This is an offline scoped *review*, never task authority.
# It can consider ONLY BOTH disabled, fully quiet old-intake roles; mixed
# Running/Disabled or uncertain PID families remain a manual incident HOLD.
function Test-V3Pr515ArmedRecoveryIdentity([object]$Before,[object]$After) {
 if(-not(Test-V3Pr515FreshRecoveryIdentity -Preview $Before) -or
    $null -eq $After){return $false}
 $old=@($Before.current_native_task_xml_sha256)
 $new=@($After.current_native_task_xml_sha256)
 return (
  [string]$After.kind -ceq 'V3_PRECAS_PR515_ARMED_POSTSTOP_READONLY_COMPATIBILITY_V1' -and
  [string]$After.status -ceq 'ARMED_DISABLED_NATIVE_SOURCE_MATCH_NOT_RELEASED' -and
  [string]$After.current_backup_directory_leaf -ceq [string]$Before.current_backup_directory_leaf -and
  [string]$After.pr515_source_sha256 -ceq [string]$Before.pr515_source_sha256 -and
  $old.Count -eq 2 -and $new.Count -eq 2 -and
  [string]$new[0] -ceq [string]$old[0] -and
  [string]$new[1] -ceq [string]$old[1] -and
  $After.after_disable_enabled_only_native_xml_comparison -eq $true -and
  $After.poststop_disabled_only_native_xml_recheck_pass -eq $true -and
  $After.single_local_supervisor_pr515_armed_observation_only -eq $true -and
  $After.single_local_supervisor_pr515_quiesced_observation_only -eq $false -and
  $After.two_distinct_supervisor_cycles_verified -eq $false -and
  $After.old_intake_pid_family_absence_independently_verified -eq $false -and
  $After.independent_cloud_cas_never_invoked_verified -eq $false -and
  $After.current_backup_valid_while_intakes_running_only -eq $false -and
  $After.preview_is_not_poststop_or_independent_cloud_ack -eq $false -and
  $After.local_poststop_snapshot_is_not_independent_cloud_ack -eq $true -and
  $After.pr515_effective_cloudsync_source_consistent -eq $true -and
  $After.external_sha_pin_independently_authenticated -eq $false -and
  $After.physical_task_restore_tested -eq $false -and
  $After.scheduler_task_mutations -eq $false -and
  $After.cloud_cas_invoked -eq $false -and
  $After.v3_paper_activated -eq $false -and
  [int]$After.technical_release_proofs_credited -eq 0
 )
}

# Pure SOURCE-ONLY comparison of two ORIGINAL Supervisor + PR515 heartbeat
# captures while the same original intake fence remains ARMED. Both captures
# must be independently acquired by a later authorized host operator.
# Timestamps and JSON values supplied by a caller are NOT provenance or CAS
# authority; this cannot itself promote the marker or count release proofs.
function Test-V3Pr515ArmedTwoCycleSnapshots([object]$Evidence) {
 if($null -eq $Evidence -or
    [string]$Evidence.kind -cne 'V3_PR515_ARMED_TWO_CYCLE_ORIGINALHOST_INPUT_V1' -or
    [string]$Evidence.phase -cne 'ARMED' -or
    [string]$Evidence.predecessor_series_id -cne 'PAPER-V2R4-20261009T110135Z' -or
    -not(Test-V3ScopedIntakeTaskSet -Names @($Evidence.task_names))){
  return $false
 }
 $captures=@($Evidence.captures)
 if($captures.Count -ne 2){return $false}
 $times=@()
 foreach($snapshot in $captures){
  if($null -eq $snapshot -or $null -eq $snapshot.supervisor -or
     $null -eq $snapshot.cloudsync){return $false}
  $sv=$snapshot.supervisor
  $cs=$snapshot.cloudsync
  if([string]$sv.kind -cne 'MINIPC_RUNTIME_SUPERVISOR_V1' -or
     [string]$sv.status -cne 'WARNING' -or
     [string]$sv.v3_paper_old_intake_fence.mode -cne 'ARMED' -or
     $sv.v3_paper_old_intake_fence.marker_present -ne $true -or
     $sv.v3_paper_old_intake_fence.v3_cloud_cas_or_release_authorized -ne $false -or
     @($sv.restarted).Count -ne 0 -or @($sv.failed_restarts).Count -ne 0 -or
     [string]$cs.kind -cne 'V2R4_PAPER_CLOUD_SYNC_HEARTBEAT_V1' -or
     [string]$cs.status -cne 'HEALTHY' -or
     [string]$cs.mode -cne 'V3_PRECOMMIT_NO_NETWORK_HOLD' -or
     [string]$cs.v3_fence_precommit_phase -cne 'ARMED' -or
     [string]$cs.v3_fence_cloud_sync_lane -cne 'PRECOMMIT_ORIGINAL' -or
     $cs.cloud_sync_intentionally_paused -ne $true -or
     $cs.cloud_updated -ne $false -or
     $cs.paper_only -ne $true -or
     $cs.order_api -ne $false -or
     $cs.real_money_actions -ne $false){
   return $false
  }
  $blocked=@($sv.tasks | Where-Object {
   $_.task -in @('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait') -and
   [string]$_.action -ceq 'V3_INTAKE_SUPERVISOR_REARM_BLOCKED' -and
   [string]$_.before.scheduler_state -ceq 'Disabled'
  })
  if($blocked.Count -ne 2 -or
     -not(Test-V3ScopedIntakeTaskSet -Names @($blocked|ForEach-Object {[string]$_.task}))){
   return $false
  }
  $svTime=[datetimeoffset]::MinValue
  $csTime=[datetimeoffset]::MinValue
  if([string]$sv.checked_at_utc -cnotmatch '(Z|\+00:00)$' -or
     [string]$cs.checked_at_utc -cnotmatch '(Z|\+00:00)$' -or
     -not([datetimeoffset]::TryParse([string]$sv.checked_at_utc,[ref]$svTime)) -or
     -not([datetimeoffset]::TryParse([string]$cs.checked_at_utc,[ref]$csTime)) -or
     [math]::Abs(($svTime-$csTime).TotalSeconds) -gt 90){
   return $false
  }
  $times+=@($svTime)
  $times+=@($csTime)
 }
 # TWO distinct native Supervisor cycles, each with its own fresh PR515
 # hold receipt, ordered without replay of one heartbeat as both samples.
 $delta=($times[2]-$times[0]).TotalSeconds
 $cloudDelta=($times[3]-$times[1]).TotalSeconds
 return ($delta -ge 5 -and $delta -le 600 -and
         $cloudDelta -ge 5 -and $cloudDelta -le 600)
}

# Only a PURE preview of ARMED -> QUIESCED. Two caller booleans or an old
# physical drill are NOT actual native, independent Supervisor or Cloud proof.
function Get-V3Pr515ArmedToQuiescedReview([object]$Receipt) {
 $status='HOLD_ARMED_INDEPENDENT_ORIGINAL_PROOFS_REQUIRED'
 if($null -eq $Receipt -or
    [string]$Receipt.kind -cne 'V3_PR515_ARMED_TO_QUIESCED_SOURCE_REVIEW_V1' -or
    [string]$Receipt.predecessor_series_id -cne 'PAPER-V2R4-20261009T110135Z' -or
    -not(Test-V3ScopedIntakeTaskSet -Names @($Receipt.task_names)) -or
    [string]$Receipt.fence_phase -cne 'ARMED' -or
    $Receipt.cloud_cas_invoked -ne $false -or
    [string]$Receipt.cloud_cas_outcome -cne 'NOT_INVOKED' -or
    $Receipt.v3_writer_started -ne $false -or
    $Receipt.paper_only -ne $true -or
    $Receipt.real_money_actions -ne $false){
  $status='BLOCK_INVALID_SCOPE_OR_CAS'
 }elseif((Test-V3Pr515ArmedTwoCycleSnapshots -Evidence $Receipt.original_armed_two_cycle_snapshots) -and
         $Receipt.current_two_native_tasks_disabled -eq $true -and
         $Receipt.current_original_intake_full_process_family_absent -eq $true -and
         $Receipt.current_supervisor_armed_no_rearm_ack -eq $true -and
         $Receipt.current_pr515_cloudsync_armed_no_network_ack -eq $true -and
         $Receipt.protected_lifecycle_cloudsync_running -eq $true -and
         $Receipt.current_xml_backup_source_identity_preserved -eq $true -and
         $Receipt.independent_old_only_cloud_after_stop -eq $true -and
         $Receipt.independent_cas_never_invoked_after_stop -eq $true){
  $status='REVIEW_SEPARATE_PHYSICAL_QUIESCED_TRANSITION_ONLY'
 }
 return [pscustomobject]@{
  kind='V3_PR515_ARMED_TO_QUIESCED_SOURCE_DISPOSITION_V1'
  disposition=$status
  input_is_untrusted_synthetic_not_originalhost_ack=$true
  original_host_authentication_performed=$false
  two_distinct_supervisor_cycles_verified=$false
  two_cycle_caller_json_is_not_original_provenance=$true
  native_process_lineage_authenticated=$false
  independent_cloud_cas_readback_performed=$false
  marker_write_or_transition_authorized=$false
  automatic_old_writer_rearm_allowed=$false
  cloud_cas_invoke_permitted=$false
  v3_paper_release_authorized=$false
  full_v3_e2e_proofs_credited=0
 }
}

# Original Supabase live inventory validator; matching one committed-state
# SELECT does NOT attest the non-occurrence of earlier/rolled-back CAS calls.
# Inputs may be from connected read-only Cloud; JSON alone has NO authenticated
# issuer, replay defense or authority to enable native Tasks. Fail closed.
function Test-V3PrecommitCurrentCloudInventory([object]$Inventory) {
 if($null -eq $Inventory -or
    [string]$Inventory.kind -cne 'V3_PRECOMMIT_CURRENT_CLOUD_INVENTORY_V1' -or
    $Inventory.historically_cas_never_invoked_proven -ne $false -or
    $Inventory.precommit_restore_authorized -ne $false){
  return $false
 }
 $counts=@{
  active_series_count=1
  exact_original_active_count=1
  recorded_v3_series_count=0
  recorded_v3_rotation_count=0
  recorded_v3_release_decision_count=0
  installed_v3_cas_function_count=0
  valid_single_active_index_count=1
 }
 foreach($key in $counts.Keys){
  $val=$Inventory.PSObject.Properties[$key]
  if($null -eq $val -or
     ($val.Value -isnot [int] -and $val.Value -isnot [long]) -or
     [long]$val.Value -ne [long]$counts[$key]){
   return $false
  }
 }
 $stamp=[datetimeoffset]::MinValue
 if([string]$Inventory.observed_at_utc -cnotmatch '(Z|\+00(?::00)?)$' -or
    -not([datetimeoffset]::TryParse([string]$Inventory.observed_at_utc,[ref]$stamp))){
  return $false
 }
 $age=([datetimeoffset]::UtcNow-$stamp).TotalSeconds
 return ($age -ge -10 -and $age -le 180)
}

# PURE review of two existing Cloud readers: authenticated NOTEBOOK private
# reader's snapshot and separately captured production paper-series inventory.
# Caller JSON, zero rows and two timestamps cannot prove complete CAS history.
function Get-V3Pr515TwoSourceCloudSnapshotReview([object]$Reader,[object]$Cloud) {
 $decision='HOLD_TWO_SOURCE_CLOUD_SNAPSHOT_DRIFT_OR_UNTRUSTED'
 if($null -ne $Reader -and $null -ne $Cloud -and
    [string]$Reader.kind -ceq 'V3_CAS_READER_CURRENT_PRIVATE_AUDIT_SNAPSHOT_V1' -and
    [string]$Reader.status -ceq 'AUTHENTICATED_READER_CURRENT_EMPTY_NOT_HISTORICAL_NEVER' -and
    [string]$Reader.actor -ceq 'v3_cas_audit_reader_actor' -and
    [string]$Reader.role -ceq 'v3_cas_audit_reader' -and
    ($Reader.epoch_count -is [int] -or $Reader.epoch_count -is [long]) -and
    [long]$Reader.epoch_count -eq 0 -and
    ($Reader.intent_count -is [int] -or $Reader.intent_count -is [long]) -and
    [long]$Reader.intent_count -eq 0 -and
    $Reader.independent_tls_certificate_verified -eq $false -and
    $Reader.independent_attempt_history_complete -eq $false -and
    $Reader.historical_cas_never_proven -eq $false -and
    $Reader.public_old_only_series_verified_here -eq $false -and
    $Reader.native_rearm_authorized -eq $false -and
    $Reader.precommit_restore_authorized -eq $false -and
    $Reader.cloud_cas_authorized -eq $false -and
    $Reader.v3_paper_release_authorized -eq $false -and
    (Test-V3PrecommitCurrentCloudInventory -Inventory $Cloud)){
  $rt=[datetimeoffset]::MinValue
  $ct=[datetimeoffset]::MinValue
  if([string]$Reader.observed_at_utc -cmatch 'Z$' -and
     [datetimeoffset]::TryParse([string]$Reader.observed_at_utc,[ref]$rt) -and
     [datetimeoffset]::TryParse([string]$Cloud.observed_at_utc,[ref]$ct) -and
     [math]::Abs(($rt-$ct).TotalSeconds) -le 90 -and
     ([datetimeoffset]::UtcNow-$rt).TotalSeconds -ge -10 -and
     ([datetimeoffset]::UtcNow-$rt).TotalSeconds -le 90){
   $decision='REVIEW_ONLY_CURRENT_OLD_ONLY_AND_READER_EMPTY_CAS_HISTORY_UNKNOWN'
  }
 }
 return [pscustomobject]@{
  kind='V3_PR515_TWO_EXISTING_CLOUD_SNAPSHOTS_SOURCE_REVIEW_V1'
  disposition=$decision
  independently_authenticated_here=$false
  complete_historical_cas_never_proven=$false
  independent_cas_never_invoked_verified=$false
  originalhost_quiesced_or_precommit_restore_authorized=$false
  native_rearm_or_cloud_cas_authorized=$false
  v3_paper_release_authorized=$false
  technical_release_proofs_credited=0
 }
}

# Future Stage4/Writer-COMMIT independent Reader evidence is compared
# with the original PR515 source/fence/caller-ACL/request identifiers.
# Pure SOURCE REVIEW only: caller-provided packets authenticate neither side.
# A valid match is NOT old-writer rearm, CAS dispatch or Paper release.
function Get-V3Pr515DurableReaderIntentSourceReview([object]$Reader,[object]$Original) {
 $disposition='HOLD_DURABLE_READER_ORIGINAL_SCOPE_NOT_VERIFIED'
 if($null -ne $Reader -and $null -ne $Original -and
    [string]$Reader.kind -ceq 'V3_ORIGINAL_READER_DURABLE_PREINVOKE_INTENT_V1' -and
    [string]$Reader.status -ceq 'CURRENT_ONE_COMMITTED_PREINVOKE_INTENT_NOT_CAS_RELEASE' -and
    [string]$Original.kind -ceq 'V3_PR515_ORIGINAL_EXPECTED_PREINVOKE_SCOPE_V1' -and
    $Reader.independent_tls_certificate_verified -eq $false -and
    $Reader.historical_cas_never_proven -eq $false -and
    $Reader.complete_cas_attempt_custody_proven -eq $false -and
    $Reader.originalhost_authenticated_here -eq $false -and
    $Reader.cloud_cas_authorized -eq $false -and
    $Reader.precommit_restore_authorized -eq $false -and
    $Reader.v3_paper_release_authorized -eq $false -and
    $Original.cloud_cas_invoked -eq $false -and
    [string]$Original.predecessor_series_id -ceq 'PAPER-V2R4-20261009T110135Z'){
  $match=$true
  $fields=@('epoch_id','intent_id','source_sha256',
            'fence_sha256','caller_acl_sha256','request_sha256')
  foreach($field in $fields){
   $readProp=$Reader.PSObject.Properties[$field]
   $oldProp=$Original.PSObject.Properties[$field]
   if($null -eq $readProp -or $null -eq $oldProp){$match=$false;break}
   $received=[string]$readProp.Value
   $expected=[string]$oldProp.Value
   $shape=if($field -eq 'epoch_id'){'^V3CAS-AUDIT-[a-f0-9]{32}$'}elseif($field -eq 'intent_id'){'^[a-f0-9-]{36}$'}else{'^[a-f0-9]{64}$'}
   if($received -cnotmatch $shape -or $received -cne $expected){$match=$false;break}
  }
  $when=[datetimeoffset]::MinValue
  if($match -and [string]$Reader.observed_at_utc -cmatch 'Z$' -and
     [datetimeoffset]::TryParse([string]$Reader.observed_at_utc,[ref]$when) -and
     ([datetimeoffset]::UtcNow-$when).TotalSeconds -ge -5 -and
     ([datetimeoffset]::UtcNow-$when).TotalSeconds -le 90){
   $disposition='REVIEW_ONLY_EXACT_COMMITTED_INTENT_MATCH_UNAUTHENTICATED_HERE'
  }
 }
 return [pscustomobject]@{
  kind='V3_PR515_DURABLE_READER_ORIGINAL_SCOPE_SOURCE_REVIEW_V1'
  disposition=$disposition
  reader_original_connection_authenticated_here=$false
  originalhost_source_fence_acl_authenticated_here=$false
  externally_complete_attempt_history_proven=$false
  old_writer_auto_rearm_allowed=$false
  precommit_restore_authorized=$false
  cloud_cas_invoke_authorized=$false
  v3_paper_release_authorized=$false
  technical_release_proofs_credited=0
 }
}

# SOURCE ONLY: assess the evidence needed from the EXISTING exclusive CAS
# invocation owner BEFORE it ever calls the future V3 RPC. This function has
# no I/O, verifies no credentials/signatures and NEVER authorizes restore.
# Caller-provided JSON cannot prove audit completeness or CAS non-invocation.
# PostgreSQL transactions cannot persist an intent on a rolled-back CAS.
function Get-V3CasPreinvokeAuditReview([object]$Audit) {
 $disposition='HOLD_AUDIT_EPOCH_OR_PROVENANCE_UNVERIFIED'
 if($null -eq $Audit -or
    [string]$Audit.kind -cne 'V3_EXPERIMENTAL_CAS_PREINVOKE_AUDIT_REVIEW_INPUT_V1' -or
    [string]$Audit.predecessor_series_id -cne 'PAPER-V2R4-20261009T110135Z' -or
    [string]$Audit.audit_epoch_id -cnotmatch '^V3CAS-AUDIT-[a-f0-9]{32}$' -or
    [string]$Audit.expected_cas_rpc -cne 'public.rotate_v2r4_to_v3_experimental_paper' -or
    $Audit.paper_only -ne $true -or
    $Audit.real_money_actions -ne $false){
  $disposition='BLOCK_INVALID_CAS_AUDIT_SCOPE'
 } elseif($Audit.local_predispatch_unknown_latch_present -eq $true -or
          $Audit.any_committed_preinvoke_intent_observed -eq $true -or
          [string]$Audit.cas_attempt_state -cne 'NOT_INVOKED' -or
          $Audit.any_failed_timedout_unknown_or_committed_attempt -ne $false -or
          $Audit.attempt_intent_count -ne 0 -or
          $Audit.inflight_or_unknown_count -ne 0){
  $disposition='HOLD_ANY_CAS_ATTEMPT_OR_UNKNOWN'
 } elseif([string]$Audit.ledger_lane -cne 'INDEPENDENT_PREINVOKE_COMMIT' -or
          [string]$Audit.ledger_write_mode -cne 'APPEND_ONLY_NO_DELETE' -or
          [string]$Audit.single_invocation_owner -cne 'EXCLUSIVE_RESTRICTED_CAS_EXECUTOR' -or
          $Audit.caller_exclusivity_independently_reviewed -ne $true -or
          $Audit.cas_rpc_execute_revoked_from_shared_service_role -ne $true -or
          $Audit.durable_ack_required_before_rpc -ne $true -or
          $Audit.unacknowledged_intent_fences_rpc -ne $true -or
          $Audit.ledger_and_rpc_use_separate_transactions -ne $true -or
          $Audit.audit_store_no_alter_or_delete_acl_independently_reviewed -ne $true -or
          $Audit.audit_provenance_issuer_independently_reviewed -ne $true -or
          $Audit.startup_coverage_before_first_rpc_independently_reviewed -ne $true -or
          $Audit.all_invocation_paths_covered_independently_reviewed -ne $true){
  $disposition='HOLD_AUDIT_COVERAGE_OR_DURABILITY_INCOMPLETE'
 } else {
  $first=[datetimeoffset]::MinValue
  $last=[datetimeoffset]::MinValue
  if([string]$Audit.coverage_started_utc -notmatch '(Z|\+00:00)$' -or
     [string]$Audit.snapshot_observed_utc -notmatch '(Z|\+00:00)$' -or
     -not([datetimeoffset]::TryParse([string]$Audit.coverage_started_utc,[ref]$first)) -or
     -not([datetimeoffset]::TryParse([string]$Audit.snapshot_observed_utc,[ref]$last)) -or
     $first -ge $last -or $last -gt [datetimeoffset]::UtcNow.AddSeconds(10) -or
     ([datetimeoffset]::UtcNow-$last).TotalSeconds -gt 180){
   $disposition='HOLD_AUDIT_EPOCH_TIMESTAMPS_UNVERIFIED'
  } else {
   $disposition='REVIEW_ONLY_PREINVOKE_AUDIT_CONTRACT_COMPLETE_UNAUTHENTICATED'
  }
 }
 return [pscustomobject]@{
  kind='V3_CAS_PREINVOKE_AUDIT_SOURCE_POLICY_V1'
  disposition=$disposition
  caller_supplied_assertions_not_original_authority=$true
  original_audit_issuer_authenticated_here=$false
  append_only_proven_here=$false
  all_invocation_paths_proven_here=$false
  historical_cas_never_invoked_proven=$false
  source_only_contract_not_runtime_ack=$true
  cloud_cas_invoke_authorized=$false
  native_recovery_authorized=$false
  old_writer_auto_rearm_allowed=$false
  v3_paper_release_authorized=$false
 }
}

# A pure decision matrix. NEVER restore an old writer after ANY CAS invocation,
# including timeout, no response or an apparently negative outcome: operator
# MUST fence and reconcile actual independent Cloud readback by hand.
# No decision returned here grants permission to execute a Windows mutation.
# The caller-supplied *independent_cloud_*_ack booleans in the historical
# simulation are NOT verified third-party or signed CAS custody. No value of
# these booleans may yield a restore candidate. Real authorization must be
# integrated through the sole originalhost operator with independent proof.
function Resolve-V3ScopedCutoverRecovery([object]$Receipt) {
 $resolution='HOLD_FENCE_MANUAL_RECONCILIATION'
 if($null -eq $Receipt -or
    [string]$Receipt.kind -cne 'V3_CUTOVER_RECOVERY_SIMULATION_V1' -or
    [string]$Receipt.predecessor_series_id -cne 'PAPER-V2R4-20261009T110135Z' -or
    -not(Test-V3ScopedIntakeTaskSet -Names @($Receipt.task_names)) -or
    $null -eq $Receipt.cloud_cas_invoked -or
    $null -eq $Receipt.v3_writer_started -or
    $Receipt.paper_only -ne $true -or
    $Receipt.real_money_actions -ne $false){
   $resolution='BLOCK_INVALID_SCOPE_OR_RECEIPT'
 } else {
  $phase=[string]$Receipt.phase
  # Receipt phase and fence claim must agree, but caller JSON is not authority.
  $marker=[string]$Receipt.fence_marker_phase
  $outcome=[string]$Receipt.cloud_cas_outcome
  $invoked=($Receipt.cloud_cas_invoked -eq $true)
  if($outcome -notin @('NOT_INVOKED','UNKNOWN','NOT_COMMITTED','COMMITTED')){
   $resolution='HOLD_INVALID_CLOUD_OUTCOME'
  } elseif($outcome -eq 'COMMITTED' -or $phase -eq 'CLOUD_COMMITTED'){
   $resolution='HOLD_POSTCOMMIT_OLD_INTAKE_PERMANENTLY_FENCED'
  } elseif($Receipt.local_predispatch_unknown_latch_present -eq $true -or
          $Receipt.any_committed_preinvoke_intent_observed -eq $true){
   # Even before any RPC, a durable intent or local UNKNOWN must never be
   # reclassified as safe-to-restore by a caller's "NOT_INVOKED" boolean.
   $resolution='HOLD_PERSISTED_PREINVOKE_OR_LOCAL_UNKNOWN_NO_REARM'
  } elseif($invoked -or $outcome -ne 'NOT_INVOKED' -or $phase -eq 'CAS_INVOKED'){
   $resolution='HOLD_CAS_ATTEMPTED_MANUAL_CLOUD_RECONCILIATION'
  } elseif($phase -eq 'PRE_CUTOVER'){
   $resolution='NO_ACTION_PRESERVE_ACTIVE_V2R4'
  } elseif($phase -notin @('ARMED','QUIESCED')){
   $resolution='HOLD_UNKNOWN_PHASE'
  } elseif($phase -eq 'ARMED' -and $marker -eq 'ARMED') {
   # Native STOP returns ARMED while awaiting its separate two-cycle and
   # QUIESCED transition. Only a fully stopped AND independently reviewed
   # pre-CAS original state may even be considered for manual restoration.
   # Half-stopped/mixed states remain HOLD for the original incident owner.
   $fullyDisabled=($Receipt.native_intake_tasks_disabled_ack -eq $true -and
                   $Receipt.original_intake_processes_absent_ack -eq $true -and
                   $Receipt.windows_supervisor_no_rearm_ack -eq $true -and
                   $Receipt.protected_lifecycle_cloudsync_running_ack -eq $true)
   if(-not $fullyDisabled){
    $resolution='HOLD_ARMED_PARTIAL_STOP_MANUAL_INCIDENT_NO_REARM'
   }elseif(-not(Test-V3Pr515CurrentOriginalBackupManifest -Manifest $Receipt.backup_manifest) -or
      $Receipt.backup_contract_verified -ne $true -or
      $Receipt.old_cloud_single_active_readback -ne $true -or
      $Receipt.new_v3_series_absent_readback -ne $true -or
      $Receipt.v3_writer_started -ne $false){
    $resolution='HOLD_ARMED_BACKUP_OR_PRECAS_STATE_INCOMPLETE'
   }else{
    $current=$Receipt.current_pr515_readonly_preview
    $armed=$Receipt.current_pr515_armed_readonly_preview
    $scope=(Test-V3Pr515ArmedRecoveryIdentity -Before $current -After $armed)
    $cloud=(Test-V3PrecommitCurrentCloudInventory -Inventory $Receipt.current_prod_cloud_inventory)
    if($scope -and $cloud -and
       $Receipt.pr515_sha_pin_separately_verified -eq $true -and
       $Receipt.fresh_current_xml_after_armed_independently_checked -eq $true -and
       $Receipt.independent_cloud_precommit_cas_never_invoked_ack -eq $true -and
       $Receipt.independent_cloud_old_only_after_armed_ack -eq $true){
      $resolution='HOLD_ARMED_UNAUTHENTICATED_EXTERNAL_CLOUD_CAS_CUSTODY'
    }else{
      $resolution='HOLD_ARMED_CURRENT_BACKUP_OR_INDEPENDENT_CLOUD_ACK'
    }
   }
  } elseif($phase -eq 'QUIESCED' -and $marker -ceq 'QUIESCED' -and
      (Test-V3Pr515CurrentOriginalBackupManifest -Manifest $Receipt.backup_manifest) -and
      $Receipt.backup_contract_verified -eq $true -and
      $Receipt.native_intake_tasks_disabled_ack -eq $true -and
      $Receipt.original_intake_processes_absent_ack -eq $true -and
      $Receipt.windows_supervisor_no_rearm_ack -eq $true -and
      $Receipt.protected_lifecycle_cloudsync_running_ack -eq $true -and
      $Receipt.old_cloud_single_active_readback -eq $true -and
      $Receipt.new_v3_series_absent_readback -eq $true -and
      $Receipt.v3_writer_started -eq $false){
   # Historical backup proposals cannot attest current PR515 or fresh XML.
   # This is an OFFLINE manual-review candidate, not permission to restore.
   $current=$Receipt.current_pr515_readonly_preview
   $poststop=$Receipt.current_pr515_quiesced_readonly_preview
   $pr515Current=(Test-V3Pr515QuiescedRecoveryIdentity -Before $current -After $poststop)
   $currentCloud=(Test-V3PrecommitCurrentCloudInventory -Inventory $Receipt.current_prod_cloud_inventory)
   if($pr515Current -and $currentCloud -and
      $Receipt.pr515_sha_pin_separately_verified -eq $true -and
      $Receipt.fresh_current_xml_after_quiesce_independently_checked -eq $true -and
      $Receipt.independent_cloud_precommit_cas_never_invoked_ack -eq $true -and
      $Receipt.independent_cloud_old_only_after_quiesce_ack -eq $true){
    $resolution='HOLD_QUIESCED_UNAUTHENTICATED_EXTERNAL_CLOUD_CAS_CUSTODY'
   }else{
    $resolution='HOLD_CURRENT_PR515_BACKUP_OR_INDEPENDENT_CLOUD_ACK'
   }
  }
 }
 return [pscustomobject]@{
  kind='V3_CUTOVER_RECOVERY_OFFLINE_DISPOSITION_V1'
  disposition=$resolution
  automatic_task_action_authorized=$false
  automatic_old_writer_rearm_allowed=$false
  current_backup_and_external_cloud_proof_required=$true
  current_poststop_disabled_xml_compatibility_required=$true
  fresh_supabase_current_old_only_inventory_required=$true
  cloud_inventory_cannot_prove_historical_cas_never=$true
  source_only_pr515_recovery_readback_not_authority=$true
  operator_stop_disable_implemented=$false
  host_rollback_implemented=$false
  cloud_cas_executed=$false
  v3_release_authorized=$false
  full_v3_e2e_proofs_credited=0
 }
}


# Exact adapter for the *actual* 15-Oct host backup-manifest.json SCHEMA.
# This validates values only, not the physical existence of a backup directory,
# file SHA, Windows Task state, privileged ACL, machine identity or provenance.
# Critically it MUST NOT upcast this V1 host readback to PR316's simulated,
# more demanding V3_OLD_INTAKE_BACKUP_PROPOSAL_V1 task_records contract.
function Get-V3NativeIntakeBackupReadbackGap([object]$Readback) {
 $errors=@()
 $expected=@{
  'CryptoMiniPC-V2R4PaperCandidates'='Candidates.task.xml'
  'CryptoMiniPC-V2R4PaperWait'='WAIT.task.xml'
 }
 if($null -eq $Readback){
  $errors+=@('MISSING_READBACK')
 } else {
  if([string]$Readback.kind -cne 'V3_OLD_INTAKE_NATIVE_BACKUP_READBACK_V1'){
   $errors+=@('WRONG_NATIVE_KIND')
  }
  if([string]$Readback.predecessor_series_id -cne 'PAPER-V2R4-20261009T110135Z'){
   $errors+=@('WRONG_PREDECESSOR')
  }
  if($Readback.task_or_process_changes -ne $false -or
     $Readback.cloud_changes -ne $false -or
     $Readback.actual_stop_or_rollback_tested -ne $false){
   $errors+=@('UNEXPECTED_MUTATION_OR_RESTORE_CLAIM')
  }
  $time=[datetimeoffset]::MinValue
  $timestamp=[string]$Readback.captured_at_utc
  if($timestamp -cnotmatch '(Z|\+00:00)$' -or
     -not([datetimeoffset]::TryParse($timestamp,[ref]$time))){
   $errors+=@('INVALID_UTC_CAPTURE_TIME')
  }
  $tasks=@($Readback.tasks)
  if($tasks.Count -ne 2){
   $errors+=@('WRONG_COUNT')
  } else {
   $names=@($tasks | ForEach-Object {[string]$_.task_name})
   if(-not(Test-V3ScopedIntakeTaskSet -Names $names)){
    $errors+=@('WRONG_TASK_SCOPE')
   }
   foreach($task in $tasks){
    $name=[string]$task.task_name
    if(-not $expected.ContainsKey($name)){continue}
    if([string]$task.backup_file -cne $expected[$name]){
     $errors+=@('UNEXPECTED_BACKUP_FILENAME')
    }
    if([string]$task.task_path -cne '\'){
     $errors+=@('UNEXPECTED_TASK_PATH')
    }
    if([string]$task.original_state -cne 'Running'){
     $errors+=@('NONRUNNING_OR_UNKNOWN_ORIGINAL_STATE')
    }
    if([string]$task.xml_sha256 -cnotmatch '^[a-f0-9]{64}$' -or
       [string]$task.action_sha256 -cnotmatch '^[a-f0-9]{64}$'){
     $errors+=@('INVALID_CAPTURED_HASH')
    }
   }
  }
 }
 return [pscustomobject]@{
  kind='V3_NATIVE_BACKUP_READBACK_SCHEMA_GAP_OFFLINE_V1'
  native_host_manifest_schema_only_pass=($errors.Count -eq 0)
  schema_errors=@($errors)
  schema_is_not_physical_provenance=$true
  host_backup_physical_readback_independently_verified_here=$false
  full_task_xml_contents_and_disk_sha_recheck_needed=$true
  original_native_principal_boot_restart_settings_recheck_needed=$true
  original_runtime_stage_source_sha_needed=$true
  exact_live_task_action_xml_and_process_tree_recheck_needed=$true
  actual_restore_dryrun_completed=$false
  can_upcast_native_host_manifest_to_recovery_proposal=$false
  automatic_intake_task_action_authorized=$false
  v3_paper_release_authorized=$false
  full_v3_release_proofs_credited=0
 }
}


# Exact-schema split vintage check only: Candidates still uses the 15-Oct
# original native Task backup, WAIT was genuinely changed to PR326 on 16-Oct.
# Never silently restore the pre-PR326 WAIT action from the older pair.
# No filesystem, TaskScheduler, token, marker or Cloud access in this helper.
function Get-V3SplitVintageNativeBackupCompositionGap([object]$Old,[object]$CurrentWait) {
 $errors=@()
 $oldShape=Get-V3NativeIntakeBackupReadbackGap -Readback $Old
 if($oldShape.native_host_manifest_schema_only_pass -ne $true){
  $errors+=@('OLD_NATIVE_MANIFEST_NOT_VALID')
 }
 if($null -eq $CurrentWait){
  $errors+=@('CURRENT_WAIT_MANIFEST_MISSING')
 }else{
  if([string]$CurrentWait.kind -cne 'V3_WAIT_PR326_POSTCUTOVER_NATIVE_BACKUP_V1' -or
     [string]$CurrentWait.task_name -cne 'CryptoMiniPC-V2R4PaperWait' -or
     [string]$CurrentWait.backup_file -cne 'WAIT.task.xml' -or
     [string]$CurrentWait.original_task_state -cne 'Running' -or
     $CurrentWait.actual_restore_tested -ne $false -or
     $CurrentWait.runtime_modified -ne $false){
   $errors+=@('POST_PR326_WAIT_IDENTITY_OR_SAFETY_INVALID')
  }
  if([string]$CurrentWait.xml_sha256 -cnotmatch '^[a-f0-9]{64}$' -or
     [string]$CurrentWait.launcher_sha256 -cne
        'c5e43d62976bdf2079a3a0402e57658aba8a33d427b0cf0d56737565b84dd51d'){
   $errors+=@('POST_PR326_WAIT_SHA_OR_LAUNCHER_PIN_INVALID')
  }
  $oldAt=[datetimeoffset]::MinValue
  $newAt=[datetimeoffset]::MinValue
  if($null -eq $Old -or
     [string]$CurrentWait.captured_at_utc -cnotmatch '(Z|\+00:00)$' -or
     -not([datetimeoffset]::TryParse([string]$Old.captured_at_utc,[ref]$oldAt)) -or
     -not([datetimeoffset]::TryParse([string]$CurrentWait.captured_at_utc,[ref]$newAt)) -or
     $newAt -le $oldAt){
   $errors+=@('POST_PR326_WAIT_CAPTURE_NOT_AFTER_OLD')
  }
 }
 if($oldShape.native_host_manifest_schema_only_pass -eq $true -and $null -ne $CurrentWait){
  $olderWait=@($Old.tasks | Where-Object {
   [string]$_.task_name -ceq 'CryptoMiniPC-V2R4PaperWait'
  })
  if($olderWait.Count -ne 1 -or
     [string]$olderWait[0].xml_sha256 -ceq [string]$CurrentWait.xml_sha256){
   $errors+=@('POST_PR326_WAIT_NOT_DISTINCT_FROM_OBSOLETE_BACKUP')
  }
 }
 return [pscustomobject]@{
  kind='V3_SPLIT_VINTAGE_ORIGINAL_TASK_BACKUP_SCHEMA_ONLY_V1'
  backup_composition_schema_only_pass=($errors.Count -eq 0)
  schema_errors=@($errors | Select-Object -Unique)
  candidates_backup_vintage='15_OCT_ORIGINAL'
  wait_backup_vintage='16_OCT_POST_PR326'
  old_wait_xml_must_never_be_restored_from_historical_pair=$true
  independent_current_task_sha_acl_launcher_and_source_pin_readbacks_required=$true
  protected_aftercare_supervisor_and_cloud_cas_remain_separate_gates=$true
  physical_task_scheduler_restore_executed=$false
  old_intake_tasks_disabled_or_stopped=$false
  task_process_marker_cloud_writes=0
  live_backup_proven_here=$false
  rollback_ready_or_authorized=$false
  physical_no_rearm_tested=$false
  v3_release_authorized=$false
  authentic_release_proofs_credited=0
 }
}


# Pure in-memory restoration PREVIEW of exact two original scheduled Tasks.
# Accept values collected by an independently authorized read-only host probe.
# Never registers, starts, disables, repairs or overwrites an actual Task.
# Even a PASS is not a true TaskScheduler import/restore or physical provenance.
function Test-V3NativeOriginalTaskRestorePreview([object]$Readback,[object[]]$Rows) {
 $errors=@()
 $shape=Get-V3NativeIntakeBackupReadbackGap -Readback $Readback
 if($shape.native_host_manifest_schema_only_pass -ne $true){
  $errors+=@('INVALID_ORIGINAL_MANIFEST')
 }
 $items=@($Rows)
 if($items.Count -ne 2){
  $errors+=@('NOT_EXACTLY_TWO_READONLY_ROWS')
 }else{
  $names=@($items | ForEach-Object {[string]$_.task_name})
  if(-not(Test-V3ScopedIntakeTaskSet -Names $names)){
   $errors+=@('INVALID_PREVIEW_TASK_SCOPE')
  }
 }
 if($errors.Count -eq 0){
  foreach($entry in @($Readback.tasks)){
   $n=[string]$entry.task_name
   $matches=@($items | Where-Object {[string]$_.task_name -ceq $n})
   if($matches.Count -ne 1){
    $errors+=@('MISSING_OR_DUPLICATE_ORIGINAL_TASK')
    continue
   }
   $row=$matches[0]
   $saved=[string]$row.backup_xml_text
   $current=[string]$row.current_task_xml_text
   if([string]$row.backup_file_sha256 -cne [string]$entry.xml_sha256){
    $errors+=@('BACKUP_FILE_HASH_MISMATCH')
   }
   if($saved.Length -eq 0 -or $saved -cne $current){
    $errors+=@('BACKUP_XML_NOT_EQUAL_ORIGINAL')
    continue
   }
   if($row.current_task_running -ne $true -or
      $row.native_task_enabled -ne $true){
    $errors+=@('ORIGINAL_TASK_NOT_ENABLED_RUNNING')
   }
   try{
    $xml=[System.Xml.XmlDocument]::new()
    $xml.XmlResolver=$null
    $xml.LoadXml($saved)
    if($xml.DocumentElement.LocalName -cne 'Task'){
     $errors+=@('WRONG_TASK_XML_ROOT')
     continue
    }
    $user=$xml.SelectSingleNode('/*[local-name()="Task"]/*[local-name()="Principals"]/*[local-name()="Principal"]/*[local-name()="UserId"]')
    if($null -eq $user -or
       [string]$user.InnerText -notin @('SYSTEM','NT AUTHORITY\SYSTEM','S-1-5-18')){
     $errors+=@('NON_SYSTEM_ORIGINAL_TASK')
    }
    $triggers=@($xml.SelectNodes('/*[local-name()="Task"]/*[local-name()="Triggers"]/*'))
    if($triggers.Count -ne 1 -or $triggers[0].LocalName -cne 'BootTrigger'){
     $errors+=@('ORIGINAL_BOOT_TRIGGER_CHANGED')
    }
    $restart=$xml.SelectSingleNode('/*[local-name()="Task"]/*[local-name()="Settings"]/*[local-name()="RestartOnFailure"]')
    $countNode=$xml.SelectSingleNode('/*[local-name()="Task"]/*[local-name()="Settings"]/*[local-name()="RestartOnFailure"]/*[local-name()="Count"]')
    $interval=$xml.SelectSingleNode('/*[local-name()="Task"]/*[local-name()="Settings"]/*[local-name()="RestartOnFailure"]/*[local-name()="Interval"]')
    $multiple=$xml.SelectSingleNode('/*[local-name()="Task"]/*[local-name()="Settings"]/*[local-name()="MultipleInstancesPolicy"]')
    if($null -eq $restart -or $null -eq $countNode -or $null -eq $interval -or $null -eq $multiple -or
       [string]$countNode.InnerText -cne '3' -or
       [string]$interval.InnerText -cne 'PT1M' -or
       [string]$multiple.InnerText -cne 'IgnoreNew'){
     $errors+=@('ORIGINAL_RESTART_POLICY_CHANGED')
    }
    $actions=@($xml.SelectNodes('/*[local-name()="Task"]/*[local-name()="Actions"]/*'))
    if($actions.Count -ne 1 -or $actions[0].LocalName -cne 'Exec'){
     $errors+=@('ORIGINAL_ACTION_SCOPE_CHANGED')
     continue
    }
    $cmdNode=$xml.SelectSingleNode('/*[local-name()="Task"]/*[local-name()="Actions"]/*[local-name()="Exec"]/*[local-name()="Command"]')
    $argsNode=$xml.SelectSingleNode('/*[local-name()="Task"]/*[local-name()="Actions"]/*[local-name()="Exec"]/*[local-name()="Arguments"]')
    $workingNode=$xml.SelectSingleNode('/*[local-name()="Task"]/*[local-name()="Actions"]/*[local-name()="Exec"]/*[local-name()="WorkingDirectory"]')
    if($null -eq $cmdNode -or [string]::IsNullOrWhiteSpace([string]$cmdNode.InnerText)){
     $errors+=@('ORIGINAL_ACTION_EXEC_MISSING')
     continue
    }
    $argsValue=''
    $workingValue=''
    if($null -ne $argsNode){$argsValue=[string]$argsNode.InnerText}
    if($null -ne $workingNode){$workingValue=[string]$workingNode.InnerText}
    $expectedScript=if($n -ceq 'CryptoMiniPC-V2R4PaperCandidates'){'v2r4-paper-local-runtime.py'}else{'wait_launcher.py'}
    if($argsValue -notmatch [regex]::Escape($expectedScript)){
     $errors+=@('ORIGINAL_ACTION_NOT_BOUND_TO_EXPECTED_SCRIPT')
    }
    $actionText=@([string]$cmdNode.InnerText,$argsValue,$workingValue) -join ([string][char]10)
    $sha=[Security.Cryptography.SHA256]::Create()
    try{
     $hash=([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($actionText)))).Replace('-','').ToLowerInvariant()
    }finally{$sha.Dispose()}
    # Exact original 15-Oct native-backup newline-delimited serialization.
    # PR313 uses a different pipe-delimited hash: do not compare against it.
    if($hash -cne [string]$entry.action_sha256){
     $errors+=@('ORIGINAL_BACKUP_ACTION_HASH_MISMATCH')
    }
   }catch{
    $errors+=@('UNPARSABLE_ORIGINAL_TASK_XML')
   }
  }
 }
 return [pscustomobject]@{
  kind='V3_ORIGINAL_TASK_RESTORE_PREVIEW_OFFLINE_ONLY_V1'
  preview_structure_only_pass=($errors.Count -eq 0)
  preview_errors=@($errors | Select-Object -Unique)
  full_host_source_and_task_identity_proven_here=$false
  original_host_backup_acl_proven_here=$false
  original_host_disk_bytes_proven_here=$false
  protected_lifecycle_cloudsync_runtime_proven_here=$false
  task_scheduler_import_or_restore_invoked=$false
  task_process_marker_cloud_writes=0
  actual_restore_test_passed=$false
  native_no_rearm_stop_ack_passed=$false
  v3_release_authorized=$false
  technical_release_proofs_credited=0
 }
}


# Pure physical-fence choreography preview: NEVER issues commands or authorizes
# Task/PID/marker/CAS changes. Receipt values below are SYNTHETIC UNTRUSTED
# inputs; actual Windows/CLOUD receipts and separate permits are mandatory.
function Get-V3SingleWriterFenceDryRunPlan([object]$Receipt) {
 $decision='BLOCK_MISSING_OR_INVALID_RECEIPT'
 $errors=@()
 if($null -eq $Receipt){
  $errors+=@('MISSING_INPUT')
 }else{
  if([string]$Receipt.kind -cne 'V3_SINGLE_WRITER_FENCE_DRYRUN_SIMULATION_V1' -or
     [string]$Receipt.predecessor_series_id -cne 'PAPER-V2R4-20261009T110135Z' -or
     $Receipt.paper_only -ne $true -or $Receipt.real_money_actions -ne $false -or
     -not(Test-V3ScopedIntakeTaskSet -Names @($Receipt.intake_task_names))){
   $errors+=@('INVALID_PREDECESSOR_OR_TASK_SCOPE')
  }
  $preserved=@($Receipt.protected_task_names)
  $required=@('CryptoMiniPC-V2R4PaperLifecycle','CryptoMiniPC-V2R4PaperCloudSync') | Sort-Object
  if($preserved.Count -ne 2 -or
     (@($preserved | Sort-Object) -join '|') -cne ($required -join '|') -or
     $Receipt.protected_tasks_running -ne $true){
   $errors+=@('PROTECTED_FOLLOWUP_ROLES_NOT_RUNNING')
  }
  if($Receipt.source_pins_verified -ne $true -or
     $Receipt.mode_lineage_fresh -ne $true -or
     $Receipt.wait_all_descendants_verified -ne $true -or
     $Receipt.original_cloud_only_readback -ne $true -or
     $Receipt.v3_writer_running -ne $false){
   $errors+=@('ORIGINAL_SOURCE_LINEAGE_OR_CLOUD_UNTRUSTED')
  }
  if($Receipt.backup_readback_verified -ne $true -or
     -not(Test-V3ScopedOriginalBackupContract -Manifest $Receipt.backup_proposal)){
   $errors+=@('BACKUP_CONTRACT_OR_ORIGINAL_READBACK_MISSING')
  }
  # The 19-Oct PR332 drill was a different vintage: do not let its synthetic
  # backup/old process flags advance ANY current PR515 stop/no-rearm phase.
  # These caller fields are still synthetic and never become host authority.
  if(-not(Test-V3Pr515FreshRecoveryIdentity -Preview $Receipt.current_pr515_readonly_preview) -or
     $Receipt.pr515_sha_pin_separately_verified -ne $true -or
     $Receipt.current_backup_original_xml_prestop_verified -ne $true){
   $errors+=@('CURRENT_PR515_ORIGINAL_BACKUP_IDENTITY_UNVERIFIED')
  }
  $taskRows=@($Receipt.intake_task_states)
  if($taskRows.Count -ne 2 -or
     -not(Test-V3ScopedIntakeTaskSet -Names @($taskRows | ForEach-Object {[string]$_.task_name}))){
   $errors+=@('WRONG_NATIVE_INTAKE_TASK_ROWS')
  }
  $phase=[string]$Receipt.phase
  $casOutcome=[string]$Receipt.cas_outcome
  $casWasInvoked=($Receipt.cas_invoked -eq $true)
  if($null -eq $Receipt.cas_invoked -or
     $casOutcome -notin @('NOT_INVOKED','UNKNOWN','COMMITTED','NOT_COMMITTED')){
   $errors+=@('AMBIGUOUS_CAS_OBSERVATION')
  }
  if($errors.Count -eq 0){
   $states=@($taskRows | ForEach-Object {[string]$_.state})
   $allRunning=(@($states | Where-Object {$_ -cne 'Running'}).Count -eq 0)
   $allDisabled=(@($states | Where-Object {$_ -cne 'Disabled'}).Count -eq 0)
   $marker=[string]$Receipt.fence_marker_phase
   # Two independent no-rearm owners; a single combined boolean or phase name
   # cannot prove that native Windows AND the existing Supervisor are fenced.
   # Only original physical readbacks may establish these in a future permit.
   $separateNoRearm=(
    $Receipt.native_windows_disable_and_no_rearm_readback -eq $true -and
    $Receipt.supervisor_intake_restart_suppressed_readback -eq $true -and
    [string]$Receipt.supervisor_reported_fence_mode -ceq $marker
   )
   # An ARMED marker is deliberately not a substitute for native task disable.
   $taskDisableAck=(
    $Receipt.both_native_tasks_disabled_readback -eq $true -and
    $allDisabled
   )
   if($casWasInvoked -or $casOutcome -ne 'NOT_INVOKED' -or $phase -in @('CAS_INVOKED','CLOUD_COMMITTED')){
    # An attempted CAS crosses the irrevocable *automatic rearm* boundary.
    if($phase -eq 'CLOUD_COMMITTED' -and $marker -eq 'CLOUD_COMMITTED' -and $casOutcome -eq 'COMMITTED' -and $allDisabled){
     $decision='HOLD_POSTCOMMIT_OLD_INTAKE_FENCED_KEEP_AFTERCARE'
    }else{
     $decision='HOLD_CAS_ATTEMPTED_MANUAL_CLOUD_RECONCILIATION'
    }
   }elseif($phase -eq 'DISCOVERY' -and $marker -eq 'ABSENT' -and $allRunning){
    $decision='REVIEW_ARM_FENCE_SEPARATE_PHYSICAL_APPROVAL'
   }elseif($phase -eq 'ARMED' -and $marker -eq 'ARMED' -and $allRunning){
    $decision='REVIEW_DISABLE_ONLY_CANDIDATES_AND_WAIT'
   }elseif($phase -eq 'TASKS_DISABLED' -and $marker -eq 'ARMED' -and $taskDisableAck -and
      $separateNoRearm){
    $decision='REVIEW_BOUNDED_OLD_INTAKE_STOP_AND_FRESH_PROCESS_READBACK'
   }elseif($phase -eq 'STOP_RECORDED' -and $marker -eq 'ARMED' -and $taskDisableAck -and
      $separateNoRearm -and
      $Receipt.old_intake_process_count -is [int] -and [int]$Receipt.old_intake_process_count -eq 0){
    $decision='REVIEW_QUIESCED_FENCE_WITH_ORIGINAL_AFTERCARE'
   }elseif($phase -eq 'QUIESCED' -and $marker -eq 'QUIESCED' -and $taskDisableAck -and
      $separateNoRearm -and
      $Receipt.old_intake_process_count -is [int] -and [int]$Receipt.old_intake_process_count -eq 0){
    # Distinct fresh Supervisor cycles and still-running PR515 aftercare are
    # REQUIRED *after* the native stop, not inherited from old pre-stop reports.
    if($Receipt.two_distinct_quiesced_supervisor_cycles_readback -ne $true -or
       $Receipt.pr515_cloudsync_precommit_no_network_hold_readback -ne $true -or
       $Receipt.current_backup_xml_after_quiesce_readback -ne $true -or
       $Receipt.independent_old_only_cloud_readback_after_quiesce -ne $true -or
       $Receipt.independent_cas_never_invoked_readback_after_quiesce -ne $true){
     $decision='HOLD_PR515_QUIESCED_OR_CLOUD_ACK_INCOMPLETE'
    }elseif([int]$Receipt.authentic_technical_e2e_proofs -eq 6 -and
       $Receipt.model_budget_separately_approved -eq $true){
     $decision='REVIEW_SEPARATE_CLOUD_CAS_APPROVAL_NO_EXECUTION'
    }else{
     $decision='HOLD_SIX_E2E_AND_BUDGET_APPROVAL'
    }
   }else{
    $decision='HOLD_INCONSISTENT_FENCE_STATE_OR_NO_REARM'
   }
  }
 }
 return [pscustomobject]@{
  kind='V3_FENCE_DRYRUN_DISPOSITION_OFFLINE_ONLY_V1'
  simulated_next_review=$decision
  input_errors=@($errors)
  intended_scope_only=@('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait')
  protected_tasks_must_keep_running=@('CryptoMiniPC-V2R4PaperLifecycle','CryptoMiniPC-V2R4PaperCloudSync')
  # Fixed, inert sequencing contract for a later separately authorized owner.
  # Strings below are labels, not scripts or runtime execution privileges.
  pre_cas_physical_order_preview=@(
   'READBACK_ORIGINAL_BACKUP_TASK_XML_AND_CURRENT_SOURCE_PINS',
   'REQUIRE_EFFECTIVE_PR515_CLOUDSYNC_SHA_AND_TWO_FRESH_BACKUP_XML_HASHES',
   'PROPOSE_ATOMIC_ARMED_MARKER_AND_CONFIRM_SUPERVISOR_ACK',
   'DISABLE_ONLY_ORIGINAL_CANDIDATES_AND_WAIT',
   'READBACK_BOTH_WINDOWS_TASKS_DISABLED_AND_NO_REARM',
   'STOP_ONLY_ORIGINAL_CANDIDATES_AND_WAIT_TASK_OWNERS',
   'READBACK_ZERO_INTAKE_PROCESSES_AND_PROTECTED_AFTERCARE',
   'RECORD_AND_READBACK_ATOMIC_QUIESCED_MARKER',
   'REQUIRE_TWO_DISTINCT_QUIESCED_SUPERVISOR_CYCLES_AND_PR515_CLOUDSYNC_PRECOMMIT_HOLD',
   'REQUIRE_FRESH_POSTSTOP_TASK_XML_AND_INDEPENDENT_CLOUD_CAS_NEVER_READBACK',
   'HOLD_FOR_SEPARATELY_APPROVED_CLOUD_CAS'
  )
  rollback_boundary_if_any_cas_invoked='NO_AUTOMATIC_OLD_INTAKE_REARM_AND_MANUAL_CLOUD_RECONCILIATION'
  native_and_supervisor_independent_no_rearm_required=$true
  pr515_current_backup_and_two_hash_identity_policy_required=$true
  pre_cas_recovery_only_if_cas_never_attempted=$true
  unknown_cas_fail_closed_holds_fence=$true
  step_implementation_present=$false
  proof_is_synthetic_not_live=$true
  native_task_disable_or_stop_permitted=$false
  process_kill_permitted=$false
  marker_write_permitted=$false
  automatic_old_intake_rearm_permitted=$false
  cloud_cas_invoke_permitted=$false
  model_spend_or_real_money_permitted=$false
  physical_quiescence_verified_here=$false
  full_e2e_release_proofs_credited=0
 }
}


# Pure, externally signed ORIGINALHOST receipt authenticity primitive.
# This does NOT collect/attest actual Windows PID, loaded bytecode, OS-lock,
# signer ACL, Cloud CAS, maintenance or the six genuine source-origin proofs.
# The SHA256 certificate pin MUST come from a separately reviewed immutable
# release manifest protected from the untrusted worker/caller; a caller-selected
# pin or this function alone is NEVER native Paper release authorization.
# 21-Oct physical key DACL readback: SYSTEM and Administrators have broad ALLOW
# entries. Therefore a mathematically valid TPM CMS signature alone cannot
# establish an INDEPENDENT signer/release role or protect against SYSTEM.
# The existing external owner, six real proofs, separate Cloud CAS and final
# user decision are mandatory; do not broaden key ACL or create a new signer.
# Invoke only after the independent Windows owner produces a detached CMS
# signature over the exact original receipt UTF-8 bytes, NOT a local self-hash.
# The signer private key is never stored, read or generated by this script.
function Test-V3IndependentOriginalHostCmsSignature(
 [byte[]]$ReceiptUtf8,[byte[]]$DetachedCms,
 [string]$ReviewedSignerCertificateSha256
) {
 $out=[ordered]@{
  kind='V3_ORIGINALHOST_DETACHED_CMS_CRYPTO_ONLY_V1'
  crypto_signature_valid=$false
  originalhost_process_or_loaded_bytes_independently_proven=$false
  originalhost_key_acl_and_signer_role_proven=$false
  cloud_cas_authorized=$false
  v3_paper_release_authorized=$false
  six_actual_e2e_proofs_credited=0
 }
 if($null -eq $ReceiptUtf8 -or $ReceiptUtf8.Length -lt 2 -or
    $ReceiptUtf8.Length -gt 65536 -or
    $null -eq $DetachedCms -or $DetachedCms.Length -lt 32 -or
    $DetachedCms.Length -gt 32768 -or
    $ReviewedSignerCertificateSha256 -cnotmatch '^[a-f0-9]{64}$'){
  return [pscustomobject]$out
 }
 try {
  # System.Security.Cryptography.Pkcs is part of Windows/.NET, no external
  # package, TLS callback, Cloud/Secret connection or network invocation.
  $content=[System.Security.Cryptography.Pkcs.ContentInfo]::new($ReceiptUtf8)
  $signed=[System.Security.Cryptography.Pkcs.SignedCms]::new($content,$true)
  $signed.Decode($DetachedCms)
  if(-not $signed.Detached -or $signed.SignerInfos.Count -ne 1){
   return [pscustomobject]$out
  }
  $signer=$signed.SignerInfos[0]
  # The exact public certificate pin is NOT enough: deny SHA-1 digests.
  # Only SHA-256 CMS digests can be cryptographically valid (not released).
  if([string]$signer.DigestAlgorithm.Value -cne '2.16.840.1.101.3.4.2.1'){
   return [pscustomobject]$out
  }
  if($null -eq $signer.Certificate){return [pscustomobject]$out}
  $cert=$signer.Certificate
  $hash=[System.Security.Cryptography.SHA256]::Create()
  try {
   $pinned=([System.BitConverter]::ToString(
    $hash.ComputeHash([byte[]]$cert.RawData))).Replace('-','').ToLowerInvariant()
  } finally {$hash.Dispose()}
  if($pinned -cne $ReviewedSignerCertificateSha256 -or
     $cert.NotBefore.ToUniversalTime() -gt [datetime]::UtcNow -or
     $cert.NotAfter.ToUniversalTime() -lt [datetime]::UtcNow){
   return [pscustomobject]$out
  }
  # true = verify signature mathematically WITHOUT accepting arbitrary CA
  # chain validation as an owner identity. ONLY a separately reviewed exact
  # certificate pin can supply the one allowed public verification key.
  $signed.CheckSignature($true)
  $out.crypto_signature_valid=$true
 } catch {
  # Unknown algorithm, malformed CMS, wrong message/key or .NET load failure
  # all fail closed. Do not expose untrusted exception content or secrets.
 }
 return [pscustomobject]$out
}


# Cross-machine signed CURRENT CAS-INACCESSIBILITY proof. Reuse the
# established Notebook Reader signer, original host PKCS verifier and one
# externally reviewed public certificate SHA. No historical NEVER inference.
# Pure: negative/positive claims are never permission to restore or stop.
function Test-V3Pr515SignedCurrentNoCasCustody(
 [byte[]]$Payload,[byte[]]$Cms,[string]$ReviewedCertSha256,
 [string]$CurrentOriginalFenceSha256
) {
 $out=[ordered]@{
  kind='V3_PR515_SIGNED_CURRENT_CAS_UNAVAILABLE_REVIEW_V1'
  status='HOLD_SIGNED_CUSTODY_UNVERIFIED'
  authenticated_observed_at_utc=''
  signature_and_current_fence_match=$false
  current_notebook_reader_no_cas_capability_observed=$false
  previous_cas_attempts_excluded=$false
  independent_cloud_old_only_verified_here=$false
  precommit_task_restore_authorized=$false
  native_stop_authorized=$false
  cas_execution_authorized=$false
  v3_paper_release_authorized=$false
 }
 if($Payload.Length -lt 100 -or $Payload.Length -gt 4096 -or
    $Cms.Length -lt 64 -or $Cms.Length -gt 32768 -or
    $CurrentOriginalFenceSha256 -cnotmatch '^[a-f0-9]{64}$'){
  return [pscustomobject]$out
 }
 $sig=Test-V3IndependentOriginalHostCmsSignature -ReceiptUtf8 $Payload -DetachedCms $Cms -ReviewedSignerCertificateSha256 $ReviewedCertSha256
 if($sig.crypto_signature_valid -ne $true){return [pscustomobject]$out}
 try {
  $wire=([Text.UTF8Encoding]::new($false,$true)).GetString($Payload)
  $obj=$wire|ConvertFrom-Json -ErrorAction Stop
  $keys=@('kind','observed_at_utc','actor','role','epochs','intents',
   'installed_cas_rpc_count','executor_login','operator_can_set_executor',
   'reader_writer_set_role','reader_can_append','historical_cas_never_proven',
   'restore_authorized','original_fence_sha256')
  $actual=@($obj.PSObject.Properties.Name)
  if($obj -isnot [pscustomobject] -or $actual.Count -ne $keys.Count -or
     @($actual|Where-Object {$_ -cnotin $keys}).Count -ne 0){throw 'CUSTODY_FIELDS'}
  foreach($field in $keys){
   if(@([regex]::Matches($wire,('"'+[regex]::Escape($field)+'"\s*:'))).Count -ne 1){
    throw 'CUSTODY_DUPLICATE'
   }
  }
  $m=[regex]::Match($wire,'"observed_at_utc"\s*:\s*"(?<v>[^"\\]*)"')
  if(-not $m.Success -or [string]$m.Groups['v'].Value -cnotmatch
     '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$'){throw 'CUSTODY_TIME'}
  $t=[datetimeoffset]::MinValue
  if(-not([datetimeoffset]::TryParseExact([string]$m.Groups['v'].Value,
     "yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'",
     [Globalization.CultureInfo]::InvariantCulture,
     [Globalization.DateTimeStyles]::AssumeUniversal,
     [ref]$t))){throw 'CUSTODY_DATE'}
  $age=([datetimeoffset]::UtcNow-$t).TotalSeconds
  if($age -lt -5 -or $age -gt 90 -or
     [string]$obj.kind -cne 'V3_NOTEBOOK_CURRENT_NO_CAS_CAPABILITY_CUSTODY_V1' -or
     [string]$obj.actor -cne 'v3_cas_audit_reader_actor' -or
     [string]$obj.role -cne 'v3_cas_audit_reader' -or
     [string]$obj.epochs -cne '0' -or
     [string]$obj.intents -cne '0' -or
     [string]$obj.installed_cas_rpc_count -cne '0' -or
     [string]$obj.original_fence_sha256 -cne $CurrentOriginalFenceSha256 -or
     $obj.executor_login -ne $false -or
     $obj.operator_can_set_executor -ne $false -or
     $obj.reader_writer_set_role -ne $false -or
     $obj.reader_can_append -ne $false -or
     $obj.historical_cas_never_proven -ne $false -or
     $obj.restore_authorized -ne $false){throw 'CUSTODY_CURRENT_POSTURE'}
  $out.authenticated_observed_at_utc=[string]$m.Groups['v'].Value
  $out.status='SIGNED_CURRENT_NO_CAS_CAPABILITY_MATCH_NOT_RELEASE'
  $out.signature_and_current_fence_match=$true
  $out.current_notebook_reader_no_cas_capability_observed=$true
 }catch{
  # No signed raw payload or confidential exception is emitted.
 }
 return [pscustomobject]$out
}

# Join the existing CMS-verified current Notebook CAS posture with the existing
# public current-series inventory. This is deliberately NOT independently
# authenticated public Cloud inventory and NEVER grants restore authority.
# The same original fence is required from the CMS verifier, not a caller flag.
function Get-V3Pr515SignedCasAndCloudSeriesReview([object]$SignedCas,[object]$Cloud,[string]$CurrentOriginalFenceSha256) {
 $out=[ordered]@{
  kind='V3_PR515_SIGNED_CAS_AND_PUBLIC_CLOUD_JOIN_V1'
  disposition='HOLD_SIGNED_CAS_OR_CLOUD_INVENTORY_DRIFT'
  signed_current_cas_matched=$false
  public_current_old_only_matched=$false
  same_original_fence_bound_by_signed_cas=$false
  observations_within_30_seconds=$false
  independent_public_cloud_origin_authenticated=$false
  complete_cas_attempt_history_proven=$false
  native_stop_or_restore_authorized=$false
  cloud_cas_authorized=$false
  v3_paper_release_authorized=$false
 }
 if($null -ne $SignedCas -and $CurrentOriginalFenceSha256 -cmatch '^[a-f0-9]{64}$' -and
    [string]$SignedCas.kind -ceq 'V3_PR515_SIGNED_CURRENT_CAS_UNAVAILABLE_REVIEW_V1' -and
    [string]$SignedCas.status -ceq 'SIGNED_CURRENT_NO_CAS_CAPABILITY_MATCH_NOT_RELEASE' -and
    $SignedCas.signature_and_current_fence_match -eq $true -and
    $SignedCas.current_notebook_reader_no_cas_capability_observed -eq $true -and
    $SignedCas.previous_cas_attempts_excluded -eq $false -and
    $SignedCas.precommit_task_restore_authorized -eq $false){
  $out.signed_current_cas_matched=$true
  $out.same_original_fence_bound_by_signed_cas=$true
  $signedAt=[datetimeoffset]::MinValue
  $cloudAt=[datetimeoffset]::MinValue
  if([string]$SignedCas.authenticated_observed_at_utc -cmatch
       '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z
   $out.public_current_old_only_matched=$true
   $out.disposition='REVIEW_ONLY_SIGNED_CAS_PLUS_UNAUTHENTICATED_PUBLIC_CLOUD_NOT_RELEASE'
  }
 }
 return [pscustomobject]$out
}

 -and
     [datetimeoffset]::TryParse([string]$SignedCas.authenticated_observed_at_utc,[ref]$signedAt) -and
     [datetimeoffset]::TryParse([string]$Cloud.observed_at_utc,[ref]$cloudAt) -and
     [math]::Abs(($signedAt-$cloudAt).TotalSeconds) -le 30){
   $out.observations_within_30_seconds=$true
  }
  if($out.observations_within_30_seconds -eq $true -and
     (Test-V3PrecommitCurrentCloudInventory -Inventory $Cloud)){
   $out.public_current_old_only_matched=$true
   $out.disposition='REVIEW_ONLY_SIGNED_CAS_PLUS_UNAUTHENTICATED_PUBLIC_CLOUD_NOT_RELEASE'
  }
 }
 return [pscustomobject]$out
}

# Only validates authentic CURRENT Notebook Reader data after detached CMS
# transfer. Reuses the existing exact SHA256-pinned cryptographic verifier;
# this does not authenticate the physical Notebook location, authorize native
# STOP/restore, prove past CAS NEVER, or promote to a Paper release token.
function Test-V3SignedNotebookPrecommitInventory(
 [byte[]]$ReceiptUtf8,[byte[]]$DetachedCms,[string]$ReviewedCertSha256){
 $out=[ordered]@{
  kind='V3_NOTEBOOK_PRECOMMIT_SIGNED_READER_ORIGINALHOST_REVIEW_V1'
  status='HOLD_SIGNED_READER_INVALID_OR_STALE'
  matched_signer_certificate_sha256=$false
  current_private_reader_zero_counts_verified=$false
  independent_notebook_key_custody_verified_here=$false
  independent_cas_attempt_history_complete=$false
  historical_cas_never_verified=$false
  native_stop_or_restore_authorized=$false
  cloud_cas_dispatch_authorized=$false
  v3_paper_release_authorized=$false
 }
 if($null -eq $ReceiptUtf8 -or $null -eq $DetachedCms -or
    $ReceiptUtf8.Length -lt 80 -or $ReceiptUtf8.Length -gt 4096 -or
    $ReviewedCertSha256 -cnotmatch '^[a-f0-9]{64}$'){
  return [pscustomobject]$out
 }
 $crypto=Test-V3IndependentOriginalHostCmsSignature -ReceiptUtf8 $ReceiptUtf8 -DetachedCms $DetachedCms -ReviewedSignerCertificateSha256 $ReviewedCertSha256
 if($crypto.crypto_signature_valid -ne $true){return [pscustomobject]$out}
 $out.matched_signer_certificate_sha256=$true
 try {
  $str=[Text.UTF8Encoding]::new($false,$true).GetString($ReceiptUtf8)
  $obj=$str | ConvertFrom-Json -ErrorAction Stop
  $keys=@('kind','observed_at_utc','actor','role','epochs','intents',
   'writer_role_access','append_access','history_never_proven','restore_authorized')
  $actual=@($obj.PSObject.Properties.Name)
  if($actual.Count -ne $keys.Count -or @($actual|Where-Object {$_ -cnotin $keys}).Count -ne 0){
   throw 'V3_NOTEBOOK_READER_EXTRA_FIELDS'
  }
  foreach($key in $keys){
   if(@([regex]::Matches($str,('"'+[regex]::Escape($key)+'"\s*:'))).Count -ne 1){
    throw 'V3_NOTEBOOK_READER_MISSING_OR_DUPLICATE_FIELD'
   }
  }
  $m=[regex]::Match($str,'"observed_at_utc"\s*:\s*"(?<utc>[^"]*)"')
  if(-not $m.Success -or [string]$m.Groups['utc'].Value -cnotmatch
     '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$'){
   throw 'V3_NOTEBOOK_READER_TIMESTAMP_INVALID'
  }
  $timestamp=[datetimeoffset]::MinValue
  $style=[Globalization.DateTimeStyles]::AssumeUniversal -bor
         [Globalization.DateTimeStyles]::AdjustToUniversal
  if(-not [datetimeoffset]::TryParseExact(
     [string]$m.Groups['utc'].Value,"yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'",
     [Globalization.CultureInfo]::InvariantCulture,$style,[ref]$timestamp)){
   throw 'V3_NOTEBOOK_READER_TIMESTAMP_UNPARSEABLE'
  }
  $age=([datetimeoffset]::UtcNow-$timestamp).TotalSeconds
  if($age -lt -5 -or $age -gt 120 -or
     [string]$obj.kind -cne 'V3_CAS_READER_CURRENT_PRIVATE_AUDIT_SNAPSHOT_V1' -or
     [string]$obj.actor -cne 'v3_cas_audit_reader_actor' -or
     [string]$obj.role -cne 'v3_cas_audit_reader' -or
     [string]$obj.epochs -cne '0' -or
     [string]$obj.intents -cne '0' -or
     $obj.writer_role_access -ne $false -or
     $obj.append_access -ne $false -or
     $obj.history_never_proven -ne $false -or
     $obj.restore_authorized -ne $false){
   throw 'V3_NOTEBOOK_READER_AUTHENTICATED_INVENTORY_MISMATCH'
  }
  $out.status='SIGNED_CURRENT_PRIVATE_READER_EMPTY_SNAPSHOT_NOT_RELEASE'
  $out.current_private_reader_zero_counts_verified=$true
 } catch {
  # No foreign JSON or actual DB exception text is printed or trusted.
 }
 return [pscustomobject]$out
}

# A real Windows XML recovery artifact is needed before any *later* Paper
# Cutover. Reuse this existing original operator; never clone its STOP/RESTORE
# paths or grant an alternate task/write/Cloud authority. Explicit opt-in is
# restricted to two durable recovery copies while both old intake roles RUN.
# A JSON plan or CI fixture never counts as an originalhost release receipt.
function Get-V3OriginalNativeActionSha([object]$Action) {
 if($null -eq $Action){throw 'native Task action absent'}
 # The ORIGINAL four-role V2R4 Windows inspector hashes three strings
 # joined with a pipe, not the V3 Task's NUL-delimited digest.
 $joined=@([string]$Action.Execute,[string]$Action.Arguments,
  [string]$Action.WorkingDirectory) -join '|'
 $bytes=[Text.UTF8Encoding]::new($false).GetBytes($joined)
 $digest=[Security.Cryptography.SHA256]::Create()
 try {return ([BitConverter]::ToString($digest.ComputeHash($bytes))).Replace('-','').ToLowerInvariant()}
 finally {$digest.Dispose()}
}
# Exact disk reread of new original Task export (not historical restore proof).
function Test-V3FreshBackupFileBytes([string]$Path,[string]$ExpectedSha,[string]$ExpectedXml) {
 if([string]::IsNullOrWhiteSpace($Path) -or
    $ExpectedSha.Length -ne 64 -or
    $ExpectedSha -match '[^a-f0-9]' -or
    [string]::IsNullOrWhiteSpace($ExpectedXml) -or
    $ExpectedXml.Length -lt 100 -or $ExpectedXml.Length -gt 65536){return $false}
 try{
  $entry=Get-Item -LiteralPath $Path -Force -ErrorAction Stop
  if($entry.PSIsContainer -or
     [bool]($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
     $entry.Length -lt 100 -or $entry.Length -gt 131072){return $false}
  $actual=[IO.File]::ReadAllBytes($entry.FullName)
  $expected=[Text.UTF8Encoding]::new($false).GetBytes($ExpectedXml)
  if($actual.Length -ne $expected.Length){return $false}
  $hash=[Security.Cryptography.SHA256]::Create()
  try{
   $digest=([BitConverter]::ToString($hash.ComputeHash($actual))).Replace('-','').ToLowerInvariant()
  }finally{$hash.Dispose()}
  if($digest -cne $ExpectedSha){return $false}
  for($i=0;$i -lt $actual.Length;$i++){
   if($actual[$i] -ne $expected[$i]){return $false}
  }
  return $true
 }catch{return $false}
}

function Save-V3OriginalIntakeXmlOnly([object]$Report,[string]$Root,
 [string]$CandidateSha,[string]$WaitSha) {
 if([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT){
  throw 'original Windows host required for recovery artifact'
 }
 $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
 $principal=[Security.Principal.WindowsPrincipal]::new($identity)
 if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){
  throw 'original local administrator confirmation required'
 }
 $real=[IO.Path]::GetFullPath($Root).TrimEnd('\')
 if(-not $real.Equals('C:\Users\ADMIN\Trading',[StringComparison]::OrdinalIgnoreCase)){
  throw 'original Trading root identity mismatch'
 }
 foreach($location in @($real,(Join-Path $real 'State'))){
  $item=Get-Item -LiteralPath $location -Force -ErrorAction Stop
  if(-not $item.PSIsContainer -or
     [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)){
   throw 'original state directory missing or linked'
  }
 }
 if(-not(Test-V3CutoverPreparationPolicy -Report $Report -FenceMarkerPresent $false -MaintenanceMarkerPresent $false)){
  throw 'original V2R4 task preflight not accepted'
 }
 $expected=@{
  'CryptoMiniPC-V2R4PaperCandidates'=$CandidateSha
  'CryptoMiniPC-V2R4PaperWait'=$WaitSha
 }
 if(-not(Test-V3ScopedIntakeTaskSet -Names @($expected.Keys))){
  throw 'backup task scope widened or incomplete'
 }
 $records=@()
 foreach($name in @('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait')){
  $task=Get-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction Stop
  if([string]$task.State -cne 'Running' -or
     [string]$task.TaskPath -cne '\' -or
     @($task.Actions).Count -ne 1 -or
     [string]$task.Principal.UserId -notin @('SYSTEM','NT AUTHORITY\SYSTEM','S-1-5-18') -or
     [string]$task.Settings.MultipleInstances -cne 'IgnoreNew'){
   throw 'original native task identity/status drift'
  }
  $digest=Get-V3OriginalNativeActionSha $task.Actions[0]
  $read=@($Report.physical_v2r4_paper_task_readback | Where-Object {$_.task_name -ceq $name})
  if($read.Count -ne 1 -or
     $digest -cne $expected[$name] -or
     $digest -cne ([string]$read[0].action_sha256).ToLowerInvariant()){
   throw 'original independent snapshot/native task SHA mismatch'
  }
  $xml=[string](Export-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction Stop)
  if($xml.Length -lt 100 -or $xml.Length -gt 65536 -or
     -not $xml.Contains('<Task')){
   throw 'original native XML not safely exportable'
  }
  $records+=@([pscustomobject]@{name=$name; action_sha256=$digest; xml=$xml})
 }
 if(@($records).Count -ne 2){throw 'backup collection incomplete'}
 # Reject a late conflicting fence/maintenance marker immediately before writes.
 if((Test-Path -LiteralPath (Join-Path $real 'State\v3-experimental-paper-old-intake-fence.json')) -or
    (Test-Path -LiteralPath (Join-Path $real 'State\v2r4-technical-cutover-maintenance.json'))){
  throw 'original V2R4 fence or maintenance marker appeared'
 }
 # New, collision-free original State child. ACL is installed AT CREATION, not
 # after exporting possibly sensitive native Task XML and argument strings.
 $secure=[Security.AccessControl.DirectorySecurity]::new()
 $secure.SetAccessRuleProtection($true,$false)
 foreach($sid in @('S-1-5-18','S-1-5-32-544')){
  $rule=[Security.AccessControl.FileSystemAccessRule]::new(
   [Security.Principal.SecurityIdentifier]::new($sid),
   [Security.AccessControl.FileSystemRights]::FullControl,
   ([Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
    [Security.AccessControl.InheritanceFlags]::ObjectInherit),
   [Security.AccessControl.PropagationFlags]::None,
   [Security.AccessControl.AccessControlType]::Allow)
  $secure.AddAccessRule($rule)
 }
 $folder=Join-Path (Join-Path $real 'State') ('V3Paper-PreCAS-Backup-'+[guid]::NewGuid().ToString('N'))
 $null=[IO.Directory]::CreateDirectory($folder,$secure)
 $manifest=@()
 foreach($record in $records){
  $base=if($record.name -ceq 'CryptoMiniPC-V2R4PaperCandidates'){'Candidates'}else{'WAIT'}
  $xmlPath=Join-Path $folder ($base+'.task.xml')
  $bytes=[Text.UTF8Encoding]::new($false).GetBytes($record.xml)
  $handle=[IO.File]::Open($xmlPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
  try{$handle.Write($bytes,0,$bytes.Length);$handle.Flush($true)}
  finally{$handle.Dispose()}
  $hash=(Get-FileHash -LiteralPath $xmlPath -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
  $manifest+=@([ordered]@{task_name=$record.name;action_sha256=$record.action_sha256;xml_file=$base+'.task.xml';xml_sha256=$hash})
 }
 # Re-read BOTH original tasks after the durable exports to detect races;
 # preserve artifacts, but never report PASS if a task changed meantime.
 foreach($record in $records){
  $after=Get-ScheduledTask -TaskName $record.name -TaskPath '\' -ErrorAction Stop
  if([string]$after.State -cne 'Running' -or @($after.Actions).Count -ne 1 -or
     (Get-V3OriginalNativeActionSha $after.Actions[0]) -cne $record.action_sha256){
   throw 'original native task changed during XML backup: preserve artifacts for review'
  }
 }
 $result=[ordered]@{
  kind='V3_PRECAS_NATIVE_XML_BACKUP_ORIGINALHOST_V1'
  status='ORIGINAL_TASK_XML_BACKUP_ONLY_NOT_RELEASED'
  checked_at_utc=[datetime]::UtcNow.ToString('o')
  predecessor_series_id='PAPER-V2R4-20261009T110135Z'
  native_task_count=2
  original_tasks_still_running=$true
  task_records=$manifest
  original_cloud_series_independently_checked=$false
  imported_or_loaded_v3_code_attested=$false
  v3_release_or_six_proofs_credited=0
  new_v3_writer_started=$false
  cloud_cas_invoked=$false
  scheduler_task_mutations=$false
  original_v2r4_changed=$false
  backup_directory=$folder
 }
 $manifestPath=Join-Path $folder 'backup-manifest.json'
 $manifestBytes=[Text.UTF8Encoding]::new($false).GetBytes(($result|ConvertTo-Json -Depth 6))
 $mh=[IO.File]::Open($manifestPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
 try{$mh.Write($manifestBytes,0,$manifestBytes.Length);$mh.Flush($true)}
 finally{$mh.Dispose()}
 # The newly persisted manifest and both exact file bytes MUST be re-read
 # before the source claims any backup-only success. The already existing
 # historical restore-preview accepts older 15-Oct newline Action hashes:
 # never silently upcast it to this NEW pipe-hash Windows capture.
 $dir=Get-Item -LiteralPath $folder -Force -ErrorAction Stop
 $meta=Get-Item -LiteralPath $manifestPath -Force -ErrorAction Stop
 if(-not $dir.PSIsContainer -or
    [bool]($dir.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
    $meta.PSIsContainer -or
    [bool]($meta.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
    $meta.Length -gt 65536){
  throw 'original backup folder or manifest not securely readable'
 }
 $persisted=Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 -ErrorAction Stop | ConvertFrom-Json
 if([string]$persisted.kind -cne 'V3_PRECAS_NATIVE_XML_BACKUP_ORIGINALHOST_V1' -or
    [string]$persisted.status -cne 'ORIGINAL_TASK_XML_BACKUP_ONLY_NOT_RELEASED' -or
    [string]$persisted.backup_directory -cne $folder -or
    [string]$persisted.predecessor_series_id -cne 'PAPER-V2R4-20261009T110135Z' -or
    [int]$persisted.native_task_count -ne 2 -or
    $persisted.cloud_cas_invoked -ne $false -or
    $persisted.original_v2r4_changed -ne $false -or
    @($persisted.task_records).Count -ne 2){
  throw 'original backup manifest readback inconsistent'
 }
 foreach($record in $records){
  $name=$record.name
  $expectedBase=if($name -ceq 'CryptoMiniPC-V2R4PaperCandidates'){'Candidates'}else{'WAIT'}
  $entry=@($persisted.task_records | Where-Object {$_.task_name -ceq $name})
  if($entry.Count -ne 1 -or
     [string]$entry[0].xml_file -cne ($expectedBase+'.task.xml') -or
     [string]$entry[0].action_sha256 -cne $record.action_sha256 -or
     -not(Test-V3FreshBackupFileBytes -Path (Join-Path $folder ([string]$entry[0].xml_file)) -ExpectedSha ([string]$entry[0].xml_sha256) -ExpectedXml $record.xml)){
   throw 'original backup file/hash/readback mismatch; preserve artifacts'
  }
  # A changed trigger/restart policy with an unchanged Execute tuple is NOT
  # a safely restorable original Task. Independently export fresh native XML
  # and compare complete bytes, then re-read the Task identity/action again.
  $current=[string](Export-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction Stop)
  $currentTask=Get-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction Stop
  if($current -cne $record.xml -or
     [string]$currentTask.State -cne 'Running' -or
     [string]$currentTask.Principal.UserId -notin @('SYSTEM','NT AUTHORITY\SYSTEM','S-1-5-18') -or
     @($currentTask.Actions).Count -ne 1 -or
     (Get-V3OriginalNativeActionSha $currentTask.Actions[0]) -cne $record.action_sha256){
   throw 'original TaskScheduler export/source changed during backup; no release'
  }
 }
 # Terminal success is returned ONLY after durable manifest + exact bytes +
 # full current task XML/Action reread. Still not a restore or cutover proof.
 $result.backup_disk_and_manifest_reread_verified=$true
 $result.current_original_task_xml_still_equal_backup=$true
 $result.actual_restore_test_passed=$false
 $result.v3_paper_release_authorized=$false
 return $result
}


# PR515 successor source owner – prepared ONLY, not connected to the CLI.
# The unconditional -Execute LOCK below is deliberately retained. This one
# function is the *only* native task-mutation source and may be connected only
# by a separately authorized, reviewed originalhost release PR/approval.
# It neither calls Cloud/CAS nor enables/starts/registrations of old intake.
function Invoke-V3Pr515ScopedNativeStopSOURCE_ONLY(
 [string]$Root,[object]$OriginalReadback,[string]$BackupFolder,
 [string]$ReviewedPr515Sha,[string]$SuccessorId,
 [string]$ReviewedRepoSha,[string]$ReviewedBundleSha,[string]$ReviewedStrategySha) {
 # Independent second hard-lock: even dot-sourcing this script cannot execute
 # the native mutations until a separately approved source change removes it.
 throw 'V3_PR515_NATIVE_STOP_SOURCE_UNCONDITIONALLY_LOCKED'
 if([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT){
  throw 'V3_NATIVE_SOURCE_ONLY_ORIGINAL_WINDOWS_REQUIRED'
 }
 $real=[IO.Path]::GetFullPath($Root).TrimEnd('\')
 if(-not $real.Equals('C:\Users\ADMIN\Trading',[StringComparison]::OrdinalIgnoreCase) -or
    $SuccessorId -cnotmatch '^PAPER-V3-[0-9]{8}T[0-9]{6}Z$' -or
    $ReviewedRepoSha -cnotmatch '^[a-f0-9]{40}$' -or
    $ReviewedBundleSha -cnotmatch '^[a-f0-9]{64}$' -or
    $ReviewedStrategySha -cnotmatch '^[a-f0-9]{64}$' -or
    $ReviewedPr515Sha -cnotmatch '^[a-f0-9]{64}$'){
  throw 'V3_PRECAS_SOURCE_OR_REVIEWED_PINS_INVALID'
 }
 $who=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
 if(-not $who.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){
  throw 'V3_PRECAS_ADMINISTRATOR_REQUIRED'
 }
 $fence=Join-Path $real 'State\v3-experimental-paper-old-intake-fence.json'
 $oldFence=Join-Path $real 'State\v2r4-technical-cutover-maintenance.json'
 if((Test-Path -LiteralPath $fence) -or (Test-Path -LiteralPath $oldFence)){
  throw 'V3_PRECAS_CONFLICTING_OR_EXISTING_FENCE'
 }
 $tasks=@('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait')
 $protected=@('CryptoMiniPC-V2R4PaperLifecycle','CryptoMiniPC-V2R4PaperCloudSync')
 if(-not(Test-V3ScopedIntakeTaskSet -Names $tasks) -or
    -not(Test-V3CutoverPreparationPolicy -Report $OriginalReadback -FenceMarkerPresent $false -MaintenanceMarkerPresent $false)){
  throw 'V3_PRECAS_NOT_EXACT_READY_V2R4'
 }
 # No new backup: use exactly the already verified original 22-Oct vintage.
 $pre=Read-V3Pr515FreshRecoveryPreview -Report $OriginalReadback -Root $real -BackupDirectory $BackupFolder -ExpectedCloudSha $ReviewedPr515Sha
 if([string]$pre.status -cne 'COMPATIBLE_READONLY_NOT_RELEASED' -or
    -not(Test-V3Pr515FreshRecoveryIdentity -Preview $pre)){
  throw 'V3_PRECAS_FRESH_XML_OR_PR515_PREVIEW_MISSING'
 }
 foreach($p in $protected){
  $t=Get-ScheduledTask -TaskName $p -TaskPath '\' -ErrorAction Stop
  if([string]$t.State -cne 'Running'){throw 'V3_PRECAS_PROTECTED_AFTERCARE_MUST_KEEP_RUNNING'}
 }
 $supervisorTask=Get-ScheduledTask -TaskName 'CryptoMiniPC-RuntimeSupervisor' -ErrorAction Stop
 if([string]$supervisorTask.State -cne 'Running'){
  throw 'V3_PRECAS_SUPERVISOR_NOT_RUNNING'
 }
 $native=@()
 foreach($name in $tasks){
  $t=Get-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction Stop
  if([string]$t.State -cne 'Running' -or
     @($t.Actions).Count -ne 1 -or
     [string]$t.Principal.UserId -notin @('SYSTEM','NT AUTHORITY\SYSTEM','S-1-5-18')){
   throw 'V3_PRECAS_INTAKE_IDENTITY_CHANGED'
  }
  $native+=@([pscustomobject]@{task=$name;arguments=[string]$t.Actions[0].Arguments})
 }
 # Native complete process inventory, not the PR313 transient PID hint.
 # Other Python command-lines that contain the entire scoped native action
 # are treated as additional owners and fail closed. No arbitrary PID kill.
 $before=@(Get-CimInstance Win32_Process -ErrorAction Stop)
 $seen=@{}
 foreach($p in $before){
  $pidNumber=[int]$p.ProcessId
  if($pidNumber -lt 0 -or $seen.ContainsKey($pidNumber)){
   throw 'V3_PRECAS_BAD_PROCESS_INVENTORY'
  }
  $seen[$pidNumber]=$p
 }
 $roots=@()
 foreach($role in $native){
  if($role.arguments.Length -lt 10){throw 'V3_PRECAS_NATIVE_ARGUMENTS_AMBIGUOUS'}
  $found=@($before | Where-Object {
   [string]$_.Name -match '(?i)^pythonw?\.exe$' -and
   ([string]$_.CommandLine).Replace('\','/').IndexOf(
    $role.arguments.Replace('\','/'),[StringComparison]::OrdinalIgnoreCase) -ge 0
  })
  if($found.Count -lt 1 -or $found.Count -gt 2){
   throw 'V3_PRECAS_NATIVE_PROCESS_OWNER_NOT_UNIQUE'
  }
  $roots+=@($found | ForEach-Object {[int]$_.ProcessId})
 }
 $roots=@($roots | Sort-Object -Unique)
 if($roots.Count -lt 2 -or $roots.Count -gt 4){
  throw 'V3_PRECAS_NATIVE_PROCESS_ROOTS_UNVERIFIED'
 }
 $descendants=@($roots)
 $changed=$true
 while($changed){
  $changed=$false
  foreach($p in $before){
   if([int]$p.ProcessId -eq 0){continue}
   if([int]$p.ParentProcessId -in $descendants -and [int]$p.ProcessId -notin $descendants){
    $descendants+=@([int]$p.ProcessId);$changed=$true
   }
  }
 }
 # The local marker is protected against unintentional peer writes and is
 # created before any Task mutation. On ANY partial failure retain the fence.
 $marker=[ordered]@{
  kind='V3_EXPERIMENTAL_OLD_INTAKE_FENCE_V1'
  phase='ARMED'
  predecessor_series_id='PAPER-V2R4-20261009T110135Z'
  proposed_successor_series_id=$SuccessorId
  proposed_v3_repo_sha=$ReviewedRepoSha
  proposed_v3_bundle_sha256=$ReviewedBundleSha
  proposed_v3_strategy_sha256=$ReviewedStrategySha
  task_names=$tasks
  paper_only=$true
  orders_enabled=$false
  real_money_actions=$false
  persistent_until_explicit_owner_release=$true
 }
 $temp=$fence+'.'+[guid]::NewGuid().ToString('N')+'.tmp'
 $security=[Security.AccessControl.FileSecurity]::new()
 $security.SetAccessRuleProtection($true,$false)
 foreach($sid in @('S-1-5-18','S-1-5-32-544')){
  $rule=[Security.AccessControl.FileSystemAccessRule]::new(
   [Security.Principal.SecurityIdentifier]::new($sid),
   [Security.AccessControl.FileSystemRights]::FullControl,
   [Security.AccessControl.AccessControlType]::Allow)
  $security.AddAccessRule($rule)
 }
 [IO.File]::WriteAllText($temp,($marker|ConvertTo-Json -Depth 5),
  [Text.UTF8Encoding]::new($false))
 Set-Acl -LiteralPath $temp -AclObject $security -ErrorAction Stop
 if(Test-Path -LiteralPath $fence){throw 'V3_PRECAS_FENCE_RACE'}
 [IO.File]::Move($temp,$fence)
 $at=[datetimeoffset]::UtcNow
 # Existing original Supervisor and PR515 CloudSync first acknowledge ARMED.
 $armed=$false
 for($i=0;$i -lt 60;$i++){
  Start-Sleep -Seconds 3
  try{
   $s=Get-Content -LiteralPath (Join-Path $real 'State\minipc-runtime-supervisor.json') -Raw -ErrorAction Stop|ConvertFrom-Json
   $c=Get-Content -LiteralPath (Join-Path $real 'State\v2r4-paper-cloud-sync-heartbeat.json') -Raw -ErrorAction Stop|ConvertFrom-Json
   # This is the SAME already approved Supervisor/PR515 ARMED contract.
   # Never disable an original native Task on a stale, wrong-lane or
   # incomplete first acknowledgment; the separate two-cycle proof after
   # stopping remains mandatory and cannot be inferred from this readback.
   $supervisorAt=[datetimeoffset]::MinValue
   $cloudAt=[datetimeoffset]::MinValue
   $now=[datetimeoffset]::UtcNow
   if([string]$s.checked_at_utc -cnotmatch '(Z|\+00:00)$' -or
      [string]$c.checked_at_utc -cnotmatch '(Z|\+00:00)$' -or
      -not [datetimeoffset]::TryParse([string]$s.checked_at_utc,[ref]$supervisorAt) -or
      -not [datetimeoffset]::TryParse([string]$c.checked_at_utc,[ref]$cloudAt)){
    continue
   }
   $blocked=@($s.tasks | Where-Object {
    $_.task -in $tasks -and
    [string]$_.action -ceq 'V3_INTAKE_SUPERVISOR_REARM_BLOCKED'
   })
   if($supervisorAt -gt $at -and $cloudAt -gt $at -and
      $supervisorAt -ge $now.AddSeconds(-180) -and
      $cloudAt -ge $now.AddSeconds(-180) -and
      $supervisorAt -le $now.AddSeconds(5) -and
      $cloudAt -le $now.AddSeconds(5) -and
      [math]::Abs(($supervisorAt-$cloudAt).TotalSeconds) -le 90 -and
      [string]$s.kind -ceq 'MINIPC_RUNTIME_SUPERVISOR_V1' -and
      [string]$s.status -ceq 'WARNING' -and
      [string]$s.v3_paper_old_intake_fence.mode -ceq 'ARMED' -and
      $s.v3_paper_old_intake_fence.marker_present -eq $true -and
      $s.v3_paper_old_intake_fence.v3_cloud_cas_or_release_authorized -eq $false -and
      $blocked.Count -eq 2 -and
      (Test-V3ScopedIntakeTaskSet -Names @($blocked | ForEach-Object {[string]$_.task})) -and
      [string]$c.kind -ceq 'V2R4_PAPER_CLOUD_SYNC_HEARTBEAT_V1' -and
      [string]$c.status -ceq 'HEALTHY' -and
      [string]$c.mode -ceq 'V3_PRECOMMIT_NO_NETWORK_HOLD' -and
      [string]$c.v3_fence_precommit_phase -ceq 'ARMED' -and
      [string]$c.v3_fence_cloud_sync_lane -ceq 'PRECOMMIT_ORIGINAL' -and
      $c.paper_only -eq $true -and
      $c.order_api -eq $false -and
      $c.real_money_actions -eq $false -and
      $c.cloud_updated -eq $false -and
      $c.cloud_sync_intentionally_paused -eq $true -and
      @($s.restarted).Count -eq 0 -and
      @($s.failed_restarts).Count -eq 0){
    $armed=$true;break
   }
  }catch{}
 }
 if(-not $armed){throw 'V3_PRECAS_ARMED_NOT_ACKED_LEAVE_FENCE'}
 # Exactly these two native task mutations, never Lifecycle or CloudSync.
 foreach($name in $tasks){
  Disable-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction Stop|Out-Null
 }
 foreach($name in $tasks){
  Stop-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction Stop|Out-Null
 }
 # Recheck complete prior PID family, plus any new matching Task process.
 $quiet=$false
 for($i=0;$i -lt 30;$i++){
  Start-Sleep -Seconds 2
  $disabled=@($tasks | Where-Object {
   [string](Get-ScheduledTask -TaskName $_ -TaskPath '\' -ErrorAction Stop).State -ceq 'Disabled'
  })
  $after=@(Get-CimInstance Win32_Process -ErrorAction Stop)
  $oldLive=@($after|Where-Object {[int]$_.ProcessId -in $descendants})
  $newLive=@(foreach($proc in $after){
   if([string]$proc.Name -notmatch '(?i)^pythonw?\.exe$'){continue}
   $line=([string]$proc.CommandLine).Replace('\','/')
   if(@($native | Where-Object {
      ([string]$_.arguments).Length -ge 10 -and
      $line.IndexOf(([string]$_.arguments).Replace('\','/'),
       [StringComparison]::OrdinalIgnoreCase) -ge 0
   }).Count -gt 0){$proc}
  })
  if($disabled.Count -eq 2 -and $oldLive.Count -eq 0 -and $newLive.Count -eq 0){
   $quiet=$true;break
  }
 }
 if(-not $quiet){throw 'V3_PRECAS_NATIVE_QUIESCENCE_UNKNOWN_LEAVE_ARMED_FENCE'}
 # Never automatically promote ARMED to QUIESCED: requires a separate
 # independent source/PID and original two-cycle Supervisor proof and another
 # atomic marker step. Keep the safe ARMED hold; no auto-rearm or CAS.
 return [pscustomobject]@{
  kind='V3_PR515_NATIVE_STOP_SOURCE_ONLY_V1'
  status='ARMED_FENCED_TWO_INTAKES_DISABLED_STOPPED_AWAIT_QUIESCED_INDEPENDENT_ACK'
  original_task_scope=@($tasks)
  protected_aftercare_scope=@($protected)
  current_pr515_readonly_preflight_pass=$true
  two_supervisor_quiesced_cycles_verified=$false
  independent_cloud_cas_never_invoked_verified=$false
  native_full_lineage_externally_authenticated=$false
  cloud_cas_invoked=$false
  automatic_old_intake_rearm_allowed=$false
  paper_release_authorized=$false
 }
}

# The exact future PR515 ARMED -> QUIESCED phase transition, kept next to
# the ONE existing original native stop/restore owner, not a second scheduler.
# Source-only: two locks remain, including external CAS-custody authority
# immediately BEFORE the first intended filesystem mutation.
function Invoke-V3Pr515ArmedToQuiescedSOURCE_ONLY(
 [string]$Root,[object]$OriginalReadback,[string]$BackupFolder,
 [string]$ReviewedPr515Sha,[string]$ExpectedArmedFenceSha) {
 throw 'V3_PR515_ARMED_TO_QUIESCED_SOURCE_UNCONDITIONALLY_LOCKED'
 if([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT){
  throw 'V3_QUIESCED_ORIGINAL_WINDOWS_ONLY'
 }
 $real=[IO.Path]::GetFullPath($Root).TrimEnd('\')
 if(-not $real.Equals('C:\Users\ADMIN\Trading',[StringComparison]::OrdinalIgnoreCase) -or
    $ReviewedPr515Sha -cnotmatch '^[a-f0-9]{64}$' -or
    $ExpectedArmedFenceSha -cnotmatch '^[a-f0-9]{64}$'){
  throw 'V3_QUIESCED_ORIGINAL_SOURCE_OR_FENCE_PIN_INVALID'
 }
 $who=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
 if(-not $who.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){
  throw 'V3_QUIESCED_ADMIN_REQUIRED'
 }
 $fence=Join-Path $real 'State\v3-experimental-paper-old-intake-fence.json'
 $item=Get-Item -LiteralPath $fence -Force -ErrorAction Stop
 if($item.PSIsContainer -or
    [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
    $item.Length -lt 100 -or $item.Length -gt 8192 -or
    (Get-FileHash -LiteralPath $fence -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant() -cne $ExpectedArmedFenceSha){
  throw 'V3_QUIESCED_UNTRUSTED_ARMED_FENCE'
 }
 $acl=Get-Acl -LiteralPath $fence -ErrorAction Stop
 if(-not $acl.AreAccessRulesProtected){throw 'V3_QUIESCED_ARMED_FENCE_ACL_DRIFT'}
 foreach($rule in @($acl.Access)){
  if($rule.AccessControlType -eq [Security.AccessControl.AccessControlType]::Allow){
   $sid=$rule.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value
   if($sid -notin @('S-1-5-18','S-1-5-32-544')){
    throw 'V3_QUIESCED_FENCE_UNTRUSTED_WRITER'
   }
  }
 }
 $marker=Get-Content -LiteralPath $fence -Raw -ErrorAction Stop|ConvertFrom-Json
 if([string]$marker.kind -cne 'V3_EXPERIMENTAL_OLD_INTAKE_FENCE_V1' -or
    [string]$marker.phase -cne 'ARMED' -or
    [string]$marker.predecessor_series_id -cne 'PAPER-V2R4-20261009T110135Z' -or
    -not(Test-V3ScopedIntakeTaskSet -Names @($marker.task_names)) -or
    $marker.paper_only -ne $true -or
    $marker.orders_enabled -ne $false -or
    $marker.real_money_actions -ne $false -or
    $marker.persistent_until_explicit_owner_release -ne $true){
  throw 'V3_QUIESCED_MARKER_SCOPE_NOT_ARMED'
 }
 # Originalhost-only native readbacks; an old source pin or single cycle HOLD.
 $two=Read-V3Pr515ArmedTwoCycleOriginalHost -Report $OriginalReadback -Root $real -BackupDirectory $BackupFolder -ExpectedCloudSha $ReviewedPr515Sha -ExpectedFenceSha $ExpectedArmedFenceSha
 if([string]$two.kind -cne 'V3_PR515_ORIGINALHOST_ARMED_TWO_CYCLE_LOCAL_READONLY_V1' -or
    [string]$two.status -cne 'ARMED_TWO_ORIGINAL_LOCAL_CYCLES_OBSERVED_NOT_QUIESCED' -or
    $two.current_two_native_xml_disabled_only_reread_pass -ne $true -or
    $two.current_pr515_source_recheck_pass -ne $true -or
    [string]$two.unchanged_armed_fence_sha256 -cne $ExpectedArmedFenceSha -or
    $two.cloud_cas_invoked -ne $false -or
    $two.v3_paper_release_authorized -ne $false){
  throw 'V3_QUIESCED_TWO_CYCLE_OR_PR515_ACK_INCOMPLETE'
 }
 # Source-level re-read of the two native intake Tasks. Protected Lifecycle
 # and CloudSync remain running; no stop/enable or process kill occurs here.
 $tasks=@('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait')
 foreach($name in $tasks){
  if([string](Get-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction Stop).State -cne 'Disabled'){
   throw 'V3_QUIESCED_NATIVE_INTAKE_REARMED'
  }
 }
 foreach($name in @('CryptoMiniPC-V2R4PaperLifecycle','CryptoMiniPC-V2R4PaperCloudSync')){
  if([string](Get-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction Stop).State -cne 'Running'){
   throw 'V3_QUIESCED_AFTERCARE_NOT_RUNNING'
  }
 }
 # Independent original PID-family absence, exclusive caller/ACL proof, and
 # complete NEVER/UNKNOWN CAS custody are not provided by the local two-cycle
 # readback. Do not weaken this boundary with caller-supplied Boolean fields.
 # It must later be wired to the existing independently authenticated owners.
 throw 'V3_PR515_QUIESCED_EXTERNAL_PID_AND_CAS_CUSTODY_NOT_WIRED'
 # Future separately authorized marker-only phase promotion, never auto-rearm:
 # secure same-directory File.Replace, preserving the exact protected ACL.
 $marker.phase='QUIESCED'
 $temp=$fence+'.'+[guid]::NewGuid().ToString('N')+'.tmp'
 $backup=$fence+'.'+[guid]::NewGuid().ToString('N')+'.armed.bak'
 if(Test-Path -LiteralPath $temp){throw 'V3_QUIESCED_TEMP_COLLISION'}
 [IO.File]::WriteAllText($temp,($marker|ConvertTo-Json -Depth 6),[Text.UTF8Encoding]::new($false))
 Set-Acl -LiteralPath $temp -AclObject $acl -ErrorAction Stop
 if((Test-Path -LiteralPath $backup) -or
    (Get-FileHash -LiteralPath $fence -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant() -cne $ExpectedArmedFenceSha){
  throw 'V3_QUIESCED_ORIGINAL_FENCE_RACE'
 }
 [IO.File]::Replace($temp,$fence,$backup,$true)
 $after=Get-Content -LiteralPath $fence -Raw -ErrorAction Stop|ConvertFrom-Json
 if([string]$after.phase -cne 'QUIESCED' -or
    [string]$after.predecessor_series_id -cne 'PAPER-V2R4-20261009T110135Z'){
  throw 'V3_QUIESCED_PHASE_READBACK_HOLD_LEAVE_FENCE'
 }
 return [pscustomobject]@{
  kind='V3_PR515_ORIGINALHOST_QUIESCED_MARKER_SOURCE_V1'
  status='QUIESCED_LOCAL_ONLY_PENDING_INDEPENDENT_POSTSTOP_ACK'
  native_intake_tasks_changed_here=$false
  external_cas_never_history_verified_here=$false
  automatic_old_writer_rearm_allowed=$false
  cloud_cas_invocation_authorized=$false
  v3_paper_release_authorized=$false
 }
}

# Current PR515 PRE-COMMIT manual recovery SOURCE ONLY. This is the sole
# future two-Task RESTORE owner; never invoke historic PR332/PR419 drill paths.
# -Execute remains unconditionally locked at the existing outer CLI. This
# function has its OWN first-statement hard lock, so even dot-sourcing cannot
# reach the three native recovery sites without a separately reviewed release.
function Invoke-V3Pr515PrecommitRestoreSOURCE_ONLY(
 [string]$Root,[object]$OriginalReadback,[object]$RecoveryReceipt,
 [string]$BackupDirectory,[string]$ReviewedPr515SourceSha256,
 [string]$ReviewedFenceSha256,[string]$Confirm) {
 throw 'V3_PR515_PRECOMMIT_RESTORE_SOURCE_UNCONDITIONALLY_LOCKED'
 if([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT){
  throw 'V3_PRECOMMIT_RESTORE_ORIGINAL_WINDOWS_REQUIRED'
 }
 $real=[IO.Path]::GetFullPath($Root).TrimEnd('\')
 if(-not $real.Equals('C:\Users\ADMIN\Trading',[StringComparison]::OrdinalIgnoreCase) -or
    $Confirm -cne 'RESTORE-PRECAS-V2R4-ONLY' -or
    $ReviewedPr515SourceSha256 -cnotmatch '^[a-f0-9]{64}$' -or
    $ReviewedFenceSha256 -cnotmatch '^[a-f0-9]{64}$'){
  throw 'V3_PRECOMMIT_RESTORE_HOST_OR_EXTERNAL_PINS_INVALID'
 }
 $wp=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
 if(-not $wp.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){
  throw 'V3_PRECOMMIT_RESTORE_ADMIN_REQUIRED'
 }
 $tasks=@('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait')
 $fence=Join-Path $real 'State\v3-experimental-paper-old-intake-fence.json'
 $maintenance=Join-Path $real 'State\v2r4-technical-cutover-maintenance.json'
 if(Test-Path -LiteralPath $maintenance){throw 'V3_PRECOMMIT_FOREIGN_MAINTENANCE_MARKER'}
 $fenceFile=Get-Item -LiteralPath $fence -Force -ErrorAction Stop
 if($fenceFile.PSIsContainer -or
    [bool]($fenceFile.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
    $fenceFile.Length -lt 100 -or $fenceFile.Length -gt 8192 -or
    (Get-FileHash -LiteralPath $fence -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant() -cne $ReviewedFenceSha256){
  throw 'V3_PRECOMMIT_ORIGINAL_FENCE_SHA_CHANGED'
 }
 $marker=Get-Content -LiteralPath $fence -Raw -ErrorAction Stop|ConvertFrom-Json
 $currentPhase=[string]$marker.phase
 # The native STOP may have left ARMED; both original pre-CAS phases are
 # eligible for strict manual review, never auto-rearm or synthetic approval.
 if([string]$marker.kind -cne 'V3_EXPERIMENTAL_OLD_INTAKE_FENCE_V1' -or
    $currentPhase -notin @('ARMED','QUIESCED') -or
    [string]$marker.predecessor_series_id -cne 'PAPER-V2R4-20261009T110135Z' -or
    -not(Test-V3ScopedIntakeTaskSet -Names @($marker.task_names)) -or
    [string]$marker.proposed_v3_repo_sha -cnotmatch '^[a-f0-9]{40}$' -or
    [string]$marker.proposed_v3_bundle_sha256 -cnotmatch '^[a-f0-9]{64}$' -or
    [string]$marker.proposed_v3_strategy_sha256 -cnotmatch '^[a-f0-9]{64}$' -or
    $marker.paper_only -ne $true -or $marker.orders_enabled -ne $false -or
    $marker.real_money_actions -ne $false -or
    $marker.persistent_until_explicit_owner_release -ne $true -or
    $marker.drill_only -eq $true){
  throw 'V3_PRECOMMIT_FOREIGN_OR_NON_QUIESCED_MARKER'
 }
 # Typed original backup/source readback must be re-executed against the
 # currently Disabled native Tasks, not just a caller-provided PR536 Boolean.
 # The original on-disk fence decides the phase; caller strings cannot.
 if([string]$RecoveryReceipt.phase -cne $currentPhase -or
    [string]$RecoveryReceipt.fence_marker_phase -cne $currentPhase){
  throw 'V3_PRECOMMIT_RECEIPT_ORIGINAL_FENCE_PHASE_MISMATCH'
 }
 $before=$RecoveryReceipt.current_pr515_readonly_preview
 $after=$null
 $valid=$false
 $expectedDisposition=$null
 if($currentPhase -ceq 'ARMED'){
  $after=$RecoveryReceipt.current_pr515_armed_readonly_preview
  $actual=Read-V3Pr515FreshRecoveryPreview -Report $OriginalReadback -Root $real -BackupDirectory $BackupDirectory -ExpectedCloudSha $ReviewedPr515SourceSha256 -ExpectedArmed
  $valid=(Test-V3Pr515ArmedRecoveryIdentity -Before $before -After $actual) -and
         (Test-V3Pr515ArmedRecoveryIdentity -Before $before -After $after)
  $expectedDisposition='PRE_CAS_ARMED_MANUAL_RESTORE_REVIEW_CANDIDATE_NOT_EXECUTABLE'
 }else{
  $after=$RecoveryReceipt.current_pr515_quiesced_readonly_preview
  $actual=Read-V3Pr515FreshRecoveryPreview -Report $OriginalReadback -Root $real -BackupDirectory $BackupDirectory -ExpectedCloudSha $ReviewedPr515SourceSha256 -ExpectedQuiesced
  $valid=(Test-V3Pr515QuiescedRecoveryIdentity -Before $before -After $actual) -and
         (Test-V3Pr515QuiescedRecoveryIdentity -Before $before -After $after)
  $expectedDisposition='PRE_CAS_MANUAL_ROLLBACK_REVIEW_CANDIDATE'
 }
 if(-not $valid -or
    [string]$actual.current_backup_directory_leaf -cne [string]$after.current_backup_directory_leaf -or
    [string]$actual.pr515_source_sha256 -cne [string]$after.pr515_source_sha256){
  throw 'V3_PRECOMMIT_CURRENT_TWO_XML_AND_PR515_RECOVERY_RECHECK_FAILED'
 }
 $review=Resolve-V3ScopedCutoverRecovery -Receipt $RecoveryReceipt
 if([string]$review.disposition -cne $expectedDisposition -or
    $review.automatic_old_writer_rearm_allowed -ne $false -or
    $RecoveryReceipt.cloud_cas_invoked -ne $false -or
    [string]$RecoveryReceipt.cloud_cas_outcome -cne 'NOT_INVOKED' -or
    $RecoveryReceipt.v3_writer_started -ne $false){
  throw 'V3_PRECOMMIT_RESTORE_NOT_MANUAL_REVIEW_ELIGIBLE'
 }
 foreach($name in @('CryptoMiniPC-V2R4PaperLifecycle','CryptoMiniPC-V2R4PaperCloudSync')){
  $t=Get-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction Stop
  if([string]$t.State -cne 'Running'){throw 'V3_PRECOMMIT_PROTECTED_AFTERCARE_NOT_RUNNING'}
 }
 # Intentionally a SECOND non-bypassable SOURCE barrier: the external
 # independent Cloud CAS NEVER/old-only attestation must be implemented via
 # its actual authorized read-only owner BEFORE any marker/Task mutation.
 # The synthetic RecoveryReceipt booleans can NEVER lift this barrier.
 throw 'V3_PRECOMMIT_INDEPENDENT_CLOUD_CAS_AUTHORITY_NOT_WIRED'
 # This remains UNREACHABLE under both current source locks. The future
 # authorized QUIESCED case transitions to ARMED atomically. If already ARMED,
 # preserve the exact protected marker rather than overwriting it.
 if($currentPhase -ceq 'QUIESCED'){
  $marker.phase='ARMED'
  $temp=$fence+'.'+[guid]::NewGuid().ToString('N')+'.tmp'
  $backup=$fence+'.'+[guid]::NewGuid().ToString('N')+'.quiesced.bak'
  [IO.File]::WriteAllText($temp,($marker|ConvertTo-Json -Depth 5),[Text.UTF8Encoding]::new($false))
  Set-Acl -LiteralPath $temp -AclObject (Get-Acl -LiteralPath $fence -ErrorAction Stop) -ErrorAction Stop
  if((Test-Path -LiteralPath $backup) -or
     (Get-FileHash -LiteralPath $fence -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant() -cne $ReviewedFenceSha256){
   throw 'V3_PRECOMMIT_MARKER_CHANGED_BEFORE_ATOMIC_REPLACE'
  }
  [IO.File]::Replace($temp,$fence,$backup,$true)
 }else{
  if((Get-FileHash -LiteralPath $fence -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant() -cne $ReviewedFenceSha256 -or
     [string](Get-Content -LiteralPath $fence -Raw -ErrorAction Stop|ConvertFrom-Json).phase -cne 'ARMED'){
   throw 'V3_PRECOMMIT_ARMED_FENCE_CHANGED_BEFORE_MANUAL_RECOVERY'
  }
 }
 $armedAt=[datetimeoffset]::UtcNow
 foreach($name in $tasks){
  Enable-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction Stop | Out-Null
 }
 foreach($name in $tasks){
  Start-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction Stop | Out-Null
 }
 $healthy=$false
 for($i=0;$i -lt 45;$i++){
  Start-Sleep -Seconds 4
  $running=@($tasks|Where-Object {
   [string](Get-ScheduledTask -TaskName $_ -TaskPath '\' -ErrorAction Stop).State -ceq 'Running'
  })
  if($running.Count -ne 2){continue}
  try{
   $candidate=Get-Content -LiteralPath (Join-Path $real 'State\v2r4-paper-candidate-runtime-heartbeat.json') -Raw -ErrorAction Stop|ConvertFrom-Json
   $wait=Get-Content -LiteralPath (Join-Path $real 'State\v2r4-paper-wait-runtime-heartbeat.json') -Raw -ErrorAction Stop|ConvertFrom-Json
   $fresh=@(@($candidate,$wait) | Where-Object {
    [string]$_.status -ceq 'HEALTHY' -and
    [string]$_.checked_at_utc -match '(Z|\+00:00)$' -and
    ([datetimeoffset]$_.checked_at_utc) -gt $armedAt
   })
   if($fresh.Count -eq 2){$healthy=$true;break}
  }catch{
   # Bounded local wait; never remove the protected ARMED marker on failure.
  }
 }
 if(-not $healthy){throw 'V3_PRECOMMIT_RESTORE_NOT_HEALTHY_PRESERVE_ARMED_FENCE'}
 $confirm=Get-Content -LiteralPath $fence -Raw -ErrorAction Stop|ConvertFrom-Json
 if([string]$confirm.kind -cne 'V3_EXPERIMENTAL_OLD_INTAKE_FENCE_V1' -or
    [string]$confirm.phase -cne 'ARMED' -or
    [string]$confirm.proposed_successor_series_id -cne [string]$marker.proposed_successor_series_id -or
    -not(Test-V3ScopedIntakeTaskSet -Names @($confirm.task_names))){
  throw 'V3_PRECOMMIT_FENCE_CHANGED_DURING_RECOVERY'
 }
 Remove-Item -LiteralPath $fence -Force -ErrorAction Stop
 # Follow-up CloudSync must become HEALTHY ACTIVE_ORIGINAL with exactly one
 # original series; this return is a local receipt, not Cloud CAS authority.
 $after=$false
 for($i=0;$i -lt 45;$i++){
  Start-Sleep -Seconds 4
  try{
   $sup=Get-Content -LiteralPath (Join-Path $real 'State\minipc-runtime-supervisor.json') -Raw -ErrorAction Stop|ConvertFrom-Json
   $cloud=Get-Content -LiteralPath (Join-Path $real 'State\v2r4-paper-cloud-sync-heartbeat.json') -Raw -ErrorAction Stop|ConvertFrom-Json
   if([string]$sup.status -ceq 'HEALTHY' -and
      [string]$sup.v3_paper_old_intake_fence.mode -ceq 'NONE' -and
      [string]$cloud.status -ceq 'HEALTHY' -and
      [string]$cloud.v3_fence_cloud_sync_lane -ceq 'ACTIVE_ORIGINAL' -and
      [string]$cloud.series_id -ceq 'PAPER-V2R4-20261009T110135Z' -and
      [string]$sup.checked_at_utc -match '(Z|\+00:00)$' -and
      [string]$cloud.checked_at_utc -match '(Z|\+00:00)$' -and
      ([datetimeoffset]$sup.checked_at_utc) -gt $armedAt -and
      ([datetimeoffset]$cloud.checked_at_utc) -gt $armedAt){
    $after=$true;break
   }
  }catch{
   # Keep bounded review; a missing local ACK never claims Cloud CAS truth.
  }
 }
 if(-not $after){throw 'V3_PRECOMMIT_RESTORE_AFTERCARE_UNKNOWN_MANUAL_REVIEW_REQUIRED'}
 return [pscustomobject]@{
  kind='V3_PR515_PRECOMMIT_OLD_INTAKE_RESTORE_ORIGINALHOST_V1'
  status='RECOVERY_SOURCE_IMPL_NOT_RELEASED'
  old_intake_task_scope=$tasks
  v3_paper_release_authorized=$false
  independent_cloud_cas_never_invoked_attested_here=$false
  automatic_old_writer_rearm_allowed=$false
  real_money_actions=$false
 }
}

# Native TaskScheduler disable may change exactly one XML field: Enabled.
# Compare all remaining XML nodes including Principal, Task action and triggers.
# Pure parser only; no actual native stop, restore or state change.
function Test-V3Pr515DisabledOnlyXmlDifference([string]$Saved,[string]$Disabled) {
 if([string]::IsNullOrWhiteSpace($Saved) -or
    [string]::IsNullOrWhiteSpace($Disabled) -or
    $Saved.Length -gt 65536 -or $Disabled.Length -gt 65536 -or
    $Saved -match '<!DOCTYPE|<!ENTITY' -or
    $Disabled -match '<!DOCTYPE|<!ENTITY'){return $false}
 try {
  $old=[xml]::new();$new=[xml]::new()
  $old.XmlResolver=$null;$new.XmlResolver=$null
  $old.LoadXml($Saved);$new.LoadXml($Disabled)
  $ns='http://schemas.microsoft.com/windows/2004/02/mit/task'
  if([string]$old.DocumentElement.LocalName -cne 'Task' -or
     [string]$new.DocumentElement.LocalName -cne 'Task' -or
     [string]$old.DocumentElement.NamespaceURI -cne $ns -or
     [string]$new.DocumentElement.NamespaceURI -cne $ns){return $false}
  $path='/*[local-name()="Task"]/*[local-name()="Settings"]'
  $os=@($old.SelectNodes($path));$ds=@($new.SelectNodes($path))
  if($os.Count -ne 1 -or $ds.Count -ne 1 -or
     [string]$os[0].NamespaceURI -cne $ns -or
     [string]$ds[0].NamespaceURI -cne $ns){return $false}
  $a=@($os[0].SelectNodes('./*[local-name()="Enabled"]'))
  $b=@($ds[0].SelectNodes('./*[local-name()="Enabled"]'))
  # A missing original Enabled is valid and defaults to true (actual PR618
  # physical PASS). Poststop must contain explicit false and NOTHING else.
  if($a.Count -gt 1 -or $b.Count -ne 1 -or
     [string]$b[0].NamespaceURI -cne $ns -or
     ([string]$b[0].InnerText).Trim() -notin @('false','0') -or
     ($a.Count -eq 1 -and
      ([string]$a[0].NamespaceURI -cne $ns -or
       ([string]$a[0].InnerText).Trim() -notin @('true','1')))){return $false}
  if($a.Count -eq 1){[void]$os[0].RemoveChild($a[0])}
  [void]$ds[0].RemoveChild($b[0])
  return ($old.OuterXml -ceq $new.OuterXml)
 }catch{return $false}
}

# A true QUIESCED phase must be verified on the same ORIGINAL Windows host.
# These are read-only LOCAL Supervisor/PR515 observations, not independently
# authenticated PID, six-release-proof, or external Cloud-CAS evidence.
function Test-V3Pr515QuiescedLocalHold([string]$Root,[ValidateSet('ARMED','QUIESCED')][string]$ExpectedPhase='QUIESCED') {
 $state=Join-Path $Root 'State'
 if(Test-Path -LiteralPath (Join-Path $state 'v2r4-technical-cutover-maintenance.json')){
  throw 'Foreign maintenance marker present'
 }
 $file=Join-Path $state 'v3-experimental-paper-old-intake-fence.json'
 $item=Get-Item -LiteralPath $file -Force -ErrorAction Stop
 if($item.PSIsContainer -or
    [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
    $item.Length -lt 100 -or $item.Length -gt 8192){throw 'Unsafe fence'}
 $marker=Get-Content -LiteralPath $file -Raw -ErrorAction Stop | ConvertFrom-Json
 if([string]$marker.kind -cne 'V3_EXPERIMENTAL_OLD_INTAKE_FENCE_V1' -or
    [string]$marker.phase -cne $ExpectedPhase -or
    [string]$marker.predecessor_series_id -cne 'PAPER-V2R4-20261009T110135Z' -or
    -not(Test-V3ScopedIntakeTaskSet -Names @($marker.task_names)) -or
    [string]$marker.proposed_v3_repo_sha -cnotmatch '^[a-f0-9]{40}$' -or
    [string]$marker.proposed_v3_bundle_sha256 -cnotmatch '^[a-f0-9]{64}$' -or
    [string]$marker.proposed_v3_strategy_sha256 -cnotmatch '^[a-f0-9]{64}$' -or
    $marker.paper_only -ne $true -or $marker.orders_enabled -ne $false -or
    $marker.real_money_actions -ne $false -or
    $marker.persistent_until_explicit_owner_release -ne $true -or
    $marker.drill_only -eq $true){throw 'Invalid or historical drill-only QUIESCED marker'}
 $reports=@()
 foreach($leaf in @('minipc-runtime-supervisor.json','v2r4-paper-cloud-sync-heartbeat.json')){
  $p=Join-Path $state $leaf
  $f=Get-Item -LiteralPath $p -Force -ErrorAction Stop
  if($f.PSIsContainer -or
     [bool]($f.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
     $f.Length -lt 50 -or $f.Length -gt 131072){throw 'Unsafe report'}
  $r=Get-Content -LiteralPath $p -Raw -ErrorAction Stop | ConvertFrom-Json
  $stamp=[datetimeoffset]::MinValue
  if([string]$r.checked_at_utc -cnotmatch '(Z|\+00:00)$' -or
     -not([datetimeoffset]::TryParse([string]$r.checked_at_utc,[ref]$stamp))){
   throw 'Invalid readback UTC time'
  }
  $age=([datetimeoffset]::UtcNow-$stamp).TotalSeconds
  if($age -lt -10 -or $age -gt 180){throw 'Stale or future originalhost readback'}
  $reports+=@($r)
 }
 $sup=$reports[0];$cloud=$reports[1]
 $matched=@($sup.tasks | Where-Object {
  $_.task -in @('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait') -and
  $_.action -ceq 'V3_INTAKE_SUPERVISOR_REARM_BLOCKED' -and
  [string]$_.before.scheduler_state -ceq 'Disabled'
 })
 if(-not(Test-V3ScopedIntakeTaskSet -Names @($matched | ForEach-Object {[string]$_.task}))){
  throw 'Supervisor no-rearm Task identities missing or duplicated'
 }
 if([string]$sup.status -cne 'WARNING' -or
    [string]$sup.v3_paper_old_intake_fence.mode -cne $ExpectedPhase -or
    $matched.Count -ne 2 -or
    @($sup.restarted).Count -ne 0 -or
    @($sup.failed_restarts).Count -ne 0 -or
    [string]$cloud.status -cne 'HEALTHY' -or
    [string]$cloud.mode -cne 'V3_PRECOMMIT_NO_NETWORK_HOLD' -or
    [string]$cloud.v3_fence_precommit_phase -cne $ExpectedPhase -or
    [string]$cloud.v3_fence_cloud_sync_lane -cne 'PRECOMMIT_ORIGINAL' -or
    $cloud.cloud_sync_intentionally_paused -ne $true -or
    $cloud.cloud_updated -ne $false){
  throw 'Native Supervisor or PR515 precommit no-network hold mismatch'
 }
 return $true
}

# Read two *actual* originalhost ARMED Supervisor/PR515 cycles, rather than
# accepting an untrusted caller JSON as proof. This is a strict READONLY preview:
# no native Task mutations, no fence phase write, no Cloud CAS or rearm.
# It is only meaningful AFTER a separately approved future native stop.
function Read-V3Pr515ArmedTwoCycleOriginalHost(
 [object]$Report,[string]$Root,[string]$BackupDirectory,
 [string]$ExpectedCloudSha,[string]$ExpectedFenceSha) {
 if([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT){
  throw 'V3_ARMED_TWO_CYCLE_ORIGINAL_WINDOWS_REQUIRED'
 }
 $real=[IO.Path]::GetFullPath($Root).TrimEnd('\')
 if(-not $real.Equals('C:\Users\ADMIN\Trading',[StringComparison]::OrdinalIgnoreCase) -or
    $ExpectedCloudSha -cnotmatch '^[a-f0-9]{64}$' -or
    $ExpectedFenceSha -cnotmatch '^[a-f0-9]{64}$'){
  throw 'V3_ARMED_TWO_CYCLE_ORIGINALHOST_OR_PINS_INVALID'
 }
 $state=Join-Path $real 'State'
 $fence=Join-Path $state 'v3-experimental-paper-old-intake-fence.json'
 $entry=Get-Item -LiteralPath $fence -Force -ErrorAction Stop
 if($entry.PSIsContainer -or
    [bool]($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
    $entry.Length -lt 100 -or $entry.Length -gt 8192){
  throw 'V3_ARMED_TWO_CYCLE_FENCE_UNSAFE'
 }
 $names=@('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait')
 $captures=@()
 $started=[datetimeoffset]::UtcNow
 # Only original files are read; bounded polling is not a service start.
 for($attempt=0;$attempt -lt 48 -and $captures.Count -lt 2;$attempt++){
  if($attempt -gt 0){Start-Sleep -Seconds 5}
  $sha=(Get-FileHash -LiteralPath $fence -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
  if($sha -cne $ExpectedFenceSha){throw 'V3_ARMED_TWO_CYCLE_FENCE_CHANGED'}
  $marker=Get-Content -LiteralPath $fence -Raw -ErrorAction Stop|ConvertFrom-Json
  if([string]$marker.phase -cne 'ARMED' -or
     [string]$marker.kind -cne 'V3_EXPERIMENTAL_OLD_INTAKE_FENCE_V1' -or
     [string]$marker.predecessor_series_id -cne 'PAPER-V2R4-20261009T110135Z' -or
     -not(Test-V3ScopedIntakeTaskSet -Names @($marker.task_names)) -or
     $marker.paper_only -ne $true -or $marker.orders_enabled -ne $false -or
     $marker.real_money_actions -ne $false -or $marker.drill_only -eq $true){
   throw 'V3_ARMED_TWO_CYCLE_FOREIGN_FENCE'
  }
  foreach($name in $names){
   if([string](Get-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction Stop).State -cne 'Disabled'){
    throw 'V3_ARMED_TWO_CYCLE_OLD_INTAKE_REARMED'
   }
  }
  foreach($name in @('CryptoMiniPC-V2R4PaperLifecycle','CryptoMiniPC-V2R4PaperCloudSync')){
   if([string](Get-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction Stop).State -cne 'Running'){
    throw 'V3_ARMED_TWO_CYCLE_AFTERCARE_NOT_RUNNING'
   }
  }
  $null=Test-V3Pr515QuiescedLocalHold -Root $real -ExpectedPhase 'ARMED'
  $source=Read-V3Pr515FreshRecoveryPreview -Report $Report -Root $real -BackupDirectory $BackupDirectory -ExpectedCloudSha $ExpectedCloudSha -ExpectedArmed
  if([string]$source.status -cne 'ARMED_DISABLED_NATIVE_SOURCE_MATCH_NOT_RELEASED' -or
     $source.poststop_disabled_only_native_xml_recheck_pass -ne $true -or
     $source.pr515_effective_cloudsync_source_consistent -ne $true){
   throw 'V3_ARMED_TWO_CYCLE_BACKUP_OR_PR515_MISMATCH'
  }
  $super=Get-Content -LiteralPath (Join-Path $state 'minipc-runtime-supervisor.json') -Raw -ErrorAction Stop|ConvertFrom-Json
  $cloud=Get-Content -LiteralPath (Join-Path $state 'v2r4-paper-cloud-sync-heartbeat.json') -Raw -ErrorAction Stop|ConvertFrom-Json
  $sAt=[datetimeoffset]::MinValue
  $cAt=[datetimeoffset]::MinValue
  if([string]$super.checked_at_utc -cnotmatch '(Z|\+00:00)$' -or
     [string]$cloud.checked_at_utc -cnotmatch '(Z|\+00:00)$' -or
     -not [datetimeoffset]::TryParse([string]$super.checked_at_utc,[ref]$sAt) -or
     -not [datetimeoffset]::TryParse([string]$cloud.checked_at_utc,[ref]$cAt)){
   throw 'V3_ARMED_TWO_CYCLE_TIMESTAMP_INVALID'
  }
  $now=[datetimeoffset]::UtcNow
  if($sAt -gt $now.AddSeconds(5) -or $cAt -gt $now.AddSeconds(5)){
   throw 'V3_ARMED_TWO_CYCLE_FUTURE_READBACK'
  }
  if($sAt -lt $started.AddSeconds(-5) -or $cAt -lt $started.AddSeconds(-5)){
   continue # Reject historical/pre-observer snapshots.
  }
  if($captures.Count -eq 1 -and
     (($sAt-$captures[0].sAt).TotalSeconds -lt 5 -or
      ($cAt-$captures[0].cAt).TotalSeconds -lt 5)){
   continue # Both files must have distinctly advanced.
  }
  $captures+=@([pscustomobject]@{supervisor=$super;cloudsync=$cloud;sAt=$sAt;cAt=$cAt})
 }
 if($captures.Count -ne 2){throw 'V3_ARMED_TWO_CYCLE_TIMEOUT_HOLD'}
 $input=[pscustomobject]@{
  kind='V3_PR515_ARMED_TWO_CYCLE_ORIGINALHOST_INPUT_V1'
  phase='ARMED'
  predecessor_series_id='PAPER-V2R4-20261009T110135Z'
  task_names=$names
  captures=@($captures|ForEach-Object{
   [pscustomobject]@{supervisor=$_.supervisor;cloudsync=$_.cloudsync}
  })
 }
 if(-not(Test-V3Pr515ArmedTwoCycleSnapshots -Evidence $input)){
  throw 'V3_ARMED_TWO_CYCLE_SEMANTICS_FAIL'
 }
 if((Get-FileHash -LiteralPath $fence -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant() -cne $ExpectedFenceSha){
  throw 'V3_ARMED_TWO_CYCLE_FINAL_FENCE_CHANGED'
 }
 $after=Read-V3Pr515FreshRecoveryPreview -Report $Report -Root $real -BackupDirectory $BackupDirectory -ExpectedCloudSha $ExpectedCloudSha -ExpectedArmed
 if([string]$after.status -cne 'ARMED_DISABLED_NATIVE_SOURCE_MATCH_NOT_RELEASED'){
  throw 'V3_ARMED_TWO_CYCLE_FINAL_PR515_SOURCE_CHANGED'
 }
 return [pscustomobject]@{
  kind='V3_PR515_ORIGINALHOST_ARMED_TWO_CYCLE_LOCAL_READONLY_V1'
  status='ARMED_TWO_ORIGINAL_LOCAL_CYCLES_OBSERVED_NOT_QUIESCED'
  supervisor_cycle_count=2
  cloudsync_cycle_count=2
  current_two_native_xml_disabled_only_reread_pass=$true
  current_pr515_source_recheck_pass=$true
  unchanged_armed_fence_sha256=$ExpectedFenceSha
  protected_aftercare_running=$true
  independent_original_pid_family_absence_proven_here=$false
  independent_cloud_cas_never_invoked_verified=$false
  independent_cloud_old_only_verified=$false
  fence_phase_promoted=$false
  task_mutations_performed=$false
  cloud_cas_invoked=$false
  automatic_old_intake_rearm_allowed=$false
  v3_paper_release_authorized=$false
  technical_release_proofs_credited=0
 }
}

# This branch ONLY observes the current PR515 plus the new original Task XML.
# Historical PR332 drill stop/restore functions are NOT called or repurposed.
function Read-V3Pr515FreshRecoveryPreview([object]$Report,[string]$Root,
 [string]$BackupDirectory,[string]$ExpectedCloudSha,[switch]$ExpectedQuiesced,[switch]$ExpectedArmed) {
 if([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT){
  throw 'Original Windows host required'
 }
 $rootPath=[IO.Path]::GetFullPath($Root).TrimEnd('\')
 if(-not $rootPath.Equals('C:\Users\ADMIN\Trading',[StringComparison]::OrdinalIgnoreCase) -or
    $ExpectedCloudSha -cnotmatch '^[a-f0-9]{64}$'){
  throw 'Invalid originalhost or externally reviewed PR515 source pin'
 }
 $state=Join-Path $rootPath 'State'
 $stateInfo=Get-Item -LiteralPath $state -Force -ErrorAction Stop
 if(-not $stateInfo.PSIsContainer -or
    [bool]($stateInfo.Attributes -band [IO.FileAttributes]::ReparsePoint)){
  throw 'Original State directory invalid'
 }
 $folder=[IO.Path]::GetFullPath($BackupDirectory).TrimEnd('\')
 $name=[IO.Path]::GetFileName($folder)
 if($name -cnotmatch '^V3Paper-PreCAS-Backup-[a-f0-9]{32}$' -or
    -not $folder.Equals((Join-Path $state $name),[StringComparison]::OrdinalIgnoreCase)){
  throw 'Fresh native XML backup path is not a direct State child'
 }
 $dir=Get-Item -LiteralPath $folder -Force -ErrorAction Stop
 if(-not $dir.PSIsContainer -or
    [bool]($dir.Attributes -band [IO.FileAttributes]::ReparsePoint)){
  throw 'Fresh backup missing or linked'
 }
 $acl=Get-Acl -LiteralPath $folder -ErrorAction Stop
 if(-not $acl.AreAccessRulesProtected){throw 'Backup ACL inheritance drift'}
 foreach($rule in @($acl.Access)){
  if($rule.AccessControlType -eq [Security.AccessControl.AccessControlType]::Allow){
   $sid=$rule.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value
   if($sid -notin @('S-1-5-18','S-1-5-32-544')){throw 'Untrusted backup ACL'}
  }
 }
 $mp=Join-Path $folder 'backup-manifest.json'
 $mi=Get-Item -LiteralPath $mp -Force -ErrorAction Stop
 if($mi.PSIsContainer -or
    [bool]($mi.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
    $mi.Length -lt 100 -or $mi.Length -gt 65536){throw 'Unsafe backup manifest'}
 $manifest=Get-Content -LiteralPath $mp -Raw -Encoding UTF8 -ErrorAction Stop | ConvertFrom-Json
 if([string]$manifest.kind -cne 'V3_PRECAS_NATIVE_XML_BACKUP_ORIGINALHOST_V1' -or
    [string]$manifest.status -cne 'ORIGINAL_TASK_XML_BACKUP_ONLY_NOT_RELEASED' -or
    [string]$manifest.predecessor_series_id -cne 'PAPER-V2R4-20261009T110135Z' -or
    [string]$manifest.backup_directory -cne $folder -or
    [int]$manifest.native_task_count -ne 2 -or
    @($manifest.task_records).Count -ne 2 -or
    $manifest.scheduler_task_mutations -ne $false -or
    $manifest.original_v2r4_changed -ne $false -or
    $manifest.cloud_cas_invoked -ne $false -or
    $manifest.new_v3_writer_started -ne $false){
  throw 'Fresh original native recovery manifest invalid'
 }
 $roles=@(
  [pscustomobject]@{name='CryptoMiniPC-V2R4PaperCandidates';file='Candidates.task.xml'},
  [pscustomobject]@{name='CryptoMiniPC-V2R4PaperWait';file='WAIT.task.xml'}
 )
 if($ExpectedArmed -and $ExpectedQuiesced){throw 'Read-only phase modes are mutually exclusive'}
 $poststop=($ExpectedArmed.IsPresent -or $ExpectedQuiesced.IsPresent)
 if($poststop){
  $stage=if($ExpectedArmed){'ARMED'}else{'QUIESCED'}
  $null=Test-V3Pr515QuiescedLocalHold -Root $rootPath -ExpectedPhase $stage
 }
 $requiredState=if($poststop){'Disabled'}else{'Running'}
 foreach($role in $roles){
  $rec=@($manifest.task_records | Where-Object {$_.task_name -ceq $role.name})
  $row=@($Report.physical_v2r4_paper_task_readback |
    Where-Object {$_.task_name -ceq $role.name})
  if($rec.Count -ne 1 -or $row.Count -ne 1 -or
     [string]$rec[0].xml_file -cne $role.file -or
     [string]$rec[0].xml_sha256 -cnotmatch '^[a-f0-9]{64}$' -or
     [string]$rec[0].action_sha256 -cnotmatch '^[a-f0-9]{64}$'){
   throw 'Fresh manifest Task role/record mismatch'
  }
  $task=Get-ScheduledTask -TaskName $role.name -TaskPath '\' -ErrorAction Stop
  if([string]$task.State -cne $requiredState -or
     @($task.Actions).Count -ne 1 -or
     [string]$task.Principal.UserId -notin @('SYSTEM','NT AUTHORITY\SYSTEM','S-1-5-18') -or
     (Get-V3OriginalNativeActionSha $task.Actions[0]) -cne [string]$rec[0].action_sha256 -or
     [string]$row[0].action_sha256 -cne [string]$rec[0].action_sha256){
   throw 'Original intake Task source changed since secured XML snapshot'
  }
  $live=[string](Export-ScheduledTask -TaskName $role.name -TaskPath '\' -ErrorAction Stop)
  $source=Join-Path $folder $role.file
  if($poststop){
   $sourceInfo=Get-Item -LiteralPath $source -Force -ErrorAction Stop
   if($sourceInfo.PSIsContainer -or
      [bool]($sourceInfo.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
      $sourceInfo.Length -lt 100 -or $sourceInfo.Length -gt 131072){
    throw 'Protected original XML is linked or unsafe'
   }
   $digest=(Get-FileHash -LiteralPath $source -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
   $saved=Get-Content -LiteralPath $source -Raw -Encoding UTF8 -ErrorAction Stop
   if($digest -cne [string]$rec[0].xml_sha256 -or
      -not(Test-V3Pr515DisabledOnlyXmlDifference -Saved $saved -Disabled $live)){
    throw 'Native disabled Task changed beyond Enabled configuration'
   }
  }elseif(-not(Test-V3FreshBackupFileBytes -Path $source -ExpectedSha ([string]$rec[0].xml_sha256) -ExpectedXml $live)){
   throw 'Durable XML does not equal current original Task'
  }
 }
 $cloudRow=@($Report.physical_v2r4_paper_task_readback |
   Where-Object {$_.task_name -ceq 'CryptoMiniPC-V2R4PaperCloudSync'})
 if($cloudRow.Count -ne 1){throw 'Original CloudSync role missing'}
 $cloudTask=Get-ScheduledTask -TaskName 'CryptoMiniPC-V2R4PaperCloudSync' -TaskPath '\' -ErrorAction Stop
 $cloudFile=Join-Path $rootPath 'Staging\PR515-CloudSync-INACTIVE-20261022\v2r4-paper-cloud-sync.py'
 $cf=Get-Item -LiteralPath $cloudFile -Force -ErrorAction Stop
 if($cf.PSIsContainer -or
    [bool]($cf.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
    [string]$cloudTask.State -cne 'Running' -or
    @($cloudTask.Actions).Count -ne 1 -or
    [string]$cloudTask.Principal.UserId -notin @('SYSTEM','NT AUTHORITY\SYSTEM','S-1-5-18') -or
    @([regex]::Matches([string]$cloudTask.Actions[0].Arguments,[regex]::Escape($cloudFile))).Count -ne 1 -or
    (Get-V3OriginalNativeActionSha $cloudTask.Actions[0]) -cne ([string]$cloudRow[0].action_sha256).ToLowerInvariant() -or
    (Get-FileHash -LiteralPath $cloudFile -Algorithm SHA256).Hash.ToLowerInvariant() -cne $ExpectedCloudSha){
  throw 'Effective PR515 CloudSync native Task/source pin mismatch'
 }
 return [ordered]@{
  kind=$(if($ExpectedArmed){'V3_PRECAS_PR515_ARMED_POSTSTOP_READONLY_COMPATIBILITY_V1'}elseif($ExpectedQuiesced){'V3_PRECAS_PR515_QUIESCED_READONLY_COMPATIBILITY_V1'}else{'V3_PRECAS_PR515_FRESH_BACKUP_READONLY_COMPATIBILITY_V1'})
  status=$(if($ExpectedArmed){'ARMED_DISABLED_NATIVE_SOURCE_MATCH_NOT_RELEASED'}elseif($ExpectedQuiesced){'QUIESCED_NATIVE_SOURCE_MATCH_NOT_RELEASED'}else{'COMPATIBLE_READONLY_NOT_RELEASED'})
  single_local_supervisor_pr515_armed_observation_only=$ExpectedArmed.IsPresent
  after_disable_enabled_only_native_xml_comparison=$poststop
  single_local_supervisor_pr515_quiesced_observation_only=$ExpectedQuiesced.IsPresent
  two_distinct_supervisor_cycles_verified=$false
  old_intake_pid_family_absence_independently_verified=$false
  independent_cloud_cas_never_invoked_verified=$false
  # Snapshot hashes are not fresh post-stop authority; re-read after QUIESCED.
  current_backup_directory_leaf=$name
  pr515_source_sha256=$ExpectedCloudSha
  current_native_task_xml_sha256=@($manifest.task_records |
   Sort-Object task_name | ForEach-Object {[string]$_.xml_sha256})
  current_backup_valid_while_intakes_running_only=(!$poststop)
  preview_is_not_poststop_or_independent_cloud_ack=(!$poststop)
  local_poststop_snapshot_is_not_independent_cloud_ack=$true
  two_current_native_xml_reread_pass=(!$poststop)
  poststop_disabled_only_native_xml_recheck_pass=$poststop
  pr515_effective_cloudsync_source_consistent=$true
  external_sha_pin_independently_authenticated=$false
  physical_task_restore_tested=$false
  single_writer_pid_and_lock_proven=$false
  old_intake_norearm_proven=$false
  cloud_cas_invoked=$false
  scheduler_task_mutations=$false
  v3_paper_activated=$false
  technical_release_proofs_credited=0
 }
}

if($Execute){
 throw 'V3_CUTOVER_EXECUTION_LOCKED: no stop/disable, marker, CAS, or rollback is implemented or authorized in this inactive source.'
}
# Reuse the TWO existing already-authenticated SOURCE OWNERS: Notebook's
# password-protected PG17 private Reader and independently fetched public
# production series/CAS inventory. This simply consumes their output files;
# it NEVER authenticates their ORIGINS, stops Tasks or authorizes CAS.
# PR613 optional second Notebook certificate is NOT a dependency.
function Read-V3ScopedPrecommitSnapshotFile([string]$Path,[string[]]$ExactKeys){
 if(-not [IO.Path]::IsPathRooted($Path) -or
    $Path.StartsWith('\\\\') -or $Path.StartsWith('//')){
  throw 'V3_PR515_TWO_SOURCE_LOCAL_FILE_ONLY'
 }
 $item=Get-Item -LiteralPath $Path -Force -ErrorAction Stop
 if($item.PSIsContainer -or
    [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
    $item.Length -lt 100 -or $item.Length -gt 8192){
  throw 'V3_PR515_TWO_SOURCE_UNSAFE_FILE'
 }
 $bytes=[IO.File]::ReadAllBytes($item.FullName)
 $raw=[Text.UTF8Encoding]::new($false,$true).GetString([byte[]]$bytes)
 if($raw.StartsWith([char]0xFEFF)){
  throw 'V3_PR515_TWO_SOURCE_UNEXPECTED_BOM'
 }
 $json=$raw|ConvertFrom-Json -ErrorAction Stop
 if($null -eq $json -or $json -isnot [pscustomobject]){
  throw 'V3_PR515_TWO_SOURCE_NOT_JSON_OBJECT'
 }
 $actual=@($json.PSObject.Properties.Name)
 if($actual.Count -ne $ExactKeys.Count -or
    @($actual | Where-Object {$_ -cnotin $ExactKeys}).Count -ne 0){
  throw 'V3_PR515_TWO_SOURCE_FIELD_SET_DRIFT'
 }
 foreach($field in $ExactKeys){
  if(@([regex]::Matches($raw,('"' + [regex]::Escape($field) + '"\s*:'))).Count -ne 1){
   throw 'V3_PR515_TWO_SOURCE_DUPLICATE_OR_MISSING_FIELD'
  }
 }
 # WinPS 5.1 and newer PowerShell versions do not treat JSON ISO timestamps
 # identically. Preserve the exact checked wire literal and reject escape
 # forms (including backslash-u) instead of trusting ConvertFrom-Json dates.
 $ts=@([regex]::Matches($raw,'"observed_at_utc"\s*:\s*"(?<v>[^"\\]*)"'))
 if($ts.Count -ne 1 -or
    [string]$ts[0].Groups['v'].Value -cnotmatch
     '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}(Z|\+00:00)$'){
  throw 'V3_PR515_TWO_SOURCE_NONCANONICAL_UTC_LITERAL'
 }
 $json.observed_at_utc=[string]$ts[0].Groups['v'].Value
 return $json
}
# ACTUAL ORIGINALHOST cryptographic review of externally signed CURRENT
# private PG17 CAS-unavailability evidence. This opt-in has NO Task mutation.
# The CMS signer uses the existing independently pre-reviewed Notebook cert.
if($ReviewSignedCurrentCasCustody){
 if($Execute -or $BackupOriginalIntake -or $PreviewPr515PreCas -or
    $PreviewPr515Quiesced -or $PreviewPr515Armed -or
    $PreviewPr515ArmedTwoCycle -or $ValidatePr515RestoreXml -or
    $VerifyNotebookPrecommitCms -or $ReviewExistingTwoSourcePrecommit -or
    $Confirm -or $OriginalBackupDirectory -or $ExpectedPr515SourceSha256 -or
    $ExpectedArmedFenceSha256 -or $ExistingNotebookReaderJson -or
    $ExistingCloudInventoryJson -or $ExpectedCandidatesActionSha256 -or
    $ExpectedWaitActionSha256 -or
    $NotebookReaderJson -eq '' -or $NotebookReaderCms -eq '' -or
    $ReviewedNotebookCertificateSha256 -cnotmatch '^[a-f0-9]{64}$' -or
    $ExpectedCurrentFenceSha256 -cnotmatch '^[a-f0-9]{64}$'){
  throw 'V3_SIGNED_CURRENT_CUSTODY_REVIEW_MODE_CONFLICT'
 }
 if([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT -or
    -not([IO.Path]::GetFullPath($TradingRoot).TrimEnd('\')).Equals(
     'C:\Users\ADMIN\Trading',[StringComparison]::OrdinalIgnoreCase)){
  throw 'V3_SIGNED_CUSTODY_ORIGINAL_WINDOWS_HOST_ONLY'
 }
 $admin=[Security.Principal.WindowsPrincipal]::new(
  [Security.Principal.WindowsIdentity]::GetCurrent())
 if(-not $admin.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){
  throw 'V3_SIGNED_CUSTODY_ORIGINAL_ADMIN_REQUIRED'
 }
 $fence=Join-Path $TradingRoot 'State\v3-experimental-paper-old-intake-fence.json'
 $foreign=Join-Path $TradingRoot 'State\v2r4-technical-cutover-maintenance.json'
 if(Test-Path -LiteralPath $foreign){throw 'V3_SIGNED_CUSTODY_MAINTENANCE_CONFLICT'}
 $item=Get-Item -LiteralPath $fence -Force -ErrorAction Stop
 if($item.PSIsContainer -or
    [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
    $item.Length -lt 100 -or $item.Length -gt 8192 -or
    (Get-FileHash -LiteralPath $fence -Algorithm SHA256).Hash.ToLowerInvariant() -cne
       $ExpectedCurrentFenceSha256){
  throw 'V3_SIGNED_CUSTODY_FENCE_INTEGRITY_DRIFT'
 }
 $acl=Get-Acl -LiteralPath $fence -ErrorAction Stop
 if(-not $acl.AreAccessRulesProtected){throw 'V3_SIGNED_CUSTODY_UNPROTECTED_FENCE'}
 foreach($rule in @($acl.Access)){
  if($rule.AccessControlType -eq [Security.AccessControl.AccessControlType]::Allow){
   $sid=$rule.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value
   if($sid -notin @('S-1-5-18','S-1-5-32-544')){
    throw 'V3_SIGNED_CUSTODY_FOREIGN_FENCE_WRITER'
   }
  }
 }
 $phase=Get-Content -LiteralPath $fence -Raw -Encoding UTF8 -ErrorAction Stop|ConvertFrom-Json
 if([string]$phase.kind -cne 'V3_EXPERIMENTAL_OLD_INTAKE_FENCE_V1' -or
    [string]$phase.phase -notin @('ARMED','QUIESCED') -or
    [string]$phase.predecessor_series_id -cne 'PAPER-V2R4-20261009T110135Z' -or
    -not(Test-V3ScopedIntakeTaskSet -Names @($phase.task_names))){
  throw 'V3_SIGNED_CUSTODY_PHASE_SCOPE_INVALID'
 }
 $signed=@($NotebookReaderJson,$NotebookReaderCms)|ForEach-Object {
  $fp=[IO.Path]::GetFullPath($_)
  if(-not [IO.Path]::IsPathRooted($_) -or $_.StartsWith('\\') -or
     $_.StartsWith('//') -or -not(Test-Path -LiteralPath $fp -PathType Leaf)){
   throw 'V3_SIGNED_CUSTODY_LOCAL_PAIR_REQUIRED'
  }
  $file=Get-Item -LiteralPath $fp -Force -ErrorAction Stop
  if([bool]($file.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
     $file.Length -lt 100 -or $file.Length -gt 32768){throw 'V3_SIGNED_CUSTODY_UNSAFE_PAIR'}
  $file
 }
 if($signed.Count -ne 2 -or
    [string]$signed[0].Name -cne 'reader.json' -or
    [string]$signed[1].Name -cne 'reader.cms' -or
    [string]$signed[0].DirectoryName -cne [string]$signed[1].DirectoryName){
  throw 'V3_SIGNED_CUSTODY_PAIR_MISMATCH'
 }
 $proof=Test-V3Pr515SignedCurrentNoCasCustody -Payload (
  [IO.File]::ReadAllBytes($signed[0].FullName)) -Cms (
  [IO.File]::ReadAllBytes($signed[1].FullName)) -ReviewedCertSha256 (
  $ReviewedNotebookCertificateSha256) -CurrentOriginalFenceSha256 (
  $ExpectedCurrentFenceSha256)
 $proof|ConvertTo-Json -Compress -Depth 4
 if($proof.status -cne 'SIGNED_CURRENT_NO_CAS_CAPABILITY_MATCH_NOT_RELEASE'){exit 1}
 return
}
if(-not $ReviewSignedCurrentCasCustody -and $ExpectedCurrentFenceSha256){
 throw 'V3_SIGNED_CUSTODY_FENCE_OUTSIDE_READONLY_MODE'
}
if($ReviewExistingTwoSourcePrecommit){
 if($Execute -or $BackupOriginalIntake -or $PreviewPr515PreCas -or
    $PreviewPr515Quiesced -or $PreviewPr515Armed -or
    $PreviewPr515ArmedTwoCycle -or $ValidatePr515RestoreXml -or
    $VerifyNotebookPrecommitCms -or
    $Confirm -or $OriginalBackupDirectory -or
    $ExpectedPr515SourceSha256 -or $ExpectedArmedFenceSha256 -or
    $ExpectedCandidatesActionSha256 -or $ExpectedWaitActionSha256 -or
    $NotebookReaderJson -or $NotebookReaderCms -or
    $ReviewedNotebookCertificateSha256 -or
    [string]::IsNullOrWhiteSpace($ExistingNotebookReaderJson) -or
    [string]::IsNullOrWhiteSpace($ExistingCloudInventoryJson)){
  throw 'V3_PR515_TWO_SOURCE_REVIEW_ONLY_MODE_CONFLICT'
 }
 $readerKeys=@('kind','status','observed_at_utc','epoch_count',
  'intent_count','actor','role','independent_tls_certificate_verified',
  'independent_attempt_history_complete','historical_cas_never_proven',
  'public_old_only_series_verified_here','native_rearm_authorized',
  'precommit_restore_authorized','cloud_cas_authorized',
  'v3_paper_release_authorized')
 $cloudKeys=@('kind','observed_at_utc',
  'historically_cas_never_invoked_proven','precommit_restore_authorized',
  'active_series_count','exact_original_active_count',
  'recorded_v3_series_count','recorded_v3_rotation_count',
  'recorded_v3_release_decision_count','installed_v3_cas_function_count',
  'valid_single_active_index_count')
 $reader=Read-V3ScopedPrecommitSnapshotFile -Path $ExistingNotebookReaderJson -ExactKeys $readerKeys
 $cloud=Read-V3ScopedPrecommitSnapshotFile -Path $ExistingCloudInventoryJson -ExactKeys $cloudKeys
 $status=Get-V3Pr515TwoSourceCloudSnapshotReview -Reader $reader -Cloud $cloud
 $status|ConvertTo-Json -Compress -Depth 3
 if($status.disposition -cne 'REVIEW_ONLY_CURRENT_OLD_ONLY_AND_READER_EMPTY_CAS_HISTORY_UNKNOWN'){
  exit 1
 }
 return
}
if(-not $ReviewExistingTwoSourcePrecommit -and
  ($ExistingNotebookReaderJson -or $ExistingCloudInventoryJson)){
 throw 'V3_PR515_TWO_SOURCE_ARGUMENTS_OUTSIDE_READONLY_MODE'
}

# Read-only originalhost consumer of the exact detached Notebook Reader CMS.
# Never call Native STOP/restore, CAS or Cloud as a result of this evidence.
if($VerifyNotebookPrecommitCms){
 if($BackupOriginalIntake -or $PreviewPr515PreCas -or $PreviewPr515Quiesced -or
    $PreviewPr515Armed -or $PreviewPr515ArmedTwoCycle -or
    $ValidatePr515RestoreXml -or $NotebookReaderJson -eq '' -or $NotebookReaderCms -eq '' -or
    $ReviewedNotebookCertificateSha256 -cnotmatch '^[a-f0-9]{64}$'){
  throw 'V3_NOTEBOOK_SIGNED_READER_MODE_CONFLICT_OR_MISSING_PIN'
 }
 $source=@($NotebookReaderJson,$NotebookReaderCms)|ForEach-Object {
  $item=Get-Item -LiteralPath $_ -Force -ErrorAction Stop
  if($item.PSIsContainer -or
     [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
     $item.Length -lt 64 -or $item.Length -gt 32768){
   throw 'V3_NOTEBOOK_SIGNED_READER_UNSAFE_TRANSFER_FILE'
  }
  $item
 }
 if($source.Count -ne 2 -or
    [IO.Path]::GetFileName($source[0].FullName) -cne 'reader.json' -or
    [IO.Path]::GetFileName($source[1].FullName) -cne 'reader.cms' -or
    [IO.Path]::GetDirectoryName($source[0].FullName) -cne
    [IO.Path]::GetDirectoryName($source[1].FullName)){
  throw 'V3_NOTEBOOK_SIGNED_READER_TRANSFER_PAIR_MISMATCH'
 }
 $v=Test-V3SignedNotebookPrecommitInventory -ReceiptUtf8 (
  [IO.File]::ReadAllBytes($source[0].FullName)) -DetachedCms (
  [IO.File]::ReadAllBytes($source[1].FullName)) -ReviewedCertSha256 $ReviewedNotebookCertificateSha256
 $v | ConvertTo-Json -Compress -Depth 3
 if($v.current_private_reader_zero_counts_verified -ne $true){exit 1}
 return
}

if($PreviewPr515PreCas -or $PreviewPr515Quiesced -or $PreviewPr515Armed -or $PreviewPr515ArmedTwoCycle -or $ValidatePr515RestoreXml) {
 $modeCount=[int]$PreviewPr515PreCas.IsPresent+[int]$PreviewPr515Quiesced.IsPresent+[int]$PreviewPr515Armed.IsPresent+[int]$PreviewPr515ArmedTwoCycle.IsPresent+[int]$ValidatePr515RestoreXml.IsPresent
 if($modeCount -ne 1 -or
    $BackupOriginalIntake -or $Confirm -or
    $ExpectedCandidatesActionSha256 -or $ExpectedWaitActionSha256 -or
    [string]::IsNullOrWhiteSpace($OriginalBackupDirectory) -or
    $ExpectedPr515SourceSha256 -cnotmatch '^[a-f0-9]{64}$' -or
    ($PreviewPr515ArmedTwoCycle -and $ExpectedArmedFenceSha256 -cnotmatch '^[a-f0-9]{64}$') -or
    (-not $PreviewPr515ArmedTwoCycle -and $ExpectedArmedFenceSha256)){
  throw 'Only approved read-only PR515 recovery preview parameters allowed'
 }
} elseif($OriginalBackupDirectory -or $ExpectedPr515SourceSha256 -or $ExpectedArmedFenceSha256){
 throw 'PR515 source preview arguments forbidden in backup mode'
}
if($BackupOriginalIntake) {
 if($Confirm -cne 'V3_PRECAS_NATIVE_XML_BACKUP_ONLY' -or
    $ExpectedCandidatesActionSha256 -cnotmatch '^[a-f0-9]{64}$' -or
    $ExpectedWaitActionSha256 -cnotmatch '^[a-f0-9]{64}$'){
  throw 'pre-CAS backup requires exact opt-in and both independent native task SHA256 pins'
 }
} elseif($Confirm -or $ExpectedCandidatesActionSha256 -or $ExpectedWaitActionSha256){
 throw 'backup-only parameters prohibited outside explicit originalhost backup'
}
$repo=Join-Path $TradingRoot 'Repos\kraken-eur-scanner'
$physical=Join-Path $repo 'tools\check-minipc-v3-physical-writer-readiness.ps1'
$marker=Join-Path $TradingRoot 'State\v3-experimental-paper-old-intake-fence.json'
$oldMaintenance=Join-Path $TradingRoot 'State\v2r4-technical-cutover-maintenance.json'
if(-not(Test-Path -LiteralPath $physical -PathType Leaf)){
 throw 'V3_READONLY_PREFLIGHT_SOURCE_MISSING: PR313 original-host source pin must be separately installed and verified.'
}
$report=& $physical -TradingRoot $TradingRoot | ConvertFrom-Json
$present=Test-Path -LiteralPath $marker
$oldPresent=Test-Path -LiteralPath $oldMaintenance
$ready=Test-V3CutoverPreparationPolicy -Report $report -FenceMarkerPresent $present -MaintenanceMarkerPresent $oldPresent
$waitTask=@($report.physical_v2r4_paper_task_readback |
 Where-Object { $_.task_name -ceq 'CryptoMiniPC-V2R4PaperWait' })
$waitActionObserved=($waitTask.Count -eq 1 -and
 $waitTask[0].action_script_basename -ceq 'wait_launcher.py' -and
 [string]$waitTask[0].action_sha256 -match '^[a-f0-9]{64}$')
$allProcessEdges=@()
$waitProcessRows=@()
$waitSnapshotReadable=$false
try {
 $allProcesses=@(Get-CimInstance Win32_Process -ErrorAction Stop)
 $allProcessEdges=@($allProcesses | ForEach-Object {
  [pscustomobject]@{
   PID=[int]$_.ProcessId
   ParentPID=[int]$_.ParentProcessId
   Name=[string]$_.Name
   TrustedConsoleHost=$false
  }
 })
 $oldStage=Join-Path $TradingRoot 'Staging\v2r4-wait-pr326-isolated-c660ebb87a39'
 foreach($p in $allProcesses){
  if([string]$p.Name -notmatch '(?i)^pythonw?\.exe$'){continue}
  $cmd=[string]$p.CommandLine
  if($cmd -notmatch '(?i)(?:wait_launcher|v2r4_wait_runtime)\.py'){continue}
  $waitProcessRows+=@([pscustomobject]@{
   PID=[int]$p.ProcessId
   ParentPID=[int]$p.ParentProcessId
   OriginalStage=$cmd.Contains($oldStage)
  })
 }
 # Never trust the image name alone. One optional extra conhost.exe is
 # attested from the SAME Win32 snapshot, then checked for PID-reuse drift.
 # Raw command lines and signer certificate details are not emitted.
 $waitIds=@($waitProcessRows | ForEach-Object {[int]$_.PID})
 $waitKids=@($waitProcessRows | Where-Object {[int]$_.ParentPID -in $waitIds})
 if($waitProcessRows.Count -eq 2 -and $waitKids.Count -eq 1){
  $waitRoot=@($waitProcessRows | Where-Object {
   [int]$_.PID -ne [int]$waitKids[0].PID
  })
  if($waitRoot.Count -eq 1){
   $extras=@($allProcesses | Where-Object {
    [int]$_.ParentProcessId -in $waitIds -and
    [int]$_.ProcessId -ne [int]$waitKids[0].PID
   })
   if($extras.Count -eq 1){
    $candidate=$extras[0]
    $rootNative=@($allProcesses | Where-Object {
     [int]$_.ProcessId -eq [int]$waitRoot[0].PID
    })
    $expectedConsole=Join-Path $env:WINDIR 'System32\conhost.exe'
    if($rootNative.Count -eq 1 -and
       [int]$candidate.ParentProcessId -eq [int]$waitRoot[0].PID -and
       [string]$candidate.Name -ieq 'conhost.exe' -and
       [string]$candidate.ExecutablePath -ieq $expectedConsole -and
       $null -ne $candidate.CreationDate -and
       $null -ne $rootNative[0].CreationDate -and
       $candidate.CreationDate -ge $rootNative[0].CreationDate -and
       @($allProcesses | Where-Object {
        [int]$_.ParentProcessId -eq [int]$candidate.ProcessId
       }).Count -eq 0){
     $sig=Get-AuthenticodeSignature -LiteralPath $expectedConsole -ErrorAction Stop
     $subject=[string]$sig.SignerCertificate.Subject
     if($sig.Status -eq 'Valid' -and
        $null -ne $sig.SignerCertificate -and
        $subject -match '(?:^|,)\s*O=Microsoft Corporation(?:,|$)'){
      $fresh=@(Get-CimInstance Win32_Process -Filter (
       'ProcessId=' + [int]$candidate.ProcessId
      ) -ErrorAction Stop)
      if($fresh.Count -eq 1 -and
         [int]$fresh[0].ParentProcessId -eq [int]$candidate.ParentProcessId -and
         [string]$fresh[0].Name -ieq 'conhost.exe' -and
         [string]$fresh[0].ExecutablePath -ieq $expectedConsole -and
         $fresh[0].CreationDate -eq $candidate.CreationDate){
       $trusted=@($allProcessEdges | Where-Object {
        [int]$_.PID -eq [int]$candidate.ProcessId
       })
       if($trusted.Count -eq 1){$trusted[0].TrustedConsoleHost=$true}
      }
     }
    }
   }
  }
 }
 $waitSnapshotReadable=$true
}catch{
 $waitProcessRows=@()
 $allProcessEdges=@()
}
$protected=@($report.native_old_paper_mode_rows | ForEach-Object {[int]$_.pid})
$completeWaitSnapshot=($waitSnapshotReadable -and
 (Test-V3WaitCompleteReadOnlyFamily -WaitRows $waitProcessRows -AllProcesses $allProcessEdges -WaitActionObserved $waitActionObserved -ProtectedRolePids $protected))
if($PreviewPr515PreCas) {
 if(-not $ready -or -not $completeWaitSnapshot){
  throw 'Originalhost V2R4 and WAIT descendants not ready'
 }
 $receipt=Read-V3Pr515FreshRecoveryPreview -Report $report -Root $TradingRoot -BackupDirectory $OriginalBackupDirectory -ExpectedCloudSha $ExpectedPr515SourceSha256
 $receipt | ConvertTo-Json -Depth 6
 return
}
# Reuse the real Windows Task Scheduler XML schema: Settings/Enabled is OPTIONAL
# and defaults to TRUE. Never alter the immutable original or backed-up XML.
# Derive an in-memory DISABLED candidate only for native TASK_VALIDATE_ONLY.
function Get-V3Pr515DisabledRestoreXmlForNativeValidation([string]$OriginalXml) {
 if([string]::IsNullOrWhiteSpace($OriginalXml) -or
    $OriginalXml.Length -lt 100 -or $OriginalXml.Length -gt 65536){
  throw 'V3_RESTORE_VALIDATE_XML_LENGTH_INVALID'
 }
 $doc=[xml]::new()
 $doc.XmlResolver=$null
 $doc.LoadXml($OriginalXml)
 $ns='http://schemas.microsoft.com/windows/2004/02/mit/task'
 if($null -eq $doc.DocumentElement -or
    [string]$doc.DocumentElement.LocalName -cne 'Task' -or
    [string]$doc.DocumentElement.NamespaceURI -cne $ns){
  throw 'V3_RESTORE_VALIDATE_FOREIGN_TASK_SCHEMA'
 }
 $settings=@($doc.SelectNodes('/*[local-name()="Task"]/*[local-name()="Settings"]'))
 if($settings.Count -ne 1 -or [string]$settings[0].NamespaceURI -cne $ns){
  throw 'V3_RESTORE_VALIDATE_SETTINGS_MISSING_OR_FOREIGN'
 }
 $enabled=@($settings[0].SelectNodes('./*[local-name()="Enabled"]'))
 if($enabled.Count -gt 1 -or
    ($enabled.Count -eq 1 -and
     ([string]$enabled[0].NamespaceURI -cne $ns -or
      ([string]$enabled[0].InnerText).Trim() -notin @('true','1')))){
  throw 'V3_RESTORE_VALIDATE_EXPLICIT_ENABLED_INVALID_OR_DISABLED'
 }
 if($enabled.Count -eq 0){
  # xs:all (Settings) permits element order variation; no Enabled means
  # the schema's default TRUE. Add only the missing child to a memory clone.
  $newEnabled=$doc.CreateElement('Enabled',$ns)
  $newEnabled.InnerText='false'
  [void]$settings[0].AppendChild($newEnabled)
 }else{
  $enabled[0].InnerText='false'
 }
 $disabled=[string]$doc.OuterXml
 if($disabled.Length -gt 65536){throw 'V3_RESTORE_VALIDATE_DISABLED_XML_TOO_LARGE'}
 return $disabled
}

# ORIGINALHOST native Scheduler XML validation, no Task registration or STOP.
# TASK_VALIDATE_ONLY=1 is a native parser validation, NOT real restore.
if($ValidatePr515RestoreXml) {
 if(-not $ready -or -not $completeWaitSnapshot){
  throw 'V3_RESTORE_VALIDATE_ORIGINALHOST_INTAKES_NOT_READY'
 }
 if([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT -or
    -not ([IO.Path]::GetFullPath($TradingRoot).TrimEnd('\')).Equals('C:\Users\ADMIN\Trading',[StringComparison]::OrdinalIgnoreCase)){
  throw 'V3_RESTORE_VALIDATE_NOT_ORIGINAL_WINDOWS_HOST'
 }
 $win=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
 if(-not $win.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){
  throw 'V3_RESTORE_VALIDATE_ORIGINAL_ADMIN_REQUIRED'
 }
 $state=Join-Path $TradingRoot 'State'
 $backup=[IO.Path]::GetFullPath($OriginalBackupDirectory).TrimEnd('\')
 if(-not ([IO.Path]::GetDirectoryName($backup)).Equals($state,[StringComparison]::OrdinalIgnoreCase) -or
    [IO.Path]::GetFileName($backup) -cnotmatch '^V3Paper-PreCAS-Backup-[a-f0-9]{32}$' -or
    (Test-Path -LiteralPath $marker) -or (Test-Path -LiteralPath $oldMaintenance)){
  throw 'V3_RESTORE_VALIDATE_FENCE_OR_BACKUP_PATH_DRIFT'
 }
 $pre=Read-V3Pr515FreshRecoveryPreview -Report $report -Root $TradingRoot -BackupDirectory $backup -ExpectedCloudSha $ExpectedPr515SourceSha256
 if([string]$pre.status -cne 'COMPATIBLE_READONLY_NOT_RELEASED' -or
    -not(Test-V3Pr515FreshRecoveryIdentity -Preview $pre)){
  throw 'V3_RESTORE_VALIDATE_ORIGINAL_BACKUP_PR515_RECHECK_FAILED'
 }
 $item=Get-Item -LiteralPath (Join-Path $backup 'backup-manifest.json') -Force -ErrorAction Stop
 if($item.PSIsContainer -or [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
    $item.Length -lt 100 -or $item.Length -gt 65536){
  throw 'V3_RESTORE_VALIDATE_UNSAFE_MANIFEST'
 }
 $manifest=Get-Content -LiteralPath $item.FullName -Raw -Encoding UTF8 -ErrorAction Stop|ConvertFrom-Json
 $names=@('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait')
 if([string]$manifest.kind -cne 'V3_PRECAS_NATIVE_XML_BACKUP_ORIGINALHOST_V1' -or
    [string]$manifest.backup_directory -cne $backup -or
    [string]$manifest.predecessor_series_id -cne 'PAPER-V2R4-20261009T110135Z' -or
    @($manifest.task_records).Count -ne 2){
  throw 'V3_RESTORE_VALIDATE_BACKUP_IDENTITY_DRIFT'
 }
 $native=@()
 foreach($name in $names){
  $row=@($manifest.task_records|Where-Object{$_.task_name -ceq $name})
  $leaf=if($name -ceq $names[0]){'Candidates.task.xml'}else{'WAIT.task.xml'}
  $task=Get-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction Stop
  $xml=[string](Export-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction Stop)
  if($row.Count -ne 1 -or [string]$row[0].xml_file -cne $leaf -or
     [string]$row[0].xml_sha256 -cnotmatch '^[a-f0-9]{64}$' -or
     [string]$task.State -cne 'Running' -or
     [string]$task.Principal.UserId -notin @('SYSTEM','NT AUTHORITY\SYSTEM','S-1-5-18') -or
     @($task.Actions).Count -ne 1 -or
     (Get-V3OriginalNativeActionSha $task.Actions[0]) -cne [string]$row[0].action_sha256 -or
     -not(Test-V3FreshBackupFileBytes -Path (Join-Path $backup $leaf) -ExpectedSha ([string]$row[0].xml_sha256) -ExpectedXml $xml)){
   throw 'V3_RESTORE_VALIDATE_NATIVE_XML_OR_SHA_DRIFT'
  }
  $disabledXml=Get-V3Pr515DisabledRestoreXmlForNativeValidation -OriginalXml $xml
  $native+=@([pscustomobject]@{name=$name;source=$xml;disabled=$disabledXml;action=[string]$row[0].action_sha256})
 }
 $svc=New-Object -ComObject 'Schedule.Service';$taskFolder=$null
 try{
  $svc.Connect();$taskFolder=$svc.GetFolder('\')
  foreach($x in $native){
   $null=$taskFolder.RegisterTask($x.name,$x.source,1,$null,$null,5)
   $null=$taskFolder.RegisterTask($x.name,$x.disabled,1,$null,$null,5)
  }
 }finally{
  if($null -ne $taskFolder){[void][Runtime.InteropServices.Marshal]::ReleaseComObject($taskFolder)}
  if($null -ne $svc){[void][Runtime.InteropServices.Marshal]::ReleaseComObject($svc)}
 }
 foreach($x in $native){
  $task=Get-ScheduledTask -TaskName $x.name -TaskPath '\' -ErrorAction Stop
  if([string]$task.State -cne 'Running' -or
     (Get-V3OriginalNativeActionSha $task.Actions[0]) -cne $x.action -or
     [string](Export-ScheduledTask -TaskName $x.name -TaskPath '\' -ErrorAction Stop) -cne $x.source -or
     (Test-Path -LiteralPath $marker) -or (Test-Path -LiteralPath $oldMaintenance)){
   throw 'V3_RESTORE_VALIDATE_ORIGINAL_CHANGED_AFTER_SCHEDULER_CHECK'
  }
 }
 [pscustomobject][ordered]@{
  kind='V3_PR515_ORIGINAL_SCHEDULER_VALIDATE_ONLY_V1'
  status='REAL_SCHEDULER_XML_VALIDATION_PASS_NO_RESTORE'
  original_tasks_checked=2
  enabled_and_disabled_xml_validations=4
  registered_or_modified_tasks=0
  actual_restore_executed=$false
  actual_stop_or_norearm_executed=$false
  independent_cloud_cas_custody_proven=$false
  v3_paper_authorized=$false
 }|ConvertTo-Json -Compress
 return
}
if($PreviewPr515ArmedTwoCycle) {
 # Originalhost local read-only evidence, NOT independent Cloud CAS authority.
 $receipt=Read-V3Pr515ArmedTwoCycleOriginalHost -Report $report -Root $TradingRoot -BackupDirectory $OriginalBackupDirectory -ExpectedCloudSha $ExpectedPr515SourceSha256 -ExpectedFenceSha $ExpectedArmedFenceSha256
 $receipt | ConvertTo-Json -Depth 5
 return
}
if($PreviewPr515Armed) {
 # After the future separately authorized native stop, the persisted fence
 # MUST still be ARMED. Only observes native Disabled XML/PR515 and one local
 # supervisor sample; NEVER promotes the marker, queries CAS or gives 2 cycles.
 $receipt=Read-V3Pr515FreshRecoveryPreview -Report $report -Root $TradingRoot -BackupDirectory $OriginalBackupDirectory -ExpectedCloudSha $ExpectedPr515SourceSha256 -ExpectedArmed
 $receipt | ConvertTo-Json -Depth 7
 return
}
if($PreviewPr515Quiesced) {
 # The original four-role inspector may see disabled native tasks. Its
 # running-intake readiness is NOT used as a QUIESCED release proof.
 $receipt=Read-V3Pr515FreshRecoveryPreview -Report $report -Root $TradingRoot -BackupDirectory $OriginalBackupDirectory -ExpectedCloudSha $ExpectedPr515SourceSha256 -ExpectedQuiesced
 $receipt | ConvertTo-Json -Depth 7
 return
}
if($BackupOriginalIntake) {
 if(-not $ready -or -not $completeWaitSnapshot) {
  throw 'pre-CAS original intake must be healthy with closed WAIT descendants'
 }
 $record=Save-V3OriginalIntakeXmlOnly -Report $report -Root $TradingRoot -CandidateSha $ExpectedCandidatesActionSha256 -WaitSha $ExpectedWaitActionSha256
 $record | ConvertTo-Json -Depth 7
 return
}
[ordered]@{
 kind='V3_SCOPED_CUTOVER_OPERATOR_SOURCE_PREP_INACTIVE_V1'
 phase='READ_ONLY'
 checked_at_utc=(Get-Date).ToUniversalTime().ToString('o')
 pre_cutover_discovery_pass=$ready
 candidate_wait_only_future_quiesce_scope=@(
  'CryptoMiniPC-V2R4PaperCandidates',
  'CryptoMiniPC-V2R4PaperWait'
 )
 must_preserve_original_tasks=@(
  'CryptoMiniPC-V2R4PaperLifecycle',
  'CryptoMiniPC-V2R4PaperCloudSync'
 )
 original_role_lineage_snapshot_only=$true
 v3_host_source_deployment_independently_required=$true
 original_wait_tree_and_full_task_source_pins_separate_gate=$true
 wait_full_process_inventory_readable=$waitSnapshotReadable
 wait_closed_descendants_readonly_snapshot_pass=$completeWaitSnapshot
 wait_closed_descendants_snapshot_only_no_stop_authority=$true
 wait_seen_python_family_count=@($waitProcessRows).Count
 wait_unrecognized_descendant_failure_is_fail_closed=$true
 wait_signed_system32_consolehost_exception_scoped=$true
 wait_consolehost_attestation_is_snapshot_only_not_stop_authority=$true
 windows_native_disable_stop_and_no_rearm_proven=$false
 physically_quiescent_old_intake_processes_proven=$false
 historical_followup_and_exit_cloud_ack_proven=$false
 cloud_single_active_cas_proven=$false
 backup_manifest_contract_policy_only=$true
 cutover_recovery_decision_matrix_policy_only=$true
 real_task_xml_backup_not_yet_executed=$true
 exact_task_stop_disable_and_native_no_rearm_unimplemented=$true
 rollback_precommit_only_unimplemented=$true
 unknown_cloud_commit_forbids_old_writer_rearm=$true
 v3_paper_technical_e2e_proofs_accepted=0
 v3_live_release_authorized=$false
 task_process_marker_cloud_writes=0
 do_not_use_old_v2r4_technical_cutover_operator=$true
} | ConvertTo-Json -Depth 7
