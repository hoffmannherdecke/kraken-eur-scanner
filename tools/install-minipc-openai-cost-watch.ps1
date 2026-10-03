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
$python = Join-Path $TradingRoot "Runtime\kraken-eur-scanner-venv\Scripts\python.exe"
$tool = Join-Path $repo "tools\minipc-openai-cost-watch.py"
$keyFile = Join-Path $TradingRoot "Secrets\openai-admin-key.txt"
$stateFile = Join-Path $TradingRoot "State\openai-api-cost-watch.json"
$taskName = "CryptoMiniPC-OpenAICostWatch"

foreach ($p in @($repo,$python,$tool,$keyFile)) {
  if (-not (Test-Path $p)) { throw "Required path missing: $p" }
}

Write-Host "=== OPENAI COST WATCH INSTALL ==="
Write-Host "1/4 Compile + deterministic self-test..."
& $python -m py_compile $tool
if ($LASTEXITCODE -ne 0) { throw "Cost-watch compile failed." }
& $python $tool --self-test
if ($LASTEXITCODE -ne 0) { throw "Cost-watch self-test failed." }

Write-Host "2/4 One-shot read-only OpenAI organization cost query..."
& $python $tool --trading-root $TradingRoot
if ($LASTEXITCODE -ne 0) {
  if (Test-Path $stateFile) {
    try {
      $failed = Get-Content $stateFile -Raw | ConvertFrom-Json
      Write-Host ("Status: " + $failed.status + " | detail=" + $failed.detail)
    } catch {}
  }
  throw "OpenAI cost query failed; persistent task was NOT installed."
}

$first = Get-Content $stateFile -Raw | ConvertFrom-Json
if ($first.status -ne "HEALTHY") { throw "One-shot cost query did not finish HEALTHY." }
if ($first.direct_prepaid_balance_supported -ne $false) { throw "Safety contract violated: prepaid balance must remain unsupported." }
if ($first.billing_mutation -ne $false -or $first.model_request_made -ne $false) { throw "Safety contract violated." }

Write-Host "3/4 Register four daily triggers (6h cadence)..."
$argLine = @(
  ('"' + $tool + '"'),
  "--trading-root",('"' + $TradingRoot + '"')
) -join " "
$action = New-ScheduledTaskAction -Execute $python -Argument $argLine
$triggers = @(
  (New-ScheduledTaskTrigger -Daily -At "00:17"),
  (New-ScheduledTaskTrigger -Daily -At "06:17"),
  (New-ScheduledTaskTrigger -Daily -At "12:17"),
  (New-ScheduledTaskTrigger -Daily -At "18:17")
)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 5) -ExecutionTimeLimit (New-TimeSpan -Minutes 3)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $triggers -Settings $settings -User "SYSTEM" -RunLevel Highest -Force | Out-Null

Write-Host "4/4 Summary..."
Write-Host ("Task: " + $taskName)
Write-Host "Cadence: 00:17 / 06:17 / 12:17 / 18:17 local time"
Write-Host ("Month spend USD: " + $first.month_spend_usd)
Write-Host "Exact prepaid balance: intentionally NOT claimed/not available from documented endpoint."
Write-Host "Model tokens used by watcher: 0"
Write-Host "Safety: GET-only / no billing mutation / no model request / no strategy / no orders / no real-money action"
Write-Host "=== END ==="
