# Build input for the separately reviewable release variant, never dot-source
# this fragment on a host. Public entry is the generated module's ONE owner.
function Test-V3ReleaseSignedTerminalPrestopReceipt(
 [byte[]]$Payload,[byte[]]$Cms,[string]$ReviewedCertSha256,
 [string]$ExpectedEpochId,[string]$ExpectedSourceSha256,
 [string]$ExpectedFenceSha256,[string]$ExpectedAclSha256) {
 # Gate B follows the terminal abort. The original issuer-prestop RPC rightly
 # rejects that state; never rerun it or relax its pre-abort Cloud contract.
 # Reuse actual signed PreparedAbortSignedCurrent bytes, with the stricter
 # existing 30-second STOP deadline. This adapter does not mint a receipt.
 $out=[ordered]@{signed_cloud_row_matches_pre_stop_inhibit=$false;
  continuous_cloud_cas_unknown_custody_proven=$false;
  originalhost_scheduler_exclusion_proven=$false;native_stop_or_restore_authorized=$false}
 $terminal=Test-V3Pr515SignedPreparedAbortReadback -Payload $Payload -Cms $Cms `
  -ReviewedCertSha256 $ReviewedCertSha256 -ExpectedEpochId $ExpectedEpochId `
  -ExpectedSourceSha256 $ExpectedSourceSha256 -ExpectedFenceSha256 $ExpectedFenceSha256 `
  -ExpectedAclSha256 $ExpectedAclSha256
 if($terminal.signed_abort_fields_and_pins_match -ne $true){return [pscustomobject]$out}
 try {
  $wire=[Text.UTF8Encoding]::new($false,$true).GetString($Payload)
  $m=[regex]::Match($wire,'"observed_at_utc"\s*:\s*"(?<t>[^"\\]+)"')
  $at=[datetimeoffset]::ParseExact($m.Groups['t'].Value,"yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'",
   [Globalization.CultureInfo]::InvariantCulture,[Globalization.DateTimeStyles]::AssumeUniversal)
  $age=([datetimeoffset]::UtcNow-$at).TotalSeconds
  if($age -ge -5 -and $age -le 30){$out.signed_cloud_row_matches_pre_stop_inhibit=$true}
 }catch{}
 return [pscustomobject]$out
}

function Assert-V3ReleaseInstalledAbortReadback([string]$Path,[object]$Bindings,[string]$ExpectedSourceSha256) {
 # Installation and host execution have separate immutable release identities.
 # The independent host approval pins BOTH the original receipt bytes and its
 # installation commit; never rewrite the catalog or repeat DDL for a new CLI.
 $bytes=Read-V3ReleaseLocalBytes -Path $Path -MaxBytes 65536
 if([string]$Bindings.install_release_commit -cnotmatch '^[a-f0-9]{40}$' -or
    [string]$Bindings.install_readback_sha256 -cnotmatch '^[a-f0-9]{64}$' -or
    $ExpectedSourceSha256 -cnotmatch '^[a-f0-9]{64}$' -or
    (Get-V3ReleaseSha256 $bytes) -cne [string]$Bindings.install_readback_sha256){
  throw 'V3_RELEASE_INSTALL_READBACK_DRIFT'
 }
 $receipt=([Text.UTF8Encoding]::new($false,$true).GetString($bytes))|ConvertFrom-Json -ErrorAction Stop
 if([string]$receipt.kind -cne 'V3_ONE_TIME_ABORT_INSTALL_READBACK_V1' -or
    $receipt.verified -isnot [bool] -or $receipt.verified -ne $true -or
    [string]$receipt.installation.kind -cne 'V3_ONE_TIME_ABORT_INSTALL_V1' -or
    [string]$receipt.installation.release_commit -cne [string]$Bindings.install_release_commit -or
    [string]$receipt.installation.source_sha256 -cne $ExpectedSourceSha256 -or
    [string]$receipt.installation.release_id -cnotmatch '^V3-ONETIME-[a-f0-9]{32}$' -or
    [string]$receipt.installation.approval_sha256 -cnotmatch '^[a-f0-9]{64}$'){
  throw 'V3_RELEASE_ORIGINAL_INSTALL_READBACK_REQUIRED'
 }
}

function Test-V3ReleaseOriginalhostScope([string]$Root,[string[]]$Tasks) {
 try {
  if($null -eq $script:V3ReleaseContext -or
     [datetimeoffset]::UtcNow -ge $script:V3ReleaseContext.authorization.expires_at -or
     $Root -cne 'C:\Users\ADMIN\Trading' -or
     -not(Test-V3ScopedIntakeTaskSet -Names $Tasks) -or
     $env:COMPUTERNAME -cne 'MINI-PC' -or $env:GITHUB_ACTIONS -eq 'true' -or
     -not [Environment]::UserInteractive){return $false}
  return $true
 }catch{return $false}
}

function Assert-V3ReleaseMutationBoundary([ValidateSet('STOP','RESTORE','ARCHIVE')][string]$Phase) {
 $ctx=$script:V3ReleaseContext
 $a=$ctx.authorization.claims
 $b=$a.bindings
 $reconcile=([string]$a.scope -ceq 'ORIGINALHOST_ABORT_RECONCILE')
 if($reconcile -and $Phase -eq 'STOP'){throw 'V3_RECONCILE_STOP_FORBIDDEN'}
 if(-not(Test-V3ReleaseOriginalhostScope -Root $script:V3ReleaseRoot -Tasks $ctx.tasks)){
  throw 'V3_RELEASE_ORIGINALHOST_AUTHORIZATION_NOT_LIVE'
 }
 # Revalidate actual package bytes and the original signed approval each time,
 # never a serialized authorized=true or an exported caller callback.
 $currentPin=Assert-V3ReleaseAuthorityAdmission -Bytes $ctx.admission_bytes `
  -ExpectedSha256 $ctx.admission_sha256 -ReleaseCommit ([string]$a.release_commit)
 if($currentPin -cne $ctx.authority_pin){throw 'V3_RELEASE_AUTHORITY_ADMISSION_CHANGED'}
 $hashes=Get-V3OneTimeReleaseArtifactInventory -PackageRoot $ctx.package_root
 $null=Assert-V3OneTimeReleaseAuthorization -Payload $ctx.payload -Cms $ctx.cms `
  -ReviewedAuthorityCertificateSha256 $ctx.authority_pin -Scope ([string]$a.scope) `
  -ExpectedReleaseCommit ([string]$a.release_commit) -ExpectedArtifacts $hashes
 if($reconcile){
  Assert-V3ReleaseReconciliationOriginals -Context $ctx
  if($null -ne $ctx.instance_snapshot){
   $current=Read-V3ReleaseContinuingIntakes -Context $ctx -EnabledNames $ctx.enabled_names
   if(($current|ConvertTo-Json -Compress) -cne ($ctx.instance_snapshot|ConvertTo-Json -Compress)){
    throw 'V3_RECONCILE_RUNNING_INSTANCE_REPLACED'
   }
  }
 }
 $terminalPayload=Read-V3ReleaseLocalBytes -Path $ctx.abort_json -MaxBytes 4096
 $terminalCms=Read-V3ReleaseLocalBytes -Path $ctx.abort_cms -MaxBytes 32768
 $abort=Test-V3Pr515SignedPreparedAbortReadback -Payload $terminalPayload -Cms $terminalCms `
  -ReviewedCertSha256 ([string]$b.reader_certificate_sha256) -ExpectedEpochId ([string]$b.epoch_id) `
  -ExpectedSourceSha256 ([string]$b.source_sha256) -ExpectedFenceSha256 ([string]$b.fence_sha256) `
  -ExpectedAclSha256 ([string]$b.caller_acl_sha256)
 if($abort.signed_abort_fields_and_pins_match -ne $true){throw 'V3_RELEASE_FRESH_TERMINAL_ABORT_REQUIRED_NO_REARM'}
 # The terminal row was committed BEFORE STOP. Its append-rejection triggers
 # are the prospective epoch barrier, not a claim of historical CAS NEVER.
 # The independent approval must bind the installed original catalog readback.
 Assert-V3ReleaseInstalledAbortReadback -Path $ctx.catalog_readback -Bindings $b `
  -ExpectedSourceSha256 $hashes['supabase/v3-cas-prepared-fence-abort-INACTIVE.sql']
 Assert-V3ReleaseProtectedTasks -Bindings $b
 $fence=Join-Path $script:V3ReleaseRoot 'State\v3-experimental-paper-old-intake-fence.json'
 if((Get-FileHash -LiteralPath $fence -Algorithm SHA256).Hash.ToLowerInvariant() -cne [string]$b.fence_sha256){
  throw 'V3_RELEASE_ARMED_FENCE_DRIFT'
 }
 # No new STOP after it was attempted. Restore/archive remain within this
 # same in-process session and do not invent replacement kernel handles.
 if($Phase -eq 'STOP'){
  if($ctx.stop_attempted){throw 'V3_RELEASE_STOP_ALREADY_ATTEMPTED'}
  $ctx.stop_attempted=$true
 }
}

