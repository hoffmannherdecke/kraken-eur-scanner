param(
  [int]$DurationSeconds=30,
  [int]$IntervalSeconds=5,
  [string]$TradingRoot=(Join-Path $env:USERPROFILE 'Trading')
)
# Issue353: ONE-SHOT READ-ONLY originalhost CPU cost and role snapshot.
# No Cloud API, disk writes, task changes, background loop or release authorization.
$ErrorActionPreference='Stop'
if($DurationSeconds -lt 15 -or $DurationSeconds -gt 120 -or
   $IntervalSeconds -lt 3 -or $IntervalSeconds -gt 15 -or
   $DurationSeconds % $IntervalSeconds -ne 0) {
   throw 'CPU_SAMPLE_INVALID_BOUNDED_WINDOW'
}
if(-not(Test-Path -LiteralPath $TradingRoot -PathType Container)){
  throw 'CPU_SAMPLE_TRADING_ROOT_NOT_PRESENT'
}
$cores=[Environment]::ProcessorCount
if($cores -le 0){throw 'CPU_SAMPLE_INVALID_PROCESSOR_COUNT'}
function Role([string]$Name,[string]$Cmdline) {
  $cmd=[string]$Cmdline
  $nameLower=([string]$Name).ToLowerInvariant()
  if($nameLower -in @('python.exe','pythonw.exe')) {
    if($cmd -match '(?i)(?:^|[\\/])v2r4-paper-local-runtime\.py(?:["\s]|$)') {
      if($cmd -match '(?i)--mode\s+candidates\b'){return 'V2R4_CANDIDATES'}
      if($cmd -match '(?i)--mode\s+lifecycle\b'){return 'V2R4_LIFECYCLE'}
      return 'V2R4_PAPER_MODE_UNKNOWN'
    }
    if($cmd -match '(?i)(?:^|[\\/])(?:wait_launcher|v2r4_wait_runtime)\.py(?:["\s]|$)'){
      return 'PR326_WAIT'
    }
    if($cmd -match '(?i)(?:^|[\\/])v2r4-paper-cloud-sync\.py(?:["\s]|$)'){return 'V2R4_CLOUDSYNC'}
    return 'OTHER_PYTHON'
  }
  if($nameLower -eq 'msmpeng.exe'){return 'WINDOWS_DEFENDER'}
  if($nameLower -eq 'chatgpt.exe'){return 'CHATGPT_UI'}
  if($nameLower -like 'codex*'){return 'CODEX_UI'}
  return 'OTHER'
}
function Snapshot(){
  $cim=@(Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe' OR Name='msmpeng.exe' OR Name='chatgpt.exe' OR Name='codex.exe'" -ErrorAction Stop)
  $cpu=@(Get-Process -ErrorAction Stop | Where-Object {
    $_.ProcessName -in @('python','pythonw','msmpeng','chatgpt','codex')
  })
  $byId=@{}
  foreach($p in $cim){
    $pidNumber=[int]$p.ProcessId
    $byId[$pidNumber]=[pscustomobject]@{
      signature=([string]$pidNumber+'|'+([datetime]$p.CreationDate).ToUniversalTime().ToString('o'))
      role=(Role ([string]$p.Name) ([string]$p.CommandLine))
    }
  }
  $rows=@{}
  foreach($p in $cpu){
    $pidNumber=[int]$p.Id
    if(-not $byId.ContainsKey($pidNumber)){continue}
    try{$cpuSeconds=[double]$p.CPU}catch{continue}
    if([double]::IsNaN($cpuSeconds) -or $cpuSeconds -lt 0){continue}
    $rows[$pidNumber]=[pscustomobject]@{
      signature=$byId[$pidNumber].signature
      role=$byId[$pidNumber].role
      cpuSeconds=$cpuSeconds
    }
  }
  $osLoad=@(Get-CimInstance Win32_Processor -ErrorAction Stop |
    ForEach-Object {[double]$_.LoadPercentage})
  $load=if($osLoad.Count){[math]::Round((($osLoad|Measure-Object -Average).Average),1)}else{$null}
  return [pscustomobject]@{timestamp=[datetime]::UtcNow;processes=$rows;osLoad=$load}
}
$roleData=@{}
$hostLoad=@()
$intervals=@()
$ignoredNew=0
$first=Snapshot
$last=$first
for($i=0;$i -lt ($DurationSeconds / $IntervalSeconds);$i++){
  Start-Sleep -Seconds $IntervalSeconds
  $next=Snapshot
  $elapsed=($next.timestamp-$last.timestamp).TotalSeconds
  if($elapsed -le 0){throw 'CPU_SAMPLE_CLOCK_INVALID'}
  $roles=@{}
  foreach($key in $next.processes.Keys){
    $p=$next.processes[$key]
    if(-not $last.processes.ContainsKey($key)){$ignoredNew++;continue}
    $previous=$last.processes[$key]
    if($previous.signature -cne $p.signature -or $previous.role -cne $p.role){
      $ignoredNew++;continue
    }
    $delta=$p.cpuSeconds-$previous.cpuSeconds
    if($delta -lt 0){$ignoredNew++;continue}
    $percent=[math]::Min(100.0,100*$delta/($elapsed*$cores))
    if(-not $roles.ContainsKey($p.role)){$roles[$p.role]=0.0}
    $roles[$p.role]+=$percent
  }
  foreach($name in $roles.Keys){
    if(-not $roleData.ContainsKey($name)){
      $roleData[$name]=[pscustomobject]@{total=0.0;maximum=0.0}
    }
    $roleData[$name].total+=$roles[$name]
    if($roles[$name] -gt $roleData[$name].maximum){$roleData[$name].maximum=$roles[$name]}
  }
  $intervals+=@([pscustomobject]@{
    seconds=[math]::Round($elapsed,1)
    host_os_load_pct=$next.osLoad
    active_python_count=@($next.processes.Values | Where-Object {
      $_.role -in @('V2R4_CANDIDATES','V2R4_LIFECYCLE','PR326_WAIT','V2R4_PAPER_MODE_UNKNOWN','OTHER_PYTHON','V2R4_CLOUDSYNC')
    }).Count
  })
  if($null -ne $next.osLoad){$hostLoad+=@($next.osLoad)}
  $last=$next
}
$n=$intervals.Count
$groups=@(foreach($name in ($roleData.Keys|Sort-Object)){
  [ordered]@{
    role=$name
    avg_total_cpu_pct=[math]::Round(($roleData[$name].total/$n),2)
    peak_interval_cpu_pct=[math]::Round($roleData[$name].maximum,2)
  }
})
$loadAvg=if($hostLoad.Count){[math]::Round((($hostLoad|Measure-Object -Average).Average),1)}else{$null}
$loadPeak=if($hostLoad.Count){($hostLoad|Measure-Object -Maximum).Maximum}else{$null}
[ordered]@{
  kind='ISSUE353_V2R4_CPU_ORIGINALHOST_BASELINE_V1'
  status='READ_ONLY_PERFORMANCE_OBSERVATION_NOT_RELEASE_ACK'
  series_id='PAPER-V2R4-20261009T110135Z'
  start_utc=$first.timestamp.ToString('o')
  end_utc=$last.timestamp.ToString('o')
  physical_cores_visible=$cores
  intervals=$n
  approximate_host_os_load_avg_pct=$loadAvg
  approximate_host_os_load_max_pct=$loadPeak
  groups=$groups
  interval_counts=$intervals
  new_or_reused_pids_excluded=$ignoredNew
  interpretation='One short sample, not matched workload parity or new cache CPU savings'
  paper_runtime_changed=$false
  task_mutations=$false
  disk_writes=$false
  cloud_mutations=$false
  production_release_authorized=$false
} | ConvertTo-Json -Depth 7
