param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading")
)

$ErrorActionPreference = "Stop"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw "Bitte dieses Skript in einer als Administrator gestarteten PowerShell ausführen."
}

$task = Get-ScheduledTask -TaskName "CryptoMiniPC-KrakenUniverse" -ErrorAction SilentlyContinue
if ($task) {
  try { Stop-ScheduledTask -TaskName "CryptoMiniPC-KrakenUniverse" -ErrorAction SilentlyContinue } catch {}
  Unregister-ScheduledTask -TaskName "CryptoMiniPC-KrakenUniverse" -Confirm:$false
  Write-Host "Removed scheduled task CryptoMiniPC-KrakenUniverse."
} else {
  Write-Host "CryptoMiniPC-KrakenUniverse is not installed."
}

Write-Host "State/log files were intentionally left in place for auditability."
