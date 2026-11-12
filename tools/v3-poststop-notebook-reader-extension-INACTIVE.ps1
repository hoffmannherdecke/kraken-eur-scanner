# PR710 source-only POSTSTOP extension; original staged Reader bytes immutable.
[CmdletBinding()]
param([switch]$PostStopHostReader,[switch]$PostStopCloudReader,[switch]$PostStopTerminalReader,
 [Parameter(Mandatory=$true)][string]$ObservationNonce,
 [Parameter(Mandatory=$true)][string]$ReviewedNotebookCertificateSha256,
 [string]$OriginalHostDirectory='',[string]$CaFile='')
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if(([int]$PostStopHostReader.IsPresent+[int]$PostStopCloudReader.IsPresent+[int]$PostStopTerminalReader.IsPresent) -ne 1){throw 'PR710_READER_MODE_HOLD'}
$pin=if($PostStopHostReader){'2e3322131208737c58a82c04764bddf4ebe29481c96c79697183710358a2fc57'}else{'61d08dd9a925730f213fedc559664dbfe2a3e4f8f1ae77496b385f7d92f3bc55'}
if($ObservationNonce -cnotmatch '^[a-f0-9]{32}$' -or $ReviewedNotebookCertificateSha256 -cne $pin){throw 'PR710_READER_PIN_HOLD'}
if($PostStopHostReader -and (-not $OriginalHostDirectory -or $CaFile)){throw 'PR710_HOST_INPUT_HOLD'}
if($PostStopCloudReader -and $OriginalHostDirectory){throw 'PR710_CLOUD_INPUT_HOLD'}
if($env:OS -cne 'Windows_NT'){throw 'PR710_READER_WINDOWS_ONLY'}
Add-Type -AssemblyName System.Security -ErrorAction Stop
$dir=Join-Path $env:LOCALAPPDATA 'V3CasAuditActors'
$psql='C:\Program Files\PostgreSQL\17\bin\psql.exe'
$hostName='aws-1-eu-west-1.pooler.supabase.com'
$project='nlgzjmqgwueojlyqmoru'

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


