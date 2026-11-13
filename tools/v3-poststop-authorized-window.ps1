# Exact PR723 post-STOP Notebook controller. One manual invocation waits for
# fresh host/Cloud readers, signs release approval, dispatches at most once,
# and performs independent terminal readback. NO usage before CI/device approval.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$PackageRoot,
 [Parameter(Mandatory=$true)][string]$StaticOwnerPolicyJson,
 [Parameter(Mandatory=$true)][string]$StaticOwnerPolicySha256,
 [Parameter(Mandatory=$true)][string]$AuthorityAdmissionJson,
 [Parameter(Mandatory=$true)][string]$AuthorityAdmissionSha256,
 [Parameter(Mandatory=$true)][string]$ObservationNonce,
 [Parameter(Mandatory=$true)][string]$OriginalHostDirectory,
 [string]$CaFile=''
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$release='b27cf775e5de25786cba5f2dd8f0bb78564f8452'
$epoch='V3CAS-AUDIT-f27cce0ba68043b480e4f97698dd2901'
$authority='2e3322131208737c58a82c04764bddf4ebe29481c96c79697183710358a2fc57'
if($env:OS -cne 'Windows_NT' -or $env:USERNAME -cne 'burns' -or $env:COMPUTERNAME -ieq 'MINI-PC' -or
 $env:GITHUB_ACTIONS -eq 'true' -or -not [Environment]::UserInteractive){throw 'POSTSTOP_AUTH_NOTEBOOK_BURNS_ONLY_HOLD'}
if($ObservationNonce -cnotmatch '^[a-f0-9]{32}$' -or $StaticOwnerPolicySha256 -cnotmatch '^[a-f0-9]{64}$' -or
 $AuthorityAdmissionSha256 -cnotmatch '^[a-f0-9]{64}$'){throw 'POSTSTOP_AUTH_PREPIN_HOLD'}
