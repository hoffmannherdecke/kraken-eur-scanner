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
 "NativeTaskState -ceq 'ABSENT'",
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
$first=$src.IndexOf('if(-not $InstallDisabled){')
$gate=$src.IndexOf('Require ($Confirm -ceq')
$service=$src.IndexOf("New-Object -ComObject 'Schedule.Service'")
$register=$src.IndexOf('RegisterTaskDefinition($taskName,$definition,2')
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

Write-Output 'V3_NATIVE_DISABLED_READONLY_TASK_STAGE_SOURCE_POLICY_PASS'
