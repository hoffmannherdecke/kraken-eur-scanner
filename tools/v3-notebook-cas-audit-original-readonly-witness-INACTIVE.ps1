# V3 Paper – original Issue #99: one-time Notebook-held, READ-ONLY Stage3 Cloud audit.
# SOURCE-ONLY. No scheduler, CAS RPC, Stage4 epoch opener, new credentials, or Paper switch.
# Reuses the TWO existing DPAPI CurrentUser identities enrolled and authenticated 27 Oct.
# Session-pooler TLS sslmode=require encrypts transport, but does NOT check the server CA.
# A PASS is scoped to THIS query only, never a durable intent or release authorization.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$psql = 'C:\Program Files\PostgreSQL\17\bin\psql.exe'
$dir = Join-Path $env:LOCALAPPDATA 'V3CasAuditActors'
$hostName = 'aws-1-eu-west-1.pooler.supabase.com'
$project = 'nlgzjmqgwueojlyqmoru'
if ($env:OS -ne 'Windows_NT' -or -not [IO.File]::Exists($psql)) {
    throw 'V3_STAGE3_READONLY_WINDOWS_PSQL17_REQUIRED'
}
Add-Type -AssemblyName System.Security -ErrorAction Stop
$checks = @(
    @{
        Name = 'WRITER'
        File = 'writer.dpapi'
        Login = 'v3_cas_audit_writer_actor'
        Sql = @'
SET ROLE v3_cas_audit_writer;
BEGIN TRANSACTION READ ONLY;
SELECT CASE WHEN
  session_user = 'v3_cas_audit_writer_actor'
  AND current_user = 'v3_cas_audit_writer'
  AND (SELECT count(*) FROM v3_cas_audit.epoch_v1) = 0
  AND pg_catalog.has_function_privilege(current_user,
      'v3_cas_audit.append_intent_v1(text,uuid,text,text,text)','EXECUTE')
  AND NOT pg_catalog.has_table_privilege(current_user,
      'v3_cas_audit.intent_v1','SELECT')
  AND NOT pg_catalog.has_table_privilege(current_user,
      'v3_cas_audit.intent_v1','INSERT')
  AND NOT pg_catalog.pg_has_role(session_user,
      'v3_cas_audit_reader','SET')
THEN 'PASS' ELSE 'HOLD' END;
COMMIT;
'@
    },
    @{
        Name = 'READER'
        File = 'reader.dpapi'
        Login = 'v3_cas_audit_reader_actor'
        Sql = @'
SET ROLE v3_cas_audit_reader;
BEGIN TRANSACTION READ ONLY;
SELECT CASE WHEN
  session_user = 'v3_cas_audit_reader_actor'
  AND current_user = 'v3_cas_audit_reader'
  AND (SELECT count(*) FROM v3_cas_audit.epoch_v1) = 0
  AND (SELECT count(*) FROM v3_cas_audit.intent_v1) = 0
  AND NOT pg_catalog.has_function_privilege(current_user,
      'v3_cas_audit.append_intent_v1(text,uuid,text,text,text)','EXECUTE')
  AND NOT pg_catalog.has_table_privilege(current_user,
      'v3_cas_audit.intent_v1','INSERT')
  AND NOT pg_catalog.pg_has_role(session_user,
      'v3_cas_audit_writer','SET')
THEN 'PASS' ELSE 'HOLD' END;
COMMIT;
'@
    }
)
$passed = 0
foreach ($check in $checks) {
    $plain = $null
    try {
        $file = Join-Path $dir $check.File
        if (-not [IO.File]::Exists($file)) {
            throw 'V3_STAGE3_DPAPI_IDENTITY_MISSING'
        }
        $entropy = [Text.Encoding]::ASCII.GetBytes(
            "V3_CAS_AUDIT_ACTOR_$($check.Name)_V1")
        $plain = [Security.Cryptography.ProtectedData]::Unprotect(
            [IO.File]::ReadAllBytes($file), $entropy,
            [Security.Cryptography.DataProtectionScope]::CurrentUser)
        $secret = [Text.Encoding]::ASCII.GetString($plain)
        if ($secret -cnotmatch '^[a-f0-9]{64}$') {
            throw 'V3_STAGE3_LOCAL_PASSWORD_FORMAT_HOLD'
        }
        $env:PGPASSWORD = $secret
        # Scope precisely two static role names. Never pass user-supplied SQL.
        $conn = "host=$hostName port=5432 dbname=postgres user=$($check.Login).$project sslmode=require connect_timeout=10"
        $output = & $psql -X -w -qAt -v ON_ERROR_STOP=1 -d $conn -c $check.Sql 2>&1
        if ($LASTEXITCODE -eq 0 -and (($output | Out-String).Trim() -ceq 'PASS')) {
            Write-Output "$($check.Name)_READONLY_SCOPE_PASS"
            $passed++
        } else {
            Write-Output "$($check.Name)_READONLY_SCOPE_HOLD"
        }
    }
    catch {
        # No raw SQL error output or password serialization in chat or logs.
        Write-Output "$($check.Name)_READONLY_SCOPE_HOLD"
    }
    finally {
        Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
        Remove-Variable secret,output -ErrorAction SilentlyContinue
        if ($null -ne $plain) { [Array]::Clear($plain,0,$plain.Length) }
    }
}
if ($passed -eq 2) {
    Write-Output 'V3_STAGE3_TWO_ORIGINAL_READONLY_AUDIT_SESSIONS_PASS_NO_CAS'
} else {
    Write-Output 'V3_STAGE3_READONLY_AUDIT_HOLD'
    exit 1
}
