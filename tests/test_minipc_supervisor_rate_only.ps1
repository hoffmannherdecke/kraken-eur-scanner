# Executes only the extracted pure policy function: NO Windows task calls,
# NO Kraken requests, NO runtime file writes or process restarts.
$ErrorActionPreference = 'Stop'
$path = Join-Path (Split-Path $PSScriptRoot -Parent) 'tools/minipc-runtime-supervisor.ps1'
$tokens=$null; $errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile(
  $path,[ref]$tokens,[ref]$errors
)
if($errors.Count -ne 0){ throw ($errors | Out-String) }
$fn=@($ast.FindAll({
  param($a)
  $a -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
  $a.Name -eq 'Test-WaitRateOnly'
},$true))
if($fn.Count -ne 1){ throw 'Expected exactly one pure rate-only source policy function' }
. ([Scriptblock]::Create($fn[0].Extent.Text))

function Make-Hb([string]$status,[hashtable]$classes,[int]$rechecks=0,[int]$sourceFailures=1){
  [pscustomobject]@{
    status=$status
    error_classes=[pscustomobject]$classes
    counters=[pscustomobject]@{
      fresh_recheck_failures=$rechecks
      data_unavailable_checks=$sourceFailures
    }
  }
}
function Check([bool]$expected,[object]$hb,[object]$age,[bool]$running,[string]$label){
  $actual = Test-WaitRateOnly -Heartbeat $hb -AgeSeconds $age -MaxAgeSeconds 30 -TaskRunning $running
  if($actual -ne $expected){ throw "SOURCE_RATE_POLICY_FAIL: $label expected $expected actual $actual" }
}
$rate=Make-Hb 'DEGRADED' @{KRAKEN_RATE_LIMIT=3}
Check $true $rate 3 $true 'fresh rate-only running'
Check $false $rate 40 $true 'stale heartbeat'
Check $false $rate -40 $true 'future heartbeat'
Check $false $rate 3 $false 'task stopped'
Check $false (Make-Hb 'DEGRADED' @{KRAKEN_RATE_LIMIT=1; KRAKEN_UNAVAILABLE=1}) 3 $true 'mixed errors'
Check $false (Make-Hb 'DEGRADED' @{KRAKEN_RATE_LIMIT=1} 1) 3 $true 'failed paper recheck'
Check $false (Make-Hb 'DEGRADED' @{KRAKEN_RATE_LIMIT=1} 0 0) 3 $true 'missing source error'
Check $false (Make-Hb 'DEGRADED' @{KRAKEN_RATE_LIMIT=0}) 3 $true 'zero rate events'
Check $false (Make-Hb 'HEALTHY' @{}) 3 $true 'healthy'
Check $false $null 3 $true 'null heartbeat'
Write-Output 'SUPERVISOR_SOURCE_RATE_POLICY_10_CASES_PASS'


# Only the extracted pure function is executed; never run the Windows
# Supervisor, Kraken, the task scheduler or local disk mutation in CI.
$progressFn=@($ast.FindAll({
  param($a)
  $a -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
  $a.Name -eq 'Test-WaitSourceProgress'
},$true))
if($progressFn.Count -ne 1){throw 'Expected one pure WAIT source-progress policy'}
. ([Scriptblock]::Create($progressFn[0].Extent.Text))
function ProgressFixture {
  [pscustomobject]@{
    kind='V2R4_WAIT_SOURCE_PROGRESS_V1';status='IN_PROGRESS_NOT_HEALTHY'
    cycle_started_at_utc='2026-10-15T18:00:10Z'
    last_source_progress_at_utc='2026-10-15T18:01:30Z'
    successful_source_steps=2;worker_pid=3001;paper_only=$true;order_api=$false
  }
}
function HbFixture([string]$At='2026-10-15T17:59:59Z',[string]$Status='HEALTHY') {
  [pscustomobject]@{checked_at_utc=$At;status=$Status}
}
$observed=[datetime]'2026-10-15T18:01:45Z'
function CheckProgress([bool]$Expected,[object]$Progress,[object]$Heartbeat,
                       [bool]$Running=$true,[bool]$Verified=$true,[string]$Label='') {
  $actual=Test-WaitSourceProgress -Progress $Progress -Heartbeat $Heartbeat -ObservedUtc $observed -TaskRunning $Running -VerifiedWorker $Verified
  if($actual -ne $Expected){throw "WAIT_PROGRESS_POLICY_FAIL $Label expected=$Expected got=$actual"}
}
CheckProgress $true (ProgressFixture) (HbFixture) -Label 'recent source replies from verified live child'
CheckProgress $false $null (HbFixture) -Label 'no progress evidence'
CheckProgress $false (ProgressFixture) $null -Label 'missing completion context'
CheckProgress $false (ProgressFixture) (HbFixture) $false -Label 'stopped scheduler'
CheckProgress $false (ProgressFixture) (HbFixture) $true $false -Label 'unverified PID'
$p=ProgressFixture;$p.kind='FAKE'
CheckProgress $false $p (HbFixture) -Label 'wrong schema'
$p=ProgressFixture;$p.status='HEALTHY'
CheckProgress $false $p (HbFixture) -Label 'never treat progress as healthy'
$p=ProgressFixture;$p.successful_source_steps=0
CheckProgress $false $p (HbFixture) -Label 'no successful source reads'
$p=ProgressFixture;$p.worker_pid=-1
CheckProgress $false $p (HbFixture) -Label 'invalid worker PID'
$p=ProgressFixture;$p.order_api=$true
CheckProgress $false $p (HbFixture) -Label 'orders not authorized'
$p=ProgressFixture;$p.paper_only=$false
CheckProgress $false $p (HbFixture) -Label 'non-paper source'
$p=ProgressFixture;$p.last_source_progress_at_utc='2026-10-15T17:59:30Z'
CheckProgress $false $p (HbFixture '2026-10-15T17:59:00Z') -Label 'stale progress means real stall'
$p=ProgressFixture;$p.last_source_progress_at_utc='2026-10-15T18:01:51Z'
CheckProgress $false $p (HbFixture) -Label 'future progress denied'
$p=ProgressFixture;$p.cycle_started_at_utc='2026-10-15T17:50:00Z'
CheckProgress $false $p (HbFixture '2026-10-15T17:49:00Z') -Label 'unbounded cycle denied'
$p=ProgressFixture;$p.cycle_started_at_utc='2026-10-15T18:01:40Z'
CheckProgress $false $p (HbFixture) -Label 'source before start denied'
CheckProgress $false (ProgressFixture) (HbFixture '2026-10-15T18:01:31Z') -Label 'newer healthy completion wins'
CheckProgress $false (ProgressFixture) (HbFixture '2026-10-15T18:01:00Z' 'DEGRADED') -Label 'newer degraded completion wins'
$p=ProgressFixture;$p.last_source_progress_at_utc='2026-10-15T18:01:30'
CheckProgress $false $p (HbFixture) -Label 'timezone required'
$p=ProgressFixture;$p.cycle_started_at_utc='2026-10-15T18:02:00Z'
CheckProgress $false $p (HbFixture) -Label 'future cycle start denied'
Write-Output 'SUPERVISOR_WAIT_SOURCE_PROGRESS_PURE_19_CASES_PASS'

# Static architecture proof, never invoke the live host check.
$progressCode=Get-Content -LiteralPath $path -Raw
foreach($required in @('[switch]$WaitSourceProgressOptIn',
 'WAIT_SOURCE_ACTIVE_NOT_HEALTHY', 'ACTIVE_NOT_HEALTHY',
 'Get-CimInstance -ClassName Win32_Process', 'Test-WaitSourceWorkerOnHost',
 'v2r4-paper-wait-source-progress.json')){
 if(-not $progressCode.Contains($required)){throw "WAIT_PROGRESS_SOURCE_GUARD_MISSING $required"}
}
Write-Output 'SUPERVISOR_WAIT_SOURCE_PROGRESS_OPT_IN_STATIC_GUARD_PASS'

