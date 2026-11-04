param(
  [string]$TradingRoot=(Join-Path $env:USERPROFILE 'Trading'),
  [string]$SourceRoot='',
  [switch]$Stage,
  [switch]$Execute,
  [switch]$Rollback,
  [string]$Confirm=''
)
# Issue #353 / #99, PR666: ONE bounded versioned V2R4 PAPER Candidates/Lifecycle release.
# Read-only default; -Stage is inert; -Execute/-Rollback require SEPARATE host approval.
# Neither WAIT nor CloudSync nor paper series nor V3/CAS is retargeted.
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$pin='b4c751fbe9df468360a7683961aaf46228c3b944'
$series='PAPER-V2R4-20261009T110135Z'
$oldRel='Runtime\v2r4-paper-stage-d8b35a8ec2e6'
$file='v2r4-paper-local-runtime.py'
$oldSha='8371CAB2D7D18F9651E604DBAB88768F77B2DFF5EB88565122858F6428DC50D0'
$names=@('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperLifecycle')
$supervisor='CryptoMiniPC-RuntimeSupervisor'
$root=[IO.Path]::GetFullPath($TradingRoot)
if(-not $SourceRoot){$SourceRoot=Join-Path $root 'Repos\kraken-eur-scanner'}
$source=[IO.Path]::GetFullPath($SourceRoot)
$old=Join-Path $root $oldRel
$new=Join-Path $root ('Runtime\v2r4-pr666-inert-'+$pin.Substring(0,12))
$stageFile=Join-Path $new $file
$manifest=Join-Path $new 'pr666-immutable-stage-manifest.json'
$sourceFile=Join-Path $source 'tools\v2r4-paper-local-runtime.py'
$maintenance=Join-Path $root 'State\v2r4-pr666-scoped-switch.json'
$backupRoot=Join-Path $root 'Backups'
function Need([bool]$ok,[string]$why){if(-not $ok){throw ('PR666_HOLD: '+$why)}}
function Sha([string]$p){
  Need (Test-Path -LiteralPath $p -PathType Leaf) ('missing '+$p)
  $i=Get-Item -LiteralPath $p -Force
  Need (-not [bool]($i.Attributes -band [IO.FileAttributes]::ReparsePoint)) ('linked '+$p)
  (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()
}
function Save([string]$p,[object]$v){
  $temp=$p+'.tmp'
  Need (-not (Test-Path -LiteralPath $temp)) ('existing temp '+$p)
  [IO.File]::WriteAllText($temp,(ConvertTo-Json -InputObject $v -Depth 20)+[Environment]::NewLine,[Text.UTF8Encoding]::new($false))
  Move-Item -LiteralPath $temp -Destination $p -Force
}
function Task([string]$n){Get-ScheduledTask -TaskName $n -ErrorAction Stop}
function OriginalAction([string]$n){
  $t=Task $n
  Need (@($t.Actions).Count -eq 1) ('multi-action '+$n)
  Need ([string]$t.Principal.UserId -in @('SYSTEM','NT AUTHORITY\SYSTEM','S-1-5-18')) ('principal '+$n)
  $a=$t.Actions[0]
  Need ([string]$a.Execute -match '(?i)(?:^|[\\/])pythonw?\.exe$') ('not Python '+$n)
  $args=[string]$a.Arguments
  # Exact quoted old script, not an arbitrary substring or untrusted input.
  $needle='"'+(Join-Path $old $file)+'"'
  Need ($args.Contains($needle)) ('not exact original binding '+$n)
  Need ($args.Split([string[]]@($needle),[StringSplitOptions]::None).Length -eq 2) ('ambiguous original script '+$n)
  return $t
}
function Inventory([string]$dir){
  @(
    Get-ChildItem -LiteralPath $dir -File -Recurse -Force |
      Where-Object { $_.FullName -ne $manifest } |
      Sort-Object FullName |
      ForEach-Object {
        $rel=$_.FullName.Substring($dir.Length).TrimStart('\').Replace('\','/')
        [ordered]@{path=$rel;sha256=(Sha $_.FullName)}
      }
  )
}
function Verify-Stage {
  Need (Test-Path -LiteralPath $manifest -PathType Leaf) 'inert manifest missing'
  $m=Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
  Need ([string]$m.kind -ceq 'V2R4_PR666_SCOPED_STAGE_V2' -and
        [string]$m.status -ceq 'INERT_NO_TASK_CHANGE' -and
        [string]$m.commit -ceq $pin -and
        [string]$m.series_id -ceq $series) 'manifest identity mismatch'
  $entries=@($m.files)
  $live=@(Inventory $new)
  Need ($entries.Count -eq $live.Count -and $entries.Count -ge 3) 'inventory size drift'
  for($j=0;$j -lt $entries.Count;$j++){
    Need ([string]$entries[$j].path -ceq [string]$live[$j].path -and
          [string]$entries[$j].sha256 -ceq [string]$live[$j].sha256) 'staged file drift'
  }
  Need ((Sha $stageFile) -ceq [string]$m.new_file_sha256) 'PR666 code drift'
  Need (-not (Test-Path -LiteralPath (Join-Path $new 'paper_runtime_control.json'))) 'active control in stage'
  return $m
}
function ActiveChildren {
  # Scheduled tasks can leave Python/evaluator or supervisor children running.
  $needleOld=(Join-Path $old $file).Replace('\','/')
  $needleNew=$stageFile.Replace('\','/')
  $eval=(Join-Path $old 'paper_evaluator\evaluate.py').Replace('\','/')
  $supervisorScript='minipc-runtime-supervisor.ps1'
  @(
    Get-CimInstance Win32_Process -ErrorAction Stop |
      Where-Object { [string]$_.Name -match '^(?:pythonw?|powershell|pwsh)\.exe$' } |
      Where-Object {
        $cmd=([string]$_.CommandLine).Replace('\','/')
        ([string]$_.Name -match '^pythonw?\.exe$' -and
         $cmd.IndexOf($file,[StringComparison]::OrdinalIgnoreCase) -ge 0) -or
        $cmd.IndexOf($needleOld,[StringComparison]::OrdinalIgnoreCase) -ge 0 -or
        $cmd.IndexOf($needleNew,[StringComparison]::OrdinalIgnoreCase) -ge 0 -or
        $cmd.IndexOf($eval,[StringComparison]::OrdinalIgnoreCase) -ge 0 -or
        ($_.Name -match '(?i)^(?:powershell|pwsh)\.exe$' -and
         $cmd.IndexOf($supervisorScript,[StringComparison]::OrdinalIgnoreCase) -ge 0)
      } | Select-Object ProcessId,CreationDate,CommandLine
  )
}
function Quiet([int]$seconds=195){
  $end=(Get-Date).AddSeconds($seconds)
  do{
    $children=@(ActiveChildren)
    if($children.Count -eq 0){return}
    Start-Sleep -Milliseconds 500
  }while((Get-Date) -lt $end)
  throw ('PR666_HOLD: old/new Candidate or evaluator child alive PID='+(@($children|ForEach-Object{$_.ProcessId}) -join ','))
}
function StopBounded([string]$name){
  if([string](Task $name).State -ne 'Running'){return}
  Stop-ScheduledTask -TaskName $name -ErrorAction Stop
  $end=(Get-Date).AddSeconds(25)
  do {
    if([string](Task $name).State -ne 'Running'){return}
    Start-Sleep -Milliseconds 250
  }while((Get-Date) -lt $end)
  throw ('PR666_HOLD: task still running '+$name)
}
function Need-Admin {
  $principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
  Need ($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) 'Administrator required for task changes'
}
function Backup-Tasks([string]$directory){
  New-Item -ItemType Directory -Path $directory -ErrorAction Stop | Out-Null
  New-Item -ItemType Directory -Path (Join-Path $directory 'tasks') -ErrorAction Stop | Out-Null
  $states=[ordered]@{}
  foreach($n in @($names)+@($supervisor)){
    $t=Task $n
    $xml=Export-ScheduledTask -TaskName $n -ErrorAction Stop
    $xmlPath=Join-Path $directory ('tasks\'+$n+'.xml')
    [IO.File]::WriteAllText($xmlPath,$xml,[Text.UTF8Encoding]::new($false))
    $states[$n]=[ordered]@{
      enabled=([bool]$t.Settings.Enabled)
      running=([string]$t.State -eq 'Running')
      xml_sha256=(Sha $xmlPath)
    }
  }
  Save (Join-Path $directory 'task-states.json') $states
  return $states
}
function Restore-Tasks([string]$directory,[bool]$startPrevious){
  # NEVER restore/start old children alongside any successor child.
  Quiet 25
  $states=Get-Content -LiteralPath (Join-Path $directory 'task-states.json') -Raw | ConvertFrom-Json
  foreach($n in @($names)+@($supervisor)){
    $entry=$states.PSObject.Properties[$n]
    Need ($null -ne $entry) ('missing state '+$n)
    $p=Join-Path $directory ('tasks\'+$n+'.xml')
    Need ((Sha $p) -ceq [string]$entry.Value.xml_sha256) ('backup XML drift '+$n)
    Register-ScheduledTask -TaskName $n -Xml (Get-Content -LiteralPath $p -Raw) -Force -ErrorAction Stop | Out-Null
    if($entry.Value.enabled -eq $true){Enable-ScheduledTask -TaskName $n | Out-Null}
    else{Disable-ScheduledTask -TaskName $n | Out-Null}
  }
  if($startPrevious){
    foreach($n in @($names)+@($supervisor)){
      $entry=$states.PSObject.Properties[$n].Value
      if($entry.enabled -eq $true -and $entry.running -eq $true){Start-ScheduledTask -TaskName $n -ErrorAction Stop}
    }
  }
}
function Check-Preflight {
  Need (Test-Path -LiteralPath $old -PathType Container) 'original release absent'
  Need ((Sha (Join-Path $old $file)) -ceq $oldSha.ToLowerInvariant()) 'frozen original SHA mismatch'
  $c=Get-Content -LiteralPath (Join-Path $old 'paper_runtime_control.json') -Raw | ConvertFrom-Json
  Need ([string]$c.series_id -ceq $series -and $c.paper_only -eq $true -and
        $c.real_money_actions_enabled -eq $false) 'active PAPER guards or series drift'
  foreach($n in $names){$null=OriginalAction $n}
  # Disallow competing bounded operator and V3 transition.
  foreach($p in @('v2r4-technical-cutover-maintenance.json','v2r4-technical-cutover-operator-lock.json',
                 'v3-paper-cutover-maintenance.json','v3-experimental-old-intake-fence.json')){
    Need (-not (Test-Path -LiteralPath (Join-Path $root ('State\'+$p)))) ('conflicting transition '+$p)
  }
}
Need ((@([bool]$Stage,[bool]$Execute,[bool]$Rollback)|Where-Object {$_}).Count -le 1) 'choose exactly one mode'
Need (Test-Path -LiteralPath $root -PathType Container) 'Trading root missing'
if($Rollback){
  Need-Admin
  Need ($Confirm -ceq 'ROLLBACK_APPROVED_PR666_PAPER_ONLY') 'separate rollback authorization absent'
  Need (Test-Path -LiteralPath $maintenance -PathType Leaf) 'no persisted original task backup'
  $record=Get-Content -LiteralPath $maintenance -Raw|ConvertFrom-Json
  Need ([string]$record.kind -ceq 'V2R4_PR666_TASK_SWITCH_V1' -and
       [string]$record.commit -ceq $pin -and [string]$record.series_id -ceq $series) 'maintenance identity mismatch'
  # If uncertain process state or incomplete backup: do not arm any writer.
  foreach($n in @($names)+@($supervisor)){StopBounded $n; Disable-ScheduledTask -TaskName $n|Out-Null}
  Quiet
  Restore-Tasks ([string]$record.backup_directory) $true
  $record.status='ROLLED_BACK_ORIGINAL_TASKS_RESTORED'
  Save $maintenance $record
  [pscustomobject]@{status=$record.status;original_sha256=$oldSha;new_writer_stopped=$true;wait_cloudsync_untouched=$true}|ConvertTo-Json
  return
}
Need (-not(Test-Path -LiteralPath $maintenance)) 'prior switch/rollback receipt exists; do not repeat'
if($Execute){
  Need-Admin
  Need ($Confirm -ceq 'EXECUTE_APPROVED_PR666_CANDIDATES_LIFECYCLE_ONLY') 'separate productive authorization absent'
  Check-Preflight
  $m=Verify-Stage
  $actions=[ordered]@{}
  foreach($n in $names){
    $t=OriginalAction $n
    $a=$t.Actions[0]
    $oldQuoted='"'+(Join-Path $old $file)+'"'
    $newQuoted='"'+$stageFile+'"'
    $newArgs=([string]$a.Arguments).Replace($oldQuoted,$newQuoted)
    Need ($newArgs -cne [string]$a.Arguments -and $newArgs.Contains($newQuoted)) 'replacement failed'
    $actions[$n]=[ordered]@{execute=[string]$a.Execute;arguments=$newArgs;working_directory=[string]$a.WorkingDirectory}
  }
  Need (@(ActiveChildren | Where-Object {([string]$_.CommandLine).Replace('\','/').IndexOf($stageFile.Replace('\','/'),[StringComparison]::OrdinalIgnoreCase) -ge 0}).Count -eq 0) 'successor already executing'
  Need (Test-Path -LiteralPath $backupRoot -PathType Container) 'existing backup root missing'
  $backup=Join-Path $backupRoot ('v2r4-pr666-'+[datetime]::UtcNow.ToString('yyyyMMddTHHmmssZ'))
  $saved=Backup-Tasks $backup
  $record=[ordered]@{
    kind='V2R4_PR666_TASK_SWITCH_V1';status='PRECOMMIT_BACKUP_COMPLETE'
    series_id=$series;commit=$pin;new_file_sha256=[string]$m.new_file_sha256
    backup_directory=$backup;started_at_utc=[datetime]::UtcNow.ToString('o')
    original_control_sha256=(Sha (Join-Path $old 'paper_runtime_control.json'))
    wait_cloudsync_mutated=$false
  }
  Save $maintenance $record
  try{
    # Existing supervisor can rearm Candidates before a bounded swap; suspend ONLY
    # this supervisor task for the maintenance window. Other tasks are untouched.
    StopBounded $supervisor
    Disable-ScheduledTask -TaskName $supervisor | Out-Null
    foreach($n in $names){StopBounded $n;Disable-ScheduledTask -TaskName $n|Out-Null}
    Quiet
    Need ((Sha (Join-Path $old 'paper_runtime_control.json')) -ceq [string]$record.original_control_sha256) 'control changed'
    $null=Verify-Stage
    foreach($n in $names){
      $a=$actions[$n]
      # Change ONLY action; all existing triggers, principal, settings, and task XML retained.
      $actionParams=@{Execute=$a.execute;Argument=$a.arguments}
      if(-not [string]::IsNullOrWhiteSpace($a.working_directory)){$actionParams['WorkingDirectory']=$a.working_directory}
      $newAction=New-ScheduledTaskAction @actionParams
      Set-ScheduledTask -TaskName $n -Action $newAction -ErrorAction Stop | Out-Null
      $bound=Task $n
      Need (@($bound.Actions).Count -eq 1 -and
            [string]$bound.Actions[0].Arguments -ceq [string]$a.arguments) ('new task action mismatch '+$n)
    }
    $record.status='TASKS_REBOUND_OLD_CHILDREN_QUIESCED'
    Save $maintenance $record
    foreach($n in $names){
      if($saved[$n].enabled -eq $true){Enable-ScheduledTask -TaskName $n|Out-Null}
      if($saved[$n].enabled -eq $true -and $saved[$n].running -eq $true){Start-ScheduledTask -TaskName $n -ErrorAction Stop}
    }
    # Do not pretend an old HEALTHY file proves new code. Require a new
    # heartbeat produced after task activation while the new PID is actually bound.
    $started=[datetime]::UtcNow
    $deadline=$started.AddSeconds(240)
    $healthy=$false
    do{
      $hbPath=Join-Path $root 'State\v2r4-paper-candidate-runtime-heartbeat.json'
      if(Test-Path -LiteralPath $hbPath){
        try{
          $hb=Get-Content -LiteralPath $hbPath -Raw | ConvertFrom-Json
          $hbAt=([datetime]$hb.checked_at_utc).ToUniversalTime()
          $processes=@(ActiveChildren | Where-Object {([string]$_.CommandLine).Replace('\','/').IndexOf($stageFile.Replace('\','/'),[StringComparison]::OrdinalIgnoreCase) -ge 0})
          if([string]$hb.status -ceq 'HEALTHY' -and $hbAt -gt $started -and
             ($hbAt-[datetime]::UtcNow).TotalSeconds -le 5 -and
             $processes.Count -gt 0 -and
             @($processes | Where-Object {([datetime]$_.CreationDate).ToUniversalTime() -le $hbAt}).Count -gt 0 -and (Sha $stageFile) -ceq [string]$m.new_file_sha256){
            $healthy=$true
          }
        }catch{}
      }
      if(-not $healthy){Start-Sleep -Seconds 2}
    }while(-not $healthy -and [datetime]::UtcNow -lt $deadline)
    Need $healthy 'fresh new-code Candidates HEALTHY not proven within bounded window'
    if($saved[$supervisor].enabled -eq $true){Enable-ScheduledTask -TaskName $supervisor|Out-Null}
    if($saved[$supervisor].enabled -eq $true -and $saved[$supervisor].running -eq $true){Start-ScheduledTask -TaskName $supervisor -ErrorAction Stop}
    $record.status='NEW_CODE_HEALTHY_ORIGINAL_BACKUP_RETAINED'
    $record.healthy_at_utc=$hbAt.ToString('o')
    Save $maintenance $record
    [pscustomobject]@{status=$record.status;commit=$pin;code_sha256=$m.new_file_sha256;heartbeat_utc=$record.healthy_at_utc;backup=$backup;wait_cloudsync_untouched=$true}|ConvertTo-Json
  }catch{
    $why=$_.Exception.Message
    # A failure after task changes is only safely rolled back after stopping
    # both task owners and verifying NO residual candidate/evaluator children.
    try{
      foreach($n in @($names)+@($supervisor)){StopBounded $n;Disable-ScheduledTask -TaskName $n|Out-Null}
      Quiet
      Restore-Tasks $backup $true
      $record.status='ROLLBACK_RESTORED_AFTER_ERROR'
      $record.reason=$why
      Save $maintenance $record
    }catch{
      $record.status='FAIL_CLOSED_MANUAL_RECOVERY_REQUIRED'
      $record.reason=$why
      $record.recovery_error=$_.Exception.Message
      Save $maintenance $record
      throw ('PR666_FAIL_CLOSED: '+$why+'; '+$record.recovery_error)
    }
    throw ('PR666_ROLLED_BACK: '+$why)
  }
  return
}
# Nonmutating default or opt-in isolated inert staging.
Need (Test-Path -LiteralPath $source -PathType Container) 'source checkout absent'
$head=(& git -C $source rev-parse HEAD 2>$null)
Need ($LASTEXITCODE -eq 0 -and [string]$head -match '^[0-9a-f]{40}$') 'source HEAD absent'
& git -C $source merge-base --is-ancestor $pin HEAD 2>$null
Need ($LASTEXITCODE -eq 0) 'PR666 merge commit is not ancestor'
& git -C $source diff --quiet $pin HEAD -- 'tools/v2r4-paper-local-runtime.py'
Need ($LASTEXITCODE -eq 0) 'candidate diverged after reviewed PR666'
$dirty=@(& git -C $source status --porcelain --untracked-files=normal 2>$null | Where-Object {$_})
Need ($LASTEXITCODE -eq 0 -and $dirty.Count -eq 0) 'source checkout dirty'
Need ((Sha (Join-Path $old $file)) -ceq $oldSha.ToLowerInvariant()) 'original candidate changed'
Need ((Sha $sourceFile) -cne $oldSha.ToLowerInvariant()) 'no reviewed PR666 change'
Check-Preflight
if(Test-Path -LiteralPath $new){
  $existing=Verify-Stage
  [pscustomobject]@{status='ALREADY_INERT_STAGED_NO_CHANGE';commit=$pin;sha256=$existing.new_file_sha256}|ConvertTo-Json
  return
}
if(-not $Stage){
  [pscustomobject]@{status='READ_ONLY_READY_NO_MUTATION';commit=$pin;new_file_sha256=(Sha $sourceFile);target=$new;series=$series}|ConvertTo-Json
  return
}
Need ($Confirm -ceq 'STAGE_PR666_INERT_ONLY') 'separate inert staging confirmation absent'
New-Item -ItemType Directory -Path $new -ErrorAction Stop|Out-Null
try{
  Copy-Item -LiteralPath $sourceFile -Destination $stageFile -ErrorAction Stop
  Need ((Sha $stageFile) -ceq (Sha $sourceFile)) 'PR666 byte copy mismatch'
  # Import closure in the script's new directory. Copy only *.py from the
  # immutable old release; no old control, decisions, queue, tokens or state.
  foreach($sub in @('market_data','paper_evaluator')){
    $from=Join-Path $old $sub
    Need (Test-Path -LiteralPath $from -PathType Container) ('original dependency directory missing '+$sub)
    $files=@(Get-ChildItem -LiteralPath $from -File -Recurse -Filter '*.py')
    Need ($files.Count -gt 0) ('no dependency Python sources '+$sub)
    foreach($f in $files){
      $rel=$f.FullName.Substring($old.Length).TrimStart('\')
      $dest=Join-Path $new $rel
      New-Item -ItemType Directory -Path (Split-Path $dest -Parent) -Force | Out-Null
      Copy-Item -LiteralPath $f.FullName -Destination $dest -ErrorAction Stop
      Need ((Sha $dest) -ceq (Sha $f.FullName)) ('dependency SHA mismatch '+$rel)
    }
  }
  $files=Inventory $new
  Need ($files.Count -ge 3) 'incomplete stage'
  $payload=[ordered]@{
    kind='V2R4_PR666_SCOPED_STAGE_V2';status='INERT_NO_TASK_CHANGE'
    commit=$pin;series_id=$series;old_file_sha256=$oldSha.ToLowerInvariant()
    new_file_sha256=(Sha $stageFile);files=@($files)
    tasks_mutated=$false;cloud_mutated=$false;wait_cloudsync_mutated=$false
  }
  Save $manifest $payload
  $null=Verify-Stage
  [pscustomobject]@{status='INERT_STAGE_VERIFIED_NOT_INSTALLED';commit=$pin;sha256=$payload.new_file_sha256;manifest_sha256=(Sha $manifest)}|ConvertTo-Json
}catch{throw ('PR666_INERT_STAGE_INCOMPLETE_NO_LIVE_MUTATION: '+$_.Exception.Message)}
 } |
      Where-Object {
        $cmd=([string]$_.CommandLine).Replace('\','/')
        $cmd.IndexOf($needleOld,[StringComparison]::OrdinalIgnoreCase) -ge 0 -or
        $cmd.IndexOf($needleNew,[StringComparison]::OrdinalIgnoreCase) -ge 0 -or
        $cmd.IndexOf($eval,[StringComparison]::OrdinalIgnoreCase) -ge 0 -or
        ($_.Name -match '(?i)^(?:powershell|pwsh)\.exe
}
function Quiet([int]$seconds=195){
  $end=(Get-Date).AddSeconds($seconds)
  do{
    $children=@(ActiveChildren)
    if($children.Count -eq 0){return}
    Start-Sleep -Milliseconds 500
  }while((Get-Date) -lt $end)
  throw ('PR666_HOLD: old/new Candidate or evaluator child alive PID='+(@($children|ForEach-Object{$_.ProcessId}) -join ','))
}
function StopBounded([string]$name){
  if([string](Task $name).State -ne 'Running'){return}
  Stop-ScheduledTask -TaskName $name -ErrorAction Stop
  $end=(Get-Date).AddSeconds(25)
  do {
    if([string](Task $name).State -ne 'Running'){return}
    Start-Sleep -Milliseconds 250
  }while((Get-Date) -lt $end)
  throw ('PR666_HOLD: task still running '+$name)
}
function Need-Admin {
  $principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
  Need ($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) 'Administrator required for task changes'
}
function Backup-Tasks([string]$directory){
  New-Item -ItemType Directory -Path $directory -ErrorAction Stop | Out-Null
  New-Item -ItemType Directory -Path (Join-Path $directory 'tasks') -ErrorAction Stop | Out-Null
  $states=[ordered]@{}
  foreach($n in @($names)+@($supervisor)){
    $t=Task $n
    $xml=Export-ScheduledTask -TaskName $n -ErrorAction Stop
    $xmlPath=Join-Path $directory ('tasks\'+$n+'.xml')
    [IO.File]::WriteAllText($xmlPath,$xml,[Text.UTF8Encoding]::new($false))
    $states[$n]=[ordered]@{
      enabled=([bool]$t.Settings.Enabled)
      running=([string]$t.State -eq 'Running')
      xml_sha256=(Sha $xmlPath)
    }
  }
  Save (Join-Path $directory 'task-states.json') $states
  return $states
}
function Restore-Tasks([string]$directory,[bool]$startPrevious){
  # NEVER restore/start old children alongside any successor child.
  Quiet 25
  $states=Get-Content -LiteralPath (Join-Path $directory 'task-states.json') -Raw | ConvertFrom-Json
  foreach($n in @($names)+@($supervisor)){
    $entry=$states.PSObject.Properties[$n]
    Need ($null -ne $entry) ('missing state '+$n)
    $p=Join-Path $directory ('tasks\'+$n+'.xml')
    Need ((Sha $p) -ceq [string]$entry.Value.xml_sha256) ('backup XML drift '+$n)
    Register-ScheduledTask -TaskName $n -Xml (Get-Content -LiteralPath $p -Raw) -Force -ErrorAction Stop | Out-Null
    if($entry.Value.enabled -eq $true){Enable-ScheduledTask -TaskName $n | Out-Null}
    else{Disable-ScheduledTask -TaskName $n | Out-Null}
  }
  if($startPrevious){
    foreach($n in @($names)+@($supervisor)){
      $entry=$states.PSObject.Properties[$n].Value
      if($entry.enabled -eq $true -and $entry.running -eq $true){Start-ScheduledTask -TaskName $n -ErrorAction Stop}
    }
  }
}
function Check-Preflight {
  Need (Test-Path -LiteralPath $old -PathType Container) 'original release absent'
  Need ((Sha (Join-Path $old $file)) -ceq $oldSha.ToLowerInvariant()) 'frozen original SHA mismatch'
  $c=Get-Content -LiteralPath (Join-Path $old 'paper_runtime_control.json') -Raw | ConvertFrom-Json
  Need ([string]$c.series_id -ceq $series -and $c.paper_only -eq $true -and
        $c.real_money_actions_enabled -eq $false) 'active PAPER guards or series drift'
  foreach($n in $names){$null=OriginalAction $n}
  # Disallow competing bounded operator and V3 transition.
  foreach($p in @('v2r4-technical-cutover-maintenance.json','v2r4-technical-cutover-operator-lock.json',
                 'v3-paper-cutover-maintenance.json','v3-experimental-old-intake-fence.json')){
    Need (-not (Test-Path -LiteralPath (Join-Path $root ('State\'+$p)))) ('conflicting transition '+$p)
  }
}
Need ((@([bool]$Stage,[bool]$Execute,[bool]$Rollback)|Where-Object {$_}).Count -le 1) 'choose exactly one mode'
Need (Test-Path -LiteralPath $root -PathType Container) 'Trading root missing'
if($Rollback){
  Need-Admin
  Need ($Confirm -ceq 'ROLLBACK_APPROVED_PR666_PAPER_ONLY') 'separate rollback authorization absent'
  Need (Test-Path -LiteralPath $maintenance -PathType Leaf) 'no persisted original task backup'
  $record=Get-Content -LiteralPath $maintenance -Raw|ConvertFrom-Json
  Need ([string]$record.kind -ceq 'V2R4_PR666_TASK_SWITCH_V1' -and
       [string]$record.commit -ceq $pin -and [string]$record.series_id -ceq $series) 'maintenance identity mismatch'
  # If uncertain process state or incomplete backup: do not arm any writer.
  foreach($n in @($names)+@($supervisor)){StopBounded $n; Disable-ScheduledTask -TaskName $n|Out-Null}
  Quiet
  Restore-Tasks ([string]$record.backup_directory) $true
  $record.status='ROLLED_BACK_ORIGINAL_TASKS_RESTORED'
  Save $maintenance $record
  [pscustomobject]@{status=$record.status;original_sha256=$oldSha;new_writer_stopped=$true;wait_cloudsync_untouched=$true}|ConvertTo-Json
  return
}
Need (-not(Test-Path -LiteralPath $maintenance)) 'prior switch/rollback receipt exists; do not repeat'
if($Execute){
  Need-Admin
  Need ($Confirm -ceq 'EXECUTE_APPROVED_PR666_CANDIDATES_LIFECYCLE_ONLY') 'separate productive authorization absent'
  Check-Preflight
  $m=Verify-Stage
  $actions=[ordered]@{}
  foreach($n in $names){
    $t=OriginalAction $n
    $a=$t.Actions[0]
    $oldQuoted='"'+(Join-Path $old $file)+'"'
    $newQuoted='"'+$stageFile+'"'
    $newArgs=([string]$a.Arguments).Replace($oldQuoted,$newQuoted)
    Need ($newArgs -cne [string]$a.Arguments -and $newArgs.Contains($newQuoted)) 'replacement failed'
    $actions[$n]=[ordered]@{execute=[string]$a.Execute;arguments=$newArgs;working_directory=[string]$a.WorkingDirectory}
  }
  Need (@(ActiveChildren | Where-Object {([string]$_.CommandLine).Replace('\','/').Contains($stageFile.Replace('\','/'))}).Count -eq 0) 'successor already executing'
  Need (Test-Path -LiteralPath $backupRoot -PathType Container) 'existing backup root missing'
  $backup=Join-Path $backupRoot ('v2r4-pr666-'+[datetime]::UtcNow.ToString('yyyyMMddTHHmmssZ'))
  $saved=Backup-Tasks $backup
  $record=[ordered]@{
    kind='V2R4_PR666_TASK_SWITCH_V1';status='PRECOMMIT_BACKUP_COMPLETE'
    series_id=$series;commit=$pin;new_file_sha256=[string]$m.new_file_sha256
    backup_directory=$backup;started_at_utc=[datetime]::UtcNow.ToString('o')
    original_control_sha256=(Sha (Join-Path $old 'paper_runtime_control.json'))
    wait_cloudsync_mutated=$false
  }
  Save $maintenance $record
  try{
    # Existing supervisor can rearm Candidates before a bounded swap; suspend ONLY
    # this supervisor task for the maintenance window. Other tasks are untouched.
    StopBounded $supervisor
    Disable-ScheduledTask -TaskName $supervisor | Out-Null
    foreach($n in $names){StopBounded $n;Disable-ScheduledTask -TaskName $n|Out-Null}
    Quiet
    Need ((Sha (Join-Path $old 'paper_runtime_control.json')) -ceq [string]$record.original_control_sha256) 'control changed'
    $null=Verify-Stage
    foreach($n in $names){
      $a=$actions[$n]
      # Change ONLY action; all existing triggers, principal, settings, and task XML retained.
      $newAction=New-ScheduledTaskAction -Execute $a.execute -Argument $a.arguments -WorkingDirectory $a.working_directory
      Set-ScheduledTask -TaskName $n -Action $newAction -ErrorAction Stop | Out-Null
      $bound=Task $n
      Need (@($bound.Actions).Count -eq 1 -and
            [string]$bound.Actions[0].Arguments -ceq [string]$a.arguments) ('new task action mismatch '+$n)
    }
    $record.status='TASKS_REBOUND_OLD_CHILDREN_QUIESCED'
    Save $maintenance $record
    foreach($n in $names){
      if($saved[$n].enabled -eq $true){Enable-ScheduledTask -TaskName $n|Out-Null}
      if($saved[$n].enabled -eq $true -and $saved[$n].running -eq $true){Start-ScheduledTask -TaskName $n -ErrorAction Stop}
    }
    # Do not pretend an old HEALTHY file proves new code. Require a new
    # heartbeat produced after task activation while the new PID is actually bound.
    $started=[datetime]::UtcNow
    $deadline=$started.AddSeconds(240)
    $healthy=$false
    do{
      $hbPath=Join-Path $root 'State\v2r4-paper-candidate-runtime-heartbeat.json'
      if(Test-Path -LiteralPath $hbPath){
        try{
          $hb=Get-Content -LiteralPath $hbPath -Raw | ConvertFrom-Json
          $hbAt=([datetime]$hb.checked_at_utc).ToUniversalTime()
          $processes=@(ActiveChildren | Where-Object {([string]$_.CommandLine).Replace('\','/').Contains($stageFile.Replace('\','/'))})
          if([string]$hb.status -ceq 'HEALTHY' -and $hbAt -gt $started -and
             ($hbAt-[datetime]::UtcNow).TotalSeconds -le 5 -and
             $processes.Count -gt 0 -and
             @($processes | Where-Object {([datetime]$_.CreationDate).ToUniversalTime() -le $hbAt}).Count -gt 0 -and (Sha $stageFile) -ceq [string]$m.new_file_sha256){
            $healthy=$true
          }
        }catch{}
      }
      if(-not $healthy){Start-Sleep -Seconds 2}
    }while(-not $healthy -and [datetime]::UtcNow -lt $deadline)
    Need $healthy 'fresh new-code Candidates HEALTHY not proven within bounded window'
    if($saved[$supervisor].enabled -eq $true){Enable-ScheduledTask -TaskName $supervisor|Out-Null}
    if($saved[$supervisor].enabled -eq $true -and $saved[$supervisor].running -eq $true){Start-ScheduledTask -TaskName $supervisor -ErrorAction Stop}
    $record.status='NEW_CODE_HEALTHY_ORIGINAL_BACKUP_RETAINED'
    $record.healthy_at_utc=$hbAt.ToString('o')
    Save $maintenance $record
    [pscustomobject]@{status=$record.status;commit=$pin;code_sha256=$m.new_file_sha256;heartbeat_utc=$record.healthy_at_utc;backup=$backup;wait_cloudsync_untouched=$true}|ConvertTo-Json
  }catch{
    $why=$_.Exception.Message
    # A failure after task changes is only safely rolled back after stopping
    # both task owners and verifying NO residual candidate/evaluator children.
    try{
      foreach($n in @($names)+@($supervisor)){StopBounded $n;Disable-ScheduledTask -TaskName $n|Out-Null}
      Quiet
      Restore-Tasks $backup $true
      $record.status='ROLLBACK_RESTORED_AFTER_ERROR'
      $record.reason=$why
      Save $maintenance $record
    }catch{
      $record.status='FAIL_CLOSED_MANUAL_RECOVERY_REQUIRED'
      $record.reason=$why
      $record.recovery_error=$_.Exception.Message
      Save $maintenance $record
      throw ('PR666_FAIL_CLOSED: '+$why+'; '+$record.recovery_error)
    }
    throw ('PR666_ROLLED_BACK: '+$why)
  }
  return
}
# Nonmutating default or opt-in isolated inert staging.
Need (Test-Path -LiteralPath $source -PathType Container) 'source checkout absent'
$head=(& git -C $source rev-parse HEAD 2>$null)
Need ($LASTEXITCODE -eq 0 -and [string]$head -match '^[0-9a-f]{40}$') 'source HEAD absent'
& git -C $source merge-base --is-ancestor $pin HEAD 2>$null
Need ($LASTEXITCODE -eq 0) 'PR666 merge commit is not ancestor'
& git -C $source diff --quiet $pin HEAD -- 'tools/v2r4-paper-local-runtime.py'
Need ($LASTEXITCODE -eq 0) 'candidate diverged after reviewed PR666'
$dirty=@(& git -C $source status --porcelain --untracked-files=normal 2>$null | Where-Object {$_})
Need ($LASTEXITCODE -eq 0 -and $dirty.Count -eq 0) 'source checkout dirty'
Need ((Sha (Join-Path $old $file)) -ceq $oldSha.ToLowerInvariant()) 'original candidate changed'
Need ((Sha $sourceFile) -cne $oldSha.ToLowerInvariant()) 'no reviewed PR666 change'
Check-Preflight
if(Test-Path -LiteralPath $new){
  $existing=Verify-Stage
  [pscustomobject]@{status='ALREADY_INERT_STAGED_NO_CHANGE';commit=$pin;sha256=$existing.new_file_sha256}|ConvertTo-Json
  return
}
if(-not $Stage){
  [pscustomobject]@{status='READ_ONLY_READY_NO_MUTATION';commit=$pin;new_file_sha256=(Sha $sourceFile);target=$new;series=$series}|ConvertTo-Json
  return
}
Need ($Confirm -ceq 'STAGE_PR666_INERT_ONLY') 'separate inert staging confirmation absent'
New-Item -ItemType Directory -Path $new -ErrorAction Stop|Out-Null
try{
  Copy-Item -LiteralPath $sourceFile -Destination $stageFile -ErrorAction Stop
  Need ((Sha $stageFile) -ceq (Sha $sourceFile)) 'PR666 byte copy mismatch'
  # Import closure in the script's new directory. Copy only *.py from the
  # immutable old release; no old control, decisions, queue, tokens or state.
  foreach($sub in @('market_data','paper_evaluator')){
    $from=Join-Path $old $sub
    Need (Test-Path -LiteralPath $from -PathType Container) ('original dependency directory missing '+$sub)
    $files=@(Get-ChildItem -LiteralPath $from -File -Recurse -Filter '*.py')
    Need ($files.Count -gt 0) ('no dependency Python sources '+$sub)
    foreach($f in $files){
      $rel=$f.FullName.Substring($old.Length).TrimStart('\')
      $dest=Join-Path $new $rel
      New-Item -ItemType Directory -Path (Split-Path $dest -Parent) -Force | Out-Null
      Copy-Item -LiteralPath $f.FullName -Destination $dest -ErrorAction Stop
      Need ((Sha $dest) -ceq (Sha $f.FullName)) ('dependency SHA mismatch '+$rel)
    }
  }
  $files=Inventory $new
  Need ($files.Count -ge 3) 'incomplete stage'
  $payload=[ordered]@{
    kind='V2R4_PR666_SCOPED_STAGE_V2';status='INERT_NO_TASK_CHANGE'
    commit=$pin;series_id=$series;old_file_sha256=$oldSha.ToLowerInvariant()
    new_file_sha256=(Sha $stageFile);files=@($files)
    tasks_mutated=$false;cloud_mutated=$false;wait_cloudsync_mutated=$false
  }
  Save $manifest $payload
  $null=Verify-Stage
  [pscustomobject]@{status='INERT_STAGE_VERIFIED_NOT_INSTALLED';commit=$pin;sha256=$payload.new_file_sha256;manifest_sha256=(Sha $manifest)}|ConvertTo-Json
}catch{throw ('PR666_INERT_STAGE_INCOMPLETE_NO_LIVE_MUTATION: '+$_.Exception.Message)}
 -and
         $cmd.IndexOf($supervisorScript,[StringComparison]::OrdinalIgnoreCase) -ge 0)
      } | Select-Object ProcessId,CreationDate,CommandLine
  )
}
function Quiet([int]$seconds=195){
  $end=(Get-Date).AddSeconds($seconds)
  do{
    $children=@(ActiveChildren)
    if($children.Count -eq 0){return}
    Start-Sleep -Milliseconds 500
  }while((Get-Date) -lt $end)
  throw ('PR666_HOLD: old/new Candidate or evaluator child alive PID='+(@($children|ForEach-Object{$_.ProcessId}) -join ','))
}
function StopBounded([string]$name){
  if([string](Task $name).State -ne 'Running'){return}
  Stop-ScheduledTask -TaskName $name -ErrorAction Stop
  $end=(Get-Date).AddSeconds(25)
  do {
    if([string](Task $name).State -ne 'Running'){return}
    Start-Sleep -Milliseconds 250
  }while((Get-Date) -lt $end)
  throw ('PR666_HOLD: task still running '+$name)
}
function Need-Admin {
  $principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
  Need ($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) 'Administrator required for task changes'
}
function Backup-Tasks([string]$directory){
  New-Item -ItemType Directory -Path $directory -ErrorAction Stop | Out-Null
  New-Item -ItemType Directory -Path (Join-Path $directory 'tasks') -ErrorAction Stop | Out-Null
  $states=[ordered]@{}
  foreach($n in @($names)+@($supervisor)){
    $t=Task $n
    $xml=Export-ScheduledTask -TaskName $n -ErrorAction Stop
    $xmlPath=Join-Path $directory ('tasks\'+$n+'.xml')
    [IO.File]::WriteAllText($xmlPath,$xml,[Text.UTF8Encoding]::new($false))
    $states[$n]=[ordered]@{
      enabled=([bool]$t.Settings.Enabled)
      running=([string]$t.State -eq 'Running')
      xml_sha256=(Sha $xmlPath)
    }
  }
  Save (Join-Path $directory 'task-states.json') $states
  return $states
}
function Restore-Tasks([string]$directory,[bool]$startPrevious){
  # NEVER restore/start old children alongside any successor child.
  Quiet 25
  $states=Get-Content -LiteralPath (Join-Path $directory 'task-states.json') -Raw | ConvertFrom-Json
  foreach($n in @($names)+@($supervisor)){
    $entry=$states.PSObject.Properties[$n]
    Need ($null -ne $entry) ('missing state '+$n)
    $p=Join-Path $directory ('tasks\'+$n+'.xml')
    Need ((Sha $p) -ceq [string]$entry.Value.xml_sha256) ('backup XML drift '+$n)
    Register-ScheduledTask -TaskName $n -Xml (Get-Content -LiteralPath $p -Raw) -Force -ErrorAction Stop | Out-Null
    if($entry.Value.enabled -eq $true){Enable-ScheduledTask -TaskName $n | Out-Null}
    else{Disable-ScheduledTask -TaskName $n | Out-Null}
  }
  if($startPrevious){
    foreach($n in @($names)+@($supervisor)){
      $entry=$states.PSObject.Properties[$n].Value
      if($entry.enabled -eq $true -and $entry.running -eq $true){Start-ScheduledTask -TaskName $n -ErrorAction Stop}
    }
  }
}
function Check-Preflight {
  Need (Test-Path -LiteralPath $old -PathType Container) 'original release absent'
  Need ((Sha (Join-Path $old $file)) -ceq $oldSha.ToLowerInvariant()) 'frozen original SHA mismatch'
  $c=Get-Content -LiteralPath (Join-Path $old 'paper_runtime_control.json') -Raw | ConvertFrom-Json
  Need ([string]$c.series_id -ceq $series -and $c.paper_only -eq $true -and
        $c.real_money_actions_enabled -eq $false) 'active PAPER guards or series drift'
  foreach($n in $names){$null=OriginalAction $n}
  # Disallow competing bounded operator and V3 transition.
  foreach($p in @('v2r4-technical-cutover-maintenance.json','v2r4-technical-cutover-operator-lock.json',
                 'v3-paper-cutover-maintenance.json','v3-experimental-old-intake-fence.json')){
    Need (-not (Test-Path -LiteralPath (Join-Path $root ('State\'+$p)))) ('conflicting transition '+$p)
  }
}
Need ((@([bool]$Stage,[bool]$Execute,[bool]$Rollback)|Where-Object {$_}).Count -le 1) 'choose exactly one mode'
Need (Test-Path -LiteralPath $root -PathType Container) 'Trading root missing'
if($Rollback){
  Need-Admin
  Need ($Confirm -ceq 'ROLLBACK_APPROVED_PR666_PAPER_ONLY') 'separate rollback authorization absent'
  Need (Test-Path -LiteralPath $maintenance -PathType Leaf) 'no persisted original task backup'
  $record=Get-Content -LiteralPath $maintenance -Raw|ConvertFrom-Json
  Need ([string]$record.kind -ceq 'V2R4_PR666_TASK_SWITCH_V1' -and
       [string]$record.commit -ceq $pin -and [string]$record.series_id -ceq $series) 'maintenance identity mismatch'
  # If uncertain process state or incomplete backup: do not arm any writer.
  foreach($n in @($names)+@($supervisor)){StopBounded $n; Disable-ScheduledTask -TaskName $n|Out-Null}
  Quiet
  Restore-Tasks ([string]$record.backup_directory) $true
  $record.status='ROLLED_BACK_ORIGINAL_TASKS_RESTORED'
  Save $maintenance $record
  [pscustomobject]@{status=$record.status;original_sha256=$oldSha;new_writer_stopped=$true;wait_cloudsync_untouched=$true}|ConvertTo-Json
  return
}
Need (-not(Test-Path -LiteralPath $maintenance)) 'prior switch/rollback receipt exists; do not repeat'
if($Execute){
  Need-Admin
  Need ($Confirm -ceq 'EXECUTE_APPROVED_PR666_CANDIDATES_LIFECYCLE_ONLY') 'separate productive authorization absent'
  Check-Preflight
  $m=Verify-Stage
  $actions=[ordered]@{}
  foreach($n in $names){
    $t=OriginalAction $n
    $a=$t.Actions[0]
    $oldQuoted='"'+(Join-Path $old $file)+'"'
    $newQuoted='"'+$stageFile+'"'
    $newArgs=([string]$a.Arguments).Replace($oldQuoted,$newQuoted)
    Need ($newArgs -cne [string]$a.Arguments -and $newArgs.Contains($newQuoted)) 'replacement failed'
    $actions[$n]=[ordered]@{execute=[string]$a.Execute;arguments=$newArgs;working_directory=[string]$a.WorkingDirectory}
  }
  Need (@(ActiveChildren | Where-Object {([string]$_.CommandLine).Replace('\','/').Contains($stageFile.Replace('\','/'))}).Count -eq 0) 'successor already executing'
  Need (Test-Path -LiteralPath $backupRoot -PathType Container) 'existing backup root missing'
  $backup=Join-Path $backupRoot ('v2r4-pr666-'+[datetime]::UtcNow.ToString('yyyyMMddTHHmmssZ'))
  $saved=Backup-Tasks $backup
  $record=[ordered]@{
    kind='V2R4_PR666_TASK_SWITCH_V1';status='PRECOMMIT_BACKUP_COMPLETE'
    series_id=$series;commit=$pin;new_file_sha256=[string]$m.new_file_sha256
    backup_directory=$backup;started_at_utc=[datetime]::UtcNow.ToString('o')
    original_control_sha256=(Sha (Join-Path $old 'paper_runtime_control.json'))
    wait_cloudsync_mutated=$false
  }
  Save $maintenance $record
  try{
    # Existing supervisor can rearm Candidates before a bounded swap; suspend ONLY
    # this supervisor task for the maintenance window. Other tasks are untouched.
    StopBounded $supervisor
    Disable-ScheduledTask -TaskName $supervisor | Out-Null
    foreach($n in $names){StopBounded $n;Disable-ScheduledTask -TaskName $n|Out-Null}
    Quiet
    Need ((Sha (Join-Path $old 'paper_runtime_control.json')) -ceq [string]$record.original_control_sha256) 'control changed'
    $null=Verify-Stage
    foreach($n in $names){
      $a=$actions[$n]
      # Change ONLY action; all existing triggers, principal, settings, and task XML retained.
      $newAction=New-ScheduledTaskAction -Execute $a.execute -Argument $a.arguments -WorkingDirectory $a.working_directory
      Set-ScheduledTask -TaskName $n -Action $newAction -ErrorAction Stop | Out-Null
      $bound=Task $n
      Need (@($bound.Actions).Count -eq 1 -and
            [string]$bound.Actions[0].Arguments -ceq [string]$a.arguments) ('new task action mismatch '+$n)
    }
    $record.status='TASKS_REBOUND_OLD_CHILDREN_QUIESCED'
    Save $maintenance $record
    foreach($n in $names){
      if($saved[$n].enabled -eq $true){Enable-ScheduledTask -TaskName $n|Out-Null}
      if($saved[$n].enabled -eq $true -and $saved[$n].running -eq $true){Start-ScheduledTask -TaskName $n -ErrorAction Stop}
    }
    # Do not pretend an old HEALTHY file proves new code. Require a new
    # heartbeat produced after task activation while the new PID is actually bound.
    $started=[datetime]::UtcNow
    $deadline=$started.AddSeconds(240)
    $healthy=$false
    do{
      $hbPath=Join-Path $root 'State\v2r4-paper-candidate-runtime-heartbeat.json'
      if(Test-Path -LiteralPath $hbPath){
        try{
          $hb=Get-Content -LiteralPath $hbPath -Raw | ConvertFrom-Json
          $hbAt=([datetime]$hb.checked_at_utc).ToUniversalTime()
          $processes=@(ActiveChildren | Where-Object {([string]$_.CommandLine).Replace('\','/').Contains($stageFile.Replace('\','/'))})
          if([string]$hb.status -ceq 'HEALTHY' -and $hbAt -gt $started -and
             ($hbAt-[datetime]::UtcNow).TotalSeconds -le 5 -and
             $processes.Count -gt 0 -and
             @($processes | Where-Object {([datetime]$_.CreationDate).ToUniversalTime() -le $hbAt}).Count -gt 0 -and (Sha $stageFile) -ceq [string]$m.new_file_sha256){
            $healthy=$true
          }
        }catch{}
      }
      if(-not $healthy){Start-Sleep -Seconds 2}
    }while(-not $healthy -and [datetime]::UtcNow -lt $deadline)
    Need $healthy 'fresh new-code Candidates HEALTHY not proven within bounded window'
    if($saved[$supervisor].enabled -eq $true){Enable-ScheduledTask -TaskName $supervisor|Out-Null}
    if($saved[$supervisor].enabled -eq $true -and $saved[$supervisor].running -eq $true){Start-ScheduledTask -TaskName $supervisor -ErrorAction Stop}
    $record.status='NEW_CODE_HEALTHY_ORIGINAL_BACKUP_RETAINED'
    $record.healthy_at_utc=$hbAt.ToString('o')
    Save $maintenance $record
    [pscustomobject]@{status=$record.status;commit=$pin;code_sha256=$m.new_file_sha256;heartbeat_utc=$record.healthy_at_utc;backup=$backup;wait_cloudsync_untouched=$true}|ConvertTo-Json
  }catch{
    $why=$_.Exception.Message
    # A failure after task changes is only safely rolled back after stopping
    # both task owners and verifying NO residual candidate/evaluator children.
    try{
      foreach($n in @($names)+@($supervisor)){StopBounded $n;Disable-ScheduledTask -TaskName $n|Out-Null}
      Quiet
      Restore-Tasks $backup $true
      $record.status='ROLLBACK_RESTORED_AFTER_ERROR'
      $record.reason=$why
      Save $maintenance $record
    }catch{
      $record.status='FAIL_CLOSED_MANUAL_RECOVERY_REQUIRED'
      $record.reason=$why
      $record.recovery_error=$_.Exception.Message
      Save $maintenance $record
      throw ('PR666_FAIL_CLOSED: '+$why+'; '+$record.recovery_error)
    }
    throw ('PR666_ROLLED_BACK: '+$why)
  }
  return
}
# Nonmutating default or opt-in isolated inert staging.
Need (Test-Path -LiteralPath $source -PathType Container) 'source checkout absent'
$head=(& git -C $source rev-parse HEAD 2>$null)
Need ($LASTEXITCODE -eq 0 -and [string]$head -match '^[0-9a-f]{40}$') 'source HEAD absent'
& git -C $source merge-base --is-ancestor $pin HEAD 2>$null
Need ($LASTEXITCODE -eq 0) 'PR666 merge commit is not ancestor'
& git -C $source diff --quiet $pin HEAD -- 'tools/v2r4-paper-local-runtime.py'
Need ($LASTEXITCODE -eq 0) 'candidate diverged after reviewed PR666'
$dirty=@(& git -C $source status --porcelain --untracked-files=normal 2>$null | Where-Object {$_})
Need ($LASTEXITCODE -eq 0 -and $dirty.Count -eq 0) 'source checkout dirty'
Need ((Sha (Join-Path $old $file)) -ceq $oldSha.ToLowerInvariant()) 'original candidate changed'
Need ((Sha $sourceFile) -cne $oldSha.ToLowerInvariant()) 'no reviewed PR666 change'
Check-Preflight
if(Test-Path -LiteralPath $new){
  $existing=Verify-Stage
  [pscustomobject]@{status='ALREADY_INERT_STAGED_NO_CHANGE';commit=$pin;sha256=$existing.new_file_sha256}|ConvertTo-Json
  return
}
if(-not $Stage){
  [pscustomobject]@{status='READ_ONLY_READY_NO_MUTATION';commit=$pin;new_file_sha256=(Sha $sourceFile);target=$new;series=$series}|ConvertTo-Json
  return
}
Need ($Confirm -ceq 'STAGE_PR666_INERT_ONLY') 'separate inert staging confirmation absent'
New-Item -ItemType Directory -Path $new -ErrorAction Stop|Out-Null
try{
  Copy-Item -LiteralPath $sourceFile -Destination $stageFile -ErrorAction Stop
  Need ((Sha $stageFile) -ceq (Sha $sourceFile)) 'PR666 byte copy mismatch'
  # Import closure in the script's new directory. Copy only *.py from the
  # immutable old release; no old control, decisions, queue, tokens or state.
  foreach($sub in @('market_data','paper_evaluator')){
    $from=Join-Path $old $sub
    Need (Test-Path -LiteralPath $from -PathType Container) ('original dependency directory missing '+$sub)
    $files=@(Get-ChildItem -LiteralPath $from -File -Recurse -Filter '*.py')
    Need ($files.Count -gt 0) ('no dependency Python sources '+$sub)
    foreach($f in $files){
      $rel=$f.FullName.Substring($old.Length).TrimStart('\')
      $dest=Join-Path $new $rel
      New-Item -ItemType Directory -Path (Split-Path $dest -Parent) -Force | Out-Null
      Copy-Item -LiteralPath $f.FullName -Destination $dest -ErrorAction Stop
      Need ((Sha $dest) -ceq (Sha $f.FullName)) ('dependency SHA mismatch '+$rel)
    }
  }
  $files=Inventory $new
  Need ($files.Count -ge 3) 'incomplete stage'
  $payload=[ordered]@{
    kind='V2R4_PR666_SCOPED_STAGE_V2';status='INERT_NO_TASK_CHANGE'
    commit=$pin;series_id=$series;old_file_sha256=$oldSha.ToLowerInvariant()
    new_file_sha256=(Sha $stageFile);files=@($files)
    tasks_mutated=$false;cloud_mutated=$false;wait_cloudsync_mutated=$false
  }
  Save $manifest $payload
  $null=Verify-Stage
  [pscustomobject]@{status='INERT_STAGE_VERIFIED_NOT_INSTALLED';commit=$pin;sha256=$payload.new_file_sha256;manifest_sha256=(Sha $manifest)}|ConvertTo-Json
}catch{throw ('PR666_INERT_STAGE_INCOMPLETE_NO_LIVE_MUTATION: '+$_.Exception.Message)}
