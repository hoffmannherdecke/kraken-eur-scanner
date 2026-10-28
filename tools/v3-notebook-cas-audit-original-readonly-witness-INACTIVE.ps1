# V3 Paper – original Issue #99: one-time Notebook-held, READ-ONLY Stage3 Cloud audit.
# SOURCE-ONLY. No scheduler, CAS RPC, Stage4 epoch opener, new credentials, or Paper switch.
# Reuses the TWO existing DPAPI CurrentUser identities enrolled and authenticated 27 Oct.
# Stage3 historical PREVIEW still uses sslmode=require (encrypted only).
# Decision-grade PrecommitCloudInventory and PostcommitDurableIntent both
# require verify-full CA + hostname. Historical Stage3 stays require.
# Authenticated transport does NOT independently authenticate copied JSON.
# A PASS is scoped to THIS query only, never a durable intent or release authorization.
[CmdletBinding()]
param([switch]$PrecommitCloudInventory,[switch]$PostcommitDurableIntent,[string]$CaFile='',
 [switch]$ExportSignedPrecommitCloudInventory,[string]$ReviewedNotebookCertificateSha256='',
 [switch]$PrecommitRestoreCustody,[string]$ReviewedOriginalFenceSha256='')
if(([int]$PrecommitCloudInventory.IsPresent+[int]$PostcommitDurableIntent.IsPresent+[int]$PrecommitRestoreCustody.IsPresent) -gt 1){throw 'V3_READER_MODE_CONFLICT'}
if($PrecommitRestoreCustody -and
   ($ExportSignedPrecommitCloudInventory -or
    $ReviewedNotebookCertificateSha256 -cnotmatch '^[a-f0-9]{64}$' -or
    $ReviewedOriginalFenceSha256 -cnotmatch '^[a-f0-9]{64}$')){
 throw 'V3_PRECOMMIT_CUSTODY_EXPLICIT_SIGNER_AND_FENCE_PINS_REQUIRED'
}
if(-not $PrecommitRestoreCustody -and $ReviewedOriginalFenceSha256){
 throw 'V3_RESTORE_CUSTODY_FENCE_OUTSIDE_MODE'
}
if($ExportSignedPrecommitCloudInventory -and (-not $PrecommitCloudInventory -or
 $ReviewedNotebookCertificateSha256 -cnotmatch '^[a-f0-9]{64}$')){
 throw 'V3_SIGNED_READER_PRECOMMIT_MODE_OR_PIN_INVALID'
}
if(-not $ExportSignedPrecommitCloudInventory -and -not $PrecommitRestoreCustody -and $ReviewedNotebookCertificateSha256){
 throw 'V3_SIGNED_READER_PIN_WITHOUT_EXPORT'
}
$decisionReaderMode=($PrecommitCloudInventory -or $PostcommitDurableIntent -or $PrecommitRestoreCustody)
if(-not $decisionReaderMode -and $CaFile){throw 'V3_READER_CA_FILE_DECISION_MODE_ONLY'}
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
# Reuse the existing originalhost PG17 verify-full strategy for the sole
# future decision-grade readbacks. CA file optional; use libpq system
# trust by default. A certificate failure MUST hold; never retry with require.
$postcommitTlsRoot='system'
if($decisionReaderMode -and -not [string]::IsNullOrWhiteSpace($CaFile)){
    $ca=Get-Item -LiteralPath $CaFile -Force -ErrorAction Stop
    if($ca.PSIsContainer -or $ca.Length -lt 100 -or $ca.Length -gt 65536 -or
       [bool]($ca.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
       [IO.Path]::GetExtension($ca.Name) -notin @('.crt','.cer','.pem')){
        throw 'V3_POSTCOMMIT_READER_CA_FILE_INVALID'
    }
    $postcommitTlsRoot=$ca.FullName
}
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
 'observed_at_utc',pg_catalog.replace(pg_catalog.to_char(pg_catalog.clock_timestamp()
   AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS.US'),' ','T') || 'Z',
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
# This separate existing Reader mode signs ONLY the CURRENT inability to
# invoke the specific V3 CAS, NOT historical NEVER or an old-writer release.
# It reuses the existing PG17 actor, verify-full and interactive CMS signer.
if($PrecommitRestoreCustody){
 $checks=@($checks|Where-Object {$_.Name -ceq 'READER'})
 if($checks.Count -ne 1){throw 'V3_RESTORE_CUSTODY_READER_AMBIGUOUS'}
 $checks[0].Sql=@'
SET ROLE v3_cas_audit_reader;
BEGIN TRANSACTION READ ONLY;
SELECT pg_catalog.jsonb_build_object(
 'kind','V3_NOTEBOOK_CURRENT_NO_CAS_CAPABILITY_CUSTODY_V1',
 'observed_at_utc',pg_catalog.replace(pg_catalog.to_char(
   pg_catalog.clock_timestamp() AT TIME ZONE 'UTC',
   'YYYY-MM-DD HH24:MI:SS.US'),' ','T') || 'Z',
 'actor',session_user,'role',current_user,
 'epochs',(SELECT count(*) FROM v3_cas_audit.epoch_v1),
 'intents',(SELECT count(*) FROM v3_cas_audit.intent_v1),
 'installed_cas_rpc_count',(SELECT count(*) FROM pg_catalog.pg_proc p
  JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
  WHERE n.nspname='public' AND p.proname='rotate_v2r4_to_v3_experimental_paper'),
 'executor_login',(SELECT rolcanlogin FROM pg_catalog.pg_roles
  WHERE rolname='v3_cas_executor_actor'),
 'operator_can_set_executor',pg_catalog.pg_has_role(
  'v3_cas_operator_login','v3_cas_executor_actor','SET'),
 'reader_writer_set_role',pg_catalog.pg_has_role(session_user,
  'v3_cas_audit_writer','SET'),
 'reader_can_append',pg_catalog.has_function_privilege(current_user,
  'v3_cas_audit.append_intent_v1(text,uuid,text,text,text)','EXECUTE'),
 'historical_cas_never_proven',false,
 'restore_authorized',false
)::text;
COMMIT;
'@
}
# Future Stage4 + separately committed Writer intent ONLY. Same enrolled
# Reader actor; this mode does NOT open Stage4, append, seal, invoke CAS or rearm.
if($PostcommitDurableIntent){
 $checks=@($checks|Where-Object {$_.Name -ceq 'READER'})
 if($checks.Count -ne 1){throw 'V3_READER_POSTCOMMIT_SCOPE_AMBIGUOUS'}
 $checks[0].Sql=@'
SET ROLE v3_cas_audit_reader;
BEGIN TRANSACTION READ ONLY;
SELECT pg_catalog.jsonb_build_object(
 'kind','V3_ORIGINAL_READER_DURABLE_PREINVOKE_INTENT_V1',
 'observed_at_utc',pg_catalog.replace(pg_catalog.to_char(pg_catalog.clock_timestamp() AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS.US'),' ','T') || 'Z',
 'actor',session_user,'role',current_user,
 'epoch_count',(SELECT count(*) FROM v3_cas_audit.epoch_v1),
 'intent_count',(SELECT count(*) FROM v3_cas_audit.intent_v1),
 'epoch_id',e.epoch_id,'intent_id',i.intent_id::text,
 'predecessor_series_id',e.predecessor_series_id,
 'expected_rpc',e.expected_rpc,'intent_rpc',i.requested_rpc,
 'source_sha256',e.source_sha256,'intent_source_sha256',i.source_sha256,
 'fence_sha256',e.original_fence_sha256,'intent_fence_sha256',i.fence_sha256,
 'caller_acl_sha256',e.approved_caller_acl_sha256,'request_sha256',i.request_sha256,
 'ordinal',i.ordinal,'next_ordinal',e.next_ordinal,
 'intent_state',i.state,'sealed',e.sealed,
 'opened_at_utc',pg_catalog.replace(pg_catalog.to_char(e.opened_at_utc AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS.US'),' ','T') || 'Z',
 'intent_created_at_utc',pg_catalog.replace(pg_catalog.to_char(i.created_at_utc AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS.US'),' ','T') || 'Z'
)::text
FROM v3_cas_audit.epoch_v1 e
JOIN v3_cas_audit.intent_v1 i ON i.epoch_id=e.epoch_id
WHERE (SELECT count(*) FROM v3_cas_audit.epoch_v1)=1
  AND (SELECT count(*) FROM v3_cas_audit.intent_v1)=1
  AND session_user='v3_cas_audit_reader_actor'
  AND current_user='v3_cas_audit_reader'
  AND NOT pg_catalog.pg_has_role(session_user,'v3_cas_audit_writer','SET')
  AND NOT pg_catalog.has_function_privilege(current_user,
    'v3_cas_audit.append_intent_v1(text,uuid,text,text,text)','EXECUTE');
COMMIT;
'@
}
# Preserve the original UTC JSON literals: ConvertFrom-Json can materialize
# ISO-8601 strings as DateTime, and formatting them loses the original 'Z'.
# Only allowlisted fields are parsed from the original JSON text.
function Read-V3ReaderUtcLiteral([string]$RawJson,[string]$Name) {
    if($Name -cnotin @('observed_at_utc','opened_at_utc','intent_created_at_utc')){
        throw 'V3_READER_UTC_FIELD_NOT_ALLOWLISTED'
    }
    $pattern='"'+[regex]::Escape($Name)+'"\s*:\s*"(?<utc>[^"\\]*)"'
    $hits=[regex]::Matches($RawJson,$pattern)
    if($hits.Count -ne 1){throw 'V3_READER_UTC_MISSING_OR_DUPLICATE'}
    $literal=[string]$hits[0].Groups['utc'].Value
    if($literal -cnotmatch '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$'){
        throw 'V3_READER_UTC_FORMAT_INVALID'
    }
    $time=[datetimeoffset]::MinValue
    $style=[Globalization.DateTimeStyles]::AssumeUniversal -bor
           [Globalization.DateTimeStyles]::AdjustToUniversal
    if(-not [datetimeoffset]::TryParseExact(
        $literal,"yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'",
        [Globalization.CultureInfo]::InvariantCulture,$style,[ref]$time) -or
        $time.Offset -ne [timespan]::Zero){
        throw 'V3_READER_UTC_DATE_INVALID'
    }
    return [pscustomobject]@{text=$literal;utc=$time}
}


# Signing is an explicit opt-in export of the already validated genuine Reader
# PG17 wire JSON, not a new SQL query, release token or CAS authorization.
# Existing Notebook CurrentUser certificate is pre-enrolled and SHA256-pinned
# by the independent reviewer; do not mint a key or expose DPAPI credentials.
function Save-V3SignedNotebookReaderSnapshot([string]$RawJson,[string]$CertSha256){
 if($env:GITHUB_ACTIONS -eq 'true' -or -not [Environment]::UserInteractive -or
    [Security.Principal.WindowsIdentity]::GetCurrent().Name -match '(?i)\\CryptoSupportSvc$'){
  throw 'V3_NOTEBOOK_READER_SIGNING_INTERACTIVE_ONLY'
 }
 if($RawJson.Length -lt 80 -or $RawJson.Length -gt 4096 -or
    $CertSha256 -cnotmatch '^[a-f0-9]{64}$'){
  throw 'V3_NOTEBOOK_READER_SIGNING_UNSAFE_INPUT'
 }
 $certs=@(Get-ChildItem Cert:\CurrentUser\My -ErrorAction Stop | Where-Object {
  $hash=[Security.Cryptography.SHA256]::Create()
  try { (([BitConverter]::ToString($hash.ComputeHash([byte[]]$_.RawData))).Replace('-','').ToLowerInvariant()) -ceq $CertSha256 }
  finally { $hash.Dispose() }
 })
 if($certs.Count -ne 1 -or -not $certs[0].HasPrivateKey -or
    $certs[0].NotBefore.ToUniversalTime() -gt [datetime]::UtcNow -or
    $certs[0].NotAfter.ToUniversalTime() -lt [datetime]::UtcNow){
  throw 'V3_NOTEBOOK_READER_EXISTING_SIGNER_NOT_AVAILABLE'
 }
 $actor=Get-Item -LiteralPath $dir -Force -ErrorAction Stop
 $drive=[IO.DriveInfo]::new([IO.Path]::GetPathRoot($dir))
 if(-not $actor.PSIsContainer -or
    [bool]($actor.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
    -not $drive.IsReady -or $drive.DriveType -ne [IO.DriveType]::Fixed -or
    $drive.DriveFormat -cne 'NTFS'){
  throw 'V3_NOTEBOOK_READER_ACTOR_VOLUME_UNSAFE'
 }
 $payload=[Text.UTF8Encoding]::new($false,$true).GetBytes($RawJson)
 $cms=[Security.Cryptography.Pkcs.SignedCms]::new(
  [Security.Cryptography.Pkcs.ContentInfo]::new([byte[]]$payload),$true)
 $signer=[Security.Cryptography.Pkcs.CmsSigner]::new($certs[0])
 $signer.DigestAlgorithm=[Security.Cryptography.Oid]::new('2.16.840.1.101.3.4.2.1')
 $cms.ComputeSignature($signer)
 $signature=[byte[]]$cms.Encode()
 if($signature.Length -gt 32768){throw 'V3_NOTEBOOK_READER_CMS_TOO_LARGE'}
 $folder=Join-Path $dir ('ReaderCMS-'+[guid]::NewGuid().ToString('N'))
 [void][IO.Directory]::CreateDirectory($folder)
 $acl=[Security.AccessControl.DirectorySecurity]::new()
 $acl.SetAccessRuleProtection($true,$false)
 $user=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
 foreach($sid in @($user,'S-1-5-18','S-1-5-32-544')){
  $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
   [Security.Principal.SecurityIdentifier]::new($sid),
   [Security.AccessControl.FileSystemRights]::FullControl,
   [Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
   [Security.AccessControl.InheritanceFlags]::ObjectInherit,
   [Security.AccessControl.PropagationFlags]::None,
   [Security.AccessControl.AccessControlType]::Allow))
 }
 Set-Acl -LiteralPath $folder -AclObject $acl -ErrorAction Stop
 foreach($name in @('reader.json','reader.cms')){
  $target=Join-Path $folder $name
  $data=if($name -ceq 'reader.json'){$payload}else{$signature}
  $file=[IO.FileStream]::new($target,[IO.FileMode]::CreateNew,
   [IO.FileAccess]::Write,[IO.FileShare]::None)
  try { $file.Write($data,0,$data.Length);$file.Flush($true) }
  finally { $file.Dispose() }
  $readback=[IO.File]::ReadAllBytes($target)
  if($readback.Length -ne $data.Length){throw 'V3_NOTEBOOK_READER_REREAD_FAILED'}
  for($i=0;$i -lt $data.Length;$i++){
   if($readback[$i] -ne $data[$i]){throw 'V3_NOTEBOOK_READER_REREAD_FAILED'}
  }
 }
 return [pscustomobject]@{
  kind='V3_NOTEBOOK_SIGNED_PRECOMMIT_READER_TRANSFER_V1'
  status='SIGNED_AUTHENTICATED_READER_SNAPSHOT_NOT_RUNTIME_RELEASE'
  local_directory=$folder;receipt='reader.json';signature='reader.cms'
  certificate_sha256=$CertSha256
  historical_cas_never_verified=$false
  old_intake_stop_or_restore_authorized=$false
  cas_dispatch_authorized=$false
 }
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
        if($decisionReaderMode){$env:PGSSLROOTCERT=$postcommitTlsRoot}
        $holdClass = 'POSTGRES_READONLY_QUERY_OR_CONNECTION'
        # Scope precisely two static role names. Never pass user-supplied SQL.
        $tlsMode=if($decisionReaderMode){'verify-full'}else{'require'}
        $conn = "host=$hostName port=5432 dbname=postgres user=$($check.Login).$project sslmode=$tlsMode connect_timeout=10"
        $output = & $psql -X -w -qAt -v ON_ERROR_STOP=1 -d $conn -c $check.Sql 2>&1
        if($PrecommitRestoreCustody){
            if($LASTEXITCODE -ne 0){throw 'V3_RESTORE_CUSTODY_SQL_HOLD'}
            $wire=($output|Out-String).Trim()
            $row=$wire|ConvertFrom-Json -ErrorAction Stop
            $at=Read-V3ReaderUtcLiteral -RawJson $wire -Name 'observed_at_utc'
            if([string]$row.kind -cne 'V3_NOTEBOOK_CURRENT_NO_CAS_CAPABILITY_CUSTODY_V1' -or
               [string]$row.actor -cne 'v3_cas_audit_reader_actor' -or
               [string]$row.role -cne 'v3_cas_audit_reader' -or
               [string]$row.epochs -cne '0' -or
               [string]$row.intents -cne '0' -or
               [string]$row.installed_cas_rpc_count -cne '0' -or
               $row.executor_login -ne $false -or
               $row.operator_can_set_executor -ne $false -or
               $row.reader_writer_set_role -ne $false -or
               $row.reader_can_append -ne $false -or
               $row.historical_cas_never_proven -ne $false -or
               $row.restore_authorized -ne $false -or
               ([datetimeoffset]::UtcNow-$at.utc).TotalSeconds -lt -5 -or
               ([datetimeoffset]::UtcNow-$at.utc).TotalSeconds -gt 60){
              throw 'V3_RESTORE_CUSTODY_CURRENT_DATABASE_NEGATIVE_GATE_HOLD'
            }
            # Caller-supplied fence SHA is bound in the CMS but not itself
            # independently observed by the Notebook; host must re-read.
            $row|Add-Member -NotePropertyName original_fence_sha256 -NotePropertyValue $ReviewedOriginalFenceSha256
            $signed=$row|ConvertTo-Json -Compress -Depth 3
            (Save-V3SignedNotebookReaderSnapshot -RawJson $signed -CertSha256 $ReviewedNotebookCertificateSha256)|ConvertTo-Json -Compress -Depth 3
            $passed++
        } elseif($PostcommitDurableIntent){
            if($LASTEXITCODE -ne 0){throw 'V3_DURABLE_INTENT_READER_SQL_HOLD'}
            $row=(($output|Out-String).Trim()|ConvertFrom-Json -ErrorAction Stop)
            $wireJson=($output|Out-String).Trim()
            $at=Read-V3ReaderUtcLiteral -RawJson $wireJson -Name 'observed_at_utc'
            $opened=Read-V3ReaderUtcLiteral -RawJson $wireJson -Name 'opened_at_utc'
            $created=Read-V3ReaderUtcLiteral -RawJson $wireJson -Name 'intent_created_at_utc'
            if($null -eq $row -or
                [string]$row.kind -cne 'V3_ORIGINAL_READER_DURABLE_PREINVOKE_INTENT_V1' -or
                [string]$row.actor -cne 'v3_cas_audit_reader_actor' -or
                [string]$row.role -cne 'v3_cas_audit_reader' -or
                [string]$row.epoch_count -cne '1' -or
                [string]$row.intent_count -cne '1' -or
                [string]$row.ordinal -cne '1' -or
                [string]$row.next_ordinal -cne '2' -or
                [string]$row.intent_state -cne 'PREINVOKE_INTENT' -or
                $row.sealed -ne $false -or
                [string]$row.predecessor_series_id -cne 'PAPER-V2R4-20261009T110135Z' -or
                [string]$row.expected_rpc -cne 'public.rotate_v2r4_to_v3_experimental_paper' -or
                [string]$row.intent_rpc -cne [string]$row.expected_rpc -or
                [string]$row.epoch_id -cnotmatch '^V3CAS-AUDIT-[a-f0-9]{32}$' -or
                [string]$row.intent_id -cnotmatch '^[a-f0-9-]{36}$' -or
                [string]$row.source_sha256 -cnotmatch '^[a-f0-9]{64}$' -or
                [string]$row.fence_sha256 -cnotmatch '^[a-f0-9]{64}$' -or
                [string]$row.caller_acl_sha256 -cnotmatch '^[a-f0-9]{64}$' -or
                [string]$row.request_sha256 -cnotmatch '^[a-f0-9]{64}$' -or
                [string]$row.intent_source_sha256 -cne [string]$row.source_sha256 -or
                [string]$row.intent_fence_sha256 -cne [string]$row.fence_sha256 -or
                $created.utc -lt $opened.utc -or $created.utc -gt $at.utc -or
                ($at.utc-$created.utc).TotalSeconds -gt 300 -or
                ([datetimeoffset]::UtcNow-$at.utc).TotalSeconds -gt 90 -or
                ([datetimeoffset]::UtcNow-$at.utc).TotalSeconds -lt -5){
                throw 'V3_DURABLE_INTENT_SINGLE_READER_HOLD'
            }
            [pscustomobject]@{
                kind='V3_ORIGINAL_READER_DURABLE_PREINVOKE_INTENT_V1'
                status='CURRENT_ONE_COMMITTED_PREINVOKE_INTENT_NOT_CAS_RELEASE'
                observed_at_utc=$at.text
                epoch_id=[string]$row.epoch_id
                intent_id=[string]$row.intent_id
                source_sha256=[string]$row.source_sha256
                fence_sha256=[string]$row.fence_sha256
                caller_acl_sha256=[string]$row.caller_acl_sha256
                request_sha256=[string]$row.request_sha256
                # The original authenticated PostgreSQL Reader projected only
                # the original public audit fields, never a password or token.
                # This claim alone is NOT an authenticated off-host receipt.
                # A separately reviewed Python adapter checks exact shape,
                # source/fence/request matches and reconstructs canonical
                # unsigned CMS bytes before an independent signer is used.
                original_reader_row_for_future_cms_proposal=[ordered]@{
                    kind=[string]$row.kind
                    observed_at_utc=$at.text
                    actor=[string]$row.actor
                    role=[string]$row.role
                    epoch_count=[int]$row.epoch_count
                    intent_count=[int]$row.intent_count
                    epoch_id=[string]$row.epoch_id
                    intent_id=[string]$row.intent_id
                    predecessor_series_id=[string]$row.predecessor_series_id
                    expected_rpc=[string]$row.expected_rpc
                    intent_rpc=[string]$row.intent_rpc
                    source_sha256=[string]$row.source_sha256
                    intent_source_sha256=[string]$row.intent_source_sha256
                    fence_sha256=[string]$row.fence_sha256
                    intent_fence_sha256=[string]$row.intent_fence_sha256
                    caller_acl_sha256=[string]$row.caller_acl_sha256
                    request_sha256=[string]$row.request_sha256
                    ordinal=[int]$row.ordinal
                    next_ordinal=[int]$row.next_ordinal
                    intent_state=[string]$row.intent_state
                    sealed=[bool]$row.sealed
                    opened_at_utc=$opened.text
                    intent_created_at_utc=$created.text
                }
                independent_tls_certificate_verified=$false
                historical_cas_never_proven=$false
                complete_cas_attempt_custody_proven=$false
                originalhost_authenticated_here=$false
                cloud_cas_authorized=$false
                precommit_restore_authorized=$false
                v3_paper_release_authorized=$false
            }|ConvertTo-Json -Compress -Depth 4
            $passed++
        } elseif($PrecommitCloudInventory){
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
            $holdClass = 'CURRENT_UTC_FORMAT'
            $at=Read-V3ReaderUtcLiteral -RawJson (($output|Out-String).Trim()) -Name 'observed_at_utc'
            $holdClass = 'CURRENT_UTC_FRESHNESS'
            if(([datetimeoffset]::UtcNow-$at.utc).TotalSeconds -gt 90 -or
                ([datetimeoffset]::UtcNow-$at.utc).TotalSeconds -lt -5){
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
                observed_at_utc=$at.text
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
            if($ExportSignedPrecommitCloudInventory){
              Save-V3SignedNotebookReaderSnapshot -RawJson (($output|Out-String).Trim()) -CertSha256 $ReviewedNotebookCertificateSha256 |
               ConvertTo-Json -Compress -Depth 3
            }
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
        if($decisionReaderMode){Remove-Item Env:\PGSSLROOTCERT -ErrorAction SilentlyContinue}
        Remove-Variable secret,output -ErrorAction SilentlyContinue
        if ($null -ne $plain) { [Array]::Clear($plain,0,$plain.Length) }
    }
}
if($PrecommitCloudInventory -or $PostcommitDurableIntent){
 if($passed -ne 1){exit 1}
 return
}
if ($passed -eq 2) {
    Write-Output 'V3_STAGE3_TWO_ORIGINAL_READONLY_AUDIT_SESSIONS_PASS_NO_CAS'
} else {
    Write-Output 'V3_STAGE3_READONLY_AUDIT_HOLD'
    exit 1
}
