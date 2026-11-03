# One-shot originalhost native custody observation for existing PR515/#99.
# READ ONLY. Never a second CAS/operator/release authority.
[CmdletBinding()]
param([string]$TradingRoot='C:\Users\ADMIN\Trading',
      [Parameter(Mandatory=$true)][string]$ExpectedCandidateRepoSha,
      [string]$NotebookReaderJson='',
      [string]$NotebookReaderCms='',
      [string]$ReviewedNotebookCertificateSha256='')
$ErrorActionPreference='Stop'
if([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT){
 throw 'V3_ORIGINALHOST_WINDOWS_ONLY'
}
$root=[IO.Path]::GetFullPath($TradingRoot).TrimEnd('\')
if(-not $root.Equals('C:\Users\ADMIN\Trading',[StringComparison]::OrdinalIgnoreCase) -or
   $ExpectedCandidateRepoSha -cnotmatch '^[a-f0-9]{40}$'){
 throw 'V3_ORIGINALHOST_ROOT_OR_SOURCE_PIN_INVALID'
}
$names=@('CryptoMiniPC-V2R4PaperCandidates',
 'CryptoMiniPC-V2R4PaperWait',
 'CryptoMiniPC-V2R4PaperLifecycle',
 'CryptoMiniPC-V2R4PaperCloudSync')
$now=[datetimeoffset]::UtcNow
$tasks=@()
foreach($name in $names){
 $task=Get-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction Stop
 $tasks+=@([pscustomobject][ordered]@{
  name=$name
  state=[string]$task.State
  action_count=@($task.Actions).Count
  principal_is_system=([string]$task.Principal.UserId -in @(
    'SYSTEM','NT AUTHORITY\SYSTEM','S-1-5-18'))
 })
}
$v3=Get-ScheduledTask -TaskName 'CryptoMiniPC-V3PaperSingleWriter' -TaskPath '\' -ErrorAction Stop
$fence=Join-Path $root 'State\v3-experimental-paper-old-intake-fence.json'
$maintenance=Join-Path $root 'State\v2r4-technical-cutover-maintenance.json'
$marker='ABSENT'
$fenceHash=''
if(Test-Path -LiteralPath $fence){
 $item=Get-Item -LiteralPath $fence -Force -ErrorAction Stop
 if($item.PSIsContainer -or
    [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
    $item.Length -lt 100 -or $item.Length -gt 8192){
  throw 'V3_MARKER_UNSAFE_FILE'
 }
 $data=Get-Content -LiteralPath $fence -Raw -ErrorAction Stop|ConvertFrom-Json
 if([string]$data.kind -cne 'V3_EXPERIMENTAL_OLD_INTAKE_FENCE_V1' -or
    [string]$data.phase -cne 'ARMED'){
  throw 'V3_MARKER_NOT_PRESTOP_ARMED'
 }
 $marker='ARMED'
 $fenceHash=(Get-FileHash -LiteralPath $fence -Algorithm SHA256).Hash.ToLowerInvariant()
}
$processes=@(Get-CimInstance Win32_Process -ErrorAction Stop)
$old=@($processes|Where-Object {
 [string]$_.Name -match '^(?i:pythonw?\.exe)$' -and
 [string]$_.CommandLine -match '(?i)v2r4|wait_launcher'
}|ForEach-Object {
 [pscustomobject][ordered]@{
  pid=[int]$_.ProcessId
  ppid=[int]$_.ParentProcessId
  created_utc=$(if($_.CreationDate){([datetimeoffset]$_.CreationDate).ToUniversalTime().ToString('o')}else{''})
 }
})
# Optional bounded cross-source join: signed CURRENT private cloud T0 wire
# and originalhost native snapshot are observed in one read-only invocation.
# A valid CMS is NOT issuer authorization, continuous UNKNOWN custody or a
# release. Do not promote cryptographic validity to a native effectful gate.
$signedCurrentMatch=$false
$notebookCloudTimeMatched=$false
if($NotebookReaderJson -or $NotebookReaderCms -or $ReviewedNotebookCertificateSha256){
 if(-not $NotebookReaderJson -or -not $NotebookReaderCms -or
    $ReviewedNotebookCertificateSha256 -cnotmatch '^[a-f0-9]{64}$'){
  throw 'V3_T0_SIGNED_PAIR_AND_EXTERNAL_CERT_PIN_REQUIRED'
 }
 $pair=@($NotebookReaderJson,$NotebookReaderCms)
 $bytes=@()
 foreach($p in $pair){
  $full=[IO.Path]::GetFullPath($p)
  if(-not $full.StartsWith('D:\',[StringComparison]::OrdinalIgnoreCase)){
   throw 'V3_T0_PAIR_MUST_USE_EXISTING_MISTRAL_SHARE'
  }
  $item=Get-Item -LiteralPath $full -Force -ErrorAction Stop
  if($item.PSIsContainer -or
     [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
     $item.Length -lt 32 -or $item.Length -gt 32768){
   throw 'V3_T0_PAIR_UNSAFE_FILE'
  }
  $bytes+=,@([IO.File]::ReadAllBytes($full))
 }
 if([IO.Path]::GetFileName($pair[0]) -cne 'reader.json' -or
    [IO.Path]::GetFileName($pair[1]) -cne 'reader.cms' -or
    [IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($pair[0])) -cne
    [IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($pair[1]))){
  throw 'V3_T0_PAIR_NOT_SAME_DIRECTORY'
 }
 try {
  $payload=[byte[]]$bytes[0]
  $cms=[byte[]]$bytes[1]
  $signed=[System.Security.Cryptography.Pkcs.SignedCms]::new(
   [System.Security.Cryptography.Pkcs.ContentInfo]::new($payload),$true)
  $signed.Decode($cms)
  if(-not $signed.Detached -or $signed.SignerInfos.Count -ne 1 -or
     [string]$signed.SignerInfos[0].DigestAlgorithm.Value -cne
     '2.16.840.1.101.3.4.2.1'){throw 'V3_T0_BAD_SIGNATURE_FORMAT'}
  $cert=$signed.SignerInfos[0].Certificate
  if($null -eq $cert -or $cert.NotBefore.ToUniversalTime() -gt [datetime]::UtcNow -or
     $cert.NotAfter.ToUniversalTime() -lt [datetime]::UtcNow){
   throw 'V3_T0_CERT_INVALID'
  }
  $hasher=[Security.Cryptography.SHA256]::Create()
  try {
   $digest=([BitConverter]::ToString($hasher.ComputeHash(
    [byte[]]$cert.RawData))).Replace('-','').ToLowerInvariant()
  } finally {$hasher.Dispose()}
  if($digest -cne $ReviewedNotebookCertificateSha256){throw 'V3_T0_CERT_PIN_MISMATCH'}
  $signed.CheckSignature($true)
  $wire=([Text.UTF8Encoding]::new($false,$true)).GetString($payload)
  $obj=$wire|ConvertFrom-Json -ErrorAction Stop
  $fields=@('kind','observed_at_utc','actor','requested_role',
   'active_series_count','original_active_series_count','epoch_count',
   'intent_count','attempt_count','dispatch_unknown_count','inhibit_count',
   'cas_rpc_count','executor_can_login','history_never_proven',
   'complete_attempt_unknown_custody_authenticated','t0_authenticated',
   'armed_marker_cancel_authorized','native_stop_restore_authorized',
   'cas_or_v3_paper_authorized')
  $actual=@($obj.PSObject.Properties.Name)
  if($actual.Count -ne $fields.Count -or
     @($actual|Where-Object {$_ -cnotin $fields}).Count -ne 0){
   throw 'V3_T0_UNEXPECTED_CATALOG_FIELDS'
  }
  foreach($field in $fields){
   if(@([regex]::Matches($wire,('"'+[regex]::Escape($field)+'"\s*:'))).Count -ne 1){
    throw 'V3_T0_DUPLICATE_FIELD'
   }
  }
  if([string]$obj.kind -cne 'V3_CAS_FORWARD_T0_CURRENT_CATALOG_READONLY_V1' -or
     [string]$obj.actor -cne 'v3_cas_audit_reader_actor' -or
     [string]$obj.requested_role -cne 'v3_cas_audit_reader'){
   throw 'V3_T0_UNTRUSTED_CLOUD_ROLE'
  }
  foreach($field in @('active_series_count','original_active_series_count')){
   if($wire -cnotmatch ('"'+$field+'"\s*:\s*1(?=\s*[,}])')){
    throw 'V3_T0_NOT_OLD_ONLY'
   }
  }
  foreach($field in @('epoch_count','intent_count','attempt_count',
   'dispatch_unknown_count','inhibit_count','cas_rpc_count')){
   if($wire -cnotmatch ('"'+$field+'"\s*:\s*0(?=\s*[,}])')){
    throw 'V3_T0_UNEXPECTED_CAS_ACTIVITY'
   }
  }
  foreach($field in @('executor_can_login','history_never_proven',
   'complete_attempt_unknown_custody_authenticated','t0_authenticated',
   'armed_marker_cancel_authorized','native_stop_restore_authorized',
   'cas_or_v3_paper_authorized')){
   if($wire -cnotmatch ('"'+$field+'"\s*:\s*false(?=\s*[,}])')){
    throw 'V3_T0_CLAIMED_FALSE_AUTHORITY'
   }
  }
  $t=[datetimeoffset]::MinValue
  $utc=[string]$obj.observed_at_utc
  if($utc -cnotmatch '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$' -or
     -not [datetimeoffset]::TryParseExact($utc,
      "yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'",
      [Globalization.CultureInfo]::InvariantCulture,
      [Globalization.DateTimeStyles]::AssumeUniversal,
      [ref]$t)){
   throw 'V3_T0_BAD_UTC'
  }
  $diff=($now-$t).TotalSeconds
  if($diff -lt -5 -or $diff -gt 30){throw 'V3_T0_NOT_CONTEMPORANEOUS_WITH_HOST'}
  $signedCurrentMatch=$true
  $notebookCloudTimeMatched=$true
 } catch {
  throw 'V3_T0_SIGNED_CROSS_SOURCE_HOLD'
 }
}
$pass=(@($tasks|Where-Object {
 $_.action_count -ne 1 -or $_.principal_is_system -ne $true
}).Count -eq 0 -and [string]$v3.State -ceq 'Disabled' -and
 -not(Test-Path -LiteralPath $maintenance))
[pscustomobject][ordered]@{
 kind='V3_PR515_PRE_EPOCH_ORIGINALHOST_NATIVE_OBSERVATION_V1'
 observed_at_utc=$now.ToString('o')
 expected_candidate_repo_sha=$ExpectedCandidateRepoSha
 originalhost_root_exact=$true
 old_task_config_observed=$pass
 old_tasks=$tasks
 old_python_processes=$old
 v3_task_disabled=([string]$v3.State -ceq 'Disabled')
 original_fence_phase=$marker
 original_fence_sha256=$fenceHash
 foreign_maintenance_present=(Test-Path -LiteralPath $maintenance)
 signed_current_notebook_cloud_catalog_cryptographically_valid=$signedCurrentMatch
 signed_current_cloud_and_originalhost_within_30_seconds=$notebookCloudTimeMatched
 independent_notebook_issuer_authority_verified_here=$false
 status='PHYSICAL_READONLY_OBSERVATION_NOT_AN_INDEPENDENT_RELEASE_ACK'
 exclusive_task_pid_antirace_proven=$false
 independently_authenticated_cloud_issuer_custody=$false
 complete_prospective_unknown_custody=$false
 marker_cancel_authorized=$false
 native_stop_or_restore_authorized=$false
 cas_or_paper_authorized=$false
 process_task_marker_cloud_writes=0
}|ConvertTo-Json -Depth 5
