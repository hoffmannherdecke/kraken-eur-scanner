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


# Separate, CURRENT, independently signed Host and Cloud evidence.
# The reviewer pins every expected SHA256 outside the supplied evidence.
# Never interprets UNKNOWN as a successful historical STOP.
# The routine is deliberately pure and never performs the next transaction.
function Assert-V3PostStopUnknownCurrentCustody(
 [byte[]]$HostPayload,[byte[]]$HostCms,
 [byte[]]$CloudPayload,[byte[]]$CloudCms,
 [object]$Pins,[datetimeoffset]$Now=[datetimeoffset]::UtcNow) {
 if($null -eq $Pins){throw 'V3_POSTSTOP_CURRENT_PINS_REQUIRED_HOLD'}
 $required=@('series_id','epoch_id','source_sha256','epoch_fence_sha256',
  'caller_acl_sha256','local_fence_file_sha256','candidates_xml_sha256',
  'wait_xml_sha256','cloudsync_xml_sha256','writer_xml_sha256',
  'host_certificate_sha256','cloud_certificate_sha256',
  'host_payload_sha256','cloud_payload_sha256','owner_review_sha256',
  'observation_nonce')
 $fields=@($Pins.PSObject.Properties.Name)
 if($fields.Count -ne $required.Count -or
    @($fields|Where-Object {$_ -cnotin $required}).Count){
  throw 'V3_POSTSTOP_CURRENT_PINS_SCOPE_HOLD'
 }
 if([string]$Pins.series_id -cne 'PAPER-V3-20261111T105211Z' -or
    [string]$Pins.epoch_id -cne 'V3CAS-AUDIT-f27cce0ba68043b480e4f97698dd2901' -or
    [string]$Pins.local_fence_file_sha256 -cne
      '4f01704d20375f201f87c56eb3350a67c1a91f82535296b28ae318768aa213ef' -or
    [string]$Pins.observation_nonce -cnotmatch '^[a-f0-9]{32}$'){
  throw 'V3_POSTSTOP_CURRENT_HISTORICAL_PIN_HOLD'
 }
 foreach($name in $required|Where-Object {$_ -notin @('series_id','epoch_id','observation_nonce')}){
  if([string]$Pins.$name -cnotmatch '^[a-f0-9]{64}$'){
   throw 'V3_POSTSTOP_CURRENT_SHA_PIN_HOLD'
  }
 }
 if([string]$Pins.host_certificate_sha256 -ceq [string]$Pins.cloud_certificate_sha256 -or
    [string]$Pins.host_payload_sha256 -ceq [string]$Pins.cloud_payload_sha256){
  throw 'V3_POSTSTOP_READER_INDEPENDENCE_HOLD'
 }
 # Reuse the exact existing detached-CMS and anti-duplicate JSON primitives.
 # Trust pins come from independently admitted owner material, never receipts.
 Assert-V3ReleaseCms -Payload $HostPayload -Cms $HostCms -ReviewedAuthorityCertificateSha256 $Pins.host_certificate_sha256
 Assert-V3ReleaseCms -Payload $CloudPayload -Cms $CloudCms -ReviewedAuthorityCertificateSha256 $Pins.cloud_certificate_sha256
 if((Get-V3ReleaseSha256 $HostPayload) -cne [string]$Pins.host_payload_sha256 -or
    (Get-V3ReleaseSha256 $CloudPayload) -cne [string]$Pins.cloud_payload_sha256){
  throw 'V3_POSTSTOP_CURRENT_RECEIPT_BYTE_DRIFT_HOLD'
 }
 $hostRow=Read-V3ReleaseJson $HostPayload
 $cloud=Read-V3ReleaseJson $CloudPayload
 $hostRequired=@('kind','series_id','epoch_id','source_sha256',
  'observation_nonce','observed_at_utc','original_fence_sha256',
  'local_fence_file_sha256','fence_phase','candidates_xml_sha256',
  'wait_xml_sha256','cloudsync_xml_sha256','writer_xml_sha256',
  'candidates_enabled','wait_enabled','cloudsync_enabled','writer_enabled',
  'writer_process_count','other_writer_authorities_closed',
  'native_stop_outcome','current_host_custody_verified')
 $cloudRequired=@('kind','series_id','epoch_id','source_sha256',
  'observation_nonce','observed_at_utc','original_fence_sha256',
  'caller_acl_sha256','inhibit_state','sealed','next_ordinal',
  'intent_count','attempt_count','abort_count','executor_login_closed',
  'executor_sessions_count','v3_active_series_count','v2r4_active_series_count',
  'cloud_cas_rpc_count','reader_role','current_cloud_custody_verified')
 if(@($hostRow.PSObject.Properties).Count -ne $hostRequired.Count -or
    @($hostRow.PSObject.Properties.Name|Where-Object {$_ -cnotin $hostRequired}).Count -or
    @($cloud.PSObject.Properties).Count -ne $cloudRequired.Count -or
    @($cloud.PSObject.Properties.Name|Where-Object {$_ -cnotin $cloudRequired}).Count){
  throw 'V3_POSTSTOP_CURRENT_RECEIPT_FIELDS_HOLD'
 }
 if([string]$hostRow.kind -cne 'V3_POSTSTOP_CURRENT_INDEPENDENT_HOST_READER_V1' -or
    [string]$cloud.kind -cne 'V3_POSTSTOP_CURRENT_INDEPENDENT_CLOUD_READER_V1' -or
    [string]$cloud.reader_role -cne 'v3_cas_audit_reader' -or
    [string]$hostRow.series_id -cne [string]$Pins.series_id -or
    [string]$cloud.series_id -cne [string]$Pins.series_id -or
    [string]$hostRow.epoch_id -cne [string]$Pins.epoch_id -or
    [string]$cloud.epoch_id -cne [string]$Pins.epoch_id -or
    [string]$hostRow.source_sha256 -cne [string]$Pins.source_sha256 -or
    [string]$cloud.source_sha256 -cne [string]$Pins.source_sha256 -or
    [string]$hostRow.observation_nonce -cne [string]$Pins.observation_nonce -or
    [string]$cloud.observation_nonce -cne [string]$Pins.observation_nonce -or
    [string]$hostRow.original_fence_sha256 -cne [string]$Pins.epoch_fence_sha256 -or
    [string]$cloud.original_fence_sha256 -cne [string]$Pins.epoch_fence_sha256 -or
    [string]$cloud.caller_acl_sha256 -cne [string]$Pins.caller_acl_sha256 -or
    [string]$hostRow.local_fence_file_sha256 -cne [string]$Pins.local_fence_file_sha256 -or
    [string]$hostRow.fence_phase -cne 'ARMED' -or
    [string]$hostRow.candidates_xml_sha256 -cne [string]$Pins.candidates_xml_sha256 -or
    [string]$hostRow.wait_xml_sha256 -cne [string]$Pins.wait_xml_sha256 -or
    [string]$hostRow.cloudsync_xml_sha256 -cne [string]$Pins.cloudsync_xml_sha256 -or
    [string]$hostRow.writer_xml_sha256 -cne [string]$Pins.writer_xml_sha256 -or
    $hostRow.candidates_enabled -isnot [bool] -or $hostRow.candidates_enabled -ne $true -or
    $hostRow.wait_enabled -isnot [bool] -or $hostRow.wait_enabled -ne $true -or
    $hostRow.cloudsync_enabled -isnot [bool] -or $hostRow.cloudsync_enabled -ne $true -or
    $hostRow.writer_enabled -isnot [bool] -or $hostRow.writer_enabled -ne $false -or
    ($hostRow.writer_process_count -isnot [int] -and $hostRow.writer_process_count -isnot [long]) -or $hostRow.writer_process_count -ne 0 -or
    $hostRow.other_writer_authorities_closed -isnot [bool] -or $hostRow.other_writer_authorities_closed -ne $true -or
    [string]$hostRow.native_stop_outcome -cne 'UNKNOWN' -or
    $hostRow.current_host_custody_verified -isnot [bool] -or $hostRow.current_host_custody_verified -ne $true -or
    [string]$cloud.inhibit_state -cne 'INHIBITED' -or
    $cloud.sealed -isnot [bool] -or $cloud.sealed -ne $false -or
    ($cloud.next_ordinal -isnot [int] -and $cloud.next_ordinal -isnot [long]) -or $cloud.next_ordinal -ne 1 -or
    ($cloud.intent_count -isnot [int] -and $cloud.intent_count -isnot [long]) -or $cloud.intent_count -ne 0 -or
    ($cloud.attempt_count -isnot [int] -and $cloud.attempt_count -isnot [long]) -or $cloud.attempt_count -ne 0 -or
    ($cloud.abort_count -isnot [int] -and $cloud.abort_count -isnot [long]) -or $cloud.abort_count -ne 0 -or
    $cloud.executor_login_closed -isnot [bool] -or $cloud.executor_login_closed -ne $true -or
    ($cloud.executor_sessions_count -isnot [int] -and $cloud.executor_sessions_count -isnot [long]) -or $cloud.executor_sessions_count -ne 0 -or
    ($cloud.v3_active_series_count -isnot [int] -and $cloud.v3_active_series_count -isnot [long]) -or $cloud.v3_active_series_count -ne 0 -or
    ($cloud.v2r4_active_series_count -isnot [int] -and $cloud.v2r4_active_series_count -isnot [long]) -or $cloud.v2r4_active_series_count -ne 1 -or
    ($cloud.cloud_cas_rpc_count -isnot [int] -and $cloud.cloud_cas_rpc_count -isnot [long]) -or $cloud.cloud_cas_rpc_count -ne 0 -or
    $cloud.current_cloud_custody_verified -isnot [bool] -or $cloud.current_cloud_custody_verified -ne $true){
  throw 'V3_POSTSTOP_CURRENT_HOST_CLOUD_SAFETY_HOLD'
 }
 try{
  # Read the signed JSON timestamp literals: PowerShell 7 otherwise coerces ISO strings into DateTime.
  $hm=[regex]::Match([Text.Encoding]::UTF8.GetString($HostPayload),'"observed_at_utc"\s*:\s*"(?<t>[^"]+)"')
  $cm=[regex]::Match([Text.Encoding]::UTF8.GetString($CloudPayload),'"observed_at_utc"\s*:\s*"(?<t>[^"]+)"')
  if(-not $hm.Success -or -not $cm.Success){throw 'V3_POSTSTOP_TIMESTAMP_LITERAL_MISSING'}
  $ht=[datetimeoffset]::ParseExact($hm.Groups['t'].Value,
   "yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'",[Globalization.CultureInfo]::InvariantCulture,
   [Globalization.DateTimeStyles]::AssumeUniversal)
  $ct=[datetimeoffset]::ParseExact($cm.Groups['t'].Value,
   "yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'",[Globalization.CultureInfo]::InvariantCulture,
   [Globalization.DateTimeStyles]::AssumeUniversal)
 }catch{throw 'V3_POSTSTOP_CURRENT_RECEIPT_TIMESTAMP_HOLD'}
 if($ht -gt $Now.AddSeconds(5) -or $ct -gt $Now.AddSeconds(5) -or
    ($Now-$ht).TotalSeconds -gt 60 -or ($Now-$ct).TotalSeconds -gt 60 -or
    [math]::Abs(($ht-$ct).TotalSeconds) -gt 15){
  throw 'V3_POSTSTOP_CURRENT_RECEIPT_STALE_OR_DRIFT_HOLD'
 }
 return [pscustomobject]@{
  kind='V3_POSTSTOP_CURRENT_CUSTODY_SOURCE_REVIEW_V1'
  series_id=[string]$Pins.series_id;epoch_id=[string]$Pins.epoch_id
  host_payload_sha256=[string]$Pins.host_payload_sha256
  cloud_payload_sha256=[string]$Pins.cloud_payload_sha256
  owner_review_sha256=[string]$Pins.owner_review_sha256
  source_sha256=[string]$Pins.source_sha256
  epoch_fence_sha256=[string]$Pins.epoch_fence_sha256
  caller_acl_sha256=[string]$Pins.caller_acl_sha256
  independently_signed_current_custody=$true
  historical_stop_reconstructed=$false
  historical_stop_success_claimed=$false
  terminal_cloud_abort_confirmed=$false
  terminal_host_recovery_confirmed=$false
  production_authorized=$false
  repeat_authorized=$false
  writer_authorized=$false
  disposition='SOURCE_REVIEW_CANDIDATE_ONLY'
 }
}

