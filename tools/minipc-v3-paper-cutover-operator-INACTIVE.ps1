param(
 [string]$TradingRoot=(Join-Path $env:USERPROFILE 'Trading'),
 [switch]$Execute
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
 # Reject any edge pointing into the WAIT family except its verified child.
 # This covers Windows process types beyond Python and deeper descendants.
 foreach($p in $all){
   if([int]$p.ParentPID -in $ids -and [int]$p.PID -ne [int]$child.PID){return $false}
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

# A pure decision matrix. NEVER restore an old writer after ANY CAS invocation,
# including timeout, no response or an apparently negative outcome: operator
# MUST fence and reconcile actual independent Cloud readback by hand.
# No decision returned here grants permission to execute a Windows mutation.
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
  $outcome=[string]$Receipt.cloud_cas_outcome
  $invoked=($Receipt.cloud_cas_invoked -eq $true)
  if($outcome -notin @('NOT_INVOKED','UNKNOWN','NOT_COMMITTED','COMMITTED')){
   $resolution='HOLD_INVALID_CLOUD_OUTCOME'
  } elseif($outcome -eq 'COMMITTED' -or $phase -eq 'CLOUD_COMMITTED'){
   $resolution='HOLD_POSTCOMMIT_OLD_INTAKE_PERMANENTLY_FENCED'
  } elseif($invoked -or $outcome -ne 'NOT_INVOKED' -or $phase -eq 'CAS_INVOKED'){
   $resolution='HOLD_CAS_ATTEMPTED_MANUAL_CLOUD_RECONCILIATION'
  } elseif($phase -eq 'PRE_CUTOVER'){
   $resolution='NO_ACTION_PRESERVE_ACTIVE_V2R4'
  } elseif($phase -notin @('ARMED','QUIESCED')){
   $resolution='HOLD_UNKNOWN_PHASE'
  } elseif($phase -eq 'QUIESCED' -and
      (Test-V3ScopedOriginalBackupContract -Manifest $Receipt.backup_manifest) -and
      $Receipt.backup_contract_verified -eq $true -and
      $Receipt.native_intake_tasks_disabled_ack -eq $true -and
      $Receipt.original_intake_processes_absent_ack -eq $true -and
      $Receipt.windows_supervisor_no_rearm_ack -eq $true -and
      $Receipt.protected_lifecycle_cloudsync_running_ack -eq $true -and
      $Receipt.old_cloud_single_active_readback -eq $true -and
      $Receipt.new_v3_series_absent_readback -eq $true -and
      $Receipt.v3_writer_started -eq $false){
   $resolution='PRE_CAS_MANUAL_ROLLBACK_REVIEW_CANDIDATE'
  }
 }
 return [pscustomobject]@{
  kind='V3_CUTOVER_RECOVERY_OFFLINE_DISPOSITION_V1'
  disposition=$resolution
  automatic_task_action_authorized=$false
  automatic_old_writer_rearm_allowed=$false
  operator_stop_disable_implemented=$false
  host_rollback_implemented=$false
  cloud_cas_executed=$false
  v3_release_authorized=$false
  full_v3_e2e_proofs_credited=0
 }
}

if($Execute){
 throw 'V3_CUTOVER_EXECUTION_LOCKED: no stop/disable, marker, CAS, or rollback is implemented or authorized in this inactive source.'
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
  [pscustomobject]@{PID=[int]$_.ProcessId;ParentPID=[int]$_.ParentProcessId}
 })
 $oldStage=Join-Path $TradingRoot 'Runtime\v2r4-paper-stage-d8b35a8ec2e6'
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
 $waitSnapshotReadable=$true
}catch{
 $waitProcessRows=@()
 $allProcessEdges=@()
}
$protected=@($report.native_old_paper_mode_rows | ForEach-Object {[int]$_.pid})
$completeWaitSnapshot=($waitSnapshotReadable -and
 (Test-V3WaitCompleteReadOnlyFamily -WaitRows $waitProcessRows -AllProcesses $allProcessEdges -WaitActionObserved $waitActionObserved -ProtectedRolePids $protected))
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
