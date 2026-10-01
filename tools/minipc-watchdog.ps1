param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading")
)

$ErrorActionPreference = "Stop"
$now = Get-Date
$stateDir = Join-Path $TradingRoot "State"
$logDir = Join-Path $TradingRoot "Logs"
$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$venvPython = Join-Path $TradingRoot "Runtime\kraken-eur-scanner-venv\Scripts\python.exe"

New-Item -ItemType Directory -Force -Path $stateDir,$logDir | Out-Null

$checks = [ordered]@{}
$issues = New-Object System.Collections.Generic.List[object]

function Add-Check {
  param([string]$Name,[bool]$Ok,[string]$Detail,[string]$Severity="CRITICAL")
  $checks[$Name] = [ordered]@{ ok=$Ok; detail=$Detail }
  if (-not $Ok) {
    $issues.Add([ordered]@{ check=$Name; severity=$Severity; detail=$Detail })
  }
}

# Disk: warn below 20 GB, critical below 10 GB.
try {
  $drive = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
  $freeGB = [math]::Round($drive.FreeSpace / 1GB, 1)
  $sizeGB = [math]::Round($drive.Size / 1GB, 1)
  Add-Check "disk_space" ($freeGB -ge 10) "C: $freeGB GB free of $sizeGB GB" "CRITICAL"
  if ($freeGB -ge 10 -and $freeGB -lt 20) {
    $issues.Add([ordered]@{ check="disk_space_warning"; severity="WARNING"; detail="C: only $freeGB GB free" })
  }
} catch {
  Add-Check "disk_space" $false $_.Exception.Message
}

# Repo + venv presence.
Add-Check "repo_exists" (Test-Path $repo) $repo
Add-Check "venv_python_exists" (Test-Path $venvPython) $venvPython

# Network path to Kraken.
try {
  $dns = Resolve-DnsName api.kraken.com -Type A -ErrorAction Stop | Select-Object -First 1
  Add-Check "kraken_dns" ([bool]$dns.IPAddress) ("api.kraken.com -> " + $dns.IPAddress)
} catch {
  Add-Check "kraken_dns" $false $_.Exception.Message
}

try {
  $tcp = Test-NetConnection api.kraken.com -Port 443 -InformationLevel Quiet -WarningAction SilentlyContinue
  Add-Check "kraken_tcp443" ([bool]$tcp) "TCP/443"
} catch {
  Add-Check "kraken_tcp443" $false $_.Exception.Message
}

try {
  $r = Invoke-WebRequest -UseBasicParsing -Uri "https://api.kraken.com/0/public/AssetPairs?pair=XBTEUR" -TimeoutSec 20
  Add-Check "kraken_powershell_https" ($r.StatusCode -eq 200) ("HTTP " + [int]$r.StatusCode)
} catch {
  Add-Check "kraken_powershell_https" $false $_.Exception.Message
}

# Python HTTPS path is the most important local runtime network check.
if (Test-Path $venvPython) {
  try {
    $pyOut = & $venvPython -c "import urllib.request; r=urllib.request.urlopen('https://api.kraken.com/0/public/AssetPairs?pair=XBTEUR',timeout=20); print(r.status)" 2>&1
    $pyCode = $LASTEXITCODE
    Add-Check "kraken_python_https" ($pyCode -eq 0 -and ($pyOut -join " ").Trim() -eq "200") (($pyOut -join " ").Trim())
  } catch {
    Add-Check "kraken_python_https" $false $_.Exception.Message
  }
}

# Backup freshness: alert only after a full week without a successful backup.
$backupDir = Join-Path $TradingRoot "Backup"
$latestBackup = Get-ChildItem $backupDir -File -Filter "minipc-state-*.zip" -ErrorAction SilentlyContinue |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1
if ($latestBackup) {
  $backupAgeDays = [math]::Round((($now - $latestBackup.LastWriteTime).TotalDays),2)
  Add-Check "backup_freshness" ($backupAgeDays -lt 7) ("latest=" + $latestBackup.Name + " age_days=" + $backupAgeDays) "WARNING"
} else {
  $checks["backup_freshness"] = [ordered]@{ ok=$null; detail="no backup yet; warning threshold starts after scheduled backup is installed" }
}

