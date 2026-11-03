# V3 Paper #99 – single independent Notebook issuer, explicitly INACTIVE source.
# One-time LOCAL credential preparation only. Never contacts Supabase or invokes CAS.
# Existing reader/writer DPAPI identities, Mini-PC and active V2R4 are untouched.
[CmdletBinding()]
param([switch]$Stage,[switch]$VerifyLocal,[switch]$RemoveEnrollmentSql,
 [switch]$VerifySourceAuthority,[string]$ReviewedSourceCommit='',
 [string]$OriginalhostOperatorFile='',[string]$NotebookReaderFile='',
 [string]$ReviewedNotebookCertificateSha256='')
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if (([int]$Stage.IsPresent+[int]$VerifyLocal.IsPresent+
     [int]$RemoveEnrollmentSql.IsPresent+[int]$VerifySourceAuthority.IsPresent) -gt 1) { throw 'V3_ISSUER_MODE_CONFLICT' }
if(-not $VerifySourceAuthority -and ($ReviewedSourceCommit -or $OriginalhostOperatorFile -or
   $NotebookReaderFile -or $ReviewedNotebookCertificateSha256)){
 throw 'V3_ISSUER_SOURCE_AUTHORITY_ARGUMENTS_OUTSIDE_MODE'
}
$role='v3_cas_inhibit_issuer_actor'
$root=Join-Path $env:LOCALAPPDATA 'V3CasIndependentIssuer'
$secretPath=Join-Path $root 'issuer-currentuser.dpapi'
$sqlPath=Join-Path $root 'issuer-enroll-ONE-TIME.sql'
$entropy=[Text.Encoding]::ASCII.GetBytes('V3_CAS_INDEPENDENT_ISSUER_NOTEBOOK_V1')
if (-not ($Stage -or $VerifyLocal -or $RemoveEnrollmentSql -or $VerifySourceAuthority)) {
 [pscustomobject]@{state='INACTIVE_PREVIEW';role=$role;network_used=$false;
   credential_created=$false;cloud_changed=$false;cas_invoked=$false} |
   ConvertTo-Json -Compress
 return
}
# Windows PowerShell 5.1 does not always autoload the DPAPI type.
# Resolve the built-in framework assembly BEFORE creating any local enrollment files.
Add-Type -AssemblyName System.Security -ErrorAction Stop
# Verify real Windows CurrentUser DPAPI before touching any local credential path.
# Assembly-qualified Type.GetType is unreliable in Windows PowerShell 5.1:
# resolving the native PowerShell type and roundtripping test bytes is decisive.
try {
 $probe=[byte[]](17,39,81,121)
 $probeBack=$null
 $probeCipher=[Security.Cryptography.ProtectedData]::Protect(
   $probe,$entropy,[Security.Cryptography.DataProtectionScope]::CurrentUser)
 try {
  $probeBack=[Security.Cryptography.ProtectedData]::Unprotect(
    $probeCipher,$entropy,[Security.Cryptography.DataProtectionScope]::CurrentUser)
  if ($probeBack.Length -ne $probe.Length) {
   throw 'V3_ISSUER_DPAPI_PROBE_LENGTH_HOLD'
  }
  for($i=0;$i -lt $probe.Length;$i++){
   if ($probeBack[$i] -ne $probe[$i]) {throw 'V3_ISSUER_DPAPI_PROBE_MISMATCH_HOLD'}
  }
 } finally {
  if ($null -ne $probeBack) {[Array]::Clear($probeBack,0,$probeBack.Length)}
  [Array]::Clear($probeCipher,0,$probeCipher.Length)
 }
} catch {
 throw ('V3_ISSUER_DPAPI_REAL_ROUNDTRIP_UNAVAILABLE: '+$_.Exception.GetType().Name)
} finally {
 [Array]::Clear($probe,0,$probe.Length)
}
$id=[Security.Principal.WindowsIdentity]::GetCurrent()
if ($env:OS -ne 'Windows_NT' -or -not [Environment]::UserInteractive -or
    $env:GITHUB_ACTIONS -eq 'true' -or $id.Name -match '(?i)\\CryptoSupportSvc$' -or
    $null -eq $id.User) {throw 'V3_ISSUER_NOTEBOOK_INTERACTIVE_ONLY'}