# PR710: exact byte-bound, read-only POSTSTOP Reader extension.
function Assert-V3PostStopFreshReader([string]$Json,[string]$Nonce,[string]$Kind){
 $v=$Json|ConvertFrom-Json -ErrorAction Stop
 if([string]$v.kind -cne $Kind -or [string]$v.observation_nonce -cne $Nonce){
  throw 'V3_POSTSTOP_READER_NONCE_KIND_HOLD'
 }
 $m=[regex]::Matches($Json,'"observed_at_utc"\s*:\s*"(?<t>[^"]+)"')
 if($m.Count -ne 1){throw 'V3_POSTSTOP_READER_TIME_COUNT_HOLD'}
 $t=[datetimeoffset]::ParseExact($m[0].Groups['t'].Value,
   "yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'",
   [Globalization.CultureInfo]::InvariantCulture,
   [Globalization.DateTimeStyles]::AssumeUniversal)
 $now=[datetimeoffset]::UtcNow
 if($t -gt $now.AddSeconds(5) -or ($now-$t).TotalSeconds -gt 60){
  throw 'V3_POSTSTOP_READER_FRESHNESS_HOLD'
 }
 return $v
}
if($PostStopHostReader){
 $prefix='\\192.168.178.179\Mistral_450\'
 $folder=[IO.Path]::GetFullPath($OriginalHostDirectory)
 if(-not $folder.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase) -or
    $OriginalHostDirectory.Contains('..')){throw 'V3_POSTSTOP_HOST_UNC_HOLD'}
 $jsonPath=Join-Path $folder 'current-host-original.json'
 $cmsPath=Join-Path $folder 'current-host-original.cms'
 foreach($filePath in @($jsonPath,$cmsPath)){
  $fi=Get-Item -LiteralPath $filePath -Force -ErrorAction Stop
  if($fi.PSIsContainer -or [bool]($fi.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
     $fi.Length -lt 300 -or $fi.Length -gt 32768){
   throw 'V3_POSTSTOP_HOST_ORIGINAL_FILE_HOLD'
  }
 }
 $bytes=[IO.File]::ReadAllBytes($jsonPath)
 $raw=[Text.UTF8Encoding]::new($false,$true).GetString($bytes)
 $hostReceipt=Assert-V3PostStopFreshReader $raw $ObservationNonce 'V3_POSTSTOP_CURRENT_INDEPENDENT_HOST_READER_V1'
 if([string]$hostReceipt.series_id -cne 'PAPER-V3-20261111T105211Z' -or
    [string]$hostReceipt.epoch_id -cne 'V3CAS-AUDIT-f27cce0ba68043b480e4f97698dd2901' -or
    [string]$hostReceipt.source_sha256 -cne '8b27c2392c2c8165660a40e15f5ab896c99da39befcd2201e43220acaa2e1251' -or
    [string]$hostReceipt.original_fence_sha256 -cne '4f01704d20375bf201f87c56eb350a67c1a91f82535296b28ae318768aa213ef' -or
    [string]$hostReceipt.native_stop_outcome -cne 'UNKNOWN' -or
    $hostReceipt.writer_enabled -ne $false -or $hostReceipt.writer_process_count -ne 0 -or
    $hostReceipt.other_writer_authorities_closed -ne $true -or
    $hostReceipt.current_host_custody_verified -ne $true){
  throw 'V3_POSTSTOP_HOST_SCOPE_HOLD'
 }
 $cms=[Security.Cryptography.Pkcs.SignedCms]::new(
    [Security.Cryptography.Pkcs.ContentInfo]::new($bytes),$true)
 $cms.Decode([IO.File]::ReadAllBytes($cmsPath))
 if(-not $cms.Detached -or $cms.SignerInfos.Count -ne 1){
  throw 'V3_POSTSTOP_HOST_ORIGIN_CMS_HOLD'
 }
 $cms.CheckSignature($true)
 $cert=$cms.SignerInfos[0].Certificate
 if($null -eq $cert){throw 'V3_POSTSTOP_HOST_ORIGIN_CERT_HOLD'}
 $h=[Security.Cryptography.SHA256]::Create()
 try{$pin=([BitConverter]::ToString($h.ComputeHash([byte[]]$cert.RawData))).Replace('-','').ToLowerInvariant()}
 finally{$h.Dispose()}
 if($pin -cne 'ce256281af6d36eb883dd2cb34594d0f2231e32a33f58e668d327814c7cfdb40'){
  throw 'V3_POSTSTOP_HOST_ORIGIN_PIN_HOLD'
 }
 $reader=Save-V3SignedNotebookReaderSnapshot $raw $ReviewedNotebookCertificateSha256
 $copy=[IO.File]::ReadAllBytes((Join-Path $reader.local_directory 'reader.json'))
 if($copy.Length -ne $bytes.Length){throw 'V3_POSTSTOP_HOST_BYTE_HOLD'}
 for($i=0;$i -lt $bytes.Length;$i++){
  if($copy[$i] -ne $bytes[$i]){throw 'V3_POSTSTOP_HOST_BYTE_HOLD'}
 }
 [pscustomobject]@{kind='V3_POSTSTOP_NOTEBOOK_HOST_CMS_V1';
  status='READ_ONLY_NO_RECOVERY';observation_nonce=$ObservationNonce
  originalhost_directory=$folder;notebook_directory=$reader.local_directory
  originalhost_json='current-host-original.json';originalhost_cms='current-host-original.cms'
  notebook_json='reader.json';notebook_cms='reader.cms'
  no_production_effect=$true}|ConvertTo-Json -Compress
 return
}

if(-not ($PostStopCloudReader -or $PostStopTerminalReader)){throw 'PR710_UNKNOWN_MODE_HOLD'}
if(-not [IO.File]::Exists($psql)){throw 'PR710_PG17_REQUIRED'}
$checks=@(@{Name='READER';File='reader.dpapi';Login='v3_cas_audit_reader_actor';Sql=''})