function Invoke-V3OneTimeOriginalhostRelease {
 [CmdletBinding()]
 param([string]$PackageRoot,[byte[]]$Approval,[byte[]]$ApprovalCms,
       [byte[]]$AuthorityAdmission,[string]$ExpectedAuthorityAdmissionSha256,[string]$ExpectedReleaseCommit,
       [string]$IssuerPrestopJson,[string]$IssuerPrestopCms,
       [string]$TerminalAbortJson,[string]$TerminalAbortCms,
       [string]$InstallReadbackJson,[string]$BackupDirectory)
 if($null -ne $script:V3ReleaseContext){throw 'V3_RELEASE_SESSION_ALREADY_OWNED'}
 $ReviewedAuthorityCertificateSha256=Assert-V3ReleaseAuthorityAdmission -Bytes $AuthorityAdmission `
  -ExpectedSha256 $ExpectedAuthorityAdmissionSha256 -ReleaseCommit $ExpectedReleaseCommit
 $hashes=Get-V3OneTimeReleaseArtifactInventory -PackageRoot $PackageRoot
 $authorization=Assert-V3OneTimeReleaseAuthorization -Payload $Approval -Cms $ApprovalCms `
  -ReviewedAuthorityCertificateSha256 $ReviewedAuthorityCertificateSha256 -Scope ORIGINALHOST_ABORT_RESTORE `
  -ExpectedReleaseCommit $ExpectedReleaseCommit -ExpectedArtifacts $hashes
 $a=$authorization.claims;$b=$a.bindings
 $fields=@('epoch_id','source_sha256','fence_sha256','caller_acl_sha256','reader_certificate_sha256','reader_source_sha256',
  'pr515_sha256','backup_manifest_sha256','successor_series_id','bundle_sha256','strategy_sha256',
  'candidate_repo_sha','lifecycle_xml_sha256','cloudsync_xml_sha256','v3_writer_xml_sha256',
  'install_readback_sha256','install_release_commit','policy')
 if(@($b.PSObject.Properties).Count -ne $fields.Count -or
    @($b.PSObject.Properties.Name|Where-Object {$_ -cnotin $fields}).Count -or
    [string]$b.policy -cne 'TERMINAL_ABORT_BEFORE_STOP_NO_CAS_V1' -or
    [string]$b.reader_source_sha256 -cne 'c81dbdca986da4fb5143bc1a315cb3b7dd548e0b6f338a02f0992767b6af2ba5' -or
    [string]$b.epoch_id -cnotmatch '^V3CAS-AUDIT-[a-f0-9]{32}$' -or
    [string]$b.candidate_repo_sha -cnotmatch '^[a-f0-9]{40}$' -or
    [string]$b.install_release_commit -cnotmatch '^[a-f0-9]{40}$' -or
    [string]$b.successor_series_id -cnotmatch '^PAPER-V3-[0-9]{8}T[0-9]{6}Z$'){
  throw 'V3_RELEASE_HOST_BINDINGS_HOLD'
 }
 foreach($field in @($fields|Where-Object {$_ -like '*sha256'})){
  if([string]$b.$field -cnotmatch '^[a-f0-9]{64}$'){throw 'V3_RELEASE_HOST_HASH_BINDINGS_HOLD'}
 }
 $script:V3ReleaseRoot='C:\Users\ADMIN\Trading'
 $tasks=@('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait')
 $script:V3ReleaseContext=[pscustomobject]@{
  authorization=$authorization;payload=$Approval;cms=$ApprovalCms;authority_pin=$ReviewedAuthorityCertificateSha256
  admission_bytes=$AuthorityAdmission;admission_sha256=$ExpectedAuthorityAdmissionSha256
  package_root=$PackageRoot;tasks=$tasks;abort_json=$TerminalAbortJson;abort_cms=$TerminalAbortCms
  catalog_readback=$InstallReadbackJson;stop_attempted=$false
 }
 $session=$null;$journal=$null;$packageLease=$null
 try {
  $packageLease=Open-V3ReleasePackageReadLease -PackageRoot $PackageRoot -Inventory $hashes
  if(-not(Test-V3ReleaseOriginalhostScope -Root $script:V3ReleaseRoot -Tasks $tasks)){
   throw 'V3_RELEASE_INTERACTIVE_ORIGINALHOST_ONLY'
  }
  $manifest=Join-Path $BackupDirectory 'backup-manifest.json'
  if((Get-FileHash -LiteralPath $manifest -Algorithm SHA256).Hash.ToLowerInvariant() -cne [string]$b.backup_manifest_sha256){
   throw 'V3_RELEASE_BACKUP_MANIFEST_PIN_HOLD'
  }
  # The existing backup validator further restricts the exact backup location,
  # XML bytes and PR515 source. No new backup or routine baseline test.
  $prestop=Read-V3ReleaseLocalBytes -Path $IssuerPrestopJson -MaxBytes 4096
  $prestopCmsBytes=Read-V3ReleaseLocalBytes -Path $IssuerPrestopCms -MaxBytes 32768
  $issuer=Test-V3ReleaseSignedTerminalPrestopReceipt -Payload $prestop -Cms $prestopCmsBytes `
   -ReviewedCertSha256 ([string]$b.reader_certificate_sha256) -ExpectedEpochId ([string]$b.epoch_id) `
   -ExpectedSourceSha256 ([string]$b.source_sha256) -ExpectedFenceSha256 ([string]$b.fence_sha256) `
   -ExpectedAclSha256 ([string]$b.caller_acl_sha256)
  if($issuer.signed_cloud_row_matches_pre_stop_inhibit -ne $true){throw 'V3_RELEASE_INDEPENDENT_PRESTOP_HOLD'}
  # Check the terminal barrier before creating any one-shot journal or entering
  # the original mutation owner. The STOP boundary rechecks it again.
  Assert-V3ReleaseMutationBoundary -Phase RESTORE
  $journalPath=Join-Path $script:V3ReleaseRoot ('State\v3-one-time-'+[string]$a.release_id+'.json')
  $journal=[IO.File]::Open($journalPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
  $record=[Text.Encoding]::UTF8.GetBytes((@{kind='V3_ONE_TIME_ORIGINALHOST_ATTEMPT_V1';
    release_id=$a.release_id;approval_sha256=$authorization.approval_sha256;epoch_id=$b.epoch_id;
    state='ATTEMPTED_RECONCILIATION_REQUIRED_UNTIL_FINAL_ACK'}|ConvertTo-Json -Compress))
  $journal.Write($record,0,$record.Length);$journal.Flush($true)
  $readiness=Join-Path $PackageRoot 'tools\check-minipc-v3-physical-writer-readiness.ps1'
  $wire=@(& $readiness -TradingRoot $script:V3ReleaseRoot)
  $report=($wire -join "`n")|ConvertFrom-Json -ErrorAction Stop
  $args=@{Root=$script:V3ReleaseRoot;OriginalReadback=$report;BackupFolder=$BackupDirectory;
   ReviewedPr515Sha=[string]$b.pr515_sha256;SuccessorId=[string]$b.successor_series_id;
   ReviewedRepoSha=[string]$b.candidate_repo_sha;ReviewedBundleSha=[string]$b.bundle_sha256;
   ReviewedStrategySha=[string]$b.strategy_sha256;OnlyIssuedNativeStop=$true;CompleteArmedAbortRestore=$true;
   ExpectedPreparedFenceSha=[string]$b.fence_sha256;IndependentIssuerReaderJson=$prestop;
   IndependentIssuerReaderCms=$prestopCmsBytes;ReviewedIssuerReaderCertificateSha256=[string]$b.reader_certificate_sha256;
   ReviewedIssuerEpochId=[string]$b.epoch_id;ReviewedIssuerSourceSha256=[string]$b.source_sha256;
   ReviewedIssuerCallerAclSha256=[string]$b.caller_acl_sha256;IsolatedTaskNames=$tasks;
   TerminalAbortJsonPath=$TerminalAbortJson;TerminalAbortCmsPath=$TerminalAbortCms}
  # Retry only with the SAME live session, never a second STOP. This permits a
  # fresh independent abort readback after a stale file or archive collision.
  do {
   $result=Invoke-V3Pr515ScopedNativeStopSOURCE_ONLY @args
   $session=$result.held_session
   if($null -eq $session){break}
   if(-not(Test-V3Pr661HeldIntakeDefinitionPair -Pair $session.pair -TaskNames $tasks)){throw 'V3_RELEASE_SESSION_HANDLES_CLOSED_RECONCILIATION_REQUIRED'}
   if([datetimeoffset]::UtcNow -ge $authorization.expires_at){throw 'V3_RELEASE_SESSION_EXPIRED_FENCE_PRESERVED'}
   $args.HeldArmedSession=$session
   Start-Sleep -Milliseconds 500
  }while($true)
  if([string]$result.status -cne 'ARMED_STOP_ABORT_RESTORE_AND_AFTERCARE_CONFIRMED'){
   throw 'V3_RELEASE_ORIGINALHOST_FINAL_ACK_NOT_CONFIRMED'
  }
  $finalReceipt=[pscustomobject]@{kind='V3_ONE_TIME_ORIGINALHOST_RELEASE_RECEIPT_V1';
   release_id=$a.release_id;release_commit=$a.release_commit;approval_sha256=$authorization.approval_sha256;
   status='TERMINAL_ABORT_STOP_RESTORE_AFTERCARE_CONFIRMED';cas_or_paper_authorized=$false}
  # Keep the durable attempt latch; add a separate CreateNew original result.
  # A missing completion file never converts UNKNOWN into permission to retry.
  $completion=[IO.File]::Open(($journalPath+'.completed.json'),[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
  try {
   $bytes=[Text.Encoding]::UTF8.GetBytes(($finalReceipt|ConvertTo-Json -Compress))
   $completion.Write($bytes,0,$bytes.Length);$completion.Flush($true)
  }finally{$completion.Dispose()}
  return $finalReceipt
 }finally {
  if($null -ne $journal){$journal.Dispose()}
  # On interruption the durable Disabled tasks and ARMED fence remain. No
  # finally path may rearm or remove them. Closed-process handles are NOT
  # resumable proof: a new process must stop at the durable one-shot journal.
  if($null -ne $session){
   foreach($lease in $session.pair.leases){$lease.readonly_definition_handle.Dispose()}
   try{$session.mutex.ReleaseMutex()}catch{};$session.mutex.Dispose()
  }
  $script:V3ReleaseContext=$null
  foreach($stream in $packageLease){$stream.Dispose()}
 }
}

# One native Enable owner, also used by the original STOP/restore path.
# Calling this helper cannot invent context or choose a third task.
function Enable-V3ReleaseIntakeDefinition([string]$TaskName) {
 Assert-V3ReleaseMutationBoundary -Phase RESTORE
 if($null -eq $script:V3ReleaseContext -or
    $TaskName -cnotin $script:V3ReleaseContext.tasks){throw 'V3_RELEASE_ENABLE_TASK_SCOPE_HOLD'}
 $name=$TaskName
 Enable-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction Stop | Out-Null
}

# Pure identity join. Expiry of the OLD approval is deliberately not renewed:
# it is historical evidence; the separate reconciliation CMS must be live.
function Assert-V3ReleaseReconciliationIdentity(
 [object]$Claims,[object]$Original,[object]$Journal,[object]$Evidence) {
 $b=$Claims.bindings
 $extra=@('journal_sha256','original_approval_sha256','evidence_sha256','reconciliation_policy','post_archive_receipt_sha256','pre_archive_attempt_sha256')
 if([string]$Claims.scope -cne 'ORIGINALHOST_ABORT_RECONCILE' -or
    [string]$b.reconciliation_policy -cne 'ENABLED_ONLY_CONTINUING_ORIGINALS_NO_STOP_V1' -or
    [string]$Original.kind -cne 'V3_ONE_TIME_RELEASE_AUTHORIZATION_V1' -or
    [string]$Original.scope -cne 'ORIGINALHOST_ABORT_RESTORE' -or
    [string]$Original.release_commit -cnotmatch '^[a-f0-9]{40}$' -or
    [string]$Original.release_commit -ceq [string]$Claims.release_commit -or
    [string]$Original.base_commit -cne [string]$Claims.base_commit -or
    [string]$Original.computer_name -cne [string]$Claims.computer_name -or
    [string]$Original.trading_root -cne [string]$Claims.trading_root -or
    [string]$Original.project_ref -cne [string]$Claims.project_ref -or
    [string]$Original.release_id -cne [string]$Claims.release_id -or
    [string]$Journal.kind -cne 'V3_ONE_TIME_ORIGINALHOST_ATTEMPT_V1' -or
    [string]$Journal.state -cne 'ATTEMPTED_RECONCILIATION_REQUIRED_UNTIL_FINAL_ACK' -or
    [string]$Journal.release_id -cne [string]$Claims.release_id -or
    [string]$Journal.approval_sha256 -cne [string]$b.original_approval_sha256 -or
    [string]$Journal.epoch_id -cne [string]$b.epoch_id -or
    @($Original.bindings.PSObject.Properties).Count -ne 18 -or
    (@($b.PSObject.Properties).Count -ne (22+@(@('post_archive_receipt_sha256','pre_archive_attempt_sha256')|Where-Object {$_ -cin @($b.PSObject.Properties.Name)}).Count))){throw 'V3_RECONCILE_IDENTITY_OR_BINDINGS_HOLD'}
 foreach($field in $extra){
  if($field -cin @('post_archive_receipt_sha256','pre_archive_attempt_sha256') -and $field -cnotin @($b.PSObject.Properties.Name)){continue}
  if($field -like '*sha256' -and [string]$b.$field -cnotmatch '^[a-f0-9]{64}$'){
   throw 'V3_RECONCILE_HASH_BINDINGS_HOLD'
  }
 }
 if(@($b.PSObject.Properties.Name|Where-Object {$_ -cnotin (@($Original.bindings.PSObject.Properties.Name)+$extra)}).Count){throw 'V3_RECONCILE_UNKNOWN_BINDING_HOLD'}
 foreach($p in $Original.bindings.PSObject.Properties){
  if($p.Name -cin $extra -or [string]$b.($p.Name) -cne [string]$p.Value -or
     [string]$Evidence.approved_bindings.($p.Name) -cne [string]$p.Value){
   throw 'V3_RECONCILE_ORIGINAL_BINDING_DRIFT'
  }
 }
 if([string]$b.policy -cne 'TERMINAL_ABORT_BEFORE_STOP_NO_CAS_V1' -or
    [string]$b.epoch_id -cnotmatch '^V3CAS-AUDIT-[a-f0-9]{32}$' -or
    [string]$Evidence.kind -cne 'V3_GATE_B_EXISTING_ATTEMPT_READONLY_RECONCILIATION_V1' -or
    [string]$Evidence.release_id -cne [string]$Claims.release_id -or
    $Evidence.native_mutations_performed -ne $false -or $Evidence.gate_b_completed -ne $false -or
    [string]$Evidence.journal.sha256 -cne [string]$b.journal_sha256 -or
    [string]$Evidence.journal.approval_sha256 -cne [string]$b.original_approval_sha256 -or
    $Evidence.journal.completion_present -ne $false -or $Evidence.archive_present -ne $false -or
    $Evidence.fence.present -ne $true -or [string]$Evidence.fence.phase -cne 'ARMED' -or
    [string]$Evidence.fence.sha256 -cne [string]$b.fence_sha256 -or
    $Evidence.original_approval.cms_valid -ne $true -or
    [string]$Evidence.original_approval.release_commit -cne [string]$Original.release_commit){
  throw 'V3_RECONCILE_ORIGINAL_EVIDENCE_HOLD'
 }
 $fields=@('epoch_id','source_sha256','fence_sha256','caller_acl_sha256','reader_certificate_sha256','reader_source_sha256',
  'pr515_sha256','backup_manifest_sha256','successor_series_id','bundle_sha256','strategy_sha256',
  'candidate_repo_sha','lifecycle_xml_sha256','cloudsync_xml_sha256','v3_writer_xml_sha256',
  'install_readback_sha256','install_release_commit','policy')
 if(@($Original.bindings.PSObject.Properties.Name|Where-Object {$_ -cnotin $fields}).Count -or
    @($Original.artifacts.PSObject.Properties).Count -ne 8 -or
    @($Evidence.approved_artifacts.PSObject.Properties).Count -ne 8){throw 'V3_RECONCILE_ORIGINAL_SCOPE_DRIFT'}
 foreach($p in $Original.artifacts.PSObject.Properties){
  if([string]$p.Value -cnotmatch '^[a-f0-9]{64}$' -or
     [string]$Evidence.approved_artifacts.($p.Name) -cne [string]$p.Value){throw 'V3_RECONCILE_ORIGINAL_ARTIFACT_DRIFT'}
 }
 $names=@('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait')
 foreach($name in $names){
  $rows=@($Evidence.tasks|Where-Object {[string]$_.name -ceq $name})
  if($rows.Count -ne 1){throw 'V3_RECONCILE_EVIDENCE_TASK_SCOPE_HOLD'}
  $row=$rows[0]
  if($row.enabled -ne $false -or [string]$row.state -cne 'Running' -or
     [int]$row.running_instances -ne 1 -or
     [string]$row.effective_config.classification -cne 'ONLY_ENABLED_FIELD_DIFFERS' -or
     $row.effective_config.original_disabled_only_contract_matches -ne $true -or
     @($row.current_matching_processes).Count -lt 1 -or
     @($row.current_matching_processes|Where-Object {$_.created_before_window -ne $true}).Count){
   throw 'V3_RECONCILE_NOT_CONTINUING_ORIGINAL_TASKS'
  }
  $pids=@($row.current_matching_processes|ForEach-Object {[int]$_.pid})
  if(@($pids|Select-Object -Unique).Count -ne $pids.Count -or @($pids|Where-Object {$_ -le 0}).Count){
   throw 'V3_RECONCILE_PROCESS_SCOPE_HOLD'
  }
  foreach($p in $row.current_matching_processes){
   if(([datetimeoffset]$p.created_at_utc) -ge ([datetimeoffset]$Original.not_before_utc)){
    throw 'V3_RECONCILE_PROCESS_NOT_OLDER_THAN_ORIGINAL_WINDOW'
   }
  }
 }
}

function Assert-V3ReleaseReconciliationOriginals([object]$Context) {
 $b=$Context.authorization.claims.bindings
 foreach($entry in @(
   @($Context.journal_path,[string]$b.journal_sha256),
   @($Context.original_approval_path,[string]$b.original_approval_sha256),
   @($Context.evidence_path,[string]$b.evidence_sha256))){
  $bytes=Read-V3ReleaseLocalBytes -Path $entry[0]
  if((Get-V3ReleaseSha256 $bytes) -cne $entry[1]){throw 'V3_RECONCILE_ORIGINAL_BYTES_CHANGED'}
 }
 if(Test-Path -LiteralPath ($Context.journal_path+'.completed.json')){
  throw 'V3_RECONCILE_ALREADY_COMPLETED_NO_REPLAY'
 }
 $journal=Read-V3ReleaseJson (Read-V3ReleaseLocalBytes $Context.journal_path)
 $oldBytes=Read-V3ReleaseLocalBytes $Context.original_approval_path
 Assert-V3ReleaseCms -Payload $oldBytes -Cms (Read-V3ReleaseLocalBytes $Context.original_cms_path -MaxBytes 32768) `
  -ReviewedAuthorityCertificateSha256 $Context.authority_pin
 $old=Read-V3ReleaseJson $oldBytes
 # Evidence is hash-pinned by the independently signed decision, never an
 # unsigned caller authorized=true flag. Its nested repeated names are valid.
 $evidence=[Text.UTF8Encoding]::new($false,$true).GetString(
  (Read-V3ReleaseLocalBytes $Context.evidence_path))|ConvertFrom-Json -ErrorAction Stop
 Assert-V3ReleaseReconciliationIdentity -Claims $Context.authorization.claims -Original $old `
  -Journal $journal -Evidence $evidence
}

# Local live state is separate from the independently approved historical
# evidence. Running is NOT the same field as Enabled. No Stop/Start/kill here.
function Read-V3ReleaseContinuingIntakes([object]$Context,[string[]]$EnabledNames=@()) {
 $b=$Context.authorization.claims.bindings
 $manifestBytes=Read-V3ReleaseLocalBytes (Join-Path $Context.backup_root 'backup-manifest.json')
 if((Get-V3ReleaseSha256 $manifestBytes) -cne [string]$b.backup_manifest_sha256){throw 'V3_RECONCILE_BACKUP_DRIFT'}
 $manifest=[Text.Encoding]::UTF8.GetString($manifestBytes)|ConvertFrom-Json -ErrorAction Stop
 if(-not(Test-V3Pr515CurrentOriginalBackupManifest $manifest) -or
    [string]$manifest.backup_directory -cne $Context.backup_root){throw 'V3_RECONCILE_BACKUP_SCOPE_HOLD'}
 $service=New-Object -ComObject 'Schedule.Service';$service.Connect()
 $processes=@(Get-CimInstance -Query "SELECT ProcessId,ParentProcessId,Name,CreationDate,CommandLine FROM Win32_Process WHERE Name='python.exe' OR Name='pythonw.exe'" -ErrorAction Stop)
 $snapshot=@()
 foreach($name in $Context.tasks){
  $row=@($Context.evidence.tasks|Where-Object {[string]$_.name -ceq $name})[0]
  $record=@($manifest.task_records|Where-Object {[string]$_.task_name -ceq $name})[0]
  $savedBytes=Read-V3ReleaseLocalBytes (Join-Path $Context.backup_root $record.xml_file) -MaxBytes 131072
  if((Get-V3ReleaseSha256 $savedBytes) -cne [string]$record.xml_sha256 -or
     [string]$record.xml_sha256 -cne [string]$row.saved_xml_sha256){throw 'V3_RECONCILE_BACKUP_XML_DRIFT'}
  $saved=[Text.UTF8Encoding]::new($false,$true).GetString($savedBytes)
  $savedDocument=[xml]$saved
  $policies=@($savedDocument.SelectNodes('/*[local-name()="Task"]/*[local-name()="Settings"]/*[local-name()="MultipleInstancesPolicy"]'))
  # Scheduler's default is IgnoreNew. Parallel, Queue and StopExisting cannot
  # guarantee that enabling preserves the sole original instance.
  if($policies.Count -gt 1 -or ($policies.Count -eq 1 -and $policies[0].InnerText -cne 'IgnoreNew')){
   throw 'V3_RECONCILE_TASK_MULTIPLE_INSTANCE_POLICY_HOLD'
  }
  $live=[string](Export-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction Stop)
  $native=$service.GetFolder('\').GetTask($name)
  $shouldEnable=($name -cin $EnabledNames)
  if([bool]$native.Enabled -ne $shouldEnable -or
     [string](Get-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction Stop).State -cne 'Running' -or
     @($native.GetInstances(0)).Count -ne 1){throw 'V3_RECONCILE_LIVE_TASK_STATE_DRIFT'}
  # Enabling must reproduce the original effective definition. Serialize both
  # XML documents uniformly; do not overwrite a task XML to force byte equality.
  if($shouldEnable){
   $old=[xml]$saved;$new=[xml]$live
   $path='/*[local-name()="Task"]/*[local-name()="Settings"]/*[local-name()="Enabled"]'
   foreach($doc in @($old,$new)){
    foreach($node in @($doc.SelectNodes($path))){
     if($node.InnerText.Trim() -cnotin @('true','1')){throw 'V3_RECONCILE_ENABLED_XML_HOLD'}
     [void]$node.ParentNode.RemoveChild($node)
    }
   }
   if($old.OuterXml -cne $new.OuterXml){throw 'V3_RECONCILE_ENABLED_DEFINITION_DRIFT'}
  }elseif(-not(Test-V3Pr515DisabledOnlyXmlDifference -Saved $saved -Disabled $live) -or
     (Get-V3ReleaseSha256 ([Text.Encoding]::UTF8.GetBytes($live))) -cne [string]$row.current_xml_sha256){
   throw 'V3_RECONCILE_DISABLED_DEFINITION_DRIFT'
  }
  # $args is automatic and empty inside Where-Object's scriptblock scope.
  # Capture the actual task arguments under an ordinary lexical variable.
  $taskArguments=([string](Get-ScheduledTask -TaskName $name -TaskPath '\').Actions[0].Arguments).Replace('\','/')
  if($taskArguments.Length -le 10){throw 'V3_RECONCILE_PROCESS_ACTION_HOLD'}
  $matches=@($processes|Where-Object {
   ([string]$_.CommandLine).Replace('\','/').IndexOf($taskArguments,[StringComparison]::OrdinalIgnoreCase) -ge 0
  })
  $expected=@($row.current_matching_processes)
  if($matches.Count -ne $expected.Count){throw 'V3_RECONCILE_PROCESS_COUNT_DRIFT'}
  foreach($p in $expected){
   $current=@($matches|Where-Object {[int]$_.ProcessId -eq [int]$p.pid})
   if($current.Count -ne 1 -or
      $current[0].CreationDate.ToUniversalTime().Ticks -ne ([datetimeoffset]$p.created_at_utc).UtcDateTime.Ticks -or
      [int]$current[0].ParentProcessId -ne [int]$p.parent_pid){throw 'V3_RECONCILE_ORIGINAL_PROCESS_IDENTITY_DRIFT'}
  }
  $instance=@($native.GetInstances(0))[0]
  if([string]$instance.InstanceGuid -cnotmatch '^\{?[a-fA-F0-9]{8}-(?:[a-fA-F0-9]{4}-){3}[a-fA-F0-9]{12}\}?$'){
   throw 'V3_RECONCILE_INSTANCE_IDENTITY_UNKNOWN'
  }
  $snapshot+=@([pscustomobject]@{name=$name;instance_id=[string]$instance.InstanceGuid})
 }
 return ,$snapshot
}

function Read-V3ReleaseReconciliationHeartbeat([string]$Path,[datetimeoffset]$After) {
 $bytes=Read-V3ReleaseLocalBytes $Path
 $wire=[Text.UTF8Encoding]::new($false,$true).GetString($bytes)
 $m=[regex]::Matches($wire,'"checked_at_utc"\s*:\s*"(?<t>[^"\\]+)"')
 if($m.Count -ne 1 -or $m[0].Groups['t'].Value -cnotmatch
    '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,7})?(?:Z|\+00:00)$'){
  throw 'V3_RECONCILE_HEARTBEAT_TIME_HOLD'
 }
 $at=[datetimeoffset]::Parse($m[0].Groups['t'].Value,[Globalization.CultureInfo]::InvariantCulture)
 $age=([datetimeoffset]::UtcNow-$at).TotalSeconds
 if($at -le $After -or $age -lt -5 -or $age -gt 90){throw 'V3_RECONCILE_HEARTBEAT_STALE_HOLD'}
 $value=$wire|ConvertFrom-Json -ErrorAction Stop
 if([string]$value.status -cne 'HEALTHY'){throw 'V3_RECONCILE_HEARTBEAT_UNHEALTHY'}
 return $value
}

function Wait-V3ReleaseReconciliationHealth([object]$Context,[datetimeoffset]$After,[switch]$AfterArchive) {
 for($i=0;$i -lt 45;$i++){
  if([datetimeoffset]::UtcNow -ge $Context.authorization.expires_at){throw 'V3_RECONCILE_SESSION_EXPIRED_NO_RETRY'}
  try{
   $snapshot=Read-V3ReleaseContinuingIntakes -Context $Context -EnabledNames $Context.tasks
   if(($snapshot|ConvertTo-Json -Compress) -cne ($Context.instance_snapshot|ConvertTo-Json -Compress)){
    throw 'V3_RECONCILE_RUNNING_INSTANCE_REPLACED'
   }
   foreach($leaf in @('v2r4-paper-candidate-runtime-heartbeat.json','v2r4-paper-wait-runtime-heartbeat.json')){
    $null=Read-V3ReleaseReconciliationHeartbeat (Join-Path $script:V3ReleaseRoot ('State\'+$leaf)) $After
   }
   if($AfterArchive){
    $sup=Read-V3ReleaseReconciliationHeartbeat (Join-Path $script:V3ReleaseRoot 'State\minipc-runtime-supervisor.json') $After
    $cloud=Read-V3ReleaseReconciliationHeartbeat (Join-Path $script:V3ReleaseRoot 'State\v2r4-paper-cloud-sync-heartbeat.json') $After
    if([string]$sup.v3_paper_old_intake_fence.mode -cne 'NONE' -or
       [string]$cloud.v3_fence_cloud_sync_lane -cne 'ACTIVE_ORIGINAL' -or
       [string]$cloud.series_id -cne 'PAPER-V2R4-20261009T110135Z'){throw 'V3_RECONCILE_AFTERCARE_NOT_ORIGINAL'}
   }
   return
  }catch{
   # UNKNOWN is never success. Bounded observation only, no mutating retry.
   if($_.Exception.Message -notlike 'V3_RECONCILE_HEARTBEAT*' -and
      $_.Exception.Message -cne 'V3_RECONCILE_AFTERCARE_NOT_ORIGINAL'){throw}
  }
  Start-Sleep -Seconds 4
 }
 throw 'V3_RECONCILE_HEALTH_UNKNOWN_NO_RETRY'
}

function Invoke-V3OneTimeOriginalhostReconciliation {
 [CmdletBinding()]
 param([string]$PackageRoot,[byte[]]$Approval,[byte[]]$ApprovalCms,
  [byte[]]$AuthorityAdmission,[string]$ExpectedAuthorityAdmissionSha256,[string]$ExpectedReleaseCommit,
  [string]$ExistingApprovalJson,[string]$ExistingApprovalCms,[string]$ReconciliationEvidenceJson,
  [string]$InterruptedApprovalJson,[string]$InterruptedApprovalCms,
  [string]$TerminalAbortJson,[string]$TerminalAbortCms,[string]$InstallReadbackJson,[string]$BackupDirectory)
 if($null -ne $script:V3ReleaseContext){throw 'V3_RELEASE_SESSION_ALREADY_OWNED'}
 $pin=Assert-V3ReleaseAuthorityAdmission $AuthorityAdmission $ExpectedAuthorityAdmissionSha256 $ExpectedReleaseCommit
 $inventory=Get-V3OneTimeReleaseArtifactInventory $PackageRoot
 $authorization=Assert-V3OneTimeReleaseAuthorization -Payload $Approval -Cms $ApprovalCms `
  -ReviewedAuthorityCertificateSha256 $pin -Scope ORIGINALHOST_ABORT_RECONCILE `
  -ExpectedReleaseCommit $ExpectedReleaseCommit -ExpectedArtifacts $inventory
 $a=$authorization.claims;$b=$a.bindings
 $script:V3ReleaseRoot='C:\Users\ADMIN\Trading'
 $journalPath=Join-Path $script:V3ReleaseRoot ('State\v3-one-time-'+[string]$a.release_id+'.json')
 $ctx=[pscustomobject]@{authorization=$authorization;payload=$Approval;cms=$ApprovalCms;authority_pin=$pin
  admission_bytes=$AuthorityAdmission;admission_sha256=$ExpectedAuthorityAdmissionSha256;package_root=$PackageRoot
  tasks=@('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait')
  abort_json=$TerminalAbortJson;abort_cms=$TerminalAbortCms;catalog_readback=$InstallReadbackJson;stop_attempted=$true
  journal_path=$journalPath;original_approval_path=$ExistingApprovalJson;original_cms_path=$ExistingApprovalCms
  evidence_path=$ReconciliationEvidenceJson;backup_root=$BackupDirectory;evidence=$null;instance_snapshot=$null;enabled_names=@();interrupted_approval_bytes=$null;interrupted_cms_bytes=$null;continuation_leases=[Collections.Generic.List[IO.FileStream]]::new()}
 $script:V3ReleaseContext=$ctx
 $mutex=$null;$held=$false;$packageLease=$null;$originalLease=$null;$pair=$null
 try{
  if(-not(Test-V3ReleaseOriginalhostScope -Root $script:V3ReleaseRoot -Tasks $ctx.tasks)){
   throw 'V3_RECONCILE_INTERACTIVE_ORIGINALHOST_ONLY'
  }
  $who=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
  if(-not $who.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'V3_RECONCILE_ADMIN_REQUIRED'}
  $mutex=[Threading.Mutex]::new($false,'Global\V3Pr661OriginalhostOneShotOperator')
  try{$held=$mutex.WaitOne(0,$false)}catch [Threading.AbandonedMutexException]{
   $held=$true;throw 'V3_RECONCILE_ABANDONED_MUTEX_HOLD'
  }
  if(-not $held){throw 'V3_RECONCILE_CONCURRENT_OPERATOR_HOLD'}
  $packageLease=Open-V3ReleasePackageReadLease -PackageRoot $PackageRoot -Inventory $inventory
  Assert-V3ReleaseReconciliationOriginals $ctx
  $ctx.evidence=[Text.UTF8Encoding]::new($false,$true).GetString(
   (Read-V3ReleaseLocalBytes $ReconciliationEvidenceJson))|ConvertFrom-Json -ErrorAction Stop
  # Real immutable handles are acquired anew under a NEW, specific authority;
  # they are never presented as the interrupted STOP session's original pair.
  $originalInventory=@{}
  foreach($p in @($journalPath,$ExistingApprovalJson,$ExistingApprovalCms,$ReconciliationEvidenceJson)){
   $originalInventory[$p]=Get-V3ReleaseSha256 (Read-V3ReleaseLocalBytes $p)
  }
  # Hold the actual existing evidence files, without rewriting their bytes.
  $originalLease=[Collections.Generic.List[IO.FileStream]]::new()
  foreach($p in $originalInventory.Keys){
   $stream=[IO.File]::Open($p,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
   $originalLease.Add($stream)
   if((Get-V3ReleaseSha256 (Read-V3ReleaseLocalBytes $p)) -cne $originalInventory[$p]){throw 'V3_RECONCILE_ORIGINAL_LEASE_RACE'}
  }
  Assert-V3ReleaseReconciliationOriginals $ctx
  $fence=Join-Path $script:V3ReleaseRoot 'State\v3-experimental-paper-old-intake-fence.json'
  $archive=Join-Path $script:V3ReleaseRoot ('State\v3-experimental-paper-old-intake-fence.aborted-'+[string]$b.epoch_id+'.json')
  if(Test-Path -LiteralPath ($journalPath+'.reconciliation-attempt.json')){
   if((Test-Path -LiteralPath $fence) -and -not(Test-Path -LiteralPath $archive)){
    if(Test-Path -LiteralPath ($journalPath+'.awaiting-post-archive-reader.json')){
     throw 'V3_RECONCILE_PRE_ARCHIVE_AWAITING_CONFLICT_HOLD'
    }
    return Complete-V3ReleasePreArchiveInterrupted -Context $ctx -InterruptedApprovalJson $InterruptedApprovalJson -InterruptedApprovalCms $InterruptedApprovalCms
   }
   $after=Get-V3ReleasePostArchiveBoundary -Context $ctx
   Assert-V3ReconciliationResumeReceipt -Claims $a -Receipt (Read-V3ReleaseLocalBytes ($journalPath+'.awaiting-post-archive-reader.json'))
   return Complete-V3ReleasePostArchive -Context $ctx -After $after
  }
  if('post_archive_receipt_sha256' -cin @($b.PSObject.Properties.Name)){
   throw 'V3_RECONCILE_CONTINUATION_PIN_WITHOUT_ATTEMPT_HOLD'
  }
  if((Test-Path -LiteralPath $archive) -or
     (Test-Path -LiteralPath (Join-Path $script:V3ReleaseRoot 'State\v2r4-technical-cutover-maintenance.json'))){
   throw 'V3_RECONCILE_ARCHIVE_OR_FOREIGN_MAINTENANCE_HOLD'
  }
  $null=Get-V3Pr515ArmedOnlyRecoveryReadback -Root $script:V3ReleaseRoot -ExpectedFenceSha256 $b.fence_sha256
  Assert-V3ReleaseMutationBoundary -Phase RESTORE
  $pair=Open-V3Pr661DisabledIntakeLeasePairSOURCE_ONLY -TaskNames $ctx.tasks
  if(-not(Test-V3Pr661HeldIntakeDefinitionPair -Pair $pair -TaskNames $ctx.tasks)){throw 'V3_RECONCILE_REAL_PAIR_REQUIRED'}
  $ctx.instance_snapshot=Read-V3ReleaseContinuingIntakes $ctx
  return Complete-V3ReleaseExistingAttempt -Context $ctx -HeldPair $pair
 }finally{
  if($null -ne $pair){foreach($lease in $pair.leases){$lease.readonly_definition_handle.Dispose()}}
  foreach($stream in $ctx.continuation_leases){$stream.Dispose()}
  foreach($stream in $originalLease){$stream.Dispose()}
  foreach($stream in $packageLease){$stream.Dispose()}
  if($held){$mutex.ReleaseMutex()};if($null -ne $mutex){$mutex.Dispose()}
  $script:V3ReleaseContext=$null
 }
}

function Assert-V3ReleaseProtectedTasks([object]$Bindings) {
 $b=$Bindings
 foreach($row in @(
  @('CryptoMiniPC-V2R4PaperLifecycle','lifecycle_xml_sha256'),
  @('CryptoMiniPC-V2R4PaperCloudSync','cloudsync_xml_sha256'),
  @('CryptoMiniPC-V3PaperSingleWriter','v3_writer_xml_sha256'))){
  $task=Get-ScheduledTask -TaskName $row[0] -TaskPath '\' -ErrorAction Stop
  $xml=[string](Export-ScheduledTask -TaskName $row[0] -TaskPath '\' -ErrorAction Stop)
  $hash=Get-V3ReleaseSha256 ([Text.Encoding]::UTF8.GetBytes($xml))
  $expectedState=if($row[0] -ceq 'CryptoMiniPC-V3PaperSingleWriter'){'Disabled'}else{'Running'}
  if($hash -cne [string]$b.($row[1]) -or [string]$task.State -cne $expectedState){throw 'V3_RELEASE_PROTECTED_TASK_DRIFT'}
 }
}

function Wait-V3ReleaseReconciliationTerminal([object]$Context,[datetimeoffset]$After) {
 $b=$Context.authorization.claims.bindings
 for($i=0;$i -lt 45;$i++){
  if([datetimeoffset]::UtcNow -ge $Context.authorization.expires_at){throw 'V3_RECONCILE_SESSION_EXPIRED_NO_RETRY'}
  $payload=Read-V3ReleaseLocalBytes $Context.abort_json -MaxBytes 4096
  $cms=Read-V3ReleaseLocalBytes $Context.abort_cms -MaxBytes 32768
  $review=Test-V3Pr515SignedPreparedAbortReadback -Payload $payload -Cms $cms `
   -ReviewedCertSha256 $b.reader_certificate_sha256 -ExpectedEpochId $b.epoch_id `
   -ExpectedSourceSha256 $b.source_sha256 -ExpectedFenceSha256 $b.fence_sha256 -ExpectedAclSha256 $b.caller_acl_sha256
  $m=[regex]::Match([Text.Encoding]::UTF8.GetString($payload),'"observed_at_utc"\s*:\s*"(?<t>[^"\\]+)"')
  if($review.signed_abort_fields_and_pins_match -eq $true -and $m.Success -and
     [datetimeoffset]::Parse($m.Groups['t'].Value,[Globalization.CultureInfo]::InvariantCulture) -gt $After){
   return [pscustomobject]@{payload=$payload;cms=$cms}
  }
  Start-Sleep -Seconds 2
 }
 throw 'V3_RECONCILE_POST_ARCHIVE_READER_UNKNOWN_NO_RETRY'
}

# Atomic, non-overwriting sidecars. A crash before rename leaves no accepted
# receipt; originals and attempt locks are never deleted or rewritten.
function Write-V3ReleaseImmutableReceipt([string]$Path,[object]$Value) {
 $temporary=$Path+'.pending-'+[guid]::NewGuid().ToString('N')
 $bytes=[Text.Encoding]::UTF8.GetBytes(($Value|ConvertTo-Json -Depth 8 -Compress))
 $stream=[IO.File]::Open($temporary,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
 try{$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
 [IO.File]::Move($temporary,$Path)
}

function Write-V3ReleaseArchiveCheckpoint([object]$Context) {
 $ctx=$Context;$a=$ctx.authorization.claims;$b=$a.bindings
 Assert-V3ReleaseMutationBoundary -Phase ARCHIVE
 $live=Read-V3ReleaseContinuingIntakes -Context $ctx -EnabledNames $ctx.tasks
 if(($live|ConvertTo-Json -Compress) -cne ($ctx.instance_snapshot|ConvertTo-Json -Compress)){
  throw 'V3_RECONCILE_RUNNING_INSTANCE_REPLACED'
 }
 $latchBytes=Read-V3ReleaseLocalBytes ($ctx.journal_path+'.reconciliation-attempt.json')
 $latch=Read-V3ReleaseJson $latchBytes
 if([string]$latch.release_id -cne [string]$a.release_id -or
    [string]$latch.journal_sha256 -cne [string]$b.journal_sha256 -or
    [string]($latch.approval_sha256 -cne [string]$ctx.authorization.approval_sha256 -and
     ($null -eq $ctx.interrupted_approval_bytes -or
      $latch.approval_sha256 -cne (Get-V3ReleaseSha256 $ctx.interrupted_approval_bytes))) -or
    $latch.stop_requested -ne $false){throw 'V3_RECONCILE_ATTEMPT_DRIFT'}
 $record=[ordered]@{kind='V3_RECONCILIATION_PRE_ARCHIVE_V1';release_id=$a.release_id
  release_commit=$a.release_commit;journal_sha256=$b.journal_sha256
  attempt_sha256=(Get-V3ReleaseSha256 $latchBytes)
  approval_base64=[Convert]::ToBase64String($ctx.payload);cms_base64=[Convert]::ToBase64String($ctx.cms)
  instances_base64=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes(($live|ConvertTo-Json -Compress)))
  state='TASKS_ENABLED_ORIGINAL_INSTANCES_CONFIRMED'}
 if($null -ne $ctx.interrupted_approval_bytes){
  $record.interrupted_approval_sha256=Get-V3ReleaseSha256 $ctx.interrupted_approval_bytes
  $record.interrupted_approval_base64=[Convert]::ToBase64String($ctx.interrupted_approval_bytes)
  $record.interrupted_cms_base64=[Convert]::ToBase64String($ctx.interrupted_cms_bytes)
 }
 Write-V3ReleaseImmutableReceipt -Path ($ctx.journal_path+'.pre-archive.json') -Value $record
}

function Assert-V3ReleasePostArchiveBoundary([object]$Context) {
 $ctx=$Context;$a=$ctx.authorization.claims;$b=$a.bindings
 if(-not(Test-V3ReleaseOriginalhostScope -Root $script:V3ReleaseRoot -Tasks $ctx.tasks)){
  throw 'V3_RECONCILE_POST_ARCHIVE_SCOPE_OR_EXPIRY_HOLD'
 }
 $pin=Assert-V3ReleaseAuthorityAdmission -Bytes $ctx.admission_bytes -ExpectedSha256 $ctx.admission_sha256 -ReleaseCommit $a.release_commit
 if($pin -cne $ctx.authority_pin){throw 'V3_RELEASE_AUTHORITY_ADMISSION_CHANGED'}
 $hashes=Get-V3OneTimeReleaseArtifactInventory $ctx.package_root
 $null=Assert-V3OneTimeReleaseAuthorization -Payload $ctx.payload -Cms $ctx.cms -ReviewedAuthorityCertificateSha256 $pin `
  -Scope ORIGINALHOST_ABORT_RECONCILE -ExpectedReleaseCommit $a.release_commit -ExpectedArtifacts $hashes
 Assert-V3ReleaseReconciliationOriginals $ctx
 Assert-V3ReleaseInstalledAbortReadback -Path $ctx.catalog_readback -Bindings $b `
  -ExpectedSourceSha256 $hashes['supabase/v3-cas-prepared-fence-abort-INACTIVE.sql']
 Assert-V3ReleaseProtectedTasks -Bindings $b
 $fence=Join-Path $script:V3ReleaseRoot 'State\v3-experimental-paper-old-intake-fence.json'
 $archive=Join-Path $script:V3ReleaseRoot ('State\v3-experimental-paper-old-intake-fence.aborted-'+[string]$b.epoch_id+'.json')
 if((Test-Path -LiteralPath $fence) -or
    (Test-Path -LiteralPath (Join-Path $script:V3ReleaseRoot 'State\v2r4-technical-cutover-maintenance.json')) -or
    (Get-V3ReleaseSha256 (Read-V3ReleaseLocalBytes $archive)) -cne [string]$b.fence_sha256){
  throw 'V3_RECONCILE_POST_ARCHIVE_FENCE_HOLD'
 }
 $checkpoint=Read-V3ReleaseJson (Read-V3ReleaseLocalBytes ($ctx.journal_path+'.pre-archive.json'))
 if([string]$checkpoint.kind -cne 'V3_RECONCILIATION_PRE_ARCHIVE_V1' -or
    [string]$checkpoint.state -cne 'TASKS_ENABLED_ORIGINAL_INSTANCES_CONFIRMED' -or
    [string]$checkpoint.release_id -cne [string]$a.release_id -or
    [string]$checkpoint.release_commit -cne [string]$a.release_commit -or
    [string]$checkpoint.journal_sha256 -cne [string]$b.journal_sha256 -or
    [string]$checkpoint.attempt_sha256 -cne (Get-V3ReleaseSha256 (Read-V3ReleaseLocalBytes ($ctx.journal_path+'.reconciliation-attempt.json')))){
  throw 'V3_RECONCILE_POST_ARCHIVE_CHECKPOINT_DRIFT'
 }
 $historical=[Convert]::FromBase64String($checkpoint.approval_base64)
 Assert-V3ReconciliationContinuationAuthority -HistoricalPayload $historical `
  -HistoricalCms ([Convert]::FromBase64String($checkpoint.cms_base64)) -AuthorityPin $pin -Current $a
 $latch=Read-V3ReleaseJson (Read-V3ReleaseLocalBytes ($ctx.journal_path+'.reconciliation-attempt.json'))
 if([string]$latch.kind -cne 'V3_EXISTING_GATE_B_RECONCILIATION_ATTEMPT_V1' -or
    [string]$latch.state -cne 'RECONCILIATION_ATTEMPTED_UNKNOWN_UNTIL_FINAL_ACK' -or
    [string]$latch.release_id -cne [string]$a.release_id -or
    [string]$latch.journal_sha256 -cne [string]$b.journal_sha256 -or
    [string]($latch.approval_sha256 -cne (Get-V3ReleaseSha256 $historical) -and
     $latch.approval_sha256 -cne [string]$checkpoint.interrupted_approval_sha256) -or
    $latch.stop_requested -ne $false){
  throw 'V3_RECONCILE_POST_ARCHIVE_ATTEMPT_DRIFT'
 }
 if('interrupted_approval_sha256' -cin @($checkpoint.PSObject.Properties.Name)){
  $priorPayload=[Convert]::FromBase64String($checkpoint.interrupted_approval_base64)
  $priorCms=[Convert]::FromBase64String($checkpoint.interrupted_cms_base64)
  Assert-V3ReconciliationPreArchiveAttemptAuthority -InterruptedPayload $priorPayload -InterruptedCms $priorCms -Attempt (Read-V3ReleaseLocalBytes ($ctx.journal_path+'.reconciliation-attempt.json')) -AuthorityPin $pin -Current $a
  if([string]$checkpoint.interrupted_approval_sha256 -cne (Get-V3ReleaseSha256 $priorPayload)){
   throw 'V3_RECONCILE_PRE_ARCHIVE_INTERRUPTED_PROOF_DRIFT'
  }
 }
 $saved=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($checkpoint.instances_base64))
 $live=Read-V3ReleaseContinuingIntakes -Context $ctx -EnabledNames $ctx.tasks
 if(($live|ConvertTo-Json -Compress) -cne $saved){throw 'V3_RECONCILE_RUNNING_INSTANCE_REPLACED'}
 $ctx.instance_snapshot=$live;$ctx.enabled_names=@($ctx.tasks)
}

function Get-V3ReleasePostArchiveBoundary([object]$Context) {
 $ctx=$Context
 Assert-V3ReleasePostArchiveBoundary -Context $ctx
 $path=$ctx.journal_path+'.awaiting-post-archive-reader.json'
 $checkpointSha=Get-V3ReleaseSha256 (Read-V3ReleaseLocalBytes ($ctx.journal_path+'.pre-archive.json'))
 if(-not(Test-Path -LiteralPath $path)){
  # Recovery cannot infer the rename time from NTFS modification time. This
  # observation is a conservative UPPER bound: a reader after it is necessarily
  # after the already verified archive. Never use the pre-rename timestamp.
  Write-V3ReleaseImmutableReceipt -Path $path -Value ([ordered]@{
   kind='V3_RECONCILIATION_AWAITING_READER_V1';state='AWAITING_POST_ARCHIVE_READER'
   checkpoint_sha256=$checkpointSha
   archive_observed_by_utc=[datetimeoffset]::UtcNow.ToString('o')})
 }
 if('continuation_leases' -cin @($ctx.PSObject.Properties.Name) -and $ctx.continuation_leases.Count -eq 0){
  $archive=Join-Path $script:V3ReleaseRoot ('State\v3-experimental-paper-old-intake-fence.aborted-'+[string]$ctx.authorization.claims.bindings.epoch_id+'.json')
  foreach($proof in @(($ctx.journal_path+'.reconciliation-attempt.json'),($ctx.journal_path+'.pre-archive.json'),$path,$archive)){
   $ctx.continuation_leases.Add([IO.File]::Open($proof,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read))
  }
  Assert-V3ReleasePostArchiveBoundary -Context $ctx
 }
 $receipt=Read-V3ReleaseJson (Read-V3ReleaseLocalBytes $path)
 $after=[datetimeoffset]::MinValue
 if([string]$receipt.kind -cne 'V3_RECONCILIATION_AWAITING_READER_V1' -or
    [string]$receipt.state -cne 'AWAITING_POST_ARCHIVE_READER' -or
    [string]$receipt.checkpoint_sha256 -cne $checkpointSha -or
    -not [datetimeoffset]::TryParse([string]$receipt.archive_observed_by_utc,[ref]$after) -or
    $after -gt [datetimeoffset]::UtcNow){throw 'V3_RECONCILE_AWAITING_RECEIPT_DRIFT'}
 return $after
}

# Resume only the pre-archive HOLD of an already durable attempt.
# Do not create a second attempt marker, re-enable tasks or fabricate health.
function Complete-V3ReleasePreArchiveInterrupted([object]$Context,
 [string]$InterruptedApprovalJson,[string]$InterruptedApprovalCms) {
 $ctx=$Context;$a=$ctx.authorization.claims;$b=$a.bindings
 $journalPath=$ctx.journal_path
 $fence=Join-Path $script:V3ReleaseRoot 'State\v3-experimental-paper-old-intake-fence.json'
 $archive=Join-Path $script:V3ReleaseRoot ('State\v3-experimental-paper-old-intake-fence.aborted-'+[string]$b.epoch_id+'.json')
 $checkpointPath=$journalPath+'.pre-archive.json'
 $latchBytes=Read-V3ReleaseLocalBytes ($journalPath+'.reconciliation-attempt.json')
 $interrupted=Read-V3ReleaseLocalBytes $InterruptedApprovalJson
 $interruptedCms=Read-V3ReleaseLocalBytes $InterruptedApprovalCms -MaxBytes 32768
 Assert-V3ReconciliationPreArchiveAttemptAuthority -InterruptedPayload $interrupted -InterruptedCms $interruptedCms -Attempt $latchBytes -AuthorityPin $ctx.authority_pin -Current $a
 if((Test-Path -LiteralPath $archive) -or -not(Test-Path -LiteralPath $fence) -or
    (Test-Path -LiteralPath ($journalPath+'.awaiting-post-archive-reader.json')) -or
    (Test-Path -LiteralPath ($journalPath+'.completed.json'))){
  throw 'V3_RECONCILE_PRE_ARCHIVE_STATE_CONFLICT_HOLD'
 }
 if(Test-Path -LiteralPath (Join-Path $script:V3ReleaseRoot 'State\v2r4-technical-cutover-maintenance.json')){
  throw 'V3_RECONCILE_FOREIGN_MAINTENANCE_HOLD'
 }
 $null=Get-V3Pr515ArmedOnlyRecoveryReadback -Root $script:V3ReleaseRoot -ExpectedFenceSha256 $b.fence_sha256
 $ctx.enabled_names=@($ctx.tasks)
 $ctx.instance_snapshot=Read-V3ReleaseContinuingIntakes -Context $ctx -EnabledNames $ctx.tasks
 if(Test-Path -LiteralPath $checkpointPath){
  $checkpoint=Read-V3ReleaseJson (Read-V3ReleaseLocalBytes $checkpointPath)
  if([string]$checkpoint.kind -cne 'V3_RECONCILIATION_PRE_ARCHIVE_V1' -or
     [string]$checkpoint.state -cne 'TASKS_ENABLED_ORIGINAL_INSTANCES_CONFIRMED' -or
     [string]$checkpoint.release_id -cne [string]$a.release_id -or
     [string]$checkpoint.attempt_sha256 -cne (Get-V3ReleaseSha256 $latchBytes) -or
     [string]$checkpoint.interrupted_approval_sha256 -cne (Get-V3ReleaseSha256 $interrupted)){
   throw 'V3_RECONCILE_PRE_ARCHIVE_CHECKPOINT_HOLD'
  }
  $checkpointOld=[Convert]::FromBase64String($checkpoint.interrupted_approval_base64)
  $checkpointCms=[Convert]::FromBase64String($checkpoint.interrupted_cms_base64)
  if((Get-V3ReleaseSha256 $checkpointOld) -cne (Get-V3ReleaseSha256 $interrupted) -or
     (Get-V3ReleaseSha256 $checkpointCms) -cne (Get-V3ReleaseSha256 $interruptedCms)){
   throw 'V3_RECONCILE_PRE_ARCHIVE_HISTORICAL_PROOF_DRIFT'
  }
  Assert-V3ReconciliationContinuationAuthority -HistoricalPayload ([Convert]::FromBase64String($checkpoint.approval_base64)) -HistoricalCms ([Convert]::FromBase64String($checkpoint.cms_base64)) -AuthorityPin $ctx.authority_pin -Current $a
  $saved=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($checkpoint.instances_base64))
  if(($ctx.instance_snapshot|ConvertTo-Json -Compress) -cne $saved){
   throw 'V3_RECONCILE_PRE_ARCHIVE_INSTANCE_REPLACED'
  }
 }else{
  # For an interrupted recovery the authorizing new session must see a real
  # fresh healthy heartbeat after it starts, not an earlier stale receipt.
  $healthAfter=[datetimeoffset]::UtcNow
  Wait-V3ReleaseReconciliationHealth -Context $ctx -After $healthAfter
  $ctx.interrupted_approval_bytes=$interrupted
  $ctx.interrupted_cms_bytes=$interruptedCms
  Write-V3ReleaseArchiveCheckpoint -Context $ctx
 }
 # A crash after checkpoint but before archive is recoverable only while
 # the original fence is present and the original instance snapshot matches.
 $healthAfter=[datetimeoffset]::UtcNow
 Wait-V3ReleaseReconciliationHealth -Context $ctx -After $healthAfter
 Assert-V3ReleaseMutationBoundary -Phase ARCHIVE
 $live=Read-V3ReleaseContinuingIntakes -Context $ctx -EnabledNames $ctx.tasks
 if(($live|ConvertTo-Json -Compress) -cne ($ctx.instance_snapshot|ConvertTo-Json -Compress)){
  throw 'V3_RECONCILE_PRE_ARCHIVE_INSTANCE_REPLACED'
 }
 if((Test-Path -LiteralPath $archive) -or -not(Test-Path -LiteralPath $fence)){
  throw 'V3_RECONCILE_PRE_ARCHIVE_ARCHIVE_CONFLICT_HOLD'
 }
 $archived=Invoke-V3Pr515NativeExclusiveFenceArchiveSOURCE_ONLY -Source $fence -Archive $archive -ExpectedSha256 $b.fence_sha256 -IsolatedRoot $script:V3ReleaseRoot -IsolatedTaskNames $ctx.tasks
 if([string]$archived.status -cne 'ATOMIC_FILE_RENAME_CONFIRMED_NO_CAS_OR_PAPER_RELEASE'){
  throw 'V3_RECONCILE_ARCHIVE_UNKNOWN_NO_RETRY'
 }
 $after=Get-V3ReleasePostArchiveBoundary -Context $ctx
 return Complete-V3ReleasePostArchive -Context $ctx -After $after
}

# Private continuation of the SAME owner. Separated for regression coverage,
# not exported, and cannot run without the real authorized context/pair.
function Complete-V3ReleaseExistingAttempt([object]$Context,[object]$HeldPair) {
 $ctx=$Context;$pair=$HeldPair;$authorization=$ctx.authorization
 $a=$authorization.claims;$b=$a.bindings
 $Approval=$ctx.payload;$ApprovalCms=$ctx.cms;$pin=$ctx.authority_pin
 $ExpectedReleaseCommit=[string]$a.release_commit;$PackageRoot=$ctx.package_root
 $journalPath=$ctx.journal_path
 $fence=Join-Path $script:V3ReleaseRoot 'State\v3-experimental-paper-old-intake-fence.json'
 $archive=Join-Path $script:V3ReleaseRoot ('State\v3-experimental-paper-old-intake-fence.aborted-'+[string]$b.epoch_id+'.json')
 $latch=$null
 try{
  Assert-V3ReleaseMutationBoundary -Phase RESTORE
  if(-not(Test-V3Pr661HeldIntakeDefinitionPair -Pair $pair -TaskNames $ctx.tasks)){
   throw 'V3_RECONCILE_REAL_PAIR_REQUIRED'
  }
  # This is a one-way extension of the EXISTING journal, not another STOP
  # transaction. CreateNew persists BEFORE Enable. No code removes this latch.
  $latchPath=$journalPath+'.reconciliation-attempt.json'
  $latch=[IO.File]::Open($latchPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
  $record=[Text.Encoding]::UTF8.GetBytes((@{kind='V3_EXISTING_GATE_B_RECONCILIATION_ATTEMPT_V1'
   release_id=$a.release_id;journal_sha256=$b.journal_sha256;approval_sha256=$authorization.approval_sha256
   state='RECONCILIATION_ATTEMPTED_UNKNOWN_UNTIL_FINAL_ACK';stop_requested=$false}|ConvertTo-Json -Compress))
  $latch.Write($record,0,$record.Length);$latch.Flush($true)
  Assert-V3ReleaseMutationBoundary -Phase RESTORE
  $null=Read-V3ReleaseContinuingIntakes $ctx
  foreach($lease in $pair.leases){$lease.readonly_definition_handle.Dispose()}
  $enabled=@();$enabledAt=[datetimeoffset]::UtcNow
  foreach($name in $ctx.tasks){
   $null=Read-V3ReleaseContinuingIntakes -Context $ctx -EnabledNames $enabled
   Enable-V3ReleaseIntakeDefinition -TaskName $name
   $enabled+=@($name);$ctx.enabled_names=@($enabled)
   $null=Read-V3ReleaseContinuingIntakes -Context $ctx -EnabledNames $enabled
  }
  Wait-V3ReleaseReconciliationHealth -Context $ctx -After $enabledAt
  $latch.Dispose();$latch=$null
  Write-V3ReleaseArchiveCheckpoint -Context $ctx
  # The existing same-handle, non-overwriting NTFS archive primitive performs
  # the final signed boundary again. Generic marker-only hardlocks stay intact.
  $archived=Invoke-V3Pr515NativeExclusiveFenceArchiveSOURCE_ONLY -Source $fence -Archive $archive `
   -ExpectedSha256 $b.fence_sha256 -IsolatedRoot $script:V3ReleaseRoot -IsolatedTaskNames $ctx.tasks
  if([string]$archived.status -cne 'ATOMIC_FILE_RENAME_CONFIRMED_NO_CAS_OR_PAPER_RELEASE'){
   throw 'V3_RECONCILE_ARCHIVE_UNKNOWN_NO_RETRY'
  }
  $archivedAt=Get-V3ReleasePostArchiveBoundary -Context $ctx
  return Complete-V3ReleasePostArchive -Context $ctx -After $archivedAt
 }finally{if($null -ne $latch){$latch.Dispose()}}
}

# Finalization has no task mutation or archive primitive. Both immediate and
# later calls run this same owner under the outer mutex and immutable leases.
function Complete-V3ReleasePostArchive([object]$Context,[datetimeoffset]$After) {
  $ctx=$Context;$authorization=$ctx.authorization;$a=$authorization.claims;$b=$a.bindings
  $Approval=$ctx.payload;$ApprovalCms=$ctx.cms;$pin=$ctx.authority_pin
  $ExpectedReleaseCommit=[string]$a.release_commit;$PackageRoot=$ctx.package_root;$journalPath=$ctx.journal_path
  $fence=Join-Path $script:V3ReleaseRoot 'State\v3-experimental-paper-old-intake-fence.json'
  $archive=Join-Path $script:V3ReleaseRoot ('State\v3-experimental-paper-old-intake-fence.aborted-'+[string]$b.epoch_id+'.json')
  Assert-V3ReleasePostArchiveBoundary -Context $ctx
  Wait-V3ReleaseReconciliationHealth -Context $ctx -After $After -AfterArchive
  # One final fresh independent Cloud Reader is still required. After archive
  # the shared RESTORE boundary expects ARMED, so validate originals/authority/
  # signed terminal explicitly without pretending the fence is still present.
  $post=Wait-V3ReleaseReconciliationTerminal -Context $ctx -After $After
  $null=Assert-V3OneTimeReleaseAuthorization -Payload $Approval -Cms $ApprovalCms `
   -ReviewedAuthorityCertificateSha256 $pin -Scope ORIGINALHOST_ABORT_RECONCILE `
   -ExpectedReleaseCommit $ExpectedReleaseCommit -ExpectedArtifacts (Get-V3OneTimeReleaseArtifactInventory $PackageRoot)
  Assert-V3ReleaseReconciliationOriginals $ctx
  Assert-V3ReleaseProtectedTasks -Bindings $b
  $finalInstances=Read-V3ReleaseContinuingIntakes -Context $ctx -EnabledNames $ctx.tasks
  if(($finalInstances|ConvertTo-Json -Compress) -cne ($ctx.instance_snapshot|ConvertTo-Json -Compress)){
   throw 'V3_RECONCILE_RUNNING_INSTANCE_REPLACED'
  }
  $terminal=Test-V3Pr515SignedPreparedAbortReadback -Payload $post.payload `
   -Cms $post.cms -ReviewedCertSha256 $b.reader_certificate_sha256 `
   -ExpectedEpochId $b.epoch_id -ExpectedSourceSha256 $b.source_sha256 -ExpectedFenceSha256 $b.fence_sha256 `
   -ExpectedAclSha256 $b.caller_acl_sha256
  if($terminal.signed_abort_fields_and_pins_match -ne $true -or (Test-Path -LiteralPath $fence) -or
     (Get-V3ReleaseSha256 (Read-V3ReleaseLocalBytes $archive)) -cne [string]$b.fence_sha256){
   throw 'V3_RECONCILE_FINAL_READBACK_UNKNOWN_NO_RETRY'
  }
  $receipt=[pscustomobject]@{kind='V3_ONE_TIME_ORIGINALHOST_RECONCILIATION_RECEIPT_V1'
   release_id=$a.release_id;release_commit=$a.release_commit;journal_sha256=$b.journal_sha256
   original_approval_sha256=$b.original_approval_sha256;approval_sha256=$authorization.approval_sha256
   status='TERMINAL_ABORT_PARTIAL_ATTEMPT_RECONCILED_AFTERCARE_CONFIRMED'
   stop_requested_here=$false;successful_stop_claimed=$false;new_process_started_here=$false
   original_processes_continued=$true;cas_or_paper_authorized=$false}
  Assert-V3ReleasePostArchiveBoundary -Context $ctx
  Write-V3ReleaseImmutableReceipt -Path ($journalPath+'.completed.json') -Value $receipt
  return $receipt
}
