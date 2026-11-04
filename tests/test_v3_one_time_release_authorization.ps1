# New release authorization tests. Ephemeral keys only; no host/Cloud action.
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$root=Split-Path $PSScriptRoot -Parent
Import-Module (Join-Path $root 'tools/v3-one-time-release-authorization.psm1') -Force
Add-Type -AssemblyName System.Security.Cryptography.Pkcs
foreach($file in @('tools/v3-one-time-release.ps1','tools/v3-one-time-release-authorization.psm1',
 'tools/v3-one-time-originalhost-boundary.ps1','tools/v3-one-time-originalhost-release.psm1')){
 $t=$null;$e=$null
 $null=[Management.Automation.Language.Parser]::ParseFile((Join-Path $root $file),[ref]$t,[ref]$e)
 if(@($e).Count){$e|ForEach-Object {Write-Output $_.Message};throw 'RELEASE_PARSE_FAILED'}
}
$rsa=[Security.Cryptography.RSA]::Create(2048)
$req=[Security.Cryptography.X509Certificates.CertificateRequest]::new('CN=CI-NOT-A-PRODUCTION-AUTHORITY',
 $rsa,[Security.Cryptography.HashAlgorithmName]::SHA256,[Security.Cryptography.RSASignaturePadding]::Pkcs1)