# Continuous public Kraken canary heartbeat is optional until the task is installed.
try {
  $canaryTask = Get-ScheduledTask -TaskName "CryptoMiniPC-KrakenCanary" -ErrorAction SilentlyContinue
  if ($canaryTask) {
    $hb = Join-Path $TradingRoot "State\kraken-canary-heartbeat.json"
    if (-not (Test-Path $hb)) {
      Add-Check "kraken_canary_heartbeat" $false "task installed but heartbeat missing" "WARNING"
    } else {
      $h = Get-Content $hb -Raw | ConvertFrom-Json
      $checked = ([datetime]$h.checked_at_utc).ToUniversalTime()
      $ageSec = [math]::Round(((Get-Date).ToUniversalTime() - $checked).TotalSeconds,1)
      $okStatus = [string]$h.status -in @("HEALTHY","CONNECTED")
      $ok = ($okStatus -and $ageSec -le 30 -and [int]$h.events_total -gt 0)
      Add-Check "kraken_canary_heartbeat" $ok ("status=" + $h.status + " age_sec=" + $ageSec + " events=" + $h.events_total + " gaps=" + $h.gaps) "WARNING"
    }
  } else {
    $checks["kraken_canary_heartbeat"] = [ordered]@{ ok=$null; detail="not installed yet; bounded Kraken smoke remains verified" }
  }
} catch {
  Add-Check "kraken_canary_heartbeat" $false $_.Exception.Message "WARNING"
}

# Broad public Kraken EUR universe feed is optional until installed.
try {
  $universeTask = Get-ScheduledTask -TaskName "CryptoMiniPC-KrakenUniverse" -ErrorAction SilentlyContinue
  if ($universeTask) {
    $hb = Join-Path $TradingRoot "State\kraken-eur-universe-heartbeat.json"
    if (-not (Test-Path $hb)) {
      Add-Check "kraken_universe_heartbeat" $false "task installed but heartbeat missing" "WARNING"
    } else {
      $h = Get-Content $hb -Raw | ConvertFrom-Json
      $ageSec = [math]::Round(((Get-Date).ToUniversalTime() - ([datetime]$h.checked_at_utc).ToUniversalTime()).TotalSeconds,1)
      $okStatus = [string]$h.status -in @("HEALTHY","CONNECTED")
      $ok = (
        $okStatus -and
        $ageSec -le 45 -and
        [int]$h.pair_count -gt 0 -and
        [int]$h.observed_pair_count -gt 0 -and
        [int]$h.subscription_errors -eq 0
      )
      Add-Check "kraken_universe_heartbeat" $ok ("status=" + $h.status + " age_sec=" + $ageSec + " pairs=" + $h.pair_count + " observed=" + $h.observed_pair_count + " coverage=" + $h.coverage_pct + "% reconnects=" + $h.reconnects) "WARNING"
    }
  } else {
    $checks["kraken_universe_heartbeat"] = [ordered]@{ ok=$null; detail="not installed yet; BTC/EUR canary remains the transport-health probe" }
  }
} catch {
  Add-Check "kraken_universe_heartbeat" $false $_.Exception.Message "WARNING"
}