$module=Join-Path $PackageRoot 'tools\v3-one-time-release-authorization.psm1'
$issuer=Join-Path $PackageRoot 'tools\v3-poststop-issuer-release.ps1'
$coordinator=Join-Path $PackageRoot 'tools\v3-poststop-triple-reader-window-INACTIVE.ps1'
$reader=Join-Path $PackageRoot 'tools\v3-poststop-notebook-reader-extension-INACTIVE.ps1'
foreach($file in @($module,$issuer,$coordinator,$reader)){
 if(-not [IO.File]::Exists($file)){throw ('POSTSTOP_AUTH_INSTALLED_SOURCE_MISSING: '+$file)}
}
Import-Module $module -Force
if((Get-V3ReleaseSha256 (Read-V3ReleaseLocalBytes $StaticOwnerPolicyJson 8192)) -cne $StaticOwnerPolicySha256){throw 'POSTSTOP_AUTH_STATIC_PIN_HOLD'}
$p=Read-V3ReleaseJson (Read-V3ReleaseLocalBytes $StaticOwnerPolicyJson 8192)
if([string]$p.observation_nonce -cne $ObservationNonce -or [string]$p.epoch_id -cne $epoch){throw 'POSTSTOP_AUTH_NONCE_EPOCH_HOLD'}
$pin=Assert-V3ReleaseAuthorityAdmission -Bytes (Read-V3ReleaseLocalBytes $AuthorityAdmissionJson) `
 -ExpectedSha256 $AuthorityAdmissionSha256 -ReleaseCommit $release
if($pin -cne $authority){throw 'POSTSTOP_AUTH_SIGNER_ADMISSION_HOLD'}
$inventory=Get-V3OneTimeReleaseArtifactInventory $PackageRoot
foreach($rel in @('tools/v3-poststop-issuer-release.ps1',
 'tools/v3-post-stop-unknown-quarantine-source-only.ps1',
 'tools/v3-poststop-notebook-reader-extension-INACTIVE.ps1')){
 $inventory[$rel]=Get-V3ReleaseSha256 (Read-V3ReleaseLocalBytes (Join-Path $PackageRoot $rel) 1048576)
}
if($inventory.Count -ne 11){throw 'POSTSTOP_AUTH_ARTIFACT_COUNT_HOLD'}
$attempt=Join-Path (Join-Path $env:LOCALAPPDATA 'V3PostStopAuthority') ('run-'+$ObservationNonce)
if(-not [IO.Directory]::Exists($attempt)){throw 'POSTSTOP_AUTH_PREP_DIRECTORY_HOLD'}
$approvalJson=Join-Path $attempt 'approval.json'
$approvalCms=Join-Path $attempt 'approval.cms'
$pinsJson=Join-Path $attempt 'approved-pins.json'
$terminalNonce=[guid]::NewGuid().ToString('N')
foreach($name in @($approvalJson,$approvalCms,$pinsJson)){
 if([IO.File]::Exists($name)){throw 'POSTSTOP_AUTH_ATTEMPT_REPLAY_HOLD'}
}
$latch=Join-Path $env:LOCALAPPDATA 'V3CasIndependentIssuer\poststop-f27cce0ba68043b480e4f97698dd2901-attempted'
if([IO.File]::Exists($latch)){throw 'POSTSTOP_AUTH_PRIOR_ISSUER_ATTEMPT_NO_RETRY'}
$cloudOpts=@{ObservationNonce=$ObservationNonce;HostDirectory=$OriginalHostDirectory;
 ApprovedPinsJson=$StaticOwnerPolicyJson;ApprovedPinsSha256=$StaticOwnerPolicySha256;MaxWaitSeconds=120}
if($CaFile){$cloudOpts.CaFile=$CaFile}
Write-Output 'NOTEBOOK_WAITING_FOR_SINGLE_ORIGINALHOST_TPM'
$lines=@(& $coordinator @cloudOpts)
if($lines.Count -ne 1){throw 'POSTSTOP_AUTH_COORDINATOR_OUTPUT_HOLD'}
$coord=Read-V3ReleaseJson ([Text.Encoding]::UTF8.GetBytes([string]$lines[0]))
if([string]$coord.kind -cne 'PR710_POSTSTOP_TRIPLE_CMS_SOURCE_ONLY_V1' -or
 [string]$coord.disposition -cne 'PASS_NO_PRODUCTION_EFFECT' -or
 [string]$coord.observation_nonce -cne $ObservationNonce){throw 'POSTSTOP_AUTH_CURRENT_CUSTODY_HOLD'}
$origJson=Join-Path $OriginalHostDirectory 'current-host-original.json'
$origCms=Join-Path $OriginalHostDirectory 'current-host-original.cms'
$hostBytes=[IO.File]::ReadAllBytes($origJson)
$origCmsBytes=[IO.File]::ReadAllBytes($origCms)
$hostSha=Get-V3ReleaseSha256 $hostBytes
# PR723 issuer rejects UNC paths: copy the exact independently verified
# original bytes to new local files without modifying either signed payload.
$issuerHostJson=Join-Path $attempt 'originalhost.json'
$issuerHostCms=Join-Path $attempt 'originalhost.cms'
if([IO.File]::Exists($issuerHostJson) -or [IO.File]::Exists($issuerHostCms)){throw 'POSTSTOP_AUTH_LOCAL_HOST_REPLAY_HOLD'}
function Write-NewExactBytes([string]$Path,[byte[]]$Bytes){
 $f=[IO.FileStream]::new($Path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
 try{$f.Write($Bytes,0,$Bytes.Length);$f.Flush($true)}finally{$f.Dispose()}
}
Write-NewExactBytes $issuerHostJson $hostBytes
Write-NewExactBytes $issuerHostCms $origCmsBytes
if((Get-V3ReleaseSha256 ([IO.File]::ReadAllBytes($issuerHostJson))) -cne $hostSha){throw 'POSTSTOP_AUTH_LOCAL_HOST_HASH_HOLD'}
$readerRoot=Join-Path $env:LOCALAPPDATA 'V3CasAuditActors'
$matches=@(Get-ChildItem -LiteralPath $readerRoot -Directory -Filter 'ReaderCMS-*' -ErrorAction Stop | Where-Object {
 $j=Join-Path $_.FullName 'reader.json'
 if(-not [IO.File]::Exists($j)){return $false}
 try{(Read-V3ReleaseJson (Read-V3ReleaseLocalBytes $j 8192)).observation_nonce -ceq $ObservationNonce}
 catch{return $false}
})
if($matches.Count -ne 2){throw 'POSTSTOP_AUTH_READER_PAIR_COUNT_HOLD'}
$hostReader=$null;$cloudReader=$null
foreach($item in $matches){
 $r=Read-V3ReleaseJson (Read-V3ReleaseLocalBytes (Join-Path $item.FullName 'reader.json') 8192)
 if([string]$r.kind -ceq 'V3_POSTSTOP_CURRENT_INDEPENDENT_HOST_READER_V1'){$hostReader=$item.FullName}
 elseif([string]$r.kind -ceq 'V3_POSTSTOP_CURRENT_INDEPENDENT_CLOUD_READER_V1'){$cloudReader=$item.FullName}
 else{throw 'POSTSTOP_AUTH_READER_KIND_HOLD'}
}
if(-not $hostReader -or -not $cloudReader){throw 'POSTSTOP_AUTH_READER_KIND_COUNT_HOLD'}
$cloudJson=Join-Path $cloudReader 'reader.json'
$cloudSha=Get-V3ReleaseSha256 (Read-V3ReleaseLocalBytes $cloudJson 8192)
if([string]$coord.host_sha256 -cne $hostSha -or [string]$coord.cloud_sha256 -cne $cloudSha){throw 'POSTSTOP_AUTH_COORDINATOR_HASH_HOLD'}
$fields=@('series_id','epoch_id','source_sha256','epoch_fence_sha256','caller_acl_sha256',
 'local_fence_file_sha256','candidates_xml_sha256','wait_xml_sha256','cloudsync_xml_sha256',
 'writer_xml_sha256','host_certificate_sha256','cloud_certificate_sha256','owner_review_sha256','observation_nonce')
$full=[ordered]@{}
foreach($field in $fields){$full[$field]=[string]$p.$field}
$full['host_payload_sha256']=$hostSha
$full['cloud_payload_sha256']=$cloudSha
$utf8=[Text.UTF8Encoding]::new($false)
Write-NewExactBytes $pinsJson $utf8.GetBytes(($full|ConvertTo-Json -Compress))
$pinsHash=Get-V3ReleaseSha256 (Read-V3ReleaseLocalBytes $pinsJson 8192)
$now=[datetimeoffset]::UtcNow
$timestamp="yyyy-MM-dd'T'HH:mm:ss'Z'"
$bindings=[ordered]@{
 epoch_id=$epoch
 source_sha256='8b27c2392c2c8165660a40e15f5ab896c99da39befcd2201e43220acaa2e1251'
 fence_sha256='4f01704d20375bf201f87c56eb350a67c1a91f82535296b28ae318768aa213ef'
 caller_acl_sha256='6f0d59c57f3f7ce3d54f5c674c0d41c342a2a08b9a86001e59353d772f5f66f0'
 pins_sha256=$pinsHash
}
$approval=[ordered]@{
 kind='V3_ONE_TIME_RELEASE_AUTHORIZATION_V1'
 release_id=('V3-ONETIME-'+[guid]::NewGuid().ToString('N'))
 scope='CLOUD_POSTSTOP_TERMINAL_ABORT'
 base_commit='5b1789e349b157d06d3109c5f0ff10d95154bf81'
 release_commit=$release
 not_before_utc=$now.AddSeconds(-3).ToString($timestamp)
 expires_at_utc=$now.AddSeconds(90).ToString($timestamp)
 project_ref='nlgzjmqgwueojlyqmoru'
 computer_name='MINI-PC'
 trading_root='C:\Users\ADMIN\Trading'
 artifacts=$inventory
 bindings=$bindings
}
$approvalBytes=$utf8.GetBytes(($approval|ConvertTo-Json -Compress -Depth 8))
Add-Type -AssemblyName System.Security -ErrorAction Stop
$certs=@(Get-ChildItem Cert:\CurrentUser\My | Where-Object {
 (Get-V3ReleaseSha256 ([byte[]]$_.RawData)) -ceq $authority
})
if($certs.Count -ne 1 -or -not $certs[0].HasPrivateKey){throw 'POSTSTOP_AUTH_INDEPENDENT_SIGNER_UNAVAILABLE'}
$cms=[Security.Cryptography.Pkcs.SignedCms]::new(
 [Security.Cryptography.Pkcs.ContentInfo]::new([byte[]]$approvalBytes),$true)
$signer=[Security.Cryptography.Pkcs.CmsSigner]::new($certs[0])
$signer.DigestAlgorithm=[Security.Cryptography.Oid]::new('2.16.840.1.101.3.4.2.1')
$cms.ComputeSignature($signer)
$signature=[byte[]]$cms.Encode()
Assert-V3ReleaseCms -Payload $approvalBytes -Cms $signature -ReviewedAuthorityCertificateSha256 $authority
Write-NewExactBytes $approvalJson $approvalBytes
Write-NewExactBytes $approvalCms $signature
$common=@{
 PackageRoot=$PackageRoot
 ApprovalJson=$approvalJson
 ApprovalCms=$approvalCms
 AuthorityAdmissionJson=$AuthorityAdmissionJson
 ExpectedAuthorityAdmissionSha256=$AuthorityAdmissionSha256
 ExpectedReleaseCommit=$release
 ApprovedPinsJson=$pinsJson
}
if($CaFile){$common.CaFile=$CaFile}
Write-Output 'POST_STOP_CMS_AUTHORIZED'
Write-Output 'ISSUER_ONCE_START'
try{
 $abort=@(& $issuer -Mode Abort @common -HostJson $issuerHostJson -OriginalHostCms $issuerHostCms `
  -NotebookHostCms (Join-Path $hostReader 'reader.cms') -CloudJson $cloudJson `
  -CloudCms (Join-Path $cloudReader 'reader.cms'))
 if($abort.Count -ne 1){throw 'POSTSTOP_AUTH_DISPATCH_OUTPUT_HOLD'}
 $answer=Read-V3ReleaseJson ([Text.Encoding]::UTF8.GetBytes([string]$abort[0]))
 if([string]$answer.kind -cne 'V3_POSTSTOP_CLOUD_DISPATCH_RESULT_UNCONFIRMED_V1'){throw 'POSTSTOP_AUTH_DISPATCH_RESULT_HOLD'}
}catch{
 if(-not [IO.File]::Exists($latch)){throw}
 Write-Output ('ISSUER_OUTCOME_UNKNOWN_NO_RETRY '+[string]$_.Exception.Message)
}
Write-Output 'INDEPENDENT_TERMINAL_READBACK_START'
$terminal=@(& $reader -PostStopTerminalReader -ObservationNonce $terminalNonce `
 -ReviewedNotebookCertificateSha256 '61d08dd9a925730f213fedc559664dbfe2a3e4f8f1ae77496b385f7d92f3bc55' -CaFile $CaFile)
