# MINIPC_REVIEWED_TASK_V1
# Generic, bounded, non-mutating host-state metadata snapshot. No PR-specific semantics.
# This is observation only, NOT an independent signed witness, writer admission or recovery.
$ErrorActionPreference = 'Stop'
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$principal=[Security.Principal.WindowsPrincipal]::new($identity)
if($identity.Name -notmatch '(?i)\\CryptoSupportSvc$' -or
   $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator) -or
   $env:RUNNER_NAME -cne 'MINI-PC-CryptoSupport'){
  throw 'HOST_SNAPSHOT_BLOCK:IDENTITY'
}
$start=[DateTimeOffset]::UtcNow
$deadline=$start.AddSeconds(35)
function Assert-Budget {
  if([DateTimeOffset]::UtcNow -ge $deadline){throw 'HOST_SNAPSHOT_BLOCK:TIME_BUDGET'}
}
function Sha256-Text([string]$value) {
  $bytes=[Text.Encoding]::UTF8.GetBytes($value)
  $sha=[Security.Cryptography.SHA256]::Create()
  try {return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-','').ToLowerInvariant()}
  finally {$sha.Dispose()}
}
# No command line, executable path, environment, token, SID, file contents or raw XML output.
$processNames=@('powershell.exe','pwsh.exe','python.exe','pythonw.exe','node.exe','dotnet.exe','Runner.Worker.exe','Runner.Listener.exe')
$processes=@()
$processTotal=0
$processScan='UNAVAILABLE'
try {
  Assert-Budget
  $observed=@(Get-CimInstance Win32_Process -ErrorAction Stop |
    Where-Object { $_.Name -cin $processNames } |
    Sort-Object ProcessId)
  $processTotal=$observed.Count
  foreach($p in @($observed | Select-Object -First 24)) {
    Assert-Budget
    $pidValue=[long]$p.ProcessId
    $parentValue=[long]$p.ParentProcessId
    if($pidValue -lt 0 -or $pidValue -gt 2147483647 -or $parentValue -lt 0 -or $parentValue -gt 2147483647){continue}
    $processes+= [pscustomobject][ordered]@{
      image=[string]$p.Name
      pid=[int]$pidValue
      parent_pid=[int]$parentValue
    }
  }
  $processScan=if($processTotal -gt 24){'PARTIAL_LIMIT'}else{'OBSERVED_BOUNDED'}
}catch{
  $processes=@()
  $processTotal=0
  $processScan='UNAVAILABLE'
}
# Only stable relevant task names; never enumerate arbitrary XML content into logs.
$tasks=@()
$taskTotal=0
$taskScan='UNAVAILABLE'
try {
  Assert-Budget
  $found=@(Get-ScheduledTask -ErrorAction Stop |
    Where-Object { $_.TaskName -match '(?i)(V3|Kraken|CryptoSupport|Paper|Scanner)' } |
    Sort-Object TaskPath,TaskName)
  $taskTotal=$found.Count
  foreach($task in @($found | Select-Object -First 24)){
    Assert-Budget
    $name=[string]$task.TaskName
    $path=[string]$task.TaskPath
    if($name -cnotmatch '^[A-Za-z0-9_. -]{1,80}$' -or
       $path -cnotmatch '^[\\A-Za-z0-9_. -]{1,120}$'){
      $taskScan='PARTIAL_FILTERED'
      continue
    }
    $xmlSha=$null
    $xmlStatus='XML_UNAVAILABLE'
    try {
      Assert-Budget
      $xml=[string](Export-ScheduledTask -TaskName $name -TaskPath $path -ErrorAction Stop)
      if($xml.Length -gt 0 -and $xml.Length -le 262144){
        $xmlSha=Sha256-Text $xml
        $xmlStatus='XML_API_UTF8_SHA256'
      }
    }catch{ $xmlStatus='XML_UNAVAILABLE' }
    $tasks+= [pscustomobject][ordered]@{
      task_name=$name
      task_path=$path
      state=if([string]$task.State -cin @('Ready','Running','Disabled','Queued','Unknown')){[string]$task.State}else{'Unknown'}
      xml_status=$xmlStatus
      xml_sha256=$xmlSha
    }
  }
  if($taskScan -ne 'PARTIAL_FILTERED'){
    $taskScan=if($taskTotal -gt 24){'PARTIAL_LIMIT'}else{'OBSERVED_BOUNDED'}
  }
}catch{
  $tasks=@()
  $taskTotal=0
  $taskScan='UNAVAILABLE'
}
# Specific service state only: the controlled bridge itself. Not a generic service dump.
$runnerState='UNAVAILABLE'
$runnerStart='UNAVAILABLE'
try {
  Assert-Budget
  $service=Get-CimInstance Win32_Service -Filter "Name='actions.runner.hoffmannherdecke-kraken-readonly-bridge.MINI-PC-CryptoSupport'" -ErrorAction Stop
  if($service){
    if([string]$service.State -cin @('Running','Stopped','Start Pending','Stop Pending','Paused')){$runnerState=[string]$service.State}
    if([string]$service.StartMode -cin @('Disabled','Manual','Auto')){$runnerStart=[string]$service.StartMode}
  }
}catch{}
[pscustomobject][ordered]@{
  kind='MINIPC_REVIEWED_TASK_ACK_V1'
  status='SUCCESS'
  task='host_state_readonly'
  mutation_scope='RESTRICTED'
  schema='MINIPC_HOST_STATE_SAFE_V1'
  observed_at_utc=[DateTimeOffset]::UtcNow.ToString('o')
  process_scan=$processScan
  process_total=$processTotal
  processes=@($processes)
  task_scan=$taskScan
  task_total=$taskTotal
  tasks=@($tasks)
  bridge_service_state=$runnerState
  bridge_service_start_mode=$runnerStart
  independent_custody_verified=$false
  complete_writer_inventory_verified=$false
  host_recovery_authorized=$false
  trading_orders_permitted=$false
  changed_host_state=$false
} | ConvertTo-Json -Depth 5 -Compress
