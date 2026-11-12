# One-shot POST-STOP UNKNOWN Notebook issuer. Separate scoped CMS authorization.
[CmdletBinding()]
param(
 [ValidateSet('Abort','Readback')][string]$Mode,
 [string]$PackageRoot,[string]$ApprovalJson,[string]$ApprovalCms,
 [string]$AuthorityAdmissionJson,[string]$ExpectedAuthorityAdmissionSha256,
 [string]$ExpectedReleaseCommit,[string]$ApprovedPinsJson,
 [string]$HostJson,[string]$OriginalHostCms,[string]$NotebookHostCms,
 [string]$CloudJson,[string]$CloudCms,[string]$TerminalJson,
 [string]$TerminalCms,[string]$CaFile=''
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($env:OS -cne 'Windows_NT' -or $env:COMPUTERNAME -ceq 'MINI-PC' -or
 $env:GITHUB_ACTIONS -eq 'true' -or -not [Environment]::UserInteractive){
 throw 'V3_POSTSTOP_NOTEBOOK_INTERACTIVE_ONLY_HOLD'
}
Import-Module (Join-Path $PSScriptRoot 'v3-one-time-release-authorization.psm1') -Force
. (Join-Path $PSScriptRoot 'v3-post-stop-unknown-quarantine-source-only.ps1')
$epoch='V3CAS-AUDIT-f27cce0ba68043b480e4f97698dd2901'
$inventory=Get-V3OneTimeReleaseArtifactInventory $PackageRoot
foreach($rel in @('tools/v3-poststop-issuer-release.ps1',
 'tools/v3-post-stop-unknown-quarantine-source-only.ps1',
 'tools/v3-poststop-notebook-reader-extension-INACTIVE.ps1')){
 $inventory[$rel]=Get-V3ReleaseSha256 (Read-V3ReleaseLocalBytes (Join-Path $PackageRoot $rel) 1048576)
}
$admission=Read-V3ReleaseLocalBytes $AuthorityAdmissionJson
$authorityPin=Assert-V3ReleaseAuthorityAdmission -Bytes $admission -ExpectedSha256 $ExpectedAuthorityAdmissionSha256 -ReleaseCommit $ExpectedReleaseCommit
$auth=Assert-V3OneTimeReleaseAuthorization -Payload (Read-V3ReleaseLocalBytes $ApprovalJson) -Cms (Read-V3ReleaseLocalBytes $ApprovalCms 32768) -ReviewedAuthorityCertificateSha256 $authorityPin -Scope 'CLOUD_POSTSTOP_TERMINAL_ABORT' -ExpectedReleaseCommit $ExpectedReleaseCommit -ExpectedArtifacts $inventory
$b=$auth.claims.bindings
$required=@('epoch_id','source_sha256','fence_sha256','caller_acl_sha256','pins_sha256')
if(@($b.PSObject.Properties.Name).Count -ne $required.Count -or
 @($b.PSObject.Properties.Name|Where-Object {$_ -cnotin $required}).Count){
 throw 'V3_POSTSTOP_AUTH_BINDINGS_HOLD'
}
if([string]$b.epoch_id -cne $epoch -or
 [string]$b.source_sha256 -cne '8b27c2392c2c8165660a40e15f5ab896c99da39befcd2201e43220acaa2e1251' -or
 [string]$b.fence_sha256 -cne '4f01704d20375bf201f87c56eb350a67c1a91f82535296b28ae318768aa213ef' -or
 [string]$b.caller_acl_sha256 -cne '6f0d59c57f3f7ce3d54f5c674c0d41c342a2a08b9a86001e59353d772f5f66f0'){
 throw 'V3_POSTSTOP_AUTH_EXACT_TARGET_HOLD'
}
$pinsBytes=Read-V3ReleaseLocalBytes $ApprovedPinsJson
if([string]$b.pins_sha256 -cne (Get-V3ReleaseSha256 $pinsBytes)){throw 'V3_POSTSTOP_APPROVED_PINS_BYTES_HOLD'}
$pins=Read-V3ReleaseJson $pinsBytes
if([string]$pins.epoch_id -cne $epoch -or
 [string]$pins.source_sha256 -cne [string]$b.source_sha256 -or
 [string]$pins.epoch_fence_sha256 -cne [string]$b.fence_sha256 -or
 [string]$pins.caller_acl_sha256 -cne [string]$b.caller_acl_sha256){
 throw 'V3_POSTSTOP_PINS_AUTH_DRIFT_HOLD'
}
if($Mode -eq 'Readback'){
 $receiptInput=[pscustomobject]@{kind='V3_POSTSTOP_CURRENT_CUSTODY_SOURCE_REVIEW_V1';independently_signed_current_custody=$true;epoch_id=$epoch;host_payload_sha256=[string]$pins.host_payload_sha256;cloud_payload_sha256=[string]$pins.cloud_payload_sha256;owner_review_sha256=[string]$pins.owner_review_sha256}
 $receiptSha=Get-V3PostStopCurrentCustodyReceiptSha256 $receiptInput
 $terminal=Assert-V3PostStopSignedTerminalCloud -Payload (Read-V3ReleaseLocalBytes $TerminalJson 8192) -Cms (Read-V3ReleaseLocalBytes $TerminalCms 32768) -Pins $pins -CurrentCustodyReceiptSha256 $receiptSha
 [pscustomobject]@{kind='TARGET_EPOCH_TERMINALIZED';epoch_id=$epoch;terminal_cloud_abort_confirmed=$terminal.terminal_cloud_abort_confirmed;stage4_authorized=$false;writer_authorized=$false}|ConvertTo-Json -Compress
 return
}
$hostBytes=Read-V3ReleaseLocalBytes $HostJson 8192
$cloudBytes=Read-V3ReleaseLocalBytes $CloudJson 8192
$receiptInput=@{
 HostPayload=$hostBytes;OriginalHostCms=(Read-V3ReleaseLocalBytes $OriginalHostCms 32768)
 NotebookHostCms=(Read-V3ReleaseLocalBytes $NotebookHostCms 32768)
 CloudPayload=$cloudBytes;CloudCms=(Read-V3ReleaseLocalBytes $CloudCms 32768)
 Pins=$pins;Now=[datetimeoffset]::UtcNow
}
$review=Assert-V3PostStopOwnerAdmittedCurrentHostTripleCms @receiptInput
if($review.current_custody_contract_verified -ne $true -or
 $review.recovery_authorized -ne $false -or $review.writer_authorized -ne $false){
 throw 'V3_POSTSTOP_CURRENT_CUSTODY_HOLD'
}
$custody=Assert-V3PostStopUnknownCurrentCustody -HostPayload $hostBytes -HostCms $receiptInput.NotebookHostCms -CloudPayload $cloudBytes -CloudCms $receiptInput.CloudCms -Pins $pins
$receiptSha=Get-V3PostStopCurrentCustodyReceiptSha256 $custody
if([string]$pins.host_payload_sha256 -cne (Get-V3ReleaseSha256 $hostBytes) -or [string]$pins.cloud_payload_sha256 -cne (Get-V3ReleaseSha256 $cloudBytes)){throw 'V3_POSTSTOP_CURRENT_RECEIPT_PIN_HOLD'}
$plan=Get-V3PostStopCloudAbortCandidate -Custody $custody -Pins $pins -CurrentCustodyReceiptSha256 $receiptSha -Expiry $auth.expires_at
if($plan.execution_authorized -ne $false){throw 'V3_POSTSTOP_CANDIDATE_AUTH_CONFUSION_HOLD'}
$issuerRoot=Join-Path $env:LOCALAPPDATA 'V3CasIndependentIssuer'
Add-Type -AssemblyName System.Security
$raw=$null;$password=$null
try{
 $raw=[Security.Cryptography.ProtectedData]::Unprotect(
  (Read-V3ReleaseLocalBytes (Join-Path $issuerRoot 'issuer-currentuser.dpapi') 8192),
  [Text.Encoding]::ASCII.GetBytes('V3_CAS_INDEPENDENT_ISSUER_NOTEBOOK_V1'),
  [Security.Cryptography.DataProtectionScope]::CurrentUser)
 $secret=[Text.Encoding]::ASCII.GetString($raw)
 if($secret -cnotmatch '^[a-f0-9]{64}$'){throw 'V3_POSTSTOP_ISSUER_SECRET_HOLD'}
 $password=ConvertTo-SecureString $secret -AsPlainText -Force
}finally{if($null -ne $raw){[Array]::Clear($raw,0,$raw.Length)};$secret=$null}
try{
 $latch=Join-Path $issuerRoot 'poststop-f27cce0ba68043b480e4f97698dd2901-attempted'
 $transport={
  param([byte[]]$Payload)
  $sql=[Text.UTF8Encoding]::new($false,$true).GetString($Payload)
  $null=Invoke-V3ReleasePg -Sql $sql -Password $password -Ca $CaFile -Actor 'v3_cas_inhibit_issuer_actor'
 }
 $out=Invoke-V3PostStopCloudOnceCandidate -LatchPath $latch -PlanBytes ([Text.UTF8Encoding]::new($false).GetBytes([string]$plan.sql)) -Transport $transport
 $out|ConvertTo-Json -Compress
}finally{if($null -ne $password){$password.Dispose()}}
# Successful dispatch never equals independent terminal readback. No retry.
