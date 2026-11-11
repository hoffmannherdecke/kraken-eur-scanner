# New release authorization tests. Ephemeral keys only; no host/Cloud action.
param([switch]$FrameworkChild,[string]$FixtureDirectory='')
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$root=Split-Path $PSScriptRoot -Parent
Import-Module (Join-Path $root 'tools/v3-one-time-release-authorization.psm1') -Force
if($FrameworkChild){
 if($env:OS -cne 'Windows_NT' -or $env:GITHUB_ACTIONS -cne 'true' -or $env:RUNNER_ENVIRONMENT -cne 'github-hosted'){
  throw 'RELEASE_FRAMEWORK_TEST_DISPOSABLE_WINDOWS_ONLY'
 }
 $fixture=Get-Content -LiteralPath (Join-Path $FixtureDirectory 'context.json') -Raw|ConvertFrom-Json
 $hashes=Get-V3OneTimeReleaseArtifactInventory -PackageRoot $root
 $null=Assert-V3OneTimeReleaseAuthorization -Payload ([IO.File]::ReadAllBytes((Join-Path $FixtureDirectory 'approval.json'))) `
  -Cms ([IO.File]::ReadAllBytes((Join-Path $FixtureDirectory 'approval.cms'))) `
  -ReviewedAuthorityCertificateSha256 ([string]$fixture.pin) -Scope CLOUD_ABORT_INSTALL `
  -ExpectedReleaseCommit ('1'*40) -ExpectedArtifacts $hashes
 $inventory=& (Join-Path $root 'tools/v3-one-time-release.ps1')
 if((($inventory -join "`n")|ConvertFrom-Json).production_authorized -ne $false){throw 'RELEASE_PS51_DEFAULT_AUTHORITY'}
 Write-Output 'V3_ONE_TIME_RELEASE_WINDOWS_POWERSHELL51_REAL_CMS_AND_INVENTORY_PASS'
 return
}
Add-Type -AssemblyName System.Security.Cryptography.Pkcs
foreach($file in @('tools/v3-one-time-release.ps1','tools/v3-one-time-release-authorization.psm1',
 'tools/v3-one-time-originalhost-boundary.ps1','tools/v3-one-time-originalhost-release.psm1',
 'tools/v3-one-time-gateb-coordination.ps1')){
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
 $repeated=[ordered]@{};foreach($key in $claim.Keys){$repeated[$key]=$claim[$key]}
 $repeated.scope='V3_PAPER_RUNTIME_REPEATED'
 $repeated.bindings=@{host_receipt_sha256=('a'*64);runtime_spec_sha256=('b'*64);plan_sha256=('c'*64);reader_certificate_sha256=('d'*64)}
 $lease=Sign-Claims $repeated
 $lease.Scope='V3_PAPER_RUNTIME_REPEATED'
 $verified=Assert-V3OneTimeReleaseAuthorization @lease
 if($verified.claims.scope -cne $repeated.scope -or $verified.not_before -ge $verified.expires_at){throw 'REPEATED_SCOPE_REJECTED'}
 $wrong=$lease.Clone();$wrong.Scope='V3_PAPER_RUNTIME';Deny $wrong
 $wrong=$lease.Clone();$wrong.Scope='V3_PAPER_ACTIVATE';Deny $wrong
 $wrong=$lease.Clone();$wrong.Now=$verified.expires_at;Deny $wrong
 $wrong=$lease.Clone();$wrong.Cms=[byte[]]@();Deny $wrong
 $repeated.expires_at_utc=$now.AddDays(3).ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
 $lease=Sign-Claims $repeated;$lease.Scope='V3_PAPER_RUNTIME_REPEATED'
 $null=Assert-V3OneTimeReleaseAuthorization @lease
 $repeated.expires_at_utc=$now.AddDays(5).ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
 $lease=Sign-Claims $repeated;$lease.Scope='V3_PAPER_RUNTIME_REPEATED';Deny $lease
 $duplicate=[Text.Encoding]::UTF8.GetBytes('{"kind":"x","kind":"y"}')
 $denied=$false;try{$null=Read-V3ReleaseJson $duplicate}catch{$denied=$true}
 if(-not $denied){throw 'RELEASE_DUPLICATE_KEYS_ACCEPTED'};$checks++
 $escaped=[Text.Encoding]::UTF8.GetBytes('{"ki\u006ed":"x"}')
 $denied=$false;try{$null=Read-V3ReleaseJson $escaped}catch{$denied=$true}
 if(-not $denied){throw 'RELEASE_ESCAPED_KEY_ACCEPTED'};$checks++
 if($env:OS -ceq 'Windows_NT' -and $env:GITHUB_ACTIONS -ceq 'true' -and $env:RUNNER_ENVIRONMENT -ceq 'github-hosted'){
  $fixture=Join-Path $env:RUNNER_TEMP ('V3-Release-PS51-'+[guid]::NewGuid().ToString('N'))
  $null=[IO.Directory]::CreateDirectory($fixture)
  try {
   [IO.File]::WriteAllBytes((Join-Path $fixture 'approval.json'),$valid.Payload)
   [IO.File]::WriteAllBytes((Join-Path $fixture 'approval.cms'),$valid.Cms)
   [IO.File]::WriteAllText((Join-Path $fixture 'context.json'),(@{pin=$pin}|ConvertTo-Json -Compress))
   & (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe') -NoProfile -File $PSCommandPath -FrameworkChild -FixtureDirectory $fixture
   if($LASTEXITCODE -ne 0){throw 'RELEASE_WINDOWS_POWERSHELL51_FAILED'}
   $checks++
  }finally{[IO.Directory]::Delete($fixture,$true)}
 }
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
 Import-Module (Join-Path $root 'tools/v3-one-time-release-authorization.psm1') -Force
 # Gate B must consume the genuine earlier installation without rewriting it
 # to the newer host release. Exact independently signed pins remain mandatory.
 $installFixture=Join-Path ([IO.Path]::GetTempPath()) ('v3-install-'+[guid]::NewGuid().ToString('N')+'.json')
 try {
  $installRecord=[ordered]@{kind='V3_ONE_TIME_ABORT_INSTALL_READBACK_V1';verified=$true;
   installation=[ordered]@{kind='V3_ONE_TIME_ABORT_INSTALL_V1';release_commit=('2'*40);
    source_sha256=$hashes['supabase/v3-cas-prepared-fence-abort-INACTIVE.sql'];
    release_id=('V3-ONETIME-'+('b'*32));approval_sha256=('c'*64)}}
  $installBytes=[Text.Encoding]::UTF8.GetBytes(($installRecord|ConvertTo-Json -Compress -Depth 5))
  [IO.File]::WriteAllBytes($installFixture,$installBytes)
  $installBindings=[pscustomobject]@{install_release_commit=('2'*40);install_readback_sha256=(Get-V3ReleaseSha256 $installBytes)}
  $installSource=$hashes['supabase/v3-cas-prepared-fence-abort-INACTIVE.sql']
  & $module {param($p,$b,$s) Assert-V3ReleaseInstalledAbortReadback -Path $p -Bindings $b -ExpectedSourceSha256 $s} $installFixture $installBindings $installSource
  $checks++
  foreach($failure in @('wrong_commit','missing_commit','wrong_hash','wrong_source','changed_bytes',
    'unverified','string_verified','wrong_kind','wrong_install_kind','bad_install_id','bad_approval')){
   $b=[pscustomobject]@{install_release_commit=('2'*40);install_readback_sha256=(Get-V3ReleaseSha256 $installBytes)}
   $record=([Text.Encoding]::UTF8.GetString($installBytes))|ConvertFrom-Json
   $sourcePin=$installSource
   switch($failure){
    wrong_commit {$b.install_release_commit=('1'*40)}
    missing_commit {$b.install_release_commit=''}
    wrong_hash {$b.install_readback_sha256=('0'*64)}
    wrong_source {$sourcePin=('0'*64)}
    changed_bytes {[IO.File]::WriteAllBytes($installFixture,([byte[]]($installBytes+32)))}
    unverified {$record.verified=$false}
    string_verified {$record.verified='true'}
    wrong_kind {$record.kind='WRONG'}
    wrong_install_kind {$record.installation.kind='WRONG'}
    bad_install_id {$record.installation.release_id='WRONG'}
    bad_approval {$record.installation.approval_sha256='WRONG'}
   }
   if($failure -in @('unverified','string_verified','wrong_kind','wrong_install_kind','bad_install_id','bad_approval')){
    $altered=[Text.Encoding]::UTF8.GetBytes(($record|ConvertTo-Json -Compress -Depth 5))
    [IO.File]::WriteAllBytes($installFixture,$altered)
    $b.install_readback_sha256=Get-V3ReleaseSha256 $altered
   }
   $denied=$false
   try{& $module {param($p,$b,$s) Assert-V3ReleaseInstalledAbortReadback -Path $p -Bindings $b -ExpectedSourceSha256 $s} $installFixture $b $sourcePin}catch{$denied=$true}
   if(-not $denied){throw ('GATE_B_INSTALL_PROVENANCE_NEGATIVE_ACCEPTED_'+$failure)}
   $checks++
   [IO.File]::WriteAllBytes($installFixture,$installBytes)
  }
  Write-Output 'V3_GATE_B_DISTINCT_INSTALL_RELEASE_AND_EXACT_RECEIPT_NEGATIVES_PASS'
 }finally{if([IO.File]::Exists($installFixture)){[IO.File]::Delete($installFixture)}}
 $terminalRecord=[ordered]@{kind='V3_CAS_PREPARED_FENCE_ABORT_READER_RECEIPT_V1';
  epoch_id=('V3CAS-AUDIT-'+('a'*32));source_sha256=('a'*64);prepared_fence_sha256=('b'*64);
  caller_acl_sha256=('c'*64);issuer_actor='v3_cas_inhibit_issuer_actor';receipt_sha256=('d'*64);
  state='ABORT_RECORDED_NOT_RELEASED';
  created_at_utc=$now.AddMinutes(-5).ToString("yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'");
  observed_at_utc=[datetimeoffset]::UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'");
  cloud_active_series_count=1;cloud_original_active_series_count=1;cloud_cas_rpc_count=0;
  cloud_executor_can_login=$false;cloud_observed_at_utc=[datetimeoffset]::UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'")}
 foreach($failure in @('valid','stale_45_seconds','future','wrong_epoch','wrong_source','wrong_fence',
   'wrong_acl','cas_present','executor_login','wrong_state','bad_signature','wrong_signer')){
  $record=[ordered]@{};foreach($k in $terminalRecord.Keys){$record[$k]=$terminalRecord[$k]}
  switch($failure){
   stale_45_seconds {$record.observed_at_utc=[datetimeoffset]::UtcNow.AddSeconds(-45).ToString("yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'");$record.cloud_observed_at_utc=$record.observed_at_utc}
   future {$record.observed_at_utc=[datetimeoffset]::UtcNow.AddSeconds(20).ToString("yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'");$record.cloud_observed_at_utc=$record.observed_at_utc}
   wrong_epoch {$record.epoch_id=('V3CAS-AUDIT-'+('e'*32))}
   wrong_source {$record.source_sha256=('e'*64)}
   wrong_fence {$record.prepared_fence_sha256=('e'*64)}
   wrong_acl {$record.caller_acl_sha256=('e'*64)}
   cas_present {$record.cloud_cas_rpc_count=1}
   executor_login {$record.cloud_executor_can_login=$true}
   wrong_state {$record.state='INHIBITED'}
  }
  $payload=[Text.Encoding]::UTF8.GetBytes(($record|ConvertTo-Json -Compress))
  $sig=[Security.Cryptography.Pkcs.SignedCms]::new([Security.Cryptography.Pkcs.ContentInfo]::new($payload),$true)
  $signer=[Security.Cryptography.Pkcs.CmsSigner]::new($cert)
  $signer.DigestAlgorithm=[Security.Cryptography.Oid]::new('2.16.840.1.101.3.4.2.1');$sig.ComputeSignature($signer)
  $sigBytes=[byte[]]$sig.Encode();$expectedPin=$pin
  if($failure -ceq 'bad_signature'){$sigBytes=[byte[]](1,2,3)}
  if($failure -ceq 'wrong_signer'){$expectedPin=('0'*64)}
  $review=& $module {param($p,$c,$pin)
   Test-V3ReleaseSignedTerminalPrestopReceipt -Payload $p -Cms $c -ReviewedCertSha256 $pin `
    -ExpectedEpochId ('V3CAS-AUDIT-'+('a'*32)) -ExpectedSourceSha256 ('a'*64) `
    -ExpectedFenceSha256 ('b'*64) -ExpectedAclSha256 ('c'*64)
  } $payload $sigBytes $expectedPin
  if($review.signed_cloud_row_matches_pre_stop_inhibit -ne ($failure -ceq 'valid')){
   throw ('GATE_B_TERMINAL_PRESTOP_REVIEW_FAILED_'+$failure)
  }
  $checks++
 }
 Write-Output 'V3_GATE_B_SIGNED_TERMINAL_PRESTOP_30_SECOND_AND_PIN_NEGATIVES_PASS'
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
# Gate A: real detached CMS over exact original receipt bytes, no Cloud access.
Import-Module (Join-Path $root 'tools/v3-one-time-release-authorization.psm1') -Force
$gate=[pscustomobject]@{epoch_id=('V3CAS-AUDIT-'+('a'*32));source_sha256=('a'*64);
 fence_sha256=('b'*64);caller_acl_sha256=('c'*64);receipt_sha256=('d'*64);reader_certificate_sha256=$pin}
$original=[ordered]@{actor='v3_cas_audit_reader_actor';requested_role='v3_cas_audit_reader';unknown_count=0;kind='V3_CAS_ISSUER_COMMITTED_PRESTOP_READER_V1';epoch_id=$gate.epoch_id;
 source_sha256=$gate.source_sha256;original_fence_sha256=$gate.fence_sha256;
 caller_acl_sha256=$gate.caller_acl_sha256;issuer_actor='v3_cas_inhibit_issuer_actor';
 state='INHIBITED';native_stop_done=$false;cas_or_paper_authorized=$false}
$bytes=[Text.Encoding]::UTF8.GetBytes(($original|ConvertTo-Json -Compress))
$signed=[Security.Cryptography.Pkcs.SignedCms]::new([Security.Cryptography.Pkcs.ContentInfo]::new($bytes),$true)
$signer=[Security.Cryptography.Pkcs.CmsSigner]::new($cert)
$signer.DigestAlgorithm=[Security.Cryptography.Oid]::new('2.16.840.1.101.3.4.2.1')
$signed.ComputeSignature($signer)
$cmsBytes=$signed.Encode()
$gate.receipt_sha256=Get-V3ReleaseSha256 $bytes
$null=Assert-V3GateAReceipt -Bindings $gate -Payload $bytes -Cms $cmsBytes
function Expect-GateAHold([scriptblock]$Action){
 $held=$false;try{& $Action}catch{$held=$true};if(-not $held){throw 'GATE_A_NEGATIVE_ACCEPTED'}
}
$changed=[byte[]]$bytes.Clone();$changed[0]=0xff
Expect-GateAHold {Assert-V3GateAReceipt -Bindings $gate -Payload $changed -Cms $cmsBytes}
$gate.source_sha256='e'*64
Expect-GateAHold {Assert-V3GateAReceipt -Bindings $gate -Payload $bytes -Cms $cmsBytes}
$gate.source_sha256='a'*64
$gate.reader_certificate_sha256='e'*64
Expect-GateAHold {Assert-V3GateAReceipt -Bindings $gate -Payload $bytes -Cms $cmsBytes}
$gate.reader_certificate_sha256=$pin
$broken=[byte[]]$cmsBytes.Clone();$broken[$broken.Length-1]=$broken[$broken.Length-1] -bxor 1
Expect-GateAHold {Assert-V3GateAReceipt -Bindings $gate -Payload $bytes -Cms $broken}
$gate.receipt_sha256='e'*64
Expect-GateAHold {Assert-V3GateAReceipt -Bindings $gate -Payload $bytes -Cms $cmsBytes}
$gate.receipt_sha256=Get-V3ReleaseSha256 $bytes
$sql=Get-V3GateATransaction -Bindings $gate -ExpiresAt ([datetimeoffset]::UtcNow.AddMinutes(5))
if(([regex]::Matches($sql,'SELECT v3_cas_audit.record_prepared_fence_abort_v1\(')).Count -ne 1 -or
 $sql -notmatch 'session_user' -or $sql -notmatch 'clock_timestamp' -or $sql -match 'SET ROLE|ALTER ROLE|begin_executor_inhibit'){
 throw 'GATE_A_SINGLE_ISSUER_TRANSACTION_CONTRACT'
}
$gate.epoch_id="bad');COMMIT;--"
Expect-GateAHold {Get-V3GateATransaction -Bindings $gate -ExpiresAt ([datetimeoffset]::UtcNow.AddMinutes(5))}
# Execute the actual launcher attempt boundary in a disposable directory.
# Replace only the PG transport, forcing an ambiguous result after dispatch.
$ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path $root 'tools/v3-one-time-release.ps1'),[ref]$null,[ref]$null)
$fn=$ast.Find({param($a) $a -is [Management.Automation.Language.FunctionDefinitionAst] -and $a.Name -eq 'Invoke-V3GateAOnce'},$true)
. ([scriptblock]::Create($fn.Extent.Text))
$script:dispatches=0
function Invoke-V3ReleasePg {param($Sql,$Password,$Ca,$Actor)
 if($Actor -cne 'v3_cas_inhibit_issuer_actor'){throw 'WRONG_ACTOR'}
 $script:dispatches++;throw 'V3_RELEASE_PG_TIMEOUT_OUTCOME_UNKNOWN_NO_RETRY'
}
$temp=Join-Path ([IO.Path]::GetTempPath()) ('gate-a-test-'+[guid]::NewGuid().ToString('N'))
$null=[IO.Directory]::CreateDirectory($temp)
try{
 $latch=Join-Path $temp 'attempt'
 Expect-GateAHold {Invoke-V3GateAOnce -LatchPath $latch -Receipt $bytes -Sql $sql}
 if($script:dispatches -ne 1 -or -not [IO.File]::Exists($latch)){throw 'UNKNOWN_LOST_LATCH_OR_RETRIED'}
 Expect-GateAHold {Invoke-V3GateAOnce -LatchPath $latch -Receipt $bytes -Sql $sql}
 if($script:dispatches -ne 1){throw 'DUPLICATE_NETWORK_DISPATCH'}
}finally{[IO.Directory]::Delete($temp,$true)}
Write-Output 'V3_GATE_A_EXACT_BYTES_REAL_CMS_NEGATIVE_TESTS_PASS'

}finally{$cert.Dispose();$rsa.Dispose()}


