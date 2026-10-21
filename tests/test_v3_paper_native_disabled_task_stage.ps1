# Source policy only. Never queries real Windows Task Scheduler or creates a Task.
# Executed in existing GitHub architecture PowerShell job.
$ErrorActionPreference='Stop'
$path=Join-Path (Split-Path $PSScriptRoot -Parent) 'tools/minipc-v3-paper-disabled-single-writer-task-INACTIVE.ps1'
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile(
  (Resolve-Path -LiteralPath $path),[ref]$tokens,[ref]$errors)
if(@($errors).Count -gt 0){throw ('V3_DISABLED_NATIVE_TASK_PARSE_FAILED '+($errors|Out-String))}
$src=Get-Content -LiteralPath $path -Raw
$expected='d6853a08e608c1e56229e27939c40ba2f5d57f8b'
foreach($must in @(
 "V3_ORIGINAL_SINGLE_WRITER_DISABLED_NATIVE_TASK_STAGE_V1",
 "REGISTER_DISABLED_READONLY_V3_TASK_NO_CUTOVER",
 "CryptoMiniPC-V3PaperSingleWriter",
 $expected,
 "V3Paper-INACTIVE-",
 "stage differs from trusted Git blob",
 "linked stage ancestor",
 "source_files_verified=66",
 "READ_ONLY_PREVIEW_NOT_INSTALLED",
 "NATIVE_DISABLED_READ_ONLY_TASK_REGISTERED_NOT_RELEASED",
 "Require ((NativeTaskState) -ceq 'ABSENT')",
 '$definition.Settings.Enabled=$false',
 '$definition.Settings.AllowDemandStart=$false',
 '$definition.Settings.MultipleInstances=2',
 '$definition.Settings.RestartCount=0',
 '$definition.Triggers.Create(8)',
 '$definition.Actions.Create(0)',
 'RegisterTaskDefinition($taskName,$definition,2',
 'original_v2r4_tasks_changed=$false',
 'v3_paper_activated=$false',
 'real_money_actions=$false',
 'cloud_cas_performed=$false',
 'technical_release_proofs_credited=0',
 "sys.argv=['v3-paper','--read-only']",
 "runpy.run_module('paper_evaluator.v3_paper_minipc_native_launcher_v1'"
)){
 if(-not $src.Contains($must)){throw ('V3_DISABLED_NATIVE_TASK_GUARD_MISSING '+$must)}
}
foreach($forbidden in @(
 'Disable-ScheduledTask',
 'Stop-ScheduledTask',
 'Unregister-ScheduledTask',
 'Set-ScheduledTask',
 'Enable-ScheduledTask',
 'Start-ScheduledTask',
 'Start-Process',
 'Invoke-RestMethod',
 'Invoke-WebRequest',
 'supabase functions deploy',
 'supabase db push',
 'git pull',
 'git checkout',
 'model_client('
)){
 if($src.IndexOf($forbidden,[StringComparison]::OrdinalIgnoreCase) -ge 0){
  throw ('V3_DISABLED_NATIVE_TASK_UNSAFE_COMMAND '+$forbidden)
 }
}
# Original successor Task is already Disabled/--read-only. This is
# source policy ONLY, not the originalhost Windows Task/PID readback.
foreach($guard in @(
 'candidate inspection must remain read-only',
 'candidate checkout HEAD mismatch',
 'original source closure readback failed',
 'candidate closure not pinned',
 'candidate dependency path invalid',
 'candidate source files mismatch',
 'candidate import SHA drift:',
 'static_transitive_closure_sha256',
 '--source-closure-readonly',
 'source_closure_is_only_candidate_not_loaded_code_ack',
 'original V3 Task not Disabled',
 'original V3 Task not read-only'
)){
 if(-not $src.Contains($guard)){
  throw ('V3_SUCCESSOR_READONLY_SOURCE_CLOSURE_GUARD_MISSING '+$guard)
 }
}
if($src.Contains('$stageFiles=if($candidateMode){69}else{66}')){
 throw 'V3_SUCCESSOR_HISTORICAL_STAGE_COUNT_RETAINED'
}
$beforeAction=$src.IndexOf('candidate source files mismatch')
$sourceGate=$src.IndexOf('candidate closure not pinned')
$taskWrite=$src.IndexOf('RegisterTaskDefinition($taskName,$definition,2')
if($sourceGate -lt 0 -or $beforeAction -le $sourceGate -or
   $taskWrite -le $beforeAction){
 throw 'V3_SUCCESSOR_READONLY_GATE_MUST_PRECEDE_TASK_MUTATION_BRANCH'
}

