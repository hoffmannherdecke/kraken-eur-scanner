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
  -ReviewedAuthorityCertificateSha256 $ctx.authority_pin -Scope ORIGINALHOST_ABORT_RESTORE `
  -ExpectedReleaseCommit ([string]$a.release_commit) -ExpectedArtifacts $hashes
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
