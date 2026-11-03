# One-shot originalhost native custody observation for existing PR515/#99.
# READ ONLY. Never a second CAS/operator/release authority.
[CmdletBinding()]
param([string]$TradingRoot='C:\Users\ADMIN\Trading',
      [Parameter(Mandatory=$true)][string]$ExpectedCandidateRepoSha)
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
 status='PHYSICAL_READONLY_OBSERVATION_NOT_AN_INDEPENDENT_RELEASE_ACK'
 exclusive_task_pid_antirace_proven=$false
 independently_authenticated_cloud_issuer_custody=$false
 complete_prospective_unknown_custody=$false
 marker_cancel_authorized=$false
 native_stop_or_restore_authorized=$false
 cas_or_paper_authorized=$false
 process_task_marker_cloud_writes=0
}|ConvertTo-Json -Depth 5
