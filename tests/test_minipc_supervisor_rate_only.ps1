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
