param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE 'Trading'),
  [switch]$Stage,
  [string]$Confirm = ''
)
# Controlled staging ONLY. Never starts, stops or updates scheduled tasks,
# Supabase, the active Paper app, H3-001 or any current paper evidence.
$ErrorActionPreference = 'Stop'
$repo=Join-Path $TradingRoot 'Repos\kraken-eur-scanner'
$oldApp=Join-Path $TradingRoot 'Runtime\v2r4-paper-app'
$oldSeries='PAPER-V2R4-20261007T184255Z'
$oldRelease='3c6729a6c548d169f56a97f07f75892f37211636'
$sourceFiles=@(
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
function Fingerprint([string]$Root,[string[]]$Paths) {
  $sb=[System.Text.StringBuilder]::new()
  foreach($rel in ($Paths | Sort-Object)) {
    $file=Join-Path $Root $rel
    if(-not (Test-Path -LiteralPath $file)){throw "Missing frozen bundle input: $rel"}
    $hash=(Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
    [void]$sb.Append($rel.Replace('\','/')+':'+$hash+[Environment]::NewLine)
  }
  $hashing=[Security.Cryptography.SHA256]::Create()
  try {
    $hash=([BitConverter]::ToString($hashing.ComputeHash([Text.Encoding]::UTF8.GetBytes($sb.ToString())))).Replace('-','').ToLowerInvariant()
    return $hash
  } finally { $hashing.Dispose() }
}
if(-not (Test-Path -LiteralPath $repo)){ throw 'Repo missing' }
if((git -C $repo branch --show-current).Trim() -ne 'main'){ throw 'Require clean main branch' }
if(@(git -C $repo status --porcelain).Count -gt 0){ throw 'Working tree has uncommitted changes' }
$sha=(git -C $repo rev-parse HEAD).Trim().ToLowerInvariant()
if($sha -notmatch '^[a-f0-9]{40}$'){ throw 'Invalid git provenance' }
$control=Get-Content (Join-Path $oldApp 'paper_runtime_control.json') -Raw | ConvertFrom-Json
if($control.series_id -ne $oldSeries -or $control.release_repo_sha -ne $oldRelease){ throw 'Old PAPER release was changed: STOP' }
if($control.enabled -ne $true -or $control.paper_only -ne $true -or $control.real_money_actions_enabled -ne $false){ throw 'Unsafe PAPER guardrails: STOP' }
if([double]$control.scout_notional_eur -ne 50 -or [double]$control.stage2_notional_eur -ne 50){ throw 'Frozen sizing differs: STOP' }
$spec=Join-Path $repo 'research\v2r4\paper_strategy_spec_v2r4_release_candidate.json'
$specHash=(Get-FileHash -LiteralPath $spec -Algorithm SHA256).Hash.ToLowerInvariant()
if($specHash -ne [string]$control.strategy_fingerprint_sha256){ throw 'Strategy fingerprint drift: STOP' }
$bundleHash=Fingerprint $repo $sourceFiles
$stagedApp=Join-Path $TradingRoot ('Runtime\v2r4-paper-stage-'+$sha.Substring(0,12))
$manifestPath=Join-Path $stagedApp 'technical-stage-manifest.json'
$plan=[ordered]@{
  kind='V2R4_TECHNICAL_STAGE_V1'
  status='PLAN_ONLY'
  source_repo_sha=$sha
  predecessor_series_id=$oldSeries
  predecessor_release_repo_sha=$oldRelease
  candidate_strategy_revision=[string]$control.strategy_revision
  strategy_fingerprint_sha256=$specHash
  proposed_runtime_bundle_fingerprint_sha256=$bundleHash
  prepared_app=$stagedApp
  current_app_unchanged=$true
  no_runtime_control_in_prepared_app=$true
  cloud_activation_performed=$false
  h3_rebinding_performed=$false
  original_state_mutated=$false
  real_money_actions=$false
  order_api=$false
}
if(-not $Stage) {
  Write-Output ($plan | ConvertTo-Json -Depth 6)
  exit 0
}
if($Confirm -ne 'STAGE_TECHNICAL_PAPER_ONLY'){ throw 'Missing explicit staging confirmation' }
if(Test-Path -LiteralPath $stagedApp) {
  if(-not (Test-Path -LiteralPath $manifestPath)){ throw 'Staging folder exists without immutable manifest' }
  $old=Get-Content $manifestPath -Raw | ConvertFrom-Json
  if($old.source_repo_sha -ne $sha -or $old.proposed_runtime_bundle_fingerprint_sha256 -ne $bundleHash) {
    throw 'Existing staging manifest fingerprint conflict'
  }
  if(Test-Path (Join-Path $stagedApp 'paper_runtime_control.json')) { throw 'Staging unexpectedly contains enabled runtime control' }
  $plan.status='ALREADY_STAGED_NO_MUTATION'
  Write-Output ($plan | ConvertTo-Json -Depth 6)
  exit 0
}
# A staged app is incapable of running: NO paper_runtime_control.json is written.
New-Item -ItemType Directory -Path $stagedApp -Force | Out-Null
try {
  foreach($rel in $sourceFiles) {
    $source=Join-Path $repo $rel
    $destRel=$rel
    if($rel.StartsWith('tools\')) { $destRel=$rel.Substring(6) }
    $dest=Join-Path $stagedApp $destRel
    New-Item -ItemType Directory -Force -Path (Split-Path $dest -Parent) | Out-Null
    Copy-Item -LiteralPath $source -Destination $dest -ErrorAction Stop
    if((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash) {
      throw "Staged copy checksum mismatch: $rel"
    }
  }
  foreach($source in (Get-ChildItem (Join-Path $repo 'paper_evaluator') -File -Filter '*.py')) {
    $dest=Join-Path $stagedApp ('paper_evaluator\'+$source.Name)
    if(-not (Test-Path -LiteralPath $dest)) { Copy-Item -LiteralPath $source.FullName -Destination $dest }
  }
  foreach($rel in @('paper_context.py','research\v2r4\paper_strategy_spec_v2r4_release_candidate.json')) {
    $dest=if($rel -eq 'paper_context.py'){Join-Path $stagedApp 'paper_context.py'} else {Join-Path $stagedApp 'paper_strategy_spec.json'}
    Copy-Item -LiteralPath (Join-Path $repo $rel) -Destination $dest -ErrorAction Stop
  }
  if(Test-Path (Join-Path $stagedApp 'paper_runtime_control.json')){ throw 'Staging must never include an active control' }
  $plan.status='STAGED_INERT_NO_ACTIVATION'
  [IO.File]::WriteAllText($manifestPath,($plan | ConvertTo-Json -Depth 6)+[Environment]::NewLine,[Text.UTF8Encoding]::new($false))
} catch {
  throw ('STAGING_INCOMPLETE_NO_ACTIVE_CHANGE: '+$_.Exception.Message)
}
Write-Output ($plan | ConvertTo-Json -Depth 6)
