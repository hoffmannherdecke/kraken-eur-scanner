param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading"),
  [int]$SmokeSeconds = 30
)

$ErrorActionPreference = "Stop"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw "Bitte dieses Installationsskript in einer als Administrator gestarteten PowerShell ausführen."
}

$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$python = Join-Path $TradingRoot "Runtime\kraken-eur-scanner-venv\Scripts\python.exe"
$snapshot = Join-Path $TradingRoot "State\kraken-eur-ticker-latest.json"
$smoke = Join-Path $repo "tools\minipc-v2r4-ws-shadow-smoke.ps1"
$runtimeCode = Join-Path $TradingRoot "Runtime\v2r4-ws-shadow-code"
$state = Join-Path $TradingRoot "State\v2r4-ws-shadow-state.json"
$heartbeat = Join-Path $TradingRoot "State\v2r4-ws-shadow-heartbeat.json"
$eventDir = Join-Path $TradingRoot "State\v2r4-ws-shadow-events"
$ledger = Join-Path $TradingRoot "Logs\v2r4-ws-shadow-ledger.jsonl"
$branch = "prep/v2r4-fast-trigger-minipc-20260929"
$taskName = "CryptoMiniPC-V2R4WSShadow"

foreach ($p in @($repo,$python,$snapshot,$smoke)) {
  if (-not (Test-Path $p)) { throw "Required path missing: $p" }
}

Write-Host "=== V2R4 WS SHADOW INSTALL ==="
Write-Host "1/4 Physical smoke before persistent activation..."

& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $smoke -TradingRoot $TradingRoot -Seconds $SmokeSeconds
if ($LASTEXITCODE -ne 0) {
  throw "Physical V2R4 WS shadow smoke failed; persistent task was NOT installed."
}

Write-Host "2/4 Pin inactive V2R4 prep branch into a detached runtime worktree..."

Push-Location $repo
try {
  git fetch origin $branch
  if ($LASTEXITCODE -ne 0) { throw "git fetch failed" }

  if (Test-Path $runtimeCode) {
    try { git worktree remove --force $runtimeCode | Out-Null } catch {}
  }
  git worktree prune | Out-Null

  git worktree add --detach $runtimeCode ("origin/" + $branch)
  if ($LASTEXITCODE -ne 0) { throw "git worktree add failed" }

  $runtimeCommit = (git -C $runtimeCode rev-parse HEAD).Trim()
  if (-not $runtimeCommit) { throw "Could not resolve pinned V2R4 runtime commit." }
} finally {
  Pop-Location
}

$watcher = Join-Path $runtimeCode "paper_evaluator\v2r4_ws_shadow_watcher.py"
if (-not (Test-Path $watcher)) { throw "Pinned WS shadow watcher missing: $watcher" }

New-Item -ItemType Directory -Force -Path $eventDir,(Split-Path $ledger -Parent) | Out-Null

Write-Host "3/4 Register startup task..."

$args = @(
  '"' + $watcher + '"',
  '--snapshot', '"' + $snapshot + '"',
  '--state', '"' + $state + '"',
  '--event-dir', '"' + $eventDir + '"',
  '--ledger', '"' + $ledger + '"',
  '--heartbeat', '"' + $heartbeat + '"',
  '--poll-seconds', '1',
  '--state-flush-seconds', '30'
) -join ' '

$action = New-ScheduledTaskAction -Execute $python -Argument $args
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -User "SYSTEM" -RunLevel Highest -Force | Out-Null
Start-ScheduledTask -TaskName $taskName

Write-Host "4/4 Verify fresh shadow heartbeat..."

$deadline = (Get-Date).AddSeconds(45)
$h = $null
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Seconds 2
  if (Test-Path $heartbeat) {
    try {
      $candidate = Get-Content $heartbeat -Raw | ConvertFrom-Json
      $ageSec = [math]::Round(((Get-Date).ToUniversalTime() - ([datetime]$candidate.checked_at_utc).ToUniversalTime()).TotalSeconds,1)
      if (
        $candidate.kind -eq "V2R4_WS_SHADOW_HEARTBEAT_V1" -and
        $candidate.status -in @("HEALTHY","DUPLICATE_SKIPPED") -and
        $ageSec -le 10 -and
        [int]$candidate.counters.snapshots_processed -gt 0
      ) {
        $h = $candidate
        break
      }
    } catch {}
  }
}

if (-not $h) {
  throw "V2R4 WS shadow task started but no fresh healthy heartbeat was observed within 45 seconds."
}

$manifest = [ordered]@{
  kind = "MINIPC_V2R4_WS_SHADOW_RUNTIME_V1"
  installed_at_local = (Get-Date).ToString("o")
  task_name = $taskName
  runtime_commit = $runtimeCommit
  runtime_branch = $branch
  runtime_path = $runtimeCode
  snapshot_path = $snapshot
  heartbeat_path = $heartbeat
  state_path = $state
  ledger_path = $ledger
  event_dir = $eventDir
  guardrails = [ordered]@{
    v2r3_changed = $false
    evaluator_invoked = $false
    strategy_action = "NONE_SHADOW_ONLY"
    order_api = $false
    account_credentials = $false
    real_money_actions = $false
  }
}
$manifestPath = Join-Path $TradingRoot "State\v2r4-ws-shadow-runtime.json"
[System.IO.File]::WriteAllText(
  $manifestPath,
  ($manifest | ConvertTo-Json -Depth 8) + [Environment]::NewLine,
  [System.Text.UTF8Encoding]::new($false)
)

Write-Host ""
Write-Host "=== V2R4 WS SHADOW INSTALL SUMMARY ==="
Write-Host "Status: HEALTHY"
Write-Host ("Task: " + $taskName)
Write-Host ("Pinned commit: " + $runtimeCommit)
Write-Host ("Heartbeat: " + $h.status + " | source_age=" + $h.source_age_seconds + "s")
Write-Host ("Snapshots processed: " + $h.counters.snapshots_processed + " | events=" + $h.counters.events_emitted)
Write-Host ("Runtime manifest: " + $manifestPath)
Write-Host "Safety: SHADOW ONLY / V2R3 UNCHANGED / NO EVALUATOR / NO ACCOUNT / NO ORDERS / NO REAL-MONEY ACTION"
Write-Host "=== END ==="
