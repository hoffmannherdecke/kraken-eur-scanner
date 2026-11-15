# PR710: native Windows PowerShell 5.1 offline read-only Reader tests.
$ErrorActionPreference='Stop'
$source=Join-Path $PSScriptRoot '../tools/v3-poststop-notebook-reader-extension-INACTIVE.ps1'
$tokens=$null;$errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile($source,[ref]$tokens,[ref]$errors)
if(@($errors).Count -ne 0){throw ('PR710_NOTEBOOK_SYNTAX_HOLD: '+($errors|Select-Object -First 1).Message)}
$coordinator=Join-Path $PSScriptRoot '../tools/v3-poststop-triple-reader-window-INACTIVE.ps1'
$otherTokens=$null;$otherErrors=$null
$null=[System.Management.Automation.Language.Parser]::ParseFile($coordinator,[ref]$otherTokens,[ref]$otherErrors)
if(@($otherErrors).Count -ne 0){throw ('PR710_COORDINATOR_PARSE_HOLD: '+($otherErrors|Select-Object -First 1).Message)}
$publisher=Join-Path $PSScriptRoot '../tools/v3-poststop-originalhost-signed-unc-publish-INACTIVE.ps1'
$pubTokens=$null;$pubErrors=$null
$null=[System.Management.Automation.Language.Parser]::ParseFile($publisher,[ref]$pubTokens,[ref]$pubErrors)
if(@($pubErrors).Count -ne 0){throw ('PR710_ORIGINALHOST_UNC_PUBLISHER_PARSE_HOLD: '+(($pubErrors | ForEach-Object {$_.Message}) -join '; '))}
$publisherSource=[IO.File]::ReadAllText($publisher)
foreach($required in @('SIGN_FRESH_ORIGINALHOST_CURRENT_READER_ONLY_NO_RECOVERY',
 'v3-paper-originalhost-manual-tpm-enroll-INACTIVE.ps1',
 'Assert-V3ReleaseCms','[IO.Directory]::Move($staging,$final)',
 'PR710_ORIGINALHOST_FINAL_BYTE_DRIFT_HOLD','FileMode]::CreateNew')){
 if(-not $publisherSource.Contains($required)){throw "PR710_ORIGINALHOST_PUBLISHER_CONTRACT_MISSING: $required"}
}

# The TPM owner's SMB access is intentionally NOT broadened. The existing
# share maps D: to the notebook UNC; publication is atomic on local D:.
foreach($required in @(
 "Get-SmbShare -Name 'Mistral_450'",
 "PR710_ORIGINALHOST_FIXED_SHARE_MAP_HOLD",
 '$root=' + [char]39 + 'D:\' + [char]39,
 'originalhost_unc_directory=$expectedUnc'
)){
 if(-not $publisherSource.Contains($required)){
  throw "PR710_ORIGINALHOST_LOCAL_BACKING_CONTRACT_MISSING: $required"
 }
}
if($publisherSource.Contains('$root=' + [char]39 + '\\192.168.178.179\Mistral_450' + [char]39)){
 throw 'PR710_ORIGINALHOST_UNAUTHORIZED_SMB_WRITE_PATH_HOLD'
}

# PowerShell reserves the case-insensitive automatic $Host variable as
# read-only. Parsing alone does not catch runtime assignment. Reject both
# extension and coordinator assigning it before any device window can open.
foreach($file in @($source,$coordinator)){
 $fileText=[IO.File]::ReadAllText($file)
 $hostAssignments=[regex]::Matches($fileText,'(?im)^\s*\$host\s*=')
 if($hostAssignments.Count -ne 0){
  throw ('PR710_READONLY_AUTOMATIC_HOST_ASSIGNMENT_HOLD: '+$file)
 }
 if(-not $fileText.Contains('$hostReceipt')){
  throw ('PR710_EXPLICIT_HOST_RECEIPT_VAR_MISSING: '+$file)
 }
}

