param(
  [string]$TradingRoot='C:\Users\ADMIN\Trading',
  [switch]$Execute,
  [string]$Confirm=''
)
# PHYSICAL pre-CAS Paper only: stop ONLY V2R4 Candidates and PR326 WAIT,
# prove native Disabled+no matching worker and independent Supervisor guard.
# DO NOT re-enable old intake in this command; manual after independent Cloud
# old-only/CAS-not-invoked readback is mandatory. No Cloud HTTP in this tool.
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath($TradingRoot).TrimEnd('\')
$expectedRoot='C:\Users\ADMIN\Trading'
$original='PAPER-V2R4-20261009T110135Z'
$names=@('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait')
$fence=Join-Path $root 'State\v3-experimental-paper-old-intake-fence.json'
$legacy=Join-Path $root 'State\v2r4-technical-cutover-maintenance.json'
$supPath=Join-Path $root 'State\minipc-runtime-supervisor.json'
$cloudPath=Join-Path $root 'State\v2r4-paper-cloud-sync-heartbeat.json'
$review=Join-Path $root 'Research\V3-SourceReview-20261015'
$cloudStage=Join-Path $root 'Staging\PR332-CloudSync-20261016-113256-d5c85c73\v2r4-paper-cloud-sync.py'
$cloudManifestPath=Join-Path $root 'Backups\PR332-CloudSync-Vorher-20261016-113256-d5c85c73\manifest.json'
$supervisorSha='9B148DB733ED61B9DA673E0E3BB9D319D336CE37FEFF9790D34BFE36B4680EF5'
$drillId=[guid]::NewGuid().ToString('N')
$markerWritten=$false
$tasksModified=$false

function Need([bool]$Valid,[string]$Why) { if(-not $Valid){throw $Why} }
function Test-ScopedTwo([string[]]$TaskNames) {
  $expected=@(@('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait')|Sort-Object)
  $actual=@($TaskNames|Sort-Object)
  return ($actual.Count -eq 2 -and ($actual -join '|') -ceq ($expected -join '|'))
}
function ScopedTask([string]$Name) {
  Need ($Name -in $names) 'Task not in original two-task scope'
  $t=Get-ScheduledTask -TaskName $Name -ErrorAction Stop
  Need ($t.TaskPath -eq '\' -and @($t.Actions).Count -eq 1) ('Native Task action drift: '+$Name)
  Need ([string]$t.Principal.UserId -in @('SYSTEM','NT AUTHORITY\SYSTEM','S-1-5-18')) ('Native SYSTEM principal drift: '+$Name)
  Need ([string]$t.Settings.MultipleInstances -eq 'IgnoreNew') ('MultipleInstances drift: '+$Name)
  return $t
}
function FreshJson([string]$Path,[int]$MaxAge=150) {
  $x=Get-Content -LiteralPath $Path -Raw -ErrorAction Stop|ConvertFrom-Json
  $age=([datetime]::UtcNow-([datetime]$x.checked_at_utc).ToUniversalTime()).TotalSeconds
  Need ($age -ge -5 -and $age -le $MaxAge) ('Missing/stale original-host heartbeat: '+(Split-Path -Leaf $Path))
  return $x
}
function Hash([string]$File) {
  Need (Test-Path -LiteralPath $File -PathType Leaf) ('Missing pinned file: '+(Split-Path -Leaf $File))
  return (Get-FileHash -LiteralPath $File -Algorithm SHA256 -ErrorAction Stop).Hash
}
function OneDirectory([string]$Pattern) {
  $folders=@(Get-ChildItem -LiteralPath (Join-Path $root 'Backups') -Directory |
    Where-Object {$_.Name -like $Pattern})
  Need ($folders.Count -eq 1) ('Native backup vintage ambiguous: '+$Pattern)
  return $folders[0].FullName
}
function PythonActionScript([object]$Task) {
  Need ([string]$Task.Actions[0].Execute -match '(?i)(?:^|[\\/])pythonw?\.exe$') 'Expected SYSTEM Python Task'
  $matches=@([regex]::Matches([string]$Task.Actions[0].Arguments,'"([^"]+\.py)"'))
  Need ($matches.Count -eq 1) 'Python action source must be uniquely quoted'
  $script=$matches[0].Groups[1].Value
  Need ([IO.Path]::IsPathRooted($script) -and
    [IO.Path]::GetFullPath($script).StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase)) 'Python action must be under original Trading'
  Need (Test-Path -LiteralPath $script -PathType Leaf) 'Python action source missing'
  return $script
}
function ResolveOriginalIntakePids([object[]]$All,[object[]]$Actions,[string[]]$Paths,[bool]$RequireRoots) {
  # A shared Python script is NOT a unique task identity. Compare the full
  # native Task arguments, then follow only verified process descendants.
  Need ($Actions.Count -eq 3 -and $Paths.Count -eq 2) 'Process role scope invalid'
  $roleRoots=@{}
  $allRoots=@()
  foreach($item in $Actions){
    $signature=([string]$item.arguments).Replace('\','/')
    Need ($signature.Length -ge 10) ('Missing Task argument identity: '+$item.name)
    $matched=@($All|Where-Object {
      $line=([string]$_.CommandLine).Replace('\','/')
      [string]$_.Name -match '(?i)^pythonw?\.exe$' -and
      $line.IndexOf($signature,[StringComparison]::OrdinalIgnoreCase) -ge 0
    })
    Need ($matched.Count -le 1) ('Duplicate running task owners: '+$item.name)
    if($RequireRoots -or $item.name -eq 'CryptoMiniPC-V2R4PaperLifecycle'){
      Need ($matched.Count -eq 1) ('Missing exact running task owner: '+$item.name)
    }
    $roleRoots[$item.name]=@($matched|ForEach-Object {[int]$_.ProcessId})
    $allRoots+=@($roleRoots[$item.name])
  }
  Need (@($allRoots|Sort-Object -Unique).Count -eq $allRoots.Count) 'Process claimed by multiple roles'
  $targetRoots=@($roleRoots['CryptoMiniPC-V2R4PaperCandidates']+
    $roleRoots['CryptoMiniPC-V2R4PaperWait'])
  $lifecycleRoots=@($roleRoots['CryptoMiniPC-V2R4PaperLifecycle'])
  $targetIds=@($targetRoots|Sort-Object -Unique)
  $lifecycleIds=@($lifecycleRoots|Sort-Object -Unique)
  do {
    $before=$targetIds.Count
    $targetIds=@($targetIds + @($All|Where-Object {
      $_.ParentProcessId -in $targetIds
    }|ForEach-Object {[int]$_.ProcessId})|Sort-Object -Unique)
  }while($targetIds.Count -ne $before)
  do {
    $before=$lifecycleIds.Count
    $lifecycleIds=@($lifecycleIds + @($All|Where-Object {
      $_.ParentProcessId -in $lifecycleIds
    }|ForEach-Object {[int]$_.ProcessId})|Sort-Object -Unique)
  }while($lifecycleIds.Count -ne $before)
  Need (@($targetIds|Where-Object {$_ -in $lifecycleIds}).Count -eq 0) 'Intake/Lifecycle process trees overlap'
  $covered=@($targetIds+$lifecycleIds|Sort-Object -Unique)
  $unknown=@($All|Where-Object {
    $p=$_
    $line=([string]$p.CommandLine).Replace('\','/')
    $hit=@($Paths|Where-Object {
      $line.IndexOf($_.Replace('\','/'),[StringComparison]::OrdinalIgnoreCase) -ge 0
    }).Count -gt 0
    $hit -and ([int]$p.ProcessId -notin $covered)
  })
  Need ($unknown.Count -eq 0) 'Unclassified original intake-script process; fail closed'
  return @($targetIds|Sort-Object -Unique)
}
function MatchingPids([string[]]$Paths,[bool]$RequireRoots=$false) {
  $scopes=@()
  foreach($role in @(
    'CryptoMiniPC-V2R4PaperCandidates',
    'CryptoMiniPC-V2R4PaperWait',
    'CryptoMiniPC-V2R4PaperLifecycle'
  )){
    $task=Get-ScheduledTask -TaskName $role -ErrorAction Stop
    Need ($task.TaskPath -eq '\' -and @($task.Actions).Count -eq 1 -and
      [string]$task.Principal.UserId -in @('SYSTEM','NT AUTHORITY\SYSTEM','S-1-5-18') -and
      [string]$task.Settings.MultipleInstances -eq 'IgnoreNew' -and
      [string]$task.Actions[0].Execute -match '(?i)(?:^|[\\/])pythonw?\.exe$') ('Process owner Task identity drift: '+$role)
    if($role -eq 'CryptoMiniPC-V2R4PaperLifecycle'){
      Need ([string]$task.State -eq 'Running') 'Lifecycle aftercare not running'
    }
    $scopes+=@([pscustomobject]@{name=$role;arguments=[string]$task.Actions[0].Arguments})
  }
  for($i=0;$i -lt 2;$i++){
    $a=([string]$scopes[$i].arguments).Replace('\','/')
    Need ($a.IndexOf($Paths[$i].Replace('\','/'),[StringComparison]::OrdinalIgnoreCase) -ge 0) 'Intake native action/source mismatch'
  }
  Need ([string]$scopes[0].arguments -ine [string]$scopes[2].arguments) 'Candidates/Lifecycle native actions ambiguous'
  $all=@(Get-CimInstance Win32_Process -ErrorAction Stop)
  return @(ResolveOriginalIntakePids $all $scopes $Paths $RequireRoots)
}

function GuardedMarker([string]$Phase,[string]$Owner) {
  $head=(git -C $review rev-parse HEAD)
  Need ($LASTEXITCODE -eq 0 -and [string]$head -match '^[a-f0-9]{40}$') 'Original V3 source HEAD unknown'
  $bundle=Hash (Join-Path $review 'research\v3\v3-experimental-paper-all-lessons-bundle-20261011.json')
  $strategy=Hash (Join-Path $review 'paper_evaluator\v3_full_entry_decision_candidate_v1.py')
  return [ordered]@{
    kind='V3_EXPERIMENTAL_OLD_INTAKE_FENCE_V1'
    phase=$Phase
    predecessor_series_id=$original
    proposed_successor_series_id='PAPER-V3-DRILL-20261016-'+$Owner
    proposed_v3_repo_sha=[string]$head
    proposed_v3_bundle_sha256=$bundle.ToLowerInvariant()
    proposed_v3_strategy_sha256=$strategy.ToLowerInvariant()
    task_names=$names
    paper_only=$true
    orders_enabled=$false
    real_money_actions=$false
    persistent_until_explicit_owner_release=$true
    drill_only=$true
    drill_token=$Owner
  }
}
function ProtectedMarkerWrite([object]$Payload,[bool]$Replace) {
  $temp=$fence+'.'+$drillId+'.tmp'
  $fileAcl=[Security.AccessControl.FileSecurity]::new()
  $fileAcl.SetAccessRuleProtection($true,$false)
  foreach($sid in @('S-1-5-18','S-1-5-32-544')){
    $rule=[Security.AccessControl.FileSystemAccessRule]::new(
      [Security.Principal.SecurityIdentifier]::new($sid),
      [Security.AccessControl.FileSystemRights]::FullControl,
      [Security.AccessControl.AccessControlType]::Allow)
    $fileAcl.AddAccessRule($rule)
  }
  [IO.File]::WriteAllText($temp,($Payload|ConvertTo-Json -Depth 5),[Text.UTF8Encoding]::new($false))
  Set-Acl -LiteralPath $temp -AclObject $fileAcl
  if($Replace) {
    $current=Get-Content -LiteralPath $fence -Raw|ConvertFrom-Json
    Need ($current.drill_token -eq $drillId -and $current.phase -eq 'ARMED') 'Marker ownership/phase changed'
    [IO.File]::Replace($temp,$fence,$null,$true)
  } else {
    Need (-not (Test-Path -LiteralPath $fence)) 'Fence unexpectedly appeared'
    [IO.File]::Move($temp,$fence)
  }
}
function WaitSupervisorAndCloud([string]$Phase,[datetime]$Since,[int]$TimeoutSec,[bool]$NeedDisabled) {
  $end=(Get-Date).AddSeconds($TimeoutSec); $receipts=@()
  do {
    Start-Sleep -Seconds 3
    $s=$null;$c=$null
    try { $s=FreshJson $supPath 180; $c=FreshJson $cloudPath 180 } catch { continue }
    if(([datetime]$s.checked_at_utc).ToUniversalTime() -le $Since -or
       ([datetime]$c.checked_at_utc).ToUniversalTime() -le $Since){continue}
    $goodTasks=@($s.tasks|Where-Object {
      $_.task -in $names -and $_.action -eq 'V3_INTAKE_SUPERVISOR_REARM_BLOCKED' -and
      (-not $NeedDisabled -or $_.before.scheduler_state -eq 'Disabled')
    })
    $healthy=($s.status -eq 'WARNING' -and
      $s.v3_paper_old_intake_fence.mode -eq $Phase -and $goodTasks.Count -eq 2 -and
      @($s.restarted).Count -eq 0 -and @($s.failed_restarts).Count -eq 0 -and
      $c.status -eq 'HEALTHY' -and $c.mode -eq 'V3_PRECOMMIT_NO_NETWORK_HOLD' -and
      $c.v3_fence_precommit_phase -eq $Phase -and
      $c.v3_fence_cloud_sync_lane -eq 'PRECOMMIT_ORIGINAL' -and
      $c.cloud_sync_intentionally_paused -eq $true -and $c.cloud_updated -eq $false)
    if($healthy){
      $stamp=([datetime]$s.checked_at_utc).ToUniversalTime().ToString('o')
      if($stamp -notin $receipts){$receipts+=@($stamp)}
      if($receipts.Count -ge $(if($NeedDisabled){2}else{1})){return $true}
    }
  } while((Get-Date) -lt $end)
  return $false
}
Need ($root -ieq 'C:\Users\ADMIN\Trading') 'Unexpected original TradingRoot'
Need (Test-ScopedTwo $names) 'Task scope is not exact Candidates+WAIT'
Need (-not (Test-Path -LiteralPath $fence) -and
      -not (Test-Path -LiteralPath $legacy)) 'Existing conflicting protection marker'
$cloudManifest=Get-Content -LiteralPath $cloudManifestPath -Raw -ErrorAction Stop|ConvertFrom-Json
Need ($cloudManifest.kind -ceq 'PR332_CLOUDSYNC_PROTECTED_STAGE_V1' -and
  $cloudManifest.task_name -ceq 'CryptoMiniPC-V2R4PaperCloudSync' -and
  [string]$cloudManifest.new_source -ieq $cloudStage -and
  [string]$cloudManifest.new_git_commit -ceq 'b97a45d589f6813b28fe94f62fd37e94e764d054' -and
  [string]$cloudManifest.new_git_blob_sha1 -ceq '63eca1cbc596819c36796f0a97155513002dd0ed' -and
  [string]$cloudManifest.new_source_sha256 -cmatch '^[A-Fa-f0-9]{64}$') 'Protected PR332 manifest identity/hash invalid'
Need ((Hash $cloudStage) -ieq [string]$cloudManifest.new_source_sha256) 'PR332 effective source SHA mismatch'
# Do not rely on the previous boolean as source identity: check the effective
# Task action independently against a pinned executable script before execute.
$supervisorTask=Get-ScheduledTask -TaskName 'CryptoMiniPC-RuntimeSupervisor' -ErrorAction Stop
$supervisorSource=([regex]::Match([string]$supervisorTask.Actions[0].Arguments,
 '(?i)([A-Z]:\\[^"''\r\n]*minipc-runtime-supervisor\.ps1)')).Groups[1].Value
Need (-not [string]::IsNullOrEmpty($supervisorSource) -and
       (Hash $supervisorSource) -eq $supervisorSha) 'Original Supervisor SHA pin drift'
$cloudTask=Get-ScheduledTask -TaskName 'CryptoMiniPC-V2R4PaperCloudSync'
Need ([string]$cloudTask.State -eq 'Running' -and
    [string]$cloudTask.Actions[0].Arguments -match [regex]::Escape($cloudStage)) 'PR332 CloudSync effective action drift'
foreach($keep in @('CryptoMiniPC-V2R4PaperLifecycle','CryptoMiniPC-V2R4PaperCloudSync')){
  Need ([string](Get-ScheduledTask -TaskName $keep).State -eq 'Running') ('Protected aftercare unhealthy: '+$keep)
}
$s=FreshJson $supPath; $c=FreshJson $cloudPath
Need ($s.status -eq 'HEALTHY' -and
      $s.v3_paper_old_intake_fence.mode -eq 'NONE' -and
      $s.maintenance.mode -eq 'NONE' -and
      $c.status -eq 'HEALTHY' -and
      $c.v3_fence_cloud_sync_lane -eq 'ACTIVE_ORIGINAL' -and
      $c.series_id -eq $original) 'Original supervisor/CloudSync current preflight invalid'
$backupOld=OneDirectory 'V3-Intake-Original-20261015-073139-*'
$backupWait=OneDirectory 'V3-WAIT-PR326-Current-20261016-*'
$m1=Get-Content (Join-Path $backupOld 'backup-manifest.json') -Raw|ConvertFrom-Json
$m2=Get-Content (Join-Path $backupWait 'backup-manifest.json') -Raw|ConvertFrom-Json
$maps=@(
  [pscustomobject]@{name=$names[0];xml=(Join-Path $backupOld 'Candidates.task.xml');expected=@($m1.tasks|Where-Object {$_.task_name -eq $names[0]})[0].xml_sha256},
  [pscustomobject]@{name=$names[1];xml=(Join-Path $backupWait 'WAIT.task.xml');expected=$m2.xml_sha256}
)
$actionPaths=@()
foreach($map in $maps){
  $task=ScopedTask $map.name
  Need ([string]$task.State -eq 'Running') ('Intake not running: '+$map.name)
  Need ((Hash $map.xml) -eq [string]$map.expected) ('Protected original XML SHA drift: '+$map.name)
  Need ([IO.File]::ReadAllText($map.xml) -ceq
    (Export-ScheduledTask -TaskName $map.name)) ('Original live Task XML differs: '+$map.name)
  $actionPaths+=@(PythonActionScript $task)
}
Need (@($actionPaths|Sort-Object -Unique).Count -eq 2) 'Two distinct original intake action scripts required'
$startingPids=@(MatchingPids $actionPaths $true)
Need ($startingPids.Count -ge 2 -and $startingPids.Count -le 8) 'Original running process family ambiguous'
Write-Output 'V3_NATIVE_STOP_PREFLIGHT=PASS'
Write-Output ('V3_NATIVE_ORIGINAL_SOURCE_PIDS='+($startingPids -join ','))
Write-Output 'V3_NATIVE_CURRENT_BACKUPS=15_OCT_CANDIDATES_PLUS_16_OCT_PR326_WAIT'
Write-Output 'V3_CAS_IN_THIS_OPERATOR=NEVER'
if(-not $Execute){Write-Output 'V3_NATIVE_STOP_PREVIEW_ONLY=True';return}
Need ($Confirm -ceq 'V3-TWO-INTAKE-STOP-ONLY') 'Exact user-approved stop-only gate absent'
$payload=GuardedMarker 'ARMED' $drillId
try {
  ProtectedMarkerWrite $payload $false
  $markerWritten=$true
  $since=[datetime]::UtcNow.AddSeconds(-3)
  Need (WaitSupervisorAndCloud 'ARMED' $since 150 $false) 'ARMED supervisor/cloud independent receipt not observed'
  # Only two original SYSTEM intake tasks may be modified, in this order.
  foreach($name in $names){ Disable-ScheduledTask -TaskName $name -ErrorAction Stop|Out-Null; $tasksModified=$true }
  # A disabled Task may still own a live Python worker. Request stop always,
  # then confirm zero original worker descendants before going QUIESCED.
  foreach($name in $names){
    Stop-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
  }
  $deadline=(Get-Date).AddSeconds(60)
  do{
    $disabled=@($names|Where-Object {[string](Get-ScheduledTask -TaskName $_).State -eq 'Disabled'})
    $pidLeft=@(MatchingPids $actionPaths)
    if($disabled.Count -eq 2 -and $pidLeft.Count -eq 0){break}
    Start-Sleep -Seconds 2
  }while((Get-Date) -lt $deadline)
  Need ($disabled.Count -eq 2 -and $pidLeft.Count -eq 0) 'Native stop not fully acknowledged; preserve fenced manual review'
  $payload.phase='QUIESCED'
  ProtectedMarkerWrite $payload $true
  $since=[datetime]::UtcNow.AddSeconds(-3)
  Need (WaitSupervisorAndCloud 'QUIESCED' $since 180 $true) 'Two supervisor QUIESCED cycles not independently confirmed'
  Need (@(MatchingPids $actionPaths).Count -eq 0) 'Intake process resurfaced'
  Need (@($names|Where-Object {[string](Get-ScheduledTask -TaskName $_).State -eq 'Disabled'}).Count -eq 2) 'Intake windows Task rearmed'
  Write-Output 'V3_PHYSICAL_NATIVE_NO_REARM=PASS'
  Write-Output 'V3_STOPPED_INTAKE=2_OF_2'
  Write-Output 'V3_SUPERVISOR_QUIESCED_ACK=2_FRESH_CYCLES'
  Write-Output 'V3_CLOUDSYNC_PRECOMMIT_NO_NETWORK=PASS'
  Write-Output 'V3_MARKER_REMAINS=QUIESCED'
  Write-Output 'V3_WINDOWS_INTAKE_TASKS_REMAIN=DISABLED'
  Write-Output 'V3_NEEDS_INDEPENDENT_CLOUD_CHECK_BEFORE_RESTORE=True'
  Write-Output 'V3_CAS_IN_THIS_OPERATOR=NEVER'
} catch {
  Write-Warning ('V3_PHYSICAL_STOP_HOLD: '+$_.Exception.Message)
  if($markerWritten -and -not $tasksModified){
    # No Scheduler change occurred. Clear our own ARMED marker only when
    # both original Task configurations are still RUNNING; else leave fenced.
    $taskStillRunning=@($names|Where-Object {
      [string](Get-ScheduledTask -TaskName $_).State -eq 'Running'
    }).Count -eq 2
    if($taskStillRunning){
      $existing=Get-Content -LiteralPath $fence -Raw|ConvertFrom-Json
      if($existing.drill_token -eq $drillId -and $existing.phase -eq 'ARMED'){
        Remove-Item -LiteralPath $fence -Force -ErrorAction Stop
        Write-Warning 'V3_ARMED_MARKER_REMOVED_NO_WINDOWS_TASK_CHANGE'
      }
    }
  }
  if($tasksModified){Write-Warning 'STOP/ROLLBACK BLOCKED: Windows intake state may be partial; marker must remain until reviewed. Do not manually re-enable.'}
  throw
}
