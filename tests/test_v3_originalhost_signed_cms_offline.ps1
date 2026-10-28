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
  # Never rely on platform-specific defaults; use explicitly SHA-256.
  $signer.DigestAlgorithm=[System.Security.Cryptography.Oid]::new('2.16.840.1.101.3.4.2.1')
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
  # Attempted self-authorization: this is a perfectly valid detached CMS
  # signed by the SAME ephemeral CI key. The arbitrary signed JSON falsely
  # claims SYSTEM exclusion, approved signer role and release/Cloud authority.
  # Crypto math may pass; it must NEVER mint trust, proofs or activation.
  $hostileBytes=[System.Text.Encoding]::UTF8.GetBytes(
   '{"system_key_access_denied":true,"signer_role_approved":true,"six_actual_e2e_proofs_credited":6,"cloud_cas_authorized":true,"v3_paper_release_authorized":true}'
  )
  $hostileContent=[System.Security.Cryptography.Pkcs.ContentInfo]::new(
   [byte[]]$hostileBytes)
  $hostileCms=[System.Security.Cryptography.Pkcs.SignedCms]::new(
   $hostileContent,$true)
  $hostileSigner=[System.Security.Cryptography.Pkcs.CmsSigner]::new($cert)
  $hostileSigner.DigestAlgorithm=[System.Security.Cryptography.Oid]::new(
   '2.16.840.1.101.3.4.2.1')
  $hostileCms.ComputeSignature($hostileSigner)
  $hostileResult=Test-V3IndependentOriginalHostCmsSignature (
   [byte[]]$hostileBytes) ([byte[]]$hostileCms.Encode()) $pin
  if($hostileResult.crypto_signature_valid -ne $true -or
     $hostileResult.originalhost_key_acl_and_signer_role_proven -ne $false -or
     $hostileResult.originalhost_process_or_loaded_bytes_independently_proven -ne $false -or
     $hostileResult.cloud_cas_authorized -ne $false -or
     $hostileResult.v3_paper_release_authorized -ne $false -or
     $hostileResult.six_actual_e2e_proofs_credited -ne 0){
   throw 'V3_SELF_SIGNED_CMS_IS_NOT_INDEPENDENT_RELEASE_AUTHORITY'
  }
  $tampered=[System.Text.Encoding]::UTF8.GetBytes('{"not_originalhost":false,"release_authority":false}')
  $otherPin='0'*64
  # Physical Originalhost public DER candidate: NOT an approved release key.
  # The prior recorded fingerprint mistakenly contained ...f586668....
  $physicalCandidateUnapproved='ce256281af6d36eb883dd2cb34594d0f2231e32a33f58e668d327814c7cfdb40'
  $oldTranscriptionInvalid='ce256281af6d36eb883dd2cb34594d0f2231e32a33f586668d327814c7cfdb40'
  if($physicalCandidateUnapproved -ceq $oldTranscriptionInvalid -or
     $physicalCandidateUnapproved -cnotmatch '^[0-9a-f]{64}$'){
   throw 'V3_PUBLIC_CERT_CANDIDATE_TRANSCRIPTION_INVALID'
  }
  # The offline synthetic signer must not match either physical public pin.
  # SHA-1 CMS signed with the same test key is denied even if crypto matches.
  $weakCms=[System.Security.Cryptography.Pkcs.SignedCms]::new($message,$true)
  $weakSigner=[System.Security.Cryptography.Pkcs.CmsSigner]::new($cert)
  $weakSigner.DigestAlgorithm=[System.Security.Cryptography.Oid]::new('1.3.14.3.2.26')
  $weakSignature=$null
  try {
   $weakCms.ComputeSignature($weakSigner)
   $weakSignature=[byte[]]$weakCms.Encode()
  } catch [System.Security.Cryptography.CryptographicException] {
   # Hardened runners may refuse SHA-1 generation before the verifier sees it.
  }
  if($null -ne $weakSignature){
   $weakResult=Test-V3IndependentOriginalHostCmsSignature $raw $weakSignature $pin
   if($weakResult.crypto_signature_valid -ne $false -or
      $weakResult.v3_paper_release_authorized -ne $false){
    throw 'V3_SHA1_CMS_DIGEST_DOWNGRADE_ACCEPTED'
   }
  }
  $badCms=[byte[]]$signed.Clone()
  $badCms[[math]::Floor($badCms.Length/2)]=(
   $badCms[[math]::Floor($badCms.Length/2)] -bxor 1)
  $bad=@(
   (Test-V3IndependentOriginalHostCmsSignature $tampered $signed $pin),
   (Test-V3IndependentOriginalHostCmsSignature $raw $signed $otherPin),
   (Test-V3IndependentOriginalHostCmsSignature $raw $signed $physicalCandidateUnapproved),
   (Test-V3IndependentOriginalHostCmsSignature $raw $signed $oldTranscriptionInvalid),
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
  # INTEGRATION TEST: consume the TRUE Python preinvoke candidate's exact
  # canonical bytes, not a hand-transcribed mock CMS payload. This fixture
  # calls the existing locked Python AuditIntent/Readback builder, NOT Cloud,
  # originalhost TPM, runner, paper writer or new credential service.
  $fixturePath=Join-Path $PSScriptRoot 'v3_cas_preinvoke_cms_bytes_fixture_INACTIVE.py'
  $fixtureOutput=@(& python -B $fixturePath)
  if($LASTEXITCODE -ne 0 -or $fixtureOutput.Count -ne 1){
   throw 'V3_CI_CANONICAL_PYTHON_BYTES_NOT_EMITTED'
  }
  $fixtureObject=$fixtureOutput[0] | ConvertFrom-Json -AsHashtable -ErrorAction Stop
  if($fixtureObject.Count -ne 7 -or
     $fixtureObject.kind -cne 'V3_CI_CANONICAL_PREINVOKE_BYTES_ONLY_NOT_REAL_CUSTODY' -or
     $fixtureObject.is_production_signer -ne $false -or
     $fixtureObject.independent_cloud_reader_proven -ne $false -or
     $fixtureObject.cas_dispatch_authorized -ne $false -or
     $fixtureObject.v3_paper_release_authorized -ne $false -or
     [string]$fixtureObject.payload_sha256 -cnotmatch '^[a-f0-9]{64}$'){
   throw 'V3_CI_PREINVOKE_PYTHON_FIXTURE_SCOPE_INVALID'
  }
  $proposalBytes=[Convert]::FromBase64String([string]$fixtureObject.payload_base64)
  if($proposalBytes.Length -lt 250 -or $proposalBytes.Length -gt 2048){
   throw 'V3_CI_PREINVOKE_CANONICAL_BYTES_OUTSIDE_LIMIT'
  }
  $proposalHash=[System.Security.Cryptography.SHA256]::Create()
  try{
   $proposalDigest=([BitConverter]::ToString(
    $proposalHash.ComputeHash($proposalBytes))).Replace('-','').ToLowerInvariant()
  }finally{$proposalHash.Dispose()}
  if($proposalDigest -cne [string]$fixtureObject.payload_sha256){
   throw 'V3_CI_PREINVOKE_PYTHON_DOTNET_DIGEST_DIVERGENCE'
  }
  $proposalText=[Text.Encoding]::UTF8.GetString($proposalBytes)
  $proposalObject=$proposalText | ConvertFrom-Json -AsHashtable -ErrorAction Stop
  if($proposalObject.kind -cne 'V3_CAS_PREINVOKE_UNSIGNED_PROPOSAL_V1' -or
     $proposalObject.proof_status -cne 'UNTRUSTED_READER_PROPOSAL_NOT_AUTHENTICATED' -or
     $proposalObject.ordinal -ne 1 -or
     $proposalObject.predecessor_series_id -cne 'PAPER-V2R4-20261009T110135Z' -or
     $proposalObject.rpc -cne 'public.rotate_v2r4_to_v3_experimental_paper'){
   throw 'V3_CI_PREINVOKE_UNSIGNED_SCOPE_DIVERGENCE'
  }
  $proposalCms=[System.Security.Cryptography.Pkcs.SignedCms]::new(
    [System.Security.Cryptography.Pkcs.ContentInfo]::new([byte[]]$proposalBytes),$true)
  $proposalSigner=[System.Security.Cryptography.Pkcs.CmsSigner]::new($cert)
  $proposalSigner.DigestAlgorithm=[System.Security.Cryptography.Oid]::new(
    '2.16.840.1.101.3.4.2.1')
  $proposalCms.ComputeSignature($proposalSigner)
  $proposalSignature=[byte[]]$proposalCms.Encode()
  $bridgeResult=Test-V3IndependentOriginalHostCmsSignature (
    [byte[]]$proposalBytes) $proposalSignature $pin
  if($bridgeResult.crypto_signature_valid -ne $true -or
     $bridgeResult.originalhost_process_or_loaded_bytes_independently_proven -ne $false -or
     $bridgeResult.originalhost_key_acl_and_signer_role_proven -ne $false -or
     $bridgeResult.cloud_cas_authorized -ne $false -or
     $bridgeResult.v3_paper_release_authorized -ne $false -or
     $bridgeResult.six_actual_e2e_proofs_credited -ne 0){
   throw 'V3_CI_PYTHON_DOTNET_CMS_CROSS_LANGUAGE_MUST_NEVER_AUTHORIZE'
  }
  $mutated=[byte[]]$proposalBytes.Clone()
  $mutated[$mutated.Length - 1] = ($mutated[$mutated.Length - 1] -bxor 1)
  foreach($badBridge in @(
   (Test-V3IndependentOriginalHostCmsSignature $mutated $proposalSignature $pin),
   (Test-V3IndependentOriginalHostCmsSignature $proposalBytes $proposalSignature ('0'*64)),
   (Test-V3IndependentOriginalHostCmsSignature $proposalBytes ([byte[]]@()) $pin)
  )){
   if($badBridge.crypto_signature_valid -ne $false -or
      $badBridge.cloud_cas_authorized -ne $false -or
      $badBridge.v3_paper_release_authorized -ne $false){
    throw 'V3_CI_PYTHON_PREINVOKE_CMS_MUTATION_OR_WRONG_PIN_ACCEPTED'
   }
  }
  # Reuse the SAME disposable CI-signed canonical Python receipt bytes.
  # This is a one-time notebook OFF-HOST copy, not a second TPM test or CAS.
  $notebookArchiveTool=Join-Path (Split-Path $PSScriptRoot -Parent) 'tools/v3-cas-notebook-cms-archive-INACTIVE.ps1'
  $tmp=Join-Path ([IO.Path]::GetTempPath()) ('v3-cms-notebook-'+[guid]::NewGuid().ToString('N'))
  $archive=Join-Path $tmp 'separate-notebook-copy'
  $receiptFile=Join-Path $tmp 'preinvoke.json'
  $cmsFile=Join-Path $tmp 'preinvoke.cms'
  try{
   [void][IO.Directory]::CreateDirectory($tmp)
   [IO.File]::WriteAllBytes($receiptFile,$proposalBytes)
   [IO.File]::WriteAllBytes($cmsFile,$proposalSignature)
   $stored=(& $notebookArchiveTool -Aktion Speichern -BelegDatei $receiptFile -CmsDatei $cmsFile -ZertifikatSha256 $pin -Ablage $archive) | ConvertFrom-Json -ErrorAction Stop
   if($stored.status -cne 'V3_CAS_NOTEBOOK_SIGNED_COPY_CRYPTO_VALID_ONLY' -or
      $stored.offhost_copy_readback -ne $true -or
      $stored.cryptographic_signature_checked -ne $true -or
      $stored.cas_execute_erlaubt -ne $false -or
      $stored.independent_immutable_external_custody_proven -ne $false -or
      $stored.exclusive_cas_attempt_coverage_proven -ne $false -or
      $stored.v2r4_rearm_erlaubt -ne $false -or
      $stored.v3_paper_freigabe -ne $false){
    throw 'V3_NOTEBOOK_SIGNED_COPY_TRUST_BOUNDARY_INCORRECT'
   }
   $reloaded=(& $notebookArchiveTool -Aktion Pruefen -ZertifikatSha256 $pin -Ablage $archive) | ConvertFrom-Json -ErrorAction Stop
   if($reloaded.payload_sha256 -cne $stored.payload_sha256){
    throw 'V3_NOTEBOOK_SIGNED_COPY_RESTART_DRIFT'
   }
   $replayDenied=$false
   try{
    & $notebookArchiveTool -Aktion Speichern -BelegDatei $receiptFile -CmsDatei $cmsFile -ZertifikatSha256 $pin -Ablage $archive | Out-Null
   }catch{$replayDenied=$true}
   if(-not $replayDenied){throw 'V3_NOTEBOOK_SIGNED_COPY_REPLAY_ACCEPTED'}
   $badPinDenied=$false
   try{
    & $notebookArchiveTool -Aktion Pruefen -ZertifikatSha256 ('0'*64) -Ablage $archive | Out-Null
   }catch{$badPinDenied=$true}
   if(-not $badPinDenied){throw 'V3_NOTEBOOK_SIGNED_COPY_WRONG_PIN_ACCEPTED'}
   [IO.File]::AppendAllText((Join-Path $archive 'voraufruf.json'),' ',[Text.Encoding]::ASCII)
   $tamperDenied=$false
   try{
    & $notebookArchiveTool -Aktion Pruefen -ZertifikatSha256 $pin -Ablage $archive | Out-Null
   }catch{$tamperDenied=$true}
   if(-not $tamperDenied){throw 'V3_NOTEBOOK_SIGNED_COPY_TAMPER_ACCEPTED'}
   Write-Output 'V3_NOTEBOOK_ORIGINAL_CMS_SIGNED_COPY_ARCHIVE_POSITIVE_NEGATIVES_NO_CAS_PASS'
  }finally{
   if([IO.Directory]::Exists($tmp)){[IO.Directory]::Delete($tmp,$true)}
  }

  Write-Output 'V3_PYTHON_PREINVOKE_TO_DOTNET_DETACHED_CMS_BYTES_PASS_NO_AUTHORITY'
  Write-Output 'V3_ORIGINALHOST_DETACHED_CMS_OFFLINE_POSITIVE_NEGATIVES_PASS_NO_AUTHORITY'
 } finally {$cert.Dispose()}
} finally {$rsa.Dispose()}
