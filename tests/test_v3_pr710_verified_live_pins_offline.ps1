# PR710: offline genuine triple detached CMS before short-lived SHA binding.
# Synthetic ephemeral certificates only. No Notebook, Originalhost or Cloud access.
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$root=Split-Path $PSScriptRoot -Parent
Import-Module (Join-Path $root 'tools/v3-one-time-release-authorization.psm1') -Force
$scriptPath=Join-Path $root 'tools/v3-poststop-triple-reader-window-INACTIVE.ps1'
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($scriptPath,[ref]$tokens,[ref]$errors)
if(@($errors).Count){throw 'PR710_COORDINATOR_SYNTAX_HOLD'}
$fn=@($ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and
 $n.Name -eq 'Get-V3PostStopVerifiedLivePins'},$true))
if($fn.Count -ne 1){throw 'PR710_PIN_BINDER_FUNCTION_COUNT_HOLD'}
$rsa=@();$certs=@()
try{
 for($i=0;$i -lt 3;$i++){
  $key=[Security.Cryptography.RSA]::Create(2048)
  $req=[Security.Cryptography.X509Certificates.CertificateRequest]::new(
   "CN=PR710-OFFLINE-TEST-$i",$key,
   [Security.Cryptography.HashAlgorithmName]::SHA256,
   [Security.Cryptography.RSASignaturePadding]::Pkcs1)
  $cert=$req.CreateSelfSigned([datetimeoffset]::UtcNow.AddMinutes(-1),
    [datetimeoffset]::UtcNow.AddMinutes(15))
  $rsa+=,$key;$certs+=,$cert
 }
 $originPin=Get-V3ReleaseSha256 $certs[0].RawData
 # The production coordinator retains its owner-admitted hardcoded TPM pin.
 # Substitute only the isolated AST function body in this ephemeral test process.
 $fnText=$fn[0].Extent.Text.Replace(
  'ce256281af6d36eb883dd2cb34594d0f2231e32a33f58e668d327814c7cfdb40',
  $originPin)
 if($fnText -ceq $fn[0].Extent.Text){throw 'PR710_PRODUCTION_ORIGIN_PIN_MISSING'}
 . ([scriptblock]::Create($fnText))
 function New-TestCms([byte[]]$Bytes,[Security.Cryptography.X509Certificates.X509Certificate2]$Cert){
  $msg=[Security.Cryptography.Pkcs.ContentInfo]::new($Bytes)
  $cms=[Security.Cryptography.Pkcs.SignedCms]::new($msg,$true)
  $signer=[Security.Cryptography.Pkcs.CmsSigner]::new($Cert)
  $signer.DigestAlgorithm=[Security.Cryptography.Oid]::new('2.16.840.1.101.3.4.2.1')
  $cms.ComputeSignature($signer)
  return [byte[]]$cms.Encode()
 }
 $hostBytes=[Text.Encoding]::UTF8.GetBytes(('H'*510))
 $cloudBytes=[Text.Encoding]::UTF8.GetBytes(('C'*580))
 $originCms=New-TestCms $hostBytes $certs[0]
 $notebookCms=New-TestCms $hostBytes $certs[1]
 $cloudCms=New-TestCms $cloudBytes $certs[2]
 $policy=[pscustomobject]@{
  series_id='PAPER-V3-20261111T105211Z'
  epoch_id='V3CAS-AUDIT-f27cce0ba68043b480e4f97698dd2901'
  source_sha256=('a'*64)
  epoch_fence_sha256=('b'*64)
  caller_acl_sha256=('c'*64)
  local_fence_file_sha256=('d'*64)
  candidates_xml_sha256=('e'*64)
  wait_xml_sha256=('f'*64)
  cloudsync_xml_sha256=('1'*64)
  writer_xml_sha256=('2'*64)
  host_certificate_sha256=(Get-V3ReleaseSha256 $certs[1].RawData)
  cloud_certificate_sha256=(Get-V3ReleaseSha256 $certs[2].RawData)
  owner_review_sha256=('5'*64)
  observation_nonce='0123456789abcdef0123456789abcdef'
 }
 $params=@{Approved=$policy;HostPayload=$hostBytes;OriginalHostCms=$originCms;
  NotebookHostCms=$notebookCms;CloudPayload=$cloudBytes;CloudCms=$cloudCms}
 $pins=Get-V3PostStopVerifiedLivePins @params
 if($pins.host_payload_sha256 -cne (Get-V3ReleaseSha256 $hostBytes) -or
    $pins.cloud_payload_sha256 -cne (Get-V3ReleaseSha256 $cloudBytes) -or
    $pins.host_certificate_sha256 -cne $policy.host_certificate_sha256 -or
    $pins.observation_nonce -cne $policy.observation_nonce){
  throw 'PR710_VERIFIED_LIVE_PIN_POSITIVE_HOLD'
 }
 function Expect-Hold([hashtable]$Inputs){
  $failed=$false
  try{$null=Get-V3PostStopVerifiedLivePins @Inputs}catch{$failed=$true}
  if(-not $failed){throw 'PR710_UNTRUSTED_LIVE_DIGEST_OR_CMS_ACCEPTED'}
 }
 $altered=[byte[]]$hostBytes.Clone();$altered[1]=[byte]0x41
 $bad=$params.Clone();$bad.HostPayload=$altered;Expect-Hold $bad
 $bad=$params.Clone();$bad.NotebookHostCms=$cloudCms;Expect-Hold $bad
 $bad=$params.Clone();$bad.CloudCms=$notebookCms;Expect-Hold $bad
 $bad=$params.Clone();$bad.OriginalHostCms=$notebookCms;Expect-Hold $bad
 $policy|Add-Member -NotePropertyName host_payload_sha256 -NotePropertyValue ('0'*64)
 $bad=$params.Clone();$bad.Approved=$policy;Expect-Hold $bad
 Write-Output 'PR710_THREE_INDEPENDENT_REAL_CMS_BEFORE_EPHEMERAL_SHA_PASS'
}finally{
 foreach($cert in $certs){$cert.Dispose()}
 foreach($key in $rsa){$key.Dispose()}
}