# Exact receipt binding over CURRENT independently signed Host/Cloud custody.
# No PRE-STOP historical original is synthesized or required.
function Get-V3PostStopCurrentCustodyReceiptSha256([object]$Custody) {
 if($null -eq $Custody -or
    [string]$Custody.kind -cne 'V3_POSTSTOP_CURRENT_CUSTODY_SOURCE_REVIEW_V1' -or
    $Custody.independently_signed_current_custody -ne $true -or
    [string]$Custody.epoch_id -cne 'V3CAS-AUDIT-f27cce0ba68043b480e4f97698dd2901') {
  throw 'V3_POSTSTOP_CURRENT_RECEIPT_SOURCE_HOLD'
 }
 foreach($field in @('host_payload_sha256','cloud_payload_sha256','owner_review_sha256')) {
  if([string]$Custody.$field -cnotmatch '^[a-f0-9]{64}\z') {
   throw 'V3_POSTSTOP_CURRENT_RECEIPT_SHA_HOLD'
  }
 }
 $material='V3_POSTSTOP_CURRENT_CUSTODY_RECEIPT_V1|'+
  [string]$Custody.epoch_id+'|'+[string]$Custody.host_payload_sha256+'|'+
  [string]$Custody.cloud_payload_sha256+'|'+[string]$Custody.owner_review_sha256
 return Get-V3ReleaseSha256 ([Text.Encoding]::UTF8.GetBytes($material))
}

# Candidate-only cloud transaction. This source is not imported by the launcher.
# The installed SQL function is already constrained to one terminal abort row.
function Get-V3PostStopCloudAbortCandidate([object]$Custody,[object]$Pins,
 [string]$CurrentCustodyReceiptSha256,[datetimeoffset]$Expiry) {
 if($null -eq $Pins -or $null -eq $Custody -or
    [string]$Custody.kind -cne 'V3_POSTSTOP_CURRENT_CUSTODY_SOURCE_REVIEW_V1' -or
    $Custody.independently_signed_current_custody -ne $true -or
    $Custody.production_authorized -ne $false -or
    [string]$Custody.epoch_id -cne 'V3CAS-AUDIT-f27cce0ba68043b480e4f97698dd2901' -or
    [string]$Custody.series_id -cne 'PAPER-V3-20261111T105211Z' -or
    [string]$Custody.host_payload_sha256 -cne [string]$Pins.host_payload_sha256 -or
    [string]$Custody.cloud_payload_sha256 -cne [string]$Pins.cloud_payload_sha256 -or
    [string]$Custody.source_sha256 -cne [string]$Pins.source_sha256 -or
    [string]$Custody.epoch_fence_sha256 -cne [string]$Pins.epoch_fence_sha256 -or
    [string]$Custody.caller_acl_sha256 -cne [string]$Pins.caller_acl_sha256 -or
    [string]$CurrentCustodyReceiptSha256 -cnotmatch '^[a-f0-9]{64}\z' -or
    [string]$CurrentCustodyReceiptSha256 -cne (Get-V3PostStopCurrentCustodyReceiptSha256 $Custody) -or
    $Expiry -le [datetimeoffset]::UtcNow -or
    $Expiry -gt [datetimeoffset]::UtcNow.AddMinutes(2)) {
  throw 'V3_POSTSTOP_CLOUD_CANDIDATE_PRECONDITION_HOLD'
 }
 foreach($key in @('source_sha256','epoch_fence_sha256','caller_acl_sha256')) {
  if([string]$Pins.$key -cnotmatch '^[a-f0-9]{64}$') {
   throw 'V3_POSTSTOP_CLOUD_CANDIDATE_PIN_HOLD'
  }
 }
 $until=$Expiry.ToUniversalTime().ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
 $sql=@(
  'BEGIN;'
  "SET LOCAL statement_timeout='15s';"
  "SET LOCAL lock_timeout='5s';"
  'DO $poststop$'
  'BEGIN'
  " IF session_user <> 'v3_cas_inhibit_issuer_actor' OR clock_timestamp() >= '$until'::timestamptz THEN"
  "  RAISE EXCEPTION 'V3_POSTSTOP_OWNER_OR_WINDOW_HOLD';"
  ' END IF;'
  'END $poststop$;'
  'SELECT v3_cas_audit.record_prepared_fence_abort_v1('
  " 'V3CAS-AUDIT-f27cce0ba68043b480e4f97698dd2901',"
  " '$($Pins.source_sha256)',"
  " '$($Pins.epoch_fence_sha256)',"
  " '$($Pins.caller_acl_sha256)',"
  " '$CurrentCustodyReceiptSha256');"
  'COMMIT;' ) -join [Environment]::NewLine
 # The expiry is an independently admitted maximum deadline, NOT a waiver.
 # This builder is SOURCE ONLY; effectful caller must check expiry inside DB
 # against the same bound clock before invoking this SQL.
 return [pscustomobject]@{
  kind='V3_POSTSTOP_CLOUD_ABORT_SQL_CANDIDATE_V1'
  epoch_id=[string]$Custody.epoch_id
  series_id=[string]$Custody.series_id
  admission_expires_at_utc=$until
  sql=$sql
  execution_authorized=$false
  stop_success_claimed=$false
  terminal_readback_required=$true
 }
}

