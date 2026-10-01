param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading"),
  [int]$MaxBootAgeMinutes = 30
)

$ErrorActionPreference = "Stop"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw "Bitte dieses Skript in einer als Administrator gestarteten PowerShell ausführen."
}

$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$postboot = Join-Path $repo "tools\minipc-v2r4-shadow-postboot-resilience.ps1"
$latest = Join-Path $TradingRoot "Logs\minipc-v2r4-shadow-resilience-latest.txt"
$shadowHeartbeat = Join-Path $TradingRoot "State\v2r4-ws-shadow-heartbeat.json"

foreach ($p in @($repo,$postboot,$shadowHeartbeat)) {
  if (-not (Test-Path $p)) { throw "Required path missing: $p" }
}

if (Test-Path $latest) {
  Write-Host "Existing resilience summary found:"
  Get-Content $latest
  exit 0
}

$boot = [datetime](Get-CimInstance Win32_OperatingSystem).LastBootUpTime
$uptimeMinutes = [math]::Round(((Get-Date) - $boot).TotalMinutes,1)
Write-Host ("Current boot: " + $boot.ToString("yyyy-MM-dd HH:mm:ss") + " | uptime=" + $uptimeMinutes + " min")

if ($uptimeMinutes -gt $MaxBootAgeMinutes) {
  throw "The current boot is older than $MaxBootAgeMinutes minutes. Refusing to claim restart-recovery evidence from a stale boot."
}

$shadowTask = Get-ScheduledTask -TaskName "CryptoMiniPC-V2R4WSShadow" -ErrorAction SilentlyContinue
if (-not $shadowTask) { throw "CryptoMiniPC-V2R4WSShadow is missing." }
$shadowInfo = $shadowTask | Get-ScheduledTaskInfo
if (-not $shadowInfo.LastRunTime -or $shadowInfo.LastRunTime -lt $boot) {
  throw "The V2R4 WS shadow task has not run since the current Windows boot."
}

$h = Get-Content $shadowHeartbeat -Raw | ConvertFrom-Json
$age = [math]::Round(((Get-Date).ToUniversalTime() - ([datetime]$h.checked_at_utc).ToUniversalTime()).TotalSeconds,1)
if ($h.status -notin @("HEALTHY","DUPLICATE_SKIPPED") -or $age -gt 30) {
  throw "V2R4 WS shadow heartbeat is not fresh/healthy: status=$($h.status) age=$age s"
}
if ([string]$h.strategy_action -ne "NONE_SHADOW_ONLY" -or [bool]$h.real_money_actions) {
  throw "V2R4 WS shadow guardrails are not in the expected safe state."
}

$oneShot = Get-ScheduledTask -TaskName "CryptoMiniPC-V2R4ShadowResilienceOnce" -ErrorAction SilentlyContinue
if ($oneShot) {
  $oneInfo = $oneShot | Get-ScheduledTaskInfo
  Write-Host ("Original one-shot task: state=" + $oneShot.State + " last_run=" + $oneInfo.LastRunTime + " result=" + $oneInfo.LastTaskResult)
} else {
  Write-Host "Original one-shot task is no longer present; salvaging the fresh reboot evidence directly."
}

Write-Host ""
Write-Host "Running the post-boot verification now without another Windows restart..."
Write-Host "A short controlled Internet outage will occur automatically."

& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $postboot `
  -TradingRoot $TradingRoot `
  -DelaySeconds 30 `
  -OfflineSeconds 20 `
  -OneShotTaskName "CryptoMiniPC-V2R4ShadowResilienceOnce"
$code = $LASTEXITCODE

if (-not (Test-Path $latest)) {
  throw "Post-boot verifier finished with exit code $code but still did not create the summary file."
}

Write-Host ""
Get-Content $latest

if ($code -ne 0) { exit $code }
exit 0
