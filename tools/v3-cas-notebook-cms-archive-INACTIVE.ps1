# One-time OFF-HOST notebook copy of a detached-SHA256-CMS signed V3 CAS
# PREINVOKE receipt. Existing Issue #99 owner; this is NOT an executor,
# independent issuer authentication, WORM service, CAS audit completeness,
# Windows STOP/restore, or Paper release. No network, secrets or scheduler.
# Windows PowerShell 5.1+; the user supplies an independently reviewed
# PUBLIC certificate SHA256 pin. Never use a self-declared signer pin as GO.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)]
 [ValidateSet('Speichern','Pruefen')]
 [string]$Aktion,
 [string]$BelegDatei,
 [string]$CmsDatei,
 [Parameter(Mandatory=$true)]
 [string]$ZertifikatSha256,
 [string]$Ablage=(Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'V3-Paper-Nachweise\CAS-Quittung-INACTIVE')
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($ZertifikatSha256 -cnotmatch '^[0-9a-f]{64}$'){
 throw 'V3_CAS_NOTEBOOK_HOLD_PUBLIC_CERT_PIN_MISSING'
}
$Ablage=[IO.Path]::GetFullPath($Ablage)
function Assert-PathNoReparse([string]$full,[bool]$existingLeaf) {
 if(-not [IO.Path]::IsPathRooted($full)){throw 'V3_CAS_NOTEBOOK_HOLD_NOT_ABSOLUTE'}
 if($existingLeaf -and -not [IO.File]::Exists($full)){
  throw 'V3_CAS_NOTEBOOK_HOLD_SOURCE_MISSING'
 }
 $cursor=$full
 while(-not [string]::IsNullOrWhiteSpace($cursor)){
  if([IO.File]::Exists($cursor) -or [IO.Directory]::Exists($cursor)){
   $item=Get-Item -LiteralPath $cursor -Force -ErrorAction Stop
   if(([int]$item.Attributes -band [int][IO.FileAttributes]::ReparsePoint) -ne 0){
    throw 'V3_CAS_NOTEBOOK_HOLD_REPARSE_POINT'
   }
  }
  $parent=[IO.Path]::GetDirectoryName($cursor.TrimEnd('\'))
  if([string]::IsNullOrWhiteSpace($parent) -or $parent -ceq $cursor){break}
  $cursor=$parent
 }
}
function Hash-Bytes([byte[]]$bytes){
 $sha=[Security.Cryptography.SHA256]::Create()
 try {return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-','').ToLowerInvariant()}
 finally {$sha.Dispose()}
}
function Read-Limited([string]$path,[int]$max){
 Assert-PathNoReparse $path $true
 $item=Get-Item -LiteralPath $path -Force -ErrorAction Stop
 if($item.PSIsContainer -or $item.Length -lt 16 -or $item.Length -gt $max){
  throw 'V3_CAS_NOTEBOOK_HOLD_FILE_SIZE_OR_TYPE'
 }
 return ,([IO.File]::ReadAllBytes($path))
}
function Test-PayloadAndCms([byte[]]$payload,[byte[]]$signature){
 if($payload.Length -lt 200 -or $payload.Length -gt 2048 -or
    $signature.Length -lt 64 -or $signature.Length -gt 32768){
  throw 'V3_CAS_NOTEBOOK_HOLD_CMS_SIZE'
 }
 try {
  $strictUtf8=[Text.UTF8Encoding]::new($false,$true)
  $raw=$strictUtf8.GetString($payload)
  $obj=$raw|ConvertFrom-Json -ErrorAction Stop
 }catch{throw 'V3_CAS_NOTEBOOK_HOLD_UNSIGNED_JSON'}
 $expected=@('epoch_id','fence_sha256','intent_id','intent_sha256',
    'kind','local_review_at_utc','ordinal','predecessor_series_id',
    'proof_status','readback_sha256','reader_claimed_observed_at_utc',
    'request_sha256','rpc','source_sha256')
 if($null -eq $obj -or $obj -isnot [pscustomobject] -or
   ((@($obj.PSObject.Properties.Name|Sort-Object) -join '|') -cne
    (@($expected|Sort-Object) -join '|')) -or
   [string]$obj.kind -cne 'V3_CAS_PREINVOKE_UNSIGNED_PROPOSAL_V1' -or
   [string]$obj.proof_status -cne 'UNTRUSTED_READER_PROPOSAL_NOT_AUTHENTICATED' -or
   ($obj.ordinal -isnot [int] -and $obj.ordinal -isnot [long]) -or $obj.ordinal -ne 1 -or
   [string]$obj.predecessor_series_id -cne 'PAPER-V2R4-20261009T110135Z' -or
   [string]$obj.rpc -cne 'public.rotate_v2r4_to_v3_experimental_paper' -or
   [string]$obj.epoch_id -cnotmatch '^V3CAS-AUDIT-[a-f0-9]{32}$' -or
   [string]$obj.intent_id -cnotmatch '^[a-f0-9-]{36}$'){
  throw 'V3_CAS_NOTEBOOK_HOLD_RECEIPT_SCOPE'
 }
 $uuid=[guid]::Empty
 if(-not [guid]::TryParseExact([string]$obj.intent_id,'D',[ref]$uuid) -or
    $uuid.ToString('D') -cne [string]$obj.intent_id){
  throw 'V3_CAS_NOTEBOOK_HOLD_RECEIPT_UUID'
 }
 foreach($key in @('fence_sha256','intent_sha256','readback_sha256',
                  'request_sha256','source_sha256')){
  if([string]$obj.$key -cnotmatch '^[a-f0-9]{64}$'){
   throw 'V3_CAS_NOTEBOOK_HOLD_RECEIPT_HASH'
  }
 }
 foreach($key in @('local_review_at_utc','reader_claimed_observed_at_utc')){
  # PS7 ConvertFrom-Json eagerly converts ISO strings to DateTime whereas
  # Windows PS5.1 retains strings. Verify the ORIGINAL signed JSON text
  # rather than a locale-dependent round-trip through parsed DateTime.
  $matches=[regex]::Matches($raw,('"'+[regex]::Escape($key)+'"\s*:\s*"(?<utc>[^"]+)"'))
  if($matches.Count -ne 1){throw 'V3_CAS_NOTEBOOK_HOLD_RECEIPT_TIME'}
  $value=[string]$matches[0].Groups['utc'].Value
  $date=[datetime]::MinValue
  if($value -cnotmatch '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z
 try{
  $content=[Security.Cryptography.Pkcs.ContentInfo]::new($payload)
  $cms=[Security.Cryptography.Pkcs.SignedCms]::new($content,$true)
  $cms.Decode($signature)
  if(-not $cms.Detached -or $cms.SignerInfos.Count -ne 1){
   throw 'V3_CAS_NOTEBOOK_HOLD_NOT_SINGLE_DETACHED'
  }
  $signer=$cms.SignerInfos[0]
  if([string]$signer.DigestAlgorithm.Value -cne '2.16.840.1.101.3.4.2.1' -or
     $null -eq $signer.Certificate -or
     (Hash-Bytes ([byte[]]$signer.Certificate.RawData)) -cne $ZertifikatSha256){
   throw 'V3_CAS_NOTEBOOK_HOLD_PUBLIC_PIN_OR_DIGEST'
  }
  $cms.CheckSignature($true)
 }catch{throw 'V3_CAS_NOTEBOOK_HOLD_CMS_VERIFY'}
 return (Hash-Bytes $payload)
}
function Write-New([string]$path,[byte[]]$data){
 $stream=[IO.FileStream]::new($path,[IO.FileMode]::CreateNew,
   [IO.FileAccess]::Write,[IO.FileShare]::None)
 try{$stream.Write($data,0,$data.Length);$stream.Flush($true)}
 finally{$stream.Dispose()}
}
function Read-Stored {
 Assert-PathNoReparse $Ablage $false
 if(-not [IO.Directory]::Exists($Ablage)){
  throw 'V3_CAS_NOTEBOOK_HOLD_NO_ARCHIVE'
 }
 $want=@('voraufruf.json','voraufruf.cms','voraufruf.sha256')
 $names=@(Get-ChildItem -LiteralPath $Ablage -Force -ErrorAction Stop|
   ForEach-Object {$_.Name}|Sort-Object)
 if(($names -join '|') -cne ((@($want|Sort-Object)) -join '|')){
  throw 'V3_CAS_NOTEBOOK_HOLD_MISSING_OR_EXTRA_RECORD'
 }
 $payload=Read-Limited (Join-Path $Ablage 'voraufruf.json') 2048
 $cms=Read-Limited (Join-Path $Ablage 'voraufruf.cms') 32768
 $pin=([Text.Encoding]::ASCII.GetString(
   (Read-Limited (Join-Path $Ablage 'voraufruf.sha256') 256))).Trim()
 $expected=(Hash-Bytes $payload)+'|'+(Hash-Bytes $cms)+'|'+$ZertifikatSha256
 if($pin -cne $expected){throw 'V3_CAS_NOTEBOOK_HOLD_ARCHIVE_HASH_DRIFT'}
 $digest=Test-PayloadAndCms $payload $cms
 return [pscustomobject]@{
  status='V3_CAS_NOTEBOOK_SIGNED_COPY_CRYPTO_VALID_ONLY'
  payload_sha256=$digest
  offhost_copy_readback=$true
  cryptographic_signature_checked=$true
  original_reader_cloud_session_authenticated_here=$false
  independent_immutable_external_custody_proven=$false
  exclusive_cas_attempt_coverage_proven=$false
  cas_execute_erlaubt=$false
  v2r4_rearm_erlaubt=$false
  v3_paper_freigabe=$false
 }
}
if($Aktion -ceq 'Pruefen'){
 Read-Stored|ConvertTo-Json -Compress
 return
}
if([string]::IsNullOrWhiteSpace($BelegDatei) -or
   [string]::IsNullOrWhiteSpace($CmsDatei) -or
   [IO.Path]::GetExtension($BelegDatei) -cne '.json' -or
   [IO.Path]::GetExtension($CmsDatei) -cne '.cms'){
 throw 'V3_CAS_NOTEBOOK_HOLD_INPUT_FILE_EXTENSIONS'
}
$beleg=Read-Limited ([IO.Path]::GetFullPath($BelegDatei)) 2048
$signatur=Read-Limited ([IO.Path]::GetFullPath($CmsDatei)) 32768
$null=Test-PayloadAndCms $beleg $signatur
Assert-PathNoReparse $Ablage $false
[void][IO.Directory]::CreateDirectory($Ablage)
if(@(Get-ChildItem -LiteralPath $Ablage -Force -ErrorAction Stop).Count -ne 0){
 throw 'V3_CAS_NOTEBOOK_HOLD_ARCHIVE_NOT_EMPTY_OR_REPLAY'
}
# One-shot CreateNew and force-flush. If power fails between files, retain
# partial evidence and HOLD; never unlink/retry or infer an absent attempt.
Write-New (Join-Path $Ablage 'voraufruf.json') $beleg
Write-New (Join-Path $Ablage 'voraufruf.cms') $signatur
$manifest=(Hash-Bytes $beleg)+'|'+(Hash-Bytes $signatur)+'|'+$ZertifikatSha256
Write-New (Join-Path $Ablage 'voraufruf.sha256') ([Text.Encoding]::ASCII.GetBytes($manifest))
Read-Stored|ConvertTo-Json -Compress
 -or
    -not [datetime]::TryParseExact($value,"yyyy-MM-dd'T'HH:mm:ss'Z'",
      [Globalization.CultureInfo]::InvariantCulture,
      [Globalization.DateTimeStyles]::None,[ref]$date)){
   throw 'V3_CAS_NOTEBOOK_HOLD_RECEIPT_TIME'
  }
 }
 try{
  $content=[Security.Cryptography.Pkcs.ContentInfo]::new($payload)
  $cms=[Security.Cryptography.Pkcs.SignedCms]::new($content,$true)
  $cms.Decode($signature)
  if(-not $cms.Detached -or $cms.SignerInfos.Count -ne 1){
   throw 'V3_CAS_NOTEBOOK_HOLD_NOT_SINGLE_DETACHED'
  }
  $signer=$cms.SignerInfos[0]
  if([string]$signer.DigestAlgorithm.Value -cne '2.16.840.1.101.3.4.2.1' -or
     $null -eq $signer.Certificate -or
     (Hash-Bytes ([byte[]]$signer.Certificate.RawData)) -cne $ZertifikatSha256){
   throw 'V3_CAS_NOTEBOOK_HOLD_PUBLIC_PIN_OR_DIGEST'
  }
  $cms.CheckSignature($true)
 }catch{throw 'V3_CAS_NOTEBOOK_HOLD_CMS_VERIFY'}
 return (Hash-Bytes $payload)
}
function Write-New([string]$path,[byte[]]$data){
 $stream=[IO.FileStream]::new($path,[IO.FileMode]::CreateNew,
   [IO.FileAccess]::Write,[IO.FileShare]::None)
 try{$stream.Write($data,0,$data.Length);$stream.Flush($true)}
 finally{$stream.Dispose()}
}
function Read-Stored {
 Assert-PathNoReparse $Ablage $false
 if(-not [IO.Directory]::Exists($Ablage)){
  throw 'V3_CAS_NOTEBOOK_HOLD_NO_ARCHIVE'
 }
 $want=@('voraufruf.json','voraufruf.cms','voraufruf.sha256')
 $names=@(Get-ChildItem -LiteralPath $Ablage -Force -ErrorAction Stop|
   ForEach-Object {$_.Name}|Sort-Object)
 if(($names -join '|') -cne ((@($want|Sort-Object)) -join '|')){
  throw 'V3_CAS_NOTEBOOK_HOLD_MISSING_OR_EXTRA_RECORD'
 }
 $payload=Read-Limited (Join-Path $Ablage 'voraufruf.json') 2048
 $cms=Read-Limited (Join-Path $Ablage 'voraufruf.cms') 32768
 $pin=([Text.Encoding]::ASCII.GetString(
   (Read-Limited (Join-Path $Ablage 'voraufruf.sha256') 256))).Trim()
 $expected=(Hash-Bytes $payload)+'|'+(Hash-Bytes $cms)+'|'+$ZertifikatSha256
 if($pin -cne $expected){throw 'V3_CAS_NOTEBOOK_HOLD_ARCHIVE_HASH_DRIFT'}
 $digest=Test-PayloadAndCms $payload $cms
 return [pscustomobject]@{
  status='V3_CAS_NOTEBOOK_SIGNED_COPY_CRYPTO_VALID_ONLY'
  payload_sha256=$digest
  offhost_copy_readback=$true
  cryptographic_signature_checked=$true
  original_reader_cloud_session_authenticated_here=$false
  independent_immutable_external_custody_proven=$false
  exclusive_cas_attempt_coverage_proven=$false
  cas_execute_erlaubt=$false
  v2r4_rearm_erlaubt=$false
  v3_paper_freigabe=$false
 }
}
if($Aktion -ceq 'Pruefen'){
 Read-Stored|ConvertTo-Json -Compress
 return
}
if([string]::IsNullOrWhiteSpace($BelegDatei) -or
   [string]::IsNullOrWhiteSpace($CmsDatei) -or
   [IO.Path]::GetExtension($BelegDatei) -cne '.json' -or
   [IO.Path]::GetExtension($CmsDatei) -cne '.cms'){
 throw 'V3_CAS_NOTEBOOK_HOLD_INPUT_FILE_EXTENSIONS'
}
$beleg=Read-Limited ([IO.Path]::GetFullPath($BelegDatei)) 2048
$signatur=Read-Limited ([IO.Path]::GetFullPath($CmsDatei)) 32768
$null=Test-PayloadAndCms $beleg $signatur
Assert-PathNoReparse $Ablage $false
[void][IO.Directory]::CreateDirectory($Ablage)
if(@(Get-ChildItem -LiteralPath $Ablage -Force -ErrorAction Stop).Count -ne 0){
 throw 'V3_CAS_NOTEBOOK_HOLD_ARCHIVE_NOT_EMPTY_OR_REPLAY'
}
# One-shot CreateNew and force-flush. If power fails between files, retain
# partial evidence and HOLD; never unlink/retry or infer an absent attempt.
Write-New (Join-Path $Ablage 'voraufruf.json') $beleg
Write-New (Join-Path $Ablage 'voraufruf.cms') $signatur
$manifest=(Hash-Bytes $beleg)+'|'+(Hash-Bytes $signatur)+'|'+$ZertifikatSha256
Write-New (Join-Path $Ablage 'voraufruf.sha256') ([Text.Encoding]::ASCII.GetBytes($manifest))
Read-Stored|ConvertTo-Json -Compress