# Durable CreateNew latch precedes any potential issuer transport.
# Callback is injectable only in an isolated reviewer harness; no production
# transport, credential or issuer is registered in this source-only candidate.
function Invoke-V3PostStopCloudOnceCandidate([string]$LatchPath,
 [byte[]]$PlanBytes,[scriptblock]$Transport) {
 if($null -eq $Transport -or $null -eq $PlanBytes -or
    $PlanBytes.Length -lt 32 -or $PlanBytes.Length -gt 32768 -or
    -not [IO.Path]::IsPathRooted($LatchPath) -or
    [IO.Path]::GetFileName($LatchPath) -cne
      'poststop-f27cce0ba68043b480e4f97698dd2901-attempted') {
  throw 'V3_POSTSTOP_CLOUD_ONCE_SCOPE_HOLD'
 }
 $digest=Get-V3ReleaseSha256 $PlanBytes
 $stream=[IO.File]::Open($LatchPath,[IO.FileMode]::CreateNew,
  [IO.FileAccess]::Write,[IO.FileShare]::None)
 try {
  $mark=[Text.Encoding]::ASCII.GetBytes(
   'V3_POSTSTOP_UNKNOWN_CLOUD_ATTEMPT_V1 '+$digest)
  $stream.Write($mark,0,$mark.Length);$stream.Flush($true)
 } finally {$stream.Dispose()}
 try {& $Transport $PlanBytes}
 catch {throw 'V3_POSTSTOP_CLOUD_DISPATCH_UNKNOWN_NO_RETRY'}
 return [pscustomobject]@{
  kind='V3_POSTSTOP_CLOUD_DISPATCH_RESULT_UNCONFIRMED_V1'
  plan_sha256=$digest
  cloud_terminal_abort_confirmed=$false
  independent_terminal_reader_required=$true
  retry_authorized=$false
  host_terminal_confirmed=$false
  production_authorized=$false
 }
}

# Signed cloud abort cannot be inferred from a successful dispatch.
function Assert-V3PostStopSignedTerminalCloud(
 [byte[]]$Payload,[byte[]]$Cms,[object]$Pins,
 [string]$CurrentCustodyReceiptSha256,[datetimeoffset]$Now=[datetimeoffset]::UtcNow) {
 if($null -eq $Pins -or [string]$CurrentCustodyReceiptSha256 -cnotmatch '^[a-f0-9]{64}$'){
  throw 'V3_POSTSTOP_TERMINAL_PINS_HOLD'
 }
 Assert-V3ReleaseCms -Payload $Payload -Cms $Cms -ReviewedAuthorityCertificateSha256 $Pins.cloud_certificate_sha256
 $row=Read-V3ReleaseJson $Payload
 if([string]$row.kind -cne 'V3_CAS_PREPARED_FENCE_ABORT_READER_RECEIPT_V1' -or
    [string]$row.epoch_id -cne 'V3CAS-AUDIT-f27cce0ba68043b480e4f97698dd2901' -or
    [string]$row.source_sha256 -cne [string]$Pins.source_sha256 -or
    [string]$row.prepared_fence_sha256 -cne [string]$Pins.epoch_fence_sha256 -or
    [string]$row.caller_acl_sha256 -cne [string]$Pins.caller_acl_sha256 -or
    [string]$row.receipt_sha256 -cne $CurrentCustodyReceiptSha256 -or
    [string]$row.state -cne 'ABORT_RECORDED_NOT_RELEASED' -or
    [string]$row.issuer_actor -cne 'v3_cas_inhibit_issuer_actor' -or
    $row.cloud_cas_rpc_count -ne 0 -or
    $row.cloud_executor_can_login -ne $false -or
    $row.cloud_active_series_count -ne 1 -or
    $row.cloud_original_active_series_count -ne 1) {
  throw 'V3_POSTSTOP_TERMINAL_CLOUD_READBACK_HOLD'
 }
 $m=[regex]::Match([Text.Encoding]::UTF8.GetString($Payload),
   '"observed_at_utc"\s*:\s*"(?<time>[^"]+)"')
 try {
  if(-not $m.Success){throw 'missing'}
  $at=[datetimeoffset]::ParseExact($m.Groups['time'].Value,
    "yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'",
    [Globalization.CultureInfo]::InvariantCulture,
    [Globalization.DateTimeStyles]::AssumeUniversal)
 } catch {throw 'V3_POSTSTOP_TERMINAL_CLOUD_TIMESTAMP_HOLD'}
 if($at -gt $Now.AddSeconds(5) -or ($Now-$at).TotalSeconds -gt 60) {
  throw 'V3_POSTSTOP_TERMINAL_CLOUD_STALE_HOLD'
 }
 return [pscustomobject]@{
  kind='V3_POSTSTOP_INDEPENDENT_TERMINAL_CLOUD_VERIFIED_V1'
  epoch_id=[string]$row.epoch_id
  reader_sha256=(Get-V3ReleaseSha256 $Payload)
  terminal_cloud_abort_confirmed=$true
  host_quarantine_confirmed=$false
  historical_stop_success_claimed=$false
  ap05a_authorized=$false
 }
}

