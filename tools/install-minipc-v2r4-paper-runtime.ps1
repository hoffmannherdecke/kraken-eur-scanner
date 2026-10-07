param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading"),
  [switch]$Execute,
  [string]$Confirm = ""
)

$impl = Join-Path $PSScriptRoot "install-minipc-v2r4-paper-runtime-v3.ps1"
if(-not (Test-Path $impl)){ throw "V2R4 paper activation implementation missing: $impl" }
& $impl -TradingRoot $TradingRoot -Execute:$Execute -Confirm $Confirm
exit $LASTEXITCODE