$coordinatorSource=[IO.File]::ReadAllText($coordinator)
foreach($required in @('Assert-V3PostStopOwnerAdmittedCurrentHostTripleCms',
 'ApprovedPinsSha256','Start-Sleep -Milliseconds 200','PR710_POLICY_FIELDS_OR_UNTRUSTED_LIVE_SHA_HOLD',
 'PR710_WINDOW_STALE_ORIGINAL_HOLD','NO_PRODUCTION_EFFECT')){
 if(-not $coordinatorSource.Contains($required)){throw "PR710_COORDINATOR_CONTRACT_MISSING: $required"}
}
$pinsAst=@($otherTokens)
$helper=@([Management.Automation.Language.Parser]::ParseFile($coordinator,[ref]$otherTokens,[ref]$otherErrors).FindAll({
 param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
 $node.Name -eq 'Get-V3PostStopVerifiedLivePins'
},$true))
if($helper.Count -ne 1){throw 'PR710_CMS_FIRST_PIN_HELPER_MISSING_HOLD'}
. ([scriptblock]::Create($helper[0].Extent.Text))
$policy=[pscustomobject]@{
 series_id='PAPER-V3-20261111T105211Z';epoch_id='V3CAS-AUDIT-f27cce0ba68043b480e4f97698dd2901'
 source_sha256=('a'*64);epoch_fence_sha256=('b'*64);caller_acl_sha256=('c'*64)
 local_fence_file_sha256=('d'*64);candidates_xml_sha256=('e'*64)
 wait_xml_sha256=('f'*64);cloudsync_xml_sha256=('1'*64);writer_xml_sha256=('2'*64)
 host_certificate_sha256=('3'*64);cloud_certificate_sha256=('4'*64)
 owner_review_sha256=('5'*64);observation_nonce='0123456789abcdef0123456789abcdef'
}
$fake=[byte[]](1..450 | ForEach-Object {$_ % 251})
$held=$false
try{
 $null=Get-V3PostStopVerifiedLivePins -Approved $policy -HostPayload $fake -CloudPayload $fake -OriginalHostCms $fake -NotebookHostCms $fake -CloudCms $fake
}catch{$held=$true}
if(-not $held){throw 'PR710_UNVERIFIED_LIVE_CMS_ACCEPTED'}
$policy | Add-Member -NotePropertyName host_payload_sha256 -NotePropertyValue ('6'*64)
$held=$false
try{
 $null=Get-V3PostStopVerifiedLivePins -Approved $policy -HostPayload $fake -CloudPayload $fake -OriginalHostCms $fake -NotebookHostCms $fake -CloudCms $fake
}catch{$held=$true}
if(-not $held){throw 'PR710_SELF_APPROVED_EPHEMERAL_SHA_ACCEPTED'}

