# Shared authorization boundary for the existing #99 one-time release.
# No credentials, database, scheduler or marker operations in this module.
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

function Get-V3ReleaseSha256([byte[]]$Bytes) {
 $hash=[Security.Cryptography.SHA256]::Create()
 try {return ([BitConverter]::ToString($hash.ComputeHash($Bytes))).Replace('-','').ToLowerInvariant()}
 finally {$hash.Dispose()}
}

function Read-V3ReleaseJson([byte[]]$Bytes) {
 if($null -eq $Bytes -or $Bytes.Length -lt 2 -or $Bytes.Length -gt 65536){throw 'V3_RELEASE_JSON_SIZE_HOLD'}
 $wire=[Text.UTF8Encoding]::new($false,$true).GetString($Bytes)
 # Restrict field names to literal ASCII. This disallows escaped-key aliases
 # as well as duplicate properties at any nesting level before deserialization.
 $keys=[regex]::Matches($wire,'"(?<key>(?:[^"\\]|\\.)*)"\s*:')
 foreach($key in $keys){
  if($key.Groups['key'].Value -cnotmatch '^[A-Za-z0-9_./-]+$'){throw 'V3_RELEASE_JSON_KEY_HOLD'}
 }
 if(@($keys|Group-Object {$_.Groups['key'].Value}|Where-Object Count -gt 1).Count){throw 'V3_RELEASE_DUPLICATE_KEY_HOLD'}
 $value=$wire|ConvertFrom-Json -ErrorAction Stop
 if($value -isnot [pscustomobject]){throw 'V3_RELEASE_JSON_OBJECT_HOLD'}
 return $value
}

function Assert-V3ReleaseCms([byte[]]$Payload,[byte[]]$Cms,[string]$ReviewedAuthorityCertificateSha256) {
 if($ReviewedAuthorityCertificateSha256 -cnotmatch '^[a-f0-9]{64}$' -or
    $null -eq $Cms -or $Cms.Length -lt 32 -or $Cms.Length -gt 32768){throw 'V3_RELEASE_AUTHORITY_PIN_OR_CMS_HOLD'}
 # Windows PowerShell 5.1 resolves SignedCms from System.Security; modern
 # PowerShell uses the separate Pkcs assembly. Reuse the built-in framework.
 if($null -eq ('System.Security.Cryptography.Pkcs.SignedCms' -as [type])){
  Add-Type -AssemblyName System.Security -ErrorAction Stop
 }
 if($null -eq ('System.Security.Cryptography.Pkcs.SignedCms' -as [type])){
  Add-Type -AssemblyName System.Security.Cryptography.Pkcs -ErrorAction Stop
 }
 $signed=[Security.Cryptography.Pkcs.SignedCms]::new([Security.Cryptography.Pkcs.ContentInfo]::new($Payload),$true)
 $signed.Decode($Cms)
 if(-not $signed.Detached -or $signed.SignerInfos.Count -ne 1){throw 'V3_RELEASE_SINGLE_DETACHED_SIGNER_REQUIRED'}
 $signer=$signed.SignerInfos[0]
 $cert=$signer.Certificate
 if($null -eq $cert -or [string]$signer.DigestAlgorithm.Value -cne '2.16.840.1.101.3.4.2.1' -or
    (Get-V3ReleaseSha256 $cert.RawData) -cne $ReviewedAuthorityCertificateSha256 -or
    $cert.NotBefore.ToUniversalTime() -gt [datetime]::UtcNow -or
    $cert.NotAfter.ToUniversalTime() -lt [datetime]::UtcNow){throw 'V3_RELEASE_SIGNER_OR_VALIDITY_HOLD'}
 # Mathematical verification against the independently reviewed exact DER pin.
 # A caller-selected certificate is NOT an independently approved trust root.
 $signed.CheckSignature($true)
}