$base=Get-Item -LiteralPath $env:LOCALAPPDATA -Force
$disk=[IO.DriveInfo]::new([IO.Path]::GetPathRoot($root))
if ($base.Attributes -band [IO.FileAttributes]::ReparsePoint -or
    $disk.DriveType -ne [IO.DriveType]::Fixed -or $disk.DriveFormat -ne 'NTFS') {
 throw 'V3_ISSUER_LOCAL_NTFS_REQUIRED'
}
$allow=@($id.User.Value,'S-1-5-18','S-1-5-32-544')
function New-SafeAcl([bool]$folder) {
 if ($folder) {
  $acl=[Security.AccessControl.DirectorySecurity]::new()
  $flags=[Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
    [Security.AccessControl.InheritanceFlags]::ObjectInherit
 } else {
  $acl=[Security.AccessControl.FileSecurity]::new()
  $flags=[Security.AccessControl.InheritanceFlags]::None
 }
 $acl.SetAccessRuleProtection($true,$false)
 foreach ($s in $allow) {
  $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
    [Security.Principal.SecurityIdentifier]::new($s),
    [Security.AccessControl.FileSystemRights]::FullControl,$flags,
    [Security.AccessControl.PropagationFlags]::None,
    [Security.AccessControl.AccessControlType]::Allow))
 }
 return $acl
}
function Assert-Safe([string]$path,[bool]$folder) {
 $file=Get-Item -LiteralPath $path -Force
 if ($file.PSIsContainer -ne $folder -or
     ($file.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
  throw 'V3_ISSUER_LOCAL_OBJECT_DRIFT'
 }
 $acl=Get-Acl -LiteralPath $path
 if (-not $acl.AreAccessRulesProtected) {throw 'V3_ISSUER_ACL_INHERITANCE_HOLD'}
 $rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
 if (-not @($rules | Where-Object {
       $_.AccessControlType -eq 'Allow' -and
       $_.IdentityReference.Value -ceq $id.User.Value }).Count) {
  throw 'V3_ISSUER_OWNER_ACL_MISSING'
 }
 foreach ($rule in $rules) {
  if ($rule.AccessControlType -eq 'Allow' -and
      $rule.IdentityReference.Value -notin $allow) {
   throw 'V3_ISSUER_FOREIGN_ACL_HOLD'
  }
 }
}
if ($RemoveEnrollmentSql -or $VerifyLocal -or $VerifySourceAuthority) {
 if (-not [IO.Directory]::Exists($root)) {throw 'V3_ISSUER_NOT_STAGED'}
} elseif (-not [IO.Directory]::Exists($root)) {
 [void][IO.Directory]::CreateDirectory($root,(New-SafeAcl $true))
}
Assert-Safe $root $true
function Write-SafeNew([string]$path,[byte[]]$bytes) {
 $fs=[IO.FileStream]::new($path,[IO.FileMode]::CreateNew,
    [Security.AccessControl.FileSystemRights]::Write,[IO.FileShare]::None,
    4096,[IO.FileOptions]::WriteThrough,(New-SafeAcl $false))
 try{$fs.Write($bytes,0,$bytes.Length);$fs.Flush($true)}
 finally{$fs.Dispose()}
 Assert-Safe $path $false
}
# PR661_SOURCE_AUTHORITY_READONLY_BEGIN
# New differential ACK only: the existing issuer login and existing Notebook
# key bind the reviewed operator/Reader bytes. No schema, epoch, inhibit,
# permission, native Task, marker, CAS or Paper is changed by this mode.
if($VerifySourceAuthority){
 if($ReviewedSourceCommit -cnotmatch '^[a-f0-9]{40}$' -or
    $ReviewedNotebookCertificateSha256 -cne
     '61d08dd9a925730f213fedc559664dbfe2a3e4f8f1ae77496b385f7d92f3bc55'){
  throw 'V3_ISSUER_SOURCE_AUTHORITY_COMMIT_OR_ACCEPTED_SIGNER_HOLD'
 }
 $files=@(
  @{path=$OriginalhostOperatorFile;name='minipc-v3-paper-cutover-operator-INACTIVE.ps1'},
  @{path=$NotebookReaderFile;name='v3-notebook-cas-audit-original-readonly-witness-INACTIVE.ps1'})
 $digests=@()
 foreach($spec in $files){
  $file=Get-Item -LiteralPath $spec.path -Force -ErrorAction Stop
  if($file.PSIsContainer -or $file.Name -cne $spec.name -or
     $file.Length -lt 100 -or $file.Length -gt 1048576 -or
     [bool]($file.Attributes -band [IO.FileAttributes]::ReparsePoint)){
   throw 'V3_ISSUER_SOURCE_AUTHORITY_FILE_SCOPE_HOLD'
  }
  $digests+=@((Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant())
 }
 Assert-Safe $secretPath $false
 $psql='C:\Program Files\PostgreSQL\17\bin\psql.exe'
 if(-not [IO.File]::Exists($psql)){throw 'V3_ISSUER_SOURCE_AUTHORITY_PSQL17_MISSING'}
 $certificate=@(Get-ChildItem Cert:\CurrentUser\My | Where-Object {
  $hash=[Security.Cryptography.SHA256]::Create()
  try{([BitConverter]::ToString($hash.ComputeHash([byte[]]$_.RawData))).Replace('-','').ToLowerInvariant() -ceq $ReviewedNotebookCertificateSha256}
  finally{$hash.Dispose()}
 })
 if($certificate.Count -ne 1 -or -not $certificate[0].HasPrivateKey -or
    $certificate[0].NotBefore.ToUniversalTime() -gt [datetime]::UtcNow -or
    $certificate[0].NotAfter.ToUniversalTime() -lt [datetime]::UtcNow){
  throw 'V3_ISSUER_SOURCE_AUTHORITY_EXISTING_KEY_HOLD'
 }
 $plain=$null;$password=$null;$output=$null
 $oldPassword=$env:PGPASSWORD;$oldRoot=$env:PGSSLROOTCERT
 try{
  $plain=[Security.Cryptography.ProtectedData]::Unprotect(
   [IO.File]::ReadAllBytes($secretPath),$entropy,
   [Security.Cryptography.DataProtectionScope]::CurrentUser)
  $password=[Text.Encoding]::ASCII.GetString($plain)
  if($password -cnotmatch '^[a-f0-9]{64}$'){throw 'V3_ISSUER_SOURCE_AUTHORITY_SECRET_SHAPE_HOLD'}
  $env:PGPASSWORD=$password;$env:PGSSLROOTCERT='system'
  $connection='host=aws-1-eu-west-1.pooler.supabase.com port=5432 dbname=postgres user=v3_cas_inhibit_issuer_actor.nlgzjmqgwueojlyqmoru sslmode=verify-full connect_timeout=10'
  $query="BEGIN TRANSACTION READ ONLY; SELECT session_user || '|' || current_user || '|' || current_database(); COMMIT;"
  $output=@(& $psql -X -w -qAt -v ON_ERROR_STOP=1 -d $connection -c $query 2>&1)
  if($LASTEXITCODE -ne 0 -or $output.Count -ne 1 -or [string]$output[0] -cne
     'v3_cas_inhibit_issuer_actor|v3_cas_inhibit_issuer_actor|postgres'){
   throw 'V3_ISSUER_SOURCE_AUTHORITY_LIVE_SESSION_HOLD'
  }
 }catch{throw 'V3_ISSUER_SOURCE_AUTHORITY_LIVE_READ_HOLD_NO_RAW_DIAGNOSTICS'}
 finally{
  $env:PGPASSWORD=$oldPassword;$env:PGSSLROOTCERT=$oldRoot
  if($null -ne $plain){[Array]::Clear($plain,0,$plain.Length)}
  $password=$null;$output=$null;$oldPassword=$null
 }
 $nonce=[guid]::NewGuid().ToString('N')
 $wire=[ordered]@{
  kind='V3_PR661_NOTEBOOK_ISSUER_SOURCE_AUTHORITY_ACK_V1'
  observed_at_utc=[datetimeoffset]::UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'",[Globalization.CultureInfo]::InvariantCulture)
  nonce=$nonce;source_commit=$ReviewedSourceCommit
  operator_sha256=$digests[0];notebook_reader_sha256=$digests[1]
  issuer_tool_sha256=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
  issuer_actor='v3_cas_inhibit_issuer_actor';database='postgres'
  transport='PG17_VERIFY_FULL_SYSTEM_CA'
  scope='REVIEWED_SOURCE_BINDING_ONLY_NOT_RUNTIME_RELEASE'
  cloud_changed=$false;native_runtime_authorized=$false;cas_or_paper_authorized=$false
 }|ConvertTo-Json -Compress
 Add-Type -AssemblyName System.Security -ErrorAction Stop
 $bytes=[Text.UTF8Encoding]::new($false).GetBytes($wire)
 $cms=[Security.Cryptography.Pkcs.SignedCms]::new([Security.Cryptography.Pkcs.ContentInfo]::new([byte[]]$bytes),$true)
 $signer=[Security.Cryptography.Pkcs.CmsSigner]::new($certificate[0])
 $signer.DigestAlgorithm=[Security.Cryptography.Oid]::new('2.16.840.1.101.3.4.2.1')
 $cms.ComputeSignature($signer)
 $folder=Join-Path $root ('source-authority-'+$nonce)
 [void][IO.Directory]::CreateDirectory($folder,(New-SafeAcl $true))
 Assert-Safe $folder $true
 Write-SafeNew (Join-Path $folder 'source-authority.json') $bytes
 Write-SafeNew (Join-Path $folder 'source-authority.cms') ([byte[]]$cms.Encode())
 [pscustomobject]@{kind='V3_PR661_NOTEBOOK_SOURCE_AUTHORITY_TRANSFER_V1'
  local_directory=$folder;source_commit=$ReviewedSourceCommit
  certificate_sha256=$ReviewedNotebookCertificateSha256
  cloud_changed=$false;native_runtime_authorized=$false;cas_or_paper_authorized=$false
 }|ConvertTo-Json -Compress
 return
}
# PR661_SOURCE_AUTHORITY_READONLY_END
if ($RemoveEnrollmentSql) {
 if ([IO.File]::Exists($sqlPath)) {
  Assert-Safe $sqlPath $false
  [IO.File]::Delete($sqlPath)
 }
 [pscustomobject]@{state='ONE_TIME_SQL_SCRUBBED';
   sealed_credential_preserved=[IO.File]::Exists($secretPath);
   cloud_changed=$false} | ConvertTo-Json -Compress
 return
}
if ($VerifyLocal) {
 if (-not [IO.File]::Exists($sqlPath) -or -not [IO.File]::Exists($secretPath)) {
  throw 'V3_ISSUER_STAGED_PAIR_MISSING'
 }
 Assert-Safe $sqlPath $false
 Assert-Safe $secretPath $false
 $raw=[Security.Cryptography.ProtectedData]::Unprotect(
   [IO.File]::ReadAllBytes($secretPath),$entropy,
   [Security.Cryptography.DataProtectionScope]::CurrentUser)
 try {$password=[Text.Encoding]::ASCII.GetString($raw)}
 finally {[Array]::Clear($raw,0,$raw.Length)}
 if ($password -cnotmatch '^[a-f0-9]{64}$') {throw 'V3_ISSUER_SECRET_SHAPE_HOLD'}
 $sql=[IO.File]::ReadAllText($sqlPath,[Text.Encoding]::ASCII)
 $m=[regex]::Matches($sql,'SCRAM-SHA-256\${1}4096:([A-Za-z0-9+/=]+)\${1}([A-Za-z0-9+/=]+):([A-Za-z0-9+/=]+)')
 if ($m.Count -ne 1 -or $sql -cnotmatch 'V3_ISSUER_ROLE_PRESTAGED_HOLD' -or
     $sql -cnotmatch 'alter role v3_cas_inhibit_issuer_actor login') {
  throw 'V3_ISSUER_SQL_SHAPE_HOLD'
 }
 $salt=[Convert]::FromBase64String($m[0].Groups[1].Value)
 $stored=[Convert]::FromBase64String($m[0].Groups[2].Value)
 $server=[Convert]::FromBase64String($m[0].Groups[3].Value)
 if ($salt.Length -ne 16 -or $stored.Length -ne 32 -or $server.Length -ne 32) {
  throw 'V3_ISSUER_VERIFIER_SHAPE_HOLD'
 }
 $kdf=[Security.Cryptography.Rfc2898DeriveBytes]::new(
   $password,$salt,4096,[Security.Cryptography.HashAlgorithmName]::SHA256)
 try {$key=$kdf.GetBytes(32)} finally {$kdf.Dispose()}
 $h=[Security.Cryptography.HMACSHA256]::new($key)
 try {
  $client=$h.ComputeHash([Text.Encoding]::ASCII.GetBytes('Client Key'))
  $checkServer=$h.ComputeHash([Text.Encoding]::ASCII.GetBytes('Server Key'))
 } finally {$h.Dispose();[Array]::Clear($key,0,$key.Length)}
 $sha=[Security.Cryptography.SHA256]::Create()
 try {$checkStored=$sha.ComputeHash($client)} finally {$sha.Dispose()}
 $delta=0
 for($i=0;$i -lt 32;$i++){
  $delta=$delta -bor ([int]$stored[$i] -bxor [int]$checkStored[$i])
  $delta=$delta -bor ([int]$server[$i] -bxor [int]$checkServer[$i])
 }
 foreach($a in @($salt,$stored,$server,$client,$checkStored,$checkServer)){
  [Array]::Clear($a,0,$a.Length)
 }
 $password=$null
 if ($delta -ne 0){throw 'V3_ISSUER_DPAPI_SCRAM_MISMATCH'}
 [pscustomobject]@{state='LOCAL_DPAPI_SCRAM_ROUNDTRIP_PASS';
   cloud_changed=$false;secret_disclosed=$false;cas_invoked=$false} |
   ConvertTo-Json -Compress
 return
}
# Stage: only one-time create-new; never overwrite an existing reader, writer or issuer.
if ([IO.File]::Exists($secretPath) -or [IO.File]::Exists($sqlPath) -or
    [IO.Directory]::Exists($secretPath) -or [IO.Directory]::Exists($sqlPath)) {
 throw 'V3_ISSUER_EXISTING_IDENTITY_HOLD'
}
$random=New-Object byte[] 32
$rng=[Security.Cryptography.RandomNumberGenerator]::Create()
try{$rng.GetBytes($random)} finally{$rng.Dispose()}
$password=[BitConverter]::ToString($random).Replace('-','').ToLowerInvariant()
[Array]::Clear($random,0,$random.Length)
$plain=[Text.Encoding]::ASCII.GetBytes($password)
try{$sealed=[Security.Cryptography.ProtectedData]::Protect(
   $plain,$entropy,[Security.Cryptography.DataProtectionScope]::CurrentUser)}
finally{[Array]::Clear($plain,0,$plain.Length)}
Write-SafeNew $secretPath $sealed
[Array]::Clear($sealed,0,$sealed.Length)
$salt=New-Object byte[] 16
$rng=[Security.Cryptography.RandomNumberGenerator]::Create()
try{$rng.GetBytes($salt)} finally{$rng.Dispose()}
$pbkdf=[Security.Cryptography.Rfc2898DeriveBytes]::new(
  $password,$salt,4096,[Security.Cryptography.HashAlgorithmName]::SHA256)
try{$key=$pbkdf.GetBytes(32)}finally{$pbkdf.Dispose()}
$hmac=[Security.Cryptography.HMACSHA256]::new($key)
try {
 $client=$hmac.ComputeHash([Text.Encoding]::ASCII.GetBytes('Client Key'))
 $server=$hmac.ComputeHash([Text.Encoding]::ASCII.GetBytes('Server Key'))
} finally {$hmac.Dispose();[Array]::Clear($key,0,$key.Length)}
$sha=[Security.Cryptography.SHA256]::Create()
try{$stored=$sha.ComputeHash($client)}finally{$sha.Dispose()}
$verifier='SCRAM-SHA-256$4096:'+[Convert]::ToBase64String($salt)+'$'+
  [Convert]::ToBase64String($stored)+':'+[Convert]::ToBase64String($server)
foreach($a in @($salt,$stored,$server,$client)){[Array]::Clear($a,0,$a.Length)}
$password=$null
# SQL stays local and must be separately reviewed and manually approved;
# no notebook PowerShell operation connects to the production database.
$sql=@'
-- SENSITIVE SCRAM verifier: keep solely in Notebook local file, never chat or GitHub.
-- Separate deployment authorization required; no automatic invocation.
begin;
do $v3_issuer_enroll$
declare v_verifier text := '__ISSUER_SCRAM_VERIFIER__';
begin
 if current_user <> 'postgres' or current_database() <> 'postgres' then
  raise exception 'V3_ISSUER_DATABASE_OWNER_HOLD';
 end if;
 if (select count(*) from pg_roles where rolname='v3_cas_inhibit_issuer_actor'
    and not rolcanlogin and not rolinherit and rolconnlimit=0
    and not rolbypassrls and not rolsuper and not rolcreaterole
    and not rolcreatedb and not rolreplication) <> 1 then
  raise exception 'V3_ISSUER_ROLE_PRESTAGED_HOLD';
 end if;
 if exists(select 1 from pg_auth_members m join pg_roles r on
   r.oid=m.member where r.rolname='v3_cas_inhibit_issuer_actor') then
  raise exception 'V3_ISSUER_FOREIGN_MEMBERSHIP_HOLD';
 end if;
 if to_regclass('v3_cas_audit.executor_inhibit_v1') is null or
    to_regclass('v3_cas_audit.attempt_v1') is null or
    to_regprocedure('v3_cas_audit.begin_executor_inhibit_v1(text,text,text,text)') is null or
    to_regprocedure('v3_cas_audit.confirm_executor_inhibit_v1(text,timestamptz,text)') is null then
  raise exception 'V3_ISSUER_SCHEMA_MISSING_HOLD';
 end if;
 if has_function_privilege('service_role',
    'v3_cas_audit.begin_executor_inhibit_v1(text,text,text,text)','EXECUTE') or
    not has_function_privilege('v3_cas_inhibit_issuer_actor',
    'v3_cas_audit.begin_executor_inhibit_v1(text,text,text,text)','EXECUTE') or
    has_table_privilege('v3_cas_inhibit_issuer_actor',
    'v3_cas_audit.executor_inhibit_v1','INSERT') then
  raise exception 'V3_ISSUER_ACL_DRIFT_HOLD';
 end if;
 if to_regprocedure(
   'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)'
   ) is not null then
  raise exception 'V3_ISSUER_CAS_ALREADY_INSTALLED_HOLD';
 end if;
 execute format('alter role v3_cas_inhibit_issuer_actor login connection limit 1 password %L',
   v_verifier);
 if (select count(*) from pg_roles where rolname='v3_cas_inhibit_issuer_actor'
     and rolcanlogin and not rolinherit and rolconnlimit=1 and
     not rolbypassrls and not rolsuper and not rolcreaterole) <> 1 then
  raise exception 'V3_ISSUER_ENROLL_ROLLBACK';
 end if;
end;
$v3_issuer_enroll$;
commit;
'@
$sql=$sql.Replace('__ISSUER_SCRAM_VERIFIER__',$verifier)
$verifier=$null
$sqlBytes=[Text.Encoding]::ASCII.GetBytes($sql)
try{Write-SafeNew $sqlPath $sqlBytes}
finally{[Array]::Clear($sqlBytes,0,$sqlBytes.Length)}
[pscustomobject]@{state='LOCAL_ONLY_ISSUER_STAGED';
 sealed_password_currentuser_only=$true;sql_contains_scram_verifier=$true;
 manual_cloud_approval_still_required=$true;cloud_changed=$false;
 existing_reader_writer_unchanged=$true;cas_invoked=$false} |
 ConvertTo-Json -Compress
