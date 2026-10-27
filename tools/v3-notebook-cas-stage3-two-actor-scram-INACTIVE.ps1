# V3 Paper Issue #99 / ONE-TIME NOTEBOOK-only audit ACTOR enrollment PREPARATION.
# No cloud connection, scheduled task, CAS, Paper activation or browser automation.
# Windows single-user account is the accepted local custody baseline.
# Default invocation is PREVIEW: only explicit -Stage creates local DPAPI files.
[CmdletBinding()]
param(
 [switch]$Stage,
 [switch]$RemoveEnrollmentSql,
 [string]$TemplatePath = ''
)
$ErrorActionPreference = 'Stop'
$kind = 'V3_CAS_NOTEBOOK_TWO_AUDIT_ACTORS_LOCAL_SCRAM_V1'
$root = Join-Path $env:LOCALAPPDATA 'V3CasAuditActors'
$sqlPath = Join-Path $root 'v3-cas-audit-actor-enroll-ONE-TIME.sql'
if ($Stage -and $RemoveEnrollmentSql) { throw 'V3_STAGE3_HOLD_CONFLICTING_ACTIONS' }
if (-not $Stage -and -not $RemoveEnrollmentSql) {
 [pscustomobject]@{
  kind=$kind; state='INACTIVE_PREVIEW'; network_used=$false
  cloud_mutation=$false; audit_epoch_created=$false; cas_invoked=$false
  next_action='Review source, then run explicit -Stage with locally downloaded approved SQL template.'
 } | ConvertTo-Json -Compress
 return
}
if (-not [Environment]::OSVersion.Platform.ToString().StartsWith('Win') -and $env:OS -ne 'Windows_NT') {
 throw 'V3_STAGE3_HOLD_WINDOWS_NOTEBOOK_ONLY'
}
if ($RemoveEnrollmentSql) {
 if ([IO.File]::Exists($sqlPath)) { [IO.File]::Delete($sqlPath) }
 [pscustomobject]@{
  kind=$kind; state='ONE_TIME_SQL_SCRUBBED'
  login_credentials_retained_sealed_with_windows_user=$true
  network_used=$false; cloud_mutation=$false
 } | ConvertTo-Json -Compress
 return
}
if ([string]::IsNullOrWhiteSpace($TemplatePath) -or
    -not [IO.File]::Exists($TemplatePath)) { throw 'V3_STAGE3_HOLD_EXACT_TEMPLATE_REQUIRED' }