# The host quarantine is by preservation of the exact ARMED fence and
# disabled V3 writer. No task mutation, restore, enable or archive is claimed.
function Assert-V3PostStopSignedHostQuarantine(
 [object]$Terminal,[byte[]]$HostPayload,[byte[]]$HostCms,
 [object]$Pins,[datetimeoffset]$Now=[datetimeoffset]::UtcNow) {
 if($null -eq $Terminal -or
    [string]$Terminal.kind -cne 'V3_POSTSTOP_INDEPENDENT_TERMINAL_CLOUD_VERIFIED_V1' -or
    $Terminal.terminal_cloud_abort_confirmed -ne $true -or
    [string]$Terminal.epoch_id -cne [string]$Pins.epoch_id){
  throw 'V3_POSTSTOP_HOST_CLOUD_TERMINAL_FIRST_HOLD'
 }
 Assert-V3ReleaseCms -Payload $HostPayload -Cms $HostCms -ReviewedAuthorityCertificateSha256 $Pins.host_certificate_sha256
 $row=Read-V3ReleaseJson $HostPayload
 if([string]$row.kind -cne 'V3_POSTSTOP_INDEPENDENT_HOST_QUARANTINE_V1' -or
    [string]$row.epoch_id -cne [string]$Pins.epoch_id -or
    [string]$row.series_id -cne [string]$Pins.series_id -or
    [string]$row.terminal_cloud_reader_sha256 -cne [string]$Terminal.reader_sha256 -or
    [string]$row.local_fence_file_sha256 -cne [string]$Pins.local_fence_file_sha256 -or
    [string]$row.fence_phase -cne 'ARMED' -or
    [string]$row.candidates_xml_sha256 -cne [string]$Pins.candidates_xml_sha256 -or
    [string]$row.wait_xml_sha256 -cne [string]$Pins.wait_xml_sha256 -or
    [string]$row.cloudsync_xml_sha256 -cne [string]$Pins.cloudsync_xml_sha256 -or
    [string]$row.writer_xml_sha256 -cne [string]$Pins.writer_xml_sha256 -or
    $row.candidates_enabled -ne $true -or $row.wait_enabled -ne $true -or
    $row.cloudsync_enabled -ne $true -or $row.writer_enabled -ne $false -or
    $row.writer_process_count -ne 0 -or
    $row.other_writer_authorities_closed -ne $true -or
    [string]$row.native_stop_outcome -cne 'UNKNOWN'){
  throw 'V3_POSTSTOP_HOST_QUARANTINE_READBACK_HOLD'
 }
 $m=[regex]::Match([Text.Encoding]::UTF8.GetString($HostPayload),
   '"observed_at_utc"\s*:\s*"(?<time>[^"]+)"')
 try {
  if(-not $m.Success){throw 'missing'}
  $at=[datetimeoffset]::ParseExact($m.Groups['time'].Value,
    "yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'",
    [Globalization.CultureInfo]::InvariantCulture,
    [Globalization.DateTimeStyles]::AssumeUniversal)
 } catch {throw 'V3_POSTSTOP_HOST_QUARANTINE_TIMESTAMP_HOLD'}
 if($at -gt $Now.AddSeconds(5) -or ($Now-$at).TotalSeconds -gt 60){
  throw 'V3_POSTSTOP_HOST_QUARANTINE_STALE_HOLD'
 }
 return [pscustomobject]@{
  kind='V3_POSTSTOP_HOST_QUARANTINE_CUSTODY_VERIFIED_V1'
  epoch_id=[string]$Pins.epoch_id
  terminal_cloud_reader_sha256=[string]$Terminal.reader_sha256
  terminal_host_reader_sha256=(Get-V3ReleaseSha256 $HostPayload)
  quarantine_preserved=$true
  historical_native_stop_success_claimed=$false
  new_writer_authorized=$false
  inhibit_lift_authorized=$false
  ap05a_authorized=$false
 }
}
) {
   throw 'V3_POSTSTOP_CURRENT_RECEIPT_SHA_HOLD'
  }
 }
 $text='V3_POSTSTOP_CURRENT_CUSTODY_RECEIPT_V1|'+
  [string]$Custody.epoch_id+'|'+[string]$Custody.host_payload_sha256+'|'+
  [string]$Custody.cloud_payload_sha256+'|'+[string]$Custody.owner_review_sha256
 return Get-V3ReleaseSha256 ([Text.Encoding]::UTF8.GetBytes($text))
}

# Candidate-only cloud transaction. This source is not imported by the launcher.
# The installed SQL function is already constrained to one terminal abort row.
function Get-V3PostStopCloudAbortCandidate([object]$Custody,[object]$Pins,
 [string]$CurrentCustodyReceiptSha256,[datetimeoffset]$Expiry) {
 if($null -eq $Pins -or $null -eq $Custody -or
    [string]$Custody.kind -cne 'V3_POSTSTOP_CURRENT_CUSTODY_SOURCE_REVIEW_V1' -or
    $Custody.independently_signed_current_custody -ne $true -or
    $Custody.production_authorized -ne $false -or
    [string]$Custody.epoch_id -cne 'V3CAS-AUDIT-f27cce0ba68043b480e4f97698dd2901' -or
    [string]$Custody.series_id -cne 'PAPER-V3-20261111T105211Z' -or
    [string]$Custody.host_payload_sha256 -cne [string]$Pins.host_payload_sha256 -or
    [string]$Custody.cloud_payload_sha256 -cne [string]$Pins.cloud_payload_sha256 -or
    [string]$Custody.source_sha256 -cne [string]$Pins.source_sha256 -or
    [string]$Custody.epoch_fence_sha256 -cne [string]$Pins.epoch_fence_sha256 -or
    [string]$Custody.caller_acl_sha256 -cne [string]$Pins.caller_acl_sha256 -or
    [string]$CurrentCustodyReceiptSha256 -cnotmatch '^[a-f0-9]{64}$' -or
    $Expiry -le [datetimeoffset]::UtcNow -or
    $Expiry -gt [datetimeoffset]::UtcNow.AddMinutes(2)) {
  throw 'V3_POSTSTOP_CLOUD_CANDIDATE_PRECONDITION_HOLD'
 }
 foreach($key in @('source_sha256','epoch_fence_sha256','caller_acl_sha256')) {
  if([string]$Pins.$key -cnotmatch '^[a-f0-9]{64}$') {
   throw 'V3_POSTSTOP_CLOUD_CANDIDATE_PIN_HOLD'
  }
 }
 $until=$Expiry.ToUniversalTime().ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
 $sql=@(
  'BEGIN;'
  "SET LOCAL statement_timeout='15s';"
  "SET LOCAL lock_timeout='5s';"
  'DO $poststop$'
  'BEGIN'
  " IF session_user <> 'v3_cas_inhibit_issuer_actor' OR clock_timestamp() >= '$until'::timestamptz THEN"
  "  RAISE EXCEPTION 'V3_POSTSTOP_OWNER_OR_WINDOW_HOLD';"
  ' END IF;'
  'END $poststop$;'
  'SELECT v3_cas_audit.record_prepared_fence_abort_v1('
  " 'V3CAS-AUDIT-f27cce0ba68043b480e4f97698dd2901',"
  " '$($Pins.source_sha256)',"
  " '$($Pins.epoch_fence_sha256)',"
  " '$($Pins.caller_acl_sha256)',"
  " '$CurrentCustodyReceiptSha256');"
  'COMMIT;' ) -join [Environment]::NewLine
 # The expiry is an independently admitted maximum deadline, NOT a waiver.
 # This builder is SOURCE ONLY; effectful caller must check expiry inside DB
 # against the same bound clock before invoking this SQL.
 return [pscustomobject]@{
  kind='V3_POSTSTOP_CLOUD_ABORT_SQL_CANDIDATE_V1'
  epoch_id=[string]$Custody.epoch_id
  series_id=[string]$Custody.series_id
  admission_expires_at_utc=$until
  sql=$sql
  execution_authorized=$false
  stop_success_claimed=$false
  terminal_readback_required=$true
 }
}

# Durable CreateNew latch precedes any potential issuer transport.
# Callback is injectable only in an isolated reviewer harness; no production
# transport, credential or issuer is registered in this source-only candidate.
function Invoke-V3PostStopCloudOnceCandidate([string]$LatchPath,
 [byte[]]$PlanBytes,[scriptblock]$Transport) {
 if($null -eq $Transport -or $null -eq $PlanBytes -or
    $PlanBytes.Length -lt 32 -or $PlanBytes.Length -gt 32768 -or
    -not [IO.Path]::IsPathRooted($LatchPath) -or
    [IO.Path]::GetFileName($LatchPath) -cne
      'poststop-f27cce0ba68043b480e4f97698dd2901-attempted') {
  throw 'V3_POSTSTOP_CLOUD_ONCE_SCOPE_HOLD'
 }
 $digest=Get-V3ReleaseSha256 $PlanBytes
 $stream=[IO.File]::Open($LatchPath,[IO.FileMode]::CreateNew,
  [IO.FileAccess]::Write,[IO.FileShare]::None)
 try {
  $mark=[Text.Encoding]::ASCII.GetBytes(
   'V3_POSTSTOP_UNKNOWN_CLOUD_ATTEMPT_V1 '+$digest)
  $stream.Write($mark,0,$mark.Length);$stream.Flush($true)
 } finally {$stream.Dispose()}
 try {& $Transport $PlanBytes}
 catch {throw 'V3_POSTSTOP_CLOUD_DISPATCH_UNKNOWN_NO_RETRY'}
 return [pscustomobject]@{
  kind='V3_POSTSTOP_CLOUD_DISPATCH_RESULT_UNCONFIRMED_V1'
  plan_sha256=$digest
  cloud_terminal_abort_confirmed=$false
  independent_terminal_reader_required=$true
  retry_authorized=$false
  host_terminal_confirmed=$false
  production_authorized=$false
 }
}

