param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading")
)

$ErrorActionPreference = "Stop"

$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$preflight = Join-Path $repo "tools\minipc-v2r4-preflight-smoke.ps1"
$secretPrep = Join-Path $repo "tools\minipc-altrady-secret-prep.ps1"
$tokenFile = Join-Path $TradingRoot "Secrets\altrady-webhook-token.txt"

foreach ($p in @($preflight,$secretPrep)) {
  if (-not (Test-Path $p)) { throw "Required path missing: $p" }
}

Write-Host "[NEXT-USER-STEP] 1/2 Run isolated V2R4 MINI-PC preflight"
& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $preflight -TradingRoot $TradingRoot
if ($LASTEXITCODE -ne 0) {
  throw "V2R4 MINI-PC preflight failed with exit code $LASTEXITCODE. Altrady secret was NOT generated."
}

Write-Host ""
Write-Host "[NEXT-USER-STEP] 2/2 Prepare Altrady relay secret"
if (Test-Path $tokenFile) {
  $token = (Get-Content $tokenFile -Raw).Trim()
  if ($token.Length -lt 24) { throw "Existing Altrady token file is invalid/too short." }
  Set-Clipboard -Value $token
  Write-Host "Existing secret kept unchanged and copied to clipboard."
  Write-Host ("Secret file: " + $tokenFile)
} else {
  & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $secretPrep -TradingRoot $TradingRoot
  if ($LASTEXITCODE -ne 0) { throw "Altrady secret preparation failed with exit code $LASTEXITCODE" }
}

Write-Host ""
Write-Host "=== NEXT USER STEP SUMMARY ==="
Write-Host "V2R4 MINI-PC isolated preflight: PASS"
Write-Host "Altrady relay token: PRESENT LOCALLY + COPIED TO CLIPBOARD"
Write-Host "Token value was not printed."
Write-Host "Next manual action: configure Supabase Edge Function secret ALTRADY_WEBHOOK_TOKEN using the clipboard value."
Write-Host "Do not paste the token into ChatGPT/GitHub/Slack."
Write-Host "=== END ==="
