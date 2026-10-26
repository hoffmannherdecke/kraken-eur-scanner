# V3 PAPER / ONE-SHOT / INTERACTIVE ORIGINAL HOST / SOURCE INACTIVE
# A separate manual human owner login: NO GitHub self-hosted runner access,
# NO service_role/anon/authenticated keys, no remote connection from this script.
# Produces only a DPAPI CurrentUser-sealed random credential and a locally
# protected SQL-enrollment file containing a SCRAM SHA256 VERIFIER (not password).
# SQL is NOT executed by this script. The original V3 CAS is NOT installed.
[CmdletBinding()]
param(
  [switch]$Stage,
  [switch]$VerifyLocal,
  [switch]$RemoveEnrollmentSql
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$kind = 'V3_CAS_LOCAL_OPERATOR_LOGIN_PREPARATION_INACTIVE_V1'
$role = 'v3_cas_operator_login'
$root = Join-Path $env:LOCALAPPDATA 'V3CasOperator-INACTIVE'
$secretPath = Join-Path $root 'operator-login-currentuser.dpapi'
$sqlPath = Join-Path $root 'operator-login-enroll-ONE-TIME.sql'
$entropy = [Text.Encoding]::ASCII.GetBytes('V3_CAS_OPERATOR_LOGIN_CURRENTUSER_V1')

if (-not $Stage -and -not $VerifyLocal -and -not $RemoveEnrollmentSql) {
  [pscustomobject]@{
    kind = $kind
    state = 'INACTIVE_PREVIEW'
    secret_written = $false
    remote_database_contacted = $false
    cloud_login_created = $false
    cas_role_membership_granted = $false
    v3_paper_activated = $false
    next_step = 'Review protected source, then manually run -Stage on original Windows interactive owner only'
  } | ConvertTo-Json -Compress
  return
}
if (([int][bool]$Stage + [int][bool]$VerifyLocal +
     [int][bool]$RemoveEnrollmentSql) -gt 1) {
  throw 'V3_CAS_OPERATOR_HOLD: choose exactly one local action'
}
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
if ($null -eq $id -or $null -eq $id.User -or
    $id.Name -match '(?i)\\CryptoSupportSvc$' -or
    $env:GITHUB_ACTIONS -eq 'true' -or
    -not [Environment]::UserInteractive) {
  throw 'V3_CAS_OPERATOR_HOLD: interactive owner only, never restricted GitHub runner'
}
if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
  throw 'V3_CAS_OPERATOR_HOLD: personal LOCALAPPDATA unavailable'
}
# The one private owner key must live on an actual local NTFS disk, not
# a mapped share, OneDrive redirection, linked root, or removable media.
$base = Get-Item -LiteralPath $env:LOCALAPPDATA -Force -ErrorAction Stop
$volume = [IO.DriveInfo]::new([IO.Path]::GetPathRoot($root))
if (-not $base.PSIsContainer -or
    [bool]($base.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
    -not $volume.IsReady -or
    $volume.DriveType -ne [IO.DriveType]::Fixed -or
    $volume.DriveFormat -cne 'NTFS' -or
    $volume.AvailableFreeSpace -lt 1048576) {
  throw 'V3_CAS_OPERATOR_HOLD: local NTFS owner profile unavailable'
}
$allow = @([string]$id.User.Value, 'S-1-5-18', 'S-1-5-32-544')
function Assert-LocalScope([string]$target,[bool]$directory) {
  $item = Get-Item -LiteralPath $target -Force -ErrorAction Stop
  if ([bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
      $item.PSIsContainer -ne $directory) {
    throw 'V3_CAS_OPERATOR_HOLD: local credential object is linked/wrong type'
  }
  $acl = Get-Acl -LiteralPath $target -ErrorAction Stop
  if (-not $acl.AreAccessRulesProtected) {
    throw 'V3_CAS_OPERATOR_HOLD: local credential ACL inherits external grants'
  }
  $rules = @($acl.GetAccessRules($true,$true,
      [Security.Principal.SecurityIdentifier]))
  if ($rules.Count -lt 1) {
    throw 'V3_CAS_OPERATOR_HOLD: empty credential ACL'
  }
  foreach ($ace in $rules) {
    if ($ace.AccessControlType -eq
        [Security.AccessControl.AccessControlType]::Allow -and
        [string]$ace.IdentityReference.Value -notin $allow) {
      throw 'V3_CAS_OPERATOR_HOLD: credential ACL has unrelated allow principal'
    }
  }
  $selfAllowed = @($rules | Where-Object {
    $_.AccessControlType -eq
      [Security.AccessControl.AccessControlType]::Allow -and
    [string]$_.IdentityReference.Value -ceq [string]$id.User.Value
  })
  if ($selfAllowed.Count -lt 1) {
    throw 'V3_CAS_OPERATOR_HOLD: current user is not owner of this boundary'
  }
}
function New-ProtectedAcl([bool]$directory) {
  if ($directory) {
    $acl = [Security.AccessControl.DirectorySecurity]::new()
    $flags = [Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
             [Security.AccessControl.InheritanceFlags]::ObjectInherit
  } else {
    $acl = [Security.AccessControl.FileSecurity]::new()
    $flags = [Security.AccessControl.InheritanceFlags]::None
  }
  $acl.SetAccessRuleProtection($true,$false)
  foreach ($sid in $allow) {
    $rule = [Security.AccessControl.FileSystemAccessRule]::new(
      [Security.Principal.SecurityIdentifier]::new($sid),
      [Security.AccessControl.FileSystemRights]::FullControl,
      $flags,[Security.AccessControl.PropagationFlags]::None,
      [Security.AccessControl.AccessControlType]::Allow)
    $acl.AddAccessRule($rule)
  }
  return $acl
}
function New-ProtectedByteFile([string]$path,[byte[]]$bytes) {
  # Atomic CREATE_NEW with an explicit DACL: no inherited-access race and
  # never overwrite existing secret or enrollment SQL.
  $acl = New-ProtectedAcl $false
  $fs = [IO.FileStream]::new(
    $path,[IO.FileMode]::CreateNew,
    [Security.AccessControl.FileSystemRights]::Write,
    [IO.FileShare]::None,4096,[IO.FileOptions]::WriteThrough,$acl)
  try {
    $fs.Write($bytes,0,$bytes.Length)
    $fs.Flush($true)
  } finally {
    $fs.Dispose()
  }
  Assert-LocalScope $path $false
}
if (-not [IO.Directory]::Exists($root)) {
  if ($VerifyLocal -or $RemoveEnrollmentSql) {
    throw 'V3_CAS_OPERATOR_HOLD: cannot verify/scrub missing local owner directory'
  }
  if ([IO.File]::Exists($root)) {
    throw 'V3_CAS_OPERATOR_HOLD: local operator path collides with a file'
  }
  [void][IO.Directory]::CreateDirectory($root,(New-ProtectedAcl $true))
}
Assert-LocalScope $root $true

if ($VerifyLocal) {
  # Physical LOCAL-only verifier: after -Stage and BEFORE SQL dashboard
  # enrollment, prove DPAPI CurrentUser decrypts the exact 256-bit secret
  # for which the staged one-time PostgreSQL SCRAM-SHA-256 verifier was made.
  # Neither password, verifier, salt, SQL, file paths nor hashes are printed.
  if (-not [IO.File]::Exists($secretPath) -or
      -not [IO.File]::Exists($sqlPath)) {
    throw 'V3_CAS_OPERATOR_HOLD: missing sealed password or staged SQL'
  }
  Assert-LocalScope $secretPath $false
  Assert-LocalScope $sqlPath $false
  $sealedBytes = [IO.File]::ReadAllBytes($secretPath)
  $sqlBytes = [IO.File]::ReadAllBytes($sqlPath)
  if ($sealedBytes.Length -lt 40 -or $sealedBytes.Length -gt 4096 -or
      $sqlBytes.Length -lt 1500 -or $sqlBytes.Length -gt 12000) {
    throw 'V3_CAS_OPERATOR_HOLD: unsafe staged credential file length'
  }
  $plainBytes = [Security.Cryptography.ProtectedData]::Unprotect(
    $sealedBytes,$entropy,[Security.Cryptography.DataProtectionScope]::CurrentUser)
  try {
    $localSecret = [Text.Encoding]::ASCII.GetString($plainBytes)
    if ($localSecret -cnotmatch '^[a-f0-9]{64}
  if ([IO.File]::Exists($sqlPath)) {
    Assert-LocalScope $sqlPath $false
    [IO.File]::Delete($sqlPath)
  }
  [pscustomobject]@{
    kind = $kind
    state = 'ONE_TIME_SQL_SCRUBBED'
    dpapi_login_secret_retained = [IO.File]::Exists($secretPath)
    cloud_change = $false
    cas_role_membership_granted = $false
  } | ConvertTo-Json -Compress
  return
}

if ([IO.File]::Exists($sqlPath) -or [IO.Directory]::Exists($secretPath) -or
    [IO.Directory]::Exists($sqlPath)) {
  throw 'V3_CAS_OPERATOR_HOLD: existing enrollment SQL or unexpected path; never overwrite'
}
$secret = $null
if ([IO.File]::Exists($secretPath)) {
  Assert-LocalScope $secretPath $false
  $sealed = [IO.File]::ReadAllBytes($secretPath)
  if ($sealed.Length -gt 4096 -or $sealed.Length -lt 40) {
    throw 'V3_CAS_OPERATOR_HOLD: invalid sealed secret format'
  }
  $plain = [Security.Cryptography.ProtectedData]::Unprotect(
    $sealed,$entropy,[Security.Cryptography.DataProtectionScope]::CurrentUser)
  try {
    $secret = [Text.Encoding]::ASCII.GetString($plain)
  } finally {
    [Array]::Clear($plain,0,$plain.Length)
  }
  if ($secret -cnotmatch '^[0-9a-f]{64}$') {
    throw 'V3_CAS_OPERATOR_HOLD: unreadable old secret'
  }
  $localStatus = 'EXISTING_DPAPI_SECRET_REUSED'
} else {
  $random = New-Object byte[] 32
  $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
  try { $rng.GetBytes($random) } finally { $rng.Dispose() }
  try {
    $secret = [BitConverter]::ToString($random).Replace('-','').ToLowerInvariant()
  } finally { [Array]::Clear($random,0,$random.Length) }
  $clear = [Text.Encoding]::ASCII.GetBytes($secret)
  try {
    $sealed = [Security.Cryptography.ProtectedData]::Protect(
      $clear,$entropy,[Security.Cryptography.DataProtectionScope]::CurrentUser)
  } finally { [Array]::Clear($clear,0,$clear.Length) }
  New-ProtectedByteFile $secretPath $sealed
  $localStatus = 'NEW_DPAPI_SECRET_GENERATED'
}

# PostgreSQL SCRAM-SHA-256 verifier: PBKDF2 -> ClientKey/StoredKey/ServerKey.
# The 256-bit random secret is never written or emitted as plaintext.
$salt = New-Object byte[] 16
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
try { $rng.GetBytes($salt) } finally { $rng.Dispose() }
$pbkdf = [Security.Cryptography.Rfc2898DeriveBytes]::new(
  $secret,$salt,4096,[Security.Cryptography.HashAlgorithmName]::SHA256)
try { $salted = $pbkdf.GetBytes(32) } finally { $pbkdf.Dispose() }
$hmac = [Security.Cryptography.HMACSHA256]::new($salted)
try {
  $clientKey = $hmac.ComputeHash([Text.Encoding]::ASCII.GetBytes('Client Key'))
  $serverKey = $hmac.ComputeHash([Text.Encoding]::ASCII.GetBytes('Server Key'))
} finally { $hmac.Dispose(); [Array]::Clear($salted,0,$salted.Length) }
$sha = [Security.Cryptography.SHA256]::Create()
try { $storedKey = $sha.ComputeHash($clientKey) } finally { $sha.Dispose() }
[Array]::Clear($clientKey,0,$clientKey.Length)
$verifier = 'SCRAM-SHA-256$4096:' +
  [Convert]::ToBase64String($salt) + '$' +
  [Convert]::ToBase64String($storedKey) + ':' +
  [Convert]::ToBase64String($serverKey)
[Array]::Clear($storedKey,0,$storedKey.Length)
[Array]::Clear($serverKey,0,$serverKey.Length)
[Array]::Clear($salt,0,$salt.Length)

# THIS SINGLE SQL SCRIPT is user-executed explicitly in existing Supabase
# SQL Editor.  It holds ONLY the SCRAM verifier; no raw login secret or admin
# password. Rejection leaves the separate user role NOLOGIN as before.
$sql = @'
-- V3 CAS operator login enrollment: MANUAL REVIEWED ONE-SHOT ONLY.
-- No executor role membership, no CAS function, no active V3 Paper or audit.
-- SCRAM verifier is credential material: do not paste into GitHub/chat.
begin;
do $v3_cas_local_login$
begin
  if current_user <> 'postgres' then
    raise exception 'V3_CAS_LOGIN_OWNER_NOT_POSTGRES';
  end if;
  if (select count(*) from pg_catalog.pg_roles r
      where r.rolname='v3_cas_operator_login'
        and not r.rolcanlogin and not r.rolinherit
        and not r.rolbypassrls and not r.rolsuper
        and not r.rolcreaterole and not r.rolcreatedb
        and not r.rolreplication) <> 1 then
    raise exception 'V3_CAS_LOGIN_NOT_PRESTAGED_SAFE_NOLOGIN';
  end if;
  if exists (
      select 1 from pg_catalog.pg_auth_members m
      join pg_catalog.pg_roles r on r.oid=m.roleid or r.oid=m.member
      where r.rolname='v3_cas_operator_login'
        and not (
          m.roleid=r.oid and m.member=(
             select oid from pg_catalog.pg_roles where rolname='postgres')
          and m.admin_option and not m.set_option and not m.inherit_option
        )
    ) then
    raise exception 'V3_CAS_LOGIN_UNEXPECTED_MEMBERSHIP';
  end if;
  if pg_catalog.to_regnamespace('v3_cas_audit') is not null
      or pg_catalog.to_regprocedure(
       'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)'
      ) is not null then
    raise exception 'V3_CAS_LOGIN_RUNTIME_ALREADY_PRESENT';
  end if;
  if (select count(*) from pg_catalog.pg_roles r
      where r.rolname in (
        'v3_cas_executor','v3_cas_audit_writer','v3_cas_audit_reader')
        and not r.rolcanlogin and not r.rolinherit and not r.rolbypassrls
        and not r.rolsuper and not r.rolcreatedb and not r.rolcreaterole
        and not r.rolreplication) <> 3 then
    raise exception 'V3_CAS_LOGIN_ORIGINAL_THREE_ROLES_CHANGED';
  end if;
  if exists (
      select 1 from pg_catalog.pg_proc p
      join pg_catalog.pg_namespace n on n.oid=p.pronamespace
      where n.nspname='public'
      and exists (
        select 1 from pg_catalog.aclexplode(
          coalesce(p.proacl,pg_catalog.acldefault('f',p.proowner))) x
        where x.grantee=0 and x.privilege_type='EXECUTE')
    ) then
    raise exception 'V3_CAS_LOGIN_PUBLIC_FUNCTION_EXECUTE_DRIFT';
  end if;
  execute format('alter role v3_cas_operator_login login password %L',
                 '__SCRAM_VERIFIER__');
  if (select count(*) from pg_catalog.pg_roles
      where rolname='v3_cas_operator_login' and rolcanlogin
        and not rolinherit and not rolbypassrls and not rolsuper
        and rolconnlimit=1) <> 1 then
    raise exception 'V3_CAS_LOGIN_ATOMIC_ENROLL_CHECK_FAILED';
  end if;
end;
$v3_cas_local_login$;
commit;
'@
# The pre-staged role has connection-limit 1, no app access/memberships.
# The verifier is not a login password and is never printed in logs.
$sql = $sql.Replace('__SCRAM_VERIFIER__',$verifier)
$bytes = [Text.Encoding]::ASCII.GetBytes($sql + [Environment]::NewLine)
try { New-ProtectedByteFile $sqlPath $bytes } finally {
  [Array]::Clear($bytes,0,$bytes.Length)
}
$secret = $null
$verifier = $null
[pscustomobject]@{
  kind = $kind
  state = $localStatus
  encrypted_secret_local_only = $true
  sql_contains_only_scram_verifier_not_password = $true
  enrollment_sql_file_local_to_interactive_user = $sqlPath
  db_role_name = $role
  supabase_sql_editor_execution_required = $true
  supabase_ddl_executed_by_this_script = $false
  cas_role_membership_granted = $false
  v3_paper_activated = $false
} | ConvertTo-Json -Compress
) {
      throw 'V3_CAS_OPERATOR_HOLD: sealed password shape mismatch'
    }
  } finally {
    [Array]::Clear($plainBytes,0,$plainBytes.Length)
  }
  $sqlText = [Text.Encoding]::ASCII.GetString($sqlBytes)
  [Array]::Clear($sqlBytes,0,$sqlBytes.Length)
  $verifierMatches = [regex]::Matches($sqlText,
    "SCRAM-SHA-256\`$4096:([A-Za-z0-9+/=]+)\`$([A-Za-z0-9+/=]+):([A-Za-z0-9+/=]+)")
  if ($verifierMatches.Count -ne 1 -or
      $sqlText -cnotmatch 'alter role v3_cas_operator_login login password %L' -or
      $sqlText -cnotmatch 'V3_CAS_LOGIN_RUNTIME_ALREADY_PRESENT' -or
      $sqlText -cnotmatch 'V3_CAS_LOGIN_PUBLIC_FUNCTION_EXECUTE_DRIFT' -or
      $sqlText -cnotmatch 'V3_CAS_LOGIN_UNEXPECTED_MEMBERSHIP') {
    throw 'V3_CAS_OPERATOR_HOLD: one-time SQL content changed or not recognized'
  }
  $saltBytes = [Convert]::FromBase64String($verifierMatches[0].Groups[1].Value)
  $expectedStored = [Convert]::FromBase64String($verifierMatches[0].Groups[2].Value)
  $expectedServer = [Convert]::FromBase64String($verifierMatches[0].Groups[3].Value)
  if ($saltBytes.Length -ne 16 -or $expectedStored.Length -ne 32 -or
      $expectedServer.Length -ne 32) {
    throw 'V3_CAS_OPERATOR_HOLD: SCRAM verifier shape mismatch'
  }
  $pbkdf = [Security.Cryptography.Rfc2898DeriveBytes]::new(
    $localSecret,$saltBytes,4096,[Security.Cryptography.HashAlgorithmName]::SHA256)
  try { $saltedBytes = $pbkdf.GetBytes(32) } finally { $pbkdf.Dispose() }
  $mac = [Security.Cryptography.HMACSHA256]::new($saltedBytes)
  try {
    $localClient = $mac.ComputeHash([Text.Encoding]::ASCII.GetBytes('Client Key'))
    $localServer = $mac.ComputeHash([Text.Encoding]::ASCII.GetBytes('Server Key'))
  } finally {
    $mac.Dispose()
    [Array]::Clear($saltedBytes,0,$saltedBytes.Length)
  }
  $sha = [Security.Cryptography.SHA256]::Create()
  try { $localStored = $sha.ComputeHash($localClient) } finally { $sha.Dispose() }
  [Array]::Clear($localClient,0,$localClient.Length)
  # Fixed-length XOR comparison: no credential, hash or mismatch byte output.
  $difference = 0
  for ($i=0; $i -lt 32; $i++) {
    $difference = $difference -bor ([int]$localStored[$i] -bxor
                                    [int]$expectedStored[$i])
    $difference = $difference -bor ([int]$localServer[$i] -bxor
                                    [int]$expectedServer[$i])
  }
  [Array]::Clear($localStored,0,$localStored.Length)
  [Array]::Clear($localServer,0,$localServer.Length)
  [Array]::Clear($expectedStored,0,$expectedStored.Length)
  [Array]::Clear($expectedServer,0,$expectedServer.Length)
  [Array]::Clear($saltBytes,0,$saltBytes.Length)
  $localSecret = $null
  $sqlText = $null
  if ($difference -ne 0) {
    throw 'V3_CAS_OPERATOR_HOLD: DPAPI and local SCRAM verifier mismatch'
  }
  [pscustomobject]@{
    kind = $kind
    state = 'LOCAL_DPAPI_SCRAM_ROUNDTRIP_PASS'
    secret_or_verifier_displayed = $false
    sql_still_local_only = $true
    remote_database_contacted = $false
    cloud_login_created_by_this_script = $false
    cas_role_membership_granted = $false
    v3_paper_activated = $false
  } | ConvertTo-Json -Compress
  return
}

if ($RemoveEnrollmentSql) {
  if ([IO.File]::Exists($sqlPath)) {
    Assert-LocalScope $sqlPath $false
    [IO.File]::Delete($sqlPath)
  }
  [pscustomobject]@{
    kind = $kind
    state = 'ONE_TIME_SQL_SCRUBBED'
    dpapi_login_secret_retained = [IO.File]::Exists($secretPath)
    cloud_change = $false
    cas_role_membership_granted = $false
  } | ConvertTo-Json -Compress
  return
}

if ([IO.File]::Exists($sqlPath) -or [IO.Directory]::Exists($secretPath) -or
    [IO.Directory]::Exists($sqlPath)) {
  throw 'V3_CAS_OPERATOR_HOLD: existing enrollment SQL or unexpected path; never overwrite'
}
$secret = $null
if ([IO.File]::Exists($secretPath)) {
  Assert-LocalScope $secretPath $false
  $sealed = [IO.File]::ReadAllBytes($secretPath)
  if ($sealed.Length -gt 4096 -or $sealed.Length -lt 40) {
    throw 'V3_CAS_OPERATOR_HOLD: invalid sealed secret format'
  }
  $plain = [Security.Cryptography.ProtectedData]::Unprotect(
    $sealed,$entropy,[Security.Cryptography.DataProtectionScope]::CurrentUser)
  try {
    $secret = [Text.Encoding]::ASCII.GetString($plain)
  } finally {
    [Array]::Clear($plain,0,$plain.Length)
  }
  if ($secret -cnotmatch '^[0-9a-f]{64}$') {
    throw 'V3_CAS_OPERATOR_HOLD: unreadable old secret'
  }
  $localStatus = 'EXISTING_DPAPI_SECRET_REUSED'
} else {
  $random = New-Object byte[] 32
  $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
  try { $rng.GetBytes($random) } finally { $rng.Dispose() }
  try {
    $secret = [BitConverter]::ToString($random).Replace('-','').ToLowerInvariant()
  } finally { [Array]::Clear($random,0,$random.Length) }
  $clear = [Text.Encoding]::ASCII.GetBytes($secret)
  try {
    $sealed = [Security.Cryptography.ProtectedData]::Protect(
      $clear,$entropy,[Security.Cryptography.DataProtectionScope]::CurrentUser)
  } finally { [Array]::Clear($clear,0,$clear.Length) }
  New-ProtectedByteFile $secretPath $sealed
  $localStatus = 'NEW_DPAPI_SECRET_GENERATED'
}

# PostgreSQL SCRAM-SHA-256 verifier: PBKDF2 -> ClientKey/StoredKey/ServerKey.
# The 256-bit random secret is never written or emitted as plaintext.
$salt = New-Object byte[] 16
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
try { $rng.GetBytes($salt) } finally { $rng.Dispose() }
$pbkdf = [Security.Cryptography.Rfc2898DeriveBytes]::new(
  $secret,$salt,4096,[Security.Cryptography.HashAlgorithmName]::SHA256)
try { $salted = $pbkdf.GetBytes(32) } finally { $pbkdf.Dispose() }
$hmac = [Security.Cryptography.HMACSHA256]::new($salted)
try {
  $clientKey = $hmac.ComputeHash([Text.Encoding]::ASCII.GetBytes('Client Key'))
  $serverKey = $hmac.ComputeHash([Text.Encoding]::ASCII.GetBytes('Server Key'))
} finally { $hmac.Dispose(); [Array]::Clear($salted,0,$salted.Length) }
$sha = [Security.Cryptography.SHA256]::Create()
try { $storedKey = $sha.ComputeHash($clientKey) } finally { $sha.Dispose() }
[Array]::Clear($clientKey,0,$clientKey.Length)
$verifier = 'SCRAM-SHA-256$4096:' +
  [Convert]::ToBase64String($salt) + '$' +
  [Convert]::ToBase64String($storedKey) + ':' +
  [Convert]::ToBase64String($serverKey)
[Array]::Clear($storedKey,0,$storedKey.Length)
[Array]::Clear($serverKey,0,$serverKey.Length)
[Array]::Clear($salt,0,$salt.Length)

# THIS SINGLE SQL SCRIPT is user-executed explicitly in existing Supabase
# SQL Editor.  It holds ONLY the SCRAM verifier; no raw login secret or admin
# password. Rejection leaves the separate user role NOLOGIN as before.
$sql = @'
-- V3 CAS operator login enrollment: MANUAL REVIEWED ONE-SHOT ONLY.
-- No executor role membership, no CAS function, no active V3 Paper or audit.
-- SCRAM verifier is credential material: do not paste into GitHub/chat.
begin;
do $v3_cas_local_login$
begin
  if current_user <> 'postgres' then
    raise exception 'V3_CAS_LOGIN_OWNER_NOT_POSTGRES';
  end if;
  if (select count(*) from pg_catalog.pg_roles r
      where r.rolname='v3_cas_operator_login'
        and not r.rolcanlogin and not r.rolinherit
        and not r.rolbypassrls and not r.rolsuper
        and not r.rolcreaterole and not r.rolcreatedb
        and not r.rolreplication) <> 1 then
    raise exception 'V3_CAS_LOGIN_NOT_PRESTAGED_SAFE_NOLOGIN';
  end if;
  if exists (
      select 1 from pg_catalog.pg_auth_members m
      join pg_catalog.pg_roles r on r.oid=m.roleid or r.oid=m.member
      where r.rolname='v3_cas_operator_login'
        and not (
          m.roleid=r.oid and m.member=(
             select oid from pg_catalog.pg_roles where rolname='postgres')
          and m.admin_option and not m.set_option and not m.inherit_option
        )
    ) then
    raise exception 'V3_CAS_LOGIN_UNEXPECTED_MEMBERSHIP';
  end if;
  if pg_catalog.to_regnamespace('v3_cas_audit') is not null
      or pg_catalog.to_regprocedure(
       'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)'
      ) is not null then
    raise exception 'V3_CAS_LOGIN_RUNTIME_ALREADY_PRESENT';
  end if;
  if (select count(*) from pg_catalog.pg_roles r
      where r.rolname in (
        'v3_cas_executor','v3_cas_audit_writer','v3_cas_audit_reader')
        and not r.rolcanlogin and not r.rolinherit and not r.rolbypassrls
        and not r.rolsuper and not r.rolcreatedb and not r.rolcreaterole
        and not r.rolreplication) <> 3 then
    raise exception 'V3_CAS_LOGIN_ORIGINAL_THREE_ROLES_CHANGED';
  end if;
  if exists (
      select 1 from pg_catalog.pg_proc p
      join pg_catalog.pg_namespace n on n.oid=p.pronamespace
      where n.nspname='public'
      and exists (
        select 1 from pg_catalog.aclexplode(
          coalesce(p.proacl,pg_catalog.acldefault('f',p.proowner))) x
        where x.grantee=0 and x.privilege_type='EXECUTE')
    ) then
    raise exception 'V3_CAS_LOGIN_PUBLIC_FUNCTION_EXECUTE_DRIFT';
  end if;
  execute format('alter role v3_cas_operator_login login password %L',
                 '__SCRAM_VERIFIER__');
  if (select count(*) from pg_catalog.pg_roles
      where rolname='v3_cas_operator_login' and rolcanlogin
        and not rolinherit and not rolbypassrls and not rolsuper
        and rolconnlimit=1) <> 1 then
    raise exception 'V3_CAS_LOGIN_ATOMIC_ENROLL_CHECK_FAILED';
  end if;
end;
$v3_cas_local_login$;
commit;
'@
# The pre-staged role has connection-limit 1, no app access/memberships.
# The verifier is not a login password and is never printed in logs.
$sql = $sql.Replace('__SCRAM_VERIFIER__',$verifier)
$bytes = [Text.Encoding]::ASCII.GetBytes($sql + [Environment]::NewLine)
try { New-ProtectedByteFile $sqlPath $bytes } finally {
  [Array]::Clear($bytes,0,$bytes.Length)
}
$secret = $null
$verifier = $null
[pscustomobject]@{
  kind = $kind
  state = $localStatus
  encrypted_secret_local_only = $true
  sql_contains_only_scram_verifier_not_password = $true
  enrollment_sql_file_local_to_interactive_user = $sqlPath
  db_role_name = $role
  supabase_sql_editor_execution_required = $true
  supabase_ddl_executed_by_this_script = $false
  cas_role_membership_granted = $false
  v3_paper_activated = $false
} | ConvertTo-Json -Compress
