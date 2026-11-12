# PR710 one-shot SOURCE-ONLY Notebook coordination; no scheduler, CAS or writer.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$ObservationNonce,
 [Parameter(Mandatory=$true)][string]$HostDirectory,
 [Parameter(Mandatory=$true)][string]$ApprovedPinsJson,
 [Parameter(Mandatory=$true)][string]$ApprovedPinsSha256,
 [string]$CaFile='', [ValidateRange(1,120)][int]$MaxWaitSeconds=90)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
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
if($LASTEXITCODE -ne 0 -or $cloudLines.Count -ne 1){throw 'PR710_WINDOW_CLOUD_HOLD'}
$cloud=$cloudLines[0]|ConvertFrom-Json -ErrorAction Stop
if([string]$cloud.kind -cne 'V3_POSTSTOP_NOTEBOOK_CLOUD_CMS_V1' -or
 $cloud.no_production_effect -ne $true){throw 'PR710_WINDOW_CLOUD_OUTPUT_HOLD'}
$hostArgs=@{PostStopHostReader=$true;ObservationNonce=$ObservationNonce;
 OriginalHostDirectory=$folder;
 ReviewedNotebookCertificateSha256='2e3322131208737c58a82c04764bddf4ebe29481c96c79697183710358a2fc57'}
$hostLines=@(& $reader @hostArgs)
if($LASTEXITCODE -ne 0 -or $hostLines.Count -ne 1){throw 'PR710_WINDOW_HOST_HOLD'}
$host=$hostLines[0]|ConvertFrom-Json -ErrorAction Stop
if([string]$host.kind -cne 'V3_POSTSTOP_NOTEBOOK_HOST_CMS_V1' -or
 $host.no_production_effect -ne $true){throw 'PR710_WINDOW_HOST_OUTPUT_HOLD'}
$cloudJson=Join-Path $cloud.local_directory 'reader.json'
if((Get-FileHash -LiteralPath $json -Algorithm SHA256).Hash.ToLowerInvariant() -cne
 [string]$pins.host_payload_sha256 -or
 (Get-FileHash -LiteralPath $cloudJson -Algorithm SHA256).Hash.ToLowerInvariant() -cne
 [string]$pins.cloud_payload_sha256){throw 'PR710_WINDOW_SOURCE_BYTE_PIN_HOLD'}
Import-Module (Join-Path $PSScriptRoot 'v3-one-time-release-authorization.psm1') -Force
. (Join-Path $PSScriptRoot 'v3-post-stop-unknown-quarantine-source-only.ps1')
$inputs=@{
 HostPayload=[IO.File]::ReadAllBytes($json)
 OriginalHostCms=[IO.File]::ReadAllBytes($cms)
 NotebookHostCms=[IO.File]::ReadAllBytes((Join-Path $host.notebook_directory 'reader.cms'))
 CloudPayload=[IO.File]::ReadAllBytes($cloudJson)
 CloudCms=[IO.File]::ReadAllBytes((Join-Path $cloud.local_directory 'reader.cms'))
 Pins=$pins;Now=[datetimeoffset]::UtcNow
}
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
