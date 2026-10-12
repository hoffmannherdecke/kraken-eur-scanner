param(
 [string]$TradingRoot=(Join-Path $env:USERPROFILE 'Trading'),
 [switch]$Execute,
 [string]$Confirm='',
 [int]$Hours=28
)
# Installs ONE bounded local V3 research-only observer task, NEVER V3
# trading/Paper activation and NEVER V2R4 task mutation. Must be explicit.
$ErrorActionPreference='Stop'
$taskName='CryptoMiniPC-V3CanaryObservation28h'
$repo=Join-Path $TradingRoot 'Repos\kraken-eur-scanner'
$venv=Join-Path $TradingRoot 'Runtime\kraken-eur-scanner-venv\Scripts\python.exe'
$root=Join-Path $TradingRoot 'Research\V3Paper'
$journal=Join-Path $root 'journal'
$capture=Join-Path $root 'capture'
$state=Join-Path $TradingRoot 'State'
$logs=Join-Path $TradingRoot 'Logs'
$secret=Join-Path $TradingRoot 'Secrets\v3-paper-relay-token.txt'
$runner=Join-Path $repo 'tools\minipc-v3-bounded-canary-observer-task.ps1'
$planPath=Join-Path $state 'v3-canary-observer-28h-plan.json'
$old='PAPER-V2R4-20261009T110135Z'
if($Hours -ne 28){throw 'Exactly 28 hours for first bounded V3 observational test'}
if(-not $Execute){
 [pscustomobject]@{kind='V3_CANARY_BOUNDED_LOCAL_OBSERVER_PLAN_V1'
   status='PLAN_ONLY_NO_WINDOWS_TASK_MODIFIED'
   task=$taskName;duration_hours=28;interval_minutes=5
   max_tracked_canary_candidates=2
   model_calls_authorized=0
   orders=$false;v2r4_untouched=$true
   explicit_confirmation='RUN_V3_CANARY_READONLY_28H'
 } | ConvertTo-Json
 exit 0
}
if($Confirm -cne 'RUN_V3_CANARY_READONLY_28H'){
 throw 'Explicit bounded CANARY task confirmation missing'
}
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$principal=[Security.Principal.WindowsPrincipal]::new($identity)
if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){
 throw 'Run in administrator PowerShell'
}
foreach($file in @($repo,$venv,$journal,$capture,$state,$logs,$secret,$runner)){
 if(!(Test-Path -LiteralPath $file)){
  throw "Required existing local V3-only path missing: $file"
 }
}
if(Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue){
 throw 'V3 bounded task already installed: no duplicate registration or automatic extension'
}
if(Test-Path -LiteralPath $planPath -PathType Leaf){
 throw 'Existing immutable 28h manifest: re-use or explicitly review, do not replace'
}
$oldApps=@(Get-ChildItem (Join-Path $TradingRoot 'Runtime') -Directory |
 Where-Object{Test-Path (Join-Path $_.FullName 'paper_runtime_control.json')} |
 Where-Object{
  try{
   (Get-Content (Join-Path $_.FullName 'paper_runtime_control.json') -Raw |
    ConvertFrom-Json).series_id -eq $old
  }catch{$false}
 })
if($oldApps.Count -ne 1){throw 'Frozen V2R4 Paper runtime identity not singular'}
$oldControl=Get-Content (Join-Path $oldApps[0].FullName 'paper_runtime_control.json') -Raw|ConvertFrom-Json
if($oldControl.paper_only -ne $true -or $oldControl.real_money_actions_enabled -ne $false){
 throw 'Unsafe old Paper runtime permissions'
}
if(!(Test-Path -LiteralPath (Join-Path $oldApps[0].FullName 'handoff_queue'))){
 throw 'Original frozen V2R4 handoff archive missing'
}
if(@(Get-ChildItem $journal -Filter '*.json' -File).Count -lt 4){
 throw 'Existing independently verified V3 original journal absent'
}
$toPin=@(
 'tools\minipc-v3-bounded-canary-observer-task.ps1',
 'tools\run-minipc-v3-existing-canary-observation.ps1',
 'paper_evaluator\v3_paper_minipc_selective_tick_v1.py',
 'paper_evaluator\v3_paper_wait_observer_v1.py',
 'paper_evaluator\v3_paper_minipc_closed_1m_capture_v1.py',
 'paper_evaluator\v3_paper_missed_opportunity_followup_v1.py',
 'paper_evaluator\v3_paper_minipc_followup_v1.py',
 'paper_evaluator\v3_experimental_paper_journal_v1.py',
 'paper_evaluator\v3_paper_cloud_receipt_sync_v1.py'
)
$hashes=@(foreach($rel in $toPin){
 $file=Join-Path $repo $rel
 if(!(Test-Path -LiteralPath $file -PathType Leaf)){throw "V3 pinned source missing: $rel"}
 [ordered]@{
  relative_path=$rel
  sha256=(Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
 }
})
$start=(Get-Date).AddMinutes(2)
$deadline=$start.ToUniversalTime().AddHours(28).ToString('o')
$manifest=[ordered]@{
 kind='V3_LOCAL_READONLY_CANARY_28H_PLAN_V1'
 created_at_utc=(Get-Date).ToUniversalTime().ToString('o')
 until_utc=$deadline
 paper_only=$true;orders=$false
 model_http_calls_authorized=0;v2r4_unchanged=$true
 max_original_canary_candidates=2
 task_name=$taskName;repetition_minutes=5
 pinned_file_hashes=$hashes
 human_confirmation='RUN_V3_CANARY_READONLY_28H'
}
# An installation does not start the task; first store immutable provenance.
$body=$manifest|ConvertTo-Json -Depth 9
$handle=[System.IO.File]::Open($planPath,[System.IO.FileMode]::CreateNew,
  [System.IO.FileAccess]::Write,[System.IO.FileShare]::None)
try{
 $bytes=[System.Text.UTF8Encoding]::new($false).GetBytes($body)
 $handle.Write($bytes,0,$bytes.Length);$handle.Flush($true)
}finally{$handle.Dispose()}
$arguments=@(
 '-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass',
 '-File',('"'+$runner+'"'),
 '-TradingRoot',('"'+$TradingRoot+'"'),
 '-UntilUtc',('"'+$deadline+'"')
) -join ' '
$action=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments
$trigger=New-ScheduledTaskTrigger -Once -At $start -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Hours 28)
$settings=New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -RestartCount 0 -ExecutionTimeLimit (New-TimeSpan -Minutes 4)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -User 'SYSTEM' -RunLevel Highest -ErrorAction Stop | Out-Null
$installed=Get-ScheduledTask -TaskName $taskName -ErrorAction Stop
if(-not $installed){throw 'Windows Task Scheduler did not verify the new V3-only task'}
[pscustomobject]@{
 status='V3_READONLY_28H_TASK_INSTALLED_AWAIT_FIRST_PHYSICAL_TICK'
 task=$taskName;windows_task_state=[string]$installed.State
 first_tick_not_yet_proven=$true;repeat_minutes=5
 expires_at_utc=$deadline;max_canaries=2
 no_model=$true;orders=$false;v2r4_unchanged=$true
 next_verify_file=(Join-Path $state 'v3-canary-observer-28h-heartbeat.json')
} | ConvertTo-Json
