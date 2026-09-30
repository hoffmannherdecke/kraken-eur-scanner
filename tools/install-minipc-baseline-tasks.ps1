param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading")
)

$ErrorActionPreference = "Stop"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw "Bitte dieses Installationsskript einmal in einer als Administrator gestarteten PowerShell ausführen."
}

$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$watchdog = Join-Path $repo "tools\minipc-watchdog.ps1"
$cleanup = Join-Path $repo "tools\minipc-log-cleanup.ps1"

foreach ($p in @($watchdog,$cleanup)) {
  if (-not (Test-Path $p)) { throw "Fehlende Datei: $p" }
}
foreach ($d in @("Runtime","State","Logs","Temp","Archive","Backup","Secrets","Repos")) {
  New-Item -ItemType Directory -Force -Path (Join-Path $TradingRoot $d) | Out-Null
}

$ps = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$healthArgs = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$watchdog`" -TradingRoot `"$TradingRoot`""
$cleanupArgs = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$cleanup`" -TradingRoot `"$TradingRoot`""

$healthAction = New-ScheduledTaskAction -Execute $ps -Argument $healthArgs
$healthTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)
$healthStartup = New-ScheduledTaskTrigger -AtStartup
$healthSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 3)
Register-ScheduledTask -TaskName "CryptoMiniPC-Health" -Action $healthAction -Trigger @($healthTrigger,$healthStartup) -Settings $healthSettings -User "SYSTEM" -RunLevel Highest -Force | Out-Null

$cleanupAction = New-ScheduledTaskAction -Execute $ps -Argument $cleanupArgs
$cleanupTrigger = New-ScheduledTaskTrigger -Daily -At "04:20"
$cleanupSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName "CryptoMiniPC-LogCleanup" -Action $cleanupAction -Trigger $cleanupTrigger -Settings $cleanupSettings -User "SYSTEM" -RunLevel Highest -Force | Out-Null

# Run one health check immediately in the current elevated session.
& $watchdog -TradingRoot $TradingRoot
$exit = $LASTEXITCODE

Write-Host ""
Write-Host "Installiert:"
Write-Host "  CryptoMiniPC-Health      -> alle 5 Minuten + bei Systemstart"
Write-Host "  CryptoMiniPC-LogCleanup  -> täglich 04:20"
Write-Host "Health state: $(Join-Path $TradingRoot 'State\minipc-health.json')"
Write-Host "Health log:   $(Join-Path $TradingRoot 'Logs\minipc-watchdog.log')"
Write-Host "Immediate health exit code: $exit"
