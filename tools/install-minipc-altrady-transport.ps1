param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading"),
  [int]$IntervalSeconds = 10
)

$ErrorActionPreference = "Stop"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw "Bitte dieses Installationsskript in einer als Administrator gestarteten PowerShell ausführen."
}

if ($IntervalSeconds -lt 5 -or $IntervalSeconds -gt 60) {
  throw "IntervalSeconds must be between 5 and 60."
}

$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$poller = Join-Path $repo "tools\minipc-altrady-poller.py"
$python = Join-Path $TradingRoot "Runtime\kraken-eur-scanner-venv\Scripts\python.exe"
$tokenFile = Join-Path $TradingRoot "Secrets\altrady-webhook-token.txt"

foreach ($p in @($poller,$python,$tokenFile)) {
  if (-not (Test-Path $p)) { throw "Required path missing: $p" }
}

$token = (Get-Content -LiteralPath $tokenFile -Raw).Trim()
if ($token.Length -lt 24) {
  throw "Altrady relay token is missing or too short."
}

$endpoint = "https://nlgzjmqgwueojlyqmoru.supabase.co/functions/v1/altrady-trigger-relay"
$args = '"' + $poller + '" --trading-root "' + $TradingRoot + '" --endpoint "' + $endpoint + '" --interval-seconds ' + $IntervalSeconds

$action = New-ScheduledTaskAction -Execute $python -Argument $args
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask -TaskName "CryptoMiniPC-AltradyTrigger" -Action $action -Trigger $trigger -Settings $settings -User "SYSTEM" -RunLevel Highest -Force | Out-Null

Start-ScheduledTask -TaskName "CryptoMiniPC-AltradyTrigger"
Start-Sleep -Seconds ([Math]::Min(15,[Math]::Max(6,$IntervalSeconds+2)))

$heartbeat = Join-Path $TradingRoot "State\altrady-trigger-heartbeat.json"
if (-not (Test-Path $heartbeat)) {
  throw "Altrady trigger task started but no heartbeat file was created."
}
$state = Get-Content $heartbeat -Raw | ConvertFrom-Json
if ($state.status -ne "HEALTHY") {
  throw ("Altrady trigger heartbeat is not healthy: " + $state.detail)
}

Write-Host "Installed: CryptoMiniPC-AltradyTrigger"
Write-Host ("Heartbeat: " + $heartbeat)
Write-Host ("Status: " + $state.status)
Write-Host ("Strategy action: " + $state.strategy_action)
