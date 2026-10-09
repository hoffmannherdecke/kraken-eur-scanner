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
      $lastEventAgeSec = $null
      if ($h.last_event_at_utc) {
        $lastEventAgeSec = [math]::Round(((Get-Date).ToUniversalTime() - ([datetime]$h.last_event_at_utc).ToUniversalTime()).TotalSeconds,1)
      }
      $ok = (
        $okStatus -and
        $ageSec -le 30 -and
        [int]$h.events_total -gt 0 -and
        $lastEventAgeSec -ne $null -and
        $lastEventAgeSec -le 45
      )
      Add-Check "kraken_canary_heartbeat" $ok ("status=" + $h.status + " age_sec=" + $ageSec + " last_event_age_sec=" + $lastEventAgeSec + " events=" + $h.events_total + " gaps=" + $h.gaps) "WARNING"
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
      $lastTickerAgeSec = $null
      if ($h.last_ticker_at_utc) {
        $lastTickerAgeSec = [math]::Round(((Get-Date).ToUniversalTime() - ([datetime]$h.last_ticker_at_utc).ToUniversalTime()).TotalSeconds,1)
      }
      $ok = (
        $okStatus -and
        $ageSec -le 45 -and
        $lastTickerAgeSec -ne $null -and
        $lastTickerAgeSec -le 45 -and
        [int]$h.pair_count -gt 0 -and
        [int]$h.observed_pair_count -gt 0 -and
        [double]$h.coverage_pct -ge 80.0 -and
        [int]$h.subscription_errors -eq 0
      )
      Add-Check "kraken_universe_heartbeat" $ok ("status=" + $h.status + " age_sec=" + $ageSec + " last_ticker_age_sec=" + $lastTickerAgeSec + " pairs=" + $h.pair_count + " observed=" + $h.observed_pair_count + " coverage=" + $h.coverage_pct + "% reconnects=" + $h.reconnects) "WARNING"
    }
  } else {
    $checks["kraken_universe_heartbeat"] = [ordered]@{ ok=$null; detail="not installed yet; BTC/EUR canary remains the transport-health probe" }
  }
} catch {
  Add-Check "kraken_universe_heartbeat" $false $_.Exception.Message "WARNING"
}

# V2R4 WS shadow heartbeat is optional until the shadow task is installed.
try {
  $shadowTask = Get-ScheduledTask -TaskName "CryptoMiniPC-V2R4WSShadow" -ErrorAction SilentlyContinue
  if ($shadowTask) {
    $hb = Join-Path $TradingRoot "State\v2r4-ws-shadow-heartbeat.json"
    if (-not (Test-Path $hb)) {
      Add-Check "v2r4_ws_shadow_heartbeat" $false "task installed but heartbeat missing" "WARNING"
    } else {
      $h = Get-Content $hb -Raw | ConvertFrom-Json
      $ageSec = [math]::Round(((Get-Date).ToUniversalTime() - ([datetime]$h.checked_at_utc).ToUniversalTime()).TotalSeconds,1)
      $okStatus = [string]$h.status -in @("HEALTHY","DUPLICATE_SKIPPED")
      $processed = [int]$h.counters.snapshots_processed
      $sourceAgeSec = $null
      if ($h.source_age_seconds -ne $null) { $sourceAgeSec = [double]$h.source_age_seconds }
      # Process heartbeat may briefly lag the 1s watcher loop under Windows scheduling/IO.
      # Keep the underlying Kraken source freshness strict (15s), but allow 30s for
      # the watcher heartbeat itself so a fresh feed is not mislabeled FEED_STALE
      # during harmless duplicate-snapshot / scheduler jitter.
      $ok = (
        $okStatus -and
        $ageSec -le 30 -and
        $processed -gt 0 -and
        $sourceAgeSec -ne $null -and
        $sourceAgeSec -le 15
      )
      Add-Check "v2r4_ws_shadow_heartbeat" $ok ("status=" + $h.status + " age_sec=" + $ageSec + " source_age_sec=" + $sourceAgeSec + " snapshots=" + $processed + " events=" + $h.counters.events_emitted + " recovery_epoch=" + $h.recovery_epoch) "WARNING"
    }
  } else {
    $checks["v2r4_ws_shadow_heartbeat"] = [ordered]@{ ok=$null; detail="shadow runtime not installed; V2R3 remains active control" }
  }
} catch {
  Add-Check "v2r4_ws_shadow_heartbeat" $false $_.Exception.Message "WARNING"
}