$raw=[IO.File]::ReadAllText($source)
# The SQL travels through Windows PowerShell 5.1 native psql arguments.
# Embedded double quotes may be removed before PostgreSQL sees its format.
$expirySql=[regex]::Match($raw,'(?ms)^if\(\$ExpiredStage4Readback\)\{\s*\$checks\[0\]\.Sql=@''\r?\n(?<sql>.*?)^''@')
$expiryFormat="replace(to_char(clock_timestamp() AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS.US'),' ','T') || 'Z'"
if(-not $expirySql.Success -or $expirySql.Groups['sql'].Value.Contains([char]34) -or
   -not $expirySql.Groups['sql'].Value.Contains($expiryFormat)){
 throw 'PR732_NOTEBOOK_UTC_NATIVE_PSQL_FORMAT_HOLD'
}
foreach($required in @(
 'PostStopHostReader','PostStopCloudReader','ObservationNonce',
 'V3_POSTSTOP_CURRENT_INDEPENDENT_HOST_READER_V1',
 'V3_POSTSTOP_CURRENT_INDEPENDENT_CLOUD_READER_V1',
 'read_forward_t0_current_v1','read_paper_release_epoch_v1',
 'BEGIN TRANSACTION READ ONLY','verify-full',
 'CheckSignature($true)','ce256281af6d36eb883dd2cb34594d0f2231e32a33f58e668d327814c7cfdb40',
 '2e3322131208737c58a82c04764bddf4ebe29481c96c79697183710358a2fc57',
 '61d08dd9a925730f213fedc559664dbfe2a3e4f8f1ae77496b385f7d92f3bc55',
 'V3_POSTSTOP_HOST_BYTE_HOLD','V3_POSTSTOP_READER_FRESHNESS_HOLD'
)){if(-not $raw.Contains($required)){throw "PR710_READER_CONTRACT_MISSING: $required"}}
# PR710: the deployed current epoch scope reader proves EVERY foreign
# epoch is exactly abort-bound; merely dropping global epoch_count=1 would
# accept a second un-terminated authority. Enforce the source contract here.
foreach($required in @(
 "p->>'state'='PRESTOP_INHIBITED_OLD_ONLY_NO_ATTEMPTS'",
 "p->>'epoch_id'=e.epoch_id",
 "p->>'source_sha256'=e.source_sha256",
 "p->>'fence_sha256'=e.original_fence_sha256",
 "p->>'caller_acl_sha256'=e.approved_caller_acl_sha256",
 "(c->>'cas_rpc_count')::integer=1",
 "('v3_cas_executor','v3_cas_executor_actor','v3_cas_audit_writer_actor')",
 "NOT EXISTS (SELECT 1 FROM v3_cas_audit.prepared_fence_abort_v1 a WHERE a.epoch_id=e.epoch_id)",
 "BEGIN TRANSACTION READ ONLY",
 "session_user='v3_cas_audit_reader_actor'",
 "current_user='v3_cas_audit_reader'"
)){
 if(-not $raw.Contains($required)){
  throw "PR710_SCOPED_CLOUD_AUTHORITY_PROOF_MISSING: $required"
 }
}
if($raw.Contains('read_committed_pre_stop_inhibit_v1') -or
   $raw.Contains("(c->>'epoch_count')::integer=1") -or
   $raw.Contains("$"+"row.cloud_cas_rpc_count -ne 0")){
 throw 'PR710_OLD_SINGLE_GLOBAL_EPOCH_PRECONDITION_REINTRODUCED'
}
$validator=Join-Path $PSScriptRoot '../tools/v3-post-stop-unknown-quarantine-source-only.ps1'
$validatorRaw=[IO.File]::ReadAllText($validator)
if(-not $validatorRaw.Contains('$cloud.cloud_cas_rpc_count -ne 1') -or
    $validatorRaw.Contains('$cloud.cloud_cas_rpc_count -ne 0')){
 throw 'PR710_SCOPE_CAS_RPC_NOT_TIED_TO_CURRENT_GATE'
}

if($raw.Contains('ForwardT0SignedCurrent -and $PostStopCloudReader')){
 throw 'PR710_WRONG_RECEIPT_MODE_REUSED'
}
$fn=@($ast.FindAll({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
 $node.Name -eq 'Assert-V3PostStopFreshReader'},$true))
