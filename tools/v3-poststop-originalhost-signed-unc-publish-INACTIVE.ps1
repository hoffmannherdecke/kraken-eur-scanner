# PR710 manual MINI-PC TPM capture and single atomic signed UNC handoff.
# NO recovery, STOP, Cloud mutation, CAS or writer change.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$ObservationNonce,
 [Parameter(Mandatory=$true)][string]$HostDirectory)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($env:COMPUTERNAME -ine 'MINI-PC' -or $env:GITHUB_ACTIONS -eq 'true' -or
 -not [Environment]::UserInteractive){throw 'PR710_ORIGINALHOST_INTERACTIVE_ONLY_HOLD'}
if($ObservationNonce -cnotmatch '^[a-f0-9]{32}$'){throw 'PR710_ORIGINALHOST_NONCE_HOLD'}
# Same physical location: the Mini-PC writes through its already admitted
# local owner identity; the independent Notebook reads the signed pair via UNC.
# Do not grant the TPM owner a new SMB account/share permission.
$uncRoot='\\192.168.178.179\Mistral_450'
$expectedUnc=$uncRoot+'\PR710-'+$ObservationNonce
$received=[IO.Path]::GetFullPath($HostDirectory).TrimEnd('\')
$share=Get-SmbShare -Name 'Mistral_450' -ErrorAction Stop
if($env:COMPUTERNAME -ine 'MINI-PC' -or
   [IO.Path]::GetFullPath([string]$share.Path).TrimEnd('\') -cne 'D:' -or
   $received -cne $expectedUnc){
 throw 'PR710_ORIGINALHOST_FIXED_SHARE_MAP_HOLD'
}
$root='D:\'
$final=Join-Path $root ('PR710-'+$ObservationNonce)
if([IO.Directory]::Exists($final) -or [IO.File]::Exists($final)){
 throw 'PR710_ORIGINALHOST_DESTINATION_OR_REPLAY_HOLD'
}
# The existing TPM signer explicitly requires local non-network output.
$localRoot=Join-Path $env:LOCALAPPDATA 'V3PostStopOriginalhost'
[void][IO.Directory]::CreateDirectory($localRoot)
$local=Join-Path $localRoot ('PR710-'+$ObservationNonce)
if([IO.Directory]::Exists($local)){throw 'PR710_ORIGINALHOST_LOCAL_REPLAY_HOLD'}
[void][IO.Directory]::CreateDirectory($local)
$json=Join-Path $local 'current-host-original.json'
$cms=Join-Path $local 'current-host-original.cms'
$signArgs=@{
 SignCurrentHost=$true;CaptureCurrentHost=$true
 ObservationNonce=$ObservationNonce;UnsignedPayloadPath=$json
 DetachedCmsOutputPath=$cms
 SignApproval='SIGN_FRESH_ORIGINALHOST_CURRENT_READER_ONLY_NO_RECOVERY'
}
& (Join-Path $PSScriptRoot 'v3-paper-originalhost-manual-tpm-enroll-INACTIVE.ps1') @signArgs | Out-Null
if(-not [IO.File]::Exists($json) -or -not [IO.File]::Exists($cms)){
 throw 'PR710_ORIGINALHOST_SIGNED_PAIR_MISSING_HOLD'
}
Import-Module (Join-Path $PSScriptRoot 'v3-one-time-release-authorization.psm1') -Force
$payload=[IO.File]::ReadAllBytes($json)
$signature=[IO.File]::ReadAllBytes($cms)
Assert-V3ReleaseCms -Payload $payload -Cms $signature -ReviewedAuthorityCertificateSha256 'ce256281af6d36eb883dd2cb34594d0f2231e32a33f58e668d327814c7cfdb40'
$staging=$root+'\PR710-PENDING-'+$ObservationNonce+'-'+[guid]::NewGuid().ToString('N')
[void][IO.Directory]::CreateDirectory($staging)
foreach($row in @(@('current-host-original.json',$payload),@('current-host-original.cms',$signature))){
 $target=Join-Path $staging ([string]$row[0])
 $bytes=[byte[]]$row[1]
 $fs=[IO.FileStream]::new($target,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
 try{$fs.Write($bytes,0,$bytes.Length);$fs.Flush($true)}finally{$fs.Dispose()}
 if((Get-V3ReleaseSha256 ([IO.File]::ReadAllBytes($target))) -cne (Get-V3ReleaseSha256 $bytes)){
  throw 'PR710_ORIGINALHOST_UNC_STAGE_BYTE_DRIFT_HOLD'
 }
}
if([IO.Directory]::Exists($final)){throw 'PR710_ORIGINALHOST_FINAL_REPLAY_HOLD'}
[IO.Directory]::Move($staging,$final)
$finalJsonSha=(Get-FileHash -LiteralPath (Join-Path $final 'current-host-original.json') -Algorithm SHA256).Hash.ToLowerInvariant()
$finalCmsSha=(Get-FileHash -LiteralPath (Join-Path $final 'current-host-original.cms') -Algorithm SHA256).Hash.ToLowerInvariant()
if($finalJsonSha -cne (Get-V3ReleaseSha256 $payload) -or
   $finalCmsSha -cne (Get-V3ReleaseSha256 $signature)){
 throw 'PR710_ORIGINALHOST_FINAL_BYTE_DRIFT_HOLD'
}
[pscustomobject]@{
 kind='PR710_ORIGINALHOST_SIGNED_PAIR_UNC_HANDOFF_V1'
 status='SIGNED_ORIGINAL_BYTES_PUBLISHED_NO_PRODUCTION_EFFECT'
 observation_nonce=$ObservationNonce
 originalhost_payload_sha256=(Get-V3ReleaseSha256 $payload)
 originalhost_cms_sha256=(Get-V3ReleaseSha256 $signature)
 originalhost_unc_directory=$expectedUnc
 recovery_authorized=$false;writer_authorized=$false
}|ConvertTo-Json -Compress