# V2R4 WS shadow outcome tracker is optional until installed.
try {
  $outcomeTask = Get-ScheduledTask -TaskName "CryptoMiniPC-V2R4ShadowOutcomes" -ErrorAction SilentlyContinue
  if ($outcomeTask) {
    $hb = Join-Path $TradingRoot "State\v2r4-ws-shadow-outcome-heartbeat.json"
    if (-not (Test-Path $hb)) {
      Add-Check "v2r4_ws_shadow_outcomes" $false "task installed but heartbeat missing" "WARNING"
    } else {
      $h = Get-Content $hb -Raw | ConvertFrom-Json
      $ageSec = [math]::Round(((Get-Date).ToUniversalTime() - ([datetime]$h.checked_at_utc).ToUniversalTime()).TotalSeconds,1)
      $activeSamplingOk = $true
      $oldestActiveSampleAgeSec = $null
      $freshestActiveSampleAgeSec = $null
      $recentActiveSamples = 0
      $sampledActiveEvents = 0
      if ([int]$h.active_events -gt 0) {
        $trackerStatePath = Join-Path $TradingRoot "State\v2r4-ws-shadow-outcome-state.json"
        if (-not (Test-Path $trackerStatePath)) {
          $activeSamplingOk = $false
        } else {
          try {
            $trackerState = Get-Content $trackerStatePath -Raw | ConvertFrom-Json
            $sampleAges = @()
            foreach ($prop in $trackerState.active.PSObject.Properties) {
              $sampleAt = $prop.Value.last_sample_at_utc
              if ($sampleAt) {
                $sampleAge = ((Get-Date).ToUniversalTime() - ([datetime]$sampleAt).ToUniversalTime()).TotalSeconds
                $sampleAges += $sampleAge
                $sampledActiveEvents++
                if ($sampleAge -le 240) { $recentActiveSamples++ }
              }
            }
            if ($sampleAges.Count -gt 0) {
              $oldestActiveSampleAgeSec = [math]::Round(($sampleAges | Measure-Object -Maximum).Maximum,1)
              $freshestActiveSampleAgeSec = [math]::Round(($sampleAges | Measure-Object -Minimum).Minimum,1)
              # Individual illiquid pairs may legitimately have no fresh ticker update
              # for several minutes. Core Kraken/WS freshness is checked separately.
              # The outcome tracker is operational if at least one active event is
              # receiving fresh samples; per-event gaps remain preserved in evidence.
              $activeSamplingOk = ($recentActiveSamples -gt 0)
            } else {
              $activeSamplingOk = $false
            }
          } catch {
            $activeSamplingOk = $false
          }
        }
      }
      $ok = (
        $h.status -eq "HEALTHY" -and
        $ageSec -le 30 -and
        $activeSamplingOk -and
        [string]$h.strategy_action -eq "NONE_EVIDENCE_ONLY" -and
        -not [bool]$h.real_money_actions
      )
      Add-Check "v2r4_ws_shadow_outcomes" $ok ("status=" + $h.status + " age_sec=" + $ageSec + " active=" + $h.active_events + " sampled_active=" + $sampledActiveEvents + " recent_active_samples=" + $recentActiveSamples + " freshest_active_sample_age_sec=" + $freshestActiveSampleAgeSec + " oldest_active_sample_age_sec=" + $oldestActiveSampleAgeSec + " enrolled=" + $h.counters.events_enrolled + " completed=" + $h.counters.events_completed) "WARNING"
    }
  } else {
    $checks["v2r4_ws_shadow_outcomes"] = [ordered]@{ ok=$null; detail="prospective outcome tracker not installed yet" }
  }
} catch {
  Add-Check "v2r4_ws_shadow_outcomes" $false $_.Exception.Message "WARNING"
}

