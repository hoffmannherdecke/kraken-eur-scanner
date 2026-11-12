# PR710 one-shot SOURCE-ONLY Notebook coordination; no scheduler, CAS or writer.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$ObservationNonce,
 [Parameter(Mandatory=$true)][string]$HostDirectory,
 [Parameter(Mandatory=$true)][string]$ApprovedPinsJson,
 [Parameter(Mandatory=$true)][string]$ApprovedPinsSha256,
 [string]$CaFile='', [ValidateRange(1,120)][int]$MaxWaitSeconds=90)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
# Fixed independent static approval first, verified live bytes afterwards.
function Get-V3PostStopVerifiedLivePins([object]$Approved,
 [byte[]]$HostPayload,[byte[]]$OriginalHostCms,[byte[]]$NotebookHostCms,
 [byte[]]$CloudPayload,[byte[]]$CloudCms){
 $fields=@('series_id','epoch_id','source_sha256','epoch_fence_sha256',
 'caller_acl_sha256','local_fence_file_sha256','candidates_xml_sha256',
 'wait_xml_sha256','cloudsync_xml_sha256','writer_xml_sha256',
 'host_certificate_sha256','cloud_certificate_sha256',
 'owner_review_sha256','observation_nonce')
 if($null -eq $Approved -or
    @($Approved.PSObject.Properties.Name).Count -ne $fields.Count -or
    @($Approved.PSObject.Properties.Name | Where-Object {$_ -cnotin $fields}).Count){
  throw 'PR710_POLICY_FIELDS_OR_UNTRUSTED_LIVE_SHA_HOLD'
 }
 foreach($field in $fields | Where-Object {$_ -notin @('series_id','epoch_id','observation_nonce')}){
  if([string]$Approved.$field -cnotmatch '^[a-f0-9]{64}$'){throw 'PR710_POLICY_SHA_HOLD'}
 }
 if([string]$Approved.observation_nonce -cnotmatch '^[a-f0-9]{32}$' -or
    [string]$Approved.host_certificate_sha256 -ceq [string]$Approved.cloud_certificate_sha256){
  throw 'PR710_POLICY_NONCE_OR_SIGNER_HOLD'
 }
 foreach($payload in @($HostPayload,$CloudPayload)){
  if($null -eq $payload -or $payload.Length -lt 400 -or $payload.Length -gt 8192){
   throw 'PR710_LIVE_PAYLOAD_SIZE_HOLD'
  }
 }
 Assert-V3ReleaseCms -Payload $HostPayload -Cms $OriginalHostCms `
  -ReviewedAuthorityCertificateSha256 'ce256281af6d36eb883dd2cb34594d0f2231e32a33f58e668d327814c7cfdb40'
 Assert-V3ReleaseCms -Payload $HostPayload -Cms $NotebookHostCms `
  -ReviewedAuthorityCertificateSha256 $Approved.host_certificate_sha256
 Assert-V3ReleaseCms -Payload $CloudPayload -Cms $CloudCms `
  -ReviewedAuthorityCertificateSha256 $Approved.cloud_certificate_sha256
 $values=[ordered]@{}
 foreach($field in $fields){$values[$field]=[string]$Approved.$field}
 $values['host_payload_sha256']=Get-V3ReleaseSha256 $HostPayload
 $values['cloud_payload_sha256']=Get-V3ReleaseSha256 $CloudPayload
 if($values['host_payload_sha256'] -ceq $values['cloud_payload_sha256']){
  throw 'PR710_LIVE_ORIGINALS_NOT_DISTINCT_HOLD'
 }
 return [pscustomobject]$values
}

if($env:OS -cne 'Windows_NT' -or $env:GITHUB_ACTIONS -eq 'true' -or
 -not [Environment]::UserInteractive){throw 'PR710_WINDOW_INTERACTIVE_NOTEBOOK_ONLY'}
if($ObservationNonce -cnotmatch '^[a-f0-9]{32}$' -or
 $ApprovedPinsSha256 -cnotmatch '^[a-f0-9]{64}$'){throw 'PR710_WINDOW_APPROVAL_HOLD'}
$prefix='\\192.168.178.179\Mistral_450\'
$folder=[IO.Path]::GetFullPath($HostDirectory)
if(-not $folder.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase) -or
 $HostDirectory.Contains('..')){throw 'PR710_WINDOW_UNC_HOLD'}
$pinFile=Get-Item -LiteralPath $ApprovedPinsJson -Force -ErrorAction Stop
if($pinFile.PSIsContainer -or $pinFile.Length -lt 100 -or $pinFile.Length -gt 8192 -or
 [bool]($pinFile.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
 (Get-FileHash -LiteralPath $pinFile.FullName -Algorithm SHA256).Hash.ToLowerInvariant() -cne $ApprovedPinsSha256){
 throw 'PR710_WINDOW_APPROVED_PINS_ORIGINAL_HOLD'
}
$approvedBytes=[IO.File]::ReadAllBytes($pinFile.FullName)
$approvedHash=[Security.Cryptography.SHA256]::Create()
try{$actualApproved=([BitConverter]::ToString($approvedHash.ComputeHash($approvedBytes))).Replace('-','').ToLowerInvariant()}
finally{$approvedHash.Dispose()}
if($actualApproved -cne $ApprovedPinsSha256){throw 'PR710_OWNER_POLICY_FILE_CHANGED_HOLD'}
$approved=([Text.UTF8Encoding]::new($false,$true).GetString($approvedBytes))|ConvertFrom-Json -ErrorAction Stop
if([string]$approved.observation_nonce -cne $ObservationNonce){throw 'PR710_WINDOW_NONCE_MISMATCH'}
$json=Join-Path $folder 'current-host-original.json'
$cms=Join-Path $folder 'current-host-original.cms'
if([IO.File]::Exists($json) -or [IO.File]::Exists($cms)){throw 'PR710_WINDOW_STALE_ORIGINAL_HOLD'}
$until=[datetimeoffset]::UtcNow.AddSeconds($MaxWaitSeconds)
while(-not ([IO.File]::Exists($json) -and [IO.File]::Exists($cms))){
 if([datetimeoffset]::UtcNow -ge $until){throw 'PR710_WINDOW_ORIGINALHOST_TIMEOUT_HOLD'}
 Start-Sleep -Milliseconds 200
}
$reader=Join-Path $PSScriptRoot 'v3-poststop-notebook-reader-extension-INACTIVE.ps1'
$cloudArgs=@{PostStopCloudReader=$true;ObservationNonce=$ObservationNonce;
 ReviewedNotebookCertificateSha256='61d08dd9a925730f213fedc559664dbfe2a3e4f8f1ae77496b385f7d92f3bc55'}
if($CaFile){$cloudArgs.CaFile=$CaFile}
$cloudLines=@(& $reader @cloudArgs)
if($cloudLines.Count -ne 1){throw 'PR710_WINDOW_CLOUD_HOLD'}
$cloud=$cloudLines[0]|ConvertFrom-Json -ErrorAction Stop
if([string]$cloud.kind -cne 'V3_POSTSTOP_NOTEBOOK_CLOUD_CMS_V1' -or
 $cloud.no_production_effect -ne $true){throw 'PR710_WINDOW_CLOUD_OUTPUT_HOLD'}
$hostArgs=@{PostStopHostReader=$true;ObservationNonce=$ObservationNonce;
 OriginalHostDirectory=$folder;
 ReviewedNotebookCertificateSha256='2e3322131208737c58a82c04764bddf4ebe29481c96c79697183710358a2fc57'}
$hostLines=@(& $reader @hostArgs)
if($hostLines.Count -ne 1){throw 'PR710_WINDOW_HOST_HOLD'}
$hostReceipt=$hostLines[0]|ConvertFrom-Json -ErrorAction Stop
if([string]$hostReceipt.kind -cne 'V3_POSTSTOP_NOTEBOOK_HOST_CMS_V1' -or
 $hostReceipt.no_production_effect -ne $true){throw 'PR710_WINDOW_HOST_OUTPUT_HOLD'}
$cloudJson=Join-Path $cloud.local_directory 'reader.json'
Import-Module (Join-Path $PSScriptRoot 'v3-one-time-release-authorization.psm1') -Force
. (Join-Path $PSScriptRoot 'v3-post-stop-unknown-quarantine-source-only.ps1')
$inputs=@{
 HostPayload=[IO.File]::ReadAllBytes($json)
 OriginalHostCms=[IO.File]::ReadAllBytes($cms)
 NotebookHostCms=[IO.File]::ReadAllBytes((Join-Path $hostReceipt.notebook_directory 'reader.cms'))
 CloudPayload=[IO.File]::ReadAllBytes($cloudJson)
 CloudCms=[IO.File]::ReadAllBytes((Join-Path $cloud.local_directory 'reader.cms'))
 Now=[datetimeoffset]::UtcNow
}
$pins=Get-V3PostStopVerifiedLivePins -Approved $approved `
 -HostPayload $inputs.HostPayload -OriginalHostCms $inputs.OriginalHostCms `
 -NotebookHostCms $inputs.NotebookHostCms -CloudPayload $inputs.CloudPayload `
 -CloudCms $inputs.CloudCms
$inputs['Pins']=$pins
$review=Assert-V3PostStopOwnerAdmittedCurrentHostTripleCms @inputs
if([string]$review.kind -cne 'V3_POSTSTOP_TRIPLE_CMS_CRYPTO_SOURCE_REVIEW_V1' -or
 $review.current_custody_contract_verified -ne $true -or
 $review.recovery_authorized -ne $false -or $review.writer_authorized -ne $false){
 throw 'PR710_WINDOW_TRIPLE_CMS_HOLD'
}
[pscustomobject]@{kind='PR710_POSTSTOP_TRIPLE_CMS_SOURCE_ONLY_V1'
 disposition='PASS_NO_PRODUCTION_EFFECT';observation_nonce=$ObservationNonce
 host_sha256=[string]$pins.host_payload_sha256
 cloud_sha256=[string]$pins.cloud_payload_sha256
 recovery_authorized=$false;writer_authorized=$false}|ConvertTo-Json -Compress
