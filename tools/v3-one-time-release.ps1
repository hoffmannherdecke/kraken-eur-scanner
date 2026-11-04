# Existing #99 release: separate authorization for Cloud DDL and host rehearsal.
# Default is local inventory only. No implicit installation, STOP, CAS or Paper.
[CmdletBinding()]
param(
 [ValidateSet('Inventory','InstallCloud','ReadbackCloud','OriginalhostAbortRestore')][string]$Mode='Inventory',
 [string]$PackageRoot=(Split-Path $PSScriptRoot -Parent),
 [string]$ApprovalJson='', [string]$ApprovalCms='', [string]$ExpectedReleaseCommit='',
 [string]$AuthorityAdmissionJson='', [string]$ExpectedAuthorityAdmissionSha256='',
 [Security.SecureString]$PostgresPassword,
 [string]$CaFile='', [string]$IssuerPrestopJson='', [string]$IssuerPrestopCms='',
 [string]$TerminalAbortJson='', [string]$TerminalAbortCms='',
 [string]$InstallReadbackJson='', [string]$BackupDirectory=''
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
Import-Module (Join-Path $PSScriptRoot 'v3-one-time-release-authorization.psm1') -Force

function Assert-V3OriginalInteractiveOwner {
 if($env:OS -cne 'Windows_NT' -or $env:COMPUTERNAME -cne 'MINI-PC' -or
    $env:GITHUB_ACTIONS -eq 'true' -or -not [Environment]::UserInteractive){throw 'V3_RELEASE_ORIGINAL_INTERACTIVE_MINIPC_REQUIRED'}
 $principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
 if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){
  throw 'V3_RELEASE_EXISTING_ADMIN_OPERATOR_REQUIRED'
 }
}
function Invoke-V3ReleasePg([string]$Sql,[Security.SecureString]$Password,[string]$Ca) {
 $exe='C:\Program Files\PostgreSQL\17\bin\psql.exe'
 $null=Read-V3ReleaseLocalBytes -Path $exe -MaxBytes 67108864
 $caRoot='system'
 if($Ca){$null=Read-V3ReleaseLocalBytes -Path $Ca -MaxBytes 65536;$caRoot=[IO.Path]::GetFullPath($Ca)}
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
 $start.EnvironmentVariables['PGUSER']='postgres.nlgzjmqgwueojlyqmoru'
 $start.EnvironmentVariables['PGSSLMODE']='verify-full'
 $start.EnvironmentVariables['PGSSLROOTCERT']=$caRoot
 $start.EnvironmentVariables['PGCONNECT_TIMEOUT']='10'
 $start.EnvironmentVariables['PGAPPNAME']='V3-one-time-release-99'
 $ptr=[IntPtr]::Zero;$proc=[Diagnostics.Process]::new()
 try {
  $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($Password)
  $start.EnvironmentVariables['PGPASSWORD']=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
  $proc.StartInfo=$start
  if(-not $proc.Start()){throw 'V3_RELEASE_PG_START_FAILED'}
  $out=$proc.StandardOutput.ReadToEndAsync();$err=$proc.StandardError.ReadToEndAsync()
  $proc.StandardInput.Write($Sql);$proc.StandardInput.Close()
  if(-not $proc.WaitForExit(60000)){
   $proc.Kill();throw 'V3_RELEASE_PG_TIMEOUT_OUTCOME_UNKNOWN_NO_RETRY'
  }
  $proc.WaitForExit()
  $output=$out.GetAwaiter().GetResult();$null=$err.GetAwaiter().GetResult()
  if($proc.ExitCode -ne 0){throw 'V3_RELEASE_PG_FAILED_OUTCOME_UNCONFIRMED_READBACK_REQUIRED_NO_RETRY'}
  return $output.Trim()
 }finally {
  if($ptr -ne [IntPtr]::Zero){[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)}
  $start.EnvironmentVariables.Remove('PGPASSWORD');$proc.Dispose()
 }
}
function Get-V3ReleaseVerifiedReadback([string]$Sql,[string]$ReleaseSql,[Security.SecureString]$Password,[string]$Ca) {
 $wire=Invoke-V3ReleasePg -Sql $Sql -Password $Password -Ca $Ca
 $readback=$wire|ConvertFrom-Json -ErrorAction Stop
 if([string]$readback.kind -cne 'V3_ONE_TIME_ABORT_INSTALL_READBACK_V1' -or $readback.verified -ne $true){
  throw 'V3_RELEASE_ORIGINAL_READBACK_WIRE_HOLD'
 }
 $bodies=@{}
 foreach($m in [regex]::Matches($ReleaseSql,'(?s)CREATE FUNCTION v3_cas_audit\.(?<name>[a-z0-9_]+)\(.*?AS \$(?<tag>[a-z]+)\$(?<body>.*?)\$\k<tag>\$;')){
  $bodies[$m.Groups['name'].Value]=$m.Groups['body'].Value
 }
 if($bodies.Count -ne 3 -or @($readback.function_bodies).Count -ne 3){throw 'V3_RELEASE_FUNCTION_SET_HOLD'}
 foreach($f in $readback.function_bodies){
  if(-not $bodies.ContainsKey([string]$f.name) -or [string]$f.body -cne [string]$bodies[[string]$f.name]){
   throw 'V3_RELEASE_ORIGINAL_FUNCTION_BODY_DRIFT'
  }
 }
 $policies=@{
  v3_cas_epoch_owner_abort_read_v1=@('epoch_v1','SELECT','v3_cas_audit_table_owner','true','')
  v3_cas_epoch_owner_abort_update_v1=@('epoch_v1','UPDATE','v3_cas_audit_table_owner','true','true')
  v3_cas_intent_owner_abort_read_v1=@('intent_v1','SELECT','v3_cas_audit_table_owner','true','')
  v3_prepared_abort_owner_only_v1=@('prepared_fence_abort_v1','ALL','v3_cas_audit_table_owner','true','true')
  v3_prepared_abort_reader_select_v1=@('prepared_fence_abort_v1','SELECT','v3_cas_audit_reader','true','')
 }
 if(@($readback.policies).Count -ne 5){throw 'V3_RELEASE_ORIGINAL_POLICY_COUNT_HOLD'}
 foreach($p in $readback.policies){
  $expected=$policies[[string]$p.policy_name]
  if($null -eq $expected -or [string]$p.table_name -cne $expected[0] -or [string]$p.command -cne $expected[1] -or
     @($p.roles).Count -ne 1 -or [string]$p.roles[0] -cne $expected[2] -or
     [string]$p.using_expression -cne $expected[3] -or [string]$p.check_expression -cne $expected[4]){
   throw 'V3_RELEASE_ORIGINAL_POLICY_DRIFT'
  }
 }
 if(@($readback.function_acl).Count -ne 5){throw 'V3_RELEASE_FUNCTION_ACL_COUNT_HOLD'}
 foreach($acl in $readback.function_acl){
  $allowed=if([string]$acl.function_name -ceq 'record_prepared_fence_abort_v1'){'v3_cas_inhibit_issuer_actor'}
   elseif([string]$acl.function_name -ceq 'read_committed_pre_stop_inhibit_v1'){'v3_cas_audit_reader'}else{''}
  if([string]$acl.privilege -cne 'EXECUTE' -or $acl.grantable -ne $false -or
     [string]$acl.grantee -cnotin @('v3_cas_audit_table_owner',$allowed)){throw 'V3_RELEASE_FUNCTION_ACL_DRIFT'}
 }
 return $wire
}

