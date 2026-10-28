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
# The new consumer is the EXISTING operator's cryptographically bound
# Notebook Reader transport, never a second CAS caller/STOP implementation.
$notebookConsumer=@($ast.FindAll({
 param($node)
 $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
 $node.Name -eq 'Test-V3SignedNotebookPrecommitInventory'
},$true))
if($notebookConsumer.Count -ne 1){throw 'V3_NOTEBOOK_READER_ORIGINALHOST_CONSUMER_MISSING'}
. ([scriptblock]::Create($notebookConsumer[0].Extent.Text))


# The SAME existing offline CMS/Notebook CI checks the real Reader's pure
# UTC-field helper. Never invoke the Reader's DB/DPAPI or the actual signer.
$notebookReader=Join-Path (Split-Path $PSScriptRoot -Parent) 'tools/v3-notebook-cas-audit-original-readonly-witness-INACTIVE.ps1'
$tokens=$null;$errors=$null
$readerAst=[System.Management.Automation.Language.Parser]::ParseFile(
 (Resolve-Path $notebookReader),[ref]$tokens,[ref]$errors)
if(@($errors).Count -ne 0){throw 'V3_NOTEBOOK_READER_SOURCE_AST_INVALID'}
$readerDefs=@($readerAst.FindAll({
 param($node)
 $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
 $node.Name -eq 'Read-V3ReaderUtcLiteral'
},$true))
if($readerDefs.Count -ne 1){throw 'V3_READER_UTC_LITERAL_FUNCTION_MISSING_OR_DUPLICATE'}
. ([scriptblock]::Create($readerDefs[0].Extent.Text))
$mockUtc='2026-10-28T06:58:19.743869Z'
$mockRow='{"observed_at_utc":"'+$mockUtc+'","opened_at_utc":"2026-10-28T06:57:19.123456Z","intent_created_at_utc":"2026-10-28T06:58:01.000001Z"}'
$parsedMock=$mockRow|ConvertFrom-Json
# DateTime JSON auto-coercion is deliberately NOT part of trusted input.
$parsed=Read-V3ReaderUtcLiteral -RawJson $mockRow -Name 'observed_at_utc'
if($parsed.text -cne $mockUtc -or
 $parsed.utc.Offset -ne [timespan]::Zero -or
 $parsed.utc.Year -ne 2026 -or
 $parsed.utc.Minute -ne 58 -or
 $parsed.utc.Millisecond -ne 743){
 throw 'V3_READER_UTC_CANONICAL_LITERAL_ACCEPTANCE_FAILED'
}
$opened=Read-V3ReaderUtcLiteral -RawJson $mockRow -Name 'opened_at_utc'
$created=Read-V3ReaderUtcLiteral -RawJson $mockRow -Name 'intent_created_at_utc'
if($opened.utc -ge $created.utc -or $created.utc -ge $parsed.utc){
 throw 'V3_READER_UTC_ORIGINAL_ORDER_INVALID'
}
$badRows=@(
 '{"observed_at_utc":"2026-10-28T06:58:19.743869+00:00"}',
 '{"observed_at_utc":"2026-10-28T06:58:19.743869z"}',
 '{"observed_at_utc":"2026-13-28T06:58:19.743869Z"}',
 '{"observed_at_utc":"2026-10-28T06:58:19Z"}',
 '{"observed_at_utc":"2026-10-28T06:58:19.743869Z","observed_at_utc":"2026-10-28T06:58:19.743869Z"}',
 '{"other_at_utc":"2026-10-28T06:58:19.743869Z"}',
 '{"observed_at_utc":"2026-10-28T06:58:19.743869\u005a"}'
)
foreach($mockBad in $badRows){
 $denied=$false
 try{Read-V3ReaderUtcLiteral -RawJson $mockBad -Name 'observed_at_utc'|Out-Null}
 catch{$denied=$true}
 if(-not $denied){throw 'V3_READER_UTC_BAD_LITERAL_ACCEPTED'}
}
$badFieldDenied=$false
try{Read-V3ReaderUtcLiteral -RawJson $mockRow -Name 'arbitrary_timestamp'|Out-Null}
catch{$badFieldDenied=$true}
if(-not $badFieldDenied){throw 'V3_READER_UTC_FOREIGN_FIELD_ACCEPTED'}
Write-Output 'V3_NOTEBOOK_READER_ORIGINAL_UTC_LITERAL_POSITIVE_NEGATIVES_PASS_NO_CAS'


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
  # A genuinely signed mock of the exact private Reader JSON is accepted as
  # a CURRENT inventory observation, never as CAS history or native authority.
  $observed=[datetimeoffset]::UtcNow.ToString(
   "yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'",[Globalization.CultureInfo]::InvariantCulture)
  $readerJson=([ordered]@{
   kind='V3_CAS_READER_CURRENT_PRIVATE_AUDIT_SNAPSHOT_V1'
   observed_at_utc=$observed
   actor='v3_cas_audit_reader_actor'
   role='v3_cas_audit_reader'
   epochs=0;intents=0;writer_role_access=$false;append_access=$false
   history_never_proven=$false;restore_authorized=$false
  }|ConvertTo-Json -Compress)
  function Sign-ReaderMock([string]$text,[Security.Cryptography.X509Certificates.X509Certificate2]$testCert){
   $b=[Text.Encoding]::UTF8.GetBytes($text)
   $c=[Security.Cryptography.Pkcs.SignedCms]::new(
    [Security.Cryptography.Pkcs.ContentInfo]::new([byte[]]$b),$true)
   $sign=[Security.Cryptography.Pkcs.CmsSigner]::new($testCert)
   $sign.DigestAlgorithm=[Security.Cryptography.Oid]::new('2.16.840.1.101.3.4.2.1')
   $c.ComputeSignature($sign)
   return ,([byte[]]$c.Encode())
  }
  $readerBytes=[Text.Encoding]::UTF8.GetBytes($readerJson)
  $readerCms=Sign-ReaderMock $readerJson $cert
  $readerGood=Test-V3SignedNotebookPrecommitInventory $readerBytes $readerCms $pin
  if($readerGood.status -cne 'SIGNED_CURRENT_PRIVATE_READER_EMPTY_SNAPSHOT_NOT_RELEASE' -or
     $readerGood.matched_signer_certificate_sha256 -ne $true -or
     $readerGood.current_private_reader_zero_counts_verified -ne $true -or
     $readerGood.historical_cas_never_verified -ne $false -or
     $readerGood.native_stop_or_restore_authorized -ne $false -or
     $readerGood.cloud_cas_dispatch_authorized -ne $false){
   throw 'V3_SIGNED_NOTEBOOK_READER_POSITIVE_WRONG_OR_EXCEEDS_AUTHORITY'
  }
  $altered=@(
   $readerJson.Replace('"epochs":0','"epochs":1'),
   $readerJson.Replace('v3_cas_audit_reader_actor','v3_cas_audit_writer_actor'),
   $readerJson.Replace('"restore_authorized":false','"restore_authorized":true'),
   $readerJson.Replace('"intents":0','"intents":0,"intents":0'),
   $readerJson.Replace('"kind":','"can_release":true,"kind":'),
   $readerJson.Replace($observed,'2026-10-01T00:00:00.000000Z')
  )
  # Each adverse JSON is VALIDLY signed by the same mock key: semantics must
  # independently reject privilege escalation, stale and duplicate fields.
  foreach($badText in $altered){
   $v=Test-V3SignedNotebookPrecommitInventory (
    [Text.Encoding]::UTF8.GetBytes($badText)) (Sign-ReaderMock $badText $cert) $pin
   if($v.current_private_reader_zero_counts_verified -ne $false -or
      $v.native_stop_or_restore_authorized -ne $false -or
      $v.cloud_cas_dispatch_authorized -ne $false){
    throw 'V3_SIGNED_NOTEBOOK_READER_SEMANTIC_NEGATIVE_ACCEPTED'
   }
  }
  $changed=[Text.Encoding]::UTF8.GetBytes($readerJson.Replace('"epochs":0','"epochs":2'))
  $wrong=Test-V3SignedNotebookPrecommitInventory $changed $readerCms $pin
  $badPin=Test-V3SignedNotebookPrecommitInventory $readerBytes $readerCms ('0'*64)
  foreach($v in @($wrong,$badPin)){
   if($v.matched_signer_certificate_sha256 -ne $false -or
      $v.current_private_reader_zero_counts_verified -ne $false -or
      $v.cloud_cas_dispatch_authorized -ne $false){
    throw 'V3_SIGNED_NOTEBOOK_READER_CRYPTO_NEGATIVE_ACCEPTED'
   }
  }
  Write-Output 'V3_NOTEBOOK_READER_PINNED_CMS_TO_EXISTING_ORIGINALHOST_OFFLINE_PASS_NO_RELEASE'
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
  if($proposalObject.kind -cne 'V3_CAS_PREINVOKE_UNSIGNED_PROPOSAL_V2' -or
     $proposalObject.proof_status -cne 'UNTRUSTED_READER_PROPOSAL_NOT_AUTHENTICATED' -or
     $proposalObject.ordinal -ne 1 -or
      [string]$proposalObject.caller_acl_sha256 -cne ('e'*64) -or
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
   # Use the EXISTING real local spool O_EXCL/fsync writer to emit one
   # canonical first intent plus sticky UNKNOWN into this disposable CI dir.
   $witness=Join-Path $tmp 'original-local-unknown'
   [void][IO.Directory]::CreateDirectory($witness)
   $fixtureAgain=@(& python -B $fixturePath --test-local-unknown-dir $witness)
   if($LASTEXITCODE -ne 0 -or $fixtureAgain.Count -ne 1){
    throw 'V3_NOTEBOOK_OFFHOST_UNKNOWN_ORIGINAL_FIXTURE_FAILED'
   }
   $entryPath=Join-Path $witness '000001.json'
   $unknownPath=Join-Path $witness 'cas-attempt-unknown.json'
   $wrongUnknown=Join-Path $tmp 'wrong-unknown.json'
   $tamperedUnknown=[IO.File]::ReadAllText($unknownPath,[Text.Encoding]::ASCII).Replace(
     'UNKNOWN_BEFORE_POSSIBLE_RPC','NOT_INVOKED')
   [IO.File]::WriteAllText($wrongUnknown,$tamperedUnknown,[Text.Encoding]::ASCII)
   $denied=$false
   try{
    & $notebookArchiveTool -Aktion VersuchSpeichern -IntentDatei $entryPath -UnknownDatei $wrongUnknown -ZertifikatSha256 $pin -Ablage $archive | Out-Null
   }catch{$denied=$true}
   if(-not $denied){throw 'V3_NOTEBOOK_OFFHOST_UNKNOWN_TAMPER_ACCEPTED'}
   if(@(Get-ChildItem -LiteralPath $archive -Force).Count -ne 3){
    throw 'V3_NOTEBOOK_OFFHOST_UNKNOWN_EARLY_WRITE'
   }
   $savedUnknown=(& $notebookArchiveTool -Aktion VersuchSpeichern -IntentDatei $entryPath -UnknownDatei $unknownPath -ZertifikatSha256 $pin -Ablage $archive) | ConvertFrom-Json -ErrorAction Stop
   if($savedUnknown.local_unknown_chain_offhost_copy_verified -ne $true -or
      $savedUnknown.exclusive_cas_attempt_coverage_proven -ne $false -or
      $savedUnknown.independent_immutable_external_custody_proven -ne $false -or
      $savedUnknown.cas_execute_erlaubt -ne $false -or
      $savedUnknown.v2r4_rearm_erlaubt -ne $false){
    throw 'V3_NOTEBOOK_OFFHOST_UNKNOWN_COPY_FALSE_AUTHORITY'
   }
   $reopenedUnknown=(& $notebookArchiveTool -Aktion Pruefen -ZertifikatSha256 $pin -Ablage $archive) | ConvertFrom-Json -ErrorAction Stop
   if($reopenedUnknown.local_unknown_chain_offhost_copy_verified -ne $true -or
      @(Get-ChildItem -LiteralPath $archive -Force).Count -ne 6){
    throw 'V3_NOTEBOOK_OFFHOST_UNKNOWN_REOPEN_INVALID'
   }
   $denied=$false
   try{
    & $notebookArchiveTool -Aktion VersuchSpeichern -IntentDatei $entryPath -UnknownDatei $unknownPath -ZertifikatSha256 $pin -Ablage $archive | Out-Null
   }catch{$denied=$true}
   if(-not $denied){throw 'V3_NOTEBOOK_OFFHOST_UNKNOWN_REPLAY_ACCEPTED'}
   Write-Output 'V3_NOTEBOOK_OFFHOST_UNKNOWN_REAL_LOCAL_PAIR_COPY_NEGATIVES_PASS_NO_CAS'
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


# Pure originalhost candidate payload validator, extracted by AST. Never run
# original script, key enrollment, SignPreinvoke, file I/O or Cloud.
$signerPath=Join-Path (Split-Path $PSScriptRoot -Parent) 'tools/v3-paper-originalhost-manual-tpm-enroll-INACTIVE.ps1'
$st=$null;$se=$null
$sa=[System.Management.Automation.Language.Parser]::ParseFile(
 (Resolve-Path $signerPath),[ref]$st,[ref]$se)
if(@($se).Count -ne 0){throw 'V3_TPM_SIGNER_CANDIDATE_AST_INVALID'}
$checkFn=@($sa.FindAll({
 param($n)
 $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
 $n.Name -eq 'Test-V3UnsignedPreinvokeCandidate'
},$true))
if($checkFn.Count -ne 1){throw 'V3_TPM_SIGNER_CANDIDATE_VALIDATOR_MISSING'}
. ([scriptblock]::Create($checkFn[0].Extent.Text))
$sample='{"caller_acl_sha256":"'+('e'*64)+'","epoch_id":"V3CAS-AUDIT-11111111111111111111111111111111","fence_sha256":"'+('a'*64)+'","intent_id":"11111111-1111-4111-8111-111111111111","intent_sha256":"'+('b'*64)+'","kind":"V3_CAS_PREINVOKE_UNSIGNED_PROPOSAL_V2","local_review_at_utc":"2026-10-28T09:30:00Z","ordinal":1,"predecessor_series_id":"PAPER-V2R4-20261009T110135Z","proof_status":"UNTRUSTED_READER_PROPOSAL_NOT_AUTHENTICATED","readback_sha256":"'+('c'*64)+'","reader_claimed_observed_at_utc":"2026-10-28T09:29:30Z","request_sha256":"'+('d'*64)+'","rpc":"public.rotate_v2r4_to_v3_experimental_paper","source_sha256":"'+('e'*64)+'"}'
$sampleBytes=[Text.Encoding]::UTF8.GetBytes($sample)
$parsed=Test-V3UnsignedPreinvokeCandidate $sampleBytes
if([string]$parsed.kind -cne 'V3_CAS_PREINVOKE_UNSIGNED_PROPOSAL_V2'){
 throw 'V3_TPM_CMS_INPUT_STRICT_POSITIVE_HOLD'
}
foreach($bad in @(
 $sample.Replace('UNTRUSTED_READER_PROPOSAL_NOT_AUTHENTICATED','AUTHENTICATED'),
 $sample.Replace('"ordinal":1','"ordinal":2'),
 $sample.Replace('PAPER-V2R4-20261009T110135Z','PAPER-V2R4-OTHER'),
 $sample.Replace('"kind":','"cloud_cas_authorized":true,"kind":'),
 $sample.Replace('"fence_sha256":"'+('a'*64)+'"','"fence_sha256":"INVALID"'),
 $sample.Replace('"caller_acl_sha256":"'+('e'*64)+'"','"caller_acl_sha256":"INVALID"')
)){
 $rejected=$false
 try{$null=Test-V3UnsignedPreinvokeCandidate ([Text.Encoding]::UTF8.GetBytes($bad))}
 catch{$rejected=$true}
 if(-not $rejected){throw 'V3_TPM_CMS_INPUT_NEGATIVE_NOT_REJECTED'}
}
Write-Output 'V3_TPM_SIGNED_PREINVOKE_CANDIDATE_PURE_SOURCE_VALIDATOR_PASS'
