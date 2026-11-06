# Gate-B transport adapter only. The sole mutation owner remains v3-one-time-release.ps1.
# Two interactive shells start before the first short-lived signature.
# No STOP, task toggles, CAS, cloud mutation or independent release authorization here.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][ValidateSet('MiniPc','Notebook')][string]$Role,
 [string]$ShareRoot='',
 [string]$ConfigPath='',
 [string]$ReaderScript='',
 [string]$CaFile='',
 [Parameter(Mandatory=$true)][string]$ReviewedCoordinatorSha256
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$utf8=[Text.UTF8Encoding]::new($false,$true)
$releaseAuthorityCert='2e3322131208737c58a82c04764bddf4ebe29481c96c79697183710358a2fc57'
$releaseId='V3-ONETIME-b90062541c1d4783a70ee814fa44ffed'
$attemptPin='353f51399f5b8c755db0d204570ab0c3d43ecfb542c79866bec86e54dbd05b47'
if($ReviewedCoordinatorSha256 -cnotmatch '^[a-f0-9]{64}$' -or
   (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $ReviewedCoordinatorSha256){
 throw 'GATEB_COORDINATOR_INDEPENDENT_SOURCE_PIN_HOLD'
}
if(-not $ShareRoot){
 $ShareRoot=if($Role -ceq 'MiniPc'){'D:\V3-GateB-PR675'}else{'\\192.168.178.179\Mistral_450\V3-GateB-PR675'}
}
if(-not $ConfigPath){$ConfigPath=Join-Path $ShareRoot 'pr675-dispatch-preparation.json'}

function Read-Json([string]$Path,[int]$Limit=65536) {
 $file=Get-Item -LiteralPath $Path -ErrorAction Stop
 if($file.PSIsContainer -or $file.Length -lt 2 -or $file.Length -gt $Limit){throw 'GATEB_HANDOFF_FILE_SIZE_HOLD'}
 return (ConvertFrom-Json -InputObject ($utf8.GetString([IO.File]::ReadAllBytes($Path))))
}
function Digest([byte[]]$Bytes){
 $h=[Security.Cryptography.SHA256]::Create()
 try {return ([BitConverter]::ToString($h.ComputeHash($Bytes))).Replace('-','').ToLowerInvariant()}
 finally {$h.Dispose()}
}
function Write-Once([string]$Path,[byte[]]$Bytes){
 if(Test-Path -LiteralPath $Path){throw 'GATEB_HANDOFF_NO_OVERWRITE_HOLD'}
 $temporary=$Path+'.pending-'+[guid]::NewGuid().ToString('N')
 $stream=[IO.File]::Open($temporary,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
 try{$stream.Write($Bytes,0,$Bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
 if((Digest ([IO.File]::ReadAllBytes($temporary))) -cne (Digest $Bytes)){throw 'GATEB_HANDOFF_DISK_READBACK_HOLD'}
 [IO.File]::Move($temporary,$Path)
}
function Publish-Json([string]$Path,[object]$Object){
 Write-Once $Path ($utf8.GetBytes(($Object|ConvertTo-Json -Depth 12 -Compress)))
}
function Wait-For([string]$Path,[string]$Directory,[int]$Seconds){
 $deadline=[datetimeoffset]::UtcNow.AddSeconds($Seconds)
 while([datetimeoffset]::UtcNow -lt $deadline){
  if(Test-Path -LiteralPath $Path -PathType Leaf){return}
  if(Test-Path -LiteralPath (Join-Path $Directory 'hold.json') -PathType Leaf){
   throw 'GATEB_REMOTE_HOLD_NO_RETRY'
  }
  Start-Sleep -Milliseconds 400
 }
 throw 'GATEB_HANDOFF_WINDOW_TIMEOUT_NO_RETRY'
}
function Check-Cms([byte[]]$Payload,[byte[]]$Signature,[string]$Pin){
 Add-Type -AssemblyName System.Security -ErrorAction Stop
 $signed=[Security.Cryptography.Pkcs.SignedCms]::new(
  [Security.Cryptography.Pkcs.ContentInfo]::new($Payload),$true)
 $signed.Decode($Signature)
 if(-not $signed.Detached -or $signed.SignerInfos.Count -ne 1){throw 'GATEB_HANDOFF_CMS_STRUCTURE_HOLD'}
 $signer=$signed.SignerInfos[0]
 if($null -eq $signer.Certificate -or [string]$signer.DigestAlgorithm.Value -cne '2.16.840.1.101.3.4.2.1' -or
    (Digest $signer.Certificate.RawData) -cne $Pin){throw 'GATEB_HANDOFF_SIGNER_HOLD'}
 $signed.CheckSignature($true)
}
function Check-Terminal([byte[]]$Payload,[byte[]]$Signature,[object]$Bindings,[datetimeoffset]$After){
 Check-Cms $Payload $Signature ([string]$Bindings.reader_certificate_sha256)
 $text=$utf8.GetString($Payload)
 $row=ConvertFrom-Json -InputObject $text
 if([string]$row.kind -cne 'V3_CAS_PREPARED_FENCE_ABORT_READER_RECEIPT_V1' -or
    [string]$row.epoch_id -cne [string]$Bindings.epoch_id -or
    [string]$row.source_sha256 -cne [string]$Bindings.source_sha256 -or
    [string]$row.prepared_fence_sha256 -cne [string]$Bindings.fence_sha256 -or
    [string]$row.caller_acl_sha256 -cne [string]$Bindings.caller_acl_sha256 -or
    [string]$row.state -cne 'ABORT_RECORDED_NOT_RELEASED' -or
    [int]$row.cloud_active_series_count -ne 1 -or
    [int]$row.cloud_original_active_series_count -ne 1 -or
    [int]$row.cloud_cas_rpc_count -ne 0 -or $row.cloud_executor_can_login -ne $false){
  throw 'GATEB_HANDOFF_READER_IDENTITY_HOLD'
 }
 $observed=[datetimeoffset]::Parse([string]$row.observed_at_utc,[Globalization.CultureInfo]::InvariantCulture)
 $age=([datetimeoffset]::UtcNow-$observed).TotalSeconds
 if($observed -le $After -or $age -lt -5 -or $age -gt 60){throw 'GATEB_HANDOFF_READER_STALE_HOLD'}
}
function Capture-NotebookReader([object]$Bindings,[datetimeoffset]$After){
 if(-not (Test-Path -LiteralPath $ReaderScript -PathType Leaf) -or
    -not(Test-Path -LiteralPath $CaFile -PathType Leaf)){throw 'GATEB_NOTEBOOK_READER_OR_CA_MISSING'}
 $out=@(& "$PSHOME\powershell.exe" -NoProfile -ExecutionPolicy RemoteSigned -File $ReaderScript -PreparedAbortSignedCurrent -ReviewedNotebookCertificateSha256 ([string]$Bindings.reader_certificate_sha256) -CaFile $CaFile)
 if($LASTEXITCODE -ne 0){throw 'GATEB_NOTEBOOK_READER_FAILED'}
 $receipts=@($out|Where-Object {$_ -is [string] -and $_ -match '"kind":"V3_NOTEBOOK_PREPARED_ABORT_CMS_TRANSFER_V1"'})
 if($receipts.Count -ne 1){throw 'GATEB_NOTEBOOK_READER_RECEIPT_HOLD'}
 $receipt=ConvertFrom-Json -InputObject $receipts[0]
 if([string]$receipt.status -cne 'SIGNED_CURRENT_ABORT_ROW_NOT_RUNTIME_RELEASE'){throw 'GATEB_NOTEBOOK_READER_NOT_SUCCESS'}
 $raw=[IO.File]::ReadAllBytes((Join-Path $receipt.local_directory 'reader.json'))
 $sig=[IO.File]::ReadAllBytes((Join-Path $receipt.local_directory 'reader.cms'))
 Check-Terminal $raw $sig $Bindings $After
 return [pscustomobject]@{Json=$raw;Cms=$sig}
}
function Find-Signer([string]$Pin) {
 $matches=@(Get-ChildItem Cert:\CurrentUser\My|Where-Object {$_.HasPrivateKey -and (Digest $_.RawData) -ceq $Pin -and $_.NotBefore -le (Get-Date) -and $_.NotAfter -gt (Get-Date)})
 if($matches.Count -ne 1){throw 'GATEB_NOTEBOOK_AUTHORITY_KEY_HOLD'}
 return $matches[0]
}
function Sign-Approval([object]$Template,[object]$Cert){
 $now=[datetimeoffset]::UtcNow
 $Template.not_before_utc=$now.AddSeconds(-5).ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
 $Template.expires_at_utc=$now.AddMinutes(12).ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
 $bytes=$utf8.GetBytes(($Template|ConvertTo-Json -Depth 30 -Compress))
 Add-Type -AssemblyName System.Security -ErrorAction Stop
 $cms=[Security.Cryptography.Pkcs.SignedCms]::new([Security.Cryptography.Pkcs.ContentInfo]::new($bytes),$true)
 $signer=[Security.Cryptography.Pkcs.CmsSigner]::new($Cert)
 $signer.DigestAlgorithm=[Security.Cryptography.Oid]::new('2.16.840.1.101.3.4.2.1')
 $cms.ComputeSignature($signer)
 $sig=[byte[]]$cms.Encode()
 Check-Cms $bytes $sig $releaseAuthorityCert
 return [pscustomobject]@{Json=$bytes;Cms=$sig}
}
function Assert-Activation([object]$Value,[object]$Template){
 if([string]$Value.kind -cne 'V3_GATEB_COORDINATED_ACTIVATION_V1' -or
    [string]$Value.release_id -cne $releaseId -or
    [string]$Value.release_commit -cne [string]$Template.release_commit -or
    [string]$Value.attempt_sha256 -cne $attemptPin -or
    [string]$Value.nonce -cnotmatch '^[a-f0-9]{32}$'){
  throw 'GATEB_ACTIVATION_IDENTITY_HOLD'
 }
 $age=([datetimeoffset]::UtcNow-[datetimeoffset]::Parse([string]$Value.created_at_utc)).TotalSeconds
 if($age -lt -5 -or $age -gt 600){throw 'GATEB_ACTIVATION_STALE_HOLD'}
}
$config=Read-Json $ConfigPath
$commit=[string]$config.release_commit
if($commit -cnotmatch '^[a-f0-9]{40}$' -or
   [string]$config.release_id -cne $releaseId -or [string]$config.mode -cne 'OriginalhostReconcile'){
 throw 'GATEB_DISPATCH_IDENTITY_HOLD'
}
# A repaired release has NEW signed bytes: keep the prior unsigned template
# immutable and allow a new leaf in a separately reviewed release config.
$templateLeaf='pr675-approval-unsigned-template.json'
if('approval_template_leaf' -cin @($config.PSObject.Properties.Name)){
 $templateLeaf=[string]$config.approval_template_leaf
}
if($templateLeaf -cnotmatch '^pr67[0-9]-approval-unsigned-template[.]json$'){
 throw 'GATEB_TEMPLATE_LEAF_SCOPE_HOLD'
}
$templateFile=Join-Path $ShareRoot $templateLeaf

if($Role -ceq 'MiniPc'){
 if($env:COMPUTERNAME -cne 'MINI-PC' -or -not [Environment]::UserInteractive){throw 'GATEB_ORIGINALHOST_INTERACTIVE_REQUIRED'}
 $principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
 if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'GATEB_ORIGINALHOST_ADMIN_REQUIRED'}
 if($ShareRoot -cne 'D:\V3-GateB-PR675'){throw 'GATEB_MINIPC_SHARE_SCOPE_HOLD'}
 $share=Get-SmbShare -Name 'Mistral_450' -ErrorAction Stop
 if([string]$share.Path.TrimEnd('\') -cne 'D:'){throw 'GATEB_MINIPC_SHARE_TARGET_HOLD'}
 $package=[string]$config.package_root
 $operator=Join-Path $package 'tools\v3-one-time-release.ps1'
 foreach($p in @($operator,[string]$config.admission,[string]$config.historical_approval,
  [string]$config.historical_cms,[string]$config.reconciliation_evidence,
  [string]$config.install_readback,'D:\V3-Cloud-Release\GateB-PR674-Window1\approval.json',
  'D:\V3-Cloud-Release\GateB-PR674-Window1\approval.cms')){
  if(-not(Test-Path -LiteralPath $p -PathType Leaf)){throw 'GATEB_REQUIRED_ORIGINAL_PATH_MISSING'}
 }
 if(-not(Test-Path -LiteralPath ([string]$config.backup_directory) -PathType Container)){throw 'GATEB_ORIGINAL_BACKUP_MISSING'}
 $template=Read-Json $templateFile
 if([string]$template.release_commit -cne $commit -or
    [string]$template.bindings.pre_archive_attempt_sha256 -cne $attemptPin){
  throw 'GATEB_UNSIGNED_TEMPLATE_WRONG_RELEASE_HOLD'
 }
 # Time-independent authority, local inventory and original-attempt gates must
 # finish BEFORE Notebook produces any short-lived certificate or Reader row.
 $authModule=Join-Path $package 'tools\v3-one-time-release-authorization.psm1'
 Import-Module $authModule -Force
 $authority=Assert-V3ReleaseAuthorityAdmission -Bytes ([IO.File]::ReadAllBytes([string]$config.admission)) -ExpectedSha256 ([string]$config.admission_sha256) -ReleaseCommit $commit
 if([string]$authority -cne $releaseAuthorityCert){throw 'GATEB_PRE_SIGN_AUTHORITY_PIN_HOLD'}
 $inventory=Get-V3OneTimeReleaseArtifactInventory -PackageRoot $package
 if(@($template.artifacts.PSObject.Properties).Count -ne $inventory.Count){throw 'GATEB_PRE_SIGN_ARTIFACT_SET_HOLD'}
 foreach($name in $inventory.Keys){
  if([string]$template.artifacts.$name -cne [string]$inventory[$name]){
   throw 'GATEB_PRE_SIGN_RELEASE_ARTIFACT_PIN_HOLD'
  }
 }
 $original='C:\Users\ADMIN\Trading\State\v3-one-time-'+$releaseId+'.json'
 if(-not(Test-Path -LiteralPath ($original+'.reconciliation-attempt.json') -PathType Leaf) -or
    (Get-FileHash -LiteralPath ($original+'.reconciliation-attempt.json') -Algorithm SHA256).Hash.ToLowerInvariant() -cne $attemptPin -or
    (Test-Path -LiteralPath ($original+'.completed.json')) -or
    (Test-Path -LiteralPath ($original+'.awaiting-post-archive-reader.json'))){
  throw 'GATEB_PRE_SIGN_ORIGINAL_ATTEMPT_STATE_HOLD'
 }
 $fence='C:\Users\ADMIN\Trading\State\v3-experimental-paper-old-intake-fence.json'
 if(-not(Test-Path -LiteralPath $fence -PathType Leaf)){
  throw 'GATEB_PRE_SIGN_ARMED_FENCE_MISSING_HOLD'
 }
 # Prepare all original inputs before allowing a Notebook signer to begin.
 $nonce=[guid]::NewGuid().ToString('N')
 $session=Join-Path $ShareRoot ('coordinated-'+$nonce)
 [IO.Directory]::CreateDirectory($session)|Out-Null
 $activation=Join-Path $ShareRoot 'coordinated-active.json'
 Publish-Json $activation ([ordered]@{
  kind='V3_GATEB_COORDINATED_ACTIVATION_V1';release_id=$releaseId
  release_commit=$commit;attempt_sha256=$attemptPin;nonce=$nonce
  created_at_utc=[datetimeoffset]::UtcNow.ToString('o')
 })
 Write-Host 'PR675_COORDINATED_MINIPC_DISPATCH_ARMED_NO_MUTATION'
 try{
  $firstPath=Join-Path $session 'first-envelope.json'
  Wait-For $firstPath $session 600
  $first=Read-Json $firstPath
  if([string]$first.kind -cne 'V3_GATEB_COORDINATED_FIRST_ENVELOPE_V1' -or
     [string]$first.nonce -cne $nonce -or [string]$first.release_id -cne $releaseId -or
     [string]$first.release_commit -cne $commit -or [string]$first.attempt_sha256 -cne $attemptPin){
   throw 'GATEB_FIRST_ENVELOPE_IDENTITY_HOLD'
  }
  try{
   $a=[Convert]::FromBase64String([string]$first.approval_json_base64)
   $ac=[Convert]::FromBase64String([string]$first.approval_cms_base64)
   $t=[Convert]::FromBase64String([string]$first.reader_json_base64)
   $tc=[Convert]::FromBase64String([string]$first.reader_cms_base64)
  }catch{throw 'GATEB_FIRST_ENVELOPE_ENCODING_HOLD'}
  $approval=ConvertFrom-Json -InputObject ($utf8.GetString($a))
  if([string]$approval.release_commit -cne $commit -or [string]$approval.release_id -cne $releaseId -or
     [string]$approval.bindings.pre_archive_attempt_sha256 -cne $attemptPin -or
     ([datetimeoffset]::Parse([string]$approval.expires_at_utc)-[datetimeoffset]::UtcNow).TotalMinutes -lt 3){
   throw 'GATEB_FIRST_APPROVAL_IDENTITY_OR_EXPIRY_HOLD'
  }
  Check-Cms $a $ac $releaseAuthorityCert
  Check-Terminal $t $tc $approval.bindings ([datetimeoffset]::MinValue)
  # The existing Originalhost release contract accepts direct Trading-root
  # terminal proofs; use unique immutable names, never a mutable shared pair.
  $localDir='C:\Users\ADMIN\Trading'
  $ap=Join-Path $localDir ('pr676-'+$nonce+'-approval.json')
  $acp=Join-Path $localDir ('pr676-'+$nonce+'-approval.cms')
  $tp=Join-Path $localDir ('pr676-'+$nonce+'-terminal.json')
  $tcp=Join-Path $localDir ('pr676-'+$nonce+'-terminal.cms')
  Write-Once $ap $a;Write-Once $acp $ac;Write-Once $tp $t;Write-Once $tcp $tc
  $params=@{
   Mode='OriginalhostReconcile';PackageRoot=$package;ExpectedReleaseCommit=$commit
   AuthorityAdmissionJson=[string]$config.admission
   ExpectedAuthorityAdmissionSha256=[string]$config.admission_sha256
   ApprovalJson=$ap;ApprovalCms=$acp
   ExistingApprovalJson=[string]$config.historical_approval
   ExistingApprovalCms=[string]$config.historical_cms
   ReconciliationEvidenceJson=[string]$config.reconciliation_evidence
   InterruptedApprovalJson='D:\V3-Cloud-Release\GateB-PR674-Window1\approval.json'
   InterruptedApprovalCms='D:\V3-Cloud-Release\GateB-PR674-Window1\approval.cms'
   InstallReadbackJson=[string]$config.install_readback
   BackupDirectory=[string]$config.backup_directory
   TerminalAbortJson=$tp;TerminalAbortCms=$tcp
   CoordinatedPostArchiveRequestPath=(Join-Path $session 'post-request.json')
   CoordinatedPostArchiveEnvelopePath=(Join-Path $session 'post-envelope.json')
   CoordinatedHandoffNonce=$nonce
  }
  Write-Host 'PR675_COORDINATED_FRESH_FIRST_READER_DISPATCH'
  # Existing operator retains sole ownership of safety checks and mutations.
  $wire=@(& $operator @params)
  $valid=@($wire|Where-Object {$_ -is [string] -and $_ -match 'TERMINAL_ABORT_PARTIAL_ATTEMPT_RECONCILED_AFTERCARE_CONFIRMED'})
  if($valid.Count -ne 1){throw 'GATEB_ORIGINAL_OPERATOR_RESULT_UNKNOWN_NO_RETRY'}
  $receiptPath='C:\Users\ADMIN\Trading\State\v3-one-time-'+$releaseId+'.json.completed.json'
  $receipt=Read-Json $receiptPath
  if([string]$receipt.kind -cne 'V3_ONE_TIME_ORIGINALHOST_RECONCILIATION_RECEIPT_V1' -or
     [string]$receipt.status -cne 'TERMINAL_ABORT_PARTIAL_ATTEMPT_RECONCILED_AFTERCARE_CONFIRMED' -or
     [string]$receipt.release_id -cne $releaseId -or
     [string]$receipt.release_commit -cne $commit -or
     $receipt.successful_stop_claimed -ne $false -or
     $receipt.cas_or_paper_authorized -ne $false){
   throw 'GATEB_ORIGINAL_COMPLETION_RECEIPT_HOLD'
  }
  Publish-Json (Join-Path $session 'completion.json') ([ordered]@{
   kind='V3_GATEB_COORDINATED_COMPLETION_WITNESS_V1';nonce=$nonce;release_id=$releaseId
   release_commit=$commit;original_receipt_sha256=(Digest ([IO.File]::ReadAllBytes($receiptPath)))
   status=[string]$receipt.status;successful_stop_claimed=$false;cas_or_paper_authorized=$false
  })
  Write-Host 'PR675_ORIGINALHOST_GATE_B_COMPLETED_ORIGINAL_RECEIPT_PASS'
 }catch{
  $reason=$_.Exception.Message
  try{Publish-Json (Join-Path $session 'hold.json') ([ordered]@{kind='V3_GATEB_COORDINATED_HOLD_V1';reason=$reason;no_retry=$true})}catch{}
  throw
 }
}else{
 if($env:COMPUTERNAME -ceq 'MINI-PC' -or -not [Environment]::UserInteractive){throw 'GATEB_INDEPENDENT_NOTEBOOK_REQUIRED'}
 if($ShareRoot -cne '\\192.168.178.179\Mistral_450\V3-GateB-PR675'){throw 'GATEB_NOTEBOOK_SHARE_SCOPE_HOLD'}
 if(-not $ReaderScript){$ReaderScript='C:\Users\burns\Documents\V3-GateA-PR670-INACTIVE\tools\v3-notebook-cas-audit-original-readonly-witness-INACTIVE.ps1'}
 if(-not $CaFile){$CaFile='C:\Users\burns\Downloads\prod-ca-2021.crt'}
 $template=Read-Json $templateFile
 if([string]$template.release_commit -cne $commit -or [string]$template.release_id -cne $releaseId -or
    [string]$template.bindings.pre_archive_attempt_sha256 -cne $attemptPin){throw 'GATEB_NOTEBOOK_TEMPLATE_IDENTITY_HOLD'}
 # Existing independently pinned Reader source is checked before a short-lived
 # CMS is signed. A different Notebook source cannot silently replace it.
 if(-not(Test-Path -LiteralPath $ReaderScript -PathType Leaf) -or
    (Get-FileHash -LiteralPath $ReaderScript -Algorithm SHA256).Hash.ToLowerInvariant() -cne [string]$template.bindings.reader_source_sha256){
  throw 'GATEB_NOTEBOOK_READER_SOURCE_PIN_HOLD'
 }
 $cert=Find-Signer $releaseAuthorityCert
 $activationPath=Join-Path $ShareRoot 'coordinated-active.json'
 Write-Host 'PR675_COORDINATED_NOTEBOOK_WAITING_FOR_MINIPC_READY'
 Wait-For $activationPath $ShareRoot 600
 $activation=Read-Json $activationPath
 Assert-Activation $activation $template
 $nonce=[string]$activation.nonce
 $session=Join-Path $ShareRoot ('coordinated-'+$nonce)
 # No short-lived output exists before MiniPc preflight has completed.
 $approval=Sign-Approval $template $cert
 $first=Capture-NotebookReader $template.bindings ([datetimeoffset]::MinValue)
 Publish-Json (Join-Path $session 'first-envelope.json') ([ordered]@{
  kind='V3_GATEB_COORDINATED_FIRST_ENVELOPE_V1';nonce=$nonce;release_id=$releaseId
  release_commit=$commit;attempt_sha256=$attemptPin
  approval_json_base64=[Convert]::ToBase64String($approval.Json)
  approval_cms_base64=[Convert]::ToBase64String($approval.Cms)
  reader_json_base64=[Convert]::ToBase64String($first.Json)
  reader_cms_base64=[Convert]::ToBase64String($first.Cms)
 })
 Write-Host 'PR675_FIRST_READER_ATOMIC_TRANSFER_COMPLETE'
 $requestPath=Join-Path $session 'post-request.json'
 Wait-For $requestPath $session 900
 $requestBytes=[IO.File]::ReadAllBytes($requestPath)
 $request=Read-Json $requestPath
 if([string]$request.kind -cne 'V3_GATEB_COORDINATED_POST_ARCHIVE_REQUEST_V1' -or
    [string]$request.nonce -cne $nonce -or
    [string]$request.release_id -cne $releaseId -or
    [string]$request.release_commit -cne $commit -or
    [string]$request.epoch_id -cne [string]$template.bindings.epoch_id -or
    [string]$request.attempt_sha256 -cne $attemptPin -or
    [string]$request.approval_sha256 -cne (Digest $approval.Json) -or
    [string]$request.receipt_sha256 -cnotmatch '^[a-f0-9]{64}$'){
  throw 'GATEB_POST_ARCHIVE_REQUEST_IDENTITY_HOLD'
 }
 $archivedAt=[datetimeoffset]::Parse([string]$request.archive_observed_by_utc)
 if($archivedAt -gt [datetimeoffset]::UtcNow){throw 'GATEB_POST_ARCHIVE_REQUEST_FUTURE_HOLD'}
 $second=Capture-NotebookReader $template.bindings $archivedAt
 Publish-Json (Join-Path $session 'post-envelope.json') ([ordered]@{
  kind='V3_GATEB_COORDINATED_POST_ARCHIVE_ENVELOPE_V1';nonce=$nonce
  release_id=$releaseId;release_commit=$commit;epoch_id=[string]$template.bindings.epoch_id
  request_sha256=(Digest $requestBytes)
  reader_json_base64=[Convert]::ToBase64String($second.Json)
  reader_cms_base64=[Convert]::ToBase64String($second.Cms)
 })
 Write-Host 'PR675_SECOND_INDEPENDENT_READER_ATOMIC_TRANSFER_COMPLETE'
 $completionPath=Join-Path $session 'completion.json'
 Wait-For $completionPath $session 120
 $completion=Read-Json $completionPath
 if([string]$completion.kind -cne 'V3_GATEB_COORDINATED_COMPLETION_WITNESS_V1' -or
    [string]$completion.nonce -cne $nonce -or
    [string]$completion.release_id -cne $releaseId -or
    [string]$completion.release_commit -cne $commit -or
    [string]$completion.status -cne 'TERMINAL_ABORT_PARTIAL_ATTEMPT_RECONCILED_AFTERCARE_CONFIRMED' -or
    $completion.successful_stop_claimed -ne $false -or $completion.cas_or_paper_authorized -ne $false){
  throw 'GATEB_NOTEBOOK_COMPLETION_WITNESS_HOLD'
 }
 Write-Host 'PR675_NOTEBOOK_INDEPENDENT_READER_HANDOFF_AND_HOST_COMPLETION_WITNESSED'
}