$first=$src.IndexOf('if(-not $InstallDisabled){')
$gate=$src.IndexOf('Require ($Confirm -ceq')
$service=$src.IndexOf("New-Object -ComObject 'Schedule.Service'",$gate)
$register=$src.IndexOf('RegisterTaskDefinition($taskName,$definition,2',$service)
if($first -lt 0 -or $gate -le $first -or $service -le $gate -or $register -le $service){
 throw 'V3_DISABLED_NATIVE_TASK_PREVIEW_OR_CONFIRM_EXECUTION_ORDER_BAD'
}
if($src.Contains('RegisterTaskDefinition($taskName,$definition,6')){
 throw 'TASK_CREATE_OR_UPDATE is forbidden; only fail-on-present CREATE'
}
$funcs=@($ast.FindAll({
 param($n)
 $n -is [Management.Automation.Language.FunctionDefinitionAst] -and
 $n.Name -in @('Under','Require','NativeTaskState','OriginalIntakeReadOnly')
},$true))
if($funcs.Count -ne 4){throw 'Native source-stage functions missing'}
foreach($old in @('CryptoMiniPC-V2R4PaperCandidates',
 'CryptoMiniPC-V2R4PaperWait','CryptoMiniPC-V2R4PaperLifecycle',
 'CryptoMiniPC-V2R4PaperCloudSync')){
 if(-not $src.Contains($old)){throw 'Original aftercare role missing'}
}
# Regression of the real originalhost PowerShell error on 17 Oct:
# Require (NativeTaskState -ceq 'ABSENT') passes a STRING to bool binding.
# Extract only the pure functions, with a fake native scheduler. No real Task.
$native=@($ast.FindAll({
 param($n)
 $n -is [Management.Automation.Language.FunctionDefinitionAst] -and
 $n.Name -eq 'NativeTaskState'
},$true))
$requireFn=@($ast.FindAll({
 param($n)
 $n -is [Management.Automation.Language.FunctionDefinitionAst] -and
 $n.Name -eq 'Require'
},$true))
if($native.Count -ne 1 -or $requireFn.Count -ne 1){throw 'Task probe function missing'}
. ([Scriptblock]::Create($requireFn[0].Extent.Text))
. ([Scriptblock]::Create($native[0].Extent.Text))
$taskName='CryptoMiniPC-V3PaperSingleWriter'
function Get-ScheduledTask {
 param([string]$TaskName,[string]$TaskPath,[string]$ErrorAction)
 return $null
}
$state=NativeTaskState
if($state -cne 'ABSENT'){throw 'Absent task fake readback failed'}
Require ((NativeTaskState) -ceq 'ABSENT') 'Expected absent V3 task'
$guardOccurrences=[regex]::Matches($src,[regex]::Escape("Require ((NativeTaskState) -ceq 'ABSENT')"))
if($guardOccurrences.Count -ne 2){
 throw 'Both preview and pre-register native Task guards must invoke function before comparing'
}
$badGuard='Require (NativeTaskState -ceq'
if($src.Contains($badGuard)){throw 'Invalid PowerShell boolean binding expression reappeared'}
Write-Output 'V3_NATIVE_ABSENT_TASK_PREVIEW_ACTUAL_POWERSHELL_REGRESSION_PASS'

