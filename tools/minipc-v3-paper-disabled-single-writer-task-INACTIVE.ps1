param(
 [string]$TradingRoot='C:\Users\ADMIN\Trading',
 [string]$SourceRepo='C:\Users\ADMIN\V3Paper-Quelle-985ed3230bb4',
 [string]$CandidateStageSha='',
 [switch]$InstallDisabled,
 [string]$Confirm=''
)
# Original Issue99 native physical Task *identity stage*, not V3 activation.
# PREVIEW default. Optional install registers an ATOMICALLY DISABLED Task
# pointing only to the already physically verified --read-only V3 launcher.
# No stop/restart of old V2R4, no Cloud, CAS, model, orders or release proof.
$ErrorActionPreference='Stop'
$stageSha='d6853a08e608c1e56229e27939c40ba2f5d57f8b'
$candidateMode=(-not [string]::IsNullOrEmpty($CandidateStageSha))
if($candidateMode){
 if($CandidateStageSha -cnotmatch '^[0-9a-f]{40}$'){throw 'invalid full candidate SHA'}
 if($InstallDisabled -or $Confirm){throw 'candidate inspection must remain read-only'}
 $stageSha=$CandidateStageSha
}
$stageFiles=if($candidateMode){69}else{66}
$taskName='CryptoMiniPC-V3PaperSingleWriter'
$oldNames=@(
 'CryptoMiniPC-V2R4PaperCandidates',
 'CryptoMiniPC-V2R4PaperWait',
 'CryptoMiniPC-V2R4PaperLifecycle',
 'CryptoMiniPC-V2R4PaperCloudSync'
)
$oldScripts=@(
 'v2r4-paper-local-runtime.py',
 'wait_launcher.py',
 'v2r4-paper-local-runtime.py',
 'v2r4-paper-cloud-sync.py'
)
function Require([bool]$Accept,[string]$Reason){
 if(-not $Accept){throw ('V3_DISABLED_TASK_STAGE_BLOCKED: '+$Reason)}
}
function Sha([string]$Path) {
 Require ((Test-Path -LiteralPath $Path -PathType Leaf)) 'stage file missing'
 $item=Get-Item -LiteralPath $Path -Force -ErrorAction Stop
 Require (-not [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) 'stage file is a link'
 return ([string](Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop).Hash).ToLowerInvariant()
}
function Under([string]$Path,[string]$Base) {
 $p=[IO.Path]::GetFullPath($Path).TrimEnd('\')
 $b=[IO.Path]::GetFullPath($Base).TrimEnd('\')
 return $p.StartsWith($b+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)
}
function NativeTaskState {
 $task=Get-ScheduledTask -TaskName $taskName -TaskPath '\' -ErrorAction SilentlyContinue
 if($null -eq $task){return 'ABSENT'}
 return [string]$task.State
}
function OriginalDisabledTaskForCandidateReadOnly {
 $existing=Get-ScheduledTask -TaskName $taskName -TaskPath '\' -ErrorAction Stop
 Require ($null -ne $existing -and [string]$existing.State -ceq 'Disabled') 'original V3 Task not Disabled'
 Require (@($existing.Actions).Count -eq 1) 'original V3 Task has multiple actions'
 Require ([string]$existing.Principal.UserId -in @('SYSTEM','NT AUTHORITY\SYSTEM','S-1-5-18')) 'original V3 Task principal drift'
 Require ($existing.Settings.AllowDemandStart -eq $false -and
   [string]$existing.Settings.MultipleInstances -ceq 'IgnoreNew') 'original V3 Task scheduling drift'
 $originalAction=$existing.Actions[0]
 # Validate the exact Windows Task string independent of the CI runner OS.
 # Windows-only GetFullPath would turn C:\... into a Linux working path in
 # source-policy CI and hide the actual Windows shape the Task must retain.
 $oldStage=[string]$originalAction.WorkingDirectory
 Require ($oldStage -match '^C:\\Users\\ADMIN\\Trading\\Staging\\V3Paper-INACTIVE-[0-9a-f]{12}$') 'original V3 Task source outside inactive staging'
 Require ([string]$originalAction.Arguments -match "(?:^|[\s'`"])--read-only(?:[\s'`"]|$)") 'original V3 Task not read-only'
 return 'Disabled'
}
function OriginalIntakeReadOnly {
 $rows=@()
 for($i=0;$i -lt $oldNames.Count;$i++){
  $t=Get-ScheduledTask -TaskName $oldNames[$i] -TaskPath '\' -ErrorAction Stop
  Require ([string]$t.State -eq 'Running') ('protected original Task not running: '+$oldNames[$i])
  Require (@($t.Actions).Count -eq 1 -and
    [string]$t.Principal.UserId -in @('SYSTEM','NT AUTHORITY\SYSTEM','S-1-5-18')) 'old Task identity drift'
  Require ([string]$t.Actions[0].Arguments -match [regex]::Escape($oldScripts[$i])) 'original V2R4 action drift'
  $rows+=@($oldNames[$i])
 }
 return $rows
}
$trading=[IO.Path]::GetFullPath($TradingRoot).TrimEnd('\')
$source=[IO.Path]::GetFullPath($SourceRepo).TrimEnd('\')
Require ($trading -ieq 'C:\Users\ADMIN\Trading') 'unexpected protected Trading path'
Require (-not (Under $source $trading)) 'separate trusted source checkout must be outside Trading'
Require ((Test-Path -LiteralPath $source -PathType Container)) 'original source checkout missing'
Require (-not [bool]((Get-Item -LiteralPath $source -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) 'source checkout link not allowed'
$gitRoot=(& git -C $source rev-parse --show-toplevel 2>$null)
Require ($LASTEXITCODE -eq 0 -and $gitRoot -and
  ([IO.Path]::GetFullPath(([string]$gitRoot).Trim())).TrimEnd('\') -ieq $source) 'not independent Git root'
$dirty=@(& git -C $source status --porcelain --untracked-files=normal 2>$null|Where-Object {$_})
Require ($LASTEXITCODE -eq 0 -and $dirty.Count -eq 0) 'independent checkout modified'
$known=(& git -C $source cat-file -t $stageSha 2>$null)
Require ($LASTEXITCODE -eq 0 -and ([string]$known).Trim() -ceq 'commit') 'reviewed Git source object missing'
$stage=Join-Path $trading ('Staging\V3Paper-INACTIVE-'+$stageSha.Substring(0,12))
Require ((Test-Path -LiteralPath $stage -PathType Container)) 'original physically staged V3 source missing'
Require (-not [bool]((Get-Item -LiteralPath $stage -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) 'stage root link'
$manifestPath=Join-Path $stage 'v3-paper-inactive-source-manifest.json'
$manifest=Get-Content -LiteralPath $manifestPath -Raw -ErrorAction Stop|ConvertFrom-Json
Require ($manifest.kind -ceq 'V3_PAPER_INACTIVE_ISOLATED_SOURCE_STAGE_V1' -and
  $manifest.status -ceq 'STAGED_INACTIVE_CODE_ONLY_NOT_INSTALLED' -and
  $manifest.source_git_sha -ceq $stageSha -and
  $manifest.v3_paper_activated -eq $false -and
  $manifest.task_changes -eq $false -and
  @($manifest.source_manifest).Count -eq $stageFiles) 'exact reviewed stage file count required'
$allow=@(& git -C $source ls-tree -r --name-only $stageSha -- paper_evaluator market_data paper_context.py 'research/v3/v3-experimental-paper-all-lessons-bundle-20261011.json' 'supabase/functions/v3-paper-evidence-relay/index.ts' 'tools/minipc-runtime-supervisor.ps1' 'tools/check-minipc-v3-physical-writer-readiness.ps1' 'tools/minipc-v3-paper-cutover-operator-INACTIVE.ps1' 'tools/v3_experimental_paper_technical_gate.py' 'tools/paper_series_transition_guard.py' 2>$null)
Require ($LASTEXITCODE -eq 0) 'trusted source tree cannot be read'
$allow=@($allow|Where-Object {
  $_ -match '^(paper_evaluator|market_data)/[A-Za-z0-9_]+\.py$' -or
  $_ -eq 'paper_context.py' -or
  $_ -eq 'research/v3/v3-experimental-paper-all-lessons-bundle-20261011.json' -or
  $_ -eq 'supabase/functions/v3-paper-evidence-relay/index.ts' -or
  ($candidateMode -and $_ -in @('tools/v3_experimental_paper_technical_gate.py',
                               'tools/paper_series_transition_guard.py')) -or
  $_ -in @('tools/minipc-runtime-supervisor.ps1',
          'tools/check-minipc-v3-physical-writer-readiness.ps1',
          'tools/minipc-v3-paper-cutover-operator-INACTIVE.ps1')
}|Sort-Object -Unique)
Require ($allow.Count -eq $stageFiles) 'original source inventory changed'
$seen=@{}
foreach($entry in @($manifest.source_manifest)){
 $rel=[string]$entry.relative_path
 Require ($rel -cin $allow -and -not $seen.ContainsKey($rel)) 'stage has untrusted or duplicate file'
 $seen[$rel]=$true
 $item=Join-Path $stage ($rel.Replace('/','\'))
 Require ((Under $item $stage)) 'stage traversal'
 $parent=Split-Path $item -Parent
 # A nested subdirectory symlink can escape the isolated stage even if the
 # final file and immediate parent look normal; reject every ancestor.
 while(Under $parent $stage){
   $node=Get-Item -LiteralPath $parent -Force -ErrorAction Stop
   Require (-not [bool]($node.Attributes -band [IO.FileAttributes]::ReparsePoint)) 'linked stage ancestor'
   $parent=Split-Path $parent -Parent
 }
 $digest=Sha $item
 Require ($digest -ceq [string]$entry.sha256) ('stage SHA256 drift: '+$rel)
 # Git blob verification independently binds EACH staged byte to the reviewed
 # immutable source COMMIT, not only to a potentially edited local manifest.
 $object=(& git -C $source rev-parse ($stageSha+':'+$rel) 2>$null)
 Require ($LASTEXITCODE -eq 0 -and ([string]$object).Trim() -match '^[a-f0-9]{40}$') 'Git source file missing'
 $actualBlob=(& git -C $source hash-object -- $item 2>$null)
 Require ($LASTEXITCODE -eq 0 -and ([string]$actualBlob).Trim() -ceq ([string]$object).Trim()) 'stage differs from trusted Git blob'
}
Require ($seen.Count -eq $stageFiles -and
 $seen.ContainsKey('paper_evaluator/v3_paper_minipc_native_launcher_v1.py') -and
 $seen.ContainsKey('paper_context.py')) 'native owner or context missing'
$protected=@(OriginalIntakeReadOnly)
Require ($protected.Count -eq 4) 'original V2R4 Task baseline incomplete'
if($candidateMode){
 Require ((OriginalDisabledTaskForCandidateReadOnly) -ceq 'Disabled') 'original inactive task changed'
}else{
 Require ((NativeTaskState) -ceq 'ABSENT') 'V3 Task already exists; never overwrite it'
}
# Get-Command can enumerate several python.exe executables on Windows.
# Choose the first resolver match deterministically; NEVER treat .Source as
# an array (which would pass several Test-Path booleans into Require [bool]).
$pythonCommand=Get-Command -Name python.exe -CommandType Application -ErrorAction Stop | Select-Object -First 1
Require ($null -ne $pythonCommand) 'Python command not found'
$python=[string]$pythonCommand.Source
Require (-not [string]::IsNullOrWhiteSpace($python) -and [IO.Path]::IsPathRooted($python)) 'Python application path ambiguous'
Require ((Test-Path -LiteralPath $python -PathType Leaf)) 'Python executable missing'
Require (-not [bool]((Get-Item -LiteralPath $python -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) 'Python executable link'
# Exactly the existing *inactive* Python CLI. No external config, API/model,
# Cloud token, trading runtime, automatic paper series or source PIN changes.
$pyCode="import sys,runpy;sys.path.insert(0,r'$stage');sys.argv=['v3-paper','--read-only'];runpy.run_module('paper_evaluator.v3_paper_minipc_native_launcher_v1',run_name='__main__')"
Require (-not $pyCode.Contains('"') -and -not $stage.Contains("'")) 'unsafe Windows action quoting'
$arguments='-I -B -c "'+$pyCode+'"'
$plan=[ordered]@{
 kind='V3_ORIGINAL_SINGLE_WRITER_DISABLED_NATIVE_TASK_STAGE_V1'
 source_git_sha=$stageSha
 source_files_verified=66
 original_v2r4_tasks_running=4
 future_task_name=$taskName
 existing_v3_task_state='ABSENT'
 proposed_task_state='DISABLED'
 trigger='AT_BOOT_DISABLED'
 action='PINNED_V3_PAPER_LAUNCHER_READ_ONLY'
 native_owner_live_execution_authorized=$false
 v3_paper_activated=$false
 cloud_edge_changed=$false
 cloud_cas_performed=$false
 original_v2r4_tasks_changed=$false
 api_model_calls=0
 real_money_actions=$false
 technical_release_proofs_credited=0
 status='READ_ONLY_PREVIEW_NOT_INSTALLED'
}
if($candidateMode){
 $plan.source_files_verified=$stageFiles
 $plan.existing_v3_task_state='Disabled'
 $plan.status='READ_ONLY_SUCCESSOR_STAGE_VERIFIED_EXISTING_TASK_UNCHANGED'
}
if(-not $InstallDisabled){
 $plan|ConvertTo-Json -Depth 5
 return
}
Require ($Confirm -ceq 'REGISTER_DISABLED_READONLY_V3_TASK_NO_CUTOVER') 'exact inactive staging opt-in required'
# Windows COM TaskScheduler lets Enabled=false be set in the definition
# BEFORE atomic RegisterTaskDefinition. No intermediate enabled window.
$svc=New-Object -ComObject 'Schedule.Service'
$svc.Connect()
$folder=$svc.GetFolder('\')
$definition=$svc.NewTask(0)
$definition.RegistrationInfo.Description='V3 Paper ORIGINAL one-owner source stage only; DISABLED; CLI --read-only, never automatic live trade'
$definition.Principal.UserId='SYSTEM'
$definition.Principal.LogonType=5 # TASK_LOGON_SERVICE_ACCOUNT
$definition.Principal.RunLevel=1
$definition.Settings.Enabled=$false
$definition.Settings.AllowDemandStart=$false
$definition.Settings.StartWhenAvailable=$false
$definition.Settings.MultipleInstances=2 # TASK_INSTANCES_IGNORE_NEW
$definition.Settings.ExecutionTimeLimit='PT2M'
$definition.Settings.RestartCount=0
$trigger=$definition.Triggers.Create(8) # TASK_TRIGGER_BOOT
$trigger.Enabled=$true
$action=$definition.Actions.Create(0) # TASK_ACTION_EXEC
$action.Path=$python
$action.Arguments=$arguments
$action.WorkingDirectory=$stage
Require ($definition.Settings.Enabled -eq $false) 'Task unexpectedly enabled before registration'
Require ((NativeTaskState) -ceq 'ABSENT') 'V3 Task registration race'
# TASK_CREATE (2), not UPDATE (4): refuses any concurrent/preexisting task.
$null=$folder.RegisterTaskDefinition($taskName,$definition,2,'SYSTEM',$null,5)
$created=Get-ScheduledTask -TaskName $taskName -TaskPath '\' -ErrorAction Stop
Require ([string]$created.State -eq 'Disabled' -and
  @($created.Actions).Count -eq 1 -and
  $created.Actions[0].Execute -ieq $python -and
  [string]$created.Actions[0].Arguments -ceq $arguments -and
  [string]$created.Actions[0].WorkingDirectory -ieq $stage -and
  [string]$created.Principal.UserId -in @('SYSTEM','NT AUTHORITY\SYSTEM','S-1-5-18')) 'registered disabled V3 Task identity mismatch; STOP REVIEW'
$plan.existing_v3_task_state='DISABLED'
$plan.status='NATIVE_DISABLED_READ_ONLY_TASK_REGISTERED_NOT_RELEASED'
$plan|ConvertTo-Json -Depth 5
