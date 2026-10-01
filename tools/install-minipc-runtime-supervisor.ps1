param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading")
)

$ErrorActionPreference = "Stop"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw "Bitte dieses Installationsskript in einer als Administrator gestarteten PowerShell ausführen."
}

$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$supervisor = Join-Path $repo "tools\minipc-runtime-supervisor.ps1"
$watchdog = Join-Path $repo "tools\minipc-watchdog.ps1"
$taskName = "CryptoMiniPC-RuntimeSupervisor"

foreach ($p in @($repo,$supervisor,$watchdog)) {
  if (-not (Test-Path $p)) { throw "Required path missing: $p" }
}

Write-Host "=== MINI-PC RUNTIME SUPERVISOR INSTALL ==="
Write-Host "1/4 Capture + immediate bounded recovery of stale read-only runtimes..."

$supervisorState = Join-Path $TradingRoot "State\minipc-runtime-supervisor.json"
$supervisorLog = Join-Path $TradingRoot "Logs\minipc-runtime-supervisor-install-last.txt"

& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $supervisor -TradingRoot $TradingRoot -ForceRecovery 2>&1 |
  Tee-Object -FilePath $supervisorLog | Out-Null
$firstCode = $LASTEXITCODE

if (-not (Test-Path $supervisorState)) {
  Write-Host ""
  Write-Host "Supervisor did not create its state report. Last supervisor output:"
  if (Test-Path $supervisorLog) { Get-Content $supervisorLog -Tail 40 }
  throw "Initial supervisor run failed before producing a state report."
}

$first = Get-Content $supervisorState -Raw | ConvertFrom-Json
if ($firstCode -ne 0 -or $first.status -eq "CRITICAL") {
  Write-Host ""
  Write-Host ("Supervisor status: " + $first.status)
  if ($first.error) { Write-Host ("Supervisor error: " + $first.error) }
  throw "Initial supervisor recovery found an unrecoverable task failure."
}

Write-Host "2/4 Register supervisor every 2 minutes + at startup..."
$args = @(
  "-NoProfile","-NonInteractive","-ExecutionPolicy","Bypass","-File",('"' + $supervisor + '"'),
  "-TradingRoot",('"' + $TradingRoot + '"')
) -join " "
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $args
$triggerStartup = New-ScheduledTaskTrigger -AtStartup
$triggerRepeat = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Minutes 2)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 2)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger @($triggerStartup,$triggerRepeat) -Settings $settings -User "SYSTEM" -RunLevel Highest -Force | Out-Null

Write-Host "3/4 Refresh local watchdog after recovery..."
& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $watchdog -TradingRoot $TradingRoot | Out-Null
$watchdogCode = $LASTEXITCODE

Write-Host "4/4 Verify supervisor result..."
$latest = Get-Content (Join-Path $TradingRoot "State\minipc-runtime-supervisor.json") -Raw | ConvertFrom-Json
$health = Get-Content (Join-Path $TradingRoot "State\minipc-health.json") -Raw | ConvertFrom-Json

Write-Host ""
Write-Host "=== MINI-PC RUNTIME SUPERVISOR INSTALL SUMMARY ==="
Write-Host ("Supervisor: " + $latest.status)
Write-Host ("Recovered tasks: " + $(if ($latest.restarted.Count -gt 0) { $latest.restarted -join ", " } else { "none" }))
Write-Host ("Local watchdog after recovery: " + $health.status)
Write-Host ("Task: " + $taskName + " | every 2 min + startup")
Write-Host "Backoff: repeated restart attempts for the same task are limited to once per 10 minutes."
Write-Host "Safety: READ-ONLY RUNTIMES ONLY / NO STRATEGY CHANGE / NO EVALUATOR / NO ORDERS / NO REAL-MONEY ACTION"
Write-Host "=== END ==="

if ($watchdogCode -ne 0) { exit $watchdogCode }
