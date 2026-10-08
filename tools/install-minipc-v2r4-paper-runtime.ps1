param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading"),
  [switch]$Execute,
  [string]$Confirm = ""
)

$ErrorActionPreference = "Stop"
$expectedConfirm = "ACTIVATE_V2R4_PAPER"
$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$app = Join-Path $TradingRoot "Runtime\v2r4-paper-app"
$python = Join-Path $TradingRoot "Runtime\kraken-eur-scanner-venv\Scripts\python.exe"
$apiKey = Join-Path $TradingRoot "Secrets\openai-api-key.txt"
$relayToken = Join-Path $TradingRoot "Secrets\shadow-evidence-token.txt"
$githubDispatchToken = Join-Path $TradingRoot "Secrets\github-actions-dispatch-token.txt"
$statusRelayToken = Join-Path $TradingRoot "Secrets\minipc-status-token.txt"
$healthPath = Join-Path $TradingRoot "State\minipc-health.json"
$shadowEvents = Join-Path $TradingRoot "State\v2r4-ws-shadow-events"
$endpoint = "https://nlgzjmqgwueojlyqmoru.supabase.co/functions/v1/v2r4-paper-evidence-relay"
$revision = "V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION"

function Write-JsonAtomic([string]$Path,[object]$Payload,[int]$Depth=12) {
  $tmp = $Path + ".tmp"
  [System.IO.File]::WriteAllText($tmp,($Payload | ConvertTo-Json -Depth $Depth) + [Environment]::NewLine,[System.Text.UTF8Encoding]::new($false))
  Move-Item -LiteralPath $tmp -Destination $Path -Force
}

