param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading")
)

$ErrorActionPreference = "Stop"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw "Bitte dieses Skript in einer als Administrator gestarteten PowerShell ausführen."
}

$taskName = "CryptoMiniPC-V2R4WSShadow"
$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$runtimeCode = Join-Path $TradingRoot "Runtime\v2r4-ws-shadow-code"

$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($task) {
  try { Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue } catch {}
  Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
  Write-Host ("Removed scheduled task " + $taskName)
} else {
  Write-Host ($taskName + " is not installed.")
}

if (Test-Path $repo) {
  Push-Location $repo
  try {
    if (Test-Path $runtimeCode) {
      try { git worktree remove --force $runtimeCode | Out-Null } catch {
        Write-Warning ("Could not remove runtime worktree automatically: " + $_.Exception.Message)
      }
    }
    git worktree prune | Out-Null
  } finally {
    Pop-Location
  }
}

Write-Host "State, heartbeat, ledger and shadow events were intentionally left in place for auditability."