# Full preflight source audit: command results passed into typed Require([bool])
# must be executed as nested expressions and remain scalar. NativeTaskState
# already failed on host once; multiple python.exe commands caused Object[]
# binding at original line124. Test the actual production assignment AST.
foreach($unsafe in @('Require (Test-Path ', 'Require (Under ', 'Require (NativeTaskState ')){
 if($src.Contains($unsafe)){throw ('UNWRAPPED_REQUIRE_COMMAND_REAPPEARED '+$unsafe)}
}
foreach($safe in @(
 'Require ((Test-Path -LiteralPath $Path -PathType Leaf))',
 'Require ((Test-Path -LiteralPath $source -PathType Container))',
 'Require ((Test-Path -LiteralPath $stage -PathType Container))',
 'Require ((Test-Path -LiteralPath $python -PathType Leaf))',
 'Require ((Under $item $stage))'
)){
 if(-not $src.Contains($safe)){throw ('NESTED_COMMAND_BOOLEAN_GUARD_MISSING '+$safe)}
}
$pythonAssignment=@($ast.FindAll({
 param($node)
 $node -is [Management.Automation.Language.AssignmentStatementAst] -and
 $node.Left.Extent.Text -eq '$pythonCommand'
},$true))
$pythonPathAssignment=@($ast.FindAll({
 param($node)
 $node -is [Management.Automation.Language.AssignmentStatementAst] -and
 $node.Left.Extent.Text -eq '$python'
},$true))
if($pythonAssignment.Count -ne 1 -or $pythonPathAssignment.Count -ne 1){
 throw 'Exactly one Python application resolver and scalar path assignment required'
}
$pythonResolverSource=$pythonAssignment[0].Extent.Text
if(-not $pythonResolverSource.Contains('Select-Object -First 1')){
 throw 'Python resolver must select a single executable even with multiple PATH matches'
}
$mockFirst=(Resolve-Path -LiteralPath $path).Path
$mockSecond=$mockFirst+'.SECOND'
function Get-Command {
 param($Name,$CommandType,$ErrorAction)
 if($Name -cne 'python.exe' -or $CommandType -cne 'Application'){
  throw 'Unsupported mocked Get-Command'
 }
 [pscustomobject]@{Source=$mockFirst}
 [pscustomobject]@{Source=$mockSecond}
}
. ([scriptblock]::Create($pythonResolverSource))
. ([scriptblock]::Create($pythonPathAssignment[0].Extent.Text))
if($pythonCommand -is [array] -or $python -is [array] -or
   $python -cne $mockFirst -or -not (Test-Path -LiteralPath $python -PathType Leaf)){
 throw 'V3 Python single PATH resolver failed with TWO executable choices'
}
Require ((Test-Path -LiteralPath $python -PathType Leaf)) 'Python path must resolve to a single file'
Write-Output 'V3_ORIGINALHOST_MULTIPLE_PYTHON_APPLICATIONS_BOOLEAN_PREVIEW_PASS'