# PR710: One atomic read-only SQL statement through the existing PG17 TLS Reader.
# State is derived from original Catalog and the existing independently
# scoped Paper release epoch Reader (including all historical abort bindings).
if($PostStopCloudReader -or $PostStopTerminalReader){
 $checks=@($checks|Where-Object {$_.Name -ceq 'READER'})
 if($checks.Count -ne 1){throw 'V3_POSTSTOP_CLOUD_ROLE_HOLD'}
 $checks[0].Sql=@'
SET ROLE v3_cas_audit_reader;
BEGIN TRANSACTION READ ONLY;
-- Existing admitted per-epoch SECURITY DEFINER reader checks all foreign
-- epochs against their exact ABORT_RECORDED_NOT_RELEASED source/fence/ACL.
-- It also verifies the installed RPC ACL, inhibited issuer, zero intents,
-- zero attempts and executor NOLOGIN. No new function or privilege is added.
WITH catalog AS MATERIALIZED (
 SELECT v3_cas_audit.read_forward_t0_current_v1() AS c
), scoped AS MATERIALIZED (
 SELECT v3_cas_audit.read_paper_release_epoch_v1(
  'V3CAS-AUDIT-f27cce0ba68043b480e4f97698dd2901') AS p
), epoch AS MATERIALIZED (
 SELECT epoch_id,source_sha256,original_fence_sha256,approved_caller_acl_sha256,sealed,next_ordinal
 FROM v3_cas_audit.epoch_v1
 WHERE epoch_id='V3CAS-AUDIT-f27cce0ba68043b480e4f97698dd2901'
)
SELECT pg_catalog.jsonb_build_object(
 'kind','V3_POSTSTOP_CURRENT_INDEPENDENT_CLOUD_READER_V1',
 'series_id','PAPER-V3-20261111T105211Z',
 'epoch_id',e.epoch_id,'source_sha256',e.source_sha256,
 'observation_nonce','__NONCE__',
 'observed_at_utc',pg_catalog.replace(pg_catalog.to_char(pg_catalog.clock_timestamp() AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS.US'),' ','T') || 'Z',
 'original_fence_sha256',e.original_fence_sha256,
 'caller_acl_sha256',e.approved_caller_acl_sha256,
 'inhibit_state','INHIBITED','sealed',e.sealed,
 'next_ordinal',e.next_ordinal,
 'intent_count',(c->>'intent_count')::integer,
 'attempt_count',(c->>'attempt_count')::integer,
 'abort_count',(SELECT count(*) FROM v3_cas_audit.prepared_fence_abort_v1 a WHERE a.epoch_id=e.epoch_id),
 'executor_login_closed',true,'executor_sessions_count',0,
 'v3_active_series_count',0,
 'v2r4_active_series_count',(c->>'original_active_series_count')::integer,
 'cloud_cas_rpc_count',(c->>'cas_rpc_count')::integer,
 'reader_role',current_user,'current_cloud_custody_verified',true
)::text FROM epoch e CROSS JOIN catalog CROSS JOIN scoped
WHERE session_user='v3_cas_audit_reader_actor'
 AND current_user='v3_cas_audit_reader'
 AND p->>'kind'='V3_PAPER_RELEASE_EPOCH_READER_V1'
 AND p->>'state'='PRESTOP_INHIBITED_OLD_ONLY_NO_ATTEMPTS'
 AND p->>'epoch_id'=e.epoch_id
 AND p->>'source_sha256'=e.source_sha256
 AND p->>'fence_sha256'=e.original_fence_sha256
 AND p->>'caller_acl_sha256'=e.approved_caller_acl_sha256
 AND (c->>'active_series_count')::integer=1
 AND (c->>'original_active_series_count')::integer=1
 AND (c->>'epoch_count')::integer>0
 AND (c->>'intent_count')::integer=0
 AND (c->>'attempt_count')::integer=0
 AND (c->>'dispatch_unknown_count')::integer=0
 AND (c->>'cas_rpc_count')::integer=1
 AND e.source_sha256='8b27c2392c2c8165660a40e15f5ab896c99da39befcd2201e43220acaa2e1251'
 AND e.original_fence_sha256='4f01704d20375bf201f87c56eb350a67c1a91f82535296b28ae318768aa213ef'
 AND e.approved_caller_acl_sha256='6f0d59c57f3f7ce3d54f5c674c0d41c342a2a08b9a86001e59353d772f5f66f0'
 AND NOT e.sealed AND e.next_ordinal=1
 AND NOT EXISTS (SELECT 1 FROM v3_cas_audit.prepared_fence_abort_v1 a WHERE a.epoch_id=e.epoch_id)
 AND (SELECT count(*) FROM pg_catalog.pg_roles WHERE rolname IN ('v3_cas_executor','v3_cas_executor_actor','v3_cas_audit_writer_actor') AND NOT rolcanlogin)=3
 AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_stat_activity WHERE usename IN ('v3_cas_executor','v3_cas_executor_actor','v3_cas_audit_writer_actor'))
 AND NOT pg_catalog.pg_has_role(session_user,'v3_cas_audit_writer','SET');
COMMIT;
'@
 $checks[0].Sql=$checks[0].Sql.Replace('__NONCE__',$ObservationNonce)

 if($PostStopTerminalReader){
  # Dedicated post-abort contract: six bound historical epochs, exact target
  # aborted once; the existing CAS RPC remains ACL-isolated and never called.
  $checks[0].Sql=@'
SET ROLE v3_cas_audit_reader;
BEGIN TRANSACTION READ ONLY;
WITH c AS MATERIALIZED (SELECT v3_cas_audit.read_forward_t0_current_v1() AS j),
 e AS MATERIALIZED (
 SELECT epoch_id,source_sha256,original_fence_sha256,approved_caller_acl_sha256
 FROM v3_cas_audit.epoch_v1
 WHERE epoch_id='V3CAS-AUDIT-f27cce0ba68043b480e4f97698dd2901'
 ), target AS MATERIALIZED (
 SELECT a.* FROM v3_cas_audit.prepared_fence_abort_v1 a
 WHERE a.epoch_id='V3CAS-AUDIT-f27cce0ba68043b480e4f97698dd2901'
 )
SELECT pg_catalog.jsonb_build_object(
 'kind','V3_CAS_PREPARED_FENCE_ABORT_READER_RECEIPT_V1',
 'observation_nonce','__NONCE__',
 'observed_at_utc',pg_catalog.replace(pg_catalog.to_char(
 pg_catalog.clock_timestamp() AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS.US'),' ','T') || 'Z',
 'cloud_observed_at_utc',(c.j->>'observed_at_utc'),
 'epoch_id',e.epoch_id,'source_sha256',a.source_sha256,
 'prepared_fence_sha256',a.prepared_fence_sha256,
 'caller_acl_sha256',a.caller_acl_sha256,
 'issuer_actor',a.issuer_actor,'receipt_sha256',a.receipt_sha256,
 'state',a.state,'cloud_active_series_count',(c.j->>'active_series_count')::integer,
 'cloud_original_active_series_count',(c.j->>'original_active_series_count')::integer,
 'cloud_cas_rpc_count',(c.j->>'cas_rpc_count')::integer,
 'cloud_cas_rpc_acl_restricted',true,
 'cloud_executor_can_login',false
)::text
FROM c CROSS JOIN e CROSS JOIN target a
WHERE session_user='v3_cas_audit_reader_actor'
 AND current_user='v3_cas_audit_reader'
 AND a.epoch_id=e.epoch_id AND a.source_sha256=e.source_sha256
 AND a.prepared_fence_sha256=e.original_fence_sha256
 AND a.caller_acl_sha256=e.approved_caller_acl_sha256
 AND a.issuer_actor='v3_cas_inhibit_issuer_actor'
 AND a.state='ABORT_RECORDED_NOT_RELEASED'
 AND e.source_sha256='8b27c2392c2c8165660a40e15f5ab896c99da39befcd2201e43220acaa2e1251'
 AND e.original_fence_sha256='4f01704d20375bf201f87c56eb350a67c1a91f82535296b28ae318768aa213ef'
 AND e.approved_caller_acl_sha256='6f0d59c57f3f7ce3d54f5c674c0d41c342a2a08b9a86001e59353d772f5f66f0'
 AND (SELECT count(*) FROM v3_cas_audit.epoch_v1)=6
 AND (SELECT count(*) FROM v3_cas_audit.prepared_fence_abort_v1)=6
 AND NOT EXISTS (
  SELECT 1 FROM v3_cas_audit.epoch_v1 other
  LEFT JOIN v3_cas_audit.prepared_fence_abort_v1 historical ON historical.epoch_id=other.epoch_id
  WHERE other.epoch_id<>e.epoch_id
    AND (historical.state IS DISTINCT FROM 'ABORT_RECORDED_NOT_RELEASED'
      OR historical.source_sha256 IS DISTINCT FROM other.source_sha256
      OR historical.prepared_fence_sha256 IS DISTINCT FROM other.original_fence_sha256
      OR historical.caller_acl_sha256 IS DISTINCT FROM other.approved_caller_acl_sha256)
 )
 AND (c.j->>'active_series_count')::integer=1
 AND (c.j->>'original_active_series_count')::integer=1
 AND (c.j->>'cas_rpc_count')::integer=1
 AND (c.j->>'intent_count')::integer=0
 AND (c.j->>'attempt_count')::integer=0
 AND (c.j->>'dispatch_unknown_count')::integer=0
 AND (SELECT count(*) FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
     WHERE n.nspname='public' AND p.proname='rotate_v2r4_to_v3_experimental_paper')=1
 AND pg_catalog.has_function_privilege('v3_cas_executor',
   'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)','EXECUTE')
 AND NOT EXISTS (SELECT 1 FROM pg_catalog.unnest(ARRAY[
    'anon','authenticated','service_role','v3_cas_executor_actor',
    'v3_cas_audit_reader','v3_cas_audit_writer']) AS r(role_name)
  WHERE pg_catalog.has_function_privilege(r.role_name,
   'public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)','EXECUTE'))
 AND (SELECT count(*) FROM pg_catalog.pg_roles WHERE rolname IN
    ('v3_cas_executor','v3_cas_executor_actor','v3_cas_audit_writer_actor') AND NOT rolcanlogin)=3
 AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_stat_activity WHERE usename IN
    ('v3_cas_executor','v3_cas_executor_actor','v3_cas_audit_writer_actor'))
 AND NOT pg_catalog.pg_has_role(session_user,'v3_cas_audit_writer','SET');
COMMIT;
'@
  $checks[0].Sql=$checks[0].Sql.Replace('__NONCE__',$ObservationNonce)
 }
}

$plain=$null
try{
 $root='system'
 if($CaFile){
  $ca=Get-Item -LiteralPath $CaFile -Force -ErrorAction Stop
  if($ca.PSIsContainer -or $ca.Length -lt 100 -or $ca.Length -gt 65536 -or
     [bool]($ca.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
     [IO.Path]::GetExtension($ca.Name) -notin @('.crt','.cer','.pem')){throw 'PR710_CA_HOLD'}
  $root=$ca.FullName
 }
 $file=Join-Path $dir 'reader.dpapi'
 $entropy=[Text.Encoding]::ASCII.GetBytes('V3_CAS_AUDIT_ACTOR_READER_V1')
 $plain=[Security.Cryptography.ProtectedData]::Unprotect([IO.File]::ReadAllBytes($file),
  $entropy,[Security.Cryptography.DataProtectionScope]::CurrentUser)
 $secret=[Text.Encoding]::ASCII.GetString($plain)
 if($secret -cnotmatch '^[a-f0-9]{64}$'){throw 'PR710_DPAPI_FORMAT_HOLD'}
 $env:PGPASSWORD=$secret;$env:PGSSLROOTCERT=$root
 $conn="host=$hostName port=5432 dbname=postgres user=v3_cas_audit_reader_actor.$project sslmode=verify-full connect_timeout=10"
 $output=& $psql -X -w -qAt -v ON_ERROR_STOP=1 -d $conn -c $checks[0].Sql 2>&1
 if($LASTEXITCODE -ne 0){throw 'PR710_CLOUD_QUERY_HOLD'}
 $wire=($output|Out-String).Trim()
 if($wire.Length -lt 400 -or $wire.Length -gt 4096){throw 'PR710_CLOUD_WIRE_HOLD'}
 $receiptKind=if($PostStopTerminalReader){'V3_CAS_PREPARED_FENCE_ABORT_READER_RECEIPT_V1'}else{'V3_POSTSTOP_CURRENT_INDEPENDENT_CLOUD_READER_V1'}
 $row=Assert-V3PostStopFreshReader $wire $ObservationNonce $receiptKind
 if($PostStopTerminalReader){
  if([string]$row.epoch_id -cne 'V3CAS-AUDIT-f27cce0ba68043b480e4f97698dd2901' -or
   [string]$row.state -cne 'ABORT_RECORDED_NOT_RELEASED' -or
   [string]$row.issuer_actor -cne 'v3_cas_inhibit_issuer_actor' -or
   $row.cloud_cas_rpc_count -ne 1 -or
   $row.cloud_cas_rpc_acl_restricted -ne $true -or
   $row.cloud_executor_can_login -ne $false -or
   $row.cloud_active_series_count -ne 1 -or
   $row.cloud_original_active_series_count -ne 1){
    throw 'V3_POSTSTOP_TERMINAL_READER_SCOPE_HOLD'
  }
  $signed=Save-V3SignedNotebookReaderSnapshot $wire $ReviewedNotebookCertificateSha256
  [pscustomobject]@{kind='V3_POSTSTOP_TERMINAL_NOTEBOOK_CLOUD_CMS_V1';status='SIGNED_TERMINAL_READER_NO_RUNTIME_AUTH'
   observation_nonce=$ObservationNonce;local_directory=$signed.local_directory
   receipt='reader.json';signature='reader.cms';no_production_effect=$true}|ConvertTo-Json -Compress
  return
 }
 # $row=Assert-V3PostStopFreshReader $wire $ObservationNonce 'V3_POSTSTOP_CURRENT_INDEPENDENT_CLOUD_READER_V1'
 if([string]$row.reader_role -cne 'v3_cas_audit_reader' -or $row.inhibit_state -cne 'INHIBITED' -or
  $row.current_cloud_custody_verified -ne $true -or $row.sealed -ne $false -or
  $row.next_ordinal -ne 1 -or $row.intent_count -ne 0 -or $row.attempt_count -ne 0 -or
  $row.abort_count -ne 0 -or $row.executor_login_closed -ne $true -or
  $row.executor_sessions_count -ne 0 -or $row.v3_active_series_count -ne 0 -or
  $row.v2r4_active_series_count -ne 1 -or $row.cloud_cas_rpc_count -ne 1){
  throw 'PR710_CLOUD_STATE_HOLD'
 }
 $signed=Save-V3SignedNotebookReaderSnapshot $wire $ReviewedNotebookCertificateSha256
 [pscustomobject]@{kind='V3_POSTSTOP_NOTEBOOK_CLOUD_CMS_V1';status='READ_ONLY_NO_RECOVERY'
  observation_nonce=$ObservationNonce;local_directory=$signed.local_directory
  receipt='reader.json';signature='reader.cms';no_production_effect=$true}|ConvertTo-Json -Compress
}finally{
 Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
 Remove-Item Env:\PGSSLROOTCERT -ErrorAction SilentlyContinue
 Remove-Variable secret,output -ErrorAction SilentlyContinue
 if($null -ne $plain){[Array]::Clear($plain,0,$plain.Length)}
}
