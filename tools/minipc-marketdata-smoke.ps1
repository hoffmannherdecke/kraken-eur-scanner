param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading"),
  [int]$Seconds = 45
)

$ErrorActionPreference = "Stop"
if ($Seconds -lt 10 -or $Seconds -gt 120) { throw "Seconds must be between 10 and 120" }

$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$python = Join-Path $TradingRoot "Runtime\kraken-eur-scanner-venv\Scripts\python.exe"
$tempRoot = Join-Path $TradingRoot "Temp"
$logDir = Join-Path $TradingRoot "Logs"

if (-not (Test-Path $repo)) { throw "Repository missing: $repo" }
if (-not (Test-Path $python)) { throw "Venv Python missing: $python" }

New-Item -ItemType Directory -Force -Path $tempRoot,$logDir | Out-Null

# Pin only the public WebSocket transport dependency used by the shared market-data layer.
& $python -m pip install --disable-pip-version-check "websockets==15.0.1"
if ($LASTEXITCODE -ne 0) { throw "websockets installation failed" }

Push-Location $repo
try {
  & $python -m unittest discover -s market_data -p "test_*.py" -v
  if ($LASTEXITCODE -ne 0) { throw "market_data unit tests failed" }

  $stamp = (Get-Date).ToString("yyyyMMdd-HHmmss")
  $out = Join-Path $tempRoot "kraken-market-smoke-$stamp"
  & $python "paper_capture\market.py" --seconds $Seconds --out $out --smoke
  if ($LASTEXITCODE -ne 0) { throw "live Kraken public WebSocket smoke failed" }

  $manifestPath = Join-Path $out "manifest.json"
  if (-not (Test-Path $manifestPath)) { throw "market smoke manifest missing" }
  $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json

  $bookVerified = [int]($manifest.counts.book_verified)
  $tradeObserved = [int]($manifest.counts.trade_observed)
  $dataGaps = [int]($manifest.counts.data_gap)
  $subscriptionErrors = [int]($manifest.counts.subscription_error)

  if ($bookVerified -lt 2) { throw "insufficient verified book events: $bookVerified" }
  if ($tradeObserved -lt 1) { throw "no trade events observed" }
  if ($dataGaps -gt 0) { throw "data gap observed during bounded smoke: $dataGaps" }
  if ($subscriptionErrors -gt 0) { throw "subscription error observed: $subscriptionErrors" }

  $result = [ordered]@{
    kind = "MINIPC_KRAKEN_MARKETDATA_SMOKE_V1"
    checked_at_local = (Get-Date).ToString("o")
    status = "PASS"
    seconds = $Seconds
    book_verified = $bookVerified
    trade_observed = $tradeObserved
    data_gap = $dataGaps
    subscription_error = $subscriptionErrors
    manifest = $manifestPath
    safety = [ordered]@{
      public_data_only = $true
      account_credentials = $false
      order_methods = $false
      live_evaluation = $false
      real_money_actions = $false
    }
  }

  $report = Join-Path $logDir "minipc-marketdata-smoke-$stamp.json"
  [System.IO.File]::WriteAllText(
    $report,
    ($result | ConvertTo-Json -Depth 6) + [Environment]::NewLine,
    [System.Text.UTF8Encoding]::new($false)
  )
  $result | ConvertTo-Json -Depth 6
  Write-Host "Report: $report"
} finally {
  Pop-Location
}