# This read-only action digest must exactly agree with original Windows inspector.
$actionAst=@($ast.FindAll({
 param($node)
 $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
 $node.Name -eq 'TaskActionSha'
},$true))
if($actionAst.Count -ne 1){throw 'Need one native Task action digest helper'}
. ([scriptblock]::Create($actionAst[0].Extent.Text))
$a=TaskActionSha 'C:\Windows\python.exe' '--read-only' 'C:\Safe\Stage'
$b=TaskActionSha 'C:\Windows\python.exe' '--read-only' 'C:\Safe\Stage'
$c=TaskActionSha 'C:\Windows\python.exe' '--one-shot-preflight' 'C:\Safe\Stage'
if($a.Length -ne 64 -or $a -cne $b -or $a -ceq $c){
 throw 'Task action digest not bound to actual executable/args/stage'
}
$raw=[Text.Encoding]::UTF8.GetBytes('C:\Windows\python.exe'+[char]0+'--read-only'+[char]0+'C:\Safe\Stage')
$hasher=[Security.Cryptography.SHA256]::Create()
try {
 $expected=([BitConverter]::ToString($hasher.ComputeHash($raw))).Replace('-','').ToLowerInvariant()
} finally { $hasher.Dispose() }
if($a -cne $expected){throw 'Task action digest differs from original inspector'}
foreach($clause in @(
 'previous_disabled_task_action_sha256',
 'proposed_disabled_readonly_task_action_sha256',
 'proposed_disabled_readonly_launcher_file_sha256',
 'phase_execution_available=$false',
 'independent_originalhost_release_accepted=$false',
 'native_task_update_executed=$false',
 'original_disabled_task_unchanged=$true'
)){
 if(-not $src.Contains($clause)){throw ('Task action source guard missing '+$clause)}
}
# Upcoming physical maintenance may use ONE opt-in original Task
# DISABLED->DISABLED revision. Source test only: never call COM TaskScheduler.
foreach($must in @(
 'ApplyDisabledCandidateAfterMaintenance',
 'ExpectedOldActionSha256',
 'AFTER_MAINTENANCE_REPLACE_DISABLED_READONLY_V3_TASK',
 'postmaintenance disabled candidate replacement requires exact confirmation',
 '$plan.previous_disabled_task_action_sha256 -ceq $ExpectedOldActionSha256',
 'Export-ScheduledTask -TaskName $taskName',
 '[IO.FileMode]::CreateNew',
 '$stream.Flush($true)',
 'RegisterTaskDefinition($taskName,$definition,4',
 'RegisterTask($taskName,$oldXml,4',
 'DISABLED_SUCCESSOR_TASK_UPDATED_NOT_RELEASED',
 '$plan.phase_execution_available=$false',
 '$plan.independent_originalhost_release_accepted=$false',
 '$plan.v3_paper_activated=$false'
)){
 if(-not $src.Contains($must)){throw ('V3_POSTMAINT_DISABLED_REPLACE_POLICY_MISSING '+$must)}
}
$disabledUpgrade=$src.IndexOf('if($candidateMode -and $ApplyDisabledCandidateAfterMaintenance){')
$confirmation=$src.IndexOf("AFTER_MAINTENANCE_REPLACE_DISABLED_READONLY_V3_TASK")
$backupAt=$src.IndexOf('[IO.FileMode]::CreateNew')
$taskUpdate=$src.IndexOf('RegisterTaskDefinition($taskName,$definition,4')
$verifyPost=$src.IndexOf('updated Task not exactly Disabled and pinned')
$restore=$src.IndexOf('RegisterTask($taskName,$oldXml,4')
if($confirmation -lt 0 -or $confirmation -ge $disabledUpgrade -or
   $backupAt -le $disabledUpgrade -or $taskUpdate -le $backupAt -or
   $verifyPost -le $taskUpdate -or $restore -le $verifyPost){
 throw 'V3_POSTMAINT_DISABLED_UPGRADE_BACKUP_UPDATE_ROLLBACK_ORDER_INVALID'
}
if($src.Contains('RegisterTaskDefinition($taskName,$definition,6') -or
   $src.Contains('Enable-ScheduledTask') -or
   $src.Contains('Start-ScheduledTask')){
 throw 'V3_POSTMAINT_DISABLED_UPGRADE_CANNOT_ENABLE_OR_START'
}
Write-Output 'V3_POSTMAINT_DISABlED_SUCCESSOR_SOURCE_BACKUP_ROLLBACK_GUARD_PASS'

Write-Output 'V3_TASK_ACTION_PREVIEW_ORIGINAL_SHA_TUPLE_COMPATIBILITY_PASS'