$hashes=Get-V3OneTimeReleaseArtifactInventory -PackageRoot $PackageRoot
$packageLease=Open-V3ReleasePackageReadLease -PackageRoot $PackageRoot -Inventory $hashes
try {
if($Mode -eq 'Inventory'){
 [pscustomobject]@{kind='V3_ONE_TIME_RELEASE_INVENTORY_V1';artifacts=$hashes;
   production_authorized=$false;cloud_contacted=$false;host_mutated=$false}|ConvertTo-Json -Depth 5
 return
}
Assert-V3OriginalInteractiveOwner
$scope=if($Mode -eq 'OriginalhostAbortRestore'){'ORIGINALHOST_ABORT_RESTORE'}else{'CLOUD_ABORT_INSTALL'}
$approval=$null;$cms=$null;$authorityPin='';$authorized=$null
if($Mode -ne 'ReadbackCloud'){
 # The independent admission record is supplied by the existing #99 authority,
 # with its exact digest in the reviewed execution instruction. Never create
 # it, auto-enroll the candidate Notebook certificate, or accept a free pin.
 $admissionBytes=Read-V3ReleaseLocalBytes -Path $AuthorityAdmissionJson
 if($Mode -ne 'OriginalhostAbortRestore'){
  $authorityPin=Assert-V3ReleaseAuthorityAdmission -Bytes $admissionBytes `
   -ExpectedSha256 $ExpectedAuthorityAdmissionSha256 -ReleaseCommit $ExpectedReleaseCommit
 }
 $approval=Read-V3ReleaseLocalBytes -Path $ApprovalJson
 $cms=Read-V3ReleaseLocalBytes -Path $ApprovalCms -MaxBytes 32768
 if($Mode -ne 'OriginalhostAbortRestore'){
  $authorized=Assert-V3OneTimeReleaseAuthorization -Payload $approval -Cms $cms `
   -ReviewedAuthorityCertificateSha256 $authorityPin -Scope $scope `
   -ExpectedReleaseCommit $ExpectedReleaseCommit -ExpectedArtifacts $hashes
 }
}
if($Mode -eq 'OriginalhostAbortRestore'){
 Import-Module (Join-Path $PSScriptRoot 'v3-one-time-originalhost-release.psm1') -Force
 Invoke-V3OneTimeOriginalhostRelease -PackageRoot $PackageRoot -Approval $approval -ApprovalCms $cms `
  -AuthorityAdmission $admissionBytes -ExpectedAuthorityAdmissionSha256 $ExpectedAuthorityAdmissionSha256 `
  -ExpectedReleaseCommit $ExpectedReleaseCommit -IssuerPrestopJson $IssuerPrestopJson -IssuerPrestopCms $IssuerPrestopCms `
  -TerminalAbortJson $TerminalAbortJson -TerminalAbortCms $TerminalAbortCms `
  -InstallReadbackJson $InstallReadbackJson -BackupDirectory $BackupDirectory|ConvertTo-Json -Depth 6
 return
}
$releaseSql=[Text.Encoding]::UTF8.GetString((Read-V3ReleaseLocalBytes -Path (Join-Path $PackageRoot 'supabase/v3-cas-prepared-fence-abort-release.sql')))
$readbackSql=[Text.Encoding]::UTF8.GetString((Read-V3ReleaseLocalBytes -Path (Join-Path $PackageRoot 'supabase/v3-cas-prepared-fence-abort-release-readback.sql')))
if($null -eq $PostgresPassword){$PostgresPassword=Read-Host 'Existing postgres password (not saved)' -AsSecureString}
if($Mode -eq 'InstallCloud'){
 $a=$authorized.claims
 if(@($a.bindings.PSObject.Properties).Count -ne 1 -or
    [string]$a.bindings.source_sha256 -cne '86dfebe688eda78ba14000a63f534e3295af63dcf19c48e07aab26d75e76fbd6'){
  throw 'V3_RELEASE_INSTALL_SOURCE_BINDING_HOLD'
 }
 $expires=$authorized.expires_at.ToUniversalTime().ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
 $settings=@{
  scope='CLOUD_ABORT_INSTALL';base_commit=[string]$a.base_commit;source_sha256=[string]$a.bindings.source_sha256
  approval_sha256=$authorized.approval_sha256;release_commit=[string]$a.release_commit;release_id=[string]$a.release_id;expires_at=$expires
 }
 $prefix=@(foreach($key in $settings.Keys){
  # All values have been strictly typed as identifiers, hex hashes or UTC.
  "SELECT set_config('v3_release.$key','$($settings[$key])',false);"
 }) -join "`n"
 $null=Invoke-V3ReleasePg -Sql ($prefix+"`n"+$releaseSql) -Password $PostgresPassword -Ca $CaFile
}
$original=Get-V3ReleaseVerifiedReadback -Sql $readbackSql -ReleaseSql $releaseSql -Password $PostgresPassword -Ca $CaFile
if($Mode -eq 'InstallCloud'){
 $row=$original|ConvertFrom-Json
 if([string]$row.installation.approval_sha256 -cne $authorized.approval_sha256 -or
    [string]$row.installation.release_commit -cne $ExpectedReleaseCommit){throw 'V3_RELEASE_INSTALL_COMMIT_BINDING_READBACK_HOLD'}
}
$original

}finally{foreach($stream in $packageLease){$stream.Dispose()}}
