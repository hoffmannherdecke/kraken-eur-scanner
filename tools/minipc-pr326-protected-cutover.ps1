param(
  [string]$TradingRoot = 'C:\Users\ADMIN\Trading',
  [switch]$Execute,
  [string]$Confirm = ''
)
# PR326 same-owner protected V2R4 WAIT + Supervisor cutover, no V3/CAS/order changes.
# Default is READ-ONLY. Operator requires exact source pins and prior physical SYSTEM import.
$ErrorActionPreference='Stop'
$sourceSha='c660ebb87a391142b74926be984a1b4c985633a0'
$oldLauncherHash='C5E43D62976BDF2079A3A0402E57658ABA8A33D427B0CF0D56737565B84DD51D'
$oldSupervisorHash='8F9E0BC76F6AF6E28362308729859FB4E85B529E0AC61687C7FC78B3D5F4DAD5'
$oldLauncher=Join-Path $TradingRoot 'Staging\v2r4-wait-pr291-isolated\wait_launcher.py'
$newStage=Join-Path $TradingRoot 'Staging\v2r4-wait-pr326-isolated-c660ebb87a39'
$newLauncher=Join-Path $newStage 'wait_launcher.py'
$newSupervisor=Join-Path $TradingRoot 'Staging\v2r4-pr326-supervisor-c660ebb87a39\minipc-runtime-supervisor.ps1'
$originalBackup='D:\Krypto-Sicherungen\PR326-VORHER-20261015-205743'
$progress=Join-Path $TradingRoot 'State\v2r4-paper-wait-source-progress.json'
$waitHeartbeat=Join-Path $TradingRoot 'State\v2r4-paper-wait-runtime-heartbeat.json'
$waitName='CryptoMiniPC-V2R4PaperWait'
$supName='CryptoMiniPC-RuntimeSupervisor'
$oldWaitXml=$null
$oldSupXml=$null
$backupDir=$null
$enteredMutation=$false
$cutoverStarted=$false