# The successor PREVIEW must inspect the existing old disabled V3 Task,
# never update it or install any successor candidate as a second Task.
foreach($must in @(
 '[string]$CandidateStageSha',
 'if($InstallDisabled){throw',
 '$stageFiles=if($candidateMode){0}else{66}',
 'READ_ONLY_SUCCESSOR_STAGE_VERIFIED_EXISTING_TASK_UNCHANGED',
 "Require ((OriginalDisabledTaskForCandidateReadOnly) -ceq 'Disabled')",
 "'tools/v3_experimental_paper_technical_gate.py'",
 "'tools/paper_series_transition_guard.py'"
)){
 if(-not $src.Contains($must)){throw ('V3_CANDIDATE_SOURCE_GUARD_MISSING '+$must)}
}
$inspectAst=@($ast.FindAll({
 param($node)
 $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
 $node.Name -eq 'OriginalDisabledTaskForCandidateReadOnly'
},$true))
if($inspectAst.Count -ne 1){throw 'Original Task successor preview must reuse exactly one source helper'}
. ([Scriptblock]::Create($inspectAst[0].Extent.Text))
function Get-ScheduledTask {
 param([string]$TaskName,[string]$TaskPath,[string]$ErrorAction)
 if($TaskName -cne 'CryptoMiniPC-V3PaperSingleWriter' -or $TaskPath -cne '\'){
  throw 'Candidate inspection touched foreign Task'
 }
 return $script:fakeCandidateTask
}
$script:fakeCandidateTask=[pscustomobject]@{
 State='Disabled'
 Actions=@([pscustomobject]@{
  WorkingDirectory='C:\Users\ADMIN\Trading\Staging\V3Paper-INACTIVE-d6853a08e608'
  Arguments="python -I -B -c sys.argv=['v3-paper','--read-only']"
 })
 Principal=[pscustomobject]@{UserId='SYSTEM'}
 Settings=[pscustomobject]@{AllowDemandStart=$false;MultipleInstances='IgnoreNew'}
}
if((OriginalDisabledTaskForCandidateReadOnly) -cne 'Disabled'){
 throw 'Original inactive Task dry-run identity rejected'
}
foreach($unsafe in @('Ready','Running')){
 $script:fakeCandidateTask.State=$unsafe
 $blocked=$false
 try{$null=OriginalDisabledTaskForCandidateReadOnly}catch{$blocked=$true}
 if(-not $blocked){throw ('Candidate Task state should fail closed: '+$unsafe)}
}
$script:fakeCandidateTask.State='Disabled'
$script:fakeCandidateTask.Actions[0].Arguments='v3-paper --execute'
$blocked=$false
try{$null=OriginalDisabledTaskForCandidateReadOnly}catch{$blocked=$true}
if(-not $blocked){throw 'Original V3 Task non-readonly action accepted'}
$script:fakeCandidateTask.Actions[0].Arguments="python -I -B -c sys.argv=['v3-paper','--read-only']"
$script:fakeCandidateTask.Settings.AllowDemandStart=$true
$blocked=$false
try{$null=OriginalDisabledTaskForCandidateReadOnly}catch{$blocked=$true}
if(-not $blocked){throw 'Original V3 Task demand start accepted'}
Write-Output 'V3_EXISTING_DISABLED_TASK_MANIFEST_SOURCE_SUCCESSOR_READONLY_PREVIEW_PASS'

Write-Output 'V3_NATIVE_DISABLED_READONLY_TASK_STAGE_SOURCE_POLICY_PASS'

# Physical V3 successor preparation also requires a REAL, strictly backup-only
# fresh Windows XML copy of both original intake Tasks. Execute ONLY its pure
# Action digest helper here; NEVER invoke the real originalhost backup or Task.
$operator=Join-Path (Split-Path $PSScriptRoot -Parent) 'tools/minipc-v3-paper-cutover-operator-INACTIVE.ps1'
$ot=$null;$oe=$null
$oa=[Management.Automation.Language.Parser]::ParseFile(
 (Resolve-Path -LiteralPath $operator),[ref]$ot,[ref]$oe)
