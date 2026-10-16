param(
  [string]$TradingRoot='C:\Users\ADMIN\Trading',
  [switch]$Execute,
  [string]$Confirm=''
)
# One-shot originalhost upgrade of exactly ONE protected V2R4 Paper CloudSync Task.
# Read-only preview by default; never changes Candidates, WAIT, Lifecycle,
# Supervisor, Cloud CAS, V3 Paper, or the historical immutable Python source.
$ErrorActionPreference='Stop'
$name='CryptoMiniPC-V2R4PaperCloudSync'
$oldHash='168E80127FA5B3400D7241FB37E86BC54EFE0C2BFADF452EDD4BE0A4BD67B559'
$sourceCommit='b97a45d589f6813b28fe94f62fd37e94e764d054'
$sourceBlob='63eca1cbc596819c36796f0a97155513002dd0ed'
$root=[IO.Path]::GetFullPath($TradingRoot).TrimEnd('\')
$stageDir=Join-Path $root 'Staging\PR332-CloudSync-20261016-113256-d5c85c73'
$backupDir=Join-Path $root 'Backups\PR332-CloudSync-Vorher-20261016-113256-d5c85c73'
$oldSource=Join-Path $root 'Runtime\v2r4-paper-stage-d8b35a8ec2e6\v2r4-paper-cloud-sync.py'
$newSource=Join-Path $stageDir 'v2r4-paper-cloud-sync.py'
$taskXmlPath=Join-Path $backupDir 'CloudSync.task.xml'
$manifestPath=Join-Path $backupDir 'manifest.json'
$heartbeatPath=Join-Path $root 'State\v2r4-paper-cloud-sync-heartbeat.json'
$supervisorPath=Join-Path $root 'State\minipc-runtime-supervisor.json'
$attempted=$false
$oldXml=$null

function Require([bool]$Ok,[string]$Why){if(-not $Ok){throw $Why}}
function Sha([string]$Path){
  Require (Test-Path -LiteralPath $Path -PathType Leaf) ('File missing: '+(Split-Path -Leaf $Path))
  (Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop).Hash
}
function Get-Pr332TaskXml([string]$Xml,[string]$OldPath,[string]$NewPath){
  [xml]$d=$Xml
  $ns=[Xml.XmlNamespaceManager]::new($d.NameTable)
  $ns.AddNamespace('t',$d.DocumentElement.NamespaceURI)
  $exec=@($d.SelectNodes('/t:Task/t:Actions/t:Exec',$ns))
  Require ($exec.Count -eq 1) 'Invalid executable task action count'
  $arg=$exec[0].SelectSingleNode('t:Arguments',$ns)
  Require ($null -ne $arg) 'Missing task arguments'
  $text=[string]$arg.InnerText
  Require (([regex]::Matches($text,[regex]::Escape($OldPath),
           [Text.RegularExpressions.RegexOptions]::IgnoreCase)).Count -eq 1) 'Old script reference not unique'
  $replacement=[regex]::Replace($text,[regex]::Escape($OldPath),
       [Text.RegularExpressions.MatchEvaluator]{param($m) $NewPath},
       [Text.RegularExpressions.RegexOptions]::IgnoreCase)
  Require (([regex]::Matches($replacement,[regex]::Escape($NewPath),
           [Text.RegularExpressions.RegexOptions]::IgnoreCase)).Count -eq 1) 'New script reference not unique'
  $arg.InnerText=$replacement
  $settings=$d.SelectSingleNode('/t:Task/t:Settings',$ns)
  Require ($null -ne $settings) 'Task settings missing'
  $enabled=$settings.SelectSingleNode('t:Enabled',$ns)
  if($null -eq $enabled){
    $enabled=$d.CreateElement('Enabled',$d.DocumentElement.NamespaceURI)
    [void]$settings.AppendChild($enabled)
  }
  $enabled.InnerText='false'
  return $d.OuterXml
}
function ScriptProcesses([string]$Path){
  @(
    Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" -ErrorAction Stop |
     Where-Object {
       ([string]$_.CommandLine).IndexOf($Path,[StringComparison]::OrdinalIgnoreCase) -ge 0
     }
  )
}
function Test-Pr332TaskFamily([object[]]$Items){
  if(@($Items).Count -ne 2){return $false}
  $parents=@($Items | Where-Object {
    $pidValue=$_.ProcessId
    @($Items | Where-Object { $_.ParentProcessId -eq $pidValue }).Count -eq 1
  })
  return ($parents.Count -eq 1)
}
function WaitNoOldOrNew([int]$Seconds) {
  $until=(Get-Date).AddSeconds($Seconds)
  do{
    if(@(ScriptProcesses $oldSource).Count -eq 0 -and
       @(ScriptProcesses $newSource).Count -eq 0){return $true}
    Start-Sleep -Milliseconds 350
  }while((Get-Date) -lt $until)
  return $false
}
function Task(){
  $task=Get-ScheduledTask -TaskName $name -ErrorAction Stop
  Require ($task.TaskPath -eq '\' -and @($task.Actions).Count -eq 1) 'Task path or action count drift'
  Require ([string]$task.Principal.UserId -in @('SYSTEM','NT AUTHORITY\SYSTEM','S-1-5-18')) 'SYSTEM identity drift'
  Require ([string]$task.Settings.MultipleInstances -eq 'IgnoreNew') 'MultipleInstances drift'
  return $task
}
function VerifyAcl([string]$Directory){
  $acl=Get-Acl -LiteralPath $Directory
  $allow=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
  $owners=@($allow | ForEach-Object {$_.IdentityReference.Value} | Sort-Object -Unique)
  $expected=@('S-1-5-18','S-1-5-32-544')
  Require ($acl.AreAccessRulesProtected -and
    @($allow | Where-Object {$_.AccessControlType -ne 'Allow'}).Count -eq 0 -and
    @($owners | Where-Object {$_ -notin $expected}).Count -eq 0 -and
    @($expected | Where-Object {$_ -notin $owners}).Count -eq 0) 'Backup/Stage ACL drift'
}
function FreshSupervisor(){
  $r=Get-Content -LiteralPath $supervisorPath -Raw -ErrorAction Stop|ConvertFrom-Json
  $age=([datetime]::UtcNow-([datetime]$r.checked_at_utc).ToUniversalTime()).TotalSeconds
  Require ($r.status -eq 'HEALTHY' -and $age -ge 0 -and $age -le 150 -and
    $r.v3_paper_old_intake_fence.mode -eq 'NONE' -and
    $r.maintenance.mode -eq 'NONE') 'Unhealthy/old Supervisor or marker'
}
function WaitHealthy([string]$ExpectedSource,[datetime]$AfterUtc,[bool]$New){
  $until=(Get-Date).AddSeconds(110)
  do {
    $t=Task
    $only=@(ScriptProcesses $ExpectedSource)
    $other=if($New){@(ScriptProcesses $oldSource)}else{@(ScriptProcesses $newSource)}
    $r=$null
    try{$r=Get-Content -LiteralPath $heartbeatPath -Raw -ErrorAction Stop|ConvertFrom-Json}catch{}
    if($null -ne $r -and [string]$t.State -eq 'Running' -and
       $only.Count -ge 1 -and $only.Count -le 2 -and $other.Count -eq 0 -and
       ([datetime]$r.checked_at_utc).ToUniversalTime() -gt $AfterUtc -and
       $r.status -eq 'HEALTHY' -and
       $r.series_id -eq 'PAPER-V2R4-20261009T110135Z'){
      if(-not $New -or $r.v3_fence_cloud_sync_lane -eq 'ACTIVE_ORIGINAL'){
        return $true
      }
    }
    Start-Sleep -Seconds 2
  }while((Get-Date) -lt $until)
  return $false
}
# Original runtime and two protected stage resources are immutable source pins.
Require ($root -ieq 'C:\Users\ADMIN\Trading') 'Unexpected TradingRoot'
VerifyAcl $stageDir
VerifyAcl $backupDir
$m=Get-Content -LiteralPath $manifestPath -Raw -ErrorAction Stop|ConvertFrom-Json
Require ($m.kind -eq 'PR332_CLOUDSYNC_PROTECTED_STAGE_V1' -and
  $m.task_name -eq $name -and
  $m.old_source -ieq $oldSource -and
  $m.new_source -ieq $newSource -and
  $m.new_git_commit -eq $sourceCommit -and
  $m.new_git_blob_sha1 -eq $sourceBlob -and
  $m.task_switched -eq $false -and
  $m.runtime_restarted -eq $false) 'Protected manifest identity mismatch'
Require ((Sha $oldSource) -eq $oldHash -and
  (Sha $newSource) -eq [string]$m.new_source_sha256 -and
  (Sha $taskXmlPath) -eq [string]$m.original_task_xml_sha256) 'Original/new file SHA mismatch'
Require ((Get-Content -LiteralPath $newSource -Raw).Contains('V3_PRECOMMIT_NO_NETWORK_HOLD')) 'PR332 fence missing'
$oldXml=[IO.File]::ReadAllText($taskXmlPath)
Require ($oldXml -ceq (Export-ScheduledTask -TaskName $name -ErrorAction Stop)) 'Original Task XML no longer current'
$t=Task
Require ([string]$t.State -eq 'Running') 'CloudSync not running before change'
Require (([regex]::Matches([string]$t.Actions[0].Arguments,[regex]::Escape($oldSource),
  [Text.RegularExpressions.RegexOptions]::IgnoreCase)).Count -eq 1) 'Current original source is not pinned'
$family=@(ScriptProcesses $oldSource)
Require (Test-Pr332TaskFamily $family) 'Original python parent/child is not exact'
Require (@(ScriptProcesses $newSource).Count -eq 0) 'New staged worker already running'
foreach($marker in @('State\v3-experimental-paper-old-intake-fence.json',
                    'State\v2r4-technical-cutover-maintenance.json')){
 Require (-not (Test-Path -LiteralPath (Join-Path $root $marker))) 'Cutover marker present'
}
foreach($protected in @('CryptoMiniPC-V2R4PaperCandidates',
 'CryptoMiniPC-V2R4PaperWait','CryptoMiniPC-V2R4PaperLifecycle')){
 Require ([string](Get-ScheduledTask -TaskName $protected).State -eq 'Running') "Protected original Task unhealthy"
}
FreshSupervisor
$candidateXml=Get-Pr332TaskXml $oldXml $oldSource $newSource
Write-Output 'PR332_CLOUDSYNC_ORIGINALHOST_PREFLIGHT=PASS'
Write-Output 'PR332_CLOUDSYNC_TASK_PREVIEW_ONLY=True'
if(-not $Execute){return}
Require ($Confirm -ceq 'PR332-CLOUDSYNC-ONLY') 'Execute requires exact operator confirmation'
Require (-not (Test-Path -LiteralPath (Join-Path $backupDir 'switch-attempted.json'))) 'This one-shot operator was already attempted'
[IO.File]::WriteAllText((Join-Path $backupDir 'switch-attempted.json'),
 '{"kind":"PR332_CLOUDSYNC_SINGLE_ATTEMPT_V1","real_cas":false,"v3_writer":false}',
 [Text.UTF8Encoding]::new($false))
$attempted=$true
try{
  Disable-ScheduledTask -TaskName $name -ErrorAction Stop|Out-Null
  Stop-ScheduledTask -TaskName $name -ErrorAction Stop
  Require (WaitNoOldOrNew 35) 'Old CloudSync process family remained after scheduler stop: do not start a second'
  Register-ScheduledTask -TaskName $name -Xml $candidateXml -Force -ErrorAction Stop|Out-Null
  $t=Task
  Require ([string]$t.State -eq 'Disabled') 'New Task XML was not imported disabled'
  Require (([string]$t.Actions[0].Arguments).Contains($newSource)) 'New Task action not installed'
  $started=[datetime]::UtcNow
  Enable-ScheduledTask -TaskName $name -ErrorAction Stop|Out-Null
  Start-ScheduledTask -TaskName $name -ErrorAction Stop
  Require (WaitHealthy $newSource $started $true) 'New PR332 CloudSync did not produce fresh HEALTHY original-series ACK'
  Write-Output 'PR332_CLOUDSYNC_SWITCH=PASS'
  Write-Output 'PR332_NEW_RUNTIME_SHA=VERIFIED'
  Write-Output 'PR332_OLD_RUNTIME_PRESERVED=True'
  Write-Output 'PR332_REAL_CLOUD_CAS=False'
  Write-Output 'PR332_V3_WRITER_STARTED=False'
}catch{
  $switchError=$_.Exception.Message
  $rollback='MANUAL_INTERVENTION_REQUIRED'
  try{
    Disable-ScheduledTask -TaskName $name -ErrorAction Stop|Out-Null
    if([string](Get-ScheduledTask -TaskName $name).State -eq 'Running'){
      Stop-ScheduledTask -TaskName $name -ErrorAction Stop
    }
    Require (WaitNoOldOrNew 35) 'A Python worker is still alive; do not launch a duplicate rollback worker'
    Register-ScheduledTask -TaskName $name -Xml $oldXml -Force -ErrorAction Stop|Out-Null
    Require (([string](Task).Actions[0].Arguments).Contains($oldSource)) 'Original Task source restore mismatch'
    $returnAt=[datetime]::UtcNow
    Enable-ScheduledTask -TaskName $name -ErrorAction Stop|Out-Null
    Start-ScheduledTask -TaskName $name -ErrorAction Stop
    Require (WaitHealthy $oldSource $returnAt $false) 'Original CloudSync could not be verified HEALTHY'
    $rollback='OLD_CLOUDSYNC_TASK_RESTORED_HEALTHY'
  }catch{
    Write-Output ('PR332_ROLLBACK_DETAIL='+$_.Exception.Message)
  }
  Write-Output ('PR332_SWITCH_ERROR='+$switchError)
  Write-Output ('PR332_ROLLBACK='+$rollback)
  throw 'CloudSync switch not approved as PASS; verify displayed rollback status'
}