# Signed cloud abort cannot be inferred from a successful dispatch.
function Assert-V3PostStopSignedTerminalCloud(
 [byte[]]$Payload,[byte[]]$Cms,[object]$Pins,
 [string]$CurrentCustodyReceiptSha256,[datetimeoffset]$Now=[datetimeoffset]::UtcNow) {
 if($null -eq $Pins -or [string]$CurrentCustodyReceiptSha256 -cnotmatch '^[a-f0-9]{64}$'){
  throw 'V3_POSTSTOP_TERMINAL_PINS_HOLD'
 }
 Assert-V3ReleaseCms -Payload $Payload -Cms $Cms -ReviewedAuthorityCertificateSha256 $Pins.cloud_certificate_sha256
 $row=Read-V3ReleaseJson $Payload
 if([string]$row.kind -cne 'V3_CAS_PREPARED_FENCE_ABORT_READER_RECEIPT_V1' -or
    [string]$row.epoch_id -cne 'V3CAS-AUDIT-f27cce0ba68043b480e4f97698dd2901' -or
    [string]$row.source_sha256 -cne [string]$Pins.source_sha256 -or
    [string]$row.prepared_fence_sha256 -cne [string]$Pins.epoch_fence_sha256 -or
    [string]$row.caller_acl_sha256 -cne [string]$Pins.caller_acl_sha256 -or
    [string]$row.receipt_sha256 -cne $CurrentCustodyReceiptSha256 -or
    [string]$row.state -cne 'ABORT_RECORDED_NOT_RELEASED' -or
    [string]$row.issuer_actor -cne 'v3_cas_inhibit_issuer_actor' -or
    $row.cloud_cas_rpc_count -ne 0 -or
    $row.cloud_executor_can_login -ne $false -or
    $row.cloud_active_series_count -ne 1 -or
    $row.cloud_original_active_series_count -ne 1) {
  throw 'V3_POSTSTOP_TERMINAL_CLOUD_READBACK_HOLD'
 }
 $m=[regex]::Match([Text.Encoding]::UTF8.GetString($Payload),
   '"observed_at_utc"\s*:\s*"(?<time>[^"]+)"')
 try {
  if(-not $m.Success){throw 'missing'}
  $at=[datetimeoffset]::ParseExact($m.Groups['time'].Value,
    "yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'",
    [Globalization.CultureInfo]::InvariantCulture,
    [Globalization.DateTimeStyles]::AssumeUniversal)
 } catch {throw 'V3_POSTSTOP_TERMINAL_CLOUD_TIMESTAMP_HOLD'}
 if($at -gt $Now.AddSeconds(5) -or ($Now-$at).TotalSeconds -gt 60) {
  throw 'V3_POSTSTOP_TERMINAL_CLOUD_STALE_HOLD'
 }
 return [pscustomobject]@{
  kind='V3_POSTSTOP_INDEPENDENT_TERMINAL_CLOUD_VERIFIED_V1'
  epoch_id=[string]$row.epoch_id
  reader_sha256=(Get-V3ReleaseSha256 $Payload)
  terminal_cloud_abort_confirmed=$true
  host_quarantine_confirmed=$false
  historical_stop_success_claimed=$false
  ap05a_authorized=$false
 }
}

# The host quarantine is by preservation of the exact ARMED fence and
# disabled V3 writer. No task mutation, restore, enable or archive is claimed.
function Assert-V3PostStopSignedHostQuarantine(
 [object]$Terminal,[byte[]]$HostPayload,[byte[]]$HostCms,
 [object]$Pins,[datetimeoffset]$Now=[datetimeoffset]::UtcNow) {
 if($null -eq $Terminal -or
    [string]$Terminal.kind -cne 'V3_POSTSTOP_INDEPENDENT_TERMINAL_CLOUD_VERIFIED_V1' -or
    $Terminal.terminal_cloud_abort_confirmed -ne $true -or
    [string]$Terminal.epoch_id -cne [string]$Pins.epoch_id){
  throw 'V3_POSTSTOP_HOST_CLOUD_TERMINAL_FIRST_HOLD'
 }
 Assert-V3ReleaseCms -Payload $HostPayload -Cms $HostCms -ReviewedAuthorityCertificateSha256 $Pins.host_certificate_sha256
 $row=Read-V3ReleaseJson $HostPayload
 if([string]$row.kind -cne 'V3_POSTSTOP_INDEPENDENT_HOST_QUARANTINE_V1' -or
    [string]$row.epoch_id -cne [string]$Pins.epoch_id -or
    [string]$row.series_id -cne [string]$Pins.series_id -or
    [string]$row.terminal_cloud_reader_sha256 -cne [string]$Terminal.reader_sha256 -or
    [string]$row.local_fence_file_sha256 -cne [string]$Pins.local_fence_file_sha256 -or
    [string]$row.fence_phase -cne 'ARMED' -or
    [string]$row.candidates_xml_sha256 -cne [string]$Pins.candidates_xml_sha256 -or
    [string]$row.wait_xml_sha256 -cne [string]$Pins.wait_xml_sha256 -or
    [string]$row.cloudsync_xml_sha256 -cne [string]$Pins.cloudsync_xml_sha256 -or
    [string]$row.writer_xml_sha256 -cne [string]$Pins.writer_xml_sha256 -or
    $row.candidates_enabled -ne $true -or $row.wait_enabled -ne $true -or
    $row.cloudsync_enabled -ne $true -or $row.writer_enabled -ne $false -or
    $row.writer_process_count -ne 0 -or
    $row.other_writer_authorities_closed -ne $true -or
    [string]$row.native_stop_outcome -cne 'UNKNOWN'){
  throw 'V3_POSTSTOP_HOST_QUARANTINE_READBACK_HOLD'
 }
 $m=[regex]::Match([Text.Encoding]::UTF8.GetString($HostPayload),
   '"observed_at_utc"\s*:\s*"(?<time>[^"]+)"')
 try {
  if(-not $m.Success){throw 'missing'}
  $at=[datetimeoffset]::ParseExact($m.Groups['time'].Value,
    "yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'",
    [Globalization.CultureInfo]::InvariantCulture,
    [Globalization.DateTimeStyles]::AssumeUniversal)
 } catch {throw 'V3_POSTSTOP_HOST_QUARANTINE_TIMESTAMP_HOLD'}
 if($at -gt $Now.AddSeconds(5) -or ($Now-$at).TotalSeconds -gt 60){
  throw 'V3_POSTSTOP_HOST_QUARANTINE_STALE_HOLD'
 }
 return [pscustomobject]@{
  kind='V3_POSTSTOP_HOST_QUARANTINE_CUSTODY_VERIFIED_V1'
  epoch_id=[string]$Pins.epoch_id
  terminal_cloud_reader_sha256=[string]$Terminal.reader_sha256
  terminal_host_reader_sha256=(Get-V3ReleaseSha256 $HostPayload)
  quarantine_preserved=$true
  historical_native_stop_success_claimed=$false
  new_writer_authorized=$false
  inhibit_lift_authorized=$false
  ap05a_authorized=$false
 }
}
 -or
    [string]$CurrentCustodyReceiptSha256 -cne (Get-V3PostStopCurrentCustodyReceiptSha256 $Custody) -or
    $Expiry -le [datetimeoffset]::UtcNow -or
    $Expiry -gt [datetimeoffset]::UtcNow.AddMinutes(2)) {
  throw 'V3_POSTSTOP_CLOUD_CANDIDATE_PRECONDITION_HOLD'
 }
 foreach($key in @('source_sha256','epoch_fence_sha256','caller_acl_sha256')) {
  if([string]$Pins.$key -cnotmatch '^[a-f0-9]{64}$') {
   throw 'V3_POSTSTOP_CLOUD_CANDIDATE_PIN_HOLD'
  }
 }
 $until=$Expiry.ToUniversalTime().ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
 $sql=@(
  'BEGIN;'
  "SET LOCAL statement_timeout='15s';"
  "SET LOCAL lock_timeout='5s';"
  'DO $poststop$'
  'BEGIN'
  " IF session_user <> 'v3_cas_inhibit_issuer_actor' OR clock_timestamp() >= '$until'::timestamptz THEN"
  "  RAISE EXCEPTION 'V3_POSTSTOP_OWNER_OR_WINDOW_HOLD';"
  ' END IF;'
  'END $poststop$;'
  'SELECT v3_cas_audit.record_prepared_fence_abort_v1('
  " 'V3CAS-AUDIT-f27cce0ba68043b480e4f97698dd2901',"
  " '$($Pins.source_sha256)',"
  " '$($Pins.epoch_fence_sha256)',"
  " '$($Pins.caller_acl_sha256)',"
  " '$CurrentCustodyReceiptSha256');"
  'COMMIT;' ) -join [Environment]::NewLine
 # The expiry is an independently admitted maximum deadline, NOT a waiver.
 # This builder is SOURCE ONLY; effectful caller must check expiry inside DB
 # against the same bound clock before invoking this SQL.
 return [pscustomobject]@{
  kind='V3_POSTSTOP_CLOUD_ABORT_SQL_CANDIDATE_V1'
  epoch_id=[string]$Custody.epoch_id
  series_id=[string]$Custody.series_id
  admission_expires_at_utc=$until
  sql=$sql
  execution_authorized=$false
  stop_success_claimed=$false
  terminal_readback_required=$true
 }
}

