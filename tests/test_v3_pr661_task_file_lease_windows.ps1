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
foreach($functionName in @('Test-V3IndependentOriginalHostCmsSignature','Test-V3Pr661SignedCloudBoundaryFields',
 'Test-V3Pr661SignedIssuerPrestopReceipt','Invoke-V3Pr661IssuerBoundIntakeStopSOURCE_ONLY',
 'Test-V3Pr515SignedPreparedAbortReadback','Test-V3Pr661HeldIntakeDefinitionPair',
 'Invoke-V3Pr661IssuerBoundIntakeRestoreSOURCE_ONLY',
 'Test-V3Pr661HostedOperatorScope','Test-V3ScopedIntakeTaskSet',
 'Test-V3Pr515FreshRecoveryIdentity','Test-V3Pr515ArmedRecoveryIdentity',
 'Test-V3Pr515QuiescedRecoveryIdentity','Test-V3Pr515CurrentOriginalBackupManifest',
 'Test-V3PrecommitCurrentCloudInventory','Resolve-V3ScopedCutoverRecovery',
 'Test-V3Pr515DisabledOnlyXmlDifference','New-V3Pr515PreparedArmedMarker',
 'Get-V3Pr515PreparedFenceSha256','Invoke-V3Pr515NativeExclusiveFenceArchiveSOURCE_ONLY',
 'Invoke-V3Pr515PrecommitRestoreSOURCE_ONLY','Invoke-V3Pr515ScopedNativeStopSOURCE_ONLY')){
 $f=@($ast.FindAll({param($n)
  $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -ceq $functionName
 },$true))
 if($f.Count -ne 1){throw 'V3_NATIVE_INTEGRATION_ORIGINAL_FUNCTION_MISSING'}
 . ([scriptblock]::Create($f[0].Extent.Text))
}
Add-Type -AssemblyName System.Security.Cryptography.Pkcs
$rsa=[Security.Cryptography.RSA]::Create(2048)
$request=[Security.Cryptography.X509Certificates.CertificateRequest]::new(
 'CN=PR661-CI-NOT-A-RELEASE-OWNER',$rsa,[Security.Cryptography.HashAlgorithmName]::SHA256,
 [Security.Cryptography.RSASignaturePadding]::Pkcs1)
