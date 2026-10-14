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
