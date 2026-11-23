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
 # Execute exact, bounded portions of candidate ASTs. The production setup,
 # credential lookup and final effectful operator dispatch are outside these ranges.
 function Get-PinnedAst($Name,$Hash) {
  $file = Join-Path $PSScriptRoot "ap05a-fixtures/$Name"
  if ((Get-FileHash -LiteralPath $file).Hash -ine $Hash) { throw "AP05A_CANDIDATE_HASH_HOLD $Name" }
  $tokens = $null
  $errors = $null
  $ast = [Management.Automation.Language.Parser]::ParseFile($file,[ref]$tokens,[ref]$errors)
  if ($errors.Count) { throw "AP05A_CANDIDATE_PARSE_HOLD $Name" }
  $ast
 }
 function Get-Range($Ast,$First,$Last) {
  $statements = @($Ast.EndBlock.Statements)
  $result = [Collections.Generic.List[string]]::new()
  $started = $false
  foreach ($statement in $statements) {
   $line = $statement.Extent.Text
   if ($line.StartsWith($First,[StringComparison]::Ordinal)) { $started = $true }
   if ($started) { $result.Add($line) }
   if ($started -and $line.StartsWith($Last,[StringComparison]::Ordinal)) { return ($result -join "`n") }
  }
  throw "AP05A_CANDIDATE_RANGE_HOLD $First $Last"
 }
 $nb = Get-PinnedAst 'Notebook-Phase.ps1' '45327fe0ae53411ffd7161aa4082752264d774dfcfd64b1bb085369f5911c364'
 $pc = Get-PinnedAst 'MiniPC-Phase.ps1' 'fc4d126ef9d2fe6ce953035dfaac3f9d8a0c80556cec95d76ec5f03d49304eac'
 $functions = Get-Range $nb 'function Digest' 'function Assert-Cms'
 . ([scriptblock]::Create($functions))
 $producer = [scriptblock]::Create(
  (Get-Range $nb '$rules = @{' '$rule = ') + "`n" +
  (Get-Range $nb 'Assert-Cms $readBytes' 'Write-Output $path'))
 $consumer = [scriptblock]::Create((Get-Range $pc '$rules = @{' 'Write-Exact (Join-Path $phase ''reader.cms'')'))
 $root = Split-Path -Parent $ReaderJson
 $handoff = Join-Path $root 'ap05a-handoff'
 [void][IO.Directory]::CreateDirectory($handoff)
 $WindowDirectory = $root
 $utf8 = [Text.UTF8Encoding]::new($false,$true)
 $id = 'V3-ONETIME-' + $EpochId.Substring(12)
 $releaseId = $id
 $fixtureArtifacts = @{}
 foreach ($n in 1..10) { $fixtureArtifacts["tools/ap05a-test-$n.ps1"] = Get-V3ReleaseSha256 ($utf8.GetBytes([string]$n)) }
 $expected = $fixtureArtifacts.Clone()
 $pins = @{
  'supabase/v3-cas-audit-stage4-followup-release.sql'='3cb150387ee4569b9826bbf5e4091ccf78981a44c0c3bbf83faeef959fc7002f'
  'supabase/v3-experimental-paper-atomic-cas-INACTIVE-20261013.sql'='989e1657e03867774907f3a1ec9c9f4f84ee70c2d4b7a258cad9dc3e480f0043'
  'tools/v3-one-time-paper-release.ps1'='aecd031a189bd6431b8d6f2656f2c2b8bc7c2bcfbd287d6ef636b082e5b3f68c'
  'tools/v3-one-time-release.ps1'='fe3d55e0299a7cd83647a6fed4580cb3956dda062402dd2e79f24cc88aae07d8'
 }
 foreach ($key in $pins.Keys) {
  $fixtureArtifacts[$key] = '0' * 64
  $expected[$key] = $pins[$key]
 }
 $fixed = @{repo_sha=$Release;artifacts=[pscustomobject]$fixtureArtifacts}
 $end = $now.AddMinutes(3)
 $runtimeBytes = $utf8.GetBytes('{"fixture":"prepare-runtime"}')
 [IO.File]::WriteAllBytes((Join-Path $root 'runtime-spec.json'),$runtimeBytes)
 $prepareApproval = $null
 foreach ($Phase in @('Prepare','Stop')) {
  $planHash = Get-V3ReleaseSha256 ($utf8.GetBytes((@{phase=$Phase;repo_sha=$Release;cas_epoch=$epoch} | ConvertTo-Json -Compress)))
  $wire = $utf8.GetString($raw).TrimEnd()
  if (-not $wire.EndsWith('}') -or $null -ne $row.PSObject.Properties['plan_sha256'] -or
      $null -ne $row.PSObject.Properties['release_id']) { throw 'AP05A_READER_ENVELOPE_HOLD' }
  $join = @{release_id=$id;plan_sha256=$planHash} | ConvertTo-Json -Compress
  $readBytes = $utf8.GetBytes($wire.Substring(0,$wire.Length-1)+','+$join.Substring(1))
  $readCms = Sign-Bytes $readBytes $readerCert
  # Inject only the temporary certificate-store lookup. The candidate still
  # checks identity/validity and itself creates the CMS and writes the transfer.
  $NotebookTransfer = & {
   function Get-ChildItem([string]$Path) {
    if ($Path -cne 'Cert:\CurrentUser\My') { throw 'AP05A_UNEXPECTED_CERT_PATH' }
    $authorityCert
   }
   & $producer
  }
  $Mode = 'Paper' + $Phase
  $paths = & {
   . $consumer
   $phase
  }
  $approvalBytes = Read-V3ReleaseLocalBytes (Join-Path $paths 'approval.json')
  $approvalCms = Read-V3ReleaseLocalBytes (Join-Path $paths 'approval.cms')
  $scope = 'V3_PAPER_' + $Phase.ToUpperInvariant()
  $verify = @{Scope=$scope;ReviewedAuthorityCertificateSha256=$authorityPin;ExpectedReleaseCommit=$Release;ExpectedArtifacts=$expected}
  $auth = Assert-V3OneTimeReleaseAuthorization -Payload $approvalBytes -Cms $approvalCms @verify
  if ($auth.claims.bindings.plan_sha256 -cne $planHash -or
      ($Phase -eq 'Prepare' -and $auth.claims.bindings.runtime_spec_sha256 -cne (Get-V3ReleaseSha256 $runtimeBytes))) {
   throw 'AP05A_CANDIDATE_PLAN_BINDING_HOLD'
  }
  $received = Read-V3PaperIndependentReceipt ([pscustomobject]@{commit=$Release;authorization=$auth}) (Join-Path $paths 'reader.json') (Join-Path $paths 'reader.cms') (Get-V3ReleaseSha256 $readBytes)
  Assert-V3PaperEpochReceipt $received $epoch
  if ($received.state -cne $row.state -or [string]$received.observed_at_utc -cne [string]$row.observed_at_utc) { throw 'AP05A_READER_ASSERTION_DRIFT' }
  if ($Phase -eq 'Prepare') { $prepareApproval = @{Payload=$approvalBytes;Cms=$approvalCms} }
  else {
   $rejected = $false
   try { $null = Assert-V3OneTimeReleaseAuthorization @prepareApproval @verify }
   catch {
    if ($_.Exception.Message -cne 'V3_RELEASE_SCOPE_OR_IDENTITY_HOLD') { throw }
    $rejected = $true
   }
   if (-not $rejected) { throw 'AP05A_CROSS_SCOPE_ACCEPTED' }
  }
  "AP05A_CANDIDATE_TRANSFER_ORIGINAL_VERIFIER_PASS $scope"
 }
}
finally {
 foreach ($resource in @($readerCert,$authorityCert,$readerKey,$authorityKey)) {
  if ($null -ne $resource) { $resource.Dispose() }
 }
}