if(@($oe).Count -ne 0){
 $details=@($oe | ForEach-Object {
  ('line={0} col={1}: {2}' -f $_.Extent.StartLineNumber,$_.Extent.StartColumnNumber,$_.Message)
 }) -join '; '
 throw ('V3_PRECAS_BACKUP_PARSE_FAILED '+$details)
}
$digestFn=@($oa.FindAll({
 param($node)
 $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
 $node.Name -eq 'Get-V3OriginalNativeActionSha'
},$true))
if($digestFn.Count -ne 1){throw 'V3 backup must use exactly one native action digest helper'}
. ([Scriptblock]::Create($digestFn[0].Extent.Text))
$sample=[pscustomobject]@{Execute='C:\Windows\python.exe';Arguments='-I -B --no-live';WorkingDirectory='C:\Trading\Stage'}
$actual=Get-V3OriginalNativeActionSha $sample
$joined=@($sample.Execute,$sample.Arguments,$sample.WorkingDirectory) -join '|'
$bytes=[Text.UTF8Encoding]::new($false).GetBytes($joined)
$expected=([BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash($bytes))).Replace('-','').ToLowerInvariant()
if($actual -cne $expected -or $actual -cnotmatch '^[0-9a-f]{64}$'){
 throw 'V3_PRECAS_BACKUP_NATIVE_ACTION_DIGEST_MISMATCH'
}
$mutated=[pscustomobject]@{Execute=$sample.Execute;Arguments=$sample.Arguments+' modified';WorkingDirectory=$sample.WorkingDirectory}
if((Get-V3OriginalNativeActionSha $mutated) -ceq $actual){
 throw 'V3_PRECAS_BACKUP_NATIVE_ACTION_DIGEST_NOT_BOUND_TO_ARGUMENTS'
}
$nullRejected=$false
try {$null=Get-V3OriginalNativeActionSha $null} catch {$nullRejected=$true}
if(-not $nullRejected){throw 'V3_PRECAS_BACKUP_INVALID_NULL_ACTION_ACCEPTED'}
Write-Host 'V3_PRECAS_BACKUP_NATIVE_ACTION_DIGEST_OFFLINE_PASS'

# Reuse the exact new originalhost FILE reread helper with independent Windows
# offline temporary files. No export, Scheduler, production root or Cloud call.
$fileFns=@($oa.FindAll({
 param($node)
 $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
 $node.Name -eq 'Test-V3FreshBackupFileBytes'
},$true))
if($fileFns.Count -ne 1){throw 'Original fresh backup reread helper must be unique'}
. ([Scriptblock]::Create($fileFns[0].Extent.Text))
$parent=Join-Path ([IO.Path]::GetTempPath()) ('v3-backup-file-test-'+[guid]::NewGuid().ToString('N'))
$null=New-Item -ItemType Directory -Path $parent -ErrorAction Stop
try{
 $p=Join-Path $parent 'Candidates.task.xml'
 $xml=('<Task><Actions><Exec><Command>python.exe</Command><Arguments>' +
  ('--read-only ' * 12)+'</Arguments></Exec></Actions></Task>')
 $payload=[Text.UTF8Encoding]::new($false).GetBytes($xml)
 [IO.File]::WriteAllBytes($p,$payload)
 $sha=([BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash($payload))).Replace('-','').ToLowerInvariant()
 if(-not (Test-V3FreshBackupFileBytes -Path $p -ExpectedSha $sha -ExpectedXml $xml)){
  throw 'original backup file byte reread rejected exact XML fixture'
 }
 $badSha='0'*64
 if($badSha -ceq $sha){$badSha='1'*64}
 if((Test-V3FreshBackupFileBytes -Path $p -ExpectedSha $badSha -ExpectedXml $xml) -or
    (Test-V3FreshBackupFileBytes -Path $p -ExpectedSha $sha -ExpectedXml ($xml+' changed'))){
  throw 'original backup file reread accepted mismatched expected hashes/bytes'
 }
 [IO.File]::WriteAllBytes($p,([Text.UTF8Encoding]::new($false).GetBytes($xml+'tampered')))
 if(Test-V3FreshBackupFileBytes -Path $p -ExpectedSha $sha -ExpectedXml $xml){
  throw 'tampered original native XML file accepted'
 }
 if(Test-V3FreshBackupFileBytes -Path (Join-Path $parent 'absent.xml') -ExpectedSha $sha -ExpectedXml $xml){
  throw 'missing original native XML backup accepted'
 }
}finally{
 Remove-Item -LiteralPath $parent -Recurse -Force -ErrorAction SilentlyContinue
}
Write-Host 'V3_PRECAS_NATIVE_BACKUP_DISK_REREAD_OFFLINE_PASS'
