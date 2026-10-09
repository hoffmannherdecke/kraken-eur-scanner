param(
 [string]$TradingRoot=(Join-Path $env:USERPROFILE 'Trading'),
 [switch]$Recover,
 [string]$Confirm='',
 [switch]$SelfTest
)
# One-time local recovery AFTER an already committed atomic Paper rotation.
# No rotation RPC, no predecessor reactivation, no real-money API.
$ErrorActionPreference='Stop'
$oldId='PAPER-V2R4-20261007T184255Z'
$newId='PAPER-V2R4-20261009T110135Z'
$release='d8b35a8ec2e6f392f219b1c36cad95f3ad629b64'
$oldRelease='3c6729a6c548d169f56a97f07f75892f37211636'
$state=Join-Path $TradingRoot 'State'
$app=Join-Path $TradingRoot ('Runtime\v2r4-paper-stage-'+$release.Substring(0,12))
$oldApp=Join-Path $TradingRoot 'Runtime\v2r4-paper-app'
$python=Join-Path $TradingRoot 'Runtime\kraken-eur-scanner-venv\Scripts\python.exe'
$api=Join-Path $TradingRoot 'Secrets\openai-api-key.txt'
$nextState=Join-Path $state ('paper-v2r4-'+$newId)
$marker=Join-Path $state 'v2r4-technical-cutover-maintenance.json'
$lock=Join-Path $state 'v2r4-technical-cutover-operator-lock.json'
$complete=Join-Path $state 'v2r4-technical-cutover-completed.json'
$supervisor='CryptoMiniPC-RuntimeSupervisor'
$h3='CryptoMiniPC-V3H3Shadow001'
$tasks=@('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait','CryptoMiniPC-V2R4PaperLifecycle','CryptoMiniPC-V2R4PaperCloudSync')
function Need([bool]$ok,[string]$message){if(-not $ok){throw $message}}
function Atomic([string]$p,[object]$v){
 $tmp=$p+'.tmp'
 [IO.File]::WriteAllText($tmp,(ConvertTo-Json $v -Depth 14)+[Environment]::NewLine,[Text.UTF8Encoding]::new($false))
 Move-Item -LiteralPath $tmp -Destination $p -Force
}
function New-Action([string]$Executable,[string[]]$TaskArguments){
 Need (-not [string]::IsNullOrWhiteSpace($Executable)) 'Missing executable'
 Need ($TaskArguments.Count -ge 2) 'Missing task arguments'
 foreach($arg in $TaskArguments){
  Need (-not [string]::IsNullOrWhiteSpace([string]$arg)) 'Empty scheduled task argument'
  Need (-not ([string]$arg).Contains('"')) 'Unsupported quote in task argument'
 }
 $q=($TaskArguments | ForEach-Object{'"'+[string]$_+'"'}) -join ' '
 Need ($q.Length -gt 12) 'Empty generated action'
 New-ScheduledTaskAction -Execute $Executable -Argument $q
}
if($SelfTest){
 $action=New-Action 'C:\Windows\py.exe' @('C:\Trading\Runtime\paper\wait.py','--mode','once')
 Need ($action.Execute -eq 'C:\Windows\py.exe') 'Executable lost'
 Need ($action.Arguments.Contains('wait.py')) 'Arguments lost'
 '{"status":"SCHEDULED_TASK_ARGUMENTS_PASS","mutation":false}'
 return
}
function VerifyCloud{
 $a=(Get-Content -LiteralPath (Join-Path $TradingRoot 'Secrets\shadow-evidence-token.txt') -Raw).Trim()
 $b=(Get-Content -LiteralPath (Join-Path $TradingRoot 'Secrets\minipc-status-token.txt') -Raw).Trim()
 Need ($a.Length -ge 24 -and $b.Length -ge 24) 'Missing relay credentials'
 $c=Invoke-RestMethod -Uri 'https://nlgzjmqgwueojlyqmoru.supabase.co/functions/v1/v2r4-technical-cutover' -Method Post -Headers @{'X-Shadow-Evidence-Token'=$a;'X-MiniPC-Status-Token'=$b} -ContentType 'application/json' -Body '{"action":"status"}' -TimeoutSec 30
 Need ($c.ok -eq $true) 'Cloud rotation lookup failed'
 $active=@($c.paper_series | Where-Object {$_.status -eq 'active'})
 Need ($active.Count -eq 1 -and $active[0].series_id -ceq $newId -and $active[0].release_repo_sha -ceq $release -and $active[0].paper_only -eq $true -and $active[0].real_money_actions_enabled -eq $false) 'Cloud successor not uniquely active and safe'
 $closed=@($c.paper_series | Where-Object {$_.series_id -eq $oldId -and $_.status -eq 'technical_closed' -and $_.release_repo_sha -eq $oldRelease})
 Need ($closed.Count -eq 1) 'Predecessor is not immutable closed'
 Need ($c.rotation -and $c.rotation.predecessor_series_id -ceq $oldId -and $c.rotation.successor_series_id -ceq $newId) 'Committed rotation row missing'
 return $c
}
function Specs{
 @(
  [pscustomobject]@{Name='CryptoMiniPC-V2R4PaperCandidates';ArgList=[string[]]@((Join-Path $app 'v2r4-paper-local-runtime.py'),'--mode','candidates','--app-root',$app,'--trading-root',$TradingRoot,'--api-key-file',$api,'--paper-state-dir',$nextState,'--interval-seconds','2')},
  [pscustomobject]@{Name='CryptoMiniPC-V2R4PaperWait';ArgList=[string[]]@((Join-Path $app 'paper_evaluator\v2r4_wait_runtime.py'),'--decision-dir',(Join-Path $app 'paper_decisions'),'--recheck-dir',(Join-Path $app 'paper_rechecks'),'--candidate-dir',(Join-Path $app 'handoff_queue'),'--receipt-dir',(Join-Path $app 'paper_trigger_receipts'),'--state',(Join-Path $nextState 'wait-state.json'),'--heartbeat',(Join-Path $state 'v2r4-paper-wait-runtime-heartbeat.json'),'--altrady-log',(Join-Path $TradingRoot 'Logs\altrady-trigger-events.jsonl'),'--spec',(Join-Path $app 'paper_strategy_spec.json'),'--control',(Join-Path $app 'paper_runtime_control.json'),'--api-key-file',$api,'--fallback-seconds','10','--loop-seconds','1','--execute-recheck')},
  [pscustomobject]@{Name='CryptoMiniPC-V2R4PaperLifecycle';ArgList=[string[]]@((Join-Path $app 'v2r4-paper-local-runtime.py'),'--mode','lifecycle','--app-root',$app,'--trading-root',$TradingRoot,'--interval-seconds','60')},
  [pscustomobject]@{Name='CryptoMiniPC-V2R4PaperCloudSync';ArgList=[string[]]@((Join-Path $app 'v2r4-paper-cloud-sync.py'),'--app-root',$app,'--trading-root',$TradingRoot,'--paper-state-dir',$nextState,'--interval-seconds','60')}
 )
}
function StopSuccessor{
 foreach($n in $tasks){
  Stop-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue
  Disable-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue | Out-Null
 }
}
try{
 Need (-not (Test-Path -LiteralPath $complete)) 'Cutover already completed; do not recover'
 Need ((Test-Path -LiteralPath $marker) -and (Test-Path -LiteralPath $lock)) 'Recovery evidence markers missing'
 $m=Get-Content $marker -Raw|ConvertFrom-Json
 $l=Get-Content $lock -Raw|ConvertFrom-Json
 Need ($m.kind -eq 'V2R4_TECHNICAL_MAINTENANCE_V1' -and $m.phase -eq 'CLOUD_COMMITTED' -and $m.predecessor_series_id -ceq $oldId -and $m.successor_repo_sha -ceq $release) 'Maintenance phase is not committed'
 Need ($l.kind -eq 'V2R4_TECHNICAL_LOCK_V1' -and $l.sha -ceq $release) 'Incorrect recovery lock'
 Need ((Test-Path -LiteralPath $python) -and (Test-Path -LiteralPath $api)) 'Python or API credential file missing'
 $ctl=Get-Content (Join-Path $app 'paper_runtime_control.json') -Raw|ConvertFrom-Json
 Need ($ctl.series_id -ceq $newId -and $ctl.release_repo_sha -ceq $release -and $ctl.paper_only -eq $true -and $ctl.real_money_actions_enabled -eq $false -and $ctl.automatic_activation_allowed -eq $false -and [double]$ctl.scout_notional_eur -eq 50 -and [double]$ctl.stage2_notional_eur -eq 50) 'Unsafe or wrong successor runtime control'
 $stg=Get-Content (Join-Path $app 'technical-stage-manifest.json') -Raw|ConvertFrom-Json
 Need ($stg.source_repo_sha -ceq $release -and $stg.status -eq 'STAGED_INERT_NO_ACTIVATION') 'Frozen stage manifest mismatch'
 foreach($f in @($stg.prepared_file_hashes)){
  $p=Join-Path $app $f.relative_path.Replace('/','\')
  Need (Test-Path -LiteralPath $p -PathType Leaf) ('Missing staged file: '+$f.relative_path)
  Need ((Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant() -ceq $f.sha256) ('Altered stage file: '+$f.relative_path)
 }
 $backups=@(Get-ChildItem -LiteralPath (Join-Path $TradingRoot 'Backups') -Directory -Filter 'v2r4-technical-*'|Where-Object{Test-Path (Join-Path $_.FullName 'committed-manifest.json')})
 Need ($backups.Count -eq 1) 'Committed backup cannot be uniquely identified'
 $bk=$backups[0].FullName
 $proof=Get-Content (Join-Path $bk 'committed-manifest.json') -Raw|ConvertFrom-Json
 Need ($proof.new_series_id -ceq $newId -and $proof.old_series_id -ceq $oldId -and $proof.new_config.release_repo_sha -ceq $release) 'Committed proof wrong'
 $zip=Join-Path $bk 'old-paper-h3-state.zip'
 Need (Test-Path $zip -PathType Leaf) 'Frozen predecessor archive missing'
 Need ((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant() -ceq $proof.physical_proof.snapshot_sha256) 'Archived predecessor ZIP changed'
 foreach($n in @($tasks)+@($h3,$supervisor)){
  $t=Get-ScheduledTask -TaskName $n -ErrorAction Stop
  Need ([string]$t.State -eq 'Disabled') ('Task not disabled: '+$n)
 }
 $p1=[regex]::Escape($oldApp+'\')
 $p2=[regex]::Escape((Join-Path $TradingRoot 'Runtime\v3-h3-shadow-001')+'\')
 $p3=[regex]::Escape($app+'\')
 $running=@(Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" -ErrorAction Stop|Where-Object{ $cl=[string]$_.CommandLine; $cl -and ($cl -match $p1 -or $cl -match $p2 -or $cl -match $p3) })
 Need ($running.Count -eq 0) 'Potential orphaned first-series or successor Python writer; stop'
 $cloud=VerifyCloud
 $specs=@(Specs)
 Need ($specs.Count -eq 4) 'Wrong successor task count'
 foreach($sp in $specs){$null=New-Action -Executable $python -TaskArguments $sp.ArgList}
 if(-not $Recover){
  [pscustomobject]@{status='POSTCOMMIT_RECOVERY_PLAN_PASS_NO_MUTATION';series_id=$newId;orders=$false}|ConvertTo-Json
  return
 }
 Need ($Confirm -ceq 'RECOVER_ALREADY_COMMITTED_PAPER_ONLY') 'Explicit postcommit-only confirmation required'
 $identity=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
 Need ($identity.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) 'Administrator PowerShell required'
 $settings=New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
 foreach($sp in $specs){
  $action=New-Action -Executable $python -TaskArguments $sp.ArgList
  Register-ScheduledTask -TaskName $sp.Name -Action $action -Trigger (New-ScheduledTaskTrigger -AtStartup) -Settings $settings -User SYSTEM -RunLevel Highest -Force|Out-Null
  Disable-ScheduledTask -TaskName $sp.Name|Out-Null
 }
 foreach($sp in $specs){
  $task=Get-ScheduledTask -TaskName $sp.Name
  Need ($task.Actions[0].Execute -ieq $python -and $task.Actions[0].Arguments.IndexOf($app,[StringComparison]::OrdinalIgnoreCase) -ge 0) ('Invalid registered action: '+$sp.Name)
 }
 foreach($sp in $specs){
  Enable-ScheduledTask -TaskName $sp.Name|Out-Null
  Start-ScheduledTask -TaskName $sp.Name
 }
 $started=[datetime]::UtcNow;$deadline=$started.AddSeconds(180)
 $heartbeats=@('v2r4-paper-candidate-runtime-heartbeat.json','v2r4-paper-wait-runtime-heartbeat.json','v2r4-paper-lifecycle-heartbeat.json','v2r4-paper-cloud-sync-heartbeat.json')
 $healthy=$false
 do {
  Start-Sleep -Seconds 3;$healthy=$true
  foreach($n in $heartbeats){
   try{
    $h=Get-Content (Join-Path $state $n) -Raw|ConvertFrom-Json
    if($h.status -ne 'HEALTHY' -or ([datetime]$h.checked_at_utc).ToUniversalTime() -lt $started -or $h.paper_only -ne $true -or $h.real_money_actions -ne $false -or $h.order_api -ne $false){$healthy=$false}
    if($n -in @('v2r4-paper-candidate-runtime-heartbeat.json','v2r4-paper-cloud-sync-heartbeat.json') -and $h.series_id -cne $newId){$healthy=$false}
   }catch{$healthy=$false}
  }
  foreach($n in $tasks){if([string](Get-ScheduledTask -TaskName $n).State -ne 'Running'){$healthy=$false}}
 }while(-not $healthy -and ([datetime]::UtcNow -lt $deadline))
 Need $healthy 'Successor heartbeat/worker health not confirmed after 180 seconds'
 $cloud=$null;$cloud=VerifyCloud
 Need ([string](Get-ScheduledTask -TaskName $h3).State -eq 'Disabled') 'Archived H3 unexpectedly running'
 Atomic $complete ([ordered]@{kind='V2R4_TECHNICAL_CUTOVER_COMPLETED_V1';completed_at_utc=[datetime]::UtcNow.ToString('o');predecessor_series_id=$oldId;successor_series_id=$newId;h3_001_retired=$true;orders=$false;real_money_actions=$false;snapshot_sha256=$proof.physical_proof.snapshot_sha256;release_repo_sha=$release;recovery_method='POSTCOMMIT_LOCAL_TASK_REPAIR_ONLY'})
 Enable-ScheduledTask -TaskName $supervisor|Out-Null
 Start-ScheduledTask -TaskName $supervisor
 Remove-Item -LiteralPath $marker,$lock -Force
 [pscustomobject]@{status='POSTCOMMIT_RECOVERED_PAPER_ONLY';series_id=$newId;orders=$false;real_money_actions=$false}|ConvertTo-Json
}catch{
 $msg=$_.Exception.Message
 if($Recover){StopSuccessor}
 [pscustomobject]@{status='BLOCKED';phase='POSTCOMMIT_RECOVERY';reason=$msg;retry_allowed=$false;orders=$false;real_money_actions=$false}|ConvertTo-Json
 if($Recover){exit 2}
}