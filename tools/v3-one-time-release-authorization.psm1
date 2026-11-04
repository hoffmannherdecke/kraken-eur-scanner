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
 Add-Type -AssemblyName System.Security.Cryptography.Pkcs
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
       [ValidateSet('CLOUD_ABORT_INSTALL','ORIGINALHOST_ABORT_RESTORE')][string]$Scope,
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
 # ExpectedSha256 is an independent trust input from the reviewed #99
 # execution instruction, not a digest discovered from this untrusted file.
 return [string]$a.certificate_sha256
}

Export-ModuleMember -Function Get-V3ReleaseSha256,Read-V3ReleaseJson,Assert-V3ReleaseCms,Assert-V3OneTimeReleaseAuthorization,Read-V3ReleaseLocalBytes,Get-V3OneTimeReleaseArtifactInventory,Assert-V3ReleaseAuthorityAdmission
