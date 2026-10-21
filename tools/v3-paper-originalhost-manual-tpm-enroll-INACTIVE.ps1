param(
 [switch]$Enroll,
 [string]$Approval=''
)
# Original V3 Paper release owner #99: MANUAL credential enrolment only.
# NO automated receipt signer, no V3 Paper approval, no Task/Cloud/Trading
# writes. The private key is TPM-backed and non-exportable *if* the original
# Windows Platform Crypto Provider reports success. Never fall back to a
# software provider or silently generate a second certificate.
# CurrentUser\My is the interactive local ADMIN profile, NOT LocalMachine,
# CryptoSupportSvc or SYSTEM's profile. The signer MUST NOT be callable by
# V3 SYSTEM Paper Task. ADMIN/SYSTEM device-level compromise still breaks
# logical independence: the future release authority must be reviewed
# externally and independent runtime/process checks remain necessary.
$ErrorActionPreference='Stop'
$subject='CN=V3-PAPER-ORIGINALHOST-MANUAL-TPM-20261021'
$store='Cert:\CurrentUser\My'
$provider='Microsoft Platform Crypto Provider'
$confirmation='ENROLL_MANUAL_TPM_SIGNING_KEY_NO_V3_RELEASE'
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
$expected=$env:COMPUTERNAME+'\ADMIN'
if($account -ine $expected -or [string]$identity.User.Value -eq 'S-1-5-18' -or
   -not [Environment]::UserInteractive){
 throw 'V3_SIGNER_MUST_BE_INTERACTIVE_LOCAL_ADMIN_NOT_SYSTEM_OR_RUNNER'
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
[pscustomobject][ordered]@{
 kind='V3_ORIGINALHOST_MANUAL_TPM_PUBLIC_IDENTITY_V1'
 status=if($Enroll){'MANUAL_TPM_KEY_ENROLLED_NOT_TRUSTED_FOR_RELEASE'}elseif($null -ne $cert){
  'READONLY_CERT_PRESENT_NOT_TRUSTED_FOR_RELEASE'
 }else{'READONLY_NO_CERT_ENROLLED'}
 interactive_account_matches_local_admin=($account -ieq $expected)
 windows_tpm_ready=$tpmReady
 provider_requested=$provider
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