# V2R4 shadow cloud archive sync is optional until installed.
try {
  $cloudTask = Get-ScheduledTask -TaskName "CryptoMiniPC-V2R4ShadowCloudSync" -ErrorAction SilentlyContinue
  if ($cloudTask) {
    $hb = Join-Path $TradingRoot "State\v2r4-shadow-cloud-sync-heartbeat.json"
    if (-not (Test-Path $hb)) {
      Add-Check "v2r4_shadow_cloud_sync" $false "task installed but heartbeat missing" "WARNING"
    } else {
      $h = Get-Content $hb -Raw | ConvertFrom-Json
      $ageSec = [math]::Round(((Get-Date).ToUniversalTime() - ([datetime]$h.checked_at_utc).ToUniversalTime()).TotalSeconds,1)
      $ok = (
        $h.status -eq "HEALTHY" -and
        $ageSec -le 180 -and
        [string]$h.strategy_action -eq "NONE_ARCHIVE_ONLY" -and
        -not [bool]$h.real_money_actions
      )
      Add-Check "v2r4_shadow_cloud_sync" $ok ("status=" + $h.status + " age_sec=" + $ageSec + " pending=" + $h.pending_records + " uploaded=" + $h.uploaded_records + " detail=" + $h.detail) "WARNING"
    }
  } else {
    $checks["v2r4_shadow_cloud_sync"] = [ordered]@{ ok=$null; detail="shadow cloud archive sync not installed yet" }
  }
} catch {
  Add-Check "v2r4_shadow_cloud_sync" $false $_.Exception.Message "WARNING"
}