# Historical post-STOP-UNKNOWN quarantine: source-only guard, no actor or host access.
$historical=[pscustomobject]@{
 kind='V3_POST_STOP_UNKNOWN_READONLY_STATE_V1'
 series_id='PAPER-V3-20261111T105211Z'
 epoch_id='V3CAS-AUDIT-f27cce0ba68043b480e4f97698dd2901'
 fence_sha256='4f01704d20375f201f87c56eb3350a67c1a91f82535296b28ae318768aa213ef'
 fence_phase='ARMED';cloud_inhibit_state='INHIBITED'
 cloud_epoch_sealed=$false;cloud_next_ordinal=1
 cloud_intent_count=0;cloud_attempt_count=0;cloud_abort_count=0
 candidates_enabled=$true;wait_enabled=$true;cloudsync_enabled=$true
 v3_writer_enabled=$false;native_stop_outcome='UNKNOWN'
 originalhost_journal_present=$false
 independent_host_custody_verified=$false
 independent_cloud_reader_verified=$false
}
$decision=Assert-V3PostStopUnknownQuarantineSourceContract $historical
if($decision.production_authorized -ne $false -or
   $decision.cloud_terminal_abort_confirmed -ne $false -or
   $decision.originalhost_recovered -ne $false -or
   $decision.historical_stop_success_claimed -ne $false -or
   $decision.retry_authorized -ne $false -or
   $decision.new_writer_authorized -ne $false -or
   $decision.disposition -cne 'SOURCE_ONLY_NO_PRODUCTION_EFFECT'){
 throw 'V3_POSTSTOP_SOURCE_GATE_CLAIMED_EXECUTION'
}
foreach($negative in @(
 @('series_id','PAPER-V3-20261111T105212Z'),
 @('epoch_id','V3CAS-AUDIT-'+('0'*32)),
 @('fence_sha256',('0'*64)),@('fence_phase','CLOSED'),
 @('cloud_inhibit_state','RELEASED'),@('cloud_epoch_sealed',$true),
 @('cloud_next_ordinal',2),@('cloud_intent_count',1),@('cloud_attempt_count',1),
 @('cloud_abort_count',1),@('candidates_enabled',$false),
 @('wait_enabled',$false),@('cloudsync_enabled',$false),
 @('v3_writer_enabled',$true),@('native_stop_outcome','SUCCESS'),
 @('originalhost_journal_present',$true)
)){
 $clone=([Text.Encoding]::UTF8.GetString([Text.Encoding]::UTF8.GetBytes(
   ($historical|ConvertTo-Json -Compress -Depth 5))))|ConvertFrom-Json
 $clone.($negative[0])=$negative[1]
 $held=$false
 try{ $null=Assert-V3PostStopUnknownQuarantineSourceContract $clone }catch{$held=$true}
 if(-not $held){throw ('V3_POSTSTOP_NEGATIVE_ACCEPTED_'+$negative[0])}
}
$missing=$historical|ConvertTo-Json -Compress|ConvertFrom-Json
$missing.PSObject.Properties.Remove('native_stop_outcome')
$held=$false
try{$null=Assert-V3PostStopUnknownQuarantineSourceContract $missing}catch{$held=$true}
if(-not $held){throw 'V3_POSTSTOP_MISSING_ORIGINAL_ACCEPTED'}
Write-Output 'V3_POSTSTOP_HISTORICAL_SOURCE_ONLY_QUARANTINE_NEGATIVES_PASS'

# Reuse this existing Linux/Windows CI entry; no new workflow or runtime task.
& (Join-Path $PSScriptRoot 'test_v3_one_time_reconciliation.ps1')
