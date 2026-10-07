param(
  [string]$TradingRoot = "",
  [switch]$Execute
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ([string]::IsNullOrWhiteSpace($TradingRoot)) {
  $homeRoot = if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }
  if ([string]::IsNullOrWhiteSpace($homeRoot)) { throw "Unable to resolve user home directory." }
  $TradingRoot = Join-Path $homeRoot "Trading"
}

$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$app = Join-Path $TradingRoot "Runtime\v3-h3-shadow-001"
$v2app = Join-Path $TradingRoot "Runtime\v2r4-paper-app"
$python = Join-Path $TradingRoot "Runtime\kraken-eur-scanner-venv\Scripts\python.exe"
$apiKey = Join-Path $TradingRoot "Secrets\openai-api-key.txt"
$relayToken = Join-Path $TradingRoot "Secrets\shadow-evidence-token.txt"
$heartbeat = Join-Path $TradingRoot "State\v3-h3-shadow-001-heartbeat.json"
$taskName = "CryptoMiniPC-V3H3Shadow001"
$expectedSeries = "PAPER-V2R4-20261007T184255Z"
$expectedRevision = "V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION"
$expectedConfigSha = "e533f05d31a5b80248076b4870addf4606dae3d8f0432a11ae66bea03db73ded"

function Get-CanonicalTextSha256([string]$Path) {
  $text = [System.IO.File]::ReadAllText($Path)
  $canonical = $text.Replace([string][char]13 + [char]10, [string][char]10).Replace([string][char]13, [string][char]10)
  $temp = [System.IO.Path]::GetTempFileName()
  try {
    [System.IO.File]::WriteAllText($temp, $canonical, [System.Text.UTF8Encoding]::new($false))
    return (Get-FileHash $temp -Algorithm SHA256).Hash.ToLowerInvariant()
  } finally {
    Remove-Item $temp -Force -ErrorAction SilentlyContinue
  }
}

foreach($p in @($repo,$v2app,$python,$apiKey,$relayToken)){
  if(-not(Test-Path -LiteralPath $p)){ throw "Required path missing: $p" }
}

$dirty = git -C $repo status --porcelain
if($LASTEXITCODE -ne 0){ throw "git status failed" }
if($dirty){ throw "Repository has local changes; refusing H3 install." }
$branchName = (git -C $repo branch --show-current).Trim()
if($branchName -ne "main"){ throw "Repository must be on main; current=$branchName" }
$head = (git -C $repo rev-parse HEAD).Trim()

$v2controlPath = Join-Path $v2app "paper_runtime_control.json"
$v2control = Get-Content $v2controlPath -Raw | ConvertFrom-Json
if($v2control.enabled -ne $true -or $v2control.paper_only -ne $true -or $v2control.real_money_actions_enabled -ne $false){
  throw "Active V2R4 runtime safety flags invalid."
}
if([string]$v2control.series_id -ne $expectedSeries){ throw "Active V2R4 series mismatch." }
if([string]$v2control.strategy_revision -ne $expectedRevision){ throw "Active V2R4 revision mismatch." }

$configSource = Join-Path $repo "research\v3\shadow-candidates\v3-h3-shadow-001-config.json"
$controlSource = Join-Path $repo "research\v3\shadow-runtime\h3-control.json"
$runtimeSource = Join-Path $repo "tools\v3-h3-shadow-runtime.py"
$commonSource = Join-Path $repo "tools\v3_h3_shadow_common.py"
$bookSource = Join-Path $repo "tools\v3-h3-kraken-ws-book-reconciliation-smoke.py"
foreach($p in @($configSource,$controlSource,$runtimeSource,$commonSource,$bookSource)){
  if(-not(Test-Path -LiteralPath $p)){ throw "Frozen H3 source missing: $p" }
}
$configSha = Get-CanonicalTextSha256 $configSource
if($configSha -ne $expectedConfigSha){ throw "Frozen H3 config SHA mismatch." }

$control = Get-Content $controlSource -Raw | ConvertFrom-Json
if($control.enabled -ne $true -or $control.orders -ne $false -or $control.real_money_actions -ne $false){
  throw "Frozen H3 control safety flags invalid."
}
if([string]$control.baseline_series_id -ne $expectedSeries -or [string]$control.baseline_strategy_revision -ne $expectedRevision){
  throw "Frozen H3 baseline binding mismatch."
}
if([string]$control.frozen_config_sha256 -ne $expectedConfigSha){ throw "H3 control config hash mismatch." }

