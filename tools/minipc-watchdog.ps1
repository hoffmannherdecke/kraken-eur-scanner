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

# Read-only Windows Task Scheduler observations; diagnostic only.
# Never promote a task return code to strategy/release health or restart a task.
# No actions, task arguments, paths, secrets, usernames, or PIDs are exported.
$nativeTaskReadback = [ordered]@{}
function Add-NativeTaskReadback {
  param([string]$Key, $Task)

  $entry = [ordered]@{
    task_state = "NOT_INSTALLED"
    last_result_code = $null
    last_result_meaning = "UNAVAILABLE"
  }
  if ($null -ne $Task) {
    $entry.task_state = [string]$Task.State
    try {
      $taskInfo = Get-ScheduledTaskInfo -TaskName ([string]$Task.TaskName) -TaskPath ([string]$Task.TaskPath) -ErrorAction Stop
      if ($null -ne $taskInfo -and $null -ne $taskInfo.LastTaskResult) {
        $value = [long]$taskInfo.LastTaskResult
        $entry.last_result_code = $value
        if ($value -eq 0) {
          $entry.last_result_meaning = "ZERO_RESULT_NOT_RUNTIME_PROOF"
        } elseif ($value -eq 267009) {
          # 0x41301 means "task is running", not automatically "task failed".
          # A mismatch with its independently observed Task.State remains unknown.
          if ([string]$Task.State -eq "Running") {
            $entry.last_result_meaning = "RUNNING_CODE_AND_STATE_MATCH"
          } else {
            $entry.last_result_meaning = "RUNNING_CODE_STATE_MISMATCH"
          }
        } else {
          $entry.last_result_meaning = "OTHER_RESULT_REVIEW_REQUIRED"
        }
      }
    } catch {
      # Native scheduler metadata is optional: never break the watchdog
      # or change an existing Paper/V3 health decision if this read fails.
      $entry.last_result_meaning = "UNAVAILABLE"
    }
  }
  $nativeTaskReadback[$Key] = $entry
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

# Read-only successor diagnostics. A committed local fence retires old
# intake, not historical aftercare. Never start or change a task here.
$paperSuccessorObservation=$null
$v3CommittedFence=$false
try {
  $fencePath=Join-Path $stateDir "v3-experimental-paper-old-intake-fence.json"
  if(Test-Path -LiteralPath $fencePath){
    $fence=Get-Content -LiteralPath $fencePath -Raw | ConvertFrom-Json
    $v3CommittedFence=(
      $fence.kind -ceq "V3_EXPERIMENTAL_OLD_INTAKE_FENCE_V1" -and
      $fence.phase -ceq "CLOUD_COMMITTED" -and
      [string]$fence.proposed_successor_series_id -cmatch '^PAPER-V3-[0-9]{8}T[0-9]{6}Z$' -and
      [string]$fence.proposed_v3_repo_sha -cmatch '^[0-9a-f]{40}$' -and
      [string]$fence.proposed_v3_bundle_sha256 -cmatch '^[0-9a-f]{64}$' -and
      [string]$fence.proposed_v3_strategy_sha256 -cmatch '^[0-9a-f]{64}$' -and
      $fence.successor_task_name -ceq "CryptoMiniPC-V3PaperSingleWriter" -and
      $fence.paper_only -eq $true -and $fence.orders_enabled -eq $false -and
      $fence.real_money_actions -eq $false -and $fence.persistent_until_explicit_owner_release -eq $true -and
      ((@($fence.task_names | Sort-Object) -join '|') -ceq 'CryptoMiniPC-V2R4PaperCandidates|CryptoMiniPC-V2R4PaperWait')
    )
    if($v3CommittedFence){
      $v3Task=Get-ScheduledTask -TaskName "CryptoMiniPC-V3PaperSingleWriter" -ErrorAction SilentlyContinue
      Add-NativeTaskReadback -Key "v3_paper_single_writer" -Task $v3Task
      $hbPath=Join-Path $stateDir "v3-paper-single-writer-heartbeat.json"
      if(-not (Test-Path -LiteralPath $hbPath)){ throw "V3 successor heartbeat missing" }
      $h=Get-Content -LiteralPath $hbPath -Raw | ConvertFrom-Json
      $stamp=([datetimeoffset]::Parse([string]$h.checked_at_utc)).UtcDateTime
      $unbounded=($h.PSObject.Properties['runtime_scope'] -and
        $h.runtime_scope -ceq 'V3_PAPER_RUNTIME_UNTIL_REVOKED' -and
        $h.PSObject.Properties['expires_at_utc'] -and $null -eq $h.expires_at_utc)
      $expiry=if(-not $unbounded){([datetimeoffset]::Parse([string]$h.expires_at_utc)).UtcDateTime}
      $age=([datetime]::UtcNow-$stamp).TotalSeconds
      $writerPresent=$false
      if([string]$h.pid -match '^[1-9][0-9]*$'){
        $writerPresent=$null -ne (Get-Process -Id ([int]$h.pid) -ErrorAction SilentlyContinue)
      }
      $writerBound=($null -ne $v3Task -and [string]$v3Task.State -ceq "Running" -and
           $h.kind -ceq "V3_PAPER_SINGLE_WRITER_HEARTBEAT_V1" -and
           $h.series_id -ceq [string]$fence.proposed_successor_series_id -and
           [string]$h.release_repo_sha -ceq [string]$fence.proposed_v3_repo_sha -and
           [string]$h.runtime_bundle_sha256 -ceq [string]$fence.proposed_v3_bundle_sha256 -and
           [string]$h.strategy_sha256 -ceq [string]$fence.proposed_v3_strategy_sha256 -and
           [string]$h.runtime_approval_sha256 -cmatch '^[0-9a-f]{64}$' -and
           $h.paper_only -eq $true -and $h.orders -eq $false -and $h.real_money_actions -eq $false -and
           $writerPresent -and ($unbounded -or $expiry -gt [datetime]::UtcNow) -and
           $age -ge -30 -and $age -le 180)
      $ok=($writerBound -and $h.status -ceq "HEALTHY")
      $level=$null
      if($writerBound -and ($h.PSObject.Properties["operating_level"] -and
          ($h.operating_level -is [int] -or $h.operating_level -is [long]))){
        if($h.status -ceq "HEALTHY" -and $h.operating_level -in @(1,2)){
          $level=$h.operating_level
        } elseif($h.operating_level -eq 3 -and $h.status -cin @(
            "DEGRADED_SCANNER_INPUT","DEGRADED_CLOUD_READ","DEGRADED_CLOUD_ACK",
            "DEGRADED_AUTHORITY_READ","DEGRADED_FOLLOWUP_SOURCE")){
          $level=3
        }
      }
      # AP06B heartbeat has no strategy_revision. Relay its existing pins,
      # never the PID, runtime arguments or paths.
      $paperSuccessorObservation=[ordered]@{
        series_id=[string]$h.series_id
        release_repo_sha=[string]$h.release_repo_sha
        runtime_bundle_sha256=[string]$h.runtime_bundle_sha256
        strategy_sha256=[string]$h.strategy_sha256
        observed_at_utc=$stamp.ToString("o")
        expires_at_utc=$(if(-not $unbounded){$expiry.ToString("o")})
        host_report_only=$true
        independent_runtime_proof=$false
      }
      if($unbounded){$paperSuccessorObservation.runtime_scope="V3_PAPER_RUNTIME_UNTIL_REVOKED"}
      $writerDetail="local task/process/heartbeat match="+$ok+" age_sec="+[math]::Round($age,1)
      if($null -ne $level){$writerDetail+=" operating_level="+$level}
      Add-Check "v3_paper_single_writer" $ok $writerDetail "WARNING"
      if ($h.kind -ceq "V3_PAPER_SINGLE_WRITER_HEARTBEAT_V1" -and $h.status -ceq "HOLD" -and
          $h.series_id -ceq $fence.proposed_successor_series_id -and
          $h.release_repo_sha -ceq $fence.proposed_v3_repo_sha -and
          $h.runtime_bundle_sha256 -ceq $fence.proposed_v3_bundle_sha256 -and
          $h.strategy_sha256 -ceq $fence.proposed_v3_strategy_sha256 -and
          $age -ge -30 -and $age -le 180 -and
          [string]$h.cycle_status -cmatch '^HOLD_[A-Z0-9_]{1,100}$') {
        $diagnosis = [ordered]@{
          series_id = [string]$h.series_id
          release_repo_sha = [string]$h.release_repo_sha
          runtime_bundle_sha256 = [string]$h.runtime_bundle_sha256
          strategy_sha256 = [string]$h.strategy_sha256
          checked_at_utc = $stamp.ToString("o")
          cycle_status = [string]$h.cycle_status
        }
        $site = $h.failure_site
        if ([string]$site.file -cmatch '^[A-Za-z0-9_]{1,120}\.py$' -and
            [string]$site.function -cmatch '^[A-Za-z0-9_]{1,100}$' -and
            $site.line -is [int] -and $site.line -gt 0) {
          $diagnosis.failure_site = @{file=$site.file; function=$site.function; line=$site.line}
        }
        $detail = $h.failure_detail
        if ($detail.kind -ceq "ORIGINALHOST_READBACK_FAILURE_V1" -and
            $detail.category -cin @("POWERSHELL_ERROR_OUTPUT_UNAVAILABLE","POWERSHELL_EXECUTION_ERROR","POWERSHELL_MULTIPLE_FIXED_CODES","POWERSHELL_OUTPUT_DECODING_ERROR","POWERSHELL_REPORTED_FIXED_CODE","POWERSHELL_REPORT_JSON_HOLD","POWERSHELL_REPORT_OBJECT_HOLD","POWERSHELL_REPORT_SIZE_HOLD","POWERSHELL_TIMEOUT","POWERSHELL_UNCLASSIFIED_ERROR")) {
          $safeDetail = [ordered]@{kind=$detail.kind; category=$detail.category}
          if (($detail.returncode -is [int] -or $detail.returncode -is [long]) -and
              $detail.returncode -ge -2147483648 -and $detail.returncode -le 4294967295) {
            $safeDetail.returncode = $detail.returncode
          }
          if ($detail.category -ceq "POWERSHELL_REPORTED_FIXED_CODE" -and
              $detail.reported_code -cin @(
            "V3_ARMED_TWO_CYCLE_AFTERCARE_NOT_RUNNING",
            "V3_ARMED_TWO_CYCLE_BACKUP_OR_PR515_MISMATCH",
            "V3_ARMED_TWO_CYCLE_FENCE_CHANGED",
            "V3_ARMED_TWO_CYCLE_FENCE_UNSAFE",
            "V3_ARMED_TWO_CYCLE_FINAL_FENCE_CHANGED",
            "V3_ARMED_TWO_CYCLE_FINAL_PR515_SOURCE_CHANGED",
            "V3_ARMED_TWO_CYCLE_FOREIGN_FENCE",
            "V3_ARMED_TWO_CYCLE_FUTURE_READBACK",
            "V3_ARMED_TWO_CYCLE_OLD_INTAKE_REARMED",
            "V3_ARMED_TWO_CYCLE_ORIGINALHOST_OR_PINS_INVALID",
            "V3_ARMED_TWO_CYCLE_ORIGINAL_WINDOWS_REQUIRED",
            "V3_ARMED_TWO_CYCLE_SEMANTICS_FAIL",
            "V3_ARMED_TWO_CYCLE_TIMEOUT_HOLD",
            "V3_ARMED_TWO_CYCLE_TIMESTAMP_INVALID",
            "V3_EXCLUSIVE_ARCHIVE_ACL_NOT_PROTECTED",
            "V3_EXCLUSIVE_ARCHIVE_FOREIGN_WRITER",
            "V3_EXCLUSIVE_ARCHIVE_PATH_SCOPE_HOLD",
            "V3_EXCLUSIVE_ARCHIVE_TARGET_EXISTS",
            "V3_EXCLUSIVE_ARCHIVE_UNSAFE_SOURCE",
            "V3_EXCLUSIVE_ARCHIVE_WRONG_HOST_OR_HASH",
            "V3_FORWARD_T0_DUPLICATE_FIELD",
            "V3_FORWARD_T0_NONZERO_OR_WRONG_TYPE",
            "V3_FORWARD_T0_OLD_ONLY_DRIFT",
            "V3_FORWARD_T0_SCHEMA_DRIFT",
            "V3_FORWARD_T0_STALE_OR_ACTOR_DRIFT",
            "V3_FORWARD_T0_UNSAFE_AUTHORITY_FLAG",
            "V3_FORWARD_T0_UTC_FORMAT",
            "V3_FORWARD_T0_UTC_INVALID",
            "V3_GATEB_COORDINATED_ARCHIVE_HOLD",
            "V3_GATEB_COORDINATED_ARCHIVE_TIME_HOLD",
            "V3_GATEB_COORDINATED_ENVELOPE_CMS_HOLD",
            "V3_GATEB_COORDINATED_ENVELOPE_ENCODING_HOLD",
            "V3_GATEB_COORDINATED_ENVELOPE_IDENTITY_HOLD",
            "V3_GATEB_COORDINATED_ENVELOPE_SIZE_HOLD",
            "V3_GATEB_COORDINATED_ENVELOPE_STALE_HOLD",
            "V3_GATEB_COORDINATED_PARTIAL_INPUT_HOLD",
            "V3_GATEB_COORDINATED_REQUEST_EXISTS_HOLD",
            "V3_GATEB_COORDINATED_SCOPE_HOLD",
            "V3_GATE_A_BINDINGS_HOLD",
            "V3_GATE_A_EXISTING_ISSUER_SECRET_HOLD",
            "V3_GATE_A_FRESH_ISSUER_READER_HOLD",
            "V3_GATE_A_HASH_BINDING_HOLD",
            "V3_GATE_A_INDEPENDENT_NOTEBOOK_REQUIRED",
            "V3_GATE_A_INDEPENDENT_READBACK_HOLD_NO_RETRY",
            "V3_GATE_A_ORIGINAL_RECEIPT_HOLD",
            "V3_GATE_A_SQL_EPOCH_HOLD",
            "V3_GATE_A_SQL_HASH_HOLD",
            "V3_INTAKE_LEASE_PAIR_EXACT_TWO_DISTINCT_REQUIRED",
            "V3_INTAKE_LEASE_PAIR_HANDLE_CLOSED",
            "V3_INTAKE_LEASE_PAIR_ORIGINAL_SCOPE_HOLD",
            "V3_INTAKE_LEASE_PAIR_SANDBOX_SCOPE_HOLD",
            "V3_ISSUER_BOUND_NATIVE_RESTORE_ARMED_FENCE_OR_V3_STATE_HOLD",
            "V3_ISSUER_BOUND_NATIVE_RESTORE_HELD_PAIR_HOLD",
            "V3_ISSUER_BOUND_NATIVE_RESTORE_PRODUCTION_RELEASE_HOLD",
            "V3_ISSUER_BOUND_NATIVE_RESTORE_PROTECTED_AFTERCARE_HOLD",
            "V3_ISSUER_BOUND_NATIVE_RESTORE_TASK_NOT_DISABLED",
            "V3_ISSUER_BOUND_NATIVE_RESTORE_TERMINAL_ABORT_HOLD",
            "V3_ISSUER_BOUND_NATIVE_STOP_CURRENT_TASK_IDENTITY_HOLD",
            "V3_ISSUER_BOUND_NATIVE_STOP_FENCE_OR_V3_STATE_HOLD",
            "V3_ISSUER_BOUND_NATIVE_STOP_PRODUCTION_RELEASE_HOLD",
            "V3_ISSUER_BOUND_NATIVE_STOP_PROTECTED_SCOPE_HOLD",
            "V3_ISSUER_BOUND_NATIVE_STOP_SIGNATURE_OR_PIN_HOLD",
            "V3_MARKER_CANCEL_ARCHIVE_EXISTS_OR_FENCE_DRIFT",
            "V3_MARKER_CANCEL_ATOMIC_RENAME_PHYSICAL_ANTIRACE_GATE_NOT_WIRED",
            "V3_MARKER_CANCEL_BAD_HOST_OR_RELEASE_PINS",
            "V3_MARKER_CANCEL_FENCE_CHANGED",
            "V3_MARKER_CANCEL_FOREIGN_MAINTENANCE",
            "V3_MARKER_CANCEL_INDEPENDENT_CLOUD_OR_UNKNOWN_CUSTODY_HOLD",
            "V3_MARKER_CANCEL_INVALID_FENCE_FILE",
            "V3_MARKER_CANCEL_NOT_EXACT_PRESTOP_ARMED",
            "V3_MARKER_CANCEL_ORIGINALHOST_ADMIN_REQUIRED",
            "V3_MARKER_CANCEL_ORIGINALHOST_WINDOWS_REQUIRED",
            "V3_MARKER_CANCEL_POST_EPOCH_CANNOT_USE_PRE_EPOCH_SNAPSHOT",
            "V3_MARKER_CANCEL_POST_EPOCH_ID_INVALID",
            "V3_MARKER_CANCEL_POST_RENAME_READBACK_HOLD_PRESERVE_ARCHIVE",
            "V3_MARKER_CANCEL_PRE_EPOCH_CANNOT_USE_POST_EPOCH_ABORT",
            "V3_MARKER_CANCEL_PRE_EPOCH_EPOCH_ID_FORBIDDEN",
            "V3_MARKER_CANCEL_PRE_EPOCH_INDEPENDENT_CUSTODY_AND_ANTIRACE_HOLD",
            "V3_MARKER_CANCEL_PRE_EPOCH_PHYSICAL_ARCHIVE_NOT_RELEASED",
            "V3_MARKER_CANCEL_PRE_EPOCH_SIGNED_T0_OR_CLOUD_MISMATCH",
            "V3_MARKER_CANCEL_SIGNED_TERMINAL_ABORT_MISMATCH",
            "V3_MARKER_CANCEL_V2R4_ORIGINAL_TASK_STATE_CHANGED",
            "V3_MARKER_CANCEL_V3_TASK_NOT_DISABLED",
            "V3_NATIVE_SOURCE_ONLY_ORIGINAL_WINDOWS_REQUIRED",
            "V3_NOTEBOOK_READER_AUTHENTICATED_INVENTORY_MISMATCH",
            "V3_NOTEBOOK_READER_EXTRA_FIELDS",
            "V3_NOTEBOOK_READER_MISSING_OR_DUPLICATE_FIELD",
            "V3_NOTEBOOK_READER_TIMESTAMP_INVALID",
            "V3_NOTEBOOK_READER_TIMESTAMP_UNPARSEABLE",
            "V3_PAPER_ABANDONED_OPERATOR_HOLD",
            "V3_PAPER_ACTIVATION_REPEATED_RUNTIME_REQUIRED",
            "V3_PAPER_ACTIVATION_REQUEST_DRIFT",
            "V3_PAPER_ACTIVATION_RUNTIME_BINDING_HOLD",
            "V3_PAPER_ACTIVATION_RUNTIME_START_BYTES_HOLD",
            "V3_PAPER_ACTUAL_NATIVE_TASK_PROCESS_SOURCE_HOLD",
            "V3_PAPER_AFTERCARE_MUST_REMAIN_RUNNING",
            "V3_PAPER_AUTHORIZATION_EXPIRED_FENCE_PRESERVED",
            "V3_PAPER_BOOTSTRAP_ARGUMENT_HOLD",
            "V3_PAPER_BOOTSTRAP_DESTINATION_HOLD",
            "V3_PAPER_BOOTSTRAP_LOCAL_TRADING_PATH_REQUIRED",
            "V3_PAPER_CAS_AUDIT_ID_HOLD",
            "V3_PAPER_CAS_AUDIT_PIN_HOLD",
            "V3_PAPER_CAS_DEADLINE_HOLD",
            "V3_PAPER_CAS_EXACT_16_ARGUMENTS_REQUIRED",
            "V3_PAPER_CAS_INDEPENDENT_REQUEST_DRIFT",
            "V3_PAPER_CAS_INSTALL_READER_HOLD",
            "V3_PAPER_CAS_ORIGINAL_INSTALL_SEAM_DRIFT",
            "V3_PAPER_CAS_RESULT_UNKNOWN_NO_RETRY",
            "V3_PAPER_CAS_RUNTIME_BINDING_HOLD",
            "V3_PAPER_COMMITTED_INDEPENDENT_READER_REQUIRED",
            "V3_PAPER_COMPETING_NATIVE_WRITER_HOLD",
            "V3_PAPER_CONCURRENT_OPERATOR_HOLD",
            "V3_PAPER_CURRENT_SUPERVISOR_NO_REARM_ACK_REQUIRED",
            "V3_PAPER_EXACT_EXISTING_TASK_SET_REQUIRED",
            "V3_PAPER_EXISTING_ADMIN_CREDENTIAL_REQUIRED",
            "V3_PAPER_EXISTING_EXECUTOR_CREDENTIAL_REQUIRED",
            "V3_PAPER_FENCE_ACL_HOLD",
            "V3_PAPER_FENCE_FOREIGN_WRITER_HOLD",
            "V3_PAPER_FOLLOWUP_PLAN_EPOCH_PINS_HOLD",
            "V3_PAPER_FOLLOWUP_PREPARED_FENCE_DRIFT",
            "V3_PAPER_FOLLOWUP_READER_EPOCH_DRIFT",
            "V3_PAPER_FOLLOWUP_READER_KIND_HOLD",
            "V3_PAPER_FOLLOWUP_SEAL_ORIGINAL_STOP_DRIFT",
            "V3_PAPER_FOLLOWUP_SEAL_READER_OR_FENCE_HOLD",
            "V3_PAPER_HOST_RECEIPT_KIND_HOLD",
            "V3_PAPER_INDEPENDENT_CURRENT_RECEIPT_HOLD",
            "V3_PAPER_INDEPENDENT_READER_PIN_REQUIRED",
            "V3_PAPER_INDEPENDENT_RECEIPT_BYTES_DRIFT",
            "V3_PAPER_NATIVE_SYSTEM_TASK_REQUIRED",
            "V3_PAPER_NATIVE_TASK_SCOPE_HOLD",
            "V3_PAPER_OLD_INTAKE_NOT_DISABLED",
            "V3_PAPER_OLD_PROCESS_REMAINS",
            "V3_PAPER_OPEN_EPOCH_EXISTING_FENCE_ATTEMPT_OR_WRITER_HOLD",
            "V3_PAPER_ORIGINALHOST_REQUIRED",
            "V3_PAPER_ORIGINAL_FENCE_IDENTITY_HOLD",
            "V3_PAPER_ORIGINAL_PROCESS_SET_REQUIRED",
            "V3_PAPER_ORIGINAL_TASK_XML_DRIFT",
            "V3_PAPER_PINNED_BYTES_HOLD",
            "V3_PAPER_PINNED_STAGE_REQUIRED",
            "V3_PAPER_PLAN_IDENTITY_HOLD",
            "V3_PAPER_POST_START_HEALTH_READBACK_HOLD_NO_RETRY",
            "V3_PAPER_PRECAS_INDEPENDENT_READER_HOLD",
            "V3_PAPER_PRECAS_ROLLBACK_V3_WRITER_NOT_DISABLED",
            "V3_PAPER_PREPARE_DISABLED_ACK_REQUIRED",
            "V3_PAPER_PREPARE_EXISTING_FENCE_OR_UNSAFE_READER_HOLD",
            "V3_PAPER_PREPARE_WRITER_MUST_BE_DISABLED",
            "V3_PAPER_PRESTOP_FENCE_EPOCH_DRIFT",
            "V3_PAPER_PRESTOP_INDEPENDENT_INHIBIT_REQUIRED",
            "V3_PAPER_PRESTOP_ROLLBACK_FENCE_DRIFT",
            "V3_PAPER_PRESTOP_ROLLBACK_ORIGINAL_INTAKE_NOT_RUNNING",
            "V3_PAPER_PRESTOP_ROLLBACK_V3_WRITER_NOT_DISABLED",
            "V3_PAPER_PROCESS_ACTION_AMBIGUOUS",
            "V3_PAPER_PROCESS_BIRTH_OR_COMMAND_DRIFT",
            "V3_PAPER_PROCESS_IDENTITY_HOLD",
            "V3_PAPER_RELEASE_COMMIT_REQUIRED",
            "V3_PAPER_REPLACEMENT_INTAKE_PROCESS_HOLD",
            "V3_PAPER_RESTORE_ARCHIVE_COLLISION_PRESERVE_FENCE",
            "V3_PAPER_RESTORE_ARMED_FENCE_DRIFT",
            "V3_PAPER_RESTORE_HEARTBEATS_MISSING_PRESERVE_FENCE",
            "V3_PAPER_REVIEWED_DISABLED_NATIVE_ACTION_REQUIRED",
            "V3_PAPER_ROLLBACK_INDEPENDENT_TERMINAL_ABORT_REQUIRED",
            "V3_PAPER_RUNTIME_ACTIVATION_BINDING_HOLD",
            "V3_PAPER_RUNTIME_SCOPE_DRIFT",
            "V3_PAPER_RUNTIME_SPEC_BINDING_HOLD",
            "V3_PAPER_RUNTIME_START_CAS_BINDING_HOLD",
            "V3_PAPER_RUNTIME_START_CLOUD_RECEIPT_HOLD",
            "V3_PAPER_RUNTIME_START_MAINTENANCE_HOLD",
            "V3_PAPER_RUNTIME_START_OBSERVATION_WINDOW_HOLD",
            "V3_PAPER_RUNTIME_START_ORIGINAL_PROOF_HOLD",
            "V3_PAPER_RUNTIME_START_PROOF_BINDING_HOLD",
            "V3_PAPER_SEAL_PARAMETER_HOLD",
            "V3_PAPER_SEAL_PINS_HOLD",
            "V3_PAPER_SEAL_SIGNED_REQUEST_DRIFT",
            "V3_PAPER_SEAL_SOURCE_LOCK_DRIFT",
            "V3_PAPER_STARTED_TASK_ACTION_DRIFT",
            "V3_PAPER_SUCCESSOR_SERIES_OUTSIDE_CAS_WINDOW",
            "V3_PAPER_SUPERSESSION_DIGEST_HOLD",
            "V3_PAPER_SUPERSESSION_PINS_REQUIRED",
            "V3_PAPER_TASK_BACKUP_HASH_HOLD",
            "V3_PAPER_UNKNOWN_MODE",
            "V3_PR515_ARMED_ONLY_FENCE_ACL_HOLD",
            "V3_PR515_ARMED_ONLY_FENCE_FILE_OR_SHA_HOLD",
            "V3_PR515_ARMED_ONLY_FOREIGN_FENCE_HOLD",
            "V3_PR515_ARMED_ONLY_FOREIGN_FENCE_WRITER_HOLD",
            "V3_PR515_ARMED_ONLY_FOREIGN_MAINTENANCE_HOLD",
            "V3_PR515_ARMED_ONLY_RECOVERY_HOST_OR_PIN_HOLD",
            "V3_PR515_ARMED_TO_QUIESCED_SOURCE_UNCONDITIONALLY_LOCKED",
            "V3_PR515_MARKER_ONLY_CANCEL_SOURCE_LOCKED_INDEPENDENT_ABORT_CUSTODY_NOT_WIRED",
            "V3_PR515_NATIVE_PHASE_CONFLICT",
            "V3_PR515_NATIVE_STOP_SOURCE_UNCONDITIONALLY_LOCKED",
            "V3_PR515_PHASE_B_EXACT_SIGNED_ISSUER_COMMIT_HOLD",
            "V3_PR515_PHASE_B_EXTERNAL_SCHEDULER_CUSTODY_RELEASE_NOT_AUTHORIZED",
            "V3_PR515_PRECOMMIT_RESTORE_SOURCE_UNCONDITIONALLY_LOCKED",
            "V3_PR515_QUIESCED_EXTERNAL_PID_AND_CAS_CUSTODY_NOT_WIRED",
            "V3_PR661_ABANDONED_MUTEX_HOLD",
            "V3_PR661_ABANDONED_OPERATOR_MUTEX_HOLD",
            "V3_PR661_COMPLETE_SESSION_PRODUCTION_RELEASE_LOCKED",
            "V3_PR661_CONCURRENT_OPERATOR_HOLD",
            "V3_PR661_CURRENT_INTAKE_PROCESS_FAMILIES_MISSING",
            "V3_PR661_EXACT_ARMED_FENCE_HOLD",
            "V3_PR661_FENCE_ACL_UNPROTECTED",
            "V3_PR661_FENCE_ARCHIVE_PRODUCTION_RELEASE_LOCKED",
            "V3_PR661_FENCE_CHANGED_BEFORE_STOP",
            "V3_PR661_FENCE_FOREIGN_WRITER_HOLD",
            "V3_PR661_FENCE_OR_FOREIGN_MAINTENANCE_HOLD",
            "V3_PR661_INDEPENDENT_ISSUER_ACK_REQUIRED",
            "V3_PR661_INTAKE_ACTION_DRIFT",
            "V3_PR661_INTAKE_ACTION_NOT_DISJOINT_FROM_PROTECTED",
            "V3_PR661_INTAKE_ARGUMENT_AMBIGUOUS",
            "V3_PR661_MARKER_PHASE_OR_REPO_HOLD",
            "V3_PR661_NATIVE_ADMIN_HOLD",
            "V3_PR661_NATIVE_HELPER_BLOB_HOLD",
            "V3_PR661_NATIVE_HELPER_PATH_HOLD",
            "V3_PR661_NATIVE_HELPER_READONLY_HOLD",
            "V3_PR661_NATIVE_SIGNED_T0_OR_DRIFT_HOLD",
            "V3_PR661_NATIVE_STOP_ORIGINAL_BACKUP_OR_SOURCE_HOLD",
            "V3_PR661_NATIVE_STOP_UNRELEASED_EFFECTFUL_SOURCE_HARDLOCK",
            "V3_PR661_NATIVE_TASK_OR_PID_NOT_QUIESCENT_LEAVE_FENCE",
            "V3_PR661_NATIVE_WINDOWS_OR_SOURCE_PIN_HOLD",
            "V3_PR661_ORIGINAL_TASK_IDENTITY_OR_STATE_HOLD",
            "V3_PR661_POSTSTOP_FENCE_DRIFT_LEAVE_FENCE",
            "V3_PR661_PROTECTED_ACTION_DRIFT",
            "V3_PR661_RESUME_SESSION_SCOPE_HOLD",
            "V3_PR661_SCHEDULER_PID_EXCLUSIVE_GATE_NOT_YET_PROVEN",
            "V3_PR661_SCOPED_TASK_SET_HOLD",
            "V3_PR661_SESSION_ABORT_FILE_SCOPE_HOLD",
            "V3_PR661_SESSION_NATIVE_NOT_QUIET",
            "V3_PR661_SESSION_NEW_INTAKE_PROCESS_SURVIVED",
            "V3_PR661_SESSION_PRIOR_PROCESS_SURVIVED",
            "V3_PR661_SESSION_REAL_PAIR_REQUIRED",
            "V3_PR661_SESSION_TASK_SCOPE_DRIFT",
            "V3_PR661_SIGNED_ISSUER_PRESTOP_HOLD",
            "V3_PR661_V3_WRITER_NOT_DISABLED",
            "V3_PRECAS_ADMINISTRATOR_REQUIRED",
            "V3_PRECAS_ARMED_FENCE_ACL_DRIFT_LEAVE_FENCE",
            "V3_PRECAS_ARMED_FENCE_CONTENT_DRIFT_LEAVE_FENCE",
            "V3_PRECAS_ARMED_FENCE_FILE_DRIFT_LEAVE_FENCE",
            "V3_PRECAS_ARMED_FENCE_FOREIGN_WRITER_LEAVE_FENCE",
            "V3_PRECAS_ARMED_NOT_ACKED_LEAVE_FENCE",
            "V3_PRECAS_BAD_PROCESS_INVENTORY",
            "V3_PRECAS_CONFLICTING_OR_EXISTING_FENCE",
            "V3_PRECAS_FENCE_RACE",
            "V3_PRECAS_FRESH_XML_OR_PR515_PREVIEW_MISSING",
            "V3_PRECAS_INTAKE_IDENTITY_CHANGED",
            "V3_PRECAS_NATIVE_ARGUMENTS_AMBIGUOUS",
            "V3_PRECAS_NATIVE_PROCESS_OWNER_NOT_UNIQUE",
            "V3_PRECAS_NATIVE_PROCESS_ROOTS_UNVERIFIED",
            "V3_PRECAS_NATIVE_QUIESCENCE_UNKNOWN_LEAVE_ARMED_FENCE",
            "V3_PRECAS_NOT_EXACT_READY_V2R4",
            "V3_PRECAS_PROTECTED_AFTERCARE_MUST_KEEP_RUNNING",
            "V3_PRECAS_SOURCE_OR_REVIEWED_PINS_INVALID",
            "V3_PRECAS_SUPERVISOR_SCHEDULE_OR_OWNER_DRIFT",
            "V3_PRECAS_UNEXPECTED_NATIVE_INTAKE_STATE_LEAVE_FENCE",
            "V3_PRECOMMIT_ARCHIVE_COLLISION_PRESERVE_PAIR_AND_FENCE",
            "V3_PRECOMMIT_ARMED_FENCE_CHANGED_BEFORE_MANUAL_RECOVERY",
            "V3_PRECOMMIT_CURRENT_TWO_XML_AND_PR515_RECOVERY_RECHECK_FAILED",
            "V3_PRECOMMIT_FENCE_CHANGED_DURING_RECOVERY",
            "V3_PRECOMMIT_FOREIGN_MAINTENANCE_MARKER",
            "V3_PRECOMMIT_FOREIGN_OR_NON_QUIESCED_MARKER",
            "V3_PRECOMMIT_INDEPENDENT_CLOUD_CAS_AUTHORITY_NOT_WIRED",
            "V3_PRECOMMIT_MARKER_CHANGED_BEFORE_ATOMIC_REPLACE",
            "V3_PRECOMMIT_NATIVE_RESTORE_NOT_REQUESTED_PRESERVE_FENCE",
            "V3_PRECOMMIT_ORIGINAL_FENCE_SHA_CHANGED",
            "V3_PRECOMMIT_PROTECTED_AFTERCARE_NOT_RUNNING",
            "V3_PRECOMMIT_RECEIPT_ORIGINAL_FENCE_PHASE_MISMATCH",
            "V3_PRECOMMIT_RESTORE_ADMIN_REQUIRED",
            "V3_PRECOMMIT_RESTORE_AFTERCARE_UNKNOWN_MANUAL_REVIEW_REQUIRED",
            "V3_PRECOMMIT_RESTORE_ARCHIVE_NOT_CONFIRMED",
            "V3_PRECOMMIT_RESTORE_HOST_OR_EXTERNAL_PINS_INVALID",
            "V3_PRECOMMIT_RESTORE_NOT_HEALTHY_PRESERVE_ARMED_FENCE",
            "V3_PRECOMMIT_RESTORE_NOT_MANUAL_REVIEW_ELIGIBLE",
            "V3_PRECOMMIT_RESTORE_ORIGINAL_WINDOWS_REQUIRED",
            "V3_PRECOMMIT_RESTORE_REAL_HELD_PAIR_REQUIRED",
            "V3_PREPARED_FENCE_BAD_PINS",
            "V3_PREPARED_FENCE_MISSING",
            "V3_PREPARED_FENCE_PIN_MISMATCH_BEFORE_WRITE",
            "V3_QUIESCED_ADMIN_REQUIRED",
            "V3_QUIESCED_AFTERCARE_NOT_RUNNING",
            "V3_QUIESCED_ARMED_FENCE_ACL_DRIFT",
            "V3_QUIESCED_FENCE_UNTRUSTED_WRITER",
            "V3_QUIESCED_MARKER_SCOPE_NOT_ARMED",
            "V3_QUIESCED_NATIVE_INTAKE_REARMED",
            "V3_QUIESCED_ORIGINAL_FENCE_RACE",
            "V3_QUIESCED_ORIGINAL_SOURCE_OR_FENCE_PIN_INVALID",
            "V3_QUIESCED_ORIGINAL_WINDOWS_ONLY",
            "V3_QUIESCED_PHASE_READBACK_HOLD_LEAVE_FENCE",
            "V3_QUIESCED_TEMP_COLLISION",
            "V3_QUIESCED_TWO_CYCLE_OR_PR515_ACK_INCOMPLETE",
            "V3_QUIESCED_UNTRUSTED_ARMED_FENCE",
            "V3_RECONCILE_ABANDONED_MUTEX_HOLD",
            "V3_RECONCILE_ADMIN_REQUIRED",
            "V3_RECONCILE_AFTERCARE_NOT_ORIGINAL",
            "V3_RECONCILE_ALREADY_COMPLETED_NO_REPLAY",
            "V3_RECONCILE_ARCHIVE_OR_FOREIGN_MAINTENANCE_HOLD",
            "V3_RECONCILE_ARCHIVE_UNKNOWN_NO_RETRY",
            "V3_RECONCILE_ATTEMPT_DRIFT",
            "V3_RECONCILE_AWAITING_RECEIPT_DRIFT",
            "V3_RECONCILE_BACKUP_DRIFT",
            "V3_RECONCILE_BACKUP_SCOPE_HOLD",
            "V3_RECONCILE_BACKUP_XML_DRIFT",
            "V3_RECONCILE_CONCURRENT_OPERATOR_HOLD",
            "V3_RECONCILE_CONTINUATION_AUTHORITY_DRIFT",
            "V3_RECONCILE_CONTINUATION_BINDING_DRIFT",
            "V3_RECONCILE_CONTINUATION_PIN_WITHOUT_ATTEMPT_HOLD",
            "V3_RECONCILE_DISABLED_DEFINITION_DRIFT",
            "V3_RECONCILE_ENABLED_DEFINITION_DRIFT",
            "V3_RECONCILE_ENABLED_XML_HOLD",
            "V3_RECONCILE_EVIDENCE_TASK_SCOPE_HOLD",
            "V3_RECONCILE_FINAL_READBACK_UNKNOWN_NO_RETRY",
            "V3_RECONCILE_FOREIGN_MAINTENANCE_HOLD",
            "V3_RECONCILE_HASH_BINDINGS_HOLD",
            "V3_RECONCILE_HEALTH_UNKNOWN_NO_RETRY",
            "V3_RECONCILE_HEARTBEAT_STALE_HOLD",
            "V3_RECONCILE_HEARTBEAT_TIME_HOLD",
            "V3_RECONCILE_HEARTBEAT_UNHEALTHY",
            "V3_RECONCILE_IDENTITY_OR_BINDINGS_HOLD",
            "V3_RECONCILE_INSTANCE_IDENTITY_UNKNOWN",
            "V3_RECONCILE_INTERACTIVE_ORIGINALHOST_ONLY",
            "V3_RECONCILE_LIVE_TASK_STATE_DRIFT",
            "V3_RECONCILE_NOT_CONTINUING_ORIGINAL_TASKS",
            "V3_RECONCILE_ORIGINAL_ARTIFACT_DRIFT",
            "V3_RECONCILE_ORIGINAL_BINDING_DRIFT",
            "V3_RECONCILE_ORIGINAL_BYTES_CHANGED",
            "V3_RECONCILE_ORIGINAL_EVIDENCE_HOLD",
            "V3_RECONCILE_ORIGINAL_LEASE_RACE",
            "V3_RECONCILE_ORIGINAL_PROCESS_IDENTITY_DRIFT",
            "V3_RECONCILE_ORIGINAL_SCOPE_DRIFT",
            "V3_RECONCILE_POST_ARCHIVE_ATTEMPT_DRIFT",
            "V3_RECONCILE_POST_ARCHIVE_CHECKPOINT_DRIFT",
            "V3_RECONCILE_POST_ARCHIVE_FENCE_HOLD",
            "V3_RECONCILE_POST_ARCHIVE_READER_UNKNOWN_NO_RETRY",
            "V3_RECONCILE_POST_ARCHIVE_SCOPE_OR_EXPIRY_HOLD",
            "V3_RECONCILE_PRE_ARCHIVE_ARCHIVE_CONFLICT_HOLD",
            "V3_RECONCILE_PRE_ARCHIVE_ARTIFACTS_HOLD",
            "V3_RECONCILE_PRE_ARCHIVE_ARTIFACT_DRIFT",
            "V3_RECONCILE_PRE_ARCHIVE_ATTEMPT_AUTHORITY_HOLD",
            "V3_RECONCILE_PRE_ARCHIVE_AWAITING_CONFLICT_HOLD",
            "V3_RECONCILE_PRE_ARCHIVE_BINDINGS_HOLD",
            "V3_RECONCILE_PRE_ARCHIVE_CHECKPOINT_HOLD",
            "V3_RECONCILE_PRE_ARCHIVE_HISTORICAL_PROOF_DRIFT",
            "V3_RECONCILE_PRE_ARCHIVE_IDENTITY_HOLD",
            "V3_RECONCILE_PRE_ARCHIVE_INSTANCE_REPLACED",
            "V3_RECONCILE_PRE_ARCHIVE_INTERRUPTED_PROOF_DRIFT",
            "V3_RECONCILE_PRE_ARCHIVE_LATCH_HOLD",
            "V3_RECONCILE_PRE_ARCHIVE_NO_REPAIR_HOLD",
            "V3_RECONCILE_PRE_ARCHIVE_STATE_CONFLICT_HOLD",
            "V3_RECONCILE_PROCESS_ACTION_HOLD",
            "V3_RECONCILE_PROCESS_COUNT_DRIFT",
            "V3_RECONCILE_PROCESS_NOT_OLDER_THAN_ORIGINAL_WINDOW",
            "V3_RECONCILE_PROCESS_SCOPE_HOLD",
            "V3_RECONCILE_REAL_PAIR_REQUIRED",
            "V3_RECONCILE_RUNNING_INSTANCE_REPLACED",
            "V3_RECONCILE_SESSION_EXPIRED_NO_RETRY",
            "V3_RECONCILE_STOP_FORBIDDEN",
            "V3_RECONCILE_TASK_MULTIPLE_INSTANCE_POLICY_HOLD",
            "V3_RECONCILE_UNKNOWN_BINDING_HOLD",
            "V3_RELEASE_APPROVAL_EXPIRED_OR_FUTURE_HOLD",
            "V3_RELEASE_APPROVAL_FIELDS_HOLD",
            "V3_RELEASE_APPROVAL_TIME_FORMAT_HOLD",
            "V3_RELEASE_ARMED_FENCE_DRIFT",
            "V3_RELEASE_ARTIFACT_HASH_HOLD",
            "V3_RELEASE_ARTIFACT_SET_HOLD",
            "V3_RELEASE_AUTHORITY_ADMISSION_CHANGED",
            "V3_RELEASE_AUTHORITY_PIN_OR_CMS_HOLD",
            "V3_RELEASE_BACKUP_MANIFEST_PIN_HOLD",
            "V3_RELEASE_BINDINGS_HOLD",
            "V3_RELEASE_DUPLICATE_KEY_HOLD",
            "V3_RELEASE_ENABLE_TASK_SCOPE_HOLD",
            "V3_RELEASE_EXISTING_ADMIN_OPERATOR_REQUIRED",
            "V3_RELEASE_FILE_SIZE_HOLD",
            "V3_RELEASE_FRESH_TERMINAL_ABORT_REQUIRED_NO_REARM",
            "V3_RELEASE_FUNCTION_ACL_COUNT_HOLD",
            "V3_RELEASE_FUNCTION_ACL_DRIFT",
            "V3_RELEASE_FUNCTION_SET_HOLD",
            "V3_RELEASE_HOST_BINDINGS_HOLD",
            "V3_RELEASE_HOST_HASH_BINDINGS_HOLD",
            "V3_RELEASE_INDEPENDENT_ADMISSION_HASH_HOLD",
            "V3_RELEASE_INDEPENDENT_AUTHORITY_NOT_ADMITTED",
            "V3_RELEASE_INDEPENDENT_PRESTOP_HOLD",
            "V3_RELEASE_INSTALL_COMMIT_BINDING_READBACK_HOLD",
            "V3_RELEASE_INSTALL_READBACK_DRIFT",
            "V3_RELEASE_INSTALL_SOURCE_BINDING_HOLD",
            "V3_RELEASE_INTERACTIVE_ORIGINALHOST_ONLY",
            "V3_RELEASE_ISSUER_EXPIRED_AFTER_LEASE",
            "V3_RELEASE_JSON_KEY_HOLD",
            "V3_RELEASE_JSON_OBJECT_HOLD",
            "V3_RELEASE_JSON_SIZE_HOLD",
            "V3_RELEASE_LOCAL_PATH_REQUIRED",
            "V3_RELEASE_ORIGINALHOST_AUTHORIZATION_NOT_LIVE",
            "V3_RELEASE_ORIGINALHOST_FINAL_ACK_NOT_CONFIRMED",
            "V3_RELEASE_ORIGINAL_FUNCTION_BODY_DRIFT",
            "V3_RELEASE_ORIGINAL_INSTALL_READBACK_REQUIRED",
            "V3_RELEASE_ORIGINAL_INTERACTIVE_MINIPC_REQUIRED",
            "V3_RELEASE_ORIGINAL_OWNER_ADMISSION_NOT_MATCHED",
            "V3_RELEASE_ORIGINAL_OWNER_IDENTITY_HOLD",
            "V3_RELEASE_ORIGINAL_POLICY_COUNT_HOLD",
            "V3_RELEASE_ORIGINAL_POLICY_DRIFT",
            "V3_RELEASE_ORIGINAL_READBACK_WIRE_HOLD",
            "V3_RELEASE_PACKAGE_CHANGED_BEFORE_READ_LEASE",
            "V3_RELEASE_PG_FAILED_OUTCOME_UNCONFIRMED_READBACK_REQUIRED_NO_RETRY",
            "V3_RELEASE_PG_START_FAILED",
            "V3_RELEASE_PG_TIMEOUT_OUTCOME_UNKNOWN_NO_RETRY",
            "V3_RELEASE_PROTECTED_TASK_DRIFT",
            "V3_RELEASE_REPARSE_PATH_HOLD",
            "V3_RELEASE_SCOPE_OR_IDENTITY_HOLD",
            "V3_RELEASE_SESSION_ALREADY_OWNED",
            "V3_RELEASE_SESSION_EXPIRED_FENCE_PRESERVED",
            "V3_RELEASE_SESSION_HANDLES_CLOSED_RECONCILIATION_REQUIRED",
            "V3_RELEASE_SIGNER_OR_VALIDITY_HOLD",
            "V3_RELEASE_SINGLE_DETACHED_SIGNER_REQUIRED",
            "V3_RELEASE_STOP_ALREADY_ATTEMPTED",
            "V3_RESTORE_HEARTBEAT_FILE_HOLD",
            "V3_RESTORE_HEARTBEAT_STALE_OR_FUTURE",
            "V3_RESTORE_HEARTBEAT_UTC_LITERAL_HOLD",
            "V3_STAGE4_EPOCH_COMMIT_READBACK_HOLD_NO_RETRY",
            "V3_STAGE4_EPOCH_INDEPENDENT_BINDINGS_HOLD",
            "V3_TASK_DEFINITION_LEASE_DISABLED_STATE_DRIFT",
            "V3_TASK_DEFINITION_LEASE_ORIGINAL_SCOPE_HOLD",
            "V3_TASK_DEFINITION_LEASE_REQUIRES_ALREADY_DISABLED",
            "V3_TASK_DEFINITION_LEASE_SANDBOX_NAME_HOLD",
            "V3_TASK_DEFINITION_LEASE_UNSAFE_FILE",
            "V3_TASK_DEFINITION_LEASE_WINDOWS_ONLY"
          )) {
            $safeDetail.reported_code = $detail.reported_code
          }
          $diagnosis.failure_detail = $safeDetail
        }
        $checks["v3_paper_single_writer"]["diagnosis"] = $diagnosis
      }
    } else {
      Add-Check "v3_paper_single_writer" $false "fence present but not a valid committed successor" "WARNING"
    }
  } else {
    $checks["v3_paper_single_writer"]=[ordered]@{ok=$null;detail="no committed V3 fence on local host"}
  }
} catch {
  Add-Check "v3_paper_single_writer" $false "V3 local successor observation unavailable" "WARNING"
}

# Active predecessor aftercare remains observed. Only deliberately fenced
# old intake is neutral; unexpected re-enable remains a warning.
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
    Add-NativeTaskReadback -Key $spec.check -Task $task
    if($v3CommittedFence -and $spec.check -in @("v2r4_paper_candidates","v2r4_paper_wait")){
      if($task -and [string]$task.State -ceq "Disabled"){
        $checks[$spec.check]=[ordered]@{ok=$null;detail="RETIRED_INTAKE_DISABLED_COMMITTED_FENCE"}
      }else{
        Add-Check $spec.check $false "committed fence requires predecessor intake Disabled" "WARNING"
      }
      continue
    }
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
    Add-NativeTaskReadback -Key $spec.check -Task $null
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
      $detail = ("status=" + $s.status + " age_sec=" + $ageSec + " restarted=" + (($s.restarted | ForEach-Object { $_ }) -join ","))
      # Display evidence only: never change existing health severity, task actions or fence.
      # Exact complete original report required; partial/foreign/old reports cannot clear a warning.
      $regular = @("CryptoMiniPC-KrakenCanary","CryptoMiniPC-KrakenUniverse","CryptoMiniPC-AltradyTrigger","CryptoMiniPC-V2R4WSShadow","CryptoMiniPC-V2R4ShadowOutcomes","CryptoMiniPC-V2R4ShadowCloudSync","CryptoMiniPC-V2R4PaperLifecycle","CryptoMiniPC-V2R4PaperCloudSync","CryptoMiniPC-StatusSync")
      $protected = @("CryptoMiniPC-V2R4PaperCandidates","CryptoMiniPC-V2R4PaperWait")
      $exactAge = ((Get-Date).ToUniversalTime() - $checked).TotalSeconds
      $fenceEvidence = (
        $s.kind -ceq "MINIPC_RUNTIME_SUPERVISOR_V1" -and $s.schema_version -eq 1 -and
        $s.status -ceq "WARNING" -and $exactAge -ge 0 -and $exactAge -le 300 -and
        $s.PSObject.Properties.Name -contains "error" -and $null -eq $s.error -and
        $s.restarted -is [array] -and @($s.restarted).Count -eq 0 -and
        $s.failed_restarts -is [array] -and @($s.failed_restarts).Count -eq 0 -and
        $s.maintenance.mode -ceq "NONE" -and
        $s.v3_paper_old_intake_fence.mode -ceq "CLOUD_COMMITTED" -and
        $s.v3_paper_old_intake_fence.marker_present -is [bool] -and $s.v3_paper_old_intake_fence.marker_present -eq $true -and
        $s.v3_paper_successor_readonly.kind -ceq "V3_PAPER_SUCCESSOR_SUPERVISOR_READONLY_OBSERVATION_V1" -and
        $s.v3_paper_successor_readonly.status -ceq "LOCAL_TASK_AND_HEARTBEAT_MATCH_NOT_RELEASE_PROOF" -and
        $s.guardrails.real_money_actions -is [bool] -and $s.guardrails.real_money_actions -eq $false -and
        $s.h3_001_archived -is [bool] -and $s.h3_001_archived -eq $true -and
        $s.tasks -is [array] -and @($s.tasks).Count -eq 12
      )
      $fenceOnly = $fenceEvidence
      $fenceResearchDelay = $false
      $otherRegularHealthy = $true
      if ($fenceEvidence) {
        foreach ($name in $regular) {
          $matchesForTask = @($s.tasks | Where-Object { $_.task -ceq $name })
          if ($matchesForTask.Count -ne 1 -or $matchesForTask[0].installed -isnot [bool] -or $matchesForTask[0].installed -ne $true -or $matchesForTask[0].healthy_after -isnot [bool] -or $matchesForTask[0].healthy_after -ne $true -or $matchesForTask[0].action -cne "NONE") {
            $fenceOnly = $false
            $r = if ($matchesForTask.Count -eq 1) { $matchesForTask[0] } else { $null }
            if ($name -ceq "CryptoMiniPC-V2R4ShadowOutcomes" -and $null -ne $r -and
                $r.installed -is [bool] -and $r.installed -eq $true -and
                $r.healthy_after -is [bool] -and $r.healthy_after -eq $false -and
                $r.action -cin @("NONE","BACKOFF") -and
                $r.before.scheduler_state -ceq "Running" -and $r.after.scheduler_state -ceq "Running" -and
                $r.after.heartbeat_status -ceq "HEALTHY" -and
                ($r.after.heartbeat_age_sec -is [double] -or $r.after.heartbeat_age_sec -is [int] -or $r.after.heartbeat_age_sec -is [long]) -and
                $r.after.heartbeat_age_sec -gt 90 -and $r.after.heartbeat_age_sec -le 300) {
              $fenceResearchDelay = $true
            } else { $otherRegularHealthy = $false }
          }
        }
        foreach ($name in $protected) {
          $matchesForTask = @($s.tasks | Where-Object { $_.task -ceq $name })
          if ($matchesForTask.Count -ne 1 -or $matchesForTask[0].installed -isnot [bool] -or $matchesForTask[0].installed -ne $true -or $matchesForTask[0].action -cne "V3_INTAKE_SUPERVISOR_REARM_BLOCKED" -or $matchesForTask[0].before.scheduler_state -cne "Disabled") { $fenceOnly = $false; $fenceEvidence = $false }
        }
        $archived = @($s.tasks | Where-Object { $_.task -ceq "CryptoMiniPC-V3H3Shadow001" })
        if ($archived.Count -ne 1 -or $archived[0].action -cne "ARCHIVED_BASELINE_NOT_RESTARTED") { $fenceOnly = $false; $fenceEvidence = $false }
      }
      if ($fenceOnly) { $detail += " classification=EXPECTED_V3_FENCE_ONLY_V1" }
      elseif ($fenceEvidence -and $otherRegularHealthy -and $fenceResearchDelay) { $detail += " classification=EXPECTED_V3_FENCE_WITH_RESEARCH_DELAY_V1" }
      $currentFenceViolation = (
        $s.kind -ceq "MINIPC_RUNTIME_SUPERVISOR_V1" -and $s.schema_version -eq 1 -and
        $s.status -ceq "CRITICAL" -and $exactAge -ge 0 -and $exactAge -le 180 -and
        $s.v3_paper_old_intake_fence.mode -ceq "CLOUD_COMMITTED" -and
        $s.v3_paper_old_intake_fence.marker_present -is [bool] -and
        $s.v3_paper_old_intake_fence.marker_present -eq $true -and
        $s.tasks -is [array] -and @($s.tasks | Where-Object {
          $_.task -cin $protected -and $_.installed -is [bool] -and $_.installed -eq $true -and
          $_.action -ceq "V3_FENCE_VIOLATION_WINDOWS_TASK_NOT_DISABLED" -and
          $_.before.scheduler_state -cin @("Ready","Running","Queued")
        }).Count -gt 0
      )
      if ($currentFenceViolation) {
        $detail += " classification=V3_SECURITY_STOP_REQUIRED_PREDECESSOR_FENCE"
      }
      Add-Check "runtime_supervisor" $ok $detail "WARNING"
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
  Add-NativeTaskReadback -Key "minipc_status_sync" -Task $statusTask
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
  Add-NativeTaskReadback -Key "minipc_status_sync" -Task $null
  Add-Check "minipc_status_sync" $false $_.Exception.Message "WARNING"
}

