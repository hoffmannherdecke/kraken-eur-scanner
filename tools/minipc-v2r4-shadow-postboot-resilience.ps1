param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading"),
  [int]$DelaySeconds = 75,
  [int]$OfflineSeconds = 20,
  [string]$OneShotTaskName = "CryptoMiniPC-V2R4ShadowResilienceOnce"
)

$ErrorActionPreference = "Stop"

if ($DelaySeconds -lt 30 -or $DelaySeconds -gt 300) { throw "DelaySeconds must be between 30 and 300." }
if ($OfflineSeconds -lt 10 -or $OfflineSeconds -gt 45) { throw "OfflineSeconds must be between 10 and 45." }

$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$logDir = Join-Path $TradingRoot "Logs"
$runtimeGate = Join-Path $repo "tools\minipc-runtime-recovery-gate.ps1"
$internetGate = Join-Path $repo "tools\minipc-internet-recovery-gate.ps1"
$evidenceGate = Join-Path $repo "tools\minipc-v2r4-ws-shadow-evidence.ps1"

foreach ($p in @($repo,$logDir,$runtimeGate,$internetGate,$evidenceGate)) {
  if (-not (Test-Path $p)) { throw "Required path missing: $p" }
}

# Make the restart test truly one-shot before any disruptive work begins.
try { Unregister-ScheduledTask -TaskName $OneShotTaskName -Confirm:$false -ErrorAction SilentlyContinue } catch {}

$started = Get-Date
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$jsonPath = Join-Path $logDir ("minipc-v2r4-shadow-resilience-" + $stamp + ".json")
$txtPath = Join-Path $logDir "minipc-v2r4-shadow-resilience-latest.txt"

Start-Sleep -Seconds $DelaySeconds

function Invoke-Gate([string]$ScriptPath, [string[]]$ExtraArgs = @()) {
  $args = @("-NoProfile","-NonInteractive","-ExecutionPolicy","Bypass","-File",$ScriptPath,"-TradingRoot",$TradingRoot) + $ExtraArgs
  $output = & powershell.exe @args 2>&1 | Out-String
  $code = $LASTEXITCODE
  return [ordered]@{ exit_code=[int]$code; output=[string]$output }
}

$runtime = Invoke-Gate $runtimeGate
$internet = $null
$evidence = $null
$issues = New-Object System.Collections.Generic.List[string]

if ($runtime.exit_code -ne 0) {
  $issues.Add("runtime_recovery_gate_failed")
} else {
  $internet = Invoke-Gate $internetGate @("-OfflineSeconds",[string]$OfflineSeconds)
  if ($internet.exit_code -ne 0) { $issues.Add("internet_recovery_gate_failed") }
}

# Evidence summary is read-only and useful even if the resilience gate found an issue.
try {
  $evidence = Invoke-Gate $evidenceGate @("-Hours","6")
  if ($evidence.exit_code -ne 0) { $issues.Add("shadow_evidence_summary_failed") }
} catch {
  $issues.Add("shadow_evidence_summary_exception")
  $evidence = [ordered]@{ exit_code=99; output=$_.Exception.Message }
}

$status = if ($issues.Count -eq 0) { "PASS" } else { "FAIL" }
$finished = Get-Date

$result = [ordered]@{
  schema_version = 1
  kind = "MINIPC_V2R4_SHADOW_RESILIENCE_BUNDLE_V1"
  status = $status
  started_at_local = $started.ToString("o")
  finished_at_local = $finished.ToString("o")
  delay_seconds = $DelaySeconds
  offline_seconds = $OfflineSeconds
  runtime_recovery = $runtime
  internet_recovery = $internet
  evidence_summary = $evidence
  issues = @($issues)
  guardrails = [ordered]@{
    v2r3_changed = $false
    evaluator_invoked = $false
    order_api = $false
    account_credentials = $false
    real_money_actions = $false
  }
}

[System.IO.File]::WriteAllText(
  $jsonPath,
  ($result | ConvertTo-Json -Depth 8) + [Environment]::NewLine,
  [System.Text.UTF8Encoding]::new($false)
)

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("=== V2R4 SHADOW RESILIENCE BUNDLE SUMMARY ===")
$lines.Add("Status: " + $status)
$lines.Add("Runtime recovery gate: exit=" + $runtime.exit_code)
$lines.Add("Internet recovery gate: exit=" + $(if ($internet) { $internet.exit_code } else { "SKIPPED" }))
$lines.Add("Evidence summary: exit=" + $(if ($evidence) { $evidence.exit_code } else { "SKIPPED" }))
$lines.Add("Issues: " + $(if ($issues.Count -gt 0) { $issues -join ", " } else { "none" }))
$lines.Add("")
$lines.Add("--- Runtime recovery ---")
$lines.Add(($runtime.output.Trim()))
if ($internet) {
  $lines.Add("")
  $lines.Add("--- Internet recovery ---")
  $lines.Add(($internet.output.Trim()))
}
if ($evidence) {
  $lines.Add("")
  $lines.Add("--- Shadow evidence ---")
  $lines.Add(($evidence.output.Trim()))
}
$lines.Add("")
$lines.Add("Safety: SHADOW ONLY / V2R3 UNCHANGED / NO EVALUATOR / NO ORDERS / NO REAL-MONEY ACTION")
$lines.Add("JSON report: " + $jsonPath)
$lines.Add("=== END ===")

[System.IO.File]::WriteAllLines($txtPath,$lines,[System.Text.UTF8Encoding]::new($false))

exit $(if ($status -eq "PASS") { 0 } else { 2 })