# Altrady transport heartbeat is optional/non-exclusive.
# Only evaluate it when the dedicated scheduled task is installed.
try {
  $altradyTask = Get-ScheduledTask -TaskName "CryptoMiniPC-AltradyTrigger" -ErrorAction SilentlyContinue
  if ($altradyTask) {
    $hb = Join-Path $TradingRoot "State\altrady-trigger-heartbeat.json"
    if (-not (Test-Path $hb)) {
      Add-Check "altrady_trigger_heartbeat" $false "task installed but heartbeat missing" "WARNING"
    } else {
      $h = Get-Content $hb -Raw | ConvertFrom-Json
      $ageSec = [math]::Round(((Get-Date).ToUniversalTime() - ([datetime]$h.checked_at_utc).ToUniversalTime()).TotalSeconds,1)
      $ok = ($h.status -eq "HEALTHY" -and $ageSec -le 60)
      Add-Check "altrady_trigger_heartbeat" $ok ("status=" + $h.status + " age_sec=" + $ageSec + " detail=" + $h.detail) "WARNING"
    }
  } else {
    $checks["altrady_trigger_heartbeat"] = [ordered]@{ ok=$null; detail="not configured; Kraken/GitHub paths remain independent" }
  }
} catch {
  Add-Check "altrady_trigger_heartbeat" $false $_.Exception.Message "WARNING"
}

# Local repo identity. Never pull/checkout/reset from the watchdog.
if (Test-Path $repo) {
  $git = $null
  $gitCandidates = @(
    "C:\Program Files\Git\cmd\git.exe",
    "C:\Program Files\Git\bin\git.exe"
  )
  foreach ($candidate in $gitCandidates) {
    if (Test-Path $candidate) { $git = $candidate; break }
  }
  if (-not $git) {
    try { $git = (Get-Command git -ErrorAction Stop).Source } catch {}
  }

  if ($git) {
    try {
      # The task runs as SYSTEM while the working tree is owned by the local ADMIN user.
      # Use a per-command safe.directory override instead of mutating global Git config.
      $branch = (& $git -c "safe.directory=$repo" -C $repo branch --show-current 2>&1 | Out-String).Trim()
      $head = (& $git -c "safe.directory=$repo" -C $repo log -1 --format=%H 2>&1 | Out-String).Trim()
      $origin = (& $git -c "safe.directory=$repo" -C $repo remote get-url origin 2>&1 | Out-String).Trim()
      Add-Check "git_branch" ($branch -eq "main") ("branch=" + $branch) "WARNING"
      Add-Check "git_origin" ($origin -eq "https://github.com/hoffmannherdecke/kraken-eur-scanner.git") $origin "WARNING"
      Add-Check "git_head" ([bool]$head) $head "WARNING"
    } catch {
      Add-Check "git_repo_check" $false $_.Exception.Message "WARNING"
    }
  } else {
    Add-Check "git_available" $false "git.exe not found for watchdog context" "WARNING"
  }
}

$critical = @($issues | Where-Object { $_.severity -eq "CRITICAL" }).Count
$warning = @($issues | Where-Object { $_.severity -eq "WARNING" }).Count
$status = if ($critical -gt 0) { "CRITICAL" } elseif ($warning -gt 0) { "WARNING" } else { "HEALTHY" }

$report = [ordered]@{
  schema_version = 1
  kind = "MINIPC_LOCAL_HEALTH_V1"
  checked_at_local = $now.ToString("o")
  computer_name = $env:COMPUTERNAME
  trading_root = $TradingRoot
  status = $status
  checks = $checks
  issues = $issues
  guardrails = [ordered]@{
    configuration_changes = $false
    process_restart = $false
    git_mutation = $false
    real_money_actions = $false
  }
}

$json = $report | ConvertTo-Json -Depth 8
$statePath = Join-Path $stateDir "minipc-health.json"
[System.IO.File]::WriteAllText($statePath, $json + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))

$logPath = Join-Path $logDir "minipc-watchdog.log"
$issueCodes = ($issues | ForEach-Object { "$($_.severity):$($_.check)" }) -join ","
$line = "{0} status={1} critical={2} warning={3} issues={4}" -f $now.ToString("o"),$status,$critical,$warning,$issueCodes
Add-Content -Path $logPath -Value $line -Encoding UTF8

Write-Output $json
if ($critical -gt 0) { exit 2 }
exit 0