function Assert-V3OneTimeReleaseAuthorization {
 param([byte[]]$Payload,[byte[]]$Cms,[string]$ReviewedAuthorityCertificateSha256,
       [ValidateSet('CLOUD_ABORT_INSTALL','ORIGINALHOST_ABORT_RESTORE','ORIGINALHOST_ABORT_RECONCILE','CLOUD_STAGE4_EPOCH_OPEN','CLOUD_PREPARED_FENCE_ABORT')][string]$Scope,
       [string]$ExpectedReleaseCommit,[hashtable]$ExpectedArtifacts,
       [datetimeoffset]$Now=[datetimeoffset]::UtcNow)
 Assert-V3ReleaseCms $Payload $Cms $ReviewedAuthorityCertificateSha256
 $a=Read-V3ReleaseJson $Payload
 $fields=@('kind','release_id','scope','base_commit','release_commit','not_before_utc',
           'expires_at_utc','project_ref','computer_name','trading_root','artifacts','bindings')
 $actual=@($a.PSObject.Properties.Name)
 if($actual.Count -ne $fields.Count -or @($actual|Where-Object {$_ -cnotin $fields}).Count){throw 'V3_RELEASE_APPROVAL_FIELDS_HOLD'}
 if([string]$a.kind -cne 'V3_ONE_TIME_RELEASE_AUTHORIZATION_V1' -or
    [string]$a.release_id -cnotmatch '^V3-ONETIME-[a-f0-9]{32}$' -or
    [string]$a.scope -cne $Scope -or
    [string]$a.base_commit -cne '5b1789e349b157d06d3109c5f0ff10d95154bf81' -or
    $ExpectedReleaseCommit -cnotmatch '^[a-f0-9]{40}$' -or
    [string]$a.release_commit -cne $ExpectedReleaseCommit -or
    [string]$a.project_ref -cne 'nlgzjmqgwueojlyqmoru' -or
    [string]$a.computer_name -cne 'MINI-PC' -or
    [string]$a.trading_root -cne 'C:\Users\ADMIN\Trading'){
  throw 'V3_RELEASE_SCOPE_OR_IDENTITY_HOLD'
 }
 $times=@{}
 # Read the original JSON literals: PowerShell 7 can coerce ISO dates.
 foreach($field in @('not_before_utc','expires_at_utc')){
  $m=[regex]::Match([Text.Encoding]::UTF8.GetString($Payload),'"'+$field+'"\s*:\s*"(?<t>[^"\\]*)"')
  $at=[datetimeoffset]::MinValue
  if(-not $m.Success -or -not [datetimeoffset]::TryParseExact($m.Groups['t'].Value,
     "yyyy-MM-dd'T'HH:mm:ss'Z'",[Globalization.CultureInfo]::InvariantCulture,
     [Globalization.DateTimeStyles]::AssumeUniversal,[ref]$at)){throw 'V3_RELEASE_APPROVAL_TIME_FORMAT_HOLD'}
  $times[$field]=$at
 }
 if($times.expires_at_utc -le $times.not_before_utc -or
    ($times.expires_at_utc-$times.not_before_utc).TotalMinutes -gt 15 -or
    $Now -lt $times.not_before_utc -or $Now -ge $times.expires_at_utc){throw 'V3_RELEASE_APPROVAL_EXPIRED_OR_FUTURE_HOLD'}
 if($a.artifacts -isnot [pscustomobject] -or $null -eq $ExpectedArtifacts -or $ExpectedArtifacts.Count -lt 2 -or
    @($a.artifacts.PSObject.Properties).Count -ne $ExpectedArtifacts.Count){throw 'V3_RELEASE_ARTIFACT_SET_HOLD'}
 foreach($path in $ExpectedArtifacts.Keys){
  if($path -cnotmatch '^(tools|supabase)/[A-Za-z0-9_./-]+$' -or $path.Contains('..') -or
     [string]$ExpectedArtifacts[$path] -cnotmatch '^[a-f0-9]{64}$' -or
     [string]$a.artifacts.$path -cne [string]$ExpectedArtifacts[$path]){throw 'V3_RELEASE_ARTIFACT_HASH_HOLD'}
 }
 if($a.bindings -isnot [pscustomobject]){throw 'V3_RELEASE_BINDINGS_HOLD'}
 return [pscustomobject]@{claims=$a;approval_sha256=(Get-V3ReleaseSha256 $Payload);
                         expires_at=$times.expires_at_utc}
}