if($terminal.Count -ne 1){throw 'POSTSTOP_AUTH_TERMINAL_SIGNED_READER_HOLD'}
$t=Read-V3ReleaseJson ([Text.Encoding]::UTF8.GetBytes([string]$terminal[0]))
if([string]$t.kind -cne 'V3_POSTSTOP_TERMINAL_NOTEBOOK_CLOUD_CMS_V1'){throw 'POSTSTOP_AUTH_TERMINAL_READER_KIND_HOLD'}
$verified=@(& $issuer -Mode Readback @common -TerminalJson (Join-Path $t.local_directory 'reader.json') `
 -TerminalCms (Join-Path $t.local_directory 'reader.cms'))
if($verified.Count -ne 1){throw 'POSTSTOP_AUTH_TERMINAL_OUTPUT_HOLD'}
$done=Read-V3ReleaseJson ([Text.Encoding]::UTF8.GetBytes([string]$verified[0]))
if([string]$done.kind -cne 'TARGET_EPOCH_TERMINALIZED' -or
 $done.terminal_cloud_abort_confirmed -ne $true -or $done.stage4_authorized -ne $false -or
 $done.writer_authorized -ne $false){throw 'POSTSTOP_AUTH_FINAL_READER_HOLD'}
Write-Output 'TARGET_EPOCH_TERMINALIZED_INDEPENDENT_READER_PASS'