$cert=$req.CreateSelfSigned([datetimeoffset]::UtcNow.AddMinutes(-1),[datetimeoffset]::UtcNow.AddMinutes(20))
$pin=Get-V3ReleaseSha256 $cert.RawData
$hashes=Get-V3OneTimeReleaseArtifactInventory -PackageRoot $root
$now=[datetimeoffset]::UtcNow
$claim=[ordered]@{
 kind='V3_ONE_TIME_RELEASE_AUTHORIZATION_V1';release_id=('V3-ONETIME-'+('a'*32));scope='CLOUD_ABORT_INSTALL'
 base_commit='5b1789e349b157d06d3109c5f0ff10d95154bf81';release_commit=('1'*40)
 not_before_utc=$now.AddSeconds(-10).ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
 expires_at_utc=$now.AddMinutes(5).ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
 project_ref='nlgzjmqgwueojlyqmoru';computer_name='MINI-PC';trading_root='C:\Users\ADMIN\Trading'
 artifacts=$hashes;bindings=@{source_sha256='86dfebe688eda78ba14000a63f534e3295af63dcf19c48e07aab26d75e76fbd6'}
}
function Sign-Claims($Claims){
 $bytes=[Text.Encoding]::UTF8.GetBytes(($Claims|ConvertTo-Json -Depth 10 -Compress))
 $signed=[Security.Cryptography.Pkcs.SignedCms]::new([Security.Cryptography.Pkcs.ContentInfo]::new($bytes),$true)
 $signer=[Security.Cryptography.Pkcs.CmsSigner]::new($cert)
 $signer.DigestAlgorithm=[Security.Cryptography.Oid]::new('2.16.840.1.101.3.4.2.1')
 $signed.ComputeSignature($signer)
 return @{Payload=$bytes;Cms=[byte[]]$signed.Encode();ReviewedAuthorityCertificateSha256=$pin;
  Scope='CLOUD_ABORT_INSTALL';ExpectedReleaseCommit=('1'*40);ExpectedArtifacts=$hashes;Now=$now}
}
$checks=0
function Deny([hashtable]$InputArgs){
 $denied=$false
 try{$null=Assert-V3OneTimeReleaseAuthorization @InputArgs}catch{$denied=$true}
 if(-not $denied){throw 'RELEASE_NEGATIVE_WAS_ACCEPTED'}
 $script:checks++
}
try {
 $valid=Sign-Claims $claim
 $a=Assert-V3OneTimeReleaseAuthorization @valid
 if($a.claims.scope -cne 'CLOUD_ABORT_INSTALL' -or $a.approval_sha256 -cne (Get-V3ReleaseSha256 $valid.Payload)){
  throw 'RELEASE_VALID_APPROVAL_REJECTED'
 }
 $checks++
 $bad=$valid.Clone();$bad.Scope='ORIGINALHOST_ABORT_RESTORE';Deny $bad
 $bad=$valid.Clone();$bad.ReviewedAuthorityCertificateSha256=('0'*64);Deny $bad
 $bad=$valid.Clone();$bad.Cms=[byte[]](1,2,3);Deny $bad
 $bad=$valid.Clone();$bad.ExpectedReleaseCommit=('2'*40);Deny $bad
 $bad=$valid.Clone();$bad.Payload=[byte[]]$valid.Payload.Clone();$bad.Payload[5]=42;Deny $bad
 $bad=$valid.Clone();$bad.Now=$now.AddHours(1);Deny $bad
 $bad=$valid.Clone();$bad.Now=$now.AddHours(-1);Deny $bad
 $bad=$valid.Clone();$bad.ExpectedArtifacts=$hashes.Clone();$bad.ExpectedArtifacts.Remove('tools/v3-one-time-release.ps1');Deny $bad
 $bad=$valid.Clone();$bad.ExpectedArtifacts=$hashes.Clone();$bad.ExpectedArtifacts['tools/v3-one-time-release.ps1']=('0'*64);Deny $bad
 $copy=[ordered]@{};foreach($key in $claim.Keys){$copy[$key]=$claim[$key]};$copy.base_commit=('0'*40);Deny (Sign-Claims $copy)
 $copy=[ordered]@{};foreach($key in $claim.Keys){$copy[$key]=$claim[$key]};$copy.computer_name='FOREIGN-HOST';Deny (Sign-Claims $copy)
 $copy=[ordered]@{};foreach($key in $claim.Keys){$copy[$key]=$claim[$key]};$copy.expires_at_utc=$now.AddHours(1).ToString("yyyy-MM-dd'T'HH:mm:ss'Z'");Deny (Sign-Claims $copy)
 $duplicate=[Text.Encoding]::UTF8.GetBytes('{"kind":"x","kind":"y"}')
 $denied=$false;try{$null=Read-V3ReleaseJson $duplicate}catch{$denied=$true}
 if(-not $denied){throw 'RELEASE_DUPLICATE_KEYS_ACCEPTED'};$checks++
 $escaped=[Text.Encoding]::UTF8.GetBytes('{"ki\u006ed":"x"}')
 $denied=$false;try{$null=Read-V3ReleaseJson $escaped}catch{$denied=$true}
 if(-not $denied){throw 'RELEASE_ESCAPED_KEY_ACCEPTED'};$checks++
 # A local file/hash/accepted flag cannot confer authority without the
 # original #99 decision. Mock HTTPS only in this disposable unit test.
 $authModule=Get-Module 'v3-one-time-release-authorization'
 $admission=[ordered]@{kind='V3_INDEPENDENT_RELEASE_AUTHORITY_ADMISSION_V1';certificate_sha256=$pin;
  release_commit=('1'*40);independent_key_custody_accepted=$true;
  original_approval_url='https://github.com/hoffmannherdecke/kraken-eur-scanner/issues/99#issuecomment-1000000000'}
 $admissionBytes=[Text.Encoding]::UTF8.GetBytes(($admission|ConvertTo-Json -Compress))
 $admissionHash=Get-V3ReleaseSha256 $admissionBytes
 $decision=@{kind=$admission.kind;certificate_sha256=$pin;release_commit=('1'*40);independent_key_custody_accepted=$true}|ConvertTo-Json -Compress
 & $authModule {
  param($Body)
  $script:TestOriginalDecision=[pscustomobject]@{id='1000000000';user=[pscustomobject]@{login='hoffmannherdecke';id='331995561'};
   issue_url='https://api.github.com/repos/hoffmannherdecke/kraken-eur-scanner/issues/99';body=$Body}
  function script:Invoke-RestMethod {param($Uri,$Method,$TimeoutSec,$MaximumRedirection,$Headers)
   if($Uri -cne 'https://api.github.com/repos/hoffmannherdecke/kraken-eur-scanner/issues/comments/1000000000' -or
      $Method -cne 'Get' -or $MaximumRedirection -ne 0){throw 'TEST_UNBOUNDED_ADMISSION_REQUEST'}
   return $script:TestOriginalDecision
  }
 } $decision
 $accepted=Assert-V3ReleaseAuthorityAdmission $admissionBytes $admissionHash ('1'*40)
 if($accepted -cne $pin){throw 'RELEASE_ORIGINAL_ADMISSION_REJECTED'};$checks++
 & $authModule {$script:TestOriginalDecision.user.login='wrong-author'}
 $denied=$false;try{$null=Assert-V3ReleaseAuthorityAdmission $admissionBytes $admissionHash ('1'*40)}catch{$denied=$true}
 if(-not $denied){throw 'RELEASE_LOCAL_ADMISSION_ACCEPTED_WITH_WRONG_ORIGIN'};$checks++
 & $authModule {$script:TestOriginalDecision.user.login='hoffmannherdecke';$script:TestOriginalDecision.issue_url='https://api.github.com/repos/hoffmannherdecke/kraken-eur-scanner/issues/353'}
 $denied=$false;try{$null=Assert-V3ReleaseAuthorityAdmission $admissionBytes $admissionHash ('1'*40)}catch{$denied=$true}
 if(-not $denied){throw 'RELEASE_ADMISSION_WRONG_OWNER_ACCEPTED'};$checks++
 & $authModule {Remove-Item Function:Invoke-RestMethod}
 # Unsigned/default execution is inventory only on every platform.
 $wire=& (Join-Path $root 'tools/v3-one-time-release.ps1')
 $inventory=($wire -join "`n")|ConvertFrom-Json
 if($inventory.production_authorized -ne $false -or $inventory.host_mutated -ne $false -or
    $inventory.cloud_contacted -ne $false){throw 'RELEASE_DEFAULT_HAS_AUTHORITY'};$checks++
 Import-Module (Join-Path $root 'tools/v3-one-time-originalhost-release.psm1') -Force
 $module=Get-Module 'v3-one-time-originalhost-release'
 $scopeDenied=& $module {Test-V3ReleaseOriginalhostScope -Root 'C:\Users\ADMIN\Trading' -Tasks @('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait')}
 if($scopeDenied){throw 'RELEASE_MISSING_SESSION_ACCEPTED'};$checks++
 # An expired signed session cannot reach any generated native owner.
 $expired=& $module {
  $script:V3ReleaseContext=[pscustomobject]@{authorization=[pscustomobject]@{expires_at=[datetimeoffset]::UtcNow.AddMinutes(-1)}}
  Test-V3ReleaseOriginalhostScope -Root 'C:\Users\ADMIN\Trading' -Tasks @('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait')
 }
 if($expired){throw 'RELEASE_EXPIRED_SESSION_ACCEPTED'};$checks++
 [pscustomobject]@{kind='V3_ONE_TIME_RELEASE_AUTHORIZATION_TEST_V1';checks_passed=$checks;
  production_credentials_used=$false;originalhost_mutated=$false;production_authorized=$false}|ConvertTo-Json -Compress
}finally{$cert.Dispose();$rsa.Dispose()}