# Durable CreateNew latch precedes any potential issuer transport.
# Callback is injectable only in an isolated reviewer harness; no production
# transport, credential or issuer is registered in this source-only candidate.
function Invoke-V3PostStopCloudOnceCandidate([string]$LatchPath,
 [byte[]]$PlanBytes,[scriptblock]$Transport) {
 if($null -eq $Transport -or $null -eq $PlanBytes -or
    $PlanBytes.Length -lt 32 -or $PlanBytes.Length -gt 32768 -or
    -not [IO.Path]::IsPathRooted($LatchPath) -or
    [IO.Path]::GetFileName($LatchPath) -cne
      'poststop-f27cce0ba68043b480e4f97698dd2901-attempted') {
  throw 'V3_POSTSTOP_CLOUD_ONCE_SCOPE_HOLD'
 }
 $digest=Get-V3ReleaseSha256 $PlanBytes
 $stream=[IO.File]::Open($LatchPath,[IO.FileMode]::CreateNew,
  [IO.FileAccess]::Write,[IO.FileShare]::None)
 try {
  $mark=[Text.Encoding]::ASCII.GetBytes(
   'V3_POSTSTOP_UNKNOWN_CLOUD_ATTEMPT_V1 '+$digest)
  $stream.Write($mark,0,$mark.Length);$stream.Flush($true)
 } finally {$stream.Dispose()}
 try {& $Transport $PlanBytes}
 catch {throw 'V3_POSTSTOP_CLOUD_DISPATCH_UNKNOWN_NO_RETRY'}
 return [pscustomobject]@{
  kind='V3_POSTSTOP_CLOUD_DISPATCH_RESULT_UNCONFIRMED_V1'
  plan_sha256=$digest
  cloud_terminal_abort_confirmed=$false
  independent_terminal_reader_required=$true
  retry_authorized=$false
  host_terminal_confirmed=$false
  production_authorized=$false
 }
}

# Signed cloud abort cannot be inferred from a successful dispatch.
function Assert-V3PostStopSignedTerminalCloud(
 [byte[]]$Payload,[byte[]]$Cms,[object]$Pins,
 [string]$CurrentCustodyReceiptSha256,[datetimeoffset]$Now=[datetimeoffset]::UtcNow) {
 if($null -eq $Pins -or [string]$CurrentCustodyReceiptSha256 -cnotmatch '^[a-f0-9]{64}$'){
  throw 'V3_POSTSTOP_TERMINAL_PINS_HOLD'
 }
 Assert-V3ReleaseCms -Payload $Payload -Cms $Cms -ReviewedAuthorityCertificateSha256 $Pins.cloud_certificate_sha256
 $row=Read-V3ReleaseJson $Payload
 if([string]$row.kind -cne 'V3_CAS_PREPARED_FENCE_ABORT_READER_RECEIPT_V1' -or
    [string]$row.epoch_id -cne 'V3CAS-AUDIT-f27cce0ba68043b480e4f97698dd2901' -or
    [string]$row.source_sha256 -cne [string]$Pins.source_sha256 -or
    [string]$row.prepared_fence_sha256 -cne [string]$Pins.epoch_fence_sha256 -or
    [string]$row.caller_acl_sha256 -cne [string]$Pins.caller_acl_sha256 -or
    [string]$row.receipt_sha256 -cne $CurrentCustodyReceiptSha256 -or
    [string]$row.state -cne 'ABORT_RECORDED_NOT_RELEASED' -or
    [string]$row.issuer_actor -cne 'v3_cas_inhibit_issuer_actor' -or
    $row.cloud_cas_rpc_count -ne 0 -or
    $row.cloud_executor_can_login -ne $false -or
    $row.cloud_active_series_count -ne 1 -or
    $row.cloud_original_active_series_count -ne 1) {
  throw 'V3_POSTSTOP_TERMINAL_CLOUD_READBACK_HOLD'
 }
 $m=[regex]::Match([Text.Encoding]::UTF8.GetString($Payload),
   '"observed_at_utc"\s*:\s*"(?<time>[^"]+)"')
 try {
  if(-not $m.Success){throw 'missing'}
  $at=[datetimeoffset]::ParseExact($m.Groups['time'].Value,
    "yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'",
    [Globalization.CultureInfo]::InvariantCulture,
    [Globalization.DateTimeStyles]::AssumeUniversal)
 } catch {throw 'V3_POSTSTOP_TERMINAL_CLOUD_TIMESTAMP_HOLD'}
 if($at -gt $Now.AddSeconds(5) -or ($Now-$at).TotalSeconds -gt 60) {
  throw 'V3_POSTSTOP_TERMINAL_CLOUD_STALE_HOLD'
 }
 return [pscustomobject]@{
  kind='V3_POSTSTOP_INDEPENDENT_TERMINAL_CLOUD_VERIFIED_V1'
  epoch_id=[string]$row.epoch_id
  reader_sha256=(Get-V3ReleaseSha256 $Payload)
  terminal_cloud_abort_confirmed=$true
  host_quarantine_confirmed=$false
  historical_stop_success_claimed=$false
  ap05a_authorized=$false
 }
}

