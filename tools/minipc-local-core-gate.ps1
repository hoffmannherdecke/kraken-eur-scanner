param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading")
)

$ErrorActionPreference = "Stop"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw "Bitte dieses Skript in einer als Administrator gestarteten PowerShell ausführen."
}

$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$preflight = Join-Path $repo "tools\minipc-v2r4-preflight-smoke.ps1"
$openaiPrep = Join-Path $repo "tools\minipc-openai-secret-prep.ps1"
$triggerE2E = Join-Path $repo "tools\minipc-v2r4-trigger-recheck-e2e.ps1"
$altradyPrep = Join-Path $repo "tools\minipc-altrady-secret-prep.ps1"
$openaiKeyFile = Join-Path $TradingRoot "Secrets\openai-api-key.txt"
$altradyTokenFile = Join-Path $TradingRoot "Secrets\altrady-webhook-token.txt"

foreach ($p in @($preflight,$openaiPrep,$triggerE2E,$altradyPrep)) {
  if (-not (Test-Path $p)) { throw "Required path missing: $p" }
}

Write-Host "[LOCAL-GATE] 1/4 V2R4 isolated MINI-PC preflight"
& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $preflight -TradingRoot $TradingRoot
if ($LASTEXITCODE -ne 0) {
  throw "V2R4 preflight failed. No secret preparation or physical E2E continued."
}

Write-Host ""
Write-Host "[LOCAL-GATE] 2/4 Secure local OpenAI API key"
if (Test-Path $openaiKeyFile) {
  $existing = (Get-Content $openaiKeyFile -Raw).Trim()
  if ($existing.Length -lt 20) { throw "Existing OpenAI key file is invalid/too short." }
  Write-Host "Existing local OpenAI key file kept unchanged."
} else {
  Write-Host "A valid OpenAI API key is required only for the local PAPER evaluator."
  Write-Host "Input is hidden and the key will not be printed."
  & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $openaiPrep -TradingRoot $TradingRoot
  if ($LASTEXITCODE -ne 0) { throw "OpenAI local secret preparation failed." }
}

Write-Host ""
Write-Host "[LOCAL-GATE] 3/4 Physical MINI-PC trigger -> fresh-recheck E2E"
& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $triggerE2E -TradingRoot $TradingRoot
if ($LASTEXITCODE -ne 0) {
  throw "Physical MINI-PC trigger-to-recheck E2E failed. Altrady token was NOT generated."
}

Write-Host ""
Write-Host "[LOCAL-GATE] 4/4 Prepare Altrady relay token for later Supabase secret entry"
if (Test-Path $altradyTokenFile) {
  $token = (Get-Content $altradyTokenFile -Raw).Trim()
  if ($token.Length -lt 24) { throw "Existing Altrady token file is invalid/too short." }
  Set-Clipboard -Value $token
  Write-Host "Existing Altrady relay token kept unchanged and copied to clipboard."
} else {
  & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $altradyPrep -TradingRoot $TradingRoot
  if ($LASTEXITCODE -ne 0) { throw "Altrady token preparation failed." }
}

Write-Host ""
Write-Host "=== MINI-PC LOCAL CORE GATE SUMMARY ==="
Write-Host "V2R4 isolated preflight: PASS"
Write-Host "Local OpenAI evaluator secret: PRESENT (value not printed)"
Write-Host "Physical trigger -> fresh paper recheck E2E: PASS"
Write-Host "Altrady relay token: PRESENT LOCALLY + COPIED TO CLIPBOARD"
Write-Host "Next manual secret action: set Supabase Edge Function secret ALTRADY_WEBHOOK_TOKEN from clipboard."
Write-Host "Do NOT paste either secret into ChatGPT, GitHub, Slack or logs."
Write-Host "Safety: PAPER ONLY / NO EXCHANGE ACCOUNT / NO ORDER API / NO REAL-MONEY ACTION"
Write-Host "=== END ==="