if ([IO.Directory]::Exists($root) -and
    ([IO.File]::Exists($sqlPath) -or
     [IO.File]::Exists((Join-Path $root 'writer.dpapi')) -or
     [IO.File]::Exists((Join-Path $root 'reader.dpapi')))) {
 throw 'V3_STAGE3_HOLD_EXISTING_LOCAL_IDENTITY_NO_OVERWRITE'
}
$sourceSql = [IO.File]::ReadAllText($TemplatePath,[Text.Encoding]::UTF8)
$lock = "  RAISE EXCEPTION 'V3_STAGE3_LOCAL_ENROLLMENT_TEMPLATE_INACTIVE';"
$writerMark = '__WRITER_SCRAM_SHA256_VERIFIER__'
$readerMark = '__READER_SCRAM_SHA256_VERIFIER__'
if ($sourceSql.Split([string[]]@($lock),[StringSplitOptions]::None).Count -ne 2 -or
    $sourceSql.Split([string[]]@($writerMark),[StringSplitOptions]::None).Count -ne 2 -or
    $sourceSql.Split([string[]]@($readerMark),[StringSplitOptions]::None).Count -ne 2 -or
    $sourceSql -cnotmatch '^-- V3 Paper / original Issue #99: ONE-TIME LOCAL ENROLLMENT TEMPLATE, INACTIVE\.' -or
    $sourceSql -cnotmatch 'DO \$v3_cas_stage3_audit_actors\$' -or
    $sourceSql -cnotmatch '\$v3_cas_stage3_audit_actors\$;\s*$' -or
    $sourceSql -cnotmatch 'GRANT v3_cas_audit_reader TO v3_cas_audit_reader_actor' -or
    $sourceSql -cnotmatch 'GRANT v3_cas_audit_writer TO v3_cas_audit_writer_actor') {
 throw 'V3_STAGE3_HOLD_UNEXPECTED_ENROLLMENT_TEMPLATE'
}
# Password is 256 bits from Windows CSPRNG. Only a DPAPI CurrentUser copy
# is saved; SQL contains salted SCRAM verifier, never plaintext password.
function New-SealedScram([string]$label,[string]$file) {
 $bytes = New-Object byte[] 32
 $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
 try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
 $secret = [BitConverter]::ToString($bytes).Replace('-','').ToLowerInvariant()
 [Array]::Clear($bytes,0,$bytes.Length)
 $raw = [Text.Encoding]::ASCII.GetBytes($secret)
 $entropy = [Text.Encoding]::ASCII.GetBytes('V3_CAS_AUDIT_ACTOR_'+$label+'_V1')
 try {
  $sealed = [Security.Cryptography.ProtectedData]::Protect(
    $raw,$entropy,[Security.Cryptography.DataProtectionScope]::CurrentUser)
 } finally { [Array]::Clear($raw,0,$raw.Length) }
 [IO.File]::WriteAllBytes($file,$sealed)
 $salt = New-Object byte[] 16
 $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
 try { $rng.GetBytes($salt) } finally { $rng.Dispose() }
 $pbkdf = [Security.Cryptography.Rfc2898DeriveBytes]::new(
   $secret,$salt,4096,[Security.Cryptography.HashAlgorithmName]::SHA256)
 try { $salted = $pbkdf.GetBytes(32) } finally { $pbkdf.Dispose() }
 $hmac = [Security.Cryptography.HMACSHA256]::new($salted)
 try {
  $client = $hmac.ComputeHash([Text.Encoding]::ASCII.GetBytes('Client Key'))
  $server = $hmac.ComputeHash([Text.Encoding]::ASCII.GetBytes('Server Key'))
 } finally { $hmac.Dispose(); [Array]::Clear($salted,0,$salted.Length) }
 $sha = [Security.Cryptography.SHA256]::Create()
 try { $stored = $sha.ComputeHash($client) } finally { $sha.Dispose() }
 [Array]::Clear($client,0,$client.Length)
 $verifier = 'SCRAM-SHA-256$4096:' +
  [Convert]::ToBase64String($salt) + '$' +
  [Convert]::ToBase64String($stored) + ':' +
  [Convert]::ToBase64String($server)
 [Array]::Clear($salt,0,$salt.Length)
 [Array]::Clear($stored,0,$stored.Length)
 [Array]::Clear($server,0,$server.Length)
 return $verifier
}
[IO.Directory]::CreateDirectory($root) | Out-Null
$w = New-SealedScram 'WRITER' (Join-Path $root 'writer.dpapi')
$r = New-SealedScram 'READER' (Join-Path $root 'reader.dpapi')
if ($w -ceq $r) { throw 'V3_STAGE3_HOLD_DUPLICATE_VERIFIERS' }
$approved = $sourceSql.Replace($lock,'  -- Locally authorized explicit one-time actor enrollment after source review.')
$approved = $approved.Replace($writerMark,$w).Replace($readerMark,$r)
if ($approved.Contains($lock) -or $approved.Contains($writerMark) -or
    $approved.Contains($readerMark)) { throw 'V3_STAGE3_HOLD_TEMPLATE_SUBSTITUTION' }
[IO.File]::WriteAllText($sqlPath,$approved,[Text.UTF8Encoding]::new($false))
[pscustomobject]@{
 kind=$kind; state='LOCAL_TWO_DPAPI_SECRETS_AND_ONE_TIME_SQL_STAGED'
 sql_file_local_to_windows_user=$sqlPath
 distinct_credentials=$true
 plaintext_password_displayed=$false
 script_outputs_any_verifier=$false
 original_executor_shell_untouched=$true
 network_used=$false; cloud_mutation=$false; cas_invoked=$false
 next_action='Later manual SQL Editor execution only after scope approval; never paste SQL or verifiers into chat/GitHub. Remove local SQL after verified enrollment.'
} | ConvertTo-Json -Compress