# The host quarantine is by preservation of the exact ARMED fence and
# disabled V3 writer. No task mutation, restore, enable or archive is claimed.
function Assert-V3PostStopSignedHostQuarantine(
 [object]$Terminal,[byte[]]$HostPayload,[byte[]]$HostCms,
 [object]$Pins,[datetimeoffset]$Now=[datetimeoffset]::UtcNow) {
 if($null -eq $Terminal -or
    [string]$Terminal.kind -cne 'V3_POSTSTOP_INDEPENDENT_TERMINAL_CLOUD_VERIFIED_V1' -or
    $Terminal.terminal_cloud_abort_confirmed -ne $true -or
    [string]$Terminal.epoch_id -cne [string]$Pins.epoch_id){
  throw 'V3_POSTSTOP_HOST_CLOUD_TERMINAL_FIRST_HOLD'
 }
 Assert-V3ReleaseCms -Payload $HostPayload -Cms $HostCms -ReviewedAuthorityCertificateSha256 $Pins.host_certificate_sha256
 $row=Read-V3ReleaseJson $HostPayload
 if([string]$row.kind -cne 'V3_POSTSTOP_INDEPENDENT_HOST_QUARANTINE_V1' -or
    [string]$row.epoch_id -cne [string]$Pins.epoch_id -or
    [string]$row.series_id -cne [string]$Pins.series_id -or
    [string]$row.terminal_cloud_reader_sha256 -cne [string]$Terminal.reader_sha256 -or
    [string]$row.local_fence_file_sha256 -cne [string]$Pins.local_fence_file_sha256 -or
    [string]$row.fence_phase -cne 'ARMED' -or
    [string]$row.candidates_xml_sha256 -cne [string]$Pins.candidates_xml_sha256 -or
    [string]$row.wait_xml_sha256 -cne [string]$Pins.wait_xml_sha256 -or
    [string]$row.cloudsync_xml_sha256 -cne [string]$Pins.cloudsync_xml_sha256 -or
    [string]$row.writer_xml_sha256 -cne [string]$Pins.writer_xml_sha256 -or
    $row.candidates_enabled -ne $true -or $row.wait_enabled -ne $true -or
    $row.cloudsync_enabled -ne $true -or $row.writer_enabled -ne $false -or
    $row.writer_process_count -ne 0 -or
    $row.other_writer_authorities_closed -ne $true -or
    [string]$row.native_stop_outcome -cne 'UNKNOWN'){
  throw 'V3_POSTSTOP_HOST_QUARANTINE_READBACK_HOLD'
 }
 $m=[regex]::Match([Text.Encoding]::UTF8.GetString($HostPayload),
   '"observed_at_utc"\s*:\s*"(?<time>[^"]+)"')
 try {
  if(-not $m.Success){throw 'missing'}
  $at=[datetimeoffset]::ParseExact($m.Groups['time'].Value,
    "yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'",
    [Globalization.CultureInfo]::InvariantCulture,
    [Globalization.DateTimeStyles]::AssumeUniversal)
 } catch {throw 'V3_POSTSTOP_HOST_QUARANTINE_TIMESTAMP_HOLD'}
 if($at -gt $Now.AddSeconds(5) -or ($Now-$at).TotalSeconds -gt 60){
  throw 'V3_POSTSTOP_HOST_QUARANTINE_STALE_HOLD'
 }
 return [pscustomobject]@{
  kind='V3_POSTSTOP_HOST_QUARANTINE_CUSTODY_VERIFIED_V1'
  epoch_id=[string]$Pins.epoch_id
  terminal_cloud_reader_sha256=[string]$Terminal.reader_sha256
  terminal_host_reader_sha256=(Get-V3ReleaseSha256 $HostPayload)
  quarantine_preserved=$true
  historical_native_stop_success_claimed=$false
  new_writer_authorized=$false
  inhibit_lift_authorized=$false
  ap05a_authorized=$false
 }
}
) {
   throw 'V3_POSTSTOP_CURRENT_RECEIPT_SHA_HOLD'
  }
 }
 $text='V3_POSTSTOP_CURRENT_CUSTODY_RECEIPT_V1|'+
  [string]$Custody.epoch_id+'|'+[string]$Custody.host_payload_sha256+'|'+
  [string]$Custody.cloud_payload_sha256+'|'+[string]$Custody.owner_review_sha256
 return Get-V3ReleaseSha256 ([Text.Encoding]::UTF8.GetBytes($text))
}

# Candidate-only cloud transaction. This source is not imported by the launcher.
# The installed SQL function is already constrained to one terminal abort row.
function Get-V3PostStopCloudAbortCandidate([object]$Custody,[object]$Pins,
 [string]$CurrentCustodyReceiptSha256,[datetimeoffset]$Expiry) {
 if($null -eq $Pins -or $null -eq $Custody -or
    [string]$Custody.kind -cne 'V3_POSTSTOP_CURRENT_CUSTODY_SOURCE_REVIEW_V1' -or
    $Custody.independently_signed_current_custody -ne $true -or
    $Custody.production_authorized -ne $false -or
    [string]$Custody.epoch_id -cne 'V3CAS-AUDIT-f27cce0ba68043b480e4f97698dd2901' -or
    [string]$Custody.series_id -cne 'PAPER-V3-20261111T105211Z' -or
    [string]$Custody.host_payload_sha256 -cne [string]$Pins.host_payload_sha256 -or
    [string]$Custody.cloud_payload_sha256 -cne [string]$Pins.cloud_payload_sha256 -or
    [string]$Custody.source_sha256 -cne [string]$Pins.source_sha256 -or
    [string]$Custody.epoch_fence_sha256 -cne [string]$Pins.epoch_fence_sha256 -or
    [string]$Custody.caller_acl_sha256 -cne [string]$Pins.caller_acl_sha256 -or
    [string]$CurrentCustodyReceiptSha256 -cnotmatch '^[a-f0-9]{64}$' -or
    $Expiry -le [datetimeoffset]::UtcNow -or
    $Expiry -gt [datetimeoffset]::UtcNow.AddMinutes(2)) {
  throw 'V3_POSTSTOP_CLOUD_CANDIDATE_PRECONDITION_HOLD'
 }
 foreach($key in @('source_sha256','epoch_fence_sha256','caller_acl_sha256')) {
  if([string]$Pins.$key -cnotmatch '^[a-f0-9]{64}$') {
   throw 'V3_POSTSTOP_CLOUD_CANDIDATE_PIN_HOLD'
  }
 }
 $until=$Expiry.ToUniversalTime().ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
 $sql=@(
  'BEGIN;'
  "SET LOCAL statement_timeout='15s';"
  "SET LOCAL lock_timeout='5s';"
  'DO $poststop$'
  'BEGIN'
  " IF session_user <> 'v3_cas_inhibit_issuer_actor' OR clock_timestamp() >= '$until'::timestamptz THEN"
  "  RAISE EXCEPTION 'V3_POSTSTOP_OWNER_OR_WINDOW_HOLD';"
  ' END IF;'
  'END $poststop$;'
  'SELECT v3_cas_audit.record_prepared_fence_abort_v1('
  " 'V3CAS-AUDIT-f27cce0ba68043b480e4f97698dd2901',"
  " '$($Pins.source_sha256)',"
  " '$($Pins.epoch_fence_sha256)',"
  " '$($Pins.caller_acl_sha256)',"
  " '$CurrentCustodyReceiptSha256');"
  'COMMIT;' ) -join [Environment]::NewLine
 # The expiry is an independently admitted maximum deadline, NOT a waiver.
 # This builder is SOURCE ONLY; effectful caller must check expiry inside DB
 # against the same bound clock before invoking this SQL.
 return [pscustomobject]@{
  kind='V3_POSTSTOP_CLOUD_ABORT_SQL_CANDIDATE_V1'
  epoch_id=[string]$Custody.epoch_id
  series_id=[string]$Custody.series_id
  admission_expires_at_utc=$until
  sql=$sql
  execution_authorized=$false
  stop_success_claimed=$false
  terminal_readback_required=$true
 }
}