# Mock pinned immutable PR291 or successor Task/SYSTEM worker and launcher fingerprint:
# no actual CIM, Scheduler, HTTP, file hash or machine task mutations.
$hostFn=@($ast.FindAll({
 param($a)
 $a -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
 $a.Name -eq 'Test-WaitSourceWorkerOnHost'
},$true))
if($hostFn.Count -ne 1){throw 'Expected one WAIT original-host PID verifier'}
. ([Scriptblock]::Create($hostFn[0].Extent.Text))
$fakeRoot=Join-Path $PSScriptRoot 'SyntheticNoDiskTrading'
$fakeLauncher=Join-Path $fakeRoot 'Staging\v2r4-wait-pr291-isolated\wait_launcher.py'
$script:fakeHash='C5E43D62976BDF2079A3A0402E57658ABA8A33D427B0CF0D56737565B84DD51D'
$script:fakeExpectedHash=$script:fakeHash
$script:fakeExists=$true
function ValidFakeTask {
 [pscustomobject]@{
   State='Running'
   Actions=@([pscustomobject]@{
     Execute='C:\Trading\Runtime\venv\Scripts\python.exe'
     Arguments=('"'+$fakeLauncher+'" --execute-recheck')
   })
 }
}
function ValidFakeWorker {
 [pscustomobject]@{
  Name='python.exe'
  CommandLine=('python.exe "' + $fakeLauncher + '"')
  CreationDate=[datetime]'2026-10-15T17:59:50Z'
 }
}
$script:fakeTask=ValidFakeTask
$script:fakeProcess=ValidFakeWorker
function Get-ScheduledTask {
 param([string]$TaskName,[object]$ErrorAction)
 if($TaskName -cne 'CryptoMiniPC-V2R4PaperWait'){throw 'Unexpected Task lookup'}
 return $script:fakeTask
}
function Test-Path {
 param([string]$LiteralPath,[string]$PathType)
 if($LiteralPath.Replace('\','/') -ine $fakeLauncher.Replace('\','/')){throw 'Unexpected test file path'}
 return $script:fakeExists
}
function Get-FileHash {
 param([string]$LiteralPath,[string]$Algorithm,[object]$ErrorAction)
 if($LiteralPath.Replace('\','/') -ine $fakeLauncher.Replace('\','/') -or
    $Algorithm -cne 'SHA256'){throw 'Unexpected file hash request'}
 return [pscustomobject]@{Hash=$script:fakeHash}
}
function Get-CimInstance {
 param([string]$ClassName,[string]$Filter,[object]$ErrorAction)
 if($ClassName -cne 'Win32_Process' -or $Filter -cne 'ProcessId = 3001'){
  throw 'Unexpected CIM process query'
 }
 return $script:fakeProcess
}
function ExpectHost([bool]$Expected,[string]$Case,[string]$OverridePath=''){
 $p=if($OverridePath){$OverridePath}else{$fakeLauncher}
 $actual=Test-WaitSourceWorkerOnHost -Progress (ProgressFixture) -TradingRoot $fakeRoot -PinnedLauncherPath $p -PinnedLauncherSha256 $script:fakeExpectedHash
 if($actual -ne $Expected){throw "ORIGINAL_WAIT_OWNER_POLICY_FAIL $Case expected=$Expected got=$actual"}
}
ExpectHost $true 'physical PR291 launcher exact file owner/child'
$script:fakeTask=ValidFakeTask;$script:fakeTask.State='Ready'
ExpectHost $false 'Task not running'
$script:fakeTask=ValidFakeTask;$script:fakeTask.Actions=@()
ExpectHost $false 'Task has no action'
$script:fakeTask=ValidFakeTask;$script:fakeTask.Actions[0].Arguments='"C:\Old\wait_launcher.py"'
ExpectHost $false 'wrong Task launcher path'
$script:fakeTask=ValidFakeTask;$script:fakeTask.Actions[0].Execute='cmd.exe'
ExpectHost $false 'wrong Task executable'
$script:fakeTask=ValidFakeTask;$script:fakeHash='a' * 64
ExpectHost $false 'launcher hash changed'
$script:fakeHash='C5E43D62976BDF2079A3A0402E57658ABA8A33D427B0CF0D56737565B84DD51D'
$script:fakeExists=$false
ExpectHost $false 'launcher missing'
$script:fakeExists=$true
$script:fakeProcess=ValidFakeWorker;$script:fakeProcess.CommandLine='python.exe foreign.py'
ExpectHost $false 'wrong process script'
$script:fakeProcess=ValidFakeWorker;$script:fakeProcess.CommandLine=('python.exe "' + $fakeLauncher + '.fake"')
ExpectHost $false 'script prefix spoof'
$script:fakeProcess=ValidFakeWorker;$script:fakeProcess.Name='foreign.exe'
ExpectHost $false 'foreign process executable'
$script:fakeProcess=ValidFakeWorker;$script:fakeProcess.CreationDate=[datetime]'2026-10-15T18:02:00Z'
ExpectHost $false 'recycled PID created after cycle'
$script:fakeProcess=$null
ExpectHost $false 'process absent'
$script:fakeTask=ValidFakeTask;$script:fakeProcess=ValidFakeWorker
Write-Output 'SUPERVISOR_PR291_WAIT_WORKER_MOCK_12_CASES_PASS'

# The Supervisor opt-in is deliberately tied to release pins, not a hardcoded
# original PR291 path. Test successor version rollover without host mutation.
$script:fakeExpectedHash=''
ExpectHost $false 'missing required supervisor pinned hash'
$script:fakeExpectedHash='f' * 64
ExpectHost $false 'mismatched supplied immutable release hash'
$script:fakeExpectedHash=$script:fakeHash
ExpectHost $false 'outside Trading Staging root' '/tmp/untrusted/wait_launcher.py'
$oldFakeLauncher=$fakeLauncher
$fakeLauncher=Join-Path $fakeRoot 'Staging\v2r4-wait-pr326-isolated-2318b2417d61\wait_launcher.py'
$script:fakeTask=ValidFakeTask
$script:fakeProcess=ValidFakeWorker
ExpectHost $true 'pinned immutable PR326 successor release path accepted'
$fakeLauncher=$oldFakeLauncher
$script:fakeTask=ValidFakeTask
$script:fakeProcess=ValidFakeWorker
Write-Output 'SUPERVISOR_VERSIONED_WAIT_LAUNCHER_MOCK_4_CASES_PASS'

# Restore native builtins so downstream policy tests stay independent.
Remove-Item Function:\Get-ScheduledTask -ErrorAction SilentlyContinue
Remove-Item Function:\Test-Path -ErrorAction SilentlyContinue
Remove-Item Function:\Get-FileHash -ErrorAction SilentlyContinue
Remove-Item Function:\Get-CimInstance -ErrorAction SilentlyContinue


# PR326 offline stage packager is never run in CI: enforce its parse and
# non-production scope with static read-only assertions.
$stageTool=Join-Path (Split-Path $PSScriptRoot -Parent) 'tools/stage-minipc-pr326-wait-offline.ps1'
if(-not (Test-Path -LiteralPath $stageTool -PathType Leaf)){throw 'Missing existing PR326 offline stage tool'}
$parseTokens=$null
$parseErrors=$null
[void][System.Management.Automation.Language.Parser]::ParseFile($stageTool,[ref]$parseTokens,[ref]$parseErrors)
if(@($parseErrors).Count -gt 0){
  foreach($syntaxError in $parseErrors){ Write-Output ('PR326_STAGE_PARSE: '+[string]$syntaxError) }
  throw 'PR326_OFFLINE_STAGE_POWERSHELL_PARSE_FAILED'
}
$stageSource=Get-Content -LiteralPath $stageTool -Raw
foreach($required in @('ExpectedSourceSha','INACTIVE_OFFLINE_STAGE_ONLY',
  'PR326_INACTIVE_WAIT_STAGE_V1','original_pr291_unchanged',
  'market_data\kraken_public_budget.py','PYTHON_COMPILE=PASS',
  'Backup manifest SHA mismatch','Original SHA256 is not 64 characters',
  'Backup contents differ from saved manifest',
  'WINDOWS_TASKS_UNCHANGED=True')){
  if(-not $stageSource.Contains($required)){throw "PR326_OFFLINE_STAGE_GUARD_MISSING $required"}
}
foreach($forbidden in @('Start-ScheduledTask','Stop-ScheduledTask',
  'Register-ScheduledTask','Set-ScheduledTask','git pull',
  'Invoke-WebRequest','Invoke-RestMethod','api.kraken.com')){
  if($stageSource.IndexOf($forbidden,[StringComparison]::OrdinalIgnoreCase) -ge 0){
    throw "PR326_OFFLINE_STAGE_FORBIDDEN_CALL $forbidden"
  }
}
if($stageSource.Contains("'v2r4_wait_runtime.py'='554E6CAF5E097D1684AB1F7557733CECFB4BCE6AF0A5BF88DBD106BF9BBA40'")){
  throw 'PR326_OFFLINE_STAGE_62_DIGIT_SHA_REGRESSION'
}
Write-Output 'PR326_PINNED_OFFLINE_STAGE_STATIC_GUARDS_PASS'


# Pure V3 supervisor intake fence regression; NEVER execute the Supervisor.
$guard=@($ast.FindAll({
  param($a)
  $a -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
  $a.Name -eq 'Test-V3PaperIntakeFence'
},$true))
if($guard.Count -ne 1){ throw 'Missing one V3 intake policy function' }
. ([Scriptblock]::Create($guard[0].Extent.Text))
function ValidFence {
  [pscustomobject]@{
    kind='V3_EXPERIMENTAL_OLD_INTAKE_FENCE_V1'
    phase='ARMED'
    predecessor_series_id='PAPER-V2R4-20261009T110135Z'
    proposed_successor_series_id='PAPER-V3-20261014-EXPERIMENT'
    proposed_v3_repo_sha=('a' * 40)
    proposed_v3_bundle_sha256=('b' * 64)
    proposed_v3_strategy_sha256=('c' * 64)
    task_names=@('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait')
    paper_only=$true; orders_enabled=$false; real_money_actions=$false
    persistent_until_explicit_owner_release=$true
  }
}
function ExpectFence([string]$Expected,[bool]$Present,[object]$Marker,[string]$Label){
  $actual=Test-V3PaperIntakeFence -Present $Present -Marker $Marker
  if($actual -cne $Expected){throw "V3_FENCE_FAIL $Label expected=$Expected actual=$actual"}
}
ExpectFence 'NONE' $false $null 'normal V2R4 remains unchanged'
ExpectFence 'INVALID_FAIL_CLOSED' $true $null 'malformed marker'
$valid=ValidFence
ExpectFence 'ARMED' $true $valid 'prepared owner fence'
$valid.phase='QUIESCED'
ExpectFence 'QUIESCED' $true $valid 'old writer quiesced only after Task disabled'
$valid.phase='CLOUD_COMMITTED'
ExpectFence 'CLOUD_COMMITTED' $true $valid 'durable postcommit'
$valid.phase='UNKNOWN'
ExpectFence 'INVALID_FAIL_CLOSED' $true $valid 'unknown phase'
$valid=ValidFence
$valid.predecessor_series_id='PAPER-V2R4-20261007T184255Z'
ExpectFence 'INVALID_FAIL_CLOSED' $true $valid 'old technical series must not rearm'
$valid=ValidFence
$valid.task_names+=@('CryptoMiniPC-V2R4PaperLifecycle')
ExpectFence 'INVALID_FAIL_CLOSED' $true $valid 'legacy lifecycle must continue'
$valid=ValidFence
$valid.orders_enabled=$true
ExpectFence 'INVALID_FAIL_CLOSED' $true $valid 'order api prohibited'
$valid=ValidFence
$valid.persistent_until_explicit_owner_release=$false
ExpectFence 'INVALID_FAIL_CLOSED' $true $valid 'must not expire automatically'
$valid=ValidFence
$valid.proposed_v3_bundle_sha256='bad'
ExpectFence 'INVALID_FAIL_CLOSED' $true $valid 'release bundle pin required'
Write-Output 'SUPERVISOR_V3_PAPER_INTAKE_PURE_POLICY_11_CASES_PASS'

# Execute ONLY the pure old-native baseline function from the existing V3
# READ-ONLY readiness script. No Windows task querying/changes in CI.
$physical=Join-Path (Split-Path $PSScriptRoot -Parent) 'tools/check-minipc-v3-physical-writer-readiness.ps1'
$ptok=$null; $perr=$null
$past=[System.Management.Automation.Language.Parser]::ParseFile($physical,[ref]$ptok,[ref]$perr)
if($perr.Count -ne 0){ throw ($perr | Out-String) }
$native=@($past.FindAll({
  param($a)
  $a -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
  $a.Name -eq 'Test-V3OldIntakeNativeBaseline'
},$true))
if($native.Count -ne 1){throw 'Expected exactly one native baseline pure policy function'}
. ([Scriptblock]::Create($native[0].Extent.Text))

# Before any host use, reject executable task writers or HTTP on this
# read-only evidence path. Get-ScheduledTask and Export-ScheduledTask are safe.
$commands=@($past.FindAll({
  param($a) $a -is [System.Management.Automation.Language.CommandAst]
},$true) | ForEach-Object {$_.GetCommandName()})
foreach($unsafe in @('Stop-ScheduledTask','Start-ScheduledTask','Disable-ScheduledTask',
                    'Enable-ScheduledTask','Register-ScheduledTask','Unregister-ScheduledTask',
                    'Set-ScheduledTask','Set-Content','Out-File','Invoke-RestMethod',
                    'Invoke-WebRequest','Remove-Item','Copy-Item','Move-Item')){
  if($commands -contains $unsafe){throw "Unsafe native read-only preflight command: $unsafe"}
}

function NativeFixture([string]$Name) {
  $script=if($Name -eq 'CryptoMiniPC-V2R4PaperWait'){'wait_launcher.py'}else{'v2r4-paper-local-runtime.py'}
  return [pscustomobject]@{
    task_name=$Name; state='Running'; principal_is_system=$true
    action_count=1; documented_script_basename_hint_matches=$true
    action_script_basename=$script
    trigger_count=1; only_boot_trigger=$true
    restart_count=3; restart_interval='PT1M'; multiple_instances='IgnoreNew'
    native_scheduler_xml_status='READ'; heartbeat_fresh_for_role=$true
  }
}
function CheckNative([bool]$Expected,[object]$Record,[string]$Label) {
  $actual=Test-V3OldIntakeNativeBaseline -Record $Record
  if($actual -ne $Expected){throw "NATIVE_BASELINE_POLICY_FAIL $Label expected=$Expected actual=$actual"}
}
$c=NativeFixture 'CryptoMiniPC-V2R4PaperCandidates'
$w=NativeFixture 'CryptoMiniPC-V2R4PaperWait'
CheckNative $true $c 'candidate original running BootTrigger 3/PT1M'
CheckNative $true $w 'WAIT original running BootTrigger 3/PT1M'
CheckNative $false $null 'missing original evidence'
$x=NativeFixture 'CryptoMiniPC-V2R4PaperCandidates'; $x.trigger_count=2
CheckNative $false $x 'extra boot or interval trigger'
$x=NativeFixture 'CryptoMiniPC-V2R4PaperWait'; $x.only_boot_trigger=$false
CheckNative $false $x 'not native boot-only'
$x=NativeFixture 'CryptoMiniPC-V2R4PaperCandidates'; $x.restart_count=2
CheckNative $false $x 'noncanonical restart count'
$x=NativeFixture 'CryptoMiniPC-V2R4PaperWait'; $x.restart_interval='PT5M'
CheckNative $false $x 'noncanonical restart interval'
$x=NativeFixture 'CryptoMiniPC-V2R4PaperCandidates'; $x.multiple_instances='Parallel'
CheckNative $false $x 'duplicate native instances'
$x=NativeFixture 'CryptoMiniPC-V2R4PaperWait'; $x.action_count=2
CheckNative $false $x 'unexpected second task action'
$x=NativeFixture 'CryptoMiniPC-V2R4PaperWait'; $x.action_script_basename='v2r4_wait_runtime.py'
CheckNative $false $x 'incorrect old WAIT launcher'
$x=NativeFixture 'CryptoMiniPC-V2R4PaperCandidates'; $x.principal_is_system=$false
CheckNative $false $x 'wrong native SYSTEM owner'
$x=NativeFixture 'CryptoMiniPC-V2R4PaperWait'; $x.heartbeat_fresh_for_role=$false
CheckNative $false $x 'stale original heartbeat'
$x=NativeFixture 'CryptoMiniPC-V2R4PaperWait'; $x.native_scheduler_xml_status='UNREADABLE'
CheckNative $false $x 'unreadable native XML'
$x=NativeFixture 'CryptoMiniPC-V2R4PaperLifecycle'
CheckNative $false $x 'cannot count old followup task as intake'
Write-Output 'V3_NATIVE_OLD_INTAKE_READONLY_BASELINE_14_CASES_PASS'



# Pure original mode and process-lineage guards, NEVER run the full Mini-PC
# script in CI, and never invoke Win32_Process/Task controls from tests.
foreach($name in @('Get-V3OldPaperMode','Test-V3OriginalPaperModeLineage')){
  $match=@($past.FindAll({
    param($a)
    $a -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
    $a.Name -eq $name
  },$true))
  if($match.Count -ne 1){throw "Missing unique pure role policy $name"}
  . ([Scriptblock]::Create($match[0].Extent.Text))
}
function ProcessFixture {
  @(
    [pscustomobject]@{Mode='candidates';PID=100;ParentPID=10;OriginalStage=$true}
    [pscustomobject]@{Mode='candidates';PID=101;ParentPID=100;OriginalStage=$true}
    [pscustomobject]@{Mode='lifecycle';PID=200;ParentPID=10;OriginalStage=$true}
    [pscustomobject]@{Mode='lifecycle';PID=201;ParentPID=200;OriginalStage=$true}
  )
}
function ExpectLineage([bool]$Expected,[object[]]$Rows,[string]$Candidate='candidates',[string]$Lifecycle='lifecycle',[string]$Label=''){
  $got=Test-V3OriginalPaperModeLineage -Rows $Rows -CandidatesTaskMode $Candidate -LifecycleTaskMode $Lifecycle
  if($got -ne $Expected){throw "MODE_LINEAGE_FAIL $Label expected=$Expected actual=$got"}
}
if((Get-V3OldPaperMode '--mode candidates --interval-seconds 2') -cne 'candidates'){throw 'Cannot parse candidate task'}
if((Get-V3OldPaperMode '--mode "lifecycle" --interval-seconds 60') -cne 'lifecycle'){throw 'Cannot parse original lifecycle task'}
if((Get-V3OldPaperMode '--mode candidates --mode lifecycle') -cne 'UNRESOLVED'){throw 'Conflicting mode must fail'}
if((Get-V3OldPaperMode '--mode buy') -cne 'UNRESOLVED'){throw 'Unknown mode must fail'}
if((Get-V3OldPaperMode '') -cne 'UNRESOLVED'){throw 'Empty mode must fail'}
ExpectLineage $true @(ProcessFixture) -Label 'exact two role-isolated parent-child trees'
ExpectLineage $false @(ProcessFixture) 'lifecycle' 'candidates' 'task roles reversed'
$p=@(ProcessFixture);$p[3].Mode='candidates'
ExpectLineage $false $p -Label 'three candidates one lifecycle'
$p=@(ProcessFixture);$p[3].ParentPID=100
ExpectLineage $false $p -Label 'cross-linked lifecycle to candidates'
$p=@(ProcessFixture);$p[3].OriginalStage=$false
ExpectLineage $false $p -Label 'foreign runtime lifecycle child'
$p=@(ProcessFixture);$p[0].PID=0
ExpectLineage $false $p -Label 'zero candidate PID'
$p=@(ProcessFixture);$p[3].PID=101
ExpectLineage $false $p -Label 'duplicated PID'
$p=@(ProcessFixture);$p[1].ParentPID=10
ExpectLineage $false $p -Label 'both candidates appear root'
$p=@(ProcessFixture);$p[0].ParentPID=101
ExpectLineage $false $p -Label 'cyclic candidate family'
$p=@(ProcessFixture);$p[2].ParentPID=101
ExpectLineage $false $p -Label 'lifecycle root parent is old candidate'
$p=@(ProcessFixture);$p+=@([pscustomobject]@{Mode='candidates';PID=102;ParentPID=100;OriginalStage=$true})
ExpectLineage $false $p -Label 'extra child or second writer'
$p=@(ProcessFixture);$p=$p[0..2]
ExpectLineage $false $p -Label 'missing lifecycle child'
Write-Output 'V3_ORIGINAL_PAPER_MODE_LINEAGE_PURE_17_CASES_PASS'


# V3 new scoped operator is source preparation ONLY. Extract the PURE policy;
# never execute its host branch in CI, and statically ban mutation commands.
$operator=Join-Path (Split-Path $PSScriptRoot -Parent) 'tools/minipc-v3-paper-cutover-operator-INACTIVE.ps1'
$ot=$null;$oe=$null
$oa=[System.Management.Automation.Language.Parser]::ParseFile($operator,[ref]$ot,[ref]$oe)
if($oe.Count -ne 0){throw ($oe | Out-String)}
$cmd=@($oa.FindAll({
 param($a) $a -is [System.Management.Automation.Language.CommandAst]
},$true) | ForEach-Object {$_.GetCommandName()})
foreach($unsafe in @('Stop-Process','Start-Process','Stop-ScheduledTask','Disable-ScheduledTask',
 'Enable-ScheduledTask','Start-ScheduledTask','Register-ScheduledTask','Unregister-ScheduledTask',
 'Set-ScheduledTask','Set-Content','Out-File','Add-Content','Copy-Item','Move-Item',
 'Remove-Item','New-Item','Invoke-RestMethod','Invoke-WebRequest','Invoke-Sqlcmd')){
 if($cmd -contains $unsafe){throw "INACTIVE_OPERATOR_MUTATION_FORBIDDEN $unsafe"}
}
$f=@($oa.FindAll({
 param($a)
 $a -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
 $a.Name -eq 'Test-V3CutoverPreparationPolicy'
},$true))
if($f.Count -ne 1){throw 'Expected exactly one inactive pure V3 operator policy'}
. ([Scriptblock]::Create($f[0].Extent.Text))
function V3OpFixture {
 $ns=@(
   @('CryptoMiniPC-V2R4PaperCandidates','v2r4-paper-local-runtime.py'),
   @('CryptoMiniPC-V2R4PaperWait','wait_launcher.py'),
   @('CryptoMiniPC-V2R4PaperLifecycle','v2r4-paper-local-runtime.py'),
   @('CryptoMiniPC-V2R4PaperCloudSync','v2r4-paper-cloud-sync.py')
 )
 $tasks=@(foreach($pair in $ns){
  [pscustomobject]@{
   task_name=$pair[0];action_script_basename=$pair[1];state='Running'
   action_count=1;documented_script_basename_hint_matches=$true
   principal_is_system=$true;heartbeat_fresh_for_role=$true
  }
 })
 [pscustomobject]@{
  kind='V3_MINIPC_SINGLE_WRITER_PHYSICAL_READONLY_PREFLIGHT_V1'
  pre_cutover_expected_predecessor_series_id='PAPER-V2R4-20261009T110135Z'
  native_old_intake_precutover_readonly_baseline_pass=$true
  native_old_paper_mode_lineage_precutover_readonly_pass=$true
  native_old_paper_mode_lineage_snapshot_only_no_stop_authority=$true
  new_v3_writer_started=$false;v2r4_changed=$false
  physical_v2r4_paper_task_readback=$tasks
 }
}
function CheckV3Op([bool]$Expected,[object]$Report,[bool]$Marker=$false,[bool]$Maintenance=$false,[string]$Label=''){
 $actual=Test-V3CutoverPreparationPolicy -Report $Report -FenceMarkerPresent $Marker -MaintenanceMarkerPresent $Maintenance
 if($actual -ne $Expected){throw "V3_OP_INACTIVE_FAIL $Label expected=$Expected actual=$actual"}
}
CheckV3Op $true (V3OpFixture) -Label 'exact intact four original roles only'
CheckV3Op $false (V3OpFixture) $true -Label 'marker already present'
CheckV3Op $false (V3OpFixture) $false $true -Label 'conflicting old technical maintenance'
$x=V3OpFixture;$x.native_old_paper_mode_lineage_precutover_readonly_pass=$false
CheckV3Op $false $x -Label 'missing exact candidate/lifecycle lineage'
$x=V3OpFixture;$x.physical_v2r4_paper_task_readback[2].state='Disabled'
CheckV3Op $false $x -Label 'original lifecycle not running'
$x=V3OpFixture;$x.physical_v2r4_paper_task_readback[3].heartbeat_fresh_for_role=$false
CheckV3Op $false $x -Label 'cloudsync stale'
$x=V3OpFixture;$x.physical_v2r4_paper_task_readback[0].action_script_basename='wait_launcher.py'
CheckV3Op $false $x -Label 'candidate switched to wait script'
$x=V3OpFixture;$x.physical_v2r4_paper_task_readback[1].task_name='CryptoMiniPC-V2R4PaperCandidates'
CheckV3Op $false $x -Label 'duplicate original task'
$x=V3OpFixture;$x.pre_cutover_expected_predecessor_series_id='PAPER-V2R4-20261007T184255Z'
CheckV3Op $false $x -Label 'stale predecessor'
$x=V3OpFixture;$x.new_v3_writer_started=$true
CheckV3Op $false $x -Label 'not a pre-cutover snapshot'
$x=V3OpFixture;$x.native_old_intake_precutover_readonly_baseline_pass=$false
CheckV3Op $false $x -Label 'Windows startup baseline unknown'
Write-Output 'V3_SCOPED_OPERATOR_INACTIVE_PURE_11_CASES_PASS'


# Pure complete WAIT root/child and unknown-child guard, source extracted only.
$waitPolicyFn=@($oa.FindAll({
 param($a)
 $a -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
 $a.Name -eq 'Test-V3WaitCompleteReadOnlyFamily'
},$true))
if($waitPolicyFn.Count -ne 1){throw 'Expected one pure WAIT descendants guard'}
. ([Scriptblock]::Create($waitPolicyFn[0].Extent.Text))
function WaitFixture {
 [pscustomobject]@{
  Wait=@(
   [pscustomobject]@{PID=100;ParentPID=10;OriginalStage=$true},
   [pscustomobject]@{PID=101;ParentPID=100;OriginalStage=$true}
  )
  All=@(
   [pscustomobject]@{PID=10;ParentPID=1},
   [pscustomobject]@{PID=100;ParentPID=10},
   [pscustomobject]@{PID=101;ParentPID=100},
   [pscustomobject]@{PID=200;ParentPID=10},
   [pscustomobject]@{PID=201;ParentPID=200}
  )
  Protected=@(200,201)
 }
}
function ExpectV3Wait([bool]$Expected,[object]$Data,[bool]$Action=$true,[string]$Label=''){
 $got=Test-V3WaitCompleteReadOnlyFamily -WaitRows $Data.Wait -AllProcesses $Data.All -WaitActionObserved $Action -ProtectedRolePids $Data.Protected
 if($got -ne $Expected){throw "V3_WAIT_DESCENDANTS_FAIL $Label expected=$Expected actual=$got"}
}
ExpectV3Wait $true (WaitFixture) -Label 'two exact WAIT descendants, unrelated sibling allowed'
$x=WaitFixture;$x.All+=@([pscustomobject]@{PID=0;ParentPID=0})
ExpectV3Wait $true $x -Label 'Windows kernel idle PID zero is not a child'
ExpectV3Wait $false (WaitFixture) $false -Label 'untrusted WAIT action'
$x=WaitFixture;$x.Wait[1].OriginalStage=$false
ExpectV3Wait $false $x -Label 'wrong runtime stage'
$x=WaitFixture;$x.Wait[0].ParentPID=101;$x.All[1].ParentPID=101
ExpectV3Wait $false $x -Label 'cyclic parent tree'
$x=WaitFixture;$x.Wait[1].ParentPID=10;$x.All[2].ParentPID=10
ExpectV3Wait $false $x -Label 'two roots without child'
$x=WaitFixture;$x.Wait[1].ParentPID=200;$x.All[2].ParentPID=200
ExpectV3Wait $false $x -Label 'child of protected Lifecycle'
$x=WaitFixture;$x.All+=@([pscustomobject]@{PID=102;ParentPID=101})
ExpectV3Wait $false $x -Label 'hidden nonpython grandchild'
$x=WaitFixture;$x.All+=@([pscustomobject]@{PID=102;ParentPID=100})
ExpectV3Wait $false $x -Label 'unrecognized sibling child'
$x=WaitFixture;$x.All[2].ParentPID=10
ExpectV3Wait $false $x -Label 'different live parent than WAIT receipt'
$x=WaitFixture;$x.All=@($x.All | Where-Object { [int]$_.PID -ne 101 })
ExpectV3Wait $false $x -Label 'missing child in full-process snapshot'
$x=WaitFixture;$x.Wait+=@([pscustomobject]@{PID=102;ParentPID=100;OriginalStage=$true})
ExpectV3Wait $false $x -Label 'extra matching python'
$x=WaitFixture;$x.All[4].PID=101
ExpectV3Wait $false $x -Label 'duplicate full-process PID'
$x=WaitFixture;$x.Protected=@(101,200)
ExpectV3Wait $false $x -Label 'protected process overlaps WAIT'
Write-Output 'V3_WAIT_COMPLETE_READONLY_FAMILY_PURE_14_CASES_PASS'

# Host-identified signed System32 conhost: EXACTLY one optional direct child
# of verified WAIT_ROOT, validated by the actual source attestation, no children.
# Synthetic flags in these pure cases DO NOT count as signed host receipts.
function SignedConsoleFixture {
 $x=WaitFixture
 $x.All+=@([pscustomobject]@{
  PID=102;ParentPID=100;Name='conhost.exe';TrustedConsoleHost=$true
 })
 return $x
}
ExpectV3Wait $true (SignedConsoleFixture) -Label 'one attested console host at exact WAIT_ROOT'
$x=SignedConsoleFixture;$x.All[5].TrustedConsoleHost=$false
ExpectV3Wait $false $x -Label 'unattested console host rejected'
$x=SignedConsoleFixture;$x.All[5].Name='consolehost.exe'
ExpectV3Wait $false $x -Label 'similar looking executable rejected'
$x=SignedConsoleFixture;$x.All[5].Name='conhost.exe.bak'
ExpectV3Wait $false $x -Label 'renamed executable rejected'
$x=SignedConsoleFixture;$x.All[5].ParentPID=101
ExpectV3Wait $false $x -Label 'conhost child of WAIT_CHILD rejected'
$x=SignedConsoleFixture;$x.All+=@([pscustomobject]@{
 PID=103;ParentPID=102;Name='helper.exe';TrustedConsoleHost=$false
})
ExpectV3Wait $false $x -Label 'console host with helper child rejected'
$x=SignedConsoleFixture;$x.All+=@([pscustomobject]@{
 PID=103;ParentPID=100;Name='conhost.exe';TrustedConsoleHost=$true
})
ExpectV3Wait $false $x -Label 'multiple trusted console hosts rejected'
$x=SignedConsoleFixture;$x.All+=@([pscustomobject]@{
 PID=103;ParentPID=100;Name='python.exe';TrustedConsoleHost=$false
})
ExpectV3Wait $false $x -Label 'new separate Python writer rejected'
$x=SignedConsoleFixture;$x.All[5].PID=101
ExpectV3Wait $false $x -Label 'duplicate native PID with expected WAIT child rejected'
$x=SignedConsoleFixture;$x.Protected=@(102,200,201)
ExpectV3Wait $false $x -Label 'protected role PID overlap with conhost rejected'
$x=SignedConsoleFixture;$x.Wait[0].OriginalStage=$false
ExpectV3Wait $false $x -Label 'lost original runtime stage rejected'
$x=SignedConsoleFixture;$x.Wait[1].ParentPID=10;$x.All[2].ParentPID=10
ExpectV3Wait $false $x -Label 'lost WAIT parent child relationship rejected'
# Code-level contract: trusted bit can ONLY be assigned after native path,
# Microsoft Authenticode, original creation-order and fresh PID re-read.
$operatorText=Get-Content -LiteralPath $operator -Raw -ErrorAction Stop
foreach($requiredCheck in @('System32\conhost.exe',
 'Get-AuthenticodeSignature','O=Microsoft Corporation',
 '$fresh[0].CreationDate -eq $candidate.CreationDate',
 '$trusted[0].TrustedConsoleHost=$true',
 'wait_consolehost_attestation_is_snapshot_only_not_stop_authority=$true')){
 if(-not $operatorText.Contains($requiredCheck)){
  throw "V3_CONHOST_TRUST_SOURCE_CHECK_MISSING $requiredCheck"
 }
}
Write-Output 'V3_SIGNED_CONHOST_EXACT_SCOPE_PURE_12_CASES_PASS'



# V3 offline transaction-contract simulation. Run extracted PURE policies only.
# Never execute the inactive operator, host commands, Task or Cloud changes.
foreach($name in @('Test-V3ScopedIntakeTaskSet','Test-V3ScopedOriginalBackupContract','Resolve-V3ScopedCutoverRecovery')){
 $fn=@($oa.FindAll({
  param($a) $a -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
  $a.Name -eq $name
 },$true))
 if($fn.Count -ne 1){throw "Missing unique pure V3 recovery policy $name"}
 . ([Scriptblock]::Create($fn[0].Extent.Text))
}
function V3BackupFixture {
 [pscustomobject]@{
  kind='V3_OLD_INTAKE_BACKUP_PROPOSAL_V1'
  predecessor_series_id='PAPER-V2R4-20261009T110135Z'
  old_stage_release_sha=('a' * 40)
  paper_only=$true;real_money_actions=$false
  task_records=@(
   [pscustomobject]@{task_name='CryptoMiniPC-V2R4PaperCandidates'
    xml_sha256=('b' * 64);action_sha256=('c' * 64)
    original_enabled=$true;original_running=$true;original_principal_system=$true
    one_original_boot_trigger=$true;restart_count=3;restart_interval='PT1M'
    multiple_instances='IgnoreNew'},
   [pscustomobject]@{task_name='CryptoMiniPC-V2R4PaperWait'
    xml_sha256=('d' * 64);action_sha256=('e' * 64)
    original_enabled=$true;original_running=$true;original_principal_system=$true
    one_original_boot_trigger=$true;restart_count=3;restart_interval='PT1M'
    multiple_instances='IgnoreNew'}
  )
 }
}
function V3RecoveryFixture {
 [pscustomobject]@{
  kind='V3_CUTOVER_RECOVERY_SIMULATION_V1'
  predecessor_series_id='PAPER-V2R4-20261009T110135Z'
  task_names=@('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait')
  phase='QUIESCED'
  paper_only=$true;real_money_actions=$false
  cloud_cas_invoked=$false;cloud_cas_outcome='NOT_INVOKED'
  backup_contract_verified=$true;backup_manifest=(V3BackupFixture)
  native_intake_tasks_disabled_ack=$true
  original_intake_processes_absent_ack=$true
  windows_supervisor_no_rearm_ack=$true
  protected_lifecycle_cloudsync_running_ack=$true
  old_cloud_single_active_readback=$true
  new_v3_series_absent_readback=$true
  v3_writer_started=$false
 }
}
function CheckBackup([bool]$Expected,[object]$Fixture,[string]$Label){
 $actual=Test-V3ScopedOriginalBackupContract -Manifest $Fixture
 if($actual -ne $Expected){throw "V3_BACKUP_CONTRACT_FAIL $Label expected=$Expected actual=$actual"}
}
function CheckRecovery([string]$Expected,[object]$Fixture,[string]$Label){
 $output=Resolve-V3ScopedCutoverRecovery -Receipt $Fixture
 if([string]$output.disposition -cne $Expected){throw "V3_RECOVERY_FAIL $Label wanted=$Expected got=$($output.disposition)"}
 if($output.automatic_task_action_authorized -ne $false -or
    $output.automatic_old_writer_rearm_allowed -ne $false -or
    $output.operator_stop_disable_implemented -ne $false -or
    $output.host_rollback_implemented -ne $false -or
    $output.cloud_cas_executed -ne $false -or
    $output.v3_release_authorized -ne $false -or
    [int]$output.full_v3_e2e_proofs_credited -ne 0){
  throw "V3_RECOVERY_POLICY_FALSE_RUNTIME_AUTHORITY $Label"
 }
}
if(-not(Test-V3ScopedIntakeTaskSet @('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait'))){throw 'Exact two-task scope rejected'}
if(Test-V3ScopedIntakeTaskSet @('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperLifecycle')){throw 'Protected Lifecycle falsely accepted'}
if(Test-V3ScopedIntakeTaskSet @('CryptoMiniPC-V2R4PaperWait','CryptoMiniPC-V2R4PaperWait')){throw 'Duplicate WAIT scope accepted'}
if(Test-V3ScopedIntakeTaskSet @('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait','CryptoMiniPC-V2R4PaperCloudSync')){throw 'Extra CloudSync scope accepted'}
CheckBackup $true (V3BackupFixture) 'exact two original backup proposals'
$x=V3BackupFixture;$x.task_records[0].xml_sha256='bad'
CheckBackup $false $x 'missing native XML hash'
$x=V3BackupFixture;$x.task_records[1].task_name='CryptoMiniPC-V2R4PaperLifecycle'
CheckBackup $false $x 'protected role in backup scope'
$x=V3BackupFixture;$x.task_records[0].original_enabled=$false
CheckBackup $false $x 'incorrect prior enabled state'
$x=V3BackupFixture;$x.task_records[1].restart_count=4
CheckBackup $false $x 'wrong native boot restart policy'
$x=V3BackupFixture;$x.old_stage_release_sha='bad'
CheckBackup $false $x 'old stage source pin missing'
CheckRecovery 'PRE_CAS_MANUAL_ROLLBACK_REVIEW_CANDIDATE' (V3RecoveryFixture) 'qualified simulation, no actual rollback'
$x=V3RecoveryFixture;$x.phase='PRE_CUTOVER'
CheckRecovery 'NO_ACTION_PRESERVE_ACTIVE_V2R4' $x 'no intervention yet'
$x=V3RecoveryFixture;$x.phase='ARMED'
CheckRecovery 'HOLD_FENCE_MANUAL_RECONCILIATION' $x 'no rollback until verified quiescence'
$x=V3RecoveryFixture;$x.cloud_cas_invoked=$true;$x.cloud_cas_outcome='UNKNOWN'
CheckRecovery 'HOLD_CAS_ATTEMPTED_MANUAL_CLOUD_RECONCILIATION' $x 'uncertain Cloud commit'
$x=V3RecoveryFixture;$x.cloud_cas_invoked=$true;$x.cloud_cas_outcome='NOT_COMMITTED'
CheckRecovery 'HOLD_CAS_ATTEMPTED_MANUAL_CLOUD_RECONCILIATION' $x 'negative outcome cannot authorize auto-rearm'
$x=V3RecoveryFixture;$x.cloud_cas_outcome='COMMITTED';$x.phase='CLOUD_COMMITTED'
CheckRecovery 'HOLD_POSTCOMMIT_OLD_INTAKE_PERMANENTLY_FENCED' $x 'postcommit old writer stays disabled'
$x=V3RecoveryFixture;$x.backup_contract_verified=$false
CheckRecovery 'HOLD_FENCE_MANUAL_RECONCILIATION' $x 'no validated physical backup receipt'
$x=V3RecoveryFixture;$x.backup_manifest.task_records[0].action_sha256='bad'
CheckRecovery 'HOLD_FENCE_MANUAL_RECONCILIATION' $x 'bad backup manifest pin'
$x=V3RecoveryFixture;$x.native_intake_tasks_disabled_ack=$false
CheckRecovery 'HOLD_FENCE_MANUAL_RECONCILIATION' $x 'Windows boot rearm still possible'
$x=V3RecoveryFixture;$x.windows_supervisor_no_rearm_ack=$false
CheckRecovery 'HOLD_FENCE_MANUAL_RECONCILIATION' $x 'Supervisor no-rearm not proven'
$x=V3RecoveryFixture;$x.original_intake_processes_absent_ack=$false
CheckRecovery 'HOLD_FENCE_MANUAL_RECONCILIATION' $x 'remaining old writer child'
$x=V3RecoveryFixture;$x.protected_lifecycle_cloudsync_running_ack=$false
CheckRecovery 'HOLD_FENCE_MANUAL_RECONCILIATION' $x 'protected aftercare offline'
$x=V3RecoveryFixture;$x.old_cloud_single_active_readback=$false
CheckRecovery 'HOLD_FENCE_MANUAL_RECONCILIATION' $x 'old Cloud authority not established'
$x=V3RecoveryFixture;$x.new_v3_series_absent_readback=$false
CheckRecovery 'HOLD_FENCE_MANUAL_RECONCILIATION' $x 'possible duplicate Cloud writer'
$x=V3RecoveryFixture;$x.v3_writer_started=$true
CheckRecovery 'HOLD_FENCE_MANUAL_RECONCILIATION' $x 'successor potentially running'
$x=V3RecoveryFixture;$x.cloud_cas_invoked=$null
CheckRecovery 'BLOCK_INVALID_SCOPE_OR_RECEIPT' $x 'missing explicit CAS attempted flag'
$x=V3RecoveryFixture;$x.task_names+=@('CryptoMiniPC-V2R4PaperLifecycle')
CheckRecovery 'BLOCK_INVALID_SCOPE_OR_RECEIPT' $x 'scope tries stopping protected aftercare'
$x=V3RecoveryFixture;$x.predecessor_series_id='PAPER-V2R4-20261007T184255Z'
CheckRecovery 'BLOCK_INVALID_SCOPE_OR_RECEIPT' $x 'stale technical predecessor'
$x=V3RecoveryFixture;$x.cloud_cas_outcome='SOMETHING_ELSE'
CheckRecovery 'HOLD_INVALID_CLOUD_OUTCOME' $x 'unrecognized Cloud result'
Write-Output 'V3_SCOPED_CUTOVER_PURE_BACKUP_RECOVERY_29_CASES_PASS'


# Native ORIGINAL host backup-manifest readback schema is intentionally
# DIFFERENT from PR316 simulated proposal. Extract PURE adapter; no host I/O.
$gapFns=@($oa.FindAll({
 param($a)
 $a -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
 $a.Name -eq 'Get-V3NativeIntakeBackupReadbackGap'
},$true))
if($gapFns.Count -ne 1){throw 'Expected one pure original backup gap adapter'}
. ([Scriptblock]::Create($gapFns[0].Extent.Text))

function NativeBackupReadbackFixture {
 [pscustomobject]@{
  kind='V3_OLD_INTAKE_NATIVE_BACKUP_READBACK_V1'
  captured_at_utc='2026-10-15T05:31:39.0000000Z'
  predecessor_series_id='PAPER-V2R4-20261009T110135Z'
  task_or_process_changes=$false; cloud_changes=$false
  actual_stop_or_rollback_tested=$false
  tasks=@(
   [pscustomobject]@{
    task_name='CryptoMiniPC-V2R4PaperCandidates'
    task_path='\';original_state='Running'
    backup_file='Candidates.task.xml'
    xml_sha256=('a' * 64);action_sha256=('b' * 64)
   },
   [pscustomobject]@{
    task_name='CryptoMiniPC-V2R4PaperWait'
    task_path='\';original_state='Running'
    backup_file='WAIT.task.xml'
    xml_sha256=('c' * 64);action_sha256=('d' * 64)
   }
  )
 }
}
function VerifyNativeBackupGap([bool]$Expected,[object]$Fixture,[string]$Label){
 $r=Get-V3NativeIntakeBackupReadbackGap -Readback $Fixture
 if($r.native_host_manifest_schema_only_pass -ne $Expected){
  throw "V3_NATIVE_BACKUP_SCHEMA_FAIL $Label wanted=$Expected got=$($r.native_host_manifest_schema_only_pass) reasons=$(@($r.schema_errors)-join ',')"
 }
 if($r.can_upcast_native_host_manifest_to_recovery_proposal -ne $false -or
    $r.host_backup_physical_readback_independently_verified_here -ne $false -or
    $r.original_native_principal_boot_restart_settings_recheck_needed -ne $true -or
    $r.original_runtime_stage_source_sha_needed -ne $true -or
    $r.actual_restore_dryrun_completed -ne $false -or
    $r.automatic_intake_task_action_authorized -ne $false -or
    $r.v3_paper_release_authorized -ne $false -or
    [int]$r.full_v3_release_proofs_credited -ne 0){
   throw "V3_NATIVE_BACKUP_SCHEMA_FALSE_PHYSICAL_AUTHORITY $Label"
 }
}
VerifyNativeBackupGap $true (NativeBackupReadbackFixture) 'exact genuine host manifest schema only'
VerifyNativeBackupGap $false $null 'missing host manifest'
$x=NativeBackupReadbackFixture;$x.kind='V3_OLD_INTAKE_BACKUP_PROPOSAL_V1'
VerifyNativeBackupGap $false $x 'not a PR316 synthetic proposed backup'
$x=NativeBackupReadbackFixture;$x.predecessor_series_id='PAPER-V2R4-20261007T184255Z'
VerifyNativeBackupGap $false $x 'wrong technical predecessor'
$x=NativeBackupReadbackFixture;$x.tasks[0].task_name='CryptoMiniPC-V2R4PaperLifecycle'
VerifyNativeBackupGap $false $x 'protected Lifecycle entry'
$x=NativeBackupReadbackFixture;$x.tasks[1].task_name='CryptoMiniPC-V2R4PaperCandidates'
VerifyNativeBackupGap $false $x 'duplicate original task name'
$x=NativeBackupReadbackFixture;$x.tasks[1].backup_file='..\..\secrets.txt'
VerifyNativeBackupGap $false $x 'path traversal backed file'
$x=NativeBackupReadbackFixture;$x.tasks[0].xml_sha256='not-a-sha'
VerifyNativeBackupGap $false $x 'missing XML sha256'
$x=NativeBackupReadbackFixture;$x.tasks[1].action_sha256='bad'
VerifyNativeBackupGap $false $x 'missing original Action sha256'
$x=NativeBackupReadbackFixture;$x.tasks[1].task_path='\Other\'
VerifyNativeBackupGap $false $x 'noncanonical TaskPath'
$x=NativeBackupReadbackFixture;$x.tasks[0].original_state='Disabled'
VerifyNativeBackupGap $false $x 'not original Running'
$x=NativeBackupReadbackFixture;$x.tasks=$x.tasks[0..0]
VerifyNativeBackupGap $false $x 'missing second original Task'
$x=NativeBackupReadbackFixture;$x.task_or_process_changes=$true
VerifyNativeBackupGap $false $x 'unpermitted physical Task mutation claimed'
$x=NativeBackupReadbackFixture;$x.actual_stop_or_rollback_tested=$true
VerifyNativeBackupGap $false $x 'unearned physical restore claim'
$x=NativeBackupReadbackFixture;$x.cloud_changes=$true
VerifyNativeBackupGap $false $x 'unpermitted Cloud mutation claimed'
$x=NativeBackupReadbackFixture;$x.captured_at_utc='2026-10-15T07:31:39'
VerifyNativeBackupGap $false $x 'UTC timezone absent'
$x=NativeBackupReadbackFixture;$x.captured_at_utc='someday'
VerifyNativeBackupGap $false $x 'invalid timestamp'
Write-Output 'V3_ORIGINAL_NATIVE_BACKUP_SCHEMA_ONLY_GAP_17_CASES_PASS'


# PR318: purely in-memory restore PREVIEW from original native manifest + two
# exact synthetic Task XML strings; no Task registration, no host Task/PID/API.
$previewFn=@($oa.FindAll({
 param($a)
 $a -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
 $a.Name -eq 'Test-V3NativeOriginalTaskRestorePreview'
},$true))
if($previewFn.Count -ne 1){throw 'Unique original restore preview policy required'}
. ([Scriptblock]::Create($previewFn[0].Extent.Text))

function MockOriginalTaskXml([string]$Script,[string]$Principal='S-1-5-18',
 [string]$Trigger='BootTrigger',[string]$Restart='PT1M',[string]$Instances='IgnoreNew'){
 $arguments=if($Script -eq 'v2r4-paper-local-runtime.py'){'--mode candidates v2r4-paper-local-runtime.py'}else{$Script}
 return @"
<Task>
 <Triggers><$Trigger><Enabled>true</Enabled></$Trigger></Triggers>
 <Principals><Principal><UserId>$Principal</UserId></Principal></Principals>
 <Settings>
  <RestartOnFailure><Interval>$Restart</Interval><Count>3</Count></RestartOnFailure>
  <MultipleInstancesPolicy>$Instances</MultipleInstancesPolicy>
 </Settings>
 <Actions><Exec><Command>C:\Python\python.exe</Command><Arguments>$arguments</Arguments><WorkingDirectory>C:\Users\ADMIN\Trading</WorkingDirectory></Exec></Actions>
</Task>
"@
}
function NativeRestoreFixture {
 $manifest=NativeBackupReadbackFixture
 $scripts=@('v2r4-paper-local-runtime.py','wait_launcher.py')
 $rows=@()
 for($i=0;$i -lt 2;$i++){
  $x=MockOriginalTaskXml $scripts[$i]
  $argsValue=if($i -eq 0){'--mode candidates v2r4-paper-local-runtime.py'}else{'wait_launcher.py'}
  $tuple=@('C:\Python\python.exe',$argsValue,'C:\Users\ADMIN\Trading') -join ([string][char]10)
  $sha=[Security.Cryptography.SHA256]::Create()
  try{
   $actualHash=([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($tuple)))).Replace('-','').ToLowerInvariant()
  }finally{$sha.Dispose()}
  $manifest.tasks[$i].action_sha256=$actualHash
  $rows+=@([pscustomobject]@{
   task_name=$manifest.tasks[$i].task_name
   backup_xml_text=$x
   current_task_xml_text=$x
   backup_file_sha256=$manifest.tasks[$i].xml_sha256
   current_task_running=$true
   native_task_enabled=$true
  })
 }
 [pscustomobject]@{Manifest=$manifest; Rows=$rows}
}
function ExpectRestorePreview([bool]$Expected,[object]$Fixture,[string]$Label){
 $r=Test-V3NativeOriginalTaskRestorePreview -Readback $Fixture.Manifest -Rows $Fixture.Rows
 if($r.preview_structure_only_pass -ne $Expected){
  throw "V3_RESTORE_PREVIEW_FAIL $Label wanted=$Expected got=$($r.preview_structure_only_pass) reason=$(@($r.preview_errors)-join ',')"
 }
 if($r.actual_restore_test_passed -ne $false -or
    $r.task_scheduler_import_or_restore_invoked -ne $false -or
    $r.original_host_backup_acl_proven_here -ne $false -or
    $r.full_host_source_and_task_identity_proven_here -ne $false -or
    $r.protected_lifecycle_cloudsync_runtime_proven_here -ne $false -or
    $r.native_no_rearm_stop_ack_passed -ne $false -or
    $r.v3_release_authorized -ne $false -or
    [int]$r.technical_release_proofs_credited -ne 0 -or
    [int]$r.task_process_marker_cloud_writes -ne 0){
  throw "V3_RESTORE_PREVIEW_FALSE_AUTHORITY $Label"
 }
}
ExpectRestorePreview $true (NativeRestoreFixture) 'simulated exact two backup XML and action serializations'
$x=NativeRestoreFixture;$x.Rows[0].backup_file_sha256='0' * 64
ExpectRestorePreview $false $x 'backup bytes digest mismatch'
$x=NativeRestoreFixture;$x.Rows[1].current_task_xml_text='changed'
ExpectRestorePreview $false $x 'current XML no longer matches saved source'
$x=NativeRestoreFixture;$x.Rows[0].current_task_running=$false
ExpectRestorePreview $false $x 'original Task not Running'
$x=NativeRestoreFixture;$x.Rows[1].native_task_enabled=$false
ExpectRestorePreview $false $x 'original Task not Enabled'
$x=NativeRestoreFixture;$x.Rows[0].backup_xml_text=(MockOriginalTaskXml 'v2r4-paper-local-runtime.py' 'USER')
$x.Rows[0].current_task_xml_text=$x.Rows[0].backup_xml_text
ExpectRestorePreview $false $x 'original nonSYSTEM principal'
$x=NativeRestoreFixture;$x.Rows[0].backup_xml_text=(MockOriginalTaskXml 'v2r4-paper-local-runtime.py' 'S-1-5-18' 'LogonTrigger')
$x.Rows[0].current_task_xml_text=$x.Rows[0].backup_xml_text
ExpectRestorePreview $false $x 'unexpected Logon instead of BootTrigger'
$x=NativeRestoreFixture;$x.Rows[0].backup_xml_text=(MockOriginalTaskXml 'v2r4-paper-local-runtime.py' 'S-1-5-18' 'BootTrigger' 'PT5M')
$x.Rows[0].current_task_xml_text=$x.Rows[0].backup_xml_text
ExpectRestorePreview $false $x 'incorrect restart interval'
$x=NativeRestoreFixture;$x.Rows[1].backup_xml_text=(MockOriginalTaskXml 'wait_launcher.py' 'S-1-5-18' 'BootTrigger' 'PT1M' 'Parallel')
$x.Rows[1].current_task_xml_text=$x.Rows[1].backup_xml_text
ExpectRestorePreview $false $x 'unexpected multiple instance policy'
$x=NativeRestoreFixture;$x.Rows[1].backup_xml_text=(MockOriginalTaskXml 'unexpected_launcher.py')
$x.Rows[1].current_task_xml_text=$x.Rows[1].backup_xml_text
ExpectRestorePreview $false $x 'wrong exact WAIT action'
$x=NativeRestoreFixture;$x.Rows[0].backup_xml_text='<not-task />';$x.Rows[0].current_task_xml_text='<not-task />'
ExpectRestorePreview $false $x 'wrong root XML'
$x=NativeRestoreFixture;$x.Rows[0].backup_xml_text='<Task><broken></Task>';$x.Rows[0].current_task_xml_text=$x.Rows[0].backup_xml_text
ExpectRestorePreview $false $x 'unparseable XML'
$x=NativeRestoreFixture;$x.Manifest.predecessor_series_id='PAPER-V2R4-20261007T184255Z'
ExpectRestorePreview $false $x 'wrong original predecessor'
$x=NativeRestoreFixture;$x.Rows[1].task_name='CryptoMiniPC-V2R4PaperLifecycle'
ExpectRestorePreview $false $x 'protected Lifecycle in restoration preview'
$x=NativeRestoreFixture;$x.Rows=@($x.Rows[0])
ExpectRestorePreview $false $x 'incomplete restore preview input'
$x=NativeRestoreFixture;$x.Manifest.tasks[0].action_sha256='f' * 64
ExpectRestorePreview $false $x 'newline serialized original Action fingerprint changed'
Write-Output 'V3_IN_MEMORY_ORIGINAL_RESTORE_PREVIEW_ONLY_16_CASES_PASS'


# PR319: pure physical fence choreography review, NEVER executes native actions.
$stageFn=@($oa.FindAll({
 param($a) $a -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
 $a.Name -eq 'Get-V3SingleWriterFenceDryRunPlan'
},$true))
if($stageFn.Count -ne 1){throw 'Exactly one V3 physical-fence dryrun planner required'}
. ([Scriptblock]::Create($stageFn[0].Extent.Text))
function V3FenceFixture {
 [pscustomobject]@{
  kind='V3_SINGLE_WRITER_FENCE_DRYRUN_SIMULATION_V1'
  predecessor_series_id='PAPER-V2R4-20261009T110135Z'
  paper_only=$true;real_money_actions=$false
  intake_task_names=@('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait')
  protected_task_names=@('CryptoMiniPC-V2R4PaperLifecycle','CryptoMiniPC-V2R4PaperCloudSync')
  protected_tasks_running=$true
  source_pins_verified=$true;mode_lineage_fresh=$true
  wait_all_descendants_verified=$true;original_cloud_only_readback=$true
  v3_writer_running=$false;backup_readback_verified=$true
  backup_proposal=(V3BackupFixture)
  intake_task_states=@(
   [pscustomobject]@{task_name='CryptoMiniPC-V2R4PaperCandidates';state='Running'},
   [pscustomobject]@{task_name='CryptoMiniPC-V2R4PaperWait';state='Running'}
  )
  phase='DISCOVERY';fence_marker_phase='ABSENT'
  cas_invoked=$false;cas_outcome='NOT_INVOKED'
  # Legacy combined bool remains intentionally untrusted.
  windows_and_supervisor_no_rearm_readback=$false
  native_windows_disable_and_no_rearm_readback=$false
  supervisor_intake_restart_suppressed_readback=$false
  supervisor_reported_fence_mode='NONE'
  both_native_tasks_disabled_readback=$false
  old_intake_process_count=4
  authentic_technical_e2e_proofs=0
  model_budget_separately_approved=$false
 }
}
function ReviewFence([string]$Expected,[object]$Fixture,[string]$Label){
 $r=Get-V3SingleWriterFenceDryRunPlan -Receipt $Fixture
 if([string]$r.simulated_next_review -cne $Expected){
  throw "V3_FENCE_SIMULATION_FAIL $Label expected=$Expected got=$($r.simulated_next_review) reasons=$(@($r.input_errors)-join ',')"
 }
 foreach($property in @('native_task_disable_or_stop_permitted',
  'process_kill_permitted','marker_write_permitted',
  'automatic_old_intake_rearm_permitted','cloud_cas_invoke_permitted',
  'model_spend_or_real_money_permitted','physical_quiescence_verified_here')){
  if($r.$property -ne $false){throw "V3_FENCE_UNAUTHORIZED_ACTION $Label $property"}
 }
 if($r.proof_is_synthetic_not_live -ne $true -or
   [int]$r.full_e2e_release_proofs_credited -ne 0){
  throw "V3_FENCE_FALSE_LIVE_EVIDENCE $Label"
 }
}
ReviewFence 'REVIEW_ARM_FENCE_SEPARATE_PHYSICAL_APPROVAL' (V3FenceFixture) 'source pinned discovery only'
$x=V3FenceFixture;$x.fence_marker_phase='ARMED'
ReviewFence 'HOLD_INCONSISTENT_FENCE_STATE_OR_NO_REARM' $x 'unexplained marker'
$x=V3FenceFixture;$x.phase='ARMED';$x.fence_marker_phase='ARMED'
ReviewFence 'REVIEW_DISABLE_ONLY_CANDIDATES_AND_WAIT' $x 'physical stop not actually allowed'
$x=V3FenceFixture;$x.phase='ARMED';$x.fence_marker_phase='ARMED';$x.protected_tasks_running=$false
ReviewFence 'BLOCK_MISSING_OR_INVALID_RECEIPT' $x 'protected aftercare down'
$x=V3FenceFixture;$x.intake_task_names=@('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperLifecycle')
ReviewFence 'BLOCK_MISSING_OR_INVALID_RECEIPT' $x 'protected Task mistakenly in scope'
$x=V3FenceFixture;$x.protected_task_names=@('CryptoMiniPC-V2R4PaperLifecycle','CryptoMiniPC-V2R4PaperWait')
ReviewFence 'BLOCK_MISSING_OR_INVALID_RECEIPT' $x 'protected role list incomplete'
$x=V3FenceFixture;$x.backup_proposal.task_records[0].xml_sha256='bad'
ReviewFence 'BLOCK_MISSING_OR_INVALID_RECEIPT' $x 'unverified TaskXML backup'
$x=V3FenceFixture;$x.source_pins_verified=$false
ReviewFence 'BLOCK_MISSING_OR_INVALID_RECEIPT' $x 'untrusted original source pin'
$x=V3FenceFixture;$x.mode_lineage_fresh=$false
ReviewFence 'BLOCK_MISSING_OR_INVALID_RECEIPT' $x 'stale PID lineage'
$x=V3FenceFixture;$x.wait_all_descendants_verified=$false
ReviewFence 'BLOCK_MISSING_OR_INVALID_RECEIPT' $x 'unrecognized WAIT grandchild'
$x=V3FenceFixture;$x.original_cloud_only_readback=$false
ReviewFence 'BLOCK_MISSING_OR_INVALID_RECEIPT' $x 'Cloud still ambiguous'
$x=V3FenceFixture;$x.v3_writer_running=$true
ReviewFence 'BLOCK_MISSING_OR_INVALID_RECEIPT' $x 'duplicate potential V3 Writer'
$x=V3FenceFixture;$x.intake_task_states[1].task_name='CryptoMiniPC-V2R4PaperLifecycle'
ReviewFence 'BLOCK_MISSING_OR_INVALID_RECEIPT' $x 'Task rows mismatched'
$x=V3FenceFixture;$x.phase='TASKS_DISABLED';$x.fence_marker_phase='ARMED'
foreach($r in $x.intake_task_states){$r.state='Disabled'}
$x.windows_and_supervisor_no_rearm_readback=$true
$x.native_windows_disable_and_no_rearm_readback=$true
$x.supervisor_intake_restart_suppressed_readback=$true
$x.supervisor_reported_fence_mode='ARMED'
$x.both_native_tasks_disabled_readback=$true
ReviewFence 'REVIEW_BOUNDED_OLD_INTAKE_STOP_AND_FRESH_PROCESS_READBACK' $x 'disabled original intake only'
$x.native_windows_disable_and_no_rearm_readback=$false
ReviewFence 'HOLD_INCONSISTENT_FENCE_STATE_OR_NO_REARM' $x 'combined true must not stand in for native no-rearm'
$x.native_windows_disable_and_no_rearm_readback=$true
$x.supervisor_intake_restart_suppressed_readback=$false
ReviewFence 'HOLD_INCONSISTENT_FENCE_STATE_OR_NO_REARM' $x 'combined true must not stand in for Supervisor no-rearm'
$x.supervisor_intake_restart_suppressed_readback=$true
$x.supervisor_reported_fence_mode='QUIESCED'
ReviewFence 'HOLD_INCONSISTENT_FENCE_STATE_OR_NO_REARM' $x 'Supervisor marker cannot report QUIESCED during ARMED'
$x.supervisor_reported_fence_mode='ARMED'
$x.both_native_tasks_disabled_readback=$false
ReviewFence 'HOLD_INCONSISTENT_FENCE_STATE_OR_NO_REARM' $x 'native Disabled tasks need independent acknowledgement'
$x.both_native_tasks_disabled_readback=$true
ReviewFence 'REVIEW_BOUNDED_OLD_INTAKE_STOP_AND_FRESH_PROCESS_READBACK' $x 'restored all independent no-rearm and disabled evidence'
$x.windows_and_supervisor_no_rearm_readback=$false
ReviewFence 'REVIEW_BOUNDED_OLD_INTAKE_STOP_AND_FRESH_PROCESS_READBACK' $x 'legacy combined false irrelevant when both independent owners agree'
$x.native_windows_disable_and_no_rearm_readback=$false
ReviewFence 'HOLD_INCONSISTENT_FENCE_STATE_OR_NO_REARM' $x 'Windows restart could rearm without original native receipt'
$x=V3FenceFixture;$x.phase='STOP_RECORDED';$x.fence_marker_phase='ARMED'
foreach($r in $x.intake_task_states){$r.state='Disabled'}
$x.windows_and_supervisor_no_rearm_readback=$true;$x.old_intake_process_count=0
$x.native_windows_disable_and_no_rearm_readback=$true
$x.supervisor_intake_restart_suppressed_readback=$true
$x.supervisor_reported_fence_mode='ARMED'
$x.both_native_tasks_disabled_readback=$true
ReviewFence 'REVIEW_QUIESCED_FENCE_WITH_ORIGINAL_AFTERCARE' $x 'synthetic empty intact family'
$x.old_intake_process_count=1
ReviewFence 'HOLD_INCONSISTENT_FENCE_STATE_OR_NO_REARM' $x 'one original intake still alive'
$x=V3FenceFixture;$x.phase='QUIESCED';$x.fence_marker_phase='QUIESCED'
foreach($r in $x.intake_task_states){$r.state='Disabled'}
$x.windows_and_supervisor_no_rearm_readback=$true;$x.old_intake_process_count=0
$x.native_windows_disable_and_no_rearm_readback=$true
$x.supervisor_intake_restart_suppressed_readback=$true
$x.supervisor_reported_fence_mode='QUIESCED'
$x.both_native_tasks_disabled_readback=$true
ReviewFence 'HOLD_SIX_E2E_AND_BUDGET_APPROVAL' $x 'no fabricated 6 technical proofs'
$x.supervisor_reported_fence_mode='ARMED'
ReviewFence 'HOLD_INCONSISTENT_FENCE_STATE_OR_NO_REARM' $x 'QUIESCED marker needs independent Supervisor QUIESCED receipt'
$x.supervisor_reported_fence_mode='QUIESCED'
$x.authentic_technical_e2e_proofs=6
ReviewFence 'HOLD_SIX_E2E_AND_BUDGET_APPROVAL' $x 'no model budget approval'
$x.model_budget_separately_approved=$true
ReviewFence 'REVIEW_SEPARATE_CLOUD_CAS_APPROVAL_NO_EXECUTION' $x 'synthetic all six and budget still no authority'
$x=V3FenceFixture;$x.cas_invoked=$true;$x.cas_outcome='UNKNOWN';$x.phase='CAS_INVOKED'
ReviewFence 'HOLD_CAS_ATTEMPTED_MANUAL_CLOUD_RECONCILIATION' $x 'unknown CAS no auto-rearm'
$x=V3FenceFixture;$x.cas_invoked=$true;$x.cas_outcome='NOT_COMMITTED';$x.phase='CAS_INVOKED'
ReviewFence 'HOLD_CAS_ATTEMPTED_MANUAL_CLOUD_RECONCILIATION' $x 'negative reply no rearm'
$x=V3FenceFixture;$x.cas_invoked=$true;$x.cas_outcome='COMMITTED';$x.phase='CLOUD_COMMITTED'
foreach($r in $x.intake_task_states){$r.state='Disabled'}
$x.fence_marker_phase='CLOUD_COMMITTED'
ReviewFence 'HOLD_POSTCOMMIT_OLD_INTAKE_FENCED_KEEP_AFTERCARE' $x 'old writer permanently off'
$x.fence_marker_phase='ARMED'
ReviewFence 'HOLD_CAS_ATTEMPTED_MANUAL_CLOUD_RECONCILIATION' $x 'mismatched postcommit marker still no rearm'
$x=V3FenceFixture;$x.cas_invoked=$null
ReviewFence 'BLOCK_MISSING_OR_INVALID_RECEIPT' $x 'ambiguous CAS input'
$x=V3FenceFixture;$x.phase='UNRECOGNIZED'
ReviewFence 'HOLD_INCONSISTENT_FENCE_STATE_OR_NO_REARM' $x 'untrusted phase'
# Guard the static preview against executable Task mutations.
$opText=Get-Content -LiteralPath $operator -Raw -ErrorAction Stop
foreach($k in @('pre_cas_physical_order_preview=@(',
 'native_and_supervisor_independent_no_rearm_required=$true',
 'step_implementation_present=$false',
 "if(`$Execute){")){
 if(-not $opText.Contains($k)){throw "V3_ORDER_CONTRACT_MISSING $k"}
}
Write-Output 'V3_SINGLE_WRITER_PHYSICAL_FENCE_PURE_33_CASES_PASS'

# PR326 protected two-task operator: AST-only / source-contract tests.
# Never source/execute the operator in CI (it can mutate Windows tasks).
$pr326Operator=Join-Path (Split-Path $PSScriptRoot -Parent) 'tools/minipc-pr326-protected-cutover.ps1'
$pr326Tokens=$null;$pr326Errors=$null
$pr326Ast=[System.Management.Automation.Language.Parser]::ParseFile(
  $pr326Operator,[ref]$pr326Tokens,[ref]$pr326Errors)
if(@($pr326Errors).Count -ne 0){throw 'PR326_CUTOVER_OPERATOR_SYNTAX_INVALID'}
$pr326Text=Get-Content -LiteralPath $pr326Operator -Raw -ErrorAction Stop
foreach($token in @(
 'PR326_RELEASE_PREFLIGHT=PASS',
 'PR326_EXECUTION=NOT_REQUESTED_READ_ONLY',
 'APPROVED_PR326_PAPER_ONLY_CUTOVER',
 'ProtectedData',
 'DataProtectionScope]::CurrentUser',
 'Old WAIT launcher PID still alive',
 'New WAIT launcher PID still alive',
 'Register-InactiveTask',
 'POST_CUTOVER_WAIT_CYCLES',
 'PR326_ROLLBACK=OLD_TASKS_RESTORED',
 'MANUAL_INTERVENTION_REQUIRED_NO_BLIND_RESTART',
 'Original task XML missing Enabled field',
 'Unexpected preexisting source progress file'
)){
  if(-not $pr326Text.Contains($token)){throw "PR326_PROTECTED_OPERATOR_CONTRACT_MISSING $token"}
}
$disableSup=$pr326Text.IndexOf('Disable-ScheduledTask -TaskName $supName -ErrorAction Stop')
$disableWait=$pr326Text.IndexOf('Disable-ScheduledTask -TaskName $waitName -ErrorAction Stop')
$stopWait=$pr326Text.IndexOf('Stop-ScheduledTask -TaskName $waitName -ErrorAction SilentlyContinue')
$startWait=$pr326Text.IndexOf('Start-ScheduledTask -TaskName $waitName -ErrorAction Stop')
$startSup=$pr326Text.IndexOf('Start-ScheduledTask -TaskName $supName -ErrorAction Stop')
if($disableSup -lt 0 -or $disableWait -le $disableSup -or
   $stopWait -le $disableWait -or $startWait -le $stopWait -or
   $startSup -le $startWait){
  throw 'PR326_PROTECTED_OPERATOR_SHUTDOWN_START_ORDER_INVALID'
}
if($pr326Text.IndexOf('Unexpected preexisting source progress file') -gt
   $pr326Text.IndexOf('$enteredMutation=$true')){
  throw 'PR326_PROGRESS_REPLAY_CHECK_AFTER_MUTATION'
}
Write-Output 'PR326_PROTECTED_OPERATOR_STATIC_FENCE_PASS'
