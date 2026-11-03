# Isolated Windows Task Scheduler permission test. NEVER run on the Mini-PC.
# Only random PR661-CI-* tasks on an ephemeral GitHub-hosted Windows runner.
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
if($env:OS -cne 'Windows_NT' -or $env:GITHUB_ACTIONS -cne 'true' -or
   $env:RUNNER_ENVIRONMENT -cne 'github-hosted'){
 throw 'V3_TASK_DENY_TEST_EPHEMERAL_HOSTED_WINDOWS_ONLY'
}
$root=Split-Path $PSScriptRoot -Parent
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile(
 (Join-Path $root 'tools/minipc-v3-paper-cutover-operator-INACTIVE.ps1'),[ref]$tokens,[ref]$errors)
if(@($errors).Count){throw 'V3_TASK_DENY_OPERATOR_AST_INVALID'}
$defs=@($ast.FindAll({param($node)
 $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
 $node.Name -ceq 'New-V3Pr661TaskExecuteDenyDescriptor'
},$true))
if($defs.Count -ne 1){throw 'V3_TASK_DENY_ORIGINAL_TRANSFORM_MISSING'}
. ([scriptblock]::Create($defs[0].Extent.Text))
$mutation=@($ast.FindAll({param($node)
 $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
 $node.Name -ceq 'Set-V3Pr661OwnedTaskExecuteGuardSOURCE_ONLY'
},$true))
if($mutation.Count -ne 1){throw 'V3_TASK_DENY_ORIGINAL_OWNER_MUTATION_MISSING'}
. ([scriptblock]::Create($mutation[0].Extent.Text))
$suffix=[guid]::NewGuid().ToString('N')
$targetName='PR661-CI-ExecuteTarget-'+$suffix
$probeName='PR661-CI-SystemProbe-'+$suffix
$temp=Join-Path $env:RUNNER_TEMP ('PR661-CI-TaskDeny-'+$suffix)
$null=[IO.Directory]::CreateDirectory($temp)
$scheduler=New-Object -ComObject 'Schedule.Service'
$scheduler.Connect()
$folder=$scheduler.GetFolder('\')
function Register-CiTask([string]$Name,[string]$Executable,[string]$Arguments){
 if($Name -cnotmatch '^PR661-CI-(ExecuteTarget|SystemProbe)-[a-f0-9]{32}$'){
  throw 'V3_TASK_DENY_TEST_NAME_SCOPE'
 }
 $definition=$scheduler.NewTask(0)
 $definition.RegistrationInfo.Description='Disposable PR661 permission integration fixture'
 $definition.Principal.UserId='SYSTEM'
 $definition.Principal.LogonType=5
 $definition.Principal.RunLevel=1
 $definition.Settings.Enabled=$true
 $definition.Settings.AllowDemandStart=$true
 $definition.Settings.DisallowStartIfOnBatteries=$false
 $definition.Settings.StopIfGoingOnBatteries=$false
 $definition.Settings.ExecutionTimeLimit='PT1M'
 $action=$definition.Actions.Create(0)
 $action.Path=$Executable;$action.Arguments=$Arguments
 return $folder.RegisterTaskDefinition($Name,$definition,2,'SYSTEM',$null,5,$null)
}
function Try-AdminRun {
 try{$null=$folder.GetTask($targetName).Run($null);return 'ALLOWED'}
 catch{
  if($_.Exception.HResult -eq -2147024891 -or
     $_.Exception.InnerException.HResult -eq -2147024891){return 'DENIED'}
  throw
 }
}
function Invoke-SystemProbe([string]$Label){
 $result=Join-Path $temp ($Label+'.txt')
 $script=Join-Path $temp ($Label+'.ps1')
 # Fixed generated names and temp paths only; no caller-supplied program or
 # production task. The SYSTEM probe reports the actual Run HRESULT.
 $body=@'
$ErrorActionPreference='Stop'
$s=New-Object -ComObject 'Schedule.Service';$s.Connect()
$answer='UNEXPECTED'
try{$null=$s.GetFolder('\').GetTask('__TASK__').Run($null);$answer='ALLOWED'}
catch{
 if($_.Exception.HResult -eq -2147024891 -or $_.Exception.InnerException.HResult -eq -2147024891){$answer='DENIED'}
 else{$answer='ERROR_'+$_.Exception.HResult}
}
[IO.File]::WriteAllText('__RESULT__',$answer,[Text.Encoding]::ASCII)
'@
 $body=$body.Replace('__TASK__',$targetName).Replace('__RESULT__',$result.Replace("'","''"))
 [IO.File]::WriteAllText($script,$body,[Text.UTF8Encoding]::new($false))
 if($Label -cne 'before'){$folder.DeleteTask($probeName,0)}
 $probe=Register-CiTask $probeName (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe') ('-NoProfile -ExecutionPolicy Bypass -File "'+$script+'"')
 $null=$probe.Run($null)
 for($i=0;$i -lt 40;$i++){
  if([IO.File]::Exists($result)){return [IO.File]::ReadAllText($result).Trim()}
  Start-Sleep -Milliseconds 250
 }
 throw 'V3_TASK_DENY_SYSTEM_PROBE_TIMEOUT'
}
$original=$null
try{
 $target=Register-CiTask $targetName (Join-Path $env:SystemRoot 'System32\cmd.exe') '/c exit 0'
 # Same permission ACEs as the supplied originalhost receipt, with a generic
 # Administrators group instead of persisting any personal-machine SID.
 $fixture='O:BAG:BAD:(A;ID;0x1f019f;;;BA)(A;ID;0x1f019f;;;SY)(A;ID;FA;;;BA)(A;;FR;;;SY)'
 $target.SetSecurityDescriptor($fixture,16)
 $original=[string]$folder.GetTask($targetName).GetSecurityDescriptor(7)
 if((Try-AdminRun) -cne 'ALLOWED'){throw 'V3_TASK_DENY_ADMIN_POSITIVE_BASELINE_FAILED'}
 $systemBefore=Invoke-SystemProbe 'before'
 if($systemBefore -cnotin @('ALLOWED','DENIED')){throw 'V3_TASK_DENY_SYSTEM_BASELINE_NOT_MEASURED'}
 $denied=New-V3Pr661TaskExecuteDenyDescriptor $original
 try{
 $apply=Set-V3Pr661OwnedTaskExecuteGuardSOURCE_ONLY -Operation Apply -TaskName $targetName -OriginalSddl $original
 }catch{
  # Only synthetic descriptors from disposable hosted CI tasks, never user SIDs.
  Write-Host ('V3_TASK_DENY_DIAGNOSTIC_ORIGINAL='+$original)
  Write-Host ('V3_TASK_DENY_DIAGNOSTIC_EXPECTED='+$denied)
  Write-Host ('V3_TASK_DENY_DIAGNOSTIC_ACTUAL='+[string]$folder.GetTask($targetName).GetSecurityDescriptor(7))
  throw
 }
 if($apply.exact_descriptor_readback -ne $true){throw 'V3_TASK_DENY_OWNER_APPLY_FAILED'}
 if((Try-AdminRun) -cne 'DENIED'){throw 'V3_TASK_DENY_ADMIN_RUN_NOT_BLOCKED'}
 if((Invoke-SystemProbe 'denied') -cne 'DENIED'){throw 'V3_TASK_DENY_SYSTEM_RUN_NOT_BLOCKED'}
 $replayDenied=$false
 try{$null=Set-V3Pr661OwnedTaskExecuteGuardSOURCE_ONLY -Operation Apply -TaskName $targetName -OriginalSddl $original}
 catch{if($_.Exception.Message -notlike '*V3_NATIVE_TASK_GUARD_CURRENT_DESCRIPTOR_DRIFT*'){throw};$replayDenied=$true}
 if(-not $replayDenied){throw 'V3_TASK_DENY_DUPLICATE_APPLY_ACCEPTED'}
 $wrongDescriptor=[Security.AccessControl.RawSecurityDescriptor]::new($original)
 $wrongDescriptor.Group=[Security.Principal.SecurityIdentifier]::new('S-1-1-0')
 $wrongSddl=$wrongDescriptor.GetSddlForm([Security.AccessControl.AccessControlSections]::All)
 $driftDenied=$false
 try{$null=Set-V3Pr661OwnedTaskExecuteGuardSOURCE_ONLY -Operation Restore -TaskName $targetName -OriginalSddl $wrongSddl}
 catch{if($_.Exception.Message -notlike '*V3_NATIVE_TASK_GUARD_CURRENT_DESCRIPTOR_DRIFT*'){throw};$driftDenied=$true}
 if(-not $driftDenied -or [string]$folder.GetTask($targetName).GetSecurityDescriptor(7) -cne $denied){
  throw 'V3_TASK_DENY_WRONG_RESTORE_ACCEPTED_OR_MUTATED'
 }
 $scopeDenied=$false
 try{$null=Set-V3Pr661OwnedTaskExecuteGuardSOURCE_ONLY -Operation Apply -TaskName 'CryptoMiniPC-V2R4PaperCandidates' -OriginalSddl $original}
 catch{if($_.Exception.Message -notlike '*V3_NATIVE_TASK_GUARD_SANDBOX_NAME_HOLD*'){throw};$scopeDenied=$true}
 if(-not $scopeDenied){throw 'V3_TASK_DENY_SANDBOX_ESCAPED_TO_ORIGINALHOST_NAME'}
 # A denial on Run is not exclusive privileged custody: WRITE_DAC remains
 # available for controlled rollback. This test NEVER asserts otherwise.
 $restore=Set-V3Pr661OwnedTaskExecuteGuardSOURCE_ONLY -Operation Restore -TaskName $targetName -OriginalSddl $original
 if($restore.exact_descriptor_readback -ne $true){throw 'V3_TASK_DENY_OWNER_RESTORE_FAILED'}
 $restored=[string]$folder.GetTask($targetName).GetSecurityDescriptor(7)
 if($restored -cne $original){throw 'V3_TASK_DENY_EXACT_DESCRIPTOR_RESTORE_FAILED'}
 if((Try-AdminRun) -cne 'ALLOWED'){throw 'V3_TASK_DENY_ADMIN_RECOVERY_FAILED'}
 if((Invoke-SystemProbe 'restored') -cne $systemBefore){throw 'V3_TASK_DENY_SYSTEM_BASELINE_NOT_RESTORED'}
 [pscustomobject]@{
  kind='V3_PR661_HOSTED_WINDOWS_TASK_EXECUTE_DENY_TEST_V1'
  admin_run_denied=$true;system_run_denied=$true;exact_dacl_restored=$true
  replay_and_descriptor_drift_denied=$true;production_names_denied_in_sandbox=$true
  originalhost_changed=$false;privileged_acl_rewrite_excluded=$false
  continuous_cas_custody_proven=$false;production_release_authorized=$false
 }|ConvertTo-Json -Compress
}finally{
 foreach($name in @($probeName,$targetName)){
  try{$folder.DeleteTask($name,0)}catch{
   if($_.Exception.HResult -ne -2147024894 -and
      $_.Exception.InnerException.HResult -ne -2147024894){throw}
  }
 }
 if([IO.Directory]::Exists($temp)){[IO.Directory]::Delete($temp,$true)}
}
