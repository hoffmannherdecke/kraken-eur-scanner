param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading")
)

$ErrorActionPreference = "Stop"
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw "Bitte dieses Installationsskript in einer als Administrator gestarteten PowerShell ausführen."
}

$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$python = Join-Path $TradingRoot "Runtime\kraken-eur-scanner-venv\Scripts\python.exe"
$tool = Join-Path $repo "tools\minipc-status-sync.py"
$health = Join-Path $TradingRoot "State\minipc-health.json"
$token = Join-Path $TradingRoot "Secrets\altrady-webhook-token.txt"
$heartbeat = Join-Path $TradingRoot "State\minipc-status-sync-heartbeat.json"
$taskName = "CryptoMiniPC-StatusSync"

foreach ($p in @($repo,$python,$tool,$health,$token)) {
  if (-not (Test-Path $p)) { throw "Required path missing: $p" }
}

Write-Host "=== MINI-PC STATUS SYNC INSTALL ==="
Write-Host "1/3 Compile + authenticated one-shot status upload..."
& $python -m py_compile $tool
if ($LASTEXITCODE -ne 0) { throw "Status sync compile failed." }

& $python $tool --trading-root $TradingRoot --once
if ($LASTEXITCODE -ne 0) {
  if (Test-Path $heartbeat) {
    try {
      $failed = Get-Content $heartbeat -Raw | ConvertFrom-Json
      Write-Host ("Sync status: " + $failed.status + " | detail=" + $failed.detail)
    } catch {}
  }
  throw "Authenticated status upload failed; persistent task was NOT installed."
}

$first = Get-Content $heartbeat -Raw | ConvertFrom-Json
if ($first.status -ne "HEALTHY") { throw "One-shot status upload did not finish HEALTHY." }

Write-Host "2/3 Register persistent startup task..."
$args = @(
  ('"' + $tool + '"'),
  "--trading-root",('"' + $TradingRoot + '"'),
  "--interval-seconds","300"
) -join " "
$action = New-ScheduledTaskAction -Execute $python -Argument $args
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -User "SYSTEM" -RunLevel Highest -Force | Out-Null
Start-ScheduledTask -TaskName $taskName

Write-Host "3/3 Verify persistent heartbeat..."
$deadline = (Get-Date).AddSeconds(45)
$hb = $null
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Seconds 2
  if (Test-Path $heartbeat) {
    try {
      $candidate = Get-Content $heartbeat -Raw | ConvertFrom-Json
      $age = [math]::Round(((Get-Date).ToUniversalTime() - ([datetime]$candidate.checked_at_utc).ToUniversalTime()).TotalSeconds,1)
      if ($candidate.status -eq "HEALTHY" -and $age -le 20) { $hb = $candidate; break }
    } catch {}
  }
}
if (-not $hb) { throw "Status sync task started but no fresh HEALTHY heartbeat was observed." }

Write-Host ""
Write-Host "=== MINI-PC STATUS SYNC INSTALL SUMMARY ==="
Write-Host "Status: HEALTHY"
Write-Host ("Task: " + $taskName)
Write-Host ("Uploaded local health status: " + $first.uploaded_health_status)
Write-Host ("Persistent heartbeat: " + $hb.status + " | node=" + $hb.node_id)
Write-Host "Destination: Supabase minipc_status_current via authenticated Edge Function"
Write-Host "Safety: STATUS ONLY / SECRET NOT PRINTED / NO EVALUATOR / NO ACCOUNT / NO ORDERS / NO REAL-MONEY ACTION"
Write-Host "=== END ==="
