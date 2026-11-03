# Isolated real Windows kernel/Task Scheduler test. Never run on the Mini-PC.
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
if($env:OS -cne 'Windows_NT' -or $env:GITHUB_ACTIONS -cne 'true' -or
   $env:RUNNER_ENVIRONMENT -cne 'github-hosted'){
 throw 'V3_FILE_LEASE_EPHEMERAL_HOSTED_WINDOWS_ONLY'
}
$source=Join-Path (Split-Path $PSScriptRoot -Parent) 'tools/minipc-v3-paper-cutover-operator-INACTIVE.ps1'
$t=$null;$e=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($source,[ref]$t,[ref]$e)
if(@($e).Count){throw 'V3_FILE_LEASE_SOURCE_AST_INVALID'}
$defs=@($ast.FindAll({param($n)
 $n -is [Management.Automation.Language.FunctionDefinitionAst] -and
 $n.Name -ceq 'Open-V3Pr661DisabledTaskDefinitionLeaseSOURCE_ONLY'
},$true))
if($defs.Count -ne 1){throw 'V3_FILE_LEASE_ORIGINAL_OWNER_HELPER_MISSING'}
. ([scriptblock]::Create($defs[0].Extent.Text))
$pairDefs=@($ast.FindAll({param($n)
 $n -is [Management.Automation.Language.FunctionDefinitionAst] -and
 $n.Name -ceq 'Open-V3Pr661DisabledIntakeLeasePairSOURCE_ONLY'
},$true))
if($pairDefs.Count -ne 1){throw 'V3_FILE_LEASE_PAIR_HELPER_MISSING'}
. ([scriptblock]::Create($pairDefs[0].Extent.Text))
$suffix=[guid]::NewGuid().ToString('N')
$name='PR661-CI-FileLease-'+$suffix
$secondName='PR661-CI-FileLease-'+[guid]::NewGuid().ToString('N')
$probeName='PR661-CI-FileLeaseProbe-'+$suffix
$temp=Join-Path $env:RUNNER_TEMP $probeName
$null=[IO.Directory]::CreateDirectory($temp)
$service=New-Object -ComObject 'Schedule.Service';$service.Connect()
$folder=$service.GetFolder('\')
function Register-Fixture([string]$TaskName,[string]$Executable,[string]$Arguments){
 if($TaskName -cnotmatch '^PR661-CI-FileLease(Probe)?-[a-f0-9]{32}$'){throw 'CI_TASK_NAME_SCOPE'}
 $d=$service.NewTask(0);$d.Principal.UserId='SYSTEM';$d.Principal.LogonType=5;$d.Principal.RunLevel=1
 $d.Settings.Enabled=$true;$d.Settings.AllowDemandStart=$true
 $d.Settings.DisallowStartIfOnBatteries=$false;$d.Settings.StopIfGoingOnBatteries=$false
 $d.Settings.ExecutionTimeLimit='PT1M'
 $a=$d.Actions.Create(0);$a.Path=$Executable;$a.Arguments=$Arguments
 return $folder.RegisterTaskDefinition($TaskName,$d,2,'SYSTEM',$null,5,$null)
}
function Assert-DisabledRunDenied {
 try{$null=$folder.GetTask($name).Run($null);throw 'FAIL_DISABLED_TASK_RUN_ACCEPTED'}
 catch{
  $cause=$_.Exception;while($cause.InnerException){$cause=$cause.InnerException}
  if($cause.HResult -notin @(-2147216602,-2147024891)){throw}
 }
}
$lease=$null;$pair=$null;$runningProcess=$null
try{
 # A real long-running SYSTEM process: verify stop while both definitions
 # are held, rather than testing only tasks that have already exited.
 $workerScript=Join-Path $temp 'worker.ps1';$workerPid=Join-Path $temp 'worker.pid'
 [IO.File]::WriteAllText($workerScript,
  ("[IO.File]::WriteAllText('"+$workerPid.Replace("'","''")+"',[string]`$PID); Start-Sleep -Seconds 120"),
  [Text.UTF8Encoding]::new($false))
 $task=Register-Fixture $name (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe') ('-NoProfile -File "'+$workerScript+'"')
 $secondTask=Register-Fixture $secondName (Join-Path $env:SystemRoot 'System32\cmd.exe') '/c exit 0'
 $null=$task.Run($null)
 for($i=0;$i -lt 40 -and -not [IO.File]::Exists($workerPid);$i++){Start-Sleep -Milliseconds 250}
 if(-not [IO.File]::Exists($workerPid)){throw 'FAIL_REAL_WORKER_NOT_STARTED'}
 $runningProcess=[Diagnostics.Process]::GetProcessById([int][IO.File]::ReadAllText($workerPid))
 # Materialize a native process handle before stopping; PID reuse cannot pass.
 $null=$runningProcess.Handle
 if($runningProcess.HasExited){throw 'FAIL_REAL_WORKER_ALREADY_EXITED'}
 $enabledRejected=$false
 try{$null=Open-V3Pr661DisabledTaskDefinitionLeaseSOURCE_ONLY $name}
 catch{if($_.Exception.Message -notlike '*REQUIRES_ALREADY_DISABLED*'){throw};$enabledRejected=$true}
 if(-not $enabledRejected){throw 'FAIL_LEASE_CAPTURED_ENABLED_TASK'}
 $task.Enabled=$false
 # Deliberately fail the second capture while it is still enabled. The first
 # kernel handle must be released and both original enable states preserved.
 $partialRejected=$false
 try{$null=Open-V3Pr661DisabledIntakeLeasePairSOURCE_ONLY @($name,$secondName)}
 catch{if($_.Exception.Message -notlike '*REQUIRES_ALREADY_DISABLED*'){throw};$partialRejected=$true}
 if(-not $partialRejected -or $folder.GetTask($name).Enabled -or -not $folder.GetTask($secondName).Enabled){
  throw 'FAIL_PARTIAL_PAIR_CHANGED_TASK_STATE'
 }
 $testWrite=[IO.File]::Open((Join-Path (Join-Path $env:SystemRoot 'System32\Tasks') $name),'Open','Write','ReadWrite')
 $testWrite.Dispose()
 $secondTask.Enabled=$false
 $pair=Open-V3Pr661DisabledIntakeLeasePairSOURCE_ONLY @($name,$secondName)
 $lease=$pair.leases[0]
 $task.Stop(0)
 if(-not $runningProcess.WaitForExit(10000)){throw 'FAIL_REAL_WORKER_SURVIVED_STOP_WITH_HELD_PAIR'}
 foreach($entry in $pair.leases){
  if($entry.readonly_definition_handle.SafeFileHandle.IsClosed){throw 'FAIL_PAIR_NOT_HELD_DURING_STOP'}
 }
 Assert-DisabledRunDenied
 # Task.RunEx ignore-constraints is a separate native start path.
 try{$null=$folder.GetTask($name).RunEx($null,2,0,$null);throw 'FAIL_RUNEX_IGNORE_CONSTRAINTS_ACCEPTED'}
 catch{
  $cause=$_.Exception;while($cause.InnerException){$cause=$cause.InnerException}
  if($cause.HResult -notin @(-2147216602,-2147024891)){throw}
 }
 if($lease.readonly_definition_handle.SafeFileHandle.IsClosed){throw 'FAIL_LEASE_ALREADY_CLOSED'}
 $writeDenied=$false
 try{$w=[IO.File]::Open($lease.definition_path,'Open','Write','ReadWrite');$w.Dispose()}
 catch{
  $cause=$_.Exception;while($cause.InnerException){$cause=$cause.InnerException}
  if($cause.HResult -ne -2147024864){throw};$writeDenied=$true
 }
 if(-not $writeDenied){throw 'FAIL_KERNEL_FILE_WRITE_NOT_DENIED'}
 $enableDenied=$false
 try{$folder.GetTask($name).Enabled=$true}
 catch{$enableDenied=$true}
 if(-not $enableDenied -or $folder.GetTask($name).Enabled){throw 'FAIL_ADMIN_REENABLE_NOT_BLOCKED'}
 Assert-DisabledRunDenied
 $replacement=$folder.GetTask($name).Definition;$replacement.Settings.Enabled=$true
 $replaceDenied=$false
 try{$null=$folder.RegisterTaskDefinition($name,$replacement,6,'SYSTEM',$null,5,$null)}
 catch{$replaceDenied=$true}
 if(-not $replaceDenied -or $folder.GetTask($name).Enabled){throw 'FAIL_ADMIN_REREGISTRATION_NOT_BLOCKED'}
 $probeScript=Join-Path $temp 'probe.ps1';$probeResult=Join-Path $temp 'result.txt'
 $probe=@'
$ErrorActionPreference='Stop'
$s=New-Object -ComObject 'Schedule.Service';$s.Connect();$f=$s.GetFolder('\')
$run='ALLOWED';$enable='ALLOWED';$runEx='ALLOWED'
try{$null=$f.GetTask('__TASK__').Run($null)}catch{$run='DENIED'}
try{$f.GetTask('__TASK__').Enabled=$true}catch{$enable='DENIED'}
try{$null=$f.GetTask('__TASK__').RunEx($null,2,0,$null)}catch{$runEx='DENIED'}
[IO.File]::WriteAllText('__RESULT__',($run+'|'+$enable+'|'+$runEx),[Text.Encoding]::ASCII)
'@
 $probe=$probe.Replace('__TASK__',$name).Replace('__RESULT__',$probeResult.Replace("'","''"))
 [IO.File]::WriteAllText($probeScript,$probe,[Text.UTF8Encoding]::new($false))
 $probeTask=Register-Fixture $probeName (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe') ('-NoProfile -ExecutionPolicy Bypass -File "'+$probeScript+'"')
 $null=$probeTask.Run($null)
 for($i=0;$i -lt 40 -and -not [IO.File]::Exists($probeResult);$i++){Start-Sleep -Milliseconds 250}
 if(-not [IO.File]::Exists($probeResult) -or [IO.File]::ReadAllText($probeResult) -cne 'DENIED|DENIED|DENIED' -or
    $folder.GetTask($name).Enabled){throw 'FAIL_SYSTEM_RUN_OR_REENABLE_NOT_BLOCKED'}
 if((Get-FileHash -LiteralPath $lease.definition_path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $lease.definition_sha256){
  throw 'FAIL_HELD_TASK_DEFINITION_BYTES_CHANGED'
 }
 foreach($entry in $pair.leases){$entry.readonly_definition_handle.Dispose()}
 # The lease must actually release: normal original Task API control must
 # work again afterwards. No ACL is changed, so no descriptor repair is needed.
 $folder.GetTask($name).Enabled=$true
 $null=$folder.GetTask($name).Run($null)
 [pscustomobject]@{
  kind='V3_PR661_HOSTED_DISABLED_TASK_FILE_LEASE_V1'
  enabled_capture_rejected=$true;kernel_write_denied=$true
  admin_reenable_and_replace_denied=$true;system_run_and_reenable_denied=$true
  original_task_api_recovered=$true;originalhost_mutated=$false
  two_task_pair_held_during_real_process_stop=$true
  partial_pair_failure_released_first_handle=$true
  admin_and_system_runex_ignore_constraints_denied=$true
  privileged_handle_closure_excluded=$false;cas_or_paper_authorized=$false
 }|ConvertTo-Json -Compress
}finally{
 if($null -ne $pair){foreach($entry in $pair.leases){$entry.readonly_definition_handle.Dispose()}}
 if($null -ne $runningProcess){$runningProcess.Dispose()}
 foreach($n in @($probeName,$name,$secondName)){
  try{$folder.GetTask($n).Stop(0);$folder.DeleteTask($n,0)}catch{
   $cause=$_.Exception;while($cause.InnerException){$cause=$cause.InnerException}
   if($cause.HResult -ne -2147024894){throw}
  }
 }
 if([IO.Directory]::Exists($temp)){[IO.Directory]::Delete($temp,$true)}
}
