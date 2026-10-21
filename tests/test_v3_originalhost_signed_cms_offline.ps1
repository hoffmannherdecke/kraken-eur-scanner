# This is an OFFLINE cryptographic signature primitive test only.
# Extract the pure verification function by AST. NEVER source/execute the
# actual Mini-PC cutover operator, task, Cloud client or any release path.
$ErrorActionPreference='Stop'
$ps=Join-Path (Split-Path $PSScriptRoot -Parent) 'tools/minipc-v3-paper-cutover-operator-INACTIVE.ps1'
$tokens=$null;$errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile(
 (Resolve-Path $ps),[ref]$tokens,[ref]$errors)
if(@($errors).Count -ne 0){throw 'V3_OPERATOR_AST_INVALID'}
$defs=@($ast.FindAll({
 param($node)
 $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
 $node.Name -eq 'Test-V3IndependentOriginalHostCmsSignature'
},$true))
if($defs.Count -ne 1){throw 'V3_INDEPENDENT_SIGNED_ORIGINAL_FUNCTION_MISSING_OR_DUPLICATE'}
. ([scriptblock]::Create($defs[0].Extent.Text))

# Only a short-lived, CI-generated PRIVATE key signs MOCK data. No material
# from the production Mini-PC, release certificates, tokens or credentials.
$rsa=[System.Security.Cryptography.RSA]::Create(2048)
try {
 $request=[System.Security.Cryptography.X509Certificates.CertificateRequest]::new(
  'CN=V3-CI-NOT-A-RELEASE-OWNER',$rsa,
  [System.Security.Cryptography.HashAlgorithmName]::SHA256,
  [System.Security.Cryptography.RSASignaturePadding]::Pkcs1)
 $cert=$request.CreateSelfSigned(
  [datetimeoffset]::UtcNow.AddMinutes(-2),
  [datetimeoffset]::UtcNow.AddMinutes(10))
 try {
  $raw=[System.Text.Encoding]::UTF8.GetBytes('{"not_originalhost":true,"release_authority":false}')
  $message=[System.Security.Cryptography.Pkcs.ContentInfo]::new([byte[]]$raw)
  $cms=[System.Security.Cryptography.Pkcs.SignedCms]::new($message,$true)
  $signer=[System.Security.Cryptography.Pkcs.CmsSigner]::new($cert)
  $cms.ComputeSignature($signer)
  $signed=[byte[]]$cms.Encode()
  $sha=[System.Security.Cryptography.SHA256]::Create()
  try {
   $pin=([BitConverter]::ToString($sha.ComputeHash([byte[]]$cert.RawData))).Replace('-','').ToLowerInvariant()
  } finally {$sha.Dispose()}
  $ok=Test-V3IndependentOriginalHostCmsSignature $raw $signed $pin
  if($ok.crypto_signature_valid -ne $true -or
     $ok.v3_paper_release_authorized -ne $false -or
     $ok.cloud_cas_authorized -ne $false -or
     $ok.six_actual_e2e_proofs_credited -ne 0 -or
     $ok.originalhost_process_or_loaded_bytes_independently_proven -ne $false){
   throw 'V3_VALID_CRYPTO_IS_NOT_AUTHORIZED_RELEASE'
  }
  $tampered=[System.Text.Encoding]::UTF8.GetBytes('{"not_originalhost":false,"release_authority":false}')
  $otherPin='0'*64
  $badCms=[byte[]]$signed.Clone()
  $badCms[[math]::Floor($badCms.Length/2)]=(
   $badCms[[math]::Floor($badCms.Length/2)] -bxor 1)
  $bad=@(
   (Test-V3IndependentOriginalHostCmsSignature $tampered $signed $pin),
   (Test-V3IndependentOriginalHostCmsSignature $raw $signed $otherPin),
   (Test-V3IndependentOriginalHostCmsSignature $raw $badCms $pin),
   (Test-V3IndependentOriginalHostCmsSignature $raw $signed 'INVALID'),
   (Test-V3IndependentOriginalHostCmsSignature ([byte[]]@()) $signed $pin),
   (Test-V3IndependentOriginalHostCmsSignature $raw ([byte[]]@()) $pin)
  )
  foreach($item in $bad){
   if($item.crypto_signature_valid -ne $false -or
      $item.v3_paper_release_authorized -ne $false -or
      $item.cloud_cas_authorized -ne $false){
    throw 'V3_INVALID_CMS_OR_PIN_ACCEPTED'
   }
  }
  Write-Output 'V3_ORIGINALHOST_DETACHED_CMS_OFFLINE_POSITIVE_NEGATIVES_PASS_NO_AUTHORITY'
 } finally {$cert.Dispose()}
} finally {$rsa.Dispose()}