# Active V2R4 Paper local runtime tasks are optional until installed.
$paperRuntimeSpecs = @(
  @{ task="CryptoMiniPC-V2R4PaperCandidates"; check="v2r4_paper_candidates"; hb="v2r4-paper-candidate-runtime-heartbeat.json"; max_age=60 },
  @{ task="CryptoMiniPC-V2R4PaperWait"; check="v2r4_paper_wait"; hb="v2r4-paper-wait-runtime-heartbeat.json"; max_age=30 },
  @{ task="CryptoMiniPC-V2R4PaperLifecycle"; check="v2r4_paper_lifecycle"; hb="v2r4-paper-lifecycle-heartbeat.json"; max_age=180 },
  @{ task="CryptoMiniPC-V2R4PaperCloudSync"; check="v2r4_paper_cloud_sync"; hb="v2r4-paper-cloud-sync-heartbeat.json"; max_age=180 }
)
foreach ($spec in $paperRuntimeSpecs) {
  try {
    $task = Get-ScheduledTask -TaskName $spec.task -ErrorAction SilentlyContinue
    if ($task) {
      $hb = Join-Path $TradingRoot ("State\" + $spec.hb)
      if (-not (Test-Path $hb)) {
        Add-Check $spec.check $false "task installed but heartbeat missing" "WARNING"
      } else {
        $h = Get-Content $hb -Raw | ConvertFrom-Json
        $ageSec = [math]::Round(((Get-Date).ToUniversalTime() - ([datetime]$h.checked_at_utc).ToUniversalTime()).TotalSeconds,1)
        $safe = (
          $h.status -eq "HEALTHY" -and
          $ageSec -le [double]$spec.max_age -and
          -not [bool]$h.order_api -and
          -not [bool]$h.real_money_actions
        )
        Add-Check $spec.check $safe ("status=" + $h.status + " age_sec=" + $ageSec + " task_state=" + $task.State) "WARNING"
      }
    } else {
      $checks[$spec.check] = [ordered]@{ ok=$null; detail="V2R4 Paper task not installed yet" }
    }
  } catch {
    Add-Check $spec.check $false $_.Exception.Message "WARNING"
  }
}

# V3 H3 shadow is observational only: monitor it without making V2R4 trading safety depend on it.
try {
  $h3Task = Get-ScheduledTask -TaskName "CryptoMiniPC-V3H3Shadow001" -ErrorAction SilentlyContinue
  if ($h3Task) {
    $retiredPath=Join-Path $TradingRoot 'State\v2r4-technical-cutover-completed.json'
    $retiredOk=$false
    if(Test-Path -LiteralPath $retiredPath){
      try {
        $r=Get-Content $retiredPath -Raw | ConvertFrom-Json
        $retiredOk=($r.kind -eq 'V2R4_TECHNICAL_CUTOVER_COMPLETED_V1' -and
          $r.predecessor_series_id -eq 'PAPER-V2R4-20261007T184255Z' -and
          [string]$r.successor_series_id -match '^PAPER-V2R4-[0-9]{8}T[0-9]{6}Z$' -and
          $r.h3_001_retired -eq $true -and
          $r.real_money_actions -eq $false -and
          [string]$h3Task.State -eq 'Disabled')
      } catch { $retiredOk=$false }
    }
    if($retiredOk){
      Add-Check 'v3_h3_shadow' $true 'ARCHIVED_001_FROZEN_ORIGINAL_BASELINE_NO_REBIND' 'WARNING'
    } else {
    $hb = Join-Path $TradingRoot "State\v3-h3-shadow-001-heartbeat.json"
    if (-not (Test-Path $hb)) {
      Add-Check "v3_h3_shadow" $false "task installed but heartbeat missing" "WARNING"
    } else {
      $h = Get-Content $hb -Raw | ConvertFrom-Json
      $checked = [datetimeoffset]::Parse([string]$h.checked_at_utc)
      $ageSec = [math]::Round(([datetimeoffset]::UtcNow - $checked).TotalSeconds,1)
      $ok = (
        $h.status -eq "HEALTHY" -and
        $h.runtime_ready -eq $true -and
        $ageSec -le 30 -and
        [string]$h3Task.State -eq "Running"
      )
      Add-Check "v3_h3_shadow" $ok ("status=" + $h.status + " age_sec=" + $ageSec + " task_state=" + $h3Task.State + " cloud_sync=" + $h.cloud_sync_status) "WARNING"
    }

    }
  } else {
    $checks["v3_h3_shadow"] = [ordered]@{ ok=$null; detail="H3 shadow task not installed" }
  }
} catch {
  Add-Check "v3_h3_shadow" $false $_.Exception.Message "WARNING"
}

# Local bounded runtime supervisor is optional until installed.
try {
  $supervisorTask = Get-ScheduledTask -TaskName "CryptoMiniPC-RuntimeSupervisor" -ErrorAction SilentlyContinue
  if ($supervisorTask) {
    $sp = Join-Path $TradingRoot "State\minipc-runtime-supervisor.json"
    if (-not (Test-Path $sp)) {
      Add-Check "runtime_supervisor" $false "task installed but state missing" "WARNING"
    } else {
      $s = Get-Content $sp -Raw | ConvertFrom-Json
      $checked = ([datetime]$s.checked_at_utc).ToUniversalTime()
      $ageSec = [math]::Round(((Get-Date).ToUniversalTime() - $checked).TotalSeconds,1)
      $ok = (
        $s.status -eq "HEALTHY" -and
        $ageSec -le 300 -and
        -not [bool]$s.guardrails.real_money_actions
      )
      Add-Check "runtime_supervisor" $ok ("status=" + $s.status + " age_sec=" + $ageSec + " restarted=" + (($s.restarted | ForEach-Object { $_ }) -join ",")) "WARNING"
    }
  } else {
    $checks["runtime_supervisor"] = [ordered]@{ ok=$null; detail="bounded runtime supervisor not installed yet" }
  }
} catch {
  Add-Check "runtime_supervisor" $false $_.Exception.Message "WARNING"
}

# MINI-PC remote status sync is optional until installed.
try {
  $statusTask = Get-ScheduledTask -TaskName "CryptoMiniPC-StatusSync" -ErrorAction SilentlyContinue
  if ($statusTask) {
    $hb = Join-Path $TradingRoot "State\minipc-status-sync-heartbeat.json"
    if (-not (Test-Path $hb)) {
      Add-Check "minipc_status_sync" $false "task installed but heartbeat missing" "WARNING"
    } else {
      $h = Get-Content $hb -Raw | ConvertFrom-Json
      $ageSec = [math]::Round(((Get-Date).ToUniversalTime() - ([datetime]$h.checked_at_utc).ToUniversalTime()).TotalSeconds,1)
      $ok = (
        $h.status -eq "HEALTHY" -and
        $ageSec -le 900 -and
        [string]$h.strategy_action -eq "NONE_STATUS_ONLY" -and
        -not [bool]$h.real_money_actions
      )
      Add-Check "minipc_status_sync" $ok ("status=" + $h.status + " age_sec=" + $ageSec + " uploaded_health_status=" + $h.uploaded_health_status + " detail=" + $h.detail) "WARNING"
    }
  } else {
    $checks["minipc_status_sync"] = [ordered]@{ ok=$null; detail="remote status sync not installed yet" }
  }
} catch {
  Add-Check "minipc_status_sync" $false $_.Exception.Message "WARNING"
}

# Local GitHub scanner-cadence recovery guard is optional until installed.
# It is a periodic one-shot task, so Ready is normal; health is heartbeat-based.
try {
  $cadenceTask = Get-ScheduledTask -TaskName "CryptoMiniPC-GitHubCadenceGuard" -ErrorAction SilentlyContinue
  if ($cadenceTask) {
    $hb = Join-Path $TradingRoot "State\github-cadence-guard.json"
    if (-not (Test-Path $hb)) {
      Add-Check "github_cadence_guard" $false "task installed but heartbeat missing" "WARNING"
    } else {
      $h = Get-Content $hb -Raw | ConvertFrom-Json
      $ageSec = [math]::Round(((Get-Date).ToUniversalTime() - ([datetime]$h.checked_at_utc).ToUniversalTime()).TotalSeconds,1)
      $safe = (
        [bool]$h.guardrails.recovery_only -and
        -not [bool]$h.guardrails.strategy_changes -and
        -not [bool]$h.guardrails.threshold_changes -and
        -not [bool]$h.guardrails.evaluator_invoked_directly -and
        -not [bool]$h.guardrails.order_api -and
        -not [bool]$h.guardrails.real_money_actions
      )
      $ok = (
        $h.status -eq "HEALTHY" -and
        $ageSec -le 600 -and
        [string]$cadenceTask.State -ne "Disabled" -and
        $safe
      )
      Add-Check "github_cadence_guard" $ok ("status=" + $h.status + " age_sec=" + $ageSec + " task_state=" + $cadenceTask.State + " action=" + $h.action + " latest_scan_age_sec=" + $h.latest_scan_run.age_seconds + " detail=" + $h.detail) "WARNING"
    }
  } else {
    $checks["github_cadence_guard"] = [ordered]@{ ok=$null; detail="not installed yet; GitHub cloud schedule + process-health recovery remain active" }
  }
} catch {
  Add-Check "github_cadence_guard" $false $_.Exception.Message "WARNING"
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

# Human-readable operational taxonomy. This is intentionally separate from the
# coarse HEALTHY/WARNING/CRITICAL status so dashboards/alerts can distinguish
# transport loss from stale data or a merely degraded support component.
$issueNames = @($issues | ForEach-Object { [string]$_.check })
$healthState = "OK"
$stateReasonCodes = @()

if ($critical -gt 0) {
  $healthState = "STOPPED"
  $stateReasonCodes = @($issueNames)
} elseif (@($issueNames | Where-Object { $_ -in @("kraken_dns","kraken_tcp443","kraken_powershell_https","kraken_python_https") }).Count -gt 0) {
  $healthState = "API_DISCONNECTED"
  $stateReasonCodes = @($issueNames)
} elseif (@($issueNames | Where-Object { $_ -in @("kraken_canary_heartbeat","kraken_universe_heartbeat") }).Count -gt 0) {
  # Only underlying Kraken transport/source failures are FEED_STALE.
  # Shadow/outcome support-process issues are DEGRADED while the source feed is healthy.
  $healthState = "FEED_STALE"
  $stateReasonCodes = @($issueNames)
} elseif (@($issueNames | Where-Object { $_ -match "queue|backlog" }).Count -gt 0) {
  $healthState = "BACKLOG_STUCK"
  $stateReasonCodes = @($issueNames)
} elseif ($warning -gt 0) {
  $healthState = "DEGRADED"
  $stateReasonCodes = @($issueNames)
} else {
  # If the core runtime stack has not been installed yet, report WAITING_NO_DATA
  # instead of claiming a fully operational OK state.
  $coreOptional = @(
    $checks["kraken_canary_heartbeat"],
    $checks["kraken_universe_heartbeat"],
    $checks["v2r4_ws_shadow_heartbeat"]
  )
  $installedCoreCount = @($coreOptional | Where-Object { $_ -and $_.ok -ne $null }).Count
  if ($installedCoreCount -eq 0) {
    $healthState = "WAITING_NO_DATA"
    $stateReasonCodes = @("core_runtime_not_installed")
  }
}

$report = [ordered]@{
  schema_version = 1
  kind = "MINIPC_LOCAL_HEALTH_V1"
  checked_at_local = $now.ToString("o")
  computer_name = $env:COMPUTERNAME
  trading_root = $TradingRoot
  status = $status
  health_state = $healthState
  state_reason_codes = @($stateReasonCodes)
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
$line = "{0} status={1} health_state={2} critical={3} warning={4} issues={5}" -f $now.ToString("o"),$status,$healthState,$critical,$warning,$issueCodes
Add-Content -Path $logPath -Value $line -Encoding UTF8

Write-Output $json
if ($critical -gt 0) { exit 2 }
exit 0
