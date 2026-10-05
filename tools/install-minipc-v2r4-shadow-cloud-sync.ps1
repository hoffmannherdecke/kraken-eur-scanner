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
$tool = Join-Path $repo "tools\v2r4-shadow-cloud-sync.py"
$token = Join-Path $TradingRoot "Secrets\shadow-evidence-token.txt"
$heartbeat = Join-Path $TradingRoot "State\v2r4-shadow-cloud-sync-heartbeat.json"
$taskName = "CryptoMiniPC-V2R4ShadowCloudSync"

foreach ($p in @($repo,$python,$tool,$token)) {
  if (-not (Test-Path $p)) { throw "Required path missing: $p" }
}

Write-Host "=== V2R4 SHADOW CLOUD ARCHIVE INSTALL ==="
Write-Host "1/3 Compile + authenticated one-shot archive smoke..."
& $python -m py_compile $tool
if ($LASTEXITCODE -ne 0) { throw "Cloud sync compile failed." }

& $python $tool --trading-root $TradingRoot --once
if ($LASTEXITCODE -ne 0) {
  if (Test-Path $heartbeat) {
    try {
      $failed = Get-Content $heartbeat -Raw | ConvertFrom-Json
      Write-Host ("Sync status: " + $failed.status + " | detail=" + $failed.detail)
    } catch {}
  }
  throw "Authenticated V2R4 shadow archive smoke failed; persistent sync task was NOT installed."
}

$first = Get-Content $heartbeat -Raw | ConvertFrom-Json
if ($first.status -ne "HEALTHY") { throw "One-shot archive smoke did not finish HEALTHY." }

Write-Host "2/3 Register persistent startup task..."
$args = @(
  ('"' + $tool + '"'),
  "--trading-root",('"' + $TradingRoot + '"'),
  "--interval-seconds","60"
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
      if ($candidate.status -eq "HEALTHY" -and $age -le 20) {
        $hb = $candidate
        break
      }
    } catch {}
  }
}
if (-not $hb) { throw "Cloud archive task started but no fresh HEALTHY heartbeat was observed." }

Write-Host ""
Write-Host "=== V2R4 SHADOW CLOUD ARCHIVE INSTALL SUMMARY ==="
Write-Host "Status: HEALTHY"
Write-Host ("Task: " + $taskName)
Write-Host ("Initial upload: " + $first.uploaded_records + " records in " + $first.batches + " batch(es)")
Write-Host ("Persistent heartbeat: pending=" + $hb.pending_records + " uploaded_this_cycle=" + $hb.uploaded_records)
Write-Host "Destination: Supabase v2r4_shadow_evidence via authenticated Edge Function"
Write-Host "Safety: ARCHIVE ONLY / SECRET NOT PRINTED / NO EVALUATOR / NO ACCOUNT / NO ORDERS / NO REAL-MONEY ACTION"
Write-Host "=== END ==="