# Durable CreateNew latch precedes any potential issuer transport.
# Callback is injectable only in an isolated reviewer harness; no production
# transport, credential or issuer is registered in this source-only candidate.
function Invoke-V3PostStopCloudOnceCandidate([string]$LatchPath,
 [byte[]]$PlanBytes,[scriptblock]$Transport) {
 if($null -eq $Transport -or $null -eq $PlanBytes -or
    $PlanBytes.Length -lt 32 -or $PlanBytes.Length -gt 32768 -or
    -not [IO.Path]::IsPathRooted($LatchPath) -or
    [IO.Path]::GetFileName($LatchPath) -cne
      'poststop-f27cce0ba68043b480e4f97698dd2901-attempted') {
  throw 'V3_POSTSTOP_CLOUD_ONCE_SCOPE_HOLD'
 }
 $digest=Get-V3ReleaseSha256 $PlanBytes
 $stream=[IO.File]::Open($LatchPath,[IO.FileMode]::CreateNew,
  [IO.FileAccess]::Write,[IO.FileShare]::None)
 try {
  $mark=[Text.Encoding]::ASCII.GetBytes(
   'V3_POSTSTOP_UNKNOWN_CLOUD_ATTEMPT_V1 '+$digest)
  $stream.Write($mark,0,$mark.Length);$stream.Flush($true)
 } finally {$stream.Dispose()}
 try {& $Transport $PlanBytes}
 catch {throw 'V3_POSTSTOP_CLOUD_DISPATCH_UNKNOWN_NO_RETRY'}
 return [pscustomobject]@{
  kind='V3_POSTSTOP_CLOUD_DISPATCH_RESULT_UNCONFIRMED_V1'
  plan_sha256=$digest
  cloud_terminal_abort_confirmed=$false
  independent_terminal_reader_required=$true
  retry_authorized=$false
  host_terminal_confirmed=$false
  production_authorized=$false
 }
}

# Signed cloud abort cannot be inferred from a successful dispatch.
function Assert-V3PostStopSignedTerminalCloud(
 [byte[]]$Payload,[byte[]]$Cms,[object]$Pins,
 [string]$CurrentCustodyReceiptSha256,[datetimeoffset]$Now=[datetimeoffset]::UtcNow) {
 if($null -eq $Pins -or [string]$CurrentCustodyReceiptSha256 -cnotmatch '^[a-f0-9]{64}$'){
  throw 'V3_POSTSTOP_TERMINAL_PINS_HOLD'
 }
 Assert-V3ReleaseCms -Payload $Payload -Cms $Cms -ReviewedAuthorityCertificateSha256 $Pins.cloud_certificate_sha256
 $row=Read-V3ReleaseJson $Payload
 if([string]$row.kind -cne 'V3_CAS_PREPARED_FENCE_ABORT_READER_RECEIPT_V1' -or
    [string]$row.epoch_id -cne 'V3CAS-AUDIT-f27cce0ba68043b480e4f97698dd2901' -or
    [string]$row.source_sha256 -cne [string]$Pins.source_sha256 -or
    [string]$row.prepared_fence_sha256 -cne [string]$Pins.epoch_fence_sha256 -or
    [string]$row.caller_acl_sha256 -cne [string]$Pins.caller_acl_sha256 -or
    [string]$row.receipt_sha256 -cne $CurrentCustodyReceiptSha256 -or
    [string]$row.state -cne 'ABORT_RECORDED_NOT_RELEASED' -or
    [string]$row.issuer_actor -cne 'v3_cas_inhibit_issuer_actor' -or
    $row.cloud_cas_rpc_count -ne 0 -or
    $row.cloud_executor_can_login -ne $false -or
    $row.cloud_active_series_count -ne 1 -or
    $row.cloud_original_active_series_count -ne 1) {
  throw 'V3_POSTSTOP_TERMINAL_CLOUD_READBACK_HOLD'
 }
 $m=[regex]::Match([Text.Encoding]::UTF8.GetString($Payload),
   '"observed_at_utc"\s*:\s*"(?<time>[^"]+)"')
 try {
  if(-not $m.Success){throw 'missing'}
  $at=[datetimeoffset]::ParseExact($m.Groups['time'].Value,
    "yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'",
    [Globalization.CultureInfo]::InvariantCulture,
    [Globalization.DateTimeStyles]::AssumeUniversal)
 } catch {throw 'V3_POSTSTOP_TERMINAL_CLOUD_TIMESTAMP_HOLD'}
 if($at -gt $Now.AddSeconds(5) -or ($Now-$at).TotalSeconds -gt 60) {
  throw 'V3_POSTSTOP_TERMINAL_CLOUD_STALE_HOLD'
 }
 return [pscustomobject]@{
  kind='V3_POSTSTOP_INDEPENDENT_TERMINAL_CLOUD_VERIFIED_V1'
  epoch_id=[string]$row.epoch_id
  reader_sha256=(Get-V3ReleaseSha256 $Payload)
  terminal_cloud_abort_confirmed=$true
  host_quarantine_confirmed=$false
  historical_stop_success_claimed=$false
  ap05a_authorized=$false
 }
}

# The host quarantine is by preservation of the exact ARMED fence and
# disabled V3 writer. No task mutation, restore, enable or archive is claimed.
function Assert-V3PostStopSignedHostQuarantine(
 [object]$Terminal,[byte[]]$HostPayload,[byte[]]$HostCms,
 [object]$Pins,[datetimeoffset]$Now=[datetimeoffset]::UtcNow) {
 if($null -eq $Terminal -or
    [string]$Terminal.kind -cne 'V3_POSTSTOP_INDEPENDENT_TERMINAL_CLOUD_VERIFIED_V1' -or
    $Terminal.terminal_cloud_abort_confirmed -ne $true -or
    [string]$Terminal.epoch_id -cne [string]$Pins.epoch_id){
  throw 'V3_POSTSTOP_HOST_CLOUD_TERMINAL_FIRST_HOLD'
 }
 Assert-V3ReleaseCms -Payload $HostPayload -Cms $HostCms -ReviewedAuthorityCertificateSha256 $Pins.host_certificate_sha256
 $row=Read-V3ReleaseJson $HostPayload
 if([string]$row.kind -cne 'V3_POSTSTOP_INDEPENDENT_HOST_QUARANTINE_V1' -or
    [string]$row.epoch_id -cne [string]$Pins.epoch_id -or
    [string]$row.series_id -cne [string]$Pins.series_id -or
    [string]$row.terminal_cloud_reader_sha256 -cne [string]$Terminal.reader_sha256 -or
    [string]$row.local_fence_file_sha256 -cne [string]$Pins.local_fence_file_sha256 -or
    [string]$row.fence_phase -cne 'ARMED' -or
    [string]$row.candidates_xml_sha256 -cne [string]$Pins.candidates_xml_sha256 -or
    [string]$row.wait_xml_sha256 -cne [string]$Pins.wait_xml_sha256 -or
    [string]$row.cloudsync_xml_sha256 -cne [string]$Pins.cloudsync_xml_sha256 -or
    [string]$row.writer_xml_sha256 -cne [string]$Pins.writer_xml_sha256 -or
    $row.candidates_enabled -ne $true -or $row.wait_enabled -ne $true -or
    $row.cloudsync_enabled -ne $true -or $row.writer_enabled -ne $false -or
    $row.writer_process_count -ne 0 -or
    $row.other_writer_authorities_closed -ne $true -or
    [string]$row.native_stop_outcome -cne 'UNKNOWN'){
  throw 'V3_POSTSTOP_HOST_QUARANTINE_READBACK_HOLD'
 }
 $m=[regex]::Match([Text.Encoding]::UTF8.GetString($HostPayload),
   '"observed_at_utc"\s*:\s*"(?<time>[^"]+)"')
 try {
  if(-not $m.Success){throw 'missing'}
  $at=[datetimeoffset]::ParseExact($m.Groups['time'].Value,
    "yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'",
    [Globalization.CultureInfo]::InvariantCulture,
    [Globalization.DateTimeStyles]::AssumeUniversal)
 } catch {throw 'V3_POSTSTOP_HOST_QUARANTINE_TIMESTAMP_HOLD'}
 if($at -gt $Now.AddSeconds(5) -or ($Now-$at).TotalSeconds -gt 60){
  throw 'V3_POSTSTOP_HOST_QUARANTINE_STALE_HOLD'
 }
 return [pscustomobject]@{
  kind='V3_POSTSTOP_HOST_QUARANTINE_CUSTODY_VERIFIED_V1'
  epoch_id=[string]$Pins.epoch_id
  terminal_cloud_reader_sha256=[string]$Terminal.reader_sha256
  terminal_host_reader_sha256=(Get-V3ReleaseSha256 $HostPayload)
  quarantine_preserved=$true
  historical_native_stop_success_claimed=$false
  new_writer_authorized=$false
  inhibit_lift_authorized=$false
  ap05a_authorized=$false
 }
}
