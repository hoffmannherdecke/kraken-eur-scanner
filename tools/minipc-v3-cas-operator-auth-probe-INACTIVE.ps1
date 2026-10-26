# V3 Paper: source-only until manual -Probe by interactive original Mini-PC owner.
# Independent read-only TLS-authenticated role proof. No CAS, SQL DDL, or trading.
[CmdletBinding()]
param(
  [switch]$Probe,
  [ValidateSet('Direct','SessionPooler')][string]$Mode = 'Direct',
  [string]$PoolerHost = '',
  [string]$CaFile = ''
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$project = 'nlgzjmqgwueojlyqmoru'
$role = 'v3_cas_operator_login'
$kind = 'V3_CAS_ORIGINALHOST_SSL_AUTH_PROBE_V1'
if (-not $Probe) {
  [pscustomobject]@{
    kind = $kind; state = 'INACTIVE_PREVIEW'; secret_read = $false;
    remote_contacted = $false; database_modified = $false
  } | ConvertTo-Json -Compress
  return
}
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
if ($null -eq $id -or $null -eq $id.User -or
    $id.Name -match '(?i)\\CryptoSupportSvc$' -or
    $env:GITHUB_ACTIONS -eq 'true' -or
    -not [Environment]::UserInteractive) {
  throw 'V3_CAS_AUTH_HOLD: interactive owner only, never GitHub runner'
}
if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
  throw 'V3_CAS_AUTH_HOLD: local owner profile missing'
}
$root = Join-Path $env:LOCALAPPDATA 'V3CasOperator-INACTIVE'
$secretFile = Join-Path $root 'operator-login-currentuser.dpapi'
$entropy = [Text.Encoding]::ASCII.GetBytes('V3_CAS_OPERATOR_LOGIN_CURRENTUSER_V1')
if ($Mode -eq 'Direct') {
  if ($PoolerHost -ne '') { throw 'V3_CAS_AUTH_HOLD: unexpected pooler host' }
  $targetHost = 'db.' + $project + '.supabase.co'
  $dbLogin = $role
} else {
  if ($PoolerHost -cnotmatch '^[a-z0-9-]+(?:\.[a-z0-9-]+)*\.pooler\.supabase\.com$') {
    throw 'V3_CAS_AUTH_HOLD: obtain exact Session pooler hostname from Supabase Connect'
  }
  $targetHost = $PoolerHost
  $dbLogin = $role + '.' + $project
}
# Only permit an existing installed PostgreSQL 17/18 client; no PATH/shell fallback.
$pgRoot = Join-Path $env:ProgramFiles 'PostgreSQL'
$exe = ''
foreach ($major in @('18','17')) {
  $candidate = Join-Path (Join-Path (Join-Path $pgRoot $major) 'bin') 'psql.exe'
  if ([IO.File]::Exists($candidate)) { $exe = $candidate; break }
}
if (-not $exe) { throw 'V3_CAS_AUTH_HOLD: PostgreSQL 17+ psql.exe not installed; no credential read' }
foreach ($path in @($pgRoot,(Split-Path (Split-Path $exe -Parent) -Parent),
                    (Split-Path $exe -Parent),$exe)) {
  $item = Get-Item -LiteralPath $path -Force -ErrorAction Stop
  if ([bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
    throw 'V3_CAS_AUTH_HOLD: linked PostgreSQL installation forbidden'
  }
}
# libpq 17+ system trust or the original dashboard-provided CA PEM; no TLS downgrade.
$caTrust = 'system'
if (-not [string]::IsNullOrWhiteSpace($CaFile)) {
  $ca = Get-Item -LiteralPath $CaFile -Force -ErrorAction Stop
  if ($ca.PSIsContainer -or
      [bool]($ca.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
    throw 'V3_CAS_AUTH_HOLD: unsafe CA file'
  }
  $caTrust = $ca.FullName
}
$volume = [IO.DriveInfo]::new([IO.Path]::GetPathRoot($secretFile))
if (-not $volume.IsReady -or $volume.DriveType -ne [IO.DriveType]::Fixed -or
    $volume.DriveFormat -cne 'NTFS') {
  throw 'V3_CAS_AUTH_HOLD: private owner local NTFS unavailable'
}
foreach ($path in @($root,$secretFile)) {
  $item = Get-Item -LiteralPath $path -Force -ErrorAction Stop
  if ([bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
    throw 'V3_CAS_AUTH_HOLD: linked secret path'
  }
  $acl = Get-Acl -LiteralPath $path -ErrorAction Stop
  if (-not $acl.AreAccessRulesProtected) {
    throw 'V3_CAS_AUTH_HOLD: credential ACL no longer private'
  }
  $allow = @([string]$id.User.Value,'S-1-5-18','S-1-5-32-544')
  $self = $false
  foreach ($rule in @($acl.GetAccessRules(
      $true,$true,[Security.Principal.SecurityIdentifier]))) {
    if ($rule.AccessControlType -eq [Security.AccessControl.AccessControlType]::Allow) {
      $principal = [string]$rule.IdentityReference.Value
      if ($principal -notin $allow) { throw 'V3_CAS_AUTH_HOLD: unexpected ACL member' }
      if ($principal -ceq [string]$id.User.Value) { $self = $true }
    }
  }
  if (-not $self) { throw 'V3_CAS_AUTH_HOLD: owner not on protected ACL' }
}
# No SQL/verifier enrollment file is needed for this network authentication test.
# Map private libpq stderr to one fixed public diagnostic category.
# Never emit raw stderr, server text, endpoint, verifier or password.
function Get-PsqlFailureCategory([string]$errorText) {
  # The SQLSTATE representation is locale-independent: never echo raw libpq stderr.
  if ($errorText -match '(?i)\b28P01\b') { return 'AUTH_CREDENTIAL_REJECTED' }
  if ($errorText -match '(?i)\b28000\b') { return 'AUTH_OR_HBA_RESTRICTION' }
  if ($errorText -match '(?i)\b53300\b') { return 'DB_CONNECTION_LIMIT' }
  if ($errorText -match '(?i)\b(3D000|42501)\b') { return 'DATABASE_CONNECT_PERMISSION' }
  if ($errorText -match '(?i)\b(42601|08P01|22023)\b') { return 'CLIENT_OR_QUERY_SYNTAX' }
  if ($errorText -match '(?i)\bXX000\b') { return 'DB_INTERNAL_FAILURE' }
  # A Windows installation may localize client messages despite psql defaults.
  if ($errorText -match '(?i)passwort|kennwort|password|fe_sendauth') {
    return 'AUTH_CREDENTIAL_REJECTED'
  }
  if ($errorText -match '(?i)certificate|sslrootcert|root\.crt|verify-full|ssl error|certificate verify failed') {
    return 'TLS_CA_OR_HOSTNAME_VERIFICATION'
  }
  if ($errorText -match '(?i)could not translate host name|name or service not known|no such host|temporary failure in name resolution') {
    return 'DNS_RESOLUTION'
  }
  if ($errorText -match '(?i)network is unreachable|no route to host|connection timed out|timeout expired|could not connect to server|connection refused|actively refused') {
    return 'NETWORK_ROUTE_OR_PORT'
  }
  if ($errorText -match '(?i)password authentication failed|no password supplied|authentication failed|invalid password') {
    return 'AUTH_CREDENTIAL_REJECTED'
  }
  if ($errorText -match '(?i)tenant or user not found|role .* does not exist|unknown user|server login failed') {
    return 'ROLE_OR_POOLER_ROUTING'
  }
  if ($errorText -match '(?i)permission denied for database|database .* does not exist') {
    return 'DATABASE_CONNECT_PERMISSION'
  }
  if ($errorText -match '(?i)unsupported startup parameter|invalid command-line argument|invalid option|unrecognized configuration parameter|option .* not supported') {
    return 'CLIENT_OR_STARTUP_OPTION'
  }
  return 'OTHER_DB_OR_CLIENT_FAILURE'
}
function Invoke-PsqlBounded([string]$fixedArguments,[string]$password,[bool]$network) {
  $p = [Diagnostics.Process]::new()
  try {
    $s = [Diagnostics.ProcessStartInfo]::new()
    $s.FileName = $exe
    $s.Arguments = $fixedArguments
    $s.UseShellExecute = $false
    $s.CreateNoWindow = $true
    $s.RedirectStandardOutput = $true
    $s.RedirectStandardError = $true
    if ($network) {
      $s.EnvironmentVariables['PGPASSWORD'] = $password
      $s.EnvironmentVariables['PGHOST'] = $targetHost
      $s.EnvironmentVariables['PGHOSTADDR'] = ''
      $s.EnvironmentVariables['PGUSER'] = $dbLogin
      $s.EnvironmentVariables['PGPORT'] = '5432'
      $s.EnvironmentVariables['PGDATABASE'] = 'postgres'
      $s.EnvironmentVariables['PGSSLMODE'] = 'verify-full'
      $s.EnvironmentVariables['PGSSLROOTCERT'] = $caTrust
      $s.EnvironmentVariables['PGCONNECT_TIMEOUT'] = '8'
      $s.EnvironmentVariables['PGOPTIONS'] = '-c default_transaction_read_only=on -c statement_timeout=10000'
      $s.EnvironmentVariables['PGPASSFILE'] = ''
      $s.EnvironmentVariables['PGSERVICE'] = ''
      $s.EnvironmentVariables['PGSSLCERT'] = ''
      $s.EnvironmentVariables['PGSSLKEY'] = ''
      $s.EnvironmentVariables['PGAPPNAME'] = 'v3_cas_operator_originalhost_one_shot'
      # Suppress locale-dependent libpq message text; categories and SQLSTATE only.
      $s.EnvironmentVariables['LC_ALL'] = 'C'
      $s.EnvironmentVariables['LC_MESSAGES'] = 'C'
      $s.EnvironmentVariables['LANG'] = 'C'
    }
    $p.StartInfo = $s
    if (-not $p.Start()) { throw 'V3_CAS_AUTH_HOLD: PostgreSQL client failed to start' }
    if (-not $p.WaitForExit(20000)) {
      try { $p.Kill() } catch { }
      throw 'V3_CAS_AUTH_HOLD: bounded auth timeout'
    }
    $result = $p.StandardOutput.ReadToEnd().Trim()
    $privateError = $p.StandardError.ReadToEnd()
    $failureClass = if ($p.ExitCode -eq 0) { 'NONE' } else {
      Get-PsqlFailureCategory $privateError
    }
    $privateError = $null
    return [pscustomobject]@{code=$p.ExitCode; output=$result; failure_class=$failureClass}
  } finally { $p.Dispose() }
}
$version = Invoke-PsqlBounded '-V' '' $false
if ($version.code -ne 0 -or
    $version.output -notmatch 'psql \(PostgreSQL\) (17|18)\.[0-9]+') {
  throw 'V3_CAS_AUTH_HOLD: unsupported libpq client'
}
# Windows PowerShell 5.1 does not reliably autoload ProtectedData's .NET assembly.
# The original owner's already-verified local stage explicitly loads System.Security.
# Perform this before reading any credential, without network or elevated privileges.
try {
  Add-Type -AssemblyName System.Security -ErrorAction Stop
} catch {
  throw 'V3_CAS_AUTH_HOLD: Windows system cryptography unavailable; no credential read'
}
$sealed = [IO.File]::ReadAllBytes($secretFile)
if ($sealed.Length -lt 40 -or $sealed.Length -gt 4096) {
  throw 'V3_CAS_AUTH_HOLD: existing sealed credential format invalid; do not regenerate'
}
$raw = [Security.Cryptography.ProtectedData]::Unprotect(
  $sealed,[Text.Encoding]::ASCII.GetBytes('V3_CAS_OPERATOR_LOGIN_CURRENTUSER_V1'),
  [Security.Cryptography.DataProtectionScope]::CurrentUser)
try { $password = [Text.Encoding]::ASCII.GetString($raw) }
finally { [Array]::Clear($raw,0,$raw.Length) }
if ($password -cnotmatch '^[0-9a-f]{64}$') {
  throw 'V3_CAS_AUTH_HOLD: DPAPI secret format invalid'
}
# Verify effective authenticated identity and TLS INSIDE the actual DB session.
# Connection is also checked by libpq against root CA and DNS (verify-full).
$query = '-X -w -A -t -q -v ON_ERROR_STOP=1 -v VERBOSITY=sqlstate -c "select current_user,session_user,(select ssl from pg_catalog.pg_stat_ssl where pid=pg_backend_pid())"'
try { $result = Invoke-PsqlBounded $query $password $true }
finally { $password = $null }
if ($result.code -ne 0) {
  # Exit code is non-secret and distinguishes psql client, connection and SQL failures.
  # It never contains stderr, the password or the verifier.
  $safeExit = if ($result.code -in @(1,2,3)) { [int]$result.code } else { 99 }
  throw ('V3_CAS_AUTH_HOLD: ' + $result.failure_class + '; PSQL_EXIT_' + $safeExit)
}
if ($result.output -cne ($role+'|'+$role+'|t')) {
  throw 'V3_CAS_AUTH_HOLD: AUTHENTICATED_IDENTITY_OR_RESULT_MISMATCH'
}
[pscustomobject]@{
  kind = $kind
  state = 'ORIGINALHOST_POSTGRES_SSL_AUTH_PASS'
  source = 'MANUAL_INTERACTIVE_ORIGINAL_MINIPC_OWNER'
  authenticated_role = $role
  connection_mode = $Mode
  ssl_mode = 'verify-full'
  ssl_hostname_ca_checked = $true
  pg_stat_ssl_checked = $true
  only_select_issued = $true
  password_or_verifier_displayed = $false
  cas_invoked = $false
  paper_activated = $false
} | ConvertTo-Json -Compress
