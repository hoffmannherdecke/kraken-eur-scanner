# V3 Paper – original Issue #99: one-time Notebook-held, READ-ONLY Stage3 Cloud audit.
# SOURCE-ONLY. No scheduler, CAS RPC, Stage4 epoch opener, new credentials, or Paper switch.
# Reuses the TWO existing DPAPI CurrentUser identities enrolled and authenticated 27 Oct.
# Session-pooler TLS sslmode=require encrypts transport, but does NOT check the server CA.
# A PASS is scoped to THIS query only, never a durable intent or release authorization.
[CmdletBinding()]
param([switch]$PrecommitCloudInventory)
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
# Optional read-only ORIGINAL Reader identity, not a CAS historical never-proof.
if($PrecommitCloudInventory){
 $checks=@($checks|Where-Object {$_.Name -ceq 'READER'})
 if($checks.Count -ne 1){throw 'V3_PRECOMMIT_READER_AMBIGUOUS'}
 $checks[0].Sql=@'
SET ROLE v3_cas_audit_reader;
BEGIN TRANSACTION READ ONLY;
SELECT pg_catalog.jsonb_build_object(
 'kind','V3_CAS_READER_CURRENT_PRIVATE_AUDIT_SNAPSHOT_V1',
 'observed_at_utc',pg_catalog.to_char(pg_catalog.clock_timestamp()
   AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
 'actor',session_user,'role',current_user,
 'epochs',(SELECT count(*) FROM v3_cas_audit.epoch_v1),
 'intents',(SELECT count(*) FROM v3_cas_audit.intent_v1),
 'writer_role_access',pg_catalog.pg_has_role(session_user,'v3_cas_audit_writer','SET'),
 'append_access',pg_catalog.has_function_privilege(
   current_user,'v3_cas_audit.append_intent_v1(text,uuid,text,text,text)','EXECUTE'),
 'history_never_proven',false,
 'restore_authorized',false
)::text;
COMMIT;
'@
}
$passed = 0
foreach ($check in $checks) {
    $plain = $null
    # Fixed sanitized reason class, only emitted for the optional Reader inventory.
    # Never emit credentials, raw database errors, process output or paths.
    $holdClass = 'LOCAL_READER_IDENTITY_OR_DPAPI'
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
        $holdClass = 'POSTGRES_READONLY_QUERY_OR_CONNECTION'
        # Scope precisely two static role names. Never pass user-supplied SQL.
        $conn = "host=$hostName port=5432 dbname=postgres user=$($check.Login).$project sslmode=require connect_timeout=10"
        $output = & $psql -X -w -qAt -v ON_ERROR_STOP=1 -d $conn -c $check.Sql 2>&1
        if($PrecommitCloudInventory){
            if($LASTEXITCODE -ne 0){throw 'V3_PRECOMMIT_READER_SQL_HOLD'}
            $holdClass = 'CURRENT_JSON_DECODE'
            $row=(($output|Out-String).Trim()|ConvertFrom-Json -ErrorAction Stop)
            $holdClass = 'CURRENT_IDENTITY_OR_SCHEMA'
            if($null -eq $row -or
                [string]$row.kind -cne 'V3_CAS_READER_CURRENT_PRIVATE_AUDIT_SNAPSHOT_V1' -or
                [string]$row.actor -cne 'v3_cas_audit_reader_actor' -or
                [string]$row.role -cne 'v3_cas_audit_reader'){
                throw 'V3_PRECOMMIT_READER_NONEMPTY_OR_UNVERIFIED_HOLD'
            }
            $holdClass = 'CURRENT_UTC_FRESHNESS'
            $at=[datetimeoffset]::MinValue
            if([string]$row.observed_at_utc -cnotmatch 'Z$' -or
                -not [datetimeoffset]::TryParse([string]$row.observed_at_utc,[ref]$at) -or
                ([datetimeoffset]::UtcNow-$at).TotalSeconds -gt 90 -or
                ([datetimeoffset]::UtcNow-$at).TotalSeconds -lt -5){
                throw 'V3_PRECOMMIT_READER_NONEMPTY_OR_UNVERIFIED_HOLD'
            }
            $holdClass = 'CURRENT_AUDIT_LEDGER_COUNTS'
            if([string]$row.epochs -cne '0' -or
                [string]$row.intents -cne '0'){
                throw 'V3_PRECOMMIT_READER_NONEMPTY_OR_UNVERIFIED_HOLD'
            }
            $holdClass = 'CURRENT_READER_ROLE_ISOLATION'
            if($row.writer_role_access -ne $false -or
                $row.append_access -ne $false){
                throw 'V3_PRECOMMIT_READER_NONEMPTY_OR_UNVERIFIED_HOLD'
            }
            $holdClass = 'CURRENT_NEGATIVE_AUTHORITY_FLAGS'
            if($row.history_never_proven -ne $false -or
                $row.restore_authorized -ne $false){
                throw 'V3_PRECOMMIT_READER_NONEMPTY_OR_UNVERIFIED_HOLD'
            }
            [pscustomobject]@{
                kind='V3_CAS_READER_CURRENT_PRIVATE_AUDIT_SNAPSHOT_V1'
                status='AUTHENTICATED_READER_CURRENT_EMPTY_NOT_HISTORICAL_NEVER'
                observed_at_utc=[string]$row.observed_at_utc
                epoch_count=0
                intent_count=0
                actor='v3_cas_audit_reader_actor'
                role='v3_cas_audit_reader'
                independent_tls_certificate_verified=$false
                independent_attempt_history_complete=$false
                historical_cas_never_proven=$false
                public_old_only_series_verified_here=$false
                native_rearm_authorized=$false
                precommit_restore_authorized=$false
                cloud_cas_authorized=$false
                v3_paper_release_authorized=$false
            }|ConvertTo-Json -Compress
            $passed++
        } elseif ($LASTEXITCODE -eq 0 -and (($output | Out-String).Trim() -ceq 'PASS')) {
            Write-Output "$($check.Name)_READONLY_SCOPE_PASS"
            $passed++
        } else {
            Write-Output "$($check.Name)_READONLY_SCOPE_HOLD"
        }
    }
    catch {
        # Report only fixed coarse categories. No raw SQL/stdout/stderr,
        # exception text, username, DPAPI material or other sensitive values.
        Write-Output "$($check.Name)_READONLY_SCOPE_HOLD"
        if($PrecommitCloudInventory){
            Write-Output "READER_PRECOMMIT_HOLD_CLASS=$holdClass"
        }
    }
    finally {
        Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
        Remove-Variable secret,output -ErrorAction SilentlyContinue
        if ($null -ne $plain) { [Array]::Clear($plain,0,$plain.Length) }
    }
}
if($PrecommitCloudInventory){
 if($passed -ne 1){exit 1}
 return
}
if ($passed -eq 2) {
    Write-Output 'V3_STAGE3_TWO_ORIGINAL_READONLY_AUDIT_SESSIONS_PASS_NO_CAS'
} else {
    Write-Output 'V3_STAGE3_READONLY_AUDIT_HOLD'
    exit 1
}
