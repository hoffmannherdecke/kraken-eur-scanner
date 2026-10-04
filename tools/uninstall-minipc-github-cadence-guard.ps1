param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading"),
  [switch]$RemoveSecret
)

$ErrorActionPreference = "Stop"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw "Bitte dieses Deinstallationsskript in einer als Administrator gestarteten PowerShell ausführen."
}

$taskName = "CryptoMiniPC-GitHubCadenceGuard"
$tokenFile = Join-Path $TradingRoot "Secrets\github-actions-dispatch-token.txt"

$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($task) {
  Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
  Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
  Write-Host ("Removed scheduled task: " + $taskName)
} else {
  Write-Host ("Task not installed: " + $taskName)
}

if ($RemoveSecret) {
  if (Test-Path $tokenFile) {
    Remove-Item -LiteralPath $tokenFile -Force
    Write-Host "Removed local GitHub dispatch token file."
  } else {
    Write-Host "Local GitHub dispatch token file was already absent."
  }
} else {
  Write-Host "Local GitHub dispatch token file was left untouched."
}

Write-Host "No repository, strategy, evaluator, market-data or trading state was modified."
