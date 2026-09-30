param(
  [Parameter(Mandatory=$true)]
  [ValidateSet("Url","TimeTestPayload","LivePriceTestPayload","PricePayload")]
  [string]$Mode,
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading")
)

$ErrorActionPreference = "Stop"

$endpoint = "https://nlgzjmqgwueojlyqmoru.supabase.co/functions/v1/altrady-trigger-relay"
$tokenFile = Join-Path $TradingRoot "Secrets\altrady-webhook-token.txt"

if ($Mode -eq "Url") {
  Set-Clipboard -Value $endpoint
  Write-Host "Altrady relay URL copied to clipboard."
  exit 0
}

if (-not (Test-Path $tokenFile)) {
  throw "Altrady relay token file missing: $tokenFile"
}
$token = (Get-Content -LiteralPath $tokenFile -Raw).Trim()
if ($token.Length -lt 24) {
  throw "Altrady relay token missing/too short."
}
$escaped = $token.Replace("\","\\").Replace('"','\"')

switch ($Mode) {
  "TimeTestPayload" {
    $payload = '{"token":"' + $escaped + '","exchange":"{{exchange}}","symbol":"{{symbol}}","direction":"LIVE_ALTRADY_TIME_TEST","time":"{{time}}"}'
  }
  "LivePriceTestPayload" {
    $payload = '{"token":"' + $escaped + '","exchange":"{{exchange}}","symbol":"{{symbol}}","direction":"LIVE_ALTRADY_PRICE_TEST","altrady_direction":"{{direction}}","close":"{{close}}","time":"{{time}}"}'
  }
  "PricePayload" {
    $payload = '{"token":"' + $escaped + '","exchange":"{{exchange}}","symbol":"{{symbol}}","direction":"{{direction}}","close":"{{close}}","time":"{{time}}","low":"{{low}}","high":"{{high}}"}'
  }
}

Set-Clipboard -Value $payload
Write-Host "Altrady JSON payload copied to clipboard."
Write-Host "Secret value was not printed."