Write-Host "=== V3-H3-SHADOW-001 INSTALL ==="
Write-Host ("Repository HEAD: " + $head)
Write-Host ("Baseline: " + $expectedSeries)
Write-Host "Scope: prospective H3 shadow only; active V2R4 remains unchanged"
Write-Host "Safety: public Kraken WS; no orders; no private exchange API; no real money"
if(-not $Execute){
  Write-Host "PLAN_ONLY - re-run with -Execute."
  exit 0
}

if(Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue){
  Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
}

New-Item -ItemType Directory -Force -Path $app | Out-Null
foreach($d in @("contexts","evidence","state")){
  New-Item -ItemType Directory -Force -Path (Join-Path $app $d) | Out-Null
}
Copy-Item $runtimeSource (Join-Path $app "v3-h3-shadow-runtime.py") -Force
Copy-Item $commonSource (Join-Path $app "v3_h3_shadow_common.py") -Force
Copy-Item $bookSource (Join-Path $app "v3-h3-kraken-ws-book-reconciliation-smoke.py") -Force
Copy-Item $configSource (Join-Path $app "v3-h3-shadow-001-config.json") -Force
Copy-Item $controlSource (Join-Path $app "h3-control.json") -Force

$appConfigSha = Get-CanonicalTextSha256 (Join-Path $app "v3-h3-shadow-001-config.json")
if($appConfigSha -ne $expectedConfigSha){ throw "Copied H3 config hash mismatch." }

$compileTargets = @(
  (Join-Path $app "v3-h3-shadow-runtime.py"),
  (Join-Path $app "v3_h3_shadow_common.py"),
  (Join-Path $app "v3-h3-kraken-ws-book-reconciliation-smoke.py")
)
& $python -m py_compile @compileTargets
if($LASTEXITCODE -ne 0){ throw "H3 runtime compile failed." }

$arguments = @(
  (Join-Path $app "v3-h3-shadow-runtime.py"),
  "--app-root", $app,
  "--v2r4-app-root", $v2app,
  "--trading-root", $TradingRoot,
  "--api-key-file", $apiKey,
  "--relay-token-file", $relayToken,
  "--source-commit", $head
)
$quoted = @()
foreach($x in $arguments){ $quoted += ('"' + [string]$x + '"') }
$action = New-ScheduledTaskAction -Execute $python -Argument ($quoted -join " ")
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -User "SYSTEM" -RunLevel Highest -Force | Out-Null

if(Test-Path $heartbeat){ Remove-Item $heartbeat -Force }
Start-ScheduledTask -TaskName $taskName

$deadline = (Get-Date).AddSeconds(120)
$hb = $null
while((Get-Date) -lt $deadline){
  Start-Sleep -Seconds 2
  if(-not(Test-Path $heartbeat)){ continue }
  try { $hb = Get-Content $heartbeat -Raw | ConvertFrom-Json } catch { continue }
  if(
    $hb.status -eq "HEALTHY" -and
    $hb.runtime_ready -eq $true -and
    [string]$hb.baseline_series_id -eq $expectedSeries -and
    $hb.cloud_sync_status -eq "PASS"
  ){ break }
}
if($null -eq $hb){ throw "No H3 runtime heartbeat received." }
if($hb.status -ne "HEALTHY" -or $hb.runtime_ready -ne $true){ throw "H3 runtime did not become HEALTHY/ready." }
if($hb.cloud_sync_status -ne "PASS"){ throw "H3 runtime cloud sync did not become PASS: $($hb.cloud_sync_error)" }

$task = Get-ScheduledTask -TaskName $taskName
$summary = [ordered]@{
  kind = "V3_H3_SHADOW_001_ACTIVATION_SUMMARY_V1"
  status = "PASS"
  shadow_candidate_id = "V3-H3-SHADOW-001"
  baseline_series_id = $expectedSeries
  baseline_strategy_revision = $expectedRevision
  repository_head = $head
  runtime_ready_at_utc = $hb.runtime_ready_at_utc
  runtime_status = $hb.status
  cloud_sync_status = $hb.cloud_sync_status
  scheduled_task_state = [string]$task.State
  intake_classification = [string]$hb.pilot_status.classification
  v2r4_changed = $false
  orders = $false
  private_exchange_api = $false
  real_money_actions = $false
  automatic_promotion = $false
}
Write-Host ""
Write-Host "=== V3-H3-SHADOW-001 ACTIVATION SUMMARY ==="
Write-Output ($summary | ConvertTo-Json -Depth 8)
Write-Host "=== END ==="