$cert=$request.CreateSelfSigned([datetimeoffset]::UtcNow.AddMinutes(-1),[datetimeoffset]::UtcNow.AddMinutes(10))
$hash=[Security.Cryptography.SHA256]::Create()
try{$testPin=([BitConverter]::ToString($hash.ComputeHash($cert.RawData))).Replace('-','').ToLowerInvariant()}
finally{$hash.Dispose()}
function New-IssuerTestInput {
 $wire=([ordered]@{
  cloud_active_series_count=1;cloud_original_active_series_count=1
  cloud_cas_rpc_count=0;cloud_executor_can_login=$false
  cloud_observed_at_utc=[datetimeoffset]::UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'")
  kind='V3_CAS_ISSUER_COMMITTED_PRESTOP_READER_V1' 
  observed_at_utc=[datetimeoffset]::UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'")
  actor='v3_cas_audit_reader_actor';requested_role='v3_cas_audit_reader'
  epoch_id='V3CAS-AUDIT-99999999999999999999999999999999'
  source_sha256=('a'*64);original_fence_sha256=('b'*64);caller_acl_sha256=('c'*64)
  issuer_actor='v3_cas_inhibit_issuer_actor'
  inhibit_started_at_utc=[datetimeoffset]::UtcNow.AddSeconds(-5).ToString("yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'")
  state='INHIBITED';native_stop_done=$false;unknown_count=0;cas_or_paper_authorized=$false
 }|ConvertTo-Json -Compress)
 $bytes=[Text.Encoding]::UTF8.GetBytes($wire)
 $cms=[Security.Cryptography.Pkcs.SignedCms]::new([Security.Cryptography.Pkcs.ContentInfo]::new([byte[]]$bytes),$true)
 $signer=[Security.Cryptography.Pkcs.CmsSigner]::new($cert)
 $signer.DigestAlgorithm=[Security.Cryptography.Oid]::new('2.16.840.1.101.3.4.2.1')
 $cms.ComputeSignature($signer)
 return @{IndependentIssuerReaderJson=$bytes;IndependentIssuerReaderCms=[byte[]]$cms.Encode()
  ReviewedIssuerReaderCertificateSha256=$testPin
  ReviewedIssuerEpochId='V3CAS-AUDIT-99999999999999999999999999999999'
  ReviewedIssuerSourceSha256=('a'*64);armedFenceSha=('b'*64);ReviewedIssuerCallerAclSha256=('c'*64)}
}
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
$lease=$null;$pair=$null;$runningProcess=$null;$operatorRoot=$null;$aftercareJob=$null;$completeSession=$null;$fullTaskNames=@()
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
 $issuerInput=New-IssuerTestInput
 $badInput=$issuerInput.Clone();$badInput.ReviewedIssuerReaderCertificateSha256=('0'*64)
 $signatureRejected=$false
 try{$null=Invoke-V3Pr661IssuerBoundIntakeStopSOURCE_ONLY -tasks @($name,$secondName) @badInput}
 catch{if($_.Exception.Message -notlike '*SIGNATURE_OR_PIN_HOLD*'){throw};$signatureRejected=$true}
 if(-not $signatureRejected -or -not $folder.GetTask($name).Enabled -or
    -not $folder.GetTask($secondName).Enabled -or $runningProcess.HasExited){
  throw 'FAIL_INVALID_ISSUER_MUTATED_NATIVE_STATE'
 }
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
 $task.Enabled=$true
 $issuerInput=New-IssuerTestInput
 $actualStop=Invoke-V3Pr661IssuerBoundIntakeStopSOURCE_ONLY -tasks @($name,$secondName) `
  -protected @() -native @([pscustomobject]@{arguments=('-NoProfile -File "'+$workerScript+'"')}) `
  -descendants @($runningProcess.Id) @issuerInput
 $pair=$actualStop.held_intake_definition_pair
 if($null -eq $pair -or $pair.leases.Count -ne 2 -or
    $actualStop.paper_release_authorized -ne $false){throw 'FAIL_REAL_SOURCE_STOP_OR_LEASE_HANDOFF'}
 $lease=$pair.leases[0]
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
 # Retain the SAME live pair through independent terminal CMS validation.
 # The original recovery owner's real enable/start implementation must run;
 # merely disposing handles and calling Task.Run in this test is insufficient.
 $abortWire=([ordered]@{
  kind='V3_CAS_PREPARED_FENCE_ABORT_READER_RECEIPT_V1'
  epoch_id='V3CAS-AUDIT-99999999999999999999999999999999'
  source_sha256=('a'*64);prepared_fence_sha256=('b'*64);caller_acl_sha256=('c'*64)
  issuer_actor='v3_cas_inhibit_issuer_actor';receipt_sha256=('d'*64)
  state='ABORT_RECORDED_NOT_RELEASED'
  created_at_utc=[datetimeoffset]::UtcNow.AddSeconds(-2).ToString("yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'")
  observed_at_utc=[datetimeoffset]::UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'")
  cloud_active_series_count=1;cloud_original_active_series_count=1
  cloud_cas_rpc_count=0;cloud_executor_can_login=$false
  cloud_observed_at_utc=[datetimeoffset]::UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'")
 }|ConvertTo-Json -Compress)
 $abortBytes=[Text.Encoding]::UTF8.GetBytes($abortWire)
 $abortCms=[Security.Cryptography.Pkcs.SignedCms]::new([Security.Cryptography.Pkcs.ContentInfo]::new([byte[]]$abortBytes),$true)
 $abortSigner=[Security.Cryptography.Pkcs.CmsSigner]::new($cert)
 $abortSigner.DigestAlgorithm=[Security.Cryptography.Oid]::new('2.16.840.1.101.3.4.2.1')
 $abortCms.ComputeSignature($abortSigner)
 $restoreInput=@{TaskNames=@($name,$secondName);HeldPair=$pair;AbortPayload=$abortBytes
  AbortCms=[byte[]]$abortCms.Encode();IssuerCertificateSha256=$testPin
  EpochId='V3CAS-AUDIT-99999999999999999999999999999999';SourceSha256=('a'*64)
  OriginalArmedFenceSha256=('b'*64);CallerAclSha256=('c'*64)}
 $invalidRestore=$restoreInput.Clone();$invalidRestore.IssuerCertificateSha256=('0'*64)
 $restoreRejected=$false
 try{$null=Invoke-V3Pr661IssuerBoundIntakeRestoreSOURCE_ONLY @invalidRestore}
 catch{if($_.Exception.Message -notlike '*TERMINAL_ABORT_HOLD*'){throw};$restoreRejected=$true}
 if(-not $restoreRejected -or $folder.GetTask($name).Enabled -or $folder.GetTask($secondName).Enabled -or
    -not(Test-V3Pr661HeldIntakeDefinitionPair -Pair $pair -TaskNames @($name,$secondName))){
  throw 'FAIL_INVALID_TERMINAL_ABORT_RELEASED_LEASE_OR_REENABLED_TASK'
 }
 # A serialized/faked or already-closed lease must never enable a task.
 $pair.leases[0].readonly_definition_handle.Dispose()
 $closedRejected=$false
 try{$null=Invoke-V3Pr661IssuerBoundIntakeRestoreSOURCE_ONLY @restoreInput}
 catch{if($_.Exception.Message -notlike '*HELD_PAIR_HOLD*'){throw};$closedRejected=$true}
 if(-not $closedRejected -or $folder.GetTask($name).Enabled -or $folder.GetTask($secondName).Enabled){
  throw 'FAIL_CLOSED_PAIR_RESTORED_TASKS'
 }
 $pair.leases[0]=Open-V3Pr661DisabledTaskDefinitionLeaseSOURCE_ONLY $name
 [IO.File]::Delete($workerPid)
 $restored=Invoke-V3Pr661IssuerBoundIntakeRestoreSOURCE_ONLY @restoreInput
 if($restored.native_task_api_restore_requested -ne $true -or $restored.marker_removed_here -ne $false -or
    $restored.cas_or_paper_authorized -ne $false -or
    -not $folder.GetTask($name).Enabled -or -not $folder.GetTask($secondName).Enabled){
  throw 'FAIL_ORIGINAL_SOURCE_RESTORE_NOT_EXECUTED_OR_FALSE_RELEASE'
 }
 for($i=0;$i -lt 40 -and -not [IO.File]::Exists($workerPid);$i++){Start-Sleep -Milliseconds 250}
 if(-not [IO.File]::Exists($workerPid)){throw 'FAIL_RESTORED_REAL_WORKER_NOT_STARTED'}
 $recoveredProcess=[Diagnostics.Process]::GetProcessById([int][IO.File]::ReadAllText($workerPid))
 try{if($recoveredProcess.HasExited){throw 'FAIL_RESTORED_REAL_WORKER_EXITED'}}finally{$recoveredProcess.Dispose()}
 foreach($entry in $pair.leases){
  if(-not $entry.readonly_definition_handle.SafeFileHandle.IsClosed){throw 'FAIL_RESTORE_DID_NOT_RELEASE_PAIR'}
 }

 # Execute the ENTIRE original owner, not the extracted native child pair.
 # Only the read-only host/Cloud boundary is adapted to disposable tasks;
 # actual task mutation, CMS, process absence, lease lifetime, fence rename,
 # restored worker health and post-archive aftercare run through source code.
 $operatorRoot=Join-Path $env:RUNNER_TEMP ('PR661-CI-Operator-'+[guid]::NewGuid().ToString('N'))
 $state=Join-Path $operatorRoot 'State';$null=[IO.Directory]::CreateDirectory($state)
 $backup=Join-Path $state ('V3Paper-PreCAS-Backup-'+[guid]::NewGuid().ToString('N'))
 $null=[IO.Directory]::CreateDirectory($backup)
 $marker=New-V3Pr515PreparedArmedMarker -SuccessorId 'PAPER-V3-20261103T000000Z' `
  -ReviewedRepoSha ('1'*40) -ReviewedBundleSha ('2'*64) -ReviewedStrategySha ('3'*64)
 $markerPath=Join-Path $state 'v3-experimental-paper-old-intake-fence.json'
 [IO.File]::WriteAllText($markerPath,($marker|ConvertTo-Json -Depth 5),[Text.UTF8Encoding]::new($false))
 $markerAcl=[Security.AccessControl.FileSecurity]::new();$markerAcl.SetAccessRuleProtection($true,$false)
 foreach($sid in @('S-1-5-18','S-1-5-32-544')){
  $markerAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
   [Security.Principal.SecurityIdentifier]::new($sid),'FullControl','Allow'))
 }
 Set-Acl -LiteralPath $markerPath -AclObject $markerAcl
 $operatorFenceSha=Get-V3Pr515PreparedFenceSha256 $marker
 if((Get-FileHash $markerPath).Hash.ToLowerInvariant() -cne $operatorFenceSha){throw 'FAIL_FULL_OPERATOR_CANONICAL_FENCE'}
 $sourceFile=Join-Path $backup 'cloudsync-fixture.py'
 [IO.File]::WriteAllText($sourceFile,'# disposable read-only original-source fixture')
 $sourceSha=(Get-FileHash $sourceFile).Hash.ToLowerInvariant()
 foreach($n in @($name,$secondName)){$folder.GetTask($n).Stop(0)}
 $fullTaskNames=@(('PR661-CI-FileLease-'+[guid]::NewGuid().ToString('N')),
  ('PR661-CI-FileLease-'+[guid]::NewGuid().ToString('N')))
 if($fullTaskNames.Count -ne 2 -or @($fullTaskNames|Where-Object {
    $_ -cnotmatch '^PR661-CI-FileLease-[a-f0-9]{32}$'
   }).Count){throw 'CI_FULL_OPERATOR_TASK_NAME_CONSTRUCTION'}
 $fullNative=@();$fullDescendants=@()
 foreach($index in @(0,1)){
  $n=$fullTaskNames[$index];$role=if($index -eq 0){'candidate'}else{'wait'}
  $scriptFile=Join-Path $operatorRoot ($role+'.ps1');$pidFile=Join-Path $operatorRoot ($role+'.pid')
  $beat=Join-Path $state ('v2r4-paper-'+$role+'-runtime-heartbeat.json')
  $worker=@'
[IO.File]::WriteAllText('__PID__',[string]$PID)
[IO.File]::WriteAllText('__BEAT__',(@{status='HEALTHY';checked_at_utc=[datetimeoffset]::UtcNow.ToString('o')}|ConvertTo-Json -Compress))
Start-Sleep -Seconds 120
'@
  [IO.File]::WriteAllText($scriptFile,$worker.Replace('__PID__',$pidFile).Replace('__BEAT__',$beat))
  $argsLine='-NoProfile -File "'+$scriptFile+'"'
  $task=Register-Fixture $n (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe') $argsLine
  $null=$task.Run($null)
  for($i=0;$i -lt 40 -and -not [IO.File]::Exists($pidFile);$i++){Start-Sleep -Milliseconds 100}
  if(-not [IO.File]::Exists($pidFile)){throw 'FAIL_FULL_OPERATOR_WORKER_NOT_RUNNING'}
  $fullDescendants+=@([int][IO.File]::ReadAllText($pidFile))
  $fullNative+=@([pscustomobject]@{arguments=$argsLine})
  [IO.File]::WriteAllText((Join-Path $backup ($n+'.xml')),[string](Export-ScheduledTask -TaskName $n -TaskPath '\'))
 }
 # The existing independent database/CMS transaction integration is retained.
 # This host adapter substitutes only the machine-specific read-only inputs.
 function Read-V3Pr515FreshRecoveryPreview {
  param($Report,$Root,$BackupDirectory,$ExpectedCloudSha,[switch]$ExpectedArmed,[switch]$ExpectedQuiesced)
  if(-not(Test-V3Pr661HostedOperatorScope $Root $fullTaskNames) -or
     (Get-FileHash (Join-Path $BackupDirectory 'cloudsync-fixture.py')).Hash.ToLowerInvariant() -cne $ExpectedCloudSha){
   throw 'CI_READONLY_BACKUP_OR_SOURCE_CHANGED'
  }
  $digests=@(foreach($n in $fullTaskNames){
   $savedFile=Join-Path $BackupDirectory ($n+'.xml');$saved=[IO.File]::ReadAllText($savedFile)
   $live=[string](Export-ScheduledTask -TaskName $n -TaskPath '\')
   $taskState=[string](Get-ScheduledTask -TaskName $n -TaskPath '\').State
   if($ExpectedArmed){
    if($taskState -cne 'Disabled' -or -not(Test-V3Pr515DisabledOnlyXmlDifference $saved $live)){throw 'CI_READONLY_DISABLED_XML_DRIFT'}
   }elseif($taskState -cne 'Running' -or $saved -cne $live){throw 'CI_READONLY_ORIGINAL_XML_DRIFT'}
   (Get-FileHash $savedFile).Hash.ToLowerInvariant()
  })
  return [pscustomobject]@{
   kind=$(if($ExpectedArmed){'V3_PRECAS_PR515_ARMED_POSTSTOP_READONLY_COMPATIBILITY_V1'}else{'V3_PRECAS_PR515_FRESH_BACKUP_READONLY_COMPATIBILITY_V1'})
   status=$(if($ExpectedArmed){'ARMED_DISABLED_NATIVE_SOURCE_MATCH_NOT_RELEASED'}else{'COMPATIBLE_READONLY_NOT_RELEASED'})
   current_backup_directory_leaf=[IO.Path]::GetFileName($BackupDirectory)
   pr515_source_sha256=$ExpectedCloudSha;current_native_task_xml_sha256=$digests
   current_backup_valid_while_intakes_running_only=(!$ExpectedArmed)
   preview_is_not_poststop_or_independent_cloud_ack=(!$ExpectedArmed)
   two_current_native_xml_reread_pass=(!$ExpectedArmed)
   pr515_effective_cloudsync_source_consistent=$true
   external_sha_pin_independently_authenticated=$false;physical_task_restore_tested=$false
   scheduler_task_mutations=$false;cloud_cas_invoked=$false;v3_paper_activated=$false;technical_release_proofs_credited=0
   after_disable_enabled_only_native_xml_comparison=$ExpectedArmed.IsPresent
   poststop_disabled_only_native_xml_recheck_pass=$ExpectedArmed.IsPresent
   single_local_supervisor_pr515_armed_observation_only=$ExpectedArmed.IsPresent
   two_distinct_supervisor_cycles_verified=$false;old_intake_pid_family_absence_independently_verified=$false
   independent_cloud_cas_never_invoked_verified=$false;local_poststop_snapshot_is_not_independent_cloud_ack=$ExpectedArmed.IsPresent
  }
 }
 function Invoke-V3Pr661ScopedNativeStopSOURCE_ONLY {
  param([switch]$ReadOnlyPreflight,$IssuerPayload,$IssuerCms,$IssuerCertSha256,$ExpectedEpochId,
   $ExpectedSourceSha256,$ExpectedFenceSha256,$ExpectedAclSha256,$ReviewedCandidateRepoSha)
  if(-not $ReadOnlyPreflight -or $ExpectedFenceSha256 -cne $operatorFenceSha){throw 'CI_READONLY_PREFLIGHT_SCOPE'}
  return [pscustomobject]@{tasks=$fullTaskNames;protected=@();native=$fullNative;descendants=$fullDescendants}
 }
 $aftercareJob=Start-Job -ArgumentList $state -ScriptBlock {
  param($State)
  $limit=[datetimeoffset]::UtcNow.AddSeconds(100)
  while([datetimeoffset]::UtcNow -lt $limit){
   $present=[IO.File]::Exists((Join-Path $State 'v3-experimental-paper-old-intake-fence.json'))
   $at=[datetimeoffset]::UtcNow.ToString('o')
   [IO.File]::WriteAllText((Join-Path $State 'minipc-runtime-supervisor.json'),
    (@{status=$(if($present){'WARNING'}else{'HEALTHY'});checked_at_utc=$at;v3_paper_old_intake_fence=@{mode=$(if($present){'ARMED'}else{'NONE'})}}|ConvertTo-Json -Compress))
   [IO.File]::WriteAllText((Join-Path $State 'v2r4-paper-cloud-sync-heartbeat.json'),
    (@{status='HEALTHY';checked_at_utc=$at;v3_fence_cloud_sync_lane=$(if($present){'PRECOMMIT_ORIGINAL'}else{'ACTIVE_ORIGINAL'});series_id='PAPER-V2R4-20261009T110135Z'}|ConvertTo-Json -Compress))
   Start-Sleep -Milliseconds 100
  }
 }
 # Bind fresh CMS to the ACTUAL canonical ARMED fence, not the old child fixture.
 $fullIssuer=New-IssuerTestInput
 $fullIssuerBytes=[Text.Encoding]::UTF8.GetBytes(
  ([Text.Encoding]::UTF8.GetString($fullIssuer.IndependentIssuerReaderJson)).Replace(('b'*64),$operatorFenceSha))
 $signedIssuer=[Security.Cryptography.Pkcs.SignedCms]::new([Security.Cryptography.Pkcs.ContentInfo]::new([byte[]]$fullIssuerBytes),$true)
 $fullSigner=[Security.Cryptography.Pkcs.CmsSigner]::new($cert)
 $fullSigner.DigestAlgorithm=[Security.Cryptography.Oid]::new('2.16.840.1.101.3.4.2.1')
 $signedIssuer.ComputeSignature($fullSigner)
 $terminalPath=Join-Path $operatorRoot 'abort.json';$terminalCmsPath=Join-Path $operatorRoot 'abort.cms'
 $fullAbortBytes=[Text.Encoding]::UTF8.GetBytes($abortWire.Replace(('b'*64),$operatorFenceSha))
 [IO.File]::WriteAllBytes($terminalPath,$fullAbortBytes)
 # First attempt is deliberately signed over DIFFERENT bytes.
 [IO.File]::WriteAllBytes($terminalCmsPath,[byte[]]$abortCms.Encode())
 $fullInput=@{Root=$operatorRoot;OriginalReadback=[pscustomobject]@{};BackupFolder=$backup;ReviewedPr515Sha=$sourceSha
  SuccessorId='PAPER-V3-20261103T000000Z';ReviewedRepoSha=('1'*40);ReviewedBundleSha=('2'*64);ReviewedStrategySha=('3'*64)
  OnlyIssuedNativeStop=$true;CompleteArmedAbortRestore=$true;IsolatedTaskNames=$fullTaskNames
  ExpectedPreparedFenceSha=$operatorFenceSha;IndependentIssuerReaderJson=$fullIssuerBytes
  IndependentIssuerReaderCms=[byte[]]$signedIssuer.Encode();ReviewedIssuerReaderCertificateSha256=$testPin
  ReviewedIssuerEpochId='V3CAS-AUDIT-99999999999999999999999999999999';ReviewedIssuerSourceSha256=('a'*64)
  ReviewedIssuerCallerAclSha256=('c'*64);TerminalAbortJsonPath=$terminalPath;TerminalAbortCmsPath=$terminalCmsPath}
 $invalidFull=$fullInput.Clone();$invalidFull.ReviewedIssuerReaderCertificateSha256=('0'*64)
 $invalidFullRejected=$false
 try{$null=Invoke-V3Pr515ScopedNativeStopSOURCE_ONLY @invalidFull}
 catch{if($_.Exception.Message -notlike '*SIGNATURE_OR_PIN_HOLD*'){throw};$invalidFullRejected=$true}
 if(-not $invalidFullRejected -or -not(Test-Path $markerPath) -or
    @($fullTaskNames|Where-Object {[string](Get-ScheduledTask -TaskName $_ -TaskPath '\').State -cne 'Running'}).Count){
  throw 'FAIL_FULL_OPERATOR_INVALID_ISSUER_CHANGED_TASKS'
 }
 $productionInput=$fullInput.Clone();$productionInput.Root='C:\Users\ADMIN\Trading'
 $productionRejected=$false
 try{$null=Invoke-V3Pr515ScopedNativeStopSOURCE_ONLY @productionInput}
 catch{if($_.Exception.Message -notlike '*NATIVE_STOP_SOURCE_UNCONDITIONALLY_LOCKED*'){throw};$productionRejected=$true}
 if(-not $productionRejected){throw 'FAIL_FULL_OPERATOR_PRODUCTION_GATE_OPENED'}
 $heldResult=Invoke-V3Pr515ScopedNativeStopSOURCE_ONLY @fullInput
 $completeSession=$heldResult.held_session
 if($heldResult.status -cne 'HOLD_FENCE_AND_SESSION_NO_AUTOMATIC_REARM' -or
    $heldResult.error_code -cne 'V3_PRECOMMIT_INDEPENDENT_CLOUD_CAS_AUTHORITY_NOT_WIRED'){
  throw ('FAIL_FULL_OPERATOR_INVALID_ABORT_PATH: '+$heldResult.status+' '+$heldResult.error_code)
 }
 if(-not(Test-V3Pr661HeldIntakeDefinitionPair $completeSession.pair $fullTaskNames) -or -not(Test-Path $markerPath)){
  throw 'FAIL_FULL_OPERATOR_ERROR_LOST_PAIR_OR_FENCE'
 }
 foreach($pidValue in $fullDescendants){
  if(Get-Process -Id $pidValue -ErrorAction SilentlyContinue){throw 'FAIL_FULL_OPERATOR_PROCESS_SURVIVED'}
 }
 # A collision is rejected BEFORE releasing either task definition.
 $fullAbortCms=[Security.Cryptography.Pkcs.SignedCms]::new([Security.Cryptography.Pkcs.ContentInfo]::new([byte[]]$fullAbortBytes),$true)
 $fullAbortCms.ComputeSignature($fullSigner)
 [IO.File]::WriteAllBytes($terminalCmsPath,[byte[]]$fullAbortCms.Encode())
 $archivePath=Join-Path $state ('v3-experimental-paper-old-intake-fence.aborted-'+$fullInput.ReviewedIssuerEpochId+'.json')
 [IO.File]::WriteAllText($archivePath,'do not overwrite')
 $fullInput.HeldArmedSession=$completeSession
 $collisionResult=Invoke-V3Pr515ScopedNativeStopSOURCE_ONLY @fullInput
 if($collisionResult.error_code -cne 'V3_PRECOMMIT_ARCHIVE_COLLISION_PRESERVE_PAIR_AND_FENCE' -or
    -not(Test-V3Pr661HeldIntakeDefinitionPair $completeSession.pair $fullTaskNames) -or
    [IO.File]::ReadAllText($archivePath) -cne 'do not overwrite'){
  throw ('FAIL_FULL_OPERATOR_ARCHIVE_COLLISION: '+$collisionResult.error_code)
 }
 [IO.File]::Delete($archivePath)
 $fullResult=Invoke-V3Pr515ScopedNativeStopSOURCE_ONLY @fullInput
 if($fullResult.status -cne 'ARMED_STOP_ABORT_RESTORE_AND_AFTERCARE_CONFIRMED' -or
    $null -ne $fullResult.held_session -or $fullResult.production_release_authorized -ne $false -or
    (Test-Path $markerPath) -or -not(Test-Path $archivePath) -or
    (Get-FileHash $archivePath).Hash.ToLowerInvariant() -cne $operatorFenceSha){
  throw ('FAIL_FULL_ORIGINAL_OPERATOR_COMPLETION: '+$fullResult.status+' '+$fullResult.error_code)
 }
 foreach($entry in $completeSession.pair.leases){
  if(-not $entry.readonly_definition_handle.SafeFileHandle.IsClosed){throw 'FAIL_FULL_OPERATOR_PAIR_NOT_RELEASED_AFTER_ABORT'}
 }
 # Disposed mutex proves ownership was released exactly once on completion.
 $disposed=$false
 try{$null=$completeSession.mutex.WaitOne(0)}catch [ObjectDisposedException]{$disposed=$true}
 if(-not $disposed){throw 'FAIL_FULL_OPERATOR_MUTEX_NOT_RELEASED'}
 foreach($n in $fullTaskNames){
  if([string](Get-ScheduledTask -TaskName $n -TaskPath '\').State -cne 'Running'){throw 'FAIL_FULL_OPERATOR_INTAKE_NOT_RESTORED'}
 }

 [pscustomobject]@{
  kind='V3_PR661_HOSTED_DISABLED_TASK_FILE_LEASE_V1'
  complete_original_armed_abort_restore_and_aftercare=$true
  complete_entry_rejected_production_root_and_invalid_issuer_before_stop=$true
  invalid_abort_preserved_live_session_for_same_owner_resume=$true
  archive_collision_rejected_before_lease_release=$true
  successful_restore_archived_exact_fence_and_disposed_mutex=$true
  enabled_capture_rejected=$true;kernel_write_denied=$true
  admin_reenable_and_replace_denied=$true;system_run_and_reenable_denied=$true
  original_task_api_recovered=$true;originalhost_mutated=$false
  two_task_pair_held_during_real_process_stop=$true
  original_source_issuer_signature_to_native_stop_integration=$true
  original_source_terminal_abort_to_native_restore_integration=$true
  invalid_abort_preserved_both_leases_and_disabled_tasks=$true
  closed_or_fake_lease_cannot_restore=$true
  invalid_signed_issuer_did_not_mutate_tasks=$true
  partial_pair_failure_released_first_handle=$true
  admin_and_system_runex_ignore_constraints_denied=$true
  privileged_handle_closure_excluded=$false;cas_or_paper_authorized=$false
 }|ConvertTo-Json -Compress
}catch{
 Write-Output ('PR661_HOSTED_TEST_FAILURE_CODE='+$_.Exception.Message)
 Write-Output ('PR661_HOSTED_TEST_FAILURE_AT='+$_.ScriptStackTrace)
 throw
}finally{
 if($null -ne $aftercareJob){Stop-Job $aftercareJob;Remove-Job $aftercareJob}
 if($null -ne $completeSession){
  foreach($entry in $completeSession.pair.leases){$entry.readonly_definition_handle.Dispose()}
  try{$completeSession.mutex.ReleaseMutex()}catch [ObjectDisposedException]{}catch [ApplicationException]{}
  $completeSession.mutex.Dispose()
 }
 if($null -ne $pair){foreach($entry in $pair.leases){$entry.readonly_definition_handle.Dispose()}}
 if($null -ne $runningProcess){$runningProcess.Dispose()}
 $cert.Dispose();$rsa.Dispose()
 foreach($n in (@($probeName,$name,$secondName)+@($fullTaskNames))){
  try{$folder.GetTask($n).Stop(0);$folder.DeleteTask($n,0)}catch{
   $cause=$_.Exception;while($cause.InnerException){$cause=$cause.InnerException}
   if($cause.HResult -ne -2147024894){throw}
  }
 }
 if([IO.Directory]::Exists($temp)){[IO.Directory]::Delete($temp,$true)}
 if($operatorRoot -and [IO.Directory]::Exists($operatorRoot)){[IO.Directory]::Delete($operatorRoot,$true)}
}