function Need([bool]$Condition,[string]$Reason) {
  if(-not $Condition){throw $Reason}
}
function Sha([string]$Path) {
  Need (Test-Path -LiteralPath $Path -PathType Leaf) ('Missing pinned file: '+(Split-Path -Leaf $Path))
  return (Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop).Hash
}
function Get-OneTask([string]$Name) {
  $t=Get-ScheduledTask -TaskName $Name -ErrorAction Stop
  Need ($t.TaskPath -eq '\') ('Unexpected TaskPath for '+$Name)
  Need (@($t.Actions).Count -eq 1) ('Task action count invalid: '+$Name)
  Need ([string]$t.Principal.UserId -in @('SYSTEM','NT AUTHORITY\SYSTEM','S-1-5-18')) ('Task principal is not SYSTEM: '+$Name)
  return $t
}
function Count-LauncherProcesses([string]$Path) {
  $norm=$Path.Replace('\','/').ToLowerInvariant()
  return @(
    Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" -ErrorAction Stop |
      Where-Object {([string]$_.CommandLine).Replace('\','/').ToLowerInvariant().Contains($norm)}
  ).Count
}
function Wait-TaskStopped([string]$Name,[int]$Seconds=30) {
  $until=(Get-Date).AddSeconds($Seconds)
  do {
    if([string](Get-ScheduledTask -TaskName $Name).State -ne 'Running'){return $true}
    Start-Sleep -Milliseconds 300
  }while((Get-Date) -lt $until)
  return $false
}
function TaskXmlWithArguments([string]$Xml,[string]$Arguments) {
  [xml]$d=$Xml
  $ns=New-Object Xml.XmlNamespaceManager($d.NameTable)
  $ns.AddNamespace('t',$d.DocumentElement.NamespaceURI)
  $exec=@($d.SelectNodes('/t:Task/t:Actions/t:Exec',$ns))
  Need ($exec.Count -eq 1) 'Missing/duplicate task Exec XML node'
  $arg=$exec[0].SelectSingleNode('t:Arguments',$ns)
  if(-not $arg){
    $arg=$d.CreateElement('Arguments',$d.DocumentElement.NamespaceURI)
    [void]$exec[0].AppendChild($arg)
  }
  $arg.InnerText=$Arguments
  $settings=$d.SelectSingleNode('/t:Task/t:Settings',$ns)
  Need ($null -ne $settings) 'Task Settings XML missing'
  $enabled=$settings.SelectSingleNode('t:Enabled',$ns)
  Need ($null -ne $enabled) 'Original task XML missing Enabled field; refusing schema mutation'
  $enabled.InnerText='false'
  return $d.OuterXml
}
function Protect-TaskXml([string]$Text,[string]$File) {
  Add-Type -AssemblyName System.Security
  $b=[Text.Encoding]::UTF8.GetBytes($Text)
  $cipher=[Security.Cryptography.ProtectedData]::Protect($b,$null,[Security.Cryptography.DataProtectionScope]::CurrentUser)
  [IO.File]::WriteAllBytes($File,$cipher)
  $round=[Security.Cryptography.ProtectedData]::Unprotect([IO.File]::ReadAllBytes($File),$null,[Security.Cryptography.DataProtectionScope]::CurrentUser)
  Need ([Text.Encoding]::UTF8.GetString($round) -ceq $Text) 'DPAPI task XML round-trip mismatch'
}
function Register-InactiveTask([string]$Name,[string]$Xml) {
  Register-ScheduledTask -TaskName $Name -Xml $Xml -Force -ErrorAction Stop | Out-Null
  $t=Get-OneTask $Name
  Need ([string]$t.State -eq 'Disabled') ('Re-registered task was not Disabled: '+$Name)
}
function Require-NoWaitProcess {
  Need ((Count-LauncherProcesses $oldLauncher) -eq 0) 'Old WAIT launcher PID still alive; do not create competing writer'
  Need ((Count-LauncherProcesses $newLauncher) -eq 0) 'New WAIT launcher PID still alive; do not create competing writer'
}
$wait=Get-OneTask $waitName
$sup=Get-OneTask $supName
Need ([string]$wait.State -eq 'Running') 'WAIT not running at preflight'
Need ([string]$sup.State -ne 'Disabled') 'Supervisor disabled at preflight'
Need ((Sha $oldLauncher) -ieq $oldLauncherHash) 'Original PR291 launcher hash drift'
Need ((Sha $newLauncher) -ieq $oldLauncherHash) 'PR326 staged launcher hash drift'
Need ((Sha $newSupervisor) -ieq (Sha (Join-Path $TradingRoot 'Staging\pr326-code-79dad178f3cd\tools\minipc-runtime-supervisor.ps1'))) 'Staged PR326 Supervisor differs from pinned source'
Need (Test-Path -LiteralPath $originalBackup -PathType Container) 'Earlier original backup missing'
$manifest=Get-Content -LiteralPath (Join-Path $newStage 'pr326-stage-manifest.json') -Raw -ErrorAction Stop | ConvertFrom-Json
Need ($manifest.pinned_git_sha -ceq $sourceSha -and $manifest.progress_opt_in -eq $false -and $manifest.supervisor_opt_in -eq $false) 'PR326 immutable stage manifest mismatch'
foreach($n in @('v2r4_wait_runtime.py','v2r4_wait_watcher.py','kraken_public_budget.py')){
  $matching=@($manifest.files | Where-Object {$_.file -ceq $n -and $_.origin -ceq 'PR326'})
  Need ($matching.Count -eq 1 -and (Sha (Join-Path $newStage $n)) -ieq $matching[0].sha256) ('Stage overlay hash mismatch: '+$n)
}
$actW=[string]$wait.Actions[0].Arguments
$actS=[string]$sup.Actions[0].Arguments
$first=@([regex]::Matches($actW,'"([^"]+)"'))
Need ($first.Count -ge 1 -and $first[0].Groups[1].Value -ieq $oldLauncher) 'WAIT launcher Task Action changed'
Need ($actW -notmatch '(?i)--source-progress-file') 'WAIT progress already enabled'
$matchS=[regex]::Match($actS,'(?i)(?:^|\s)-File\s+(?:"([^"]+)"|(\S+))')
Need ($matchS.Success) 'Supervisor -File action is not recognizable'
$oldSupervisor=$matchS.Groups[1].Value
if(-not $oldSupervisor){$oldSupervisor=$matchS.Groups[2].Value}
Need ((Sha $oldSupervisor) -ieq $oldSupervisorHash) 'Original Supervisor source SHA drift'
Need ($actS -notmatch '(?i)WaitSourceProgressOptIn|WaitSourceLauncherPath|WaitSourceLauncherSha256') 'Supervisor source-progress already enabled'
Need (-not (Test-Path -LiteralPath $progress)) 'Unexpected preexisting source progress file; refusing replay'
Need ((Count-LauncherProcesses $oldLauncher) -ge 1) 'Original WAIT process not physically identified'
Need ((Count-LauncherProcesses $newLauncher) -eq 0) 'PR326 launcher already active unexpectedly'
$work=Join-Path $TradingRoot 'Staging\pr326-code-79dad178f3cd'
$head=(& git -C $work rev-parse HEAD)
Need ($LASTEXITCODE -eq 0 -and [string]$head.Trim() -ceq $sourceSha) 'Pinned PR326 source Git HEAD drift'
$supervisorBlob=(& git -C $work hash-object '--path=tools/minipc-runtime-supervisor.ps1' -- $newSupervisor)
Need ($LASTEXITCODE -eq 0 -and [string]$supervisorBlob.Trim() -ceq 'b4d09346ff7bb5d1fd91c256c0b5a4c1663a2e8b') 'PR326 Supervisor Git blob pin mismatch'
$oldWaitXml=Export-ScheduledTask -TaskName $waitName -ErrorAction Stop
$oldSupXml=Export-ScheduledTask -TaskName $supName -ErrorAction Stop
$newWaitArgs=$actW.Substring(0,$first[0].Groups[1].Index)+$newLauncher+$actW.Substring($first[0].Groups[1].Index+$first[0].Groups[1].Length)+' --source-progress-file "'+$progress+'"'
$newSupArgs=$actS.Substring(0,$matchS.Index)+ ' -File "'+$newSupervisor+'"'+$actS.Substring($matchS.Index+$matchS.Length)+ ' -WaitSourceProgressOptIn -WaitSourceLauncherPath "'+$newLauncher+'" -WaitSourceLauncherSha256 '+$oldLauncherHash
$newWaitXml=TaskXmlWithArguments -Xml $oldWaitXml -Arguments $newWaitArgs
$newSupXml=TaskXmlWithArguments -Xml $oldSupXml -Arguments $newSupArgs
'PR326_RELEASE_PREFLIGHT=PASS'
'PR326_SOURCE_COMMIT_PIN=PASS'
'PR326_NEW_SUPERVISOR_PIN=PASS'
'PR326_TASK_XML_IN_MEMORY=PASS'
'PR326_BACKUP_ORIGINAL_VERIFIED_PRESENT=True'
if(-not $Execute){
  'PR326_EXECUTION=NOT_REQUESTED_READ_ONLY'
  exit 0
}
Need ($Confirm -ceq 'APPROVED_PR326_PAPER_ONLY_CUTOVER') 'Exact protected cutover confirmation argument missing'
$admin=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
Need ($admin.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) 'Admin Windows token required'
$backupDir=Join-Path 'D:\Krypto-Sicherungen' ('PR326-CUTOVER-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))
Need (-not (Test-Path -LiteralPath $backupDir)) 'Backup destination collision'
New-Item -ItemType Directory -Path $backupDir -ErrorAction Stop|Out-Null
Protect-TaskXml $oldWaitXml (Join-Path $backupDir 'WAIT.xml.dpapi')
Protect-TaskXml $oldSupXml (Join-Path $backupDir 'SUPERVISOR.xml.dpapi')
[ordered]@{
  kind='PR326_PROTECTED_CUTOVER_BACKUP_V1'
  created_at_utc=[datetime]::UtcNow.ToString('o')
  original_wait_launcher_sha256=$oldLauncherHash
  original_supervisor_sha256=$oldSupervisorHash
  pinned_source_commit=$sourceSha
  task_xml_dpapi_current_user=$true
  original_tasks_running=@{wait=$true;supervisor=([string]$sup.State -eq 'Running')}
  existing_strategy_unchanged=$true
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $backupDir 'manifest.json') -Encoding UTF8
try {
  $enteredMutation=$true
  Disable-ScheduledTask -TaskName $supName -ErrorAction Stop|Out-Null
  if([string](Get-ScheduledTask -TaskName $supName).State -eq 'Running'){
    Stop-ScheduledTask -TaskName $supName -ErrorAction Stop
  }
  Need (Wait-TaskStopped $supName 20) 'Supervisor would not stop'
  Disable-ScheduledTask -TaskName $waitName -ErrorAction Stop|Out-Null
  Stop-ScheduledTask -TaskName $waitName -ErrorAction SilentlyContinue
  Need (Wait-TaskStopped $waitName 30) 'WAIT scheduled task would not stop'
  $deadline=(Get-Date).AddSeconds(30)
  while((Count-LauncherProcesses $oldLauncher) -gt 0 -and (Get-Date) -lt $deadline){Start-Sleep -Milliseconds 500}
  Require-NoWaitProcess
  Register-InactiveTask $waitName $newWaitXml
  Register-InactiveTask $supName $newSupXml
  Need ([string](Get-OneTask $waitName).Actions[0].Arguments -ceq $newWaitArgs) 'WAIT action readback mismatch'
  Need ([string](Get-OneTask $supName).Actions[0].Arguments -ceq $newSupArgs) 'Supervisor action readback mismatch'
  $startAt=[datetime]::UtcNow
  Enable-ScheduledTask -TaskName $waitName -ErrorAction Stop|Out-Null
  Start-ScheduledTask -TaskName $waitName -ErrorAction Stop
  $cutoverStarted=$true
  $observed=@{}
  $deadline=(Get-Date).AddMinutes(7)
  while((Get-Date) -lt $deadline -and $observed.Count -lt 2){
    $liveCount=Count-LauncherProcesses $newLauncher
    Need ((Count-LauncherProcesses $oldLauncher) -eq 0 -and $liveCount -ge 1 -and $liveCount -le 2) 'Unexpected old/new WAIT process identity or duplicate tree'
    if(Test-Path -LiteralPath $waitHeartbeat){
      try {
        $h=Get-Content -LiteralPath $waitHeartbeat -Raw | ConvertFrom-Json
        $done=([datetime]$h.checked_at_utc).ToUniversalTime()
        if($done -gt $startAt -and $h.status -in @('HEALTHY','DEGRADED')){
          $observed[$h.checked_at_utc]=[string]$h.status
        }
      }catch{}
    }
    if($observed.Count -lt 2){Start-Sleep -Seconds 3}
  }
  Need ($observed.Count -ge 2) 'Two real post-cutover WAIT completions not observed'
  $p=Get-Content -LiteralPath $progress -Raw -ErrorAction Stop|ConvertFrom-Json
  Need ($p.kind -ceq 'V2R4_WAIT_SOURCE_PROGRESS_V1' -and $p.status -ceq 'IN_PROGRESS_NOT_HEALTHY' -and [int]$p.successful_source_steps -ge 1) 'No genuine source progress observed'
  Enable-ScheduledTask -TaskName $supName -ErrorAction Stop|Out-Null
  Start-ScheduledTask -TaskName $supName -ErrorAction Stop
  Start-Sleep -Seconds 5
  Need ((Get-OneTask $waitName).State -eq 'Running') 'WAIT not running after supervised start'
  Need ((Get-OneTask $supName).State -ne 'Disabled') 'Supervisor unexpectedly disabled'
  Need ((Count-LauncherProcesses $oldLauncher) -eq 0) 'Original WAIT launcher came back'
  "PR326_CUTOVER=PHYSICAL_PASS_PENDING_INDEPENDENT_CLOUD_ACK"
  "BACKUP_PATH=$backupDir"
  "POST_CUTOVER_WAIT_CYCLES=$($observed.Count)"
  "WAIT_SOURCE_PROGRESS_STEPS=$($p.successful_source_steps)"
  'PR326_PAPER_ONLY=True'
  'V3_CAS_AND_REAL_MONEY=False'
  exit 0
} catch {
  $problem=$_.Exception.Message
  "PR326_CUTOVER_ERROR=$problem"
  if($enteredMutation) {
    try {
      Disable-ScheduledTask -TaskName $supName -ErrorAction SilentlyContinue|Out-Null
      if([string](Get-ScheduledTask -TaskName $supName).State -eq 'Running'){Stop-ScheduledTask -TaskName $supName -ErrorAction SilentlyContinue}
      Disable-ScheduledTask -TaskName $waitName -ErrorAction SilentlyContinue|Out-Null
      Stop-ScheduledTask -TaskName $waitName -ErrorAction SilentlyContinue
      Need (Wait-TaskStopped $waitName 30) 'Rollback WAIT stop not confirmed'
      $until=(Get-Date).AddSeconds(30)
      while((Count-LauncherProcesses $newLauncher) -gt 0 -and (Get-Date) -lt $until){Start-Sleep -Milliseconds 500}
      Require-NoWaitProcess
      Register-ScheduledTask -TaskName $waitName -Xml $oldWaitXml -Force -ErrorAction Stop|Out-Null
      Register-ScheduledTask -TaskName $supName -Xml $oldSupXml -Force -ErrorAction Stop|Out-Null
      Need ((Sha $oldLauncher) -ieq $oldLauncherHash) 'Original WAIT source changed during rollback'
      Need ((Sha $oldSupervisor) -ieq $oldSupervisorHash) 'Original Supervisor source changed during rollback'
      Enable-ScheduledTask -TaskName $waitName -ErrorAction Stop|Out-Null
      Start-ScheduledTask -TaskName $waitName -ErrorAction Stop
      Enable-ScheduledTask -TaskName $supName -ErrorAction Stop|Out-Null
      Start-ScheduledTask -TaskName $supName -ErrorAction Stop
      'PR326_ROLLBACK=OLD_TASKS_RESTORED'
    } catch {
      'PR326_ROLLBACK=MANUAL_INTERVENTION_REQUIRED_NO_BLIND_RESTART'
      'PR326_ROLLBACK_ERROR='+$_.Exception.Message
    }
  }
  "BACKUP_PATH=$backupDir"
  exit 2
}