function Get-BundleFingerprint([string]$Root,[string[]]$RelativePaths) {
  $builder = New-Object System.Text.StringBuilder
  foreach($rel in ($RelativePaths | Sort-Object)) {
    $path = Join-Path $Root $rel
    if(-not (Test-Path $path)){ throw "Runtime fingerprint input missing: $path" }
    $hash = (Get-FileHash $path -Algorithm SHA256).Hash.ToLowerInvariant()
    [void]$builder.Append($rel.Replace('\','/') + ':' + $hash + [Environment]::NewLine)
  }
  $bytes=[System.Text.Encoding]::UTF8.GetBytes($builder.ToString())
  $sha=[System.Security.Cryptography.SHA256]::Create()
  try {
    return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-','').ToLowerInvariant()
  } finally {
    $sha.Dispose()
  }
}
function Wait-FreshHeartbeat([string]$Path,[int]$MaxAgeSeconds=45,[int]$TimeoutSeconds=90) {
  $deadline=(Get-Date).AddSeconds($TimeoutSeconds)
  while((Get-Date)-lt $deadline){
    Start-Sleep -Seconds 2
    if(Test-Path $Path){
      try{
        $h=Get-Content $Path -Raw | ConvertFrom-Json
        $age=[math]::Round(((Get-Date).ToUniversalTime()-([datetime]$h.checked_at_utc).ToUniversalTime()).TotalSeconds,1)
        if($h.status -eq 'HEALTHY' -and $age -le $MaxAgeSeconds){ return $h }
      }catch{}
    }
  }
  throw "No fresh HEALTHY heartbeat: $Path"
}

$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$principal=New-Object Security.Principal.WindowsPrincipal($identity)
if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){ throw "Run this command in an Administrator PowerShell." }

foreach($p in @($repo,$python,$apiKey,$relayToken,$githubDispatchToken,$statusRelayToken,$healthPath,$shadowEvents)) { if(-not (Test-Path $p)){ throw "Required path missing: $p" } }

if(-not $Execute){
  [pscustomobject]@{
    kind='MINIPC_V2R4_PAPER_ACTIVATION_PLAN_V1'; status='PLAN_ONLY'; required_confirm=$expectedConfirm;
    app_root=$app; release_revision=$revision; paper_only=$true; order_api=$false; real_money_actions=$false
  } | ConvertTo-Json -Depth 6
  exit 0
}
if($Confirm -ne $expectedConfirm){ throw "Refusing activation: -Confirm must equal $expectedConfirm" }

Write-Host "=== V2R4 PAPER ACTIVATION ==="
Write-Host "1/8 Fast-forward main, refresh machine health and pin exact provenance..."
Push-Location $repo
try {
  if((git branch --show-current).Trim() -ne 'main'){ throw 'MINI-PC repository must be on main.' }
  if(git status --porcelain){ throw 'MINI-PC repository must be clean before activation.' }
  & git fetch origin main
  if($LASTEXITCODE -ne 0){ throw 'git fetch origin main failed.' }
  & git pull --ff-only origin main
  if($LASTEXITCODE -ne 0){ throw 'Fast-forward pull failed.' }
  $releaseSha=(& git rev-parse HEAD).Trim().ToLowerInvariant()
  $originSha=(& git rev-parse origin/main).Trim().ToLowerInvariant()
  if($releaseSha -ne $originSha){ throw "Local main is not exactly origin/main: local=$releaseSha origin=$originSha" }
} finally { Pop-Location }

$supervisor=Join-Path $repo 'tools\minipc-runtime-supervisor.ps1'
$supervisorTask=Get-ScheduledTask -TaskName 'CryptoMiniPC-RuntimeSupervisor' -ErrorAction SilentlyContinue
if($supervisorTask -and (Test-Path $supervisor)){
  # Refresh the supervisor snapshot at the release boundary so watchdog health
  # cannot be blocked by a stale pre-activation recovery report.
  & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $supervisor -TradingRoot $TradingRoot | Out-Null
  if($LASTEXITCODE -ne 0){ throw "Runtime supervisor refresh failed with exit code $LASTEXITCODE" }
}
$watchdog=Join-Path $repo 'tools\minipc-watchdog.ps1'
& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $watchdog -TradingRoot $TradingRoot | Out-Null
if($LASTEXITCODE -ne 0){ throw "Post-pull watchdog failed with exit code $LASTEXITCODE" }
$health=Get-Content $healthPath -Raw | ConvertFrom-Json
$healthStamp=[string]$health.checked_at_utc
if([string]::IsNullOrWhiteSpace($healthStamp)){ $healthStamp=[string]$health.checked_at_local }
if([string]::IsNullOrWhiteSpace($healthStamp)){ throw 'MINI-PC health timestamp missing from watchdog report.' }
$healthAge=[math]::Round(((Get-Date).ToUniversalTime()-([datetime]$healthStamp).ToUniversalTime()).TotalSeconds,1)
if($health.status -ne 'HEALTHY' -or $health.health_state -ne 'OK' -or $healthAge -gt 120){
  throw "MINI-PC health is not fresh HEALTHY/OK: $($health.status)/$($health.health_state) age_sec=$healthAge"
}
$statusSync=Join-Path $repo 'tools\minipc-status-sync.py'
& $python $statusSync --trading-root $TradingRoot --once | Out-Null
if($LASTEXITCODE -ne 0){ throw "Fresh MINI-PC health could not be uploaded before activation." }

$strategySpecSource=Join-Path $repo 'research\v2r4\paper_strategy_spec_v2r4_release_candidate.json'
$strategyFingerprint=(Get-FileHash $strategySpecSource -Algorithm SHA256).Hash.ToLowerInvariant()
$runtimeFiles=@(
  'paper_evaluator\evaluate.py',
  'paper_evaluator\v2r4_trigger_contract.py',
  'paper_evaluator\v2r4_trigger_plan.py',
  'paper_evaluator\v2r4_wait_runtime.py',
  'paper_evaluator\v2r4_local_recheck.py',
  'paper_position_tracker.py',
  'paper_followup.py',
  'tools\v2r4-paper-local-runtime.py',
  'tools\v2r4-paper-cloud-sync.py',
  'market_data\__init__.py',
  'market_data\universe.py'
)
$runtimeFingerprint=Get-BundleFingerprint $repo $runtimeFiles
$approvalPath=Join-Path $repo 'research\v2r4\release-evidence\v2r4-paper-approval-20261007.json'
$approval=Get-Content $approvalPath -Raw | ConvertFrom-Json
if($approval.decision -ne 'APPROVED_PAPER' -or $approval.real_money_actions_allowed -ne $false){
  throw 'Repository release approval evidence is not a safe APPROVED_PAPER record.'
}
$candidateMergeSha=[string]$approval.candidate_merge_sha

Write-Host "2/8 Materialize isolated local V2R4 runtime app..."
New-Item -ItemType Directory -Force -Path $app | Out-Null
$evaluatorApp=Join-Path $app 'paper_evaluator'
New-Item -ItemType Directory -Force -Path $evaluatorApp | Out-Null
Copy-Item (Join-Path $repo 'paper_evaluator\*') $evaluatorApp -Recurse -Force
foreach($name in @('paper_context.py','paper_position_tracker.py','paper_followup.py')){ Copy-Item (Join-Path $repo $name) (Join-Path $app $name) -Force }
Copy-Item (Join-Path $repo 'tools\v2r4-paper-local-runtime.py') (Join-Path $app 'v2r4-paper-local-runtime.py') -Force
Copy-Item (Join-Path $repo 'tools\v2r4-paper-cloud-sync.py') (Join-Path $app 'v2r4-paper-cloud-sync.py') -Force
# The isolated app needs the same canonical WS-v2 symbol normalization as the
# Kraken universe feed; never reintroduce a private/static ticker whitelist.
$marketDataApp=Join-Path $app 'market_data'
New-Item -ItemType Directory -Force -Path $marketDataApp | Out-Null
Copy-Item (Join-Path $repo 'market_data\__init__.py') (Join-Path $marketDataApp '__init__.py') -Force
Copy-Item (Join-Path $repo 'market_data\universe.py') (Join-Path $marketDataApp 'universe.py') -Force
Copy-Item $strategySpecSource (Join-Path $app 'paper_strategy_spec.json') -Force
$appStrategyFingerprint=(Get-FileHash (Join-Path $app 'paper_strategy_spec.json') -Algorithm SHA256).Hash.ToLowerInvariant()
if($appStrategyFingerprint -ne $strategyFingerprint){ throw 'Copied V2R4 strategy fingerprint mismatch.' }
foreach($d in @('handoff_queue','paper_decisions','paper_rechecks','paper_revalidations','paper_positions','paper_followups','paper_trigger_receipts')){ New-Item -ItemType Directory -Force -Path (Join-Path $app $d) | Out-Null }

$controlPath=Join-Path $app 'paper_runtime_control.json'
if(Test-Path $controlPath){
  $control=Get-Content $controlPath -Raw | ConvertFrom-Json
  if($control.strategy_revision -ne $revision){ throw 'Existing V2R4 app has a different strategy revision; refusing overwrite.' }
  if([string]$control.release_repo_sha -ne $releaseSha){ throw 'Existing V2R4 app is pinned to a different release SHA; refusing mixed-series code.' }
  if([string]$control.strategy_fingerprint_sha256 -ne $strategyFingerprint){ throw 'Existing V2R4 app strategy fingerprint differs; refusing overwrite.' }
  if([string]$control.runtime_bundle_fingerprint_sha256 -ne $runtimeFingerprint){ throw 'Existing V2R4 app runtime fingerprint differs; refusing overwrite.' }
  if($control.real_money_actions_enabled -ne $false -or $control.paper_only -ne $true){ throw 'Existing V2R4 app safety flags are invalid.' }
  $seriesId=[string]$control.series_id; $testId=[string]$control.test_id; $startedAt=[string]$control.series_started_at_utc
}else{
  $now=(Get-Date).ToUniversalTime(); $stamp=$now.ToString('yyyyMMddTHHmmssZ'); $day=$now.ToString('yyyyMMdd')
  $seriesId="PAPER-V2R4-$stamp"; $testId="PAPER-V2R4-SERIES1-$day"; $startedAt=$now.ToString('o')
  $control=[ordered]@{
    schema_version=9; enabled=$true; runtime_owner='MINIPC_LOCAL_V2R4'; test_id=$testId; series_id=$seriesId;
    strategy_revision=$revision; series_started_at_utc=$startedAt; paper_only=$true; real_money_actions_enabled=$false;
    target_completed_paper_trades=20; predecessor_series_id='PAPER-V2R3-CLEAN-20261001T0925Z';
    supabase_archive_mode='AUTHENTICATED_EDGE_RELAY_PRIMARY_RUNTIME_EVIDENCE';
    runtime_storage_policy='SUPABASE_PRIMARY_BOUNDED_LOCAL_STATE_NO_PER_EVENT_GIT_COMMITS';
    wait_fallback_seconds=10; scout_notional_eur=50; stage2_notional_eur=50;
    release_decision='APPROVED_PAPER'; automatic_activation_allowed=$false;
    release_repo_sha=$releaseSha; candidate_merge_sha=$candidateMergeSha;
    strategy_fingerprint_sha256=$strategyFingerprint; runtime_bundle_fingerprint_sha256=$runtimeFingerprint
  }
  Write-JsonAtomic $controlPath $control 10
}

Write-Host "3/8 Compile active runtime and protect local secrets for SYSTEM tasks..."
& $python -m py_compile (Join-Path $app 'v2r4-paper-local-runtime.py') (Join-Path $app 'v2r4-paper-cloud-sync.py') (Join-Path $app 'market_data\universe.py') (Join-Path $app 'paper_evaluator\evaluate.py') (Join-Path $app 'paper_evaluator\v2r4_wait_runtime.py') (Join-Path $app 'paper_evaluator\v2r4_local_recheck.py') (Join-Path $app 'paper_position_tracker.py') (Join-Path $app 'paper_followup.py')
if($LASTEXITCODE -ne 0){ throw 'V2R4 runtime compile failed.' }
icacls $apiKey /grant:r 'SYSTEM:(R)' /C | Out-Null
icacls $relayToken /grant:r 'SYSTEM:(R)' /C | Out-Null
icacls $githubDispatchToken /grant:r 'SYSTEM:(R)' /C | Out-Null
icacls $statusRelayToken /grant:r 'SYSTEM:(R)' /C | Out-Null

Write-Host "4/8 Register V2R4 local tasks (not started yet)..."
$taskSpecs=@(
  @{name='CryptoMiniPC-V2R4PaperCandidates'; args=@((Join-Path $app 'v2r4-paper-local-runtime.py'),'--mode','candidates','--app-root',$app,'--trading-root',$TradingRoot,'--api-key-file',$apiKey,'--interval-seconds','2')},
  @{name='CryptoMiniPC-V2R4PaperWait'; args=@((Join-Path $app 'paper_evaluator\v2r4_wait_runtime.py'),'--decision-dir',(Join-Path $app 'paper_decisions'),'--recheck-dir',(Join-Path $app 'paper_rechecks'),'--candidate-dir',(Join-Path $app 'handoff_queue'),'--receipt-dir',(Join-Path $app 'paper_trigger_receipts'),'--state',(Join-Path $TradingRoot 'State\v2r4-paper-wait-runtime-state.json'),'--heartbeat',(Join-Path $TradingRoot 'State\v2r4-paper-wait-runtime-heartbeat.json'),'--altrady-log',(Join-Path $TradingRoot 'Logs\altrady-trigger-events.jsonl'),'--spec',(Join-Path $app 'paper_strategy_spec.json'),'--control',$controlPath,'--api-key-file',$apiKey,'--fallback-seconds','10','--loop-seconds','1','--execute-recheck')},
  @{name='CryptoMiniPC-V2R4PaperLifecycle'; args=@((Join-Path $app 'v2r4-paper-local-runtime.py'),'--mode','lifecycle','--app-root',$app,'--trading-root',$TradingRoot,'--interval-seconds','60')},
  @{name='CryptoMiniPC-V2R4PaperCloudSync'; args=@((Join-Path $app 'v2r4-paper-cloud-sync.py'),'--app-root',$app,'--trading-root',$TradingRoot,'--interval-seconds','60')}
)
foreach($spec in $taskSpecs){
  $quoted=@(); foreach($x in $spec.args){ $quoted += ('"'+[string]$x+'"') }
  $action=New-ScheduledTaskAction -Execute $python -Argument ($quoted -join ' ')
  $trigger=New-ScheduledTaskTrigger -AtStartup
  $settings=New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
  Register-ScheduledTask -TaskName $spec.name -Action $action -Trigger $trigger -Settings $settings -User 'SYSTEM' -RunLevel Highest -Force | Out-Null
}

Write-Host "5/8 Record explicit V2R4 Paper series activation in Supabase..."
$token=(Get-Content $relayToken -Raw).Trim(); if($token.Length -lt 24){ throw 'Paper evidence relay token missing/too short.' }
$statusToken=(Get-Content $statusRelayToken -Raw).Trim(); if($statusToken.Length -lt 24){ throw 'MINI-PC status relay token missing/too short.' }
$payload=@{action='activate';series_id=$seriesId;test_id=$testId;strategy_revision=$revision;started_at=$startedAt;config=$control} | ConvertTo-Json -Depth 12
$resp=Invoke-RestMethod -Uri $endpoint -Method Post -Headers @{'X-Shadow-Evidence-Token'=$token;'X-MiniPC-Status-Token'=$statusToken} -ContentType 'application/json' -Body $payload -TimeoutSec 30
if(-not $resp.ok -or $resp.status -ne 'active'){ throw 'Supabase activation relay did not confirm active series.' }

Write-Host "6/8 Start local V2R4 Paper tasks..."
foreach($spec in $taskSpecs){ Start-ScheduledTask -TaskName $spec.name }

Write-Host "7/8 Verify fresh runtime heartbeats..."
$cand=Wait-FreshHeartbeat (Join-Path $TradingRoot 'State\v2r4-paper-candidate-runtime-heartbeat.json') 45 120
$wait=Wait-FreshHeartbeat (Join-Path $TradingRoot 'State\v2r4-paper-wait-runtime-heartbeat.json') 30 120
$life=Wait-FreshHeartbeat (Join-Path $TradingRoot 'State\v2r4-paper-lifecycle-heartbeat.json') 120 120
$sync=Wait-FreshHeartbeat (Join-Path $TradingRoot 'State\v2r4-paper-cloud-sync-heartbeat.json') 120 120

Write-Host "8/8 Refresh watchdog + remote status..."
& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File (Join-Path $repo 'tools\minipc-watchdog.ps1') -TradingRoot $TradingRoot | Out-Null
if(Test-Path $statusSync){ & $python $statusSync --trading-root $TradingRoot --once | Out-Null }

$summary=[ordered]@{
  kind='MINIPC_V2R4_PAPER_ACTIVATION_SUMMARY_V1'; status='PASS'; series_id=$seriesId; test_id=$testId; strategy_revision=$revision;
  series_started_at_utc=$startedAt; runtime_owner='MINIPC_LOCAL_V2R4'; candidate_runtime=$cand.status; wait_runtime=$wait.status;
  lifecycle=$life.status; cloud_sync=$sync.status; release_repo_sha=$releaseSha; candidate_merge_sha=$candidateMergeSha;
  strategy_fingerprint_sha256=$strategyFingerprint; runtime_bundle_fingerprint_sha256=$runtimeFingerprint;
  paper_only=$true; order_api=$false; real_money_actions=$false
}
Write-Host ""
Write-Host "=== V2R4 PAPER ACTIVATION SUMMARY ==="
Write-Output ($summary | ConvertTo-Json -Depth 8)
Write-Host "=== END ==="
