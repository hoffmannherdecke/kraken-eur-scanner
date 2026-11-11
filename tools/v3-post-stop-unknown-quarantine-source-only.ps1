# Pure source-only contract; NOT imported by any production operator.
# Historical release package/authority bytes remain immutable.
# AP04 historical Post-STOP-UNKNOWN: deterministic source-only quarantine decision.
# This function intentionally grants NO execution, cloud mutation, task enable,
# STOP replay, fence archival or transition to AP05A. No external calls.
# The source-only candidate cannot assert past STOP success from current state.
function Assert-V3PostStopUnknownQuarantineSourceContract([object]$Evidence) {
 if($null -eq $Evidence){throw 'V3_POSTSTOP_EVIDENCE_REQUIRED_HOLD'}
 $names=@($Evidence.PSObject.Properties.Name)
 $required=@('kind','series_id','epoch_id','fence_sha256','fence_phase',
  'cloud_inhibit_state','cloud_epoch_sealed','cloud_next_ordinal',
  'cloud_intent_count','cloud_attempt_count','cloud_abort_count',
  'candidates_enabled','wait_enabled','cloudsync_enabled','v3_writer_enabled',
  'native_stop_outcome','originalhost_journal_present',
  'independent_host_custody_verified','independent_cloud_reader_verified')
 if($names.Count -ne $required.Count -or
    @($names|Where-Object {$_ -cnotin $required}).Count){
  throw 'V3_POSTSTOP_EVIDENCE_FIELDS_HOLD'
 }
 if([string]$Evidence.kind -cne 'V3_POST_STOP_UNKNOWN_READONLY_STATE_V1' -or
    [string]$Evidence.series_id -cne 'PAPER-V3-20261111T105211Z' -or
    [string]$Evidence.epoch_id -cne 'V3CAS-AUDIT-f27cce0ba68043b480e4f97698dd2901' -or
    [string]$Evidence.fence_sha256 -cne '4f01704d20375f201f87c56eb3350a67c1a91f82535296b28ae318768aa213ef' -or
    [string]$Evidence.fence_phase -cne 'ARMED' -or
    [string]$Evidence.cloud_inhibit_state -cne 'INHIBITED' -or
    $Evidence.cloud_epoch_sealed -isnot [bool] -or $Evidence.cloud_epoch_sealed -ne $false -or
    $Evidence.cloud_next_ordinal -isnot [int] -or $Evidence.cloud_next_ordinal -ne 1 -or
    $Evidence.cloud_intent_count -isnot [int] -or $Evidence.cloud_intent_count -ne 0 -or
    $Evidence.cloud_attempt_count -isnot [int] -or $Evidence.cloud_attempt_count -ne 0 -or
    $Evidence.cloud_abort_count -isnot [int] -or $Evidence.cloud_abort_count -ne 0 -or
    $Evidence.candidates_enabled -isnot [bool] -or $Evidence.candidates_enabled -ne $true -or
    $Evidence.wait_enabled -isnot [bool] -or $Evidence.wait_enabled -ne $true -or
    $Evidence.cloudsync_enabled -isnot [bool] -or $Evidence.cloudsync_enabled -ne $true -or
    $Evidence.v3_writer_enabled -isnot [bool] -or $Evidence.v3_writer_enabled -ne $false -or
    [string]$Evidence.native_stop_outcome -cne 'UNKNOWN' -or
    $Evidence.originalhost_journal_present -isnot [bool] -or $Evidence.originalhost_journal_present -ne $false -or
    $Evidence.independent_host_custody_verified -isnot [bool] -or
    $Evidence.independent_cloud_reader_verified -isnot [bool]){
  throw 'V3_POSTSTOP_STATE_OR_SCOPE_HOLD'
 }
 # Positive current-state match is NOT historical custody, or production authority.
 return [pscustomobject]@{
  kind='V3_POST_STOP_UNKNOWN_QUARANTINE_SOURCE_DECISION_V1'
  series_id=[string]$Evidence.series_id
  epoch_id=[string]$Evidence.epoch_id
  current_state_matches_historical_hold=$true
  historical_stop_success_claimed=$false
  cloud_terminal_abort_confirmed=$false
  originalhost_recovered=$false
  production_authorized=$false
  retry_authorized=$false
  new_writer_authorized=$false
  requires_separate_effectful_operator_and_owner_cms=$true
  requires_current_independent_host_and_cloud_reader=$true
  disposition='SOURCE_ONLY_NO_PRODUCTION_EFFECT'
 }
}

