# V3 Paper #99 – single independent Notebook issuer, explicitly INACTIVE source.
# One-time LOCAL credential preparation only. Never contacts Supabase or invokes CAS.
# Existing reader/writer DPAPI identities, Mini-PC and active V2R4 are untouched.
[CmdletBinding()]
param([switch]$Stage,[switch]$VerifyLocal,[switch]$RemoveEnrollmentSql)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if (([int]$Stage.IsPresent+[int]$VerifyLocal.IsPresent+
     [int]$RemoveEnrollmentSql.IsPresent) -gt 1) { throw 'V3_ISSUER_MODE_CONFLICT' }
$role='v3_cas_inhibit_issuer_actor'
$root=Join-Path $env:LOCALAPPDATA 'V3CasIndependentIssuer'
$secretPath=Join-Path $root 'issuer-currentuser.dpapi'
$sqlPath=Join-Path $root 'issuer-enroll-ONE-TIME.sql'
$entropy=[Text.Encoding]::ASCII.GetBytes('V3_CAS_INDEPENDENT_ISSUER_NOTEBOOK_V1')
if (-not ($Stage -or $VerifyLocal -or $RemoveEnrollmentSql)) {
 [pscustomobject]@{state='INACTIVE_PREVIEW';role=$role;network_used=$false;
   credential_created=$false;cloud_changed=$false;cas_invoked=$false} |
   ConvertTo-Json -Compress
 return
}
# Windows PowerShell 5.1 does not always autoload the DPAPI type.
# Resolve the built-in framework assembly BEFORE creating any local enrollment files.
Add-Type -AssemblyName System.Security -ErrorAction Stop
if (-not ([type]::GetType('System.Security.Cryptography.ProtectedData, System.Security', $false))) {
 throw 'V3_ISSUER_DPAPI_FRAMEWORK_UNAVAILABLE'
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
if ($RemoveEnrollmentSql -or $VerifyLocal) {
 if (-not [IO.Directory]::Exists($root)) {throw 'V3_ISSUER_NOT_STAGED'}
} elseif (-not [IO.Directory]::Exists($root)) {
 [void][IO.Directory]::CreateDirectory($root,(New-SafeAcl $true))
}
Assert-Safe $root $true
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
function Write-SafeNew([string]$path,[byte[]]$bytes) {
 $fs=[IO.FileStream]::new($path,[IO.FileMode]::CreateNew,
    [Security.AccessControl.FileSystemRights]::Write,[IO.FileShare]::None,
    4096,[IO.FileOptions]::WriteThrough,(New-SafeAcl $false))
 try{$fs.Write($bytes,0,$bytes.Length);$fs.Flush($true)}
 finally{$fs.Dispose()}
 Assert-Safe $path $false
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
