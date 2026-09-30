param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading")
)

$ErrorActionPreference = "Stop"

$keyFile = Join-Path $TradingRoot "Secrets\openai-api-key.txt"
if (-not (Test-Path $keyFile)) {
  throw "OpenAI key file missing: $keyFile"
}

$key = (Get-Content $keyFile -Raw).Trim()
if (-not $key -or $key.Length -lt 20) {
  throw "Stored OpenAI key is empty/too short."
}

Write-Host "=== OPENAI AUTH DIAGNOSTIC ==="
Write-Host ("Stored key format: " + $(if ($key.StartsWith("sk-")) { "sk-* / plausible" } else { "unexpected prefix" }))
Write-Host ("Stored key length: " + $key.Length + " characters")
Write-Host "Testing authenticated GET /v1/models (key value will NOT be printed)..."

try {
  $null = Invoke-WebRequest -UseBasicParsing -Uri "https://api.openai.com/v1/models" -Headers @{ Authorization = ("Bearer " + $key) } -Method GET -TimeoutSec 30
  Write-Host "HTTP status: 200"
  Write-Host "OPENAI_AUTH: PASS"
  Write-Host "=== END ==="
  exit 0
}
catch {
  $status = $null
  $body = $null
  $resp = $_.Exception.Response
  if ($resp) {
    try { $status = [int]$resp.StatusCode } catch {}
    try {
      $reader = New-Object System.IO.StreamReader($resp.GetResponseStream())
      $body = $reader.ReadToEnd()
      $reader.Close()
    } catch {}
  }

  Write-Host ("HTTP status: " + $(if ($status) { $status } else { "unknown" }))

  if ($body) {
    try {
      $j = $body | ConvertFrom-Json
      $code = $j.error.code
      $type = $j.error.type
      Write-Host ("OpenAI error code: " + $(if ($code) { $code } else { "(none)" }))
      Write-Host ("OpenAI error type: " + $(if ($type) { $type } else { "(none)" }))
    } catch {
      Write-Host "OpenAI error body was present but could not be parsed."
    }
  } else {
    Write-Host ("Transport error: " + $_.Exception.Message)
  }

  Write-Host "OPENAI_AUTH: FAIL"
  Write-Host "=== END ==="
  exit 2
}
