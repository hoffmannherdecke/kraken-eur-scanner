param(
 [switch]$Enroll,
 [switch]$InspectProvider,
 [switch]$SignPreinvoke,
 [string]$UnsignedPayloadPath='',
 [string]$DetachedCmsOutputPath='',
 [string]$SignApproval='',
 [string]$Approval=''
)
# Original V3 Paper release owner #99: one manual TPM identity.
# The OPTIONAL manual preinvoke-CMS candidate is NOT a CAS attempt, a Cloud
# reader/commit ACK, independent custody or V3 Paper approval. No Task/Cloud/
# Trading writes; no unattended receipt signer. The private key is TPM-backed and non-exportable *if* the original
# Windows Platform Crypto Provider reports success. Never fall back to a
# software provider or silently generate a second certificate.
# CurrentUser\My is the verified original local MINI-PC\Thomas profile,
# NOT LocalMachine, CryptoSupportSvc, ADMIN-as-a-guessed-username or SYSTEM.
# Bound to original Windows SID observed on 21 Oct 2026, not generic admin role. The signer MUST NOT be callable by
# V3 SYSTEM Paper Task. ADMIN/SYSTEM device-level compromise still breaks
# logical independence: the future release authority must be reviewed
# externally and independent runtime/process checks remain necessary.
$ErrorActionPreference='Stop'
$subject='CN=V3-PAPER-ORIGINALHOST-MANUAL-TPM-20261021'
$store='Cert:\CurrentUser\My'
$provider='Microsoft Platform Crypto Provider'
$confirmation='ENROLL_MANUAL_TPM_SIGNING_KEY_NO_V3_RELEASE'
if($InspectProvider -and $Enroll){
 throw 'V3_SIGNER_PROVIDER_READONLY_CANNOT_ENROLL'
}
if($SignPreinvoke -and ($Enroll -or $InspectProvider)){
 throw 'V3_SIGNER_ONE_MODE_ONLY_NO_ENROLL_OR_PROBE'
}
if($SignPreinvoke -and $SignApproval -cne 'SIGN_ONE_UNSIGNED_PREINVOKE_CANDIDATE_NO_RELEASE'){
 throw 'V3_SIGNER_CMS_EXPLICIT_MANUAL_APPROVAL_REQUIRED'
}
if(-not $SignPreinvoke -and ($UnsignedPayloadPath -or $DetachedCmsOutputPath -or $SignApproval)){
 throw 'V3_SIGNER_CMS_ARGS_WITHOUT_SIGN_MODE_HOLD'
}
if($Enroll -and $Approval -cne $confirmation){
 throw 'V3_SIGNER_ENROLL_BLOCKED_EXPLICIT_APPROVAL_REQUIRED'
}
if(-not $Enroll -and $Approval){
 throw 'V3_SIGNER_READONLY_DOES_NOT_ACCEPT_APPROVAL'
}
if([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT){
 throw 'V3_SIGNER_ORIGINAL_WINDOWS_ONLY'
}
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$account=[string]$identity.Name
# Exact physical Originalhost diagnosis: local machine MINI-PC, Thomas is the
# interactive elevated administrator, and this immutable local Windows SID
# belongs to that account. Never trust a caller-provided principal or the
# Trading path 'ADMIN' to determine which user actually owns this key.
$expected='MINI-PC\Thomas'
$expectedSid='S-1-5-21-3814592484-1822576909-3594267478-1000'
$who=[Security.Principal.WindowsPrincipal]::new($identity)
$adminRole=[Security.Principal.WindowsBuiltInRole]::Administrator
$sessionId=(Get-Process -Id $PID -ErrorAction Stop).SessionId
if($env:COMPUTERNAME -ine 'MINI-PC' -or $account -ine $expected -or
   [string]$identity.User.Value -cne $expectedSid -or
   [string]$identity.User.Value -eq 'S-1-5-18' -or
   -not $who.IsInRole($adminRole) -or
   -not [Environment]::UserInteractive -or $sessionId -le 0){
 throw 'V3_SIGNER_REQUIRES_PINNED_INTERACTIVE_MINIPC_THOMAS_ADMIN_SID_NOT_SYSTEM_OR_RUNNER'
}
if(-not (Get-Command -Name New-SelfSignedCertificate -CommandType Cmdlet -ErrorAction SilentlyContinue)){
 throw 'V3_SIGNER_WINDOWS_PKI_CMDLET_UNAVAILABLE'
}
$tpm=Get-Tpm -ErrorAction Stop
$tpmReady=($tpm.TpmPresent -eq $true -and $tpm.TpmReady -eq $true)
$existing=@(Get-ChildItem -Path $store -ErrorAction Stop |
 Where-Object {[string]$_.Subject -ceq $subject})
if($existing.Count -gt 1){
 throw 'V3_SIGNER_DUPLICATE_SUBJECT_STOP_NO_REPAIR_OR_DELETE'
}
if($Enroll){
 if(-not $tpmReady){throw 'V3_SIGNER_TPM_NOT_READY_NO_SOFTWARE_FALLBACK'}
 if($existing.Count -ne 0){throw 'V3_SIGNER_ALREADY_EXISTS_NO_REENROLL'}
 $options=@{
   Type='Custom'
   Subject=$subject
   FriendlyName='V3 Paper Originalhost MANUAL review key - not trading'
   Provider=$provider
   KeyAlgorithm='RSA'
   KeyLength=2048
   HashAlgorithm='SHA256'
   KeyExportPolicy='NonExportable'
   KeyUsage='DigitalSignature'
   KeyProtection='Protect'
   CertStoreLocation=$store
   NotAfter=(Get-Date).AddMonths(6)
 }
 # EXACTLY one permitted mutation: create one non-exportable TPM-backed
 # CurrentUser digital-signature key/certificate. No other side effects.
 $new=New-SelfSignedCertificate @options -ErrorAction Stop
 if($null -eq $new){throw 'V3_SIGNER_ENROLL_RETURNED_NO_CERT'}
 $existing=@(Get-ChildItem -Path $store -ErrorAction Stop |
   Where-Object {[string]$_.Subject -ceq $subject})
 if($existing.Count -ne 1 -or
    [string]$existing[0].Thumbprint -cne [string]$new.Thumbprint){
  throw 'V3_SIGNER_ENROLLED_BUT_CERT_READBACK_UNEXPECTED_KEEP_KEY_REVIEW_MANUALLY'
 }
}
$cert=if($existing.Count -eq 1){$existing[0]}else{$null}
$pin=$null
if($null -ne $cert){
 $digest=[Security.Cryptography.SHA256]::Create()
 try{
   $pin=([BitConverter]::ToString(
      $digest.ComputeHash([byte[]]$cert.RawData))).Replace('-','').ToLowerInvariant()
 }finally{$digest.Dispose()}
 if($pin -cnotmatch '^[0-9a-f]{64}$' -or
    $cert.HasPrivateKey -ne $true -or
    $cert.NotAfter.ToUniversalTime() -le [DateTime]::UtcNow){
  throw 'V3_SIGNER_CERTIFICATE_PUBLIC_READBACK_INVALID_KEEP_KEY_NO_RELEASE'
 }
}
# Optional originalhost provider-scoped READ-ONLY evidence only. The existing
# default output / enrollment contract stays unchanged; never regenerate a key.
# This queries CNG key metadata but never signs, exports, changes ACL or PIN.
$providerReadOnly = $false
$providerExactPlatform = $false
$userScopedKey = $false
$exportPolicyNonExportable = $false
if($InspectProvider -or $SignPreinvoke){
 if($null -eq $cert){throw 'V3_SIGNER_PROVIDER_READONLY_CERT_MISSING'}
 if(-not $tpmReady){throw 'V3_SIGNER_PROVIDER_READONLY_TPM_NOT_READY'}
 $rsa=$null
 try{
  $rsa=[Security.Cryptography.X509Certificates.RSACertificateExtensions]::GetRSAPrivateKey($cert)
  if($null -eq $rsa -or -not ($rsa -is [Security.Cryptography.RSACng])){
   throw 'V3_SIGNER_PROVIDER_READONLY_NON_CNG_KEY'
  }
  $cng=$rsa.Key
  if($null -eq $cng){throw 'V3_SIGNER_PROVIDER_READONLY_KEY_METADATA_MISSING'}
  $providerExactPlatform=([string]$cng.Provider.Provider -ceq $provider)
  $userScopedKey=(-not [bool]$cng.IsMachineKey)
  $exportPolicyNonExportable=(
    $cng.ExportPolicy -eq [Security.Cryptography.CngExportPolicies]::None)
  if(-not $providerExactPlatform -or -not $userScopedKey -or
     -not $exportPolicyNonExportable){
   throw 'V3_SIGNER_PROVIDER_READONLY_SCOPE_NOT_MATCHED'
  }
  $providerReadOnly=$true
 }catch{
  # No CNG provider exception, private-key identity or credential contents
  # may reach output. Preserve original key and do not retry enrollment.
  throw 'V3_SIGNER_PROVIDER_READONLY_METADATA_HOLD'
 }finally{
  if($null -ne $rsa){$rsa.Dispose()}
 }
}

# Pure reader-CMS input shape check; the content is STILL UNTRUSTED even if
# signed by the real TPM key. It never says a Cloud Writer committed.
function Test-V3UnsignedPreinvokeCandidate([byte[]]$Payload){
 if($null -eq $Payload -or $Payload.Length -lt 200 -or $Payload.Length -gt 2048){
  throw 'V3_SIGNER_CMS_BAD_PAYLOAD_SIZE'
 }
 $raw=[Text.UTF8Encoding]::new($false,$true).GetString($Payload)
 if($raw -cnotmatch '^[\x20-\x7e]+
 status=if($Enroll){'MANUAL_TPM_KEY_ENROLLED_NOT_TRUSTED_FOR_RELEASE'}elseif($null -ne $cert){
  'READONLY_CERT_PRESENT_NOT_TRUSTED_FOR_RELEASE'
 }else{'READONLY_NO_CERT_ENROLLED'}
 interactive_account_matches_local_admin=($account -ieq $expected -and
   [string]$identity.User.Value -ceq $expectedSid -and
   $who.IsInRole($adminRole) -and $sessionId -gt 0)
 windows_tpm_ready=$tpmReady
 provider_requested=$provider
 provider_metadata_readonly_checked=$providerReadOnly
 existing_key_platform_provider_matches=$providerExactPlatform
 existing_key_current_user_scope_matches=$userScopedKey
 existing_key_nonexportable_policy_matches=$exportPolicyNonExportable
 provider_metadata_not_external_attestation=$true
 store_location=$store
 certificate_present=($null -ne $cert)
 certificate_thumbprint_sha1=if($null -ne $cert){[string]$cert.Thumbprint}else{$null}
 certificate_der_sha256_public_pin_unapproved=$pin
 certificate_expires_utc=if($null -ne $cert){$cert.NotAfter.ToUniversalTime().ToString('o')}else{$null}
 private_key_exported=$false
 private_key_acl_independently_verified=$false
 tpm_hardware_attestation_independently_verified=$false
 originalhost_signed_receipt_generated=$false
 pin_externally_reviewed_and_approved=$false
 originalhost_runtime_identity_verified=$false
 six_e2e_release_proofs_credited=0
 cloud_cas_authorized=$false
 v3_task_modified=$false
 v2r4_modified=$false
 v3_paper_activated=$false
} | ConvertTo-Json -Depth 3
){
  throw 'V3_SIGNER_CMS_NONCANONICAL_ASCII'
 }
 try{$obj=$raw|ConvertFrom-Json -ErrorAction Stop}
 catch{throw 'V3_SIGNER_CMS_INVALID_JSON'}
 $keys=@('epoch_id','fence_sha256','intent_id','intent_sha256','kind',
  'local_review_at_utc','ordinal','predecessor_series_id','proof_status',
  'readback_sha256','reader_claimed_observed_at_utc','request_sha256','rpc',
  'source_sha256')
 if($null -eq $obj -or $obj -isnot [pscustomobject] -or
   (@($obj.PSObject.Properties.Name|Sort-Object) -join '|') -cne
    (@($keys|Sort-Object) -join '|')){
  throw 'V3_SIGNER_CMS_BAD_PROPOSAL_KEYS'
 }
 if([string]$obj.kind -cne 'V3_CAS_PREINVOKE_UNSIGNED_PROPOSAL_V1' -or
    [string]$obj.proof_status -cne 'UNTRUSTED_READER_PROPOSAL_NOT_AUTHENTICATED' -or
    ($obj.ordinal -isnot [int] -and $obj.ordinal -isnot [long]) -or
    $obj.ordinal -ne 1 -or
    [string]$obj.predecessor_series_id -cne 'PAPER-V2R4-20261009T110135Z' -or
    [string]$obj.rpc -cne 'public.rotate_v2r4_to_v3_experimental_paper' -or
    [string]$obj.epoch_id -cnotmatch '^V3CAS-AUDIT-[a-f0-9]{32}
 status=if($Enroll){'MANUAL_TPM_KEY_ENROLLED_NOT_TRUSTED_FOR_RELEASE'}elseif($null -ne $cert){
  'READONLY_CERT_PRESENT_NOT_TRUSTED_FOR_RELEASE'
 }else{'READONLY_NO_CERT_ENROLLED'}
 interactive_account_matches_local_admin=($account -ieq $expected -and
   [string]$identity.User.Value -ceq $expectedSid -and
   $who.IsInRole($adminRole) -and $sessionId -gt 0)
 windows_tpm_ready=$tpmReady
 provider_requested=$provider
 provider_metadata_readonly_checked=$providerReadOnly
 existing_key_platform_provider_matches=$providerExactPlatform
 existing_key_current_user_scope_matches=$userScopedKey
 existing_key_nonexportable_policy_matches=$exportPolicyNonExportable
 provider_metadata_not_external_attestation=$true
 store_location=$store
 certificate_present=($null -ne $cert)
 certificate_thumbprint_sha1=if($null -ne $cert){[string]$cert.Thumbprint}else{$null}
 certificate_der_sha256_public_pin_unapproved=$pin
 certificate_expires_utc=if($null -ne $cert){$cert.NotAfter.ToUniversalTime().ToString('o')}else{$null}
 private_key_exported=$false
 private_key_acl_independently_verified=$false
 tpm_hardware_attestation_independently_verified=$false
 originalhost_signed_receipt_generated=$false
 pin_externally_reviewed_and_approved=$false
 originalhost_runtime_identity_verified=$false
 six_e2e_release_proofs_credited=0
 cloud_cas_authorized=$false
 v3_task_modified=$false
 v2r4_modified=$false
 v3_paper_activated=$false
} | ConvertTo-Json -Depth 3
){
  throw 'V3_SIGNER_CMS_WRONG_OR_UNTRUSTED_SCOPE'
 }
 $uuid=[guid]::Empty
 if(-not [guid]::TryParseExact([string]$obj.intent_id,'D',[ref]$uuid) -or
    $uuid.ToString('D') -cne [string]$obj.intent_id){
  throw 'V3_SIGNER_CMS_NONCANONICAL_INTENT_ID'
 }
 foreach($field in @('fence_sha256','intent_sha256','readback_sha256',
                     'request_sha256','source_sha256')){
  if([string]$obj.$field -cnotmatch '^[a-f0-9]{64}
 status=if($Enroll){'MANUAL_TPM_KEY_ENROLLED_NOT_TRUSTED_FOR_RELEASE'}elseif($null -ne $cert){
  'READONLY_CERT_PRESENT_NOT_TRUSTED_FOR_RELEASE'
 }else{'READONLY_NO_CERT_ENROLLED'}
 interactive_account_matches_local_admin=($account -ieq $expected -and
   [string]$identity.User.Value -ceq $expectedSid -and
   $who.IsInRole($adminRole) -and $sessionId -gt 0)
 windows_tpm_ready=$tpmReady
 provider_requested=$provider
 provider_metadata_readonly_checked=$providerReadOnly
 existing_key_platform_provider_matches=$providerExactPlatform
 existing_key_current_user_scope_matches=$userScopedKey
 existing_key_nonexportable_policy_matches=$exportPolicyNonExportable
 provider_metadata_not_external_attestation=$true
 store_location=$store
 certificate_present=($null -ne $cert)
 certificate_thumbprint_sha1=if($null -ne $cert){[string]$cert.Thumbprint}else{$null}
 certificate_der_sha256_public_pin_unapproved=$pin
 certificate_expires_utc=if($null -ne $cert){$cert.NotAfter.ToUniversalTime().ToString('o')}else{$null}
 private_key_exported=$false
 private_key_acl_independently_verified=$false
 tpm_hardware_attestation_independently_verified=$false
 originalhost_signed_receipt_generated=$false
 pin_externally_reviewed_and_approved=$false
 originalhost_runtime_identity_verified=$false
 six_e2e_release_proofs_credited=0
 cloud_cas_authorized=$false
 v3_task_modified=$false
 v2r4_modified=$false
 v3_paper_activated=$false
} | ConvertTo-Json -Depth 3
){
   throw 'V3_SIGNER_CMS_INVALID_BINDING_HASH'
  }
 }
 foreach($field in @('local_review_at_utc','reader_claimed_observed_at_utc')){
  $needle='"'+$field+'":"'
  $at=$raw.IndexOf($needle,[StringComparison]::Ordinal)
  if($at -lt 0 -or $raw.IndexOf($needle,$at+1,[StringComparison]::Ordinal) -ge 0){
   throw 'V3_SIGNER_CMS_NONCANONICAL_UTC'
  }
  $begin=$at+$needle.Length
  $end=$raw.IndexOf('"',$begin,[StringComparison]::Ordinal)
  if($end -le $begin -or
     $raw.Substring($begin,$end-$begin) -cnotmatch
       '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z
 status=if($Enroll){'MANUAL_TPM_KEY_ENROLLED_NOT_TRUSTED_FOR_RELEASE'}elseif($null -ne $cert){
  'READONLY_CERT_PRESENT_NOT_TRUSTED_FOR_RELEASE'
 }else{'READONLY_NO_CERT_ENROLLED'}
 interactive_account_matches_local_admin=($account -ieq $expected -and
   [string]$identity.User.Value -ceq $expectedSid -and
   $who.IsInRole($adminRole) -and $sessionId -gt 0)
 windows_tpm_ready=$tpmReady
 provider_requested=$provider
 provider_metadata_readonly_checked=$providerReadOnly
 existing_key_platform_provider_matches=$providerExactPlatform
 existing_key_current_user_scope_matches=$userScopedKey
 existing_key_nonexportable_policy_matches=$exportPolicyNonExportable
 provider_metadata_not_external_attestation=$true
 store_location=$store
 certificate_present=($null -ne $cert)
 certificate_thumbprint_sha1=if($null -ne $cert){[string]$cert.Thumbprint}else{$null}
 certificate_der_sha256_public_pin_unapproved=$pin
 certificate_expires_utc=if($null -ne $cert){$cert.NotAfter.ToUniversalTime().ToString('o')}else{$null}
 private_key_exported=$false
 private_key_acl_independently_verified=$false
 tpm_hardware_attestation_independently_verified=$false
 originalhost_signed_receipt_generated=$false
 pin_externally_reviewed_and_approved=$false
 originalhost_runtime_identity_verified=$false
 six_e2e_release_proofs_credited=0
 cloud_cas_authorized=$false
 v3_task_modified=$false
 v2r4_modified=$false
 v3_paper_activated=$false
} | ConvertTo-Json -Depth 3
){
   throw 'V3_SIGNER_CMS_NONCANONICAL_UTC'
  }
 }
 return $obj
}
# Protect the existing original Windows user account from UNC, reparse and
# overwrite mistakes. This does not assert administrator-independent ACLs.
function Assert-V3CmsLocalPath([string]$Path,[bool]$ExistingLeaf){
 if([string]::IsNullOrWhiteSpace($Path) -or
    -not [IO.Path]::IsPathRooted($Path)){throw 'V3_SIGNER_CMS_ABSOLUTE_PATH_REQUIRED'}
 $p=[IO.Path]::GetFullPath($Path)
 if($p.StartsWith('\\') -or $p.StartsWith('//')){
  throw 'V3_SIGNER_CMS_NETWORK_PATH_DENIED'
 }
 if($ExistingLeaf -and -not [IO.File]::Exists($p)){
  throw 'V3_SIGNER_CMS_INPUT_MISSING'
 }
 if(-not $ExistingLeaf -and [IO.File]::Exists($p)){
  throw 'V3_SIGNER_CMS_OUTPUT_REPLAY_NO_OVERWRITE'
 }
 $cursor=if($ExistingLeaf){$p}else{[IO.Path]::GetDirectoryName($p)}
 if(-not [IO.Directory]::Exists([IO.Path]::GetDirectoryName($p))){
  throw 'V3_SIGNER_CMS_PARENT_DIRECTORY_MISSING'
 }
 while(-not [string]::IsNullOrEmpty($cursor)){
  if([IO.File]::Exists($cursor) -or [IO.Directory]::Exists($cursor)){
   $info=Get-Item -LiteralPath $cursor -Force -ErrorAction Stop
   if(([int]$info.Attributes -band [int][IO.FileAttributes]::ReparsePoint) -ne 0){
    throw 'V3_SIGNER_CMS_REPARSE_PATH_DENIED'
   }
  }
  $parent=[IO.Path]::GetDirectoryName($cursor.TrimEnd('\'))
  if([string]::IsNullOrEmpty($parent) -or $parent -ceq $cursor){break}
  $cursor=$parent
 }
 return $p
}
if($SignPreinvoke){
 if(-not $providerReadOnly -or -not $tpmReady -or $null -eq $cert){
  throw 'V3_SIGNER_CMS_ORIGINAL_PROVIDER_NOT_VERIFIED'
 }
 if([IO.Path]::GetExtension($UnsignedPayloadPath) -cne '.json' -or
    [IO.Path]::GetExtension($DetachedCmsOutputPath) -cne '.cms'){
  throw 'V3_SIGNER_CMS_FILE_TYPE_HOLD'
 }
 $in=Assert-V3CmsLocalPath $UnsignedPayloadPath $true
 $out=Assert-V3CmsLocalPath $DetachedCmsOutputPath $false
 if($in -ceq $out){throw 'V3_SIGNER_CMS_INPUT_EQUALS_OUTPUT'}
 $length=(Get-Item -LiteralPath $in -ErrorAction Stop).Length
 if($length -lt 200 -or $length -gt 2048){
  throw 'V3_SIGNER_CMS_INPUT_FILE_BOUNDS'
 }
 $raw=[IO.File]::ReadAllBytes($in)
 $null=Test-V3UnsignedPreinvokeCandidate $raw
 # Exactly the pre-existing CurrentUser TPM key; no export or second key.
 # The CMS proves signing math only; no Cloud COMMIT/Reader/attempts/caller.
 $msg=[Security.Cryptography.Pkcs.ContentInfo]::new($raw)
 $cms=[Security.Cryptography.Pkcs.SignedCms]::new($msg,$true)
 $signer=[Security.Cryptography.Pkcs.CmsSigner]::new($cert)
 $signer.DigestAlgorithm=[Security.Cryptography.Oid]::new('2.16.840.1.101.3.4.2.1')
 $signer.IncludeOption=[Security.Cryptography.X509Certificates.X509IncludeOption]::EndCertOnly
 try{$cms.ComputeSignature($signer)}
 catch{throw 'V3_SIGNER_CMS_TPM_SIGNATURE_FAILURE_KEEP_ORIGINAL_KEY'}
 $encoded=[byte[]]$cms.Encode()
 if($encoded.Length -lt 64 -or $encoded.Length -gt 32768 -or
    $cms.SignerInfos.Count -ne 1){
  throw 'V3_SIGNER_CMS_SIGNATURE_SIZE_OR_SIGNER_COUNT_HOLD'
 }
 try{
  $verify=[Security.Cryptography.Pkcs.SignedCms]::new(
   [Security.Cryptography.Pkcs.ContentInfo]::new($raw),$true)
  $verify.Decode($encoded)
  if(-not $verify.Detached -or $verify.SignerInfos.Count -ne 1 -or
     [string]$verify.SignerInfos[0].DigestAlgorithm.Value -cne
       '2.16.840.1.101.3.4.2.1'){
   throw 'V3_SIGNER_CMS_READBACK_MISMATCH'
  }
  $verify.CheckSignature($true)
 }catch{throw 'V3_SIGNER_CMS_SELF_VERIFY_FAILURE_NO_FILE'}
 # Exclusive, one-shot output. Partial files intentionally remain on crash:
 # never silently remove, repair, overwrite or retry an uncertain attempt.
 try{
  $stream=[IO.FileStream]::new($out,[IO.FileMode]::CreateNew,
     [IO.FileAccess]::Write,[IO.FileShare]::None)
  try{$stream.Write($encoded,0,$encoded.Length);$stream.Flush($true)}
  finally{$stream.Dispose()}
 }catch{throw 'V3_SIGNER_CMS_OUTPUT_INCOMPLETE_OR_REPLAY_HOLD'}
 $h=[Security.Cryptography.SHA256]::Create()
 try{
  $payloadHash=([BitConverter]::ToString($h.ComputeHash($raw))).Replace('-','').ToLowerInvariant()
  $cmsHash=([BitConverter]::ToString($h.ComputeHash($encoded))).Replace('-','').ToLowerInvariant()
 }finally{$h.Dispose()}
 [pscustomobject][ordered]@{
  kind='V3_ORIGINALHOST_MANUAL_TPM_PREINVOKE_CMS_CANDIDATE_V1'
  status='ORIGINALHOST_CMS_SIGNED_CANDIDATE_NO_CLOUD_OR_CAS_AUTHORITY'
  payload_sha256=$payloadHash
  detached_cms_sha256=$cmsHash
  certificate_der_sha256_public_pin_unapproved=$pin
  existing_key_platform_provider_matches=$providerExactPlatform
  existing_key_current_user_scope_matches=$userScopedKey
  existing_key_nonexportable_policy_matches=$exportPolicyNonExportable
  originalhost_signed_cms_candidate_generated=$true
  original_reader_commit_authenticated_by_this_action=$false
  independent_offhost_custody_proven=$false
  cas_attempt_coverage_proven=$false
  precommit_restore_authorized=$false
  cloud_cas_authorized=$false
  old_writer_auto_rearm_allowed=$false
  v3_paper_activated=$false
 }|ConvertTo-Json -Depth 3
 return
}

[pscustomobject][ordered]@{
 kind='V3_ORIGINALHOST_MANUAL_TPM_PUBLIC_IDENTITY_V1'
 status=if($Enroll){'MANUAL_TPM_KEY_ENROLLED_NOT_TRUSTED_FOR_RELEASE'}elseif($null -ne $cert){
  'READONLY_CERT_PRESENT_NOT_TRUSTED_FOR_RELEASE'
 }else{'READONLY_NO_CERT_ENROLLED'}
 interactive_account_matches_local_admin=($account -ieq $expected -and
   [string]$identity.User.Value -ceq $expectedSid -and
   $who.IsInRole($adminRole) -and $sessionId -gt 0)
 windows_tpm_ready=$tpmReady
 provider_requested=$provider
 provider_metadata_readonly_checked=$providerReadOnly
 existing_key_platform_provider_matches=$providerExactPlatform
 existing_key_current_user_scope_matches=$userScopedKey
 existing_key_nonexportable_policy_matches=$exportPolicyNonExportable
 provider_metadata_not_external_attestation=$true
 store_location=$store
 certificate_present=($null -ne $cert)
 certificate_thumbprint_sha1=if($null -ne $cert){[string]$cert.Thumbprint}else{$null}
 certificate_der_sha256_public_pin_unapproved=$pin
 certificate_expires_utc=if($null -ne $cert){$cert.NotAfter.ToUniversalTime().ToString('o')}else{$null}
 private_key_exported=$false
 private_key_acl_independently_verified=$false
 tpm_hardware_attestation_independently_verified=$false
 originalhost_signed_receipt_generated=$false
 pin_externally_reviewed_and_approved=$false
 originalhost_runtime_identity_verified=$false
 six_e2e_release_proofs_credited=0
 cloud_cas_authorized=$false
 v3_task_modified=$false
 v2r4_modified=$false
 v3_paper_activated=$false
} | ConvertTo-Json -Depth 3
