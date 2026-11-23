# One-shot POST-STOP UNKNOWN Notebook issuer. Separate scoped CMS authorization.
[CmdletBinding()]
param(
 [ValidateSet('Abort','Readback','ExpiredStage4Abort')][string]$Mode,
 [string]$PackageRoot,[string]$ApprovalJson,[string]$ApprovalCms,
 [string]$AuthorityAdmissionJson,[string]$ExpectedAuthorityAdmissionSha256,
 [string]$ExpectedReleaseCommit,[string]$ApprovedPinsJson,
 [string]$HostJson,[string]$OriginalHostCms,[string]$NotebookHostCms,
 [string]$CloudJson,[string]$CloudCms,[string]$TerminalJson,
 [string]$TerminalCms,[string]$CaFile=''
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($env:OS -cne 'Windows_NT' -or $env:COMPUTERNAME -ceq 'MINI-PC' -or
 $env:GITHUB_ACTIONS -eq 'true' -or -not [Environment]::UserInteractive){
 throw 'V3_POSTSTOP_NOTEBOOK_INTERACTIVE_ONLY_HOLD'
}
Import-Module (Join-Path $PSScriptRoot 'v3-one-time-release-authorization.psm1') -Force
. (Join-Path $PSScriptRoot 'v3-post-stop-unknown-quarantine-source-only.ps1')

if($Mode -ceq 'ExpiredStage4Abort'){
 $epoch='V3CAS-AUDIT-caafcb9247b0480b8925b154f8351935'
 $series='PAPER-V3-20261123T091458Z'
 $commit='46c5abbd6af16266c1229943db973dc9d6b2fb4f'
 $source='989e1657e03867774907f3a1ec9c9f4f84ee70c2d4b7a258cad9dc3e480f0043'
 $fence='d4b81e56c455348259d95514ff95b5a28bd057df4c576d912d8f3476d216537b'
 $acl='6f0d59c57f3f7ce3d54f5c674c0d41c342a2a08b9a86001e59353d772f5f66f0'
 $inventory=Get-V3OneTimeReleaseArtifactInventory $PackageRoot
 foreach($rel in @('tools/v3-poststop-authorized-window.ps1','tools/v3-poststop-issuer-release.ps1','tools/v3-poststop-notebook-reader-extension-INACTIVE.ps1')){
  $inventory[$rel]=Get-V3ReleaseSha256 (Read-V3ReleaseLocalBytes (Join-Path $PackageRoot $rel) 1048576)
 }
 if($env:USERNAME -cne 'burns'){throw 'AP05A_NOTEBOOK_ACTOR_HOLD'}
 $pin=Assert-V3ReleaseAuthorityAdmission -Bytes (Read-V3ReleaseLocalBytes $AuthorityAdmissionJson) -ExpectedSha256 $ExpectedAuthorityAdmissionSha256 -ReleaseCommit $ExpectedReleaseCommit
 if($pin -cne '2e3322131208737c58a82c04764bddf4ebe29481c96c79697183710358a2fc57'){throw 'AP05A_AUTHORITY_HOLD'}
 $approvalBytes=Read-V3ReleaseLocalBytes $ApprovalJson 16384
 # Reuse the original PR723 narrow CMS schema without changing the common release module.
 Assert-V3ReleaseCms -Payload $approvalBytes -Cms (Read-V3ReleaseLocalBytes $ApprovalCms 32768) -ReviewedAuthorityCertificateSha256 $pin
 $claims=Read-V3ReleaseJson $approvalBytes
 $af=@('kind','release_id','scope','base_commit','release_commit','not_before_utc','expires_at_utc','project_ref','computer_name','trading_root','artifacts','bindings')
 if(@($claims.PSObject.Properties).Count -ne $af.Count -or @($claims.PSObject.Properties.Name|Where-Object {$_ -cnotin $af}).Count -ne 0 -or
  $claims.kind -cne 'V3_ONE_TIME_RELEASE_AUTHORIZATION_V1' -or [string]$claims.release_id -cnotmatch '^V3-ONETIME-[a-f0-9]{32}$' -or
  $claims.scope -cne 'CLOUD_EXPIRED_STAGE4_TERMINAL_ABORT' -or $claims.base_commit -cne '5b1789e349b157d06d3109c5f0ff10d95154bf81' -or
  $claims.release_commit -cne $ExpectedReleaseCommit -or $claims.project_ref -cne 'nlgzjmqgwueojlyqmoru' -or
  $claims.computer_name -cne 'MINI-PC' -or $claims.trading_root -cne 'C:\Users\ADMIN\Trading' -or
  $claims.artifacts -isnot [pscustomobject] -or $claims.bindings -isnot [pscustomobject] -or
  @($claims.artifacts.PSObject.Properties).Count -ne $inventory.Count){throw 'AP05A_SIGNED_AUTHORIZATION_SCHEMA_HOLD'}
 foreach($rel in $inventory.Keys){
  if([string]$claims.artifacts.$rel -cne [string]$inventory[$rel]){throw 'AP05A_ARTIFACT_PIN_HOLD'}
 }
 $fmt="yyyy-MM-dd'T'HH:mm:ss'Z'"
 $startTime=[datetimeoffset]::MinValue;$endTime=[datetimeoffset]::MinValue
 if(-not [datetimeoffset]::TryParseExact([string]$claims.not_before_utc,$fmt,[Globalization.CultureInfo]::InvariantCulture,[Globalization.DateTimeStyles]::AssumeUniversal,[ref]$startTime) -or
  -not [datetimeoffset]::TryParseExact([string]$claims.expires_at_utc,$fmt,[Globalization.CultureInfo]::InvariantCulture,[Globalization.DateTimeStyles]::AssumeUniversal,[ref]$endTime) -or
  $endTime -le $startTime -or ($endTime-$startTime).TotalMinutes -gt 15 -or
  [datetimeoffset]::UtcNow -lt $startTime -or [datetimeoffset]::UtcNow -ge $endTime){throw 'AP05A_SIGNED_TIME_HOLD'}
 $auth=[pscustomobject]@{claims=$claims;expires_at=$endTime}
 $bindings=$auth.claims.bindings
 $names=@('series_id','epoch_id','epoch_release_commit','source_sha256','fence_sha256','caller_acl_sha256','operator_sha256','controller_sha256','preflight_sha256','terminal_receipt_sha256','owner_comment_id')
 if(@($bindings.PSObject.Properties).Count -ne $names.Count -or @($bindings.PSObject.Properties.Name|Where-Object {$_ -cnotin $names}).Count -ne 0 -or
  $bindings.series_id -cne $series -or $bindings.epoch_id -cne $epoch -or $bindings.epoch_release_commit -cne $commit -or
  $bindings.source_sha256 -cne $source -or $bindings.fence_sha256 -cne $fence -or $bindings.caller_acl_sha256 -cne $acl -or
  $bindings.operator_sha256 -cne $inventory['tools/v3-poststop-issuer-release.ps1'] -or
  $bindings.controller_sha256 -cne $inventory['tools/v3-poststop-authorized-window.ps1'] -or
  [string]$bindings.owner_comment_id -cnotmatch '^[0-9]{9,12}$'){throw 'AP05A_EXACT_BINDINGS_HOLD'}
 $reader=Read-V3ReleaseLocalBytes $CloudJson 8192
 Assert-V3ReleaseCms $reader (Read-V3ReleaseLocalBytes $CloudCms 32768) '61d08dd9a925730f213fedc559664dbfe2a3e4f8f1ae77496b385f7d92f3bc55'
 $pre=Read-V3ReleaseJson $reader
 $preHash=Get-V3ReleaseSha256 $reader
 $observed=[datetimeoffset]::ParseExact([string]$pre.observed_at_utc,"yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'",[Globalization.CultureInfo]::InvariantCulture,[Globalization.DateTimeStyles]::AssumeUniversal)
 if($preHash -cne $bindings.preflight_sha256 -or $pre.kind -cne 'V3_EXPIRED_STAGE4_NOTEBOOK_READBACK_V1' -or $pre.state -cne 'INSTALL_READBACK_ONLY' -or
  $pre.epoch_id -cne $epoch -or $pre.source_sha256 -cne $source -or $pre.fence_sha256 -cne $fence -or $pre.caller_acl_sha256 -cne $acl -or
  $null -ne $pre.terminal_receipt_sha256 -or $observed -gt [datetimeoffset]::UtcNow.AddSeconds(5) -or
  ([datetimeoffset]::UtcNow-$observed).TotalSeconds -ge 30){throw 'AP05A_FRESH_READER_HOLD'}
 $defs=@{begin_executor_inhibit_v1='4aa74188a95758989676049f8200d9b920e3942cd78f793b9d975c79a9d82166';read_paper_release_epoch_v1='b3f6274308a558f305732bfed98e65a2c077e3a36fb9438a52792a09c8f152bf';record_paper_release_abort_v1='96fcbb36d68d6f6544194e4b636f7ee6b24ddf122c961955369876325d9bf2a9'}
 if(@($pre.function_sha256.PSObject.Properties).Count -ne 3){throw 'AP05A_DEFINITION_COUNT_HOLD'}
 foreach($key in $defs.Keys){if([string]$pre.function_sha256.$key -cne $defs[$key]){throw 'AP05A_DEFINITION_DRIFT_HOLD'}}
 $receipt=Get-V3ReleaseSha256 ([Text.Encoding]::ASCII.GetBytes("V3_EXPIRED_STAGE4_TERMINAL_RECEIPT_V1"+[char]10+$epoch+[char]10+$preHash))
 if($receipt -cne $bindings.terminal_receipt_sha256){throw 'AP05A_RECEIPT_DERIVATION_HOLD'}
 $original=Invoke-RestMethod -Uri ('https://api.github.com/repos/hoffmannherdecke/kraken-eur-scanner/issues/comments/'+$bindings.owner_comment_id) -Method Get -TimeoutSec 10 -MaximumRedirection 0
 if([string]$original.id -cne [string]$bindings.owner_comment_id -or $original.user.login -cne 'hoffmannherdecke' -or [string]$original.user.id -cne '331995561' -or
  $original.issue_url -cne 'https://api.github.com/repos/hoffmannherdecke/kraken-eur-scanner/issues/99'){throw 'AP05A_OWNER_ORIGIN_HOLD'}
 $owner=Read-V3ReleaseJson ([Text.Encoding]::UTF8.GetBytes([string]$original.body))
 $fields=@('decision','scope','release_commit','series_id','epoch_id','operator_sha256','controller_sha256','source_sha256','fence_sha256','caller_acl_sha256')
 if(@($owner.PSObject.Properties).Count -ne $fields.Count -or @($owner.PSObject.Properties.Name|Where-Object {$_ -cnotin $fields}).Count -ne 0 -or
  $owner.decision -cne 'APPROVE_ONE_EXPIRED_STAGE4_TERMINAL_ABORT' -or $owner.scope -cne 'CLOUD_EXPIRED_STAGE4_TERMINAL_ABORT' -or
  $owner.release_commit -cne $ExpectedReleaseCommit -or $owner.series_id -cne $series -or $owner.epoch_id -cne $epoch -or
  $owner.operator_sha256 -cne $bindings.operator_sha256 -or $owner.controller_sha256 -cne $bindings.controller_sha256 -or
  $owner.source_sha256 -cne $source -or $owner.fence_sha256 -cne $fence -or $owner.caller_acl_sha256 -cne $acl){throw 'AP05A_OWNER_DECISION_HOLD'}
 $issuerRoot=Join-Path $env:LOCALAPPDATA 'V3CasIndependentIssuer'
 $latch=Join-Path $issuerRoot ($epoch+'-terminal-attempted')
 $sql=@'
BEGIN TRANSACTION ISOLATION LEVEL READ COMMITTED;
SET LOCAL lock_timeout='5s';
SET LOCAL statement_timeout='15s';
SELECT v3_cas_audit.record_paper_release_abort_v1('__EPOCH__','__COMMIT__','__SOURCE__','__FENCE__','__ACL__','__RECEIPT__');
COMMIT;
'@
 foreach($key in @('EPOCH','COMMIT','SOURCE','FENCE','ACL','RECEIPT')){$sql=$sql.Replace('__'+$key+'__',[string](Get-Variable -Name $key.ToLowerInvariant() -ValueOnly))}
 $raw=$null;$password=$null
 try{
  $raw=[Security.Cryptography.ProtectedData]::Unprotect((Read-V3ReleaseLocalBytes (Join-Path $issuerRoot 'issuer-currentuser.dpapi') 8192),[Text.Encoding]::ASCII.GetBytes('V3_CAS_INDEPENDENT_ISSUER_NOTEBOOK_V1'),[Security.Cryptography.DataProtectionScope]::CurrentUser)
  $secret=[Text.Encoding]::ASCII.GetString($raw)
  if($secret -cnotmatch '^[a-f0-9]{64}$'){throw 'AP05A_ISSUER_SECRET_HOLD'}
  $password=ConvertTo-SecureString $secret -AsPlainText -Force
 }finally{if($null -ne $raw){[Array]::Clear($raw,0,$raw.Length)};$secret=$null}
 try{
  if(([datetimeoffset]::UtcNow-$observed).TotalSeconds -ge 30 -or [datetimeoffset]::UtcNow -ge $auth.expires_at){throw 'AP05A_PREFLIGHT_EXPIRED_HOLD'}
  $fs=[IO.File]::Open($latch,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
  try{$fs.Write($approvalBytes,0,$approvalBytes.Length);$fs.Flush($true)}finally{$fs.Dispose()}
  $exe='C:\Program Files\PostgreSQL\17\bin\psql.exe'
  $null=Read-V3ReleaseLocalBytes $exe 67108864
  $ca='system'
  if($CaFile){$null=Read-V3ReleaseLocalBytes $CaFile 65536;$ca=[IO.Path]::GetFullPath($CaFile)}
  $start=[Diagnostics.ProcessStartInfo]::new()
  $start.FileName=$exe;$start.Arguments='-X -q -A -t -w -v ON_ERROR_STOP=1 -f -'
  $start.UseShellExecute=$false;$start.CreateNoWindow=$true
  $start.RedirectStandardInput=$true;$start.RedirectStandardOutput=$true;$start.RedirectStandardError=$true
  foreach($key in @($start.EnvironmentVariables.Keys)){if([string]$key -match '^PG'){$start.EnvironmentVariables.Remove([string]$key)}}
  $start.EnvironmentVariables['PGHOST']='aws-1-eu-west-1.pooler.supabase.com'
  $start.EnvironmentVariables['PGPORT']='5432';$start.EnvironmentVariables['PGDATABASE']='postgres'
  $start.EnvironmentVariables['PGUSER']='v3_cas_inhibit_issuer_actor.nlgzjmqgwueojlyqmoru'
  $start.EnvironmentVariables['PGSSLMODE']='verify-full';$start.EnvironmentVariables['PGSSLROOTCERT']=$ca
  $start.EnvironmentVariables['PGCONNECT_TIMEOUT']='10'
  $start.EnvironmentVariables['PGAPPNAME']='AP05A-once'
  $ptr=[IntPtr]::Zero;$process=[Diagnostics.Process]::new()
  try{
   $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($password)
   $start.EnvironmentVariables['PGPASSWORD']=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
   $process.StartInfo=$start
   if(-not $process.Start()){throw 'AP05A_START_UNKNOWN_NO_RETRY'}
   $out=$process.StandardOutput.ReadToEndAsync();$err=$process.StandardError.ReadToEndAsync()
   $process.StandardInput.Write($sql);$process.StandardInput.Close()
   if(-not $process.WaitForExit(45000)){$process.Kill();throw 'AP05A_TIMEOUT_UNKNOWN_NO_RETRY'}
   $process.WaitForExit()
   $null=$out.GetAwaiter().GetResult();$null=$err.GetAwaiter().GetResult()
   if($process.ExitCode -ne 0){throw 'AP05A_RESULT_UNKNOWN_NO_RETRY'}
  }finally{
   if($ptr -ne [IntPtr]::Zero){[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)}
   $start.EnvironmentVariables.Remove('PGPASSWORD');$process.Dispose()
  }
 }finally{if($null -ne $password){$password.Dispose()}}
 [pscustomobject]@{kind='AP05A_TERMINAL_DISPATCH_RETURNED_READER_REQUIRED';epoch_id=$epoch;receipt_sha256=$receipt;retry_authorized=$false}|ConvertTo-Json -Compress
 return
}

$epoch='V3CAS-AUDIT-3c6b22d02d8a413c88bfede21acce2ea'
$inventory=Get-V3OneTimeReleaseArtifactInventory $PackageRoot
foreach($rel in @('tools/v3-poststop-issuer-release.ps1',
 'tools/v3-post-stop-unknown-quarantine-source-only.ps1',
 'tools/v3-poststop-notebook-reader-extension-INACTIVE.ps1')){
 $inventory[$rel]=Get-V3ReleaseSha256 (Read-V3ReleaseLocalBytes (Join-Path $PackageRoot $rel) 1048576)
}
$admission=Read-V3ReleaseLocalBytes $AuthorityAdmissionJson
$authorityPin=Assert-V3ReleaseAuthorityAdmission -Bytes $admission -ExpectedSha256 $ExpectedAuthorityAdmissionSha256 -ReleaseCommit $ExpectedReleaseCommit
# Separate narrow scope; immutable historical release module is unchanged.
$approvalBytes=Read-V3ReleaseLocalBytes $ApprovalJson
Assert-V3ReleaseCms -Payload $approvalBytes -Cms (Read-V3ReleaseLocalBytes $ApprovalCms 32768) -ReviewedAuthorityCertificateSha256 $authorityPin
$a=Read-V3ReleaseJson $approvalBytes
$fields=@('kind','release_id','scope','base_commit','release_commit','not_before_utc',
 'expires_at_utc','project_ref','computer_name','trading_root','artifacts','bindings')
if(@($a.PSObject.Properties.Name).Count -ne $fields.Count -or
 @($a.PSObject.Properties.Name|Where-Object {$_ -cnotin $fields}).Count -ne 0 -or
 [string]$a.kind -cne 'V3_ONE_TIME_RELEASE_AUTHORIZATION_V1' -or
 [string]$a.release_id -cnotmatch '^V3-ONETIME-[a-f0-9]{32}$' -or
 [string]$a.scope -cne 'CLOUD_POSTSTOP_TERMINAL_ABORT' -or
 [string]$a.base_commit -cne '5b1789e349b157d06d3109c5f0ff10d95154bf81' -or
 [string]$a.release_commit -cne $ExpectedReleaseCommit -or
 [string]$a.project_ref -cne 'nlgzjmqgwueojlyqmoru' -or
 [string]$a.computer_name -cne 'MINI-PC' -or
 [string]$a.trading_root -cne 'C:\Users\ADMIN\Trading' -or
 $a.artifacts -isnot [pscustomobject] -or $a.bindings -isnot [pscustomobject]){
 throw 'V3_POSTSTOP_SIGNED_SCOPE_OR_IDENTITY_HOLD'
}
$times=@{}
foreach($key in @('not_before_utc','expires_at_utc')){
 $m=[regex]::Match([Text.Encoding]::UTF8.GetString($approvalBytes),'"'+$key+'"\s*:\s*"(?<t>[^"\\]*)"')
 $at=[datetimeoffset]::MinValue
 if(-not $m.Success -or -not [datetimeoffset]::TryParseExact(
  $m.Groups['t'].Value,"yyyy-MM-dd'T'HH:mm:ss'Z'",
  [Globalization.CultureInfo]::InvariantCulture,
  [Globalization.DateTimeStyles]::AssumeUniversal,[ref]$at)){
  throw 'V3_POSTSTOP_APPROVAL_TIME_FORMAT_HOLD'
 }
 $times[$key]=$at
}
$now=[datetimeoffset]::UtcNow
if($times.expires_at_utc -le $times.not_before_utc -or
 ($times.expires_at_utc-$times.not_before_utc).TotalMinutes -gt 15 -or
 $now -lt $times.not_before_utc -or $now -ge $times.expires_at_utc){
 throw 'V3_POSTSTOP_APPROVAL_EXPIRED_HOLD'
}
if(@($a.artifacts.PSObject.Properties).Count -ne $inventory.Count){
 throw 'V3_POSTSTOP_ARTIFACT_SET_HOLD'
}
foreach($rel in $inventory.Keys){
 if([string]$a.artifacts.$rel -cne [string]$inventory[$rel] -or
  [string]$inventory[$rel] -cnotmatch '^[a-f0-9]{64}$'){
  throw 'V3_POSTSTOP_ARTIFACT_HASH_HOLD'
 }
}
$auth=[pscustomobject]@{claims=$a;expires_at=$times.expires_at_utc}
$b=$auth.claims.bindings
$required=@('epoch_id','source_sha256','fence_sha256','caller_acl_sha256','pins_sha256')
if(@($b.PSObject.Properties.Name).Count -ne $required.Count -or
 @($b.PSObject.Properties.Name|Where-Object {$_ -cnotin $required}).Count){
 throw 'V3_POSTSTOP_AUTH_BINDINGS_HOLD'
}
if([string]$b.epoch_id -cne $epoch -or
 [string]$b.source_sha256 -cne '989e1657e03867774907f3a1ec9c9f4f84ee70c2d4b7a258cad9dc3e480f0043' -or
 [string]$b.fence_sha256 -cne '548615beee65139c2f4cdf8172ba5ddc383d68452c41821b4af1ea2de91f4d0a' -or
 [string]$b.caller_acl_sha256 -cne '6f0d59c57f3f7ce3d54f5c674c0d41c342a2a08b9a86001e59353d772f5f66f0'){
 throw 'V3_POSTSTOP_AUTH_EXACT_TARGET_HOLD'
}
$pinsBytes=Read-V3ReleaseLocalBytes $ApprovedPinsJson
if([string]$b.pins_sha256 -cne (Get-V3ReleaseSha256 $pinsBytes)){throw 'V3_POSTSTOP_APPROVED_PINS_BYTES_HOLD'}
$pins=Read-V3ReleaseJson $pinsBytes
if([string]$pins.epoch_id -cne $epoch -or
 [string]$pins.source_sha256 -cne [string]$b.source_sha256 -or
 [string]$pins.epoch_fence_sha256 -cne [string]$b.fence_sha256 -or
 [string]$pins.caller_acl_sha256 -cne [string]$b.caller_acl_sha256){
 throw 'V3_POSTSTOP_PINS_AUTH_DRIFT_HOLD'
}
if($Mode -eq 'Readback'){
 $receiptInput=[pscustomobject]@{kind='V3_POSTSTOP_CURRENT_CUSTODY_SOURCE_REVIEW_V1';independently_signed_current_custody=$true;epoch_id=$epoch;host_payload_sha256=[string]$pins.host_payload_sha256;cloud_payload_sha256=[string]$pins.cloud_payload_sha256;owner_review_sha256=[string]$pins.owner_review_sha256}
 $receiptSha=Get-V3PostStopCurrentCustodyReceiptSha256 $receiptInput
 $terminal=Assert-V3PostStopSignedTerminalCloud -Payload (Read-V3ReleaseLocalBytes $TerminalJson 8192) -Cms (Read-V3ReleaseLocalBytes $TerminalCms 32768) -Pins $pins -CurrentCustodyReceiptSha256 $receiptSha
 [pscustomobject]@{kind='TARGET_EPOCH_TERMINALIZED';epoch_id=$epoch;terminal_cloud_abort_confirmed=$terminal.terminal_cloud_abort_confirmed;stage4_authorized=$false;writer_authorized=$false}|ConvertTo-Json -Compress
 return
}
$hostBytes=Read-V3ReleaseLocalBytes $HostJson 8192
$cloudBytes=Read-V3ReleaseLocalBytes $CloudJson 8192
$receiptInput=@{
 HostPayload=$hostBytes;OriginalHostCms=(Read-V3ReleaseLocalBytes $OriginalHostCms 32768)
 NotebookHostCms=(Read-V3ReleaseLocalBytes $NotebookHostCms 32768)
 CloudPayload=$cloudBytes;CloudCms=(Read-V3ReleaseLocalBytes $CloudCms 32768)
 Pins=$pins;Now=[datetimeoffset]::UtcNow
}
$review=Assert-V3PostStopOwnerAdmittedCurrentHostTripleCms @receiptInput
if($review.current_custody_contract_verified -ne $true -or
 $review.recovery_authorized -ne $false -or $review.writer_authorized -ne $false){
 throw 'V3_POSTSTOP_CURRENT_CUSTODY_HOLD'
}
$custody=Assert-V3PostStopUnknownCurrentCustody -HostPayload $hostBytes -HostCms $receiptInput.NotebookHostCms -CloudPayload $cloudBytes -CloudCms $receiptInput.CloudCms -Pins $pins
$receiptSha=Get-V3PostStopCurrentCustodyReceiptSha256 $custody
if([string]$pins.host_payload_sha256 -cne (Get-V3ReleaseSha256 $hostBytes) -or [string]$pins.cloud_payload_sha256 -cne (Get-V3ReleaseSha256 $cloudBytes)){throw 'V3_POSTSTOP_CURRENT_RECEIPT_PIN_HOLD'}
$plan=Get-V3PostStopCloudAbortCandidate -Custody $custody -Pins $pins -CurrentCustodyReceiptSha256 $receiptSha -Expiry $auth.expires_at
if($plan.execution_authorized -ne $false){throw 'V3_POSTSTOP_CANDIDATE_AUTH_CONFUSION_HOLD'}
# Scoped PG17 TLS transport, independent issuer identity only.
function Invoke-V3PostStopIssuerPg([string]$Sql,[Security.SecureString]$Password,[string]$Ca){
 $exe='C:\Program Files\PostgreSQL\17\bin\psql.exe'
 $null=Read-V3ReleaseLocalBytes $exe 67108864
 $root='system'
 if($Ca){$null=Read-V3ReleaseLocalBytes $Ca 65536;$root=[IO.Path]::GetFullPath($Ca)}
 $start=[Diagnostics.ProcessStartInfo]::new()
 $start.FileName=$exe
 $start.Arguments='-X -q -A -t -w -v ON_ERROR_STOP=1 -f -'
 $start.UseShellExecute=$false;$start.CreateNoWindow=$true
 $start.RedirectStandardInput=$true;$start.RedirectStandardOutput=$true;$start.RedirectStandardError=$true
 foreach($key in @($start.EnvironmentVariables.Keys)){
  if([string]$key -match '^PG'){$start.EnvironmentVariables.Remove([string]$key)}
 }
 $start.EnvironmentVariables['PGHOST']='aws-1-eu-west-1.pooler.supabase.com'
 $start.EnvironmentVariables['PGPORT']='5432'
 $start.EnvironmentVariables['PGDATABASE']='postgres'
 $start.EnvironmentVariables['PGUSER']='v3_cas_inhibit_issuer_actor.nlgzjmqgwueojlyqmoru'
 $start.EnvironmentVariables['PGSSLMODE']='verify-full'
 $start.EnvironmentVariables['PGSSLROOTCERT']=$root
 $start.EnvironmentVariables['PGCONNECT_TIMEOUT']='10'
 $start.EnvironmentVariables['PGAPPNAME']='V3-AP04-poststop-issuer-once'
 $ptr=[IntPtr]::Zero;$proc=[Diagnostics.Process]::new()
 try{
  $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($Password)
  $start.EnvironmentVariables['PGPASSWORD']=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
  $proc.StartInfo=$start
  if(-not $proc.Start()){throw 'V3_POSTSTOP_ISSUER_START_HOLD'}
  $out=$proc.StandardOutput.ReadToEndAsync()
  $err=$proc.StandardError.ReadToEndAsync()
  $proc.StandardInput.Write($Sql);$proc.StandardInput.Close()
  if(-not $proc.WaitForExit(60000)){$proc.Kill();throw 'V3_POSTSTOP_PG_UNKNOWN_NO_RETRY'}
  $proc.WaitForExit()
  $null=$out.GetAwaiter().GetResult()
  $null=$err.GetAwaiter().GetResult()
  if($proc.ExitCode -ne 0){throw 'V3_POSTSTOP_PG_OUTCOME_UNKNOWN_NO_RETRY'}
 }finally{
  if($ptr -ne [IntPtr]::Zero){[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)}
  $start.EnvironmentVariables.Remove('PGPASSWORD');$proc.Dispose()
 }
}
$issuerRoot=Join-Path $env:LOCALAPPDATA 'V3CasIndependentIssuer'
Add-Type -AssemblyName System.Security
$raw=$null;$password=$null
try{
 $raw=[Security.Cryptography.ProtectedData]::Unprotect(
  (Read-V3ReleaseLocalBytes (Join-Path $issuerRoot 'issuer-currentuser.dpapi') 8192),
  [Text.Encoding]::ASCII.GetBytes('V3_CAS_INDEPENDENT_ISSUER_NOTEBOOK_V1'),
  [Security.Cryptography.DataProtectionScope]::CurrentUser)
 $secret=[Text.Encoding]::ASCII.GetString($raw)
 if($secret -cnotmatch '^[a-f0-9]{64}$'){throw 'V3_POSTSTOP_ISSUER_SECRET_HOLD'}
 $password=ConvertTo-SecureString $secret -AsPlainText -Force
}finally{if($null -ne $raw){[Array]::Clear($raw,0,$raw.Length)};$secret=$null}
try{
 $latch=Join-Path $issuerRoot 'poststop-3c6b22d02d8a413c88bfede21acce2ea-attempted'
 $transport={
  param([byte[]]$Payload)
  $sql=[Text.UTF8Encoding]::new($false,$true).GetString($Payload)
  $null=Invoke-V3PostStopIssuerPg -Sql $sql -Password $password -Ca $CaFile
 }
 $out=Invoke-V3PostStopCloudOnceCandidate -LatchPath $latch -PlanBytes ([Text.UTF8Encoding]::new($false).GetBytes([string]$plan.sql)) -Transport $transport
 $out|ConvertTo-Json -Compress
}finally{if($null -ne $password){$password.Dispose()}}
# Successful dispatch never equals independent terminal readback. No retry.
