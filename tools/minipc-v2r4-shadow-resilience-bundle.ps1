param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading"),
  [int]$DelaySeconds = 75,
  [int]$OfflineSeconds = 20
)

$ErrorActionPreference = "Stop"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw "Bitte dieses Skript in einer als Administrator gestarteten PowerShell ausführen."
}

$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$postboot = Join-Path $repo "tools\minipc-v2r4-shadow-postboot-resilience.ps1"
$heartbeat = Join-Path $TradingRoot "State\v2r4-ws-shadow-heartbeat.json"
$taskName = "CryptoMiniPC-V2R4ShadowResilienceOnce"

foreach ($p in @($repo,$postboot,$heartbeat)) {
  if (-not (Test-Path $p)) { throw "Required path missing: $p" }
}

$shadowTask = Get-ScheduledTask -TaskName "CryptoMiniPC-V2R4WSShadow" -ErrorAction SilentlyContinue
if (-not $shadowTask) { throw "CryptoMiniPC-V2R4WSShadow is not installed." }

$h = Get-Content $heartbeat -Raw | ConvertFrom-Json
$age = [math]::Round(((Get-Date).ToUniversalTime() - ([datetime]$h.checked_at_utc).ToUniversalTime()).TotalSeconds,1)
if ($h.status -notin @("HEALTHY","DUPLICATE_SKIPPED") -or $age -gt 30) {
  throw "V2R4 WS shadow heartbeat is not fresh/healthy before resilience test."
}
if ([string]$h.strategy_action -ne "NONE_SHADOW_ONLY" -or [bool]$h.real_money_actions) {
  throw "V2R4 WS shadow guardrails are not in the expected safe state."
}

$args = @(
  "-NoProfile","-NonInteractive","-ExecutionPolicy","Bypass","-File",('"' + $postboot + '"'),
  "-TradingRoot",('"' + $TradingRoot + '"'),
  "-DelaySeconds",[string]$DelaySeconds,
  "-OfflineSeconds",[string]$OfflineSeconds,
  "-OneShotTaskName",$taskName
) -join " "

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $args
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -User "SYSTEM" -RunLevel Highest -Force | Out-Null

Write-Host ""
Write-Host "=== V2R4 SHADOW RESILIENCE TEST ARMED ==="
Write-Host ("Current shadow heartbeat: " + $h.status + " | age=" + $age + "s")
Write-Host ("Post-boot delay: " + $DelaySeconds + "s")
Write-Host ("Controlled Internet outage window after reboot: " + $OfflineSeconds + "s")
Write-Host "The one-shot verifier unregisters itself before the disruptive checks."
Write-Host "After reboot, wait about 4 minutes before checking the summary."
Write-Host "Safety: SHADOW ONLY / NO EVALUATOR / NO ORDERS / NO REAL-MONEY ACTION"
Write-Host "Restarting Windows in 5 seconds..."
Start-Sleep -Seconds 5
Restart-Computer -Force
