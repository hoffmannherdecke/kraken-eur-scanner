param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading")
)

$ErrorActionPreference = "Stop"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw "Bitte dieses Skript in einer als Administrator gestarteten PowerShell ausführen."
}

$task = Get-ScheduledTask -TaskName "CryptoMiniPC-KrakenCanary" -ErrorAction SilentlyContinue
if ($task) {
  Stop-ScheduledTask -TaskName "CryptoMiniPC-KrakenCanary" -ErrorAction SilentlyContinue
  Unregister-ScheduledTask -TaskName "CryptoMiniPC-KrakenCanary" -Confirm:$false
}
Write-Host "Removed: CryptoMiniPC-KrakenCanary"