function Read-V3ReleaseLocalBytes([string]$Path,[int]$MaxBytes=65536) {
 if(-not [IO.Path]::IsPathRooted($Path) -or $Path.StartsWith('\\') -or $Path.StartsWith('//')){
  throw 'V3_RELEASE_LOCAL_PATH_REQUIRED'
 }
 $full=[IO.Path]::GetFullPath($Path)
 $walk=$full
 while($walk){
  $item=Get-Item -LiteralPath $walk -Force -ErrorAction Stop
  if([bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'V3_RELEASE_REPARSE_PATH_HOLD'}
  $walk=[IO.Path]::GetDirectoryName($walk)
 }
 $item=Get-Item -LiteralPath $full -Force -ErrorAction Stop
 if($item.PSIsContainer -or $item.Length -lt 1 -or $item.Length -gt $MaxBytes){throw 'V3_RELEASE_FILE_SIZE_HOLD'}
 return ,[IO.File]::ReadAllBytes($full)
}

function Get-V3OneTimeReleaseArtifactInventory([string]$PackageRoot) {
 $paths=@('tools/v3-one-time-release.ps1','tools/v3-one-time-release-authorization.psm1',
  'tools/v3-one-time-originalhost-release.psm1','tools/check-minipc-v3-physical-writer-readiness.ps1',
  'tools/minipc-v3-paper-cutover-operator-INACTIVE.ps1',
  'supabase/v3-cas-prepared-fence-abort-INACTIVE.sql',
  'supabase/v3-cas-prepared-fence-abort-release.sql',
  'supabase/v3-cas-prepared-fence-abort-release-readback.sql')
 $out=@{}
 foreach($path in $paths){
  $out[$path]=Get-V3ReleaseSha256 (Read-V3ReleaseLocalBytes -Path (Join-Path $PackageRoot $path) -MaxBytes 1048576)
 }
 return $out
}

function Assert-V3ReleaseAuthorityAdmission([byte[]]$Bytes,[string]$ExpectedSha256,[string]$ReleaseCommit) {
 if($ExpectedSha256 -cnotmatch '^[a-f0-9]{64}$' -or
    (Get-V3ReleaseSha256 $Bytes) -cne $ExpectedSha256){throw 'V3_RELEASE_INDEPENDENT_ADMISSION_HASH_HOLD'}
 $a=Read-V3ReleaseJson $Bytes
 $fields=@('kind','certificate_sha256','release_commit','independent_key_custody_accepted','original_approval_url')
 if(@($a.PSObject.Properties).Count -ne $fields.Count -or
    @($a.PSObject.Properties.Name|Where-Object {$_ -cnotin $fields}).Count -or
    [string]$a.kind -cne 'V3_INDEPENDENT_RELEASE_AUTHORITY_ADMISSION_V1' -or
    [string]$a.certificate_sha256 -cnotmatch '^[a-f0-9]{64}$' -or
    $ReleaseCommit -cnotmatch '^[a-f0-9]{40}$' -or [string]$a.release_commit -cne $ReleaseCommit -or
    $a.independent_key_custody_accepted -isnot [bool] -or $a.independent_key_custody_accepted -ne $true -or
    [string]$a.original_approval_url -cnotmatch '^https://github\.com/hoffmannherdecke/kraken-eur-scanner/issues/99#issuecomment-[0-9]+$'){
  throw 'V3_RELEASE_INDEPENDENT_AUTHORITY_NOT_ADMITTED'
 }
 # A file digest and a local accepted=true flag are NOT original authority.
 # Re-read the existing #99 decision itself from GitHub over authenticated
 # HTTPS. No redirects, arbitrary URL, token, secondary owner or new service.
 $id=([regex]::Match([string]$a.original_approval_url,'issuecomment-([0-9]+)$')).Groups[1].Value
 $url='https://api.github.com/repos/hoffmannherdecke/kraken-eur-scanner/issues/comments/'+$id
 $original=Invoke-RestMethod -Uri $url -Method Get -TimeoutSec 10 -MaximumRedirection 0 `
  -Headers @{Accept='application/vnd.github+json';'X-GitHub-Api-Version'='2022-11-28'}
 if([string]$original.id -cne $id -or [string]$original.user.login -cne 'hoffmannherdecke' -or
    [string]$original.user.id -cne '331995561' -or
    [string]$original.issue_url -cne 'https://api.github.com/repos/hoffmannherdecke/kraken-eur-scanner/issues/99'){
  throw 'V3_RELEASE_ORIGINAL_OWNER_IDENTITY_HOLD'
 }
 $decision=Read-V3ReleaseJson ([Text.Encoding]::UTF8.GetBytes([string]$original.body))
 $decisionFields=@('kind','release_commit','certificate_sha256','independent_key_custody_accepted')
 if(@($decision.PSObject.Properties).Count -ne $decisionFields.Count -or
    @($decision.PSObject.Properties.Name|Where-Object {$_ -cnotin $decisionFields}).Count -or
    [string]$decision.kind -cne 'V3_INDEPENDENT_RELEASE_AUTHORITY_ADMISSION_V1' -or
    [string]$decision.release_commit -cne $ReleaseCommit -or
    [string]$decision.certificate_sha256 -cne [string]$a.certificate_sha256 -or
    $decision.independent_key_custody_accepted -isnot [bool] -or
    $decision.independent_key_custody_accepted -ne $true){throw 'V3_RELEASE_ORIGINAL_OWNER_ADMISSION_NOT_MATCHED'}
 # ExpectedSha256 is a separate trust input from the reviewed execution
 # instruction. This code never creates/posts the independent owner decision.
 return [string]$a.certificate_sha256
}

function Open-V3ReleasePackageReadLease([string]$PackageRoot,[hashtable]$Inventory) {
 $streams=[Collections.Generic.List[IO.FileStream]]::new()
 try {
  foreach($path in $Inventory.Keys){
   $full=Join-Path $PackageRoot $path
   $null=Read-V3ReleaseLocalBytes -Path $full -MaxBytes 1048576
   $stream=[IO.File]::Open($full,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
   $streams.Add($stream)
   $sha=[Security.Cryptography.SHA256]::Create()
   try{$actual=([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-','').ToLowerInvariant()}
   finally{$sha.Dispose();$stream.Position=0}
   if($actual -cne [string]$Inventory[$path]){throw 'V3_RELEASE_PACKAGE_CHANGED_BEFORE_READ_LEASE'}
  }
  return ,$streams
 }catch{foreach($stream in $streams){$stream.Dispose()};throw}
}

Export-ModuleMember -Function Get-V3ReleaseSha256,Read-V3ReleaseJson,Assert-V3ReleaseCms,Assert-V3OneTimeReleaseAuthorization,Read-V3ReleaseLocalBytes,Get-V3OneTimeReleaseArtifactInventory,Assert-V3ReleaseAuthorityAdmission,Open-V3ReleasePackageReadLease

# Existing signed issuer-prestop reader receipt is the only accepted source.
# Its original exact UTF-8 bytes are durable evidence; freshness is separately
# enforced by the existing 30-second prestop reader before dispatch.
function Assert-V3GateAReceipt([object]$Bindings,[byte[]]$Payload,[byte[]]$Cms) {
 $fields=@('epoch_id','source_sha256','fence_sha256','caller_acl_sha256','receipt_sha256','reader_certificate_sha256')
 if($null -eq $Bindings -or @($Bindings.PSObject.Properties).Count -ne $fields.Count -or
    @($Bindings.PSObject.Properties.Name|Where-Object {$_ -cnotin $fields}).Count -or
    [string]$Bindings.epoch_id -cnotmatch '^V3CAS-AUDIT-[a-f0-9]{32}$'){throw 'V3_GATE_A_BINDINGS_HOLD'}
 foreach($field in $fields|Where-Object {$_ -ne 'epoch_id'}){
  if([string]$Bindings.$field -cnotmatch '^[a-f0-9]{64}$'){throw 'V3_GATE_A_HASH_BINDING_HOLD'}
 }
 Assert-V3ReleaseCms -Payload $Payload -Cms $Cms -ReviewedAuthorityCertificateSha256 $Bindings.reader_certificate_sha256
 $r=Read-V3ReleaseJson $Payload
 if((Get-V3ReleaseSha256 $Payload) -cne [string]$Bindings.receipt_sha256 -or
    [string]$r.kind -cne 'V3_CAS_ISSUER_COMMITTED_PRESTOP_READER_V1' -or
    [string]$r.epoch_id -cne [string]$Bindings.epoch_id -or
    [string]$r.source_sha256 -cne [string]$Bindings.source_sha256 -or
    [string]$r.original_fence_sha256 -cne [string]$Bindings.fence_sha256 -or
    [string]$r.caller_acl_sha256 -cne [string]$Bindings.caller_acl_sha256 -or
    [string]$r.issuer_actor -cne 'v3_cas_inhibit_issuer_actor' -or
    [string]$r.actor -cne 'v3_cas_audit_reader_actor' -or
    [string]$r.requested_role -cne 'v3_cas_audit_reader' -or
    $r.unknown_count -ne 0 -or
    [string]$r.state -cne 'INHIBITED' -or $r.native_stop_done -ne $false -or
    $r.cas_or_paper_authorized -ne $false){throw 'V3_GATE_A_ORIGINAL_RECEIPT_HOLD'}
 return Get-V3ReleaseSha256 $Payload
}
function Get-V3GateATransaction([object]$Bindings,[datetimeoffset]$ExpiresAt) {
 # No caller SQL or unvalidated interpolation; only typed immutable identities.
 if([string]$Bindings.epoch_id -cnotmatch '^V3CAS-AUDIT-[a-f0-9]{32}$'){throw 'V3_GATE_A_SQL_EPOCH_HOLD'}
 foreach($field in @('source_sha256','fence_sha256','caller_acl_sha256','receipt_sha256')){
  if([string]$Bindings.$field -cnotmatch '^[a-f0-9]{64}$'){throw 'V3_GATE_A_SQL_HASH_HOLD'}
 }
 $expires=$ExpiresAt.ToUniversalTime().ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
 return @"
BEGIN;
SET LOCAL statement_timeout='15s';
SET LOCAL lock_timeout='5s';
DO `$gate_a`$
BEGIN
 IF session_user <> 'v3_cas_inhibit_issuer_actor' OR clock_timestamp() >= '$expires'::timestamptz
 THEN RAISE EXCEPTION 'V3_GATE_A_ACTOR_OR_AUTHORIZATION_EXPIRED'; END IF;
END `$gate_a`$;
SELECT v3_cas_audit.record_prepared_fence_abort_v1('$($Bindings.epoch_id)',
 '$($Bindings.source_sha256)','$($Bindings.fence_sha256)',
 '$($Bindings.caller_acl_sha256)','$($Bindings.receipt_sha256)');
COMMIT;
"@
}
Export-ModuleMember -Function Assert-V3GateAReceipt,Get-V3GateATransaction