# V3 Canary 28h is observational only: do not change its active task or
# make the frozen V2R4 Paper health depend on the Canary task.
try {
  $v3CanaryTask = Get-ScheduledTask -TaskName "CryptoMiniPC-V3CanaryObservation28h" -ErrorAction SilentlyContinue
  Add-NativeTaskReadback -Key "v3_canary_observation_28h" -Task $v3CanaryTask
} catch {
  Add-NativeTaskReadback -Key "v3_canary_observation_28h" -Task $null
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
  paper_successor_observation = $paperSuccessorObservation
  native_task_readback = [ordered]@{
    kind = "MINIPC_NATIVE_TASK_READBACK_V1"
    observations = $nativeTaskReadback
    no_runtime_or_release_authority = $true
  }
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


# Local infrastructure alert routing is independent of the cloud health
# upload. Publish the original health report above first, and preserve its
# existing severity and exit code. This extension has no trading authority.
function Read-InfraTask {
  param([string]$Name)
  try {
    $items = @(Get-ScheduledTask -TaskName $Name -ErrorAction Stop)
    if ($items.Count -ne 1) { return @{ state="UNKNOWN" } }
    $task = $items[0]
    $info = Get-ScheduledTaskInfo -TaskName $task.TaskName -TaskPath $task.TaskPath -ErrorAction Stop
    return @{
      state=[string]$task.State
      result=[long]$info.LastTaskResult
      last_run=$(if ($info.LastRunTime -and $info.LastRunTime.Year -ge 2000) { $info.LastRunTime.ToUniversalTime().ToString("o") } else { $null })
      restart_count=[int]$task.Settings.RestartCount
      task_path=[string]$task.TaskPath
    }
  } catch {
    if ($_.CategoryInfo.Category -eq [System.Management.Automation.ErrorCategory]::ObjectNotFound) {
      return @{ state="MISSING" }
    }
    return @{ state="UNKNOWN" }
  }
}

function Read-InfraDrive {
  param([string]$Path)
  try { return [bool](Test-Path -LiteralPath $Path -PathType Container -ErrorAction Stop) }
  catch { return $null }
}

function Invoke-LocalInfrastructureMonitor {
  $proof = [ordered]@{
    kind="LOCAL_INFRASTRUCTURE_MONITOR_V1"
    checked_at_utc=[datetime]::UtcNow.ToString("o")
    status="HOLD"
    no_trading_authority=$true
  }
  $proc = $null
  $secretBytes = $null
  $secretText = $null
  $inputJson = $null
  try {
    if ([Security.Principal.WindowsIdentity]::GetCurrent().User.Value -ne "S-1-5-18") {
      $proof["reason"]="SYSTEM_REQUIRED"
      return $proof
    }

    $archive = Read-InfraTask "CryptoMiniPC-V2R4ShadowArchive"
    $archive["markers"]=@()
    $archive["log_matches_run"]=$false
    $archive["physical_bytes"]=$null
    $archiveLog = Join-Path $TradingRoot "Runtime\ShadowArchive\last-run.log"
    if ($archive.last_run -and (Test-Path -LiteralPath $archiveLog -PathType Leaf)) {
      try {
        $item = Get-Item -LiteralPath $archiveLog -ErrorAction Stop
        $start = ([datetimeoffset]::Parse($archive.last_run)).UtcDateTime
        $archive["log_matches_run"]=($item.LastWriteTimeUtc -ge $start.AddSeconds(-2) -and $item.LastWriteTimeUtc -le [datetime]::UtcNow.AddSeconds(5))
        if ($archive.log_matches_run) {
          $allowed = "^(NO_ARCHIVE_REQUIRED_PASS|ARCHIVE_MAINTENANCE_PASS|ARCHIVE_HOLD|PHYSICAL_COMPACTION_DEFERRED|PHYSICAL_RELATION_BYTES_RELEASED|PHYSICAL_TARGET_NOT_REACHED|PHYSICAL_COMPACTION_NO_NEW_DELETE_SKIP|PHYSICAL_COMPACTION_BELOW_START_THRESHOLD_SKIP|PHYSICAL_COMPACTION_TARGET_MET)(?:\s*:|\s*$)"
          foreach ($line in @(Get-Content -LiteralPath $archiveLog -Tail 48 -ErrorAction Stop)) {
            if ($line.Trim() -match $allowed) {
              $archive["markers"] += $Matches[1]
            }
            if ($line.Trim() -match '^PHYSICAL_RELATION_BYTES_RELEASED:\s*(\d+)\s*$') {
              $archive["physical_bytes"]=[long]$Matches[1]
            }
          }
          $archive["markers"]=@($archive.markers | Sort-Object -Unique)
        }
      } catch {
        $archive["log_matches_run"]=$false
        $archive["markers"]=@()
      }
    }

    $tunnel = Read-InfraTask "GitHub-SafeAccess-Tunnel"
    $tunnel["failed_runs"]=@()
    # Read only a bounded set of relevant scheduler events, not tunnel logs
    # or task arguments (which may contain confidential configuration).
    try {
      $taskFullName = [string]$tunnel.task_path + "GitHub-SafeAccess-Tunnel"
      if ($taskFullName -match '^\\[A-Za-z0-9_\\ -]+$') {
        $xpath = "*[System[(EventID=101 or EventID=201 or EventID=202 or EventID=203) and TimeCreated[timediff(@SystemTime) <= 3600000]] and EventData[Data[@Name='TaskName']='$taskFullName']]"
        $events = @(Get-WinEvent -LogName "Microsoft-Windows-TaskScheduler/Operational" -FilterXPath $xpath -MaxEvents 12 -ErrorAction SilentlyContinue)
        foreach ($event in $events) {
          $failed = $event.Id -in @(101,202,203)
          if ($event.Id -eq 201) {
            $xml = [xml]$event.ToXml()
            $data = @($xml.Event.EventData.Data | Where-Object { $_.Name -eq "ResultCode" })
            if ($data.Count -eq 1) {
              $value = [string]$data[0]."#text"
              if ($value -match '^(?:0x[0-9a-fA-F]+|[0-9]+)$') {
                $failed = ([Convert]::ToUInt64($value.Replace("0x",""),$(if ($value.StartsWith("0x")) {16} else {10})) -ne 0)
              }
            }
          }
          if ($failed -and $event.TimeCreated) {
            $tunnel["failed_runs"] += $event.TimeCreated.ToUniversalTime().ToString("o")
          }
        }
      }
    } catch { }
    $tunnel.Remove("task_path")
    $archive.Remove("task_path")

    $sync = @{}
    try {
      $syncFile = Join-Path $TradingRoot "State\minipc-status-sync-heartbeat.json"
      $h = Get-Content -LiteralPath $syncFile -Raw -ErrorAction Stop | ConvertFrom-Json
      $sync = @{ status=[string]$h.status; checked_at_utc=[string]$h.checked_at_utc }
      # Derive only a bounded non-secret transport classification.
      $sync["transport_failure"]=([string]$h.detail -match '(?i)relay HTTP 5\d\d|URLError|TimeoutError|ConnectionError|RemoteDisconnected|timed out|connection (?:refused|reset|aborted)')
    } catch { }

    $router = Join-Path $repo "tools\process-health-alert-router.py"
    if (-not (Test-Path -LiteralPath $router -PathType Leaf) -or -not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
      $proof["reason"]="LOCAL_ROUTER_UNAVAILABLE"
      return $proof
    }
    Add-Type -AssemblyName System.Security
    $secretFile = Join-Path $TradingRoot "Runtime\WatchdogSecrets\slack-webhook.dpapi"
    $secretBytes = [Security.Cryptography.ProtectedData]::Unprotect(
      [IO.File]::ReadAllBytes($secretFile), $null,
      [Security.Cryptography.DataProtectionScope]::LocalMachine)
    $secretText = [Text.Encoding]::UTF8.GetString($secretBytes)
    $inputJson = [ordered]@{
      system=$true
      status_sync=$sync
      archive=$archive
      tunnel=$tunnel
      drives=@{
        c=(Read-InfraDrive (Join-Path $TradingRoot "Backup\Shadow-Archive\Automatic"))
        mistral=(Read-InfraDrive "D:\V3-Shadow-Archive-Automatic")
      }
      webhook=$secretText
    } | ConvertTo-Json -Depth 7 -Compress

    # Credentials travel only through the child's standard input, never as
    # arguments, environment variables, diagnostics or log lines.
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $venvPython
    $psi.Arguments = '-B "' + $router + '" --local-watchdog "' + $TradingRoot + '"'
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardInput = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $proc = [Diagnostics.Process]::Start($psi)
    $outTask = $proc.StandardOutput.ReadToEndAsync()
    $errTask = $proc.StandardError.ReadToEndAsync()
    $proc.StandardInput.WriteLine($inputJson)
    $proc.StandardInput.Close()
    if (-not $proc.WaitForExit(30000)) {
      $proc.Kill()
      $proof["reason"]="LOCAL_ROUTER_TIMEOUT"
      return $proof
    }
    if ($proc.ExitCode -ne 0) {
      $proof["reason"]="LOCAL_ROUTER_HOLD"
      return $proof
    }
    $raw = $outTask.GetAwaiter().GetResult()
    if ($raw.Length -gt 16384) {
      $proof["reason"]="LOCAL_ROUTER_OUTPUT_LIMIT"
      return $proof
    }
    $receipt = $raw | ConvertFrom-Json
    if ($receipt.kind -ne "LOCAL_INFRASTRUCTURE_MONITOR_V1" -or $receipt.no_trading_authority -ne $true) {
      $proof["reason"]="LOCAL_ROUTER_RECEIPT_INVALID"
      return $proof
    }
    return $receipt
  } catch {
    # Never surface exceptions from secret handling or network calls.
    $proof["reason"]="LOCAL_MONITORING_ERROR"
    return $proof
  } finally {
    if ($proc) { $proc.Dispose() }
    if ($secretBytes) { [Array]::Clear($secretBytes,0,$secretBytes.Length) }
    $secretText=$null
    $inputJson=$null
  }
}

try {
  $infraReceipt = Invoke-LocalInfrastructureMonitor
  $infraPath = Join-Path $stateDir "minipc-infrastructure-monitoring.json"
  $infraTemp = $infraPath + "." + [guid]::NewGuid().ToString("N") + ".tmp"
  try {
    [IO.File]::WriteAllText($infraTemp, ($infraReceipt | ConvertTo-Json -Depth 9), (New-Object System.Text.UTF8Encoding($false)))
    if (Test-Path -LiteralPath $infraPath) {
      [IO.File]::Replace($infraTemp,$infraPath,$null)
    } else {
      [IO.File]::Move($infraTemp,$infraPath)
    }
  } finally {
    if (Test-Path -LiteralPath $infraTemp) { Remove-Item -LiteralPath $infraTemp -Force -ErrorAction SilentlyContinue }
  }
} catch { }

Write-Output $json
if ($critical -gt 0) { exit 2 }
exit 0