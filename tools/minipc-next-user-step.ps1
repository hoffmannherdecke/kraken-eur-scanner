param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading")
)

$ErrorActionPreference = "Stop"

$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$coreGate = Join-Path $repo "tools\minipc-local-core-gate.ps1"

if (-not (Test-Path $coreGate)) {
  throw "Required path missing: $coreGate"
}

Write-Host "This compatibility entry point now delegates to the canonical local core gate."
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $coreGate -TradingRoot $TradingRoot
if ($LASTEXITCODE -ne 0) {
  throw "MINI-PC local core gate failed with exit code $LASTEXITCODE"
}
