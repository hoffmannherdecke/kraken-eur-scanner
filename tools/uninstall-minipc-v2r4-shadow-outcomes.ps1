param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading")
)

$ErrorActionPreference = "Stop"
$taskName = "CryptoMiniPC-V2R4ShadowOutcomes"
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($task) {
  try { Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue } catch {}
  Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
  Write-Host ("Removed scheduled task " + $taskName)
} else {
  Write-Host ($taskName + " is not installed.")
}
Write-Host "Outcome state/evidence files were intentionally retained for auditability."