if($fn.Count -ne 1){throw 'PR710_READER_FRESH_FUNCTION_COUNT_HOLD'}
. ([scriptblock]::Create($fn[0].Extent.Text))
$valid=[ordered]@{
 kind='V3_POSTSTOP_CURRENT_INDEPENDENT_HOST_READER_V1'
 observation_nonce='0123456789abcdef0123456789abcdef'
 observed_at_utc=([datetime]::UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'",[Globalization.CultureInfo]::InvariantCulture))
}
$json=$valid|ConvertTo-Json -Compress
$null=Assert-V3PostStopFreshReader $json $valid.observation_nonce $valid.kind
function Expect-Hold([string]$Value,[string]$Nonce,[string]$Kind){
 $caught=$false
 try{$null=Assert-V3PostStopFreshReader $Value $Nonce $Kind}catch{$caught=$true}
 if(-not $caught){throw 'PR710_READER_FAIL_CLOSED_NEGATIVE_MISSING'}
}
Expect-Hold $json 'ffffffffffffffffffffffffffffffff' $valid.kind
Expect-Hold $json $valid.observation_nonce 'V3_CAS_FORWARD_T0_CURRENT_CATALOG_READONLY_V1'
$valid.observed_at_utc=([datetime]::UtcNow.AddSeconds(-75).ToString("yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'",[Globalization.CultureInfo]::InvariantCulture))
Expect-Hold ($valid|ConvertTo-Json -Compress) $valid.observation_nonce $valid.kind
$valid.observed_at_utc=([datetime]::UtcNow.AddSeconds(20).ToString("yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'",[Globalization.CultureInfo]::InvariantCulture))
Expect-Hold ($valid|ConvertTo-Json -Compress) $valid.observation_nonce $valid.kind
Write-Output 'PR710_POSTSTOP_NATIVE_PS51_READER_PARSE_AND_FRESHNESS_NEGATIVES_PASS'


# AP04 post-STOP operational delta: new issuer transport and terminal reader.
$entry=Join-Path $PSScriptRoot '../tools/v3-poststop-issuer-release.ps1'
foreach($file in @($entry,$validator)){
 $tok=$null;$err=$null
 $null=[Management.Automation.Language.Parser]::ParseFile($file,[ref]$tok,[ref]$err)
 if(@($err).Count -ne 0){throw ('AP04_POSTSTOP_PARSE_HOLD: '+$file+' : '+(($err | ForEach-Object {$_.Message + ' at line ' + $_.Extent.StartLineNumber}) -join '; '))}
}
$entryRaw=[IO.File]::ReadAllText($entry)
foreach($required in @(
 'CLOUD_POSTSTOP_TERMINAL_ABORT','Assert-V3ReleaseAuthorityAdmission',
 'V3_POSTSTOP_SIGNED_SCOPE_OR_IDENTITY_HOLD','v3_cas_inhibit_issuer_actor',
 'issuer-currentuser.dpapi','DataProtectionScope]::CurrentUser',
 'Invoke-V3PostStopCloudOnceCandidate','Get-V3PostStopCloudAbortCandidate',
 'Assert-V3PostStopSignedTerminalCloud','TARGET_EPOCH_TERMINALIZED',
 'PostStopUnknownCurrentCustody','poststop-3c6b22d02d8a413c88bfede21acce2ea-attempted'
)){
 if(-not $entryRaw.Contains($required)){throw ('AP04_POSTSTOP_OPERATOR_CONTRACT_MISSING: '+$required)}
}
if($entryRaw -match "Actor\s+'postgres'" -or
   $entryRaw.Contains('Remove-Item $latch')){
 throw 'AP04_POSTSTOP_ADMIN_OR_RETRY_FORBIDDEN'
}
foreach($required in @(
 'PostStopTerminalReader',
 'cloud_cas_rpc_acl_restricted',
 'V3_CAS_PREPARED_FENCE_ABORT_READER_RECEIPT_V1',
 'historical.source_sha256 IS DISTINCT FROM other.source_sha256',
 'historical.prepared_fence_sha256 IS DISTINCT FROM other.original_fence_sha256',
 'historical.caller_acl_sha256 IS DISTINCT FROM other.approved_caller_acl_sha256',
 "pg_catalog.has_function_privilege('v3_cas_executor'",
 "WHERE other.epoch_id<>e.epoch_id"
)){
 if(-not $raw.Contains($required)){throw ('AP04_POSTSTOP_TERMINAL_READER_GUARD_MISSING: '+$required)}
}
if(-not $validatorRaw.Contains('$row.cloud_cas_rpc_acl_restricted -ne $true') -or
   -not $validatorRaw.Contains('$row.cloud_cas_rpc_count -ne 1')){
 throw 'AP04_POSTSTOP_TERMINAL_ACL_RPC_GUARD_MISSING'
}
Write-Output 'AP04_POSTSTOP_ISSUER_TERMINAL_SOURCE_GATES_PASS'


# Targeted regression for the new PR723 same-window authorization bridge.
$bridge=Join-Path $PSScriptRoot '../tools/v3-poststop-authorized-window.ps1'
$parseTokens=$null;$parseErrors=$null
$parsed=[System.Management.Automation.Language.Parser]::ParseFile($bridge,[ref]$parseTokens,[ref]$parseErrors)
if($null -eq $parsed -or @($parseErrors).Count -ne 0){throw 'AP04_BRIDGE_NATIVE_PS51_PARSE_HOLD'}
$bridgeText=[IO.File]::ReadAllText($bridge)
foreach($token in @('POSTSTOP_AUTH_PRIOR_ISSUER_ATTEMPT_NO_RETRY',
 'Assert-V3ReleaseAuthorityAdmission','Get-V3OneTimeReleaseArtifactInventory',
 'PASS_NO_PRODUCTION_EFFECT','POSTSTOP_AUTH_COORDINATOR_HASH_HOLD',
 'POSTSTOP_AUTH_LOCAL_HOST_HASH_HOLD','ComputeSignature',
 'Assert-V3ReleaseCms','POST_STOP_CMS_AUTHORIZED','-Mode Abort',
 '-PostStopTerminalReader','-Mode Readback',
 'TARGET_EPOCH_TERMINALIZED_INDEPENDENT_READER_PASS',
 'if(-not [IO.File]::Exists($latch)){throw}')){
 if(-not $bridgeText.Contains($token)){throw ('AP04_BRIDGE_REQUIRED_BOUNDARY_MISSING: '+$token)}
}
if($bridgeText -match '(?i)(ALTER\s+ROLE|CREATE\s+ROLE|DROP\s+ROLE|Remove-Item\s+.*-Recurse)'){
 throw 'AP04_BRIDGE_FORBIDDEN_AUTHORITY_MUTATION'
}
Write-Output 'AP04_POSTSTOP_BRIDGE_NATIVE_PS51_PARSE_AND_GUARDS_PASS'


# AP04 Owner-directed current Host/Cloud observation bound: 30 seconds,
# with each independently signed payload still limited to 60s freshness.
$sourceContract=Join-Path $PSScriptRoot '../tools/v3-post-stop-unknown-quarantine-source-only.ps1'
$sourceContractRaw=[IO.File]::ReadAllText($sourceContract)
$expectedSource='[math]::Abs(($ht-$ct).TotalSeconds) -gt 30'
$expectedBridge='[Math]::Abs(($hostAt-$cloudAt).TotalSeconds) -gt 30'
if(-not $sourceContractRaw.Contains($expectedSource) -or
   -not $bridgeText.Contains($expectedBridge)){
 throw 'AP04_POSTSTOP_30S_HOST_CLOUD_BOUND_MISSING'
}
if($sourceContractRaw.Contains('[math]::Abs(($ht-$ct).TotalSeconds) -gt 15') -or
   $bridgeText.Contains('[Math]::Abs(($hostAt-$cloudAt).TotalSeconds) -gt 15')){
 throw 'AP04_POSTSTOP_OLD_15S_BOUND_REMAINS'
}
foreach($sample in @(17.95,29.99,30.0)){
 if([math]::Abs($sample) -gt 30){throw 'AP04_POSTSTOP_30S_ACCEPTANCE_REGRESSION'}
}
foreach($sample in @(30.01,45.0)){
 if(-not ([math]::Abs($sample) -gt 30)){throw 'AP04_POSTSTOP_30S_REJECTION_REGRESSION'}
}
if(-not $sourceContractRaw.Contains('($Now-$ht).TotalSeconds -gt 60') -or
   -not $sourceContractRaw.Contains('($Now-$ct).TotalSeconds -gt 60') -or
   -not $bridgeText.Contains('($freshAt-$hostAt).TotalSeconds -ge 45') -or
   -not $bridgeText.Contains('($freshAt-$cloudAt).TotalSeconds -ge 45')){
 throw 'AP04_POSTSTOP_EXISTING_FRESHNESS_BOUND_CHANGED'
}
Write-Output 'AP04_POSTSTOP_30S_OVERLAP_BOUNDARY_AND_FRESHNESS_PASS'


# AP05A: changed terminal dispatch only, no PR732/PR733 fixture replay.
$ap05Issuer=Join-Path $PSScriptRoot '../tools/v3-poststop-issuer-release.ps1'
$ap05Controller=Join-Path $PSScriptRoot '../tools/v3-poststop-authorized-window.ps1'
$ap05Auth=Join-Path $PSScriptRoot '../tools/v3-one-time-release-authorization.psm1'
foreach($p in @($ap05Issuer,$ap05Controller,$ap05Auth)){
 $tok=$null;$errs=$null
 $null=[Management.Automation.Language.Parser]::ParseFile($p,[ref]$tok,[ref]$errs)
 if(@($errs).Count -gt 0){throw ('AP05A_NATIVE_PARSER_HOLD: '+$p+' '+$errs[0].Message)}
}
$i=[IO.File]::ReadAllText($ap05Issuer)
$c=[IO.File]::ReadAllText($ap05Controller)
$a=[IO.File]::ReadAllText($ap05Auth)
$start=$i.IndexOf('if($Mode -ceq '+[char]39+'ExpiredStage4Abort'+[char]39+'){')
$end=$i.IndexOf('$epoch='+[char]39+'V3CAS-AUDIT-3c6b22d02d8a413c88bfede21acce2ea'+[char]39,[Math]::Max(0,$start))
if($start -lt 0 -or $end -le $start){throw 'AP05A_NARROW_BRANCH_HOLD'}
$target=$i.Substring($start,$end-$start)
foreach($required in @(
 'V3CAS-AUDIT-7fce8ba3fd714b008407d687e29f50f4',
 'PAPER-V3-20261115T073741Z',
 'c9775bdeee0be54a2658fb7673180f2e499035830656300ad68067196e426e28',
 'CLOUD_EXPIRED_STAGE4_TERMINAL_ABORT',
 'AP05A_SIGNED_AUTHORIZATION_SCHEMA_HOLD','Assert-V3ReleaseAuthorityAdmission',
 'Assert-V3ReleaseCms','AP05A_DEFINITION_DRIFT_HOLD',
 'AP05A_FRESH_READER_HOLD','AP05A_RECEIPT_DERIVATION_HOLD',
 'AP05A_OWNER_DECISION_HOLD','AP05A_EXACT_BINDINGS_HOLD',
 'v3_cas_inhibit_issuer_actor.nlgzjmqgwueojlyqmoru',
 'FileMode]::CreateNew','AP05A_TIMEOUT_UNKNOWN_NO_RETRY',
 'AP05A_RESULT_UNKNOWN_NO_RETRY','BEGIN TRANSACTION ISOLATION LEVEL READ COMMITTED',
 'record_paper_release_abort_v1','-MaximumRedirection 0'
)){
 if(-not $target.Contains($required)){throw ('AP05A_TERMINAL_GUARD_MISSING: '+$required)}
}
if(([regex]::Matches($target,'SELECT v3_cas_audit.record_paper_release_abort_v1')).Count -ne 1 -or
 $target.Contains('DROP TABLE') -or $target.Contains('ALTER ROLE') -or
 $target.Contains('rotate_v2r4_to_v3_experimental_paper(')){
 throw 'AP05A_UNEXPECTED_EFFECT_HOLD'
}
foreach($required in @('ExpectedIssuerSha256','ExpectedControllerSha256',
 'AUTHORIZE-EXPIRED-STAGE4-TERMINAL-','AP05A_PREFLIGHT_TERMINAL_OR_DRIFT_HOLD',
 'AP05A_PREFLIGHT_TOO_OLD_HOLD','AP05A_TERMINAL_INDEPENDENT_READER_HOLD_NO_RETRY',
 'FileMode]::CreateNew','-ExpiredStage4Readback',
 'AP05A_TERMINAL_INDEPENDENT_SIGNED_PASS')){
 if(-not $c.Contains($required)){throw ('AP05A_CONTROLLER_GUARD_MISSING: '+$required)}
}
if(-not $target.Contains("'CLOUD_EXPIRED_STAGE4_TERMINAL_ABORT'")){throw 'AP05A_SCOPE_MISSING_HOLD'}
'AP05A_TARGETED_NATIVE_CONTRACT_PASS'
