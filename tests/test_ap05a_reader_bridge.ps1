param(
 [Parameter(Mandatory=$true)][string]$ReaderJson,
 [Parameter(Mandatory=$true)][string]$EpochId,
 [Parameter(Mandatory=$true)][string]$Release,
 [Parameter(Mandatory=$true)][string]$Source,
 [Parameter(Mandatory=$true)][string]$Fence,
 [Parameter(Mandatory=$true)][string]$Acl
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$tools = Join-Path (Split-Path $PSScriptRoot -Parent) 'tools'
Import-Module (Join-Path $tools 'v3-one-time-release-authorization.psm1') -Scope Local
. (Join-Path $tools 'v3-one-time-paper-release.ps1')
if ($null -eq ('System.Security.Cryptography.Pkcs.SignedCms' -as [type])) {
 Add-Type -AssemblyName System.Security
}
$epoch = @{epoch_id=$EpochId;source_sha256=$Source;fence_sha256=$Fence;caller_acl_sha256=$Acl}
if ($EpochId -cnotmatch '^V3CAS-AUDIT-[a-f0-9]{32}$' -or $Release -cnotmatch '^[a-f0-9]{40}$') { throw 'AP05A_FIXTURE_IDENTITY_HOLD' }
foreach ($hash in @($Source,$Fence,$Acl)) {
 if ($hash -cnotmatch '^[a-f0-9]{64}$') { throw 'AP05A_FIXTURE_HASH_HOLD' }
}
$raw = Read-V3ReleaseLocalBytes $ReaderJson
$row = Read-V3ReleaseJson $raw
Assert-V3PaperEpochReceipt $row $epoch
if ($row.state -cne 'PRESTOP_INHIBITED_OLD_ONLY_NO_ATTEMPTS' -or $row.release_commit -cne $Release) {
 throw 'AP05A_PG_READER_STATE_OR_RELEASE_HOLD'
}
$now = [DateTimeOffset]::UtcNow
$age = ($now - [DateTimeOffset]::Parse([string]$row.observed_at_utc)).TotalSeconds
if ($age -lt 0 -or $age -gt 75) { throw 'AP05A_PG_READER_FRESHNESS_HOLD' }
"PG17_READER_EVIDENCE_PASS SHA256=$(Get-V3ReleaseSha256 $raw)"
function Sign-Bytes([byte[]]$Bytes,$Cert) {
 $cms = [Security.Cryptography.Pkcs.SignedCms]::new([Security.Cryptography.Pkcs.ContentInfo]::new($Bytes),$true)
 $signer = [Security.Cryptography.Pkcs.CmsSigner]::new($Cert)
 $signer.DigestAlgorithm = [Security.Cryptography.Oid]::new('2.16.840.1.101.3.4.2.1')
 $cms.ComputeSignature($signer)
 return ,$cms.Encode()
}
$readerKey = $authorityKey = $readerCert = $authorityCert = $null
try {
 $readerKey = [Security.Cryptography.RSA]::Create(2048)
 $authorityKey = [Security.Cryptography.RSA]::Create(2048)
 $readerReq = [Security.Cryptography.X509Certificates.CertificateRequest]::new('CN=AP05A isolated Reader',$readerKey,[Security.Cryptography.HashAlgorithmName]::SHA256,[Security.Cryptography.RSASignaturePadding]::Pkcs1)
 $authorityReq = [Security.Cryptography.X509Certificates.CertificateRequest]::new('CN=AP05A isolated Authority',$authorityKey,[Security.Cryptography.HashAlgorithmName]::SHA256,[Security.Cryptography.RSASignaturePadding]::Pkcs1)
 $readerCert = $readerReq.CreateSelfSigned($now.AddMinutes(-1),$now.AddMinutes(5))
 $authorityCert = $authorityReq.CreateSelfSigned($now.AddMinutes(-1),$now.AddMinutes(5))
 $readerPin = Get-V3ReleaseSha256 $readerCert.RawData
 $authorityPin = Get-V3ReleaseSha256 $authorityCert.RawData
 if ($readerPin -ceq $authorityPin) { throw 'AP05A_FIXTURE_SIGNERS_NOT_DISTINCT' }
 $artifacts = @{
  'tools/v3-one-time-release-authorization.psm1' = (Get-FileHash (Join-Path $tools 'v3-one-time-release-authorization.psm1')).Hash.ToLowerInvariant()
  'tools/v3-one-time-paper-release.ps1' = (Get-FileHash (Join-Path $tools 'v3-one-time-paper-release.ps1')).Hash.ToLowerInvariant()
 }
 $releaseId = 'V3-ONETIME-' + $EpochId.Substring(12)
 $utf8 = [Text.UTF8Encoding]::new($false)
 foreach ($phase in @('PREPARE','STOP')) {
  # These are separate local fixture plans. No signed claim rewrites the database fields.
  $planBytes = $utf8.GetBytes((@{phase=$phase;repo_sha=$Release;cas_epoch=$epoch} | ConvertTo-Json -Compress))
  $planSha = Get-V3ReleaseSha256 $planBytes
  foreach ($field in @('release_id','plan_sha256')) {
   if ($null -ne $row.PSObject.Properties[$field]) { throw 'AP05A_UNEXPECTED_READER_ENVELOPE_FIELD' }
  }
  $wire = $utf8.GetString($raw).TrimEnd()
  if (-not $wire.EndsWith('}')) { throw 'AP05A_READER_ENVELOPE_HOLD' }
  $bindingsJson = @{release_id=$releaseId;plan_sha256=$planSha} | ConvertTo-Json -Compress
  $receiptBytes = $utf8.GetBytes($wire.Substring(0,$wire.Length-1) + ',' + $bindingsJson.Substring(1))
  $receiptFile = "$ReaderJson.$phase.json"
  $cmsFile = "$ReaderJson.$phase.cms"
  [IO.File]::WriteAllBytes($receiptFile,$receiptBytes)
  [IO.File]::WriteAllBytes($cmsFile,(Sign-Bytes $receiptBytes $readerCert))
  $scope = "V3_PAPER_$phase"
  $claims = @{
   kind='V3_ONE_TIME_RELEASE_AUTHORIZATION_V1';release_id=$releaseId;scope=$scope
   base_commit='5b1789e349b157d06d3109c5f0ff10d95154bf81';release_commit=$Release
   not_before_utc=$now.AddSeconds(-5).ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
   expires_at_utc=$now.AddMinutes(2).ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
   project_ref='nlgzjmqgwueojlyqmoru';computer_name='MINI-PC';trading_root='C:\Users\ADMIN\Trading'
   artifacts=$artifacts;bindings=@{plan_sha256=$planSha;reader_certificate_sha256=$readerPin}
  }
  $payload = $utf8.GetBytes(($claims | ConvertTo-Json -Depth 10 -Compress))
  $cms = Sign-Bytes $payload $authorityCert
  $auth = Assert-V3OneTimeReleaseAuthorization -Payload $payload -Cms $cms -Scope $scope -ReviewedAuthorityCertificateSha256 $authorityPin -ExpectedReleaseCommit $Release -ExpectedArtifacts $artifacts
  $verified = Read-V3PaperIndependentReceipt ([pscustomobject]@{commit=$Release;authorization=$auth}) $receiptFile $cmsFile ''
  Assert-V3PaperEpochReceipt $verified $epoch
  if ($verified.state -cne $row.state -or [string]$verified.observed_at_utc -cne [string]$row.observed_at_utc) { throw 'AP05A_READER_ASSERTION_DRIFT' }
  "AP05A_PG17_READER_ORIGINAL_VERIFIER_SCOPE_PASS $scope"
 }
}
finally {
 foreach ($resource in @($readerCert,$authorityCert,$readerKey,$authorityKey)) {
  if ($null -ne $resource) { $resource.Dispose() }
 }
}
