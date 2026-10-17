param(
  [Parameter(Mandatory=$true)][string]$SourceRoot,
  [Parameter(Mandatory=$true)][string]$ExpectedSourceSha,
  [string]$TradingRoot=(Join-Path $env:USERPROFILE 'Trading'),
  [switch]$Stage,
  [string]$Confirm=''
)
# Original Issue #99: ONE-SHOT, source-only, INACTIVE V3 Paper release stage.
# Default is READ-ONLY. This is not a launcher, updater, task installer, Cloud
# CAS, Edge deploy, model caller, Supervisor or trading approval.
$ErrorActionPreference='Stop'

function Need([bool]$Condition,[string]$Reason) {
  if(-not $Condition){throw ('V3_INACTIVE_CODE_STAGE_BLOCKED: '+$Reason)}
}
function IsUnder([string]$Path,[string]$Root) {
  $base=[IO.Path]::GetFullPath($Root).TrimEnd('\','/')
  $child=[IO.Path]::GetFullPath($Path).TrimEnd('\','/')
  return $child.Equals($base,[StringComparison]::OrdinalIgnoreCase) -or
    $child.StartsWith($base+[IO.Path]::DirectorySeparatorChar,
                      [StringComparison]::OrdinalIgnoreCase)
}
function Fingerprint([string]$FilePath) {
  Need (Test-Path -LiteralPath $FilePath -PathType Leaf) 'tracked source missing'
  $item=Get-Item -LiteralPath $FilePath -Force -ErrorAction Stop
  Need (-not [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) 'linked file forbidden'
  $hash=([string](Get-FileHash -LiteralPath $FilePath -Algorithm SHA256 -ErrorAction Stop).Hash).ToLowerInvariant()
  Need ($hash -cmatch '^[0-9a-f]{64}$') 'invalid file digest'
  return $hash
}

Need ($ExpectedSourceSha -cmatch '^[0-9a-f]{40}$') 'exact reviewed source SHA required'
Need (Test-Path -LiteralPath $SourceRoot -PathType Container) 'independent source checkout missing'
Need (Test-Path -LiteralPath $TradingRoot -PathType Container) 'Trading root missing'
$source=[IO.Path]::GetFullPath((Resolve-Path -LiteralPath $SourceRoot).ProviderPath)
$trading=[IO.Path]::GetFullPath((Resolve-Path -LiteralPath $TradingRoot).ProviderPath)
Need (-not [bool]((Get-Item -LiteralPath $source -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) 'linked source root'
Need (-not (IsUnder $source $trading)) 'source MUST be a separate, independently pinned checkout outside Trading'
$root=(& git -C $source rev-parse --show-toplevel 2>$null)
Need ($LASTEXITCODE -eq 0 -and $root -and
  [IO.Path]::GetFullPath(([string]$root).Trim()).TrimEnd('\','/') -ieq $source.TrimEnd('\','/')) 'not a clean separate Git root'
$head=(& git -C $source rev-parse HEAD 2>$null)
Need ($LASTEXITCODE -eq 0 -and $head -and ([string]$head).Trim() -ceq $ExpectedSourceSha) 'source Git HEAD differs from reviewed release'
$uncommitted=@(& git -C $source status --porcelain --untracked-files=normal 2>$null | Where-Object {$_})
Need ($LASTEXITCODE -eq 0 -and $uncommitted.Count -eq 0) 'independent source checkout dirty'

# Select *tracked code only*. This intentionally includes its full existing
# paper_evaluator and market_data Python dependencies rather than a handpicked
# incomplete subset pretending to be a bootable V3 writer. No .env, database,
# secrets, logs, user state, new daemon or Task definitions are imported.
$bundle='research/v3/v3-experimental-paper-all-lessons-bundle-20261011.json'
$relay='supabase/functions/v3-paper-evidence-relay/index.ts'
# The existing evaluator and V3 model path import build_context here.
# Root module must be pinned alongside its paper_evaluator package.
$coreSupport='paper_context.py'
$operatorSource=@(
 'tools/minipc-runtime-supervisor.ps1',
 'tools/check-minipc-v3-physical-writer-readiness.ps1',
 'tools/minipc-v3-paper-cutover-operator-INACTIVE.ps1'
)
$tracked=@(& git -C $source ls-files --cached -- paper_evaluator market_data $coreSupport $bundle $relay $operatorSource 2>$null)
Need ($LASTEXITCODE -eq 0) 'tracked source inventory unavailable'
$selected=@($tracked | Where-Object {
  $_ -cmatch '^(paper_evaluator|market_data)/[A-Za-z0-9_]+\.py$' -or
  $_ -ceq $coreSupport -or $_ -ceq $bundle -or $_ -ceq $relay -or $_ -cin $operatorSource
} | Sort-Object -Unique)
$must=@(
 'paper_evaluator/v3_paper_minipc_one_candidate_v1.py',
 'paper_evaluator/v3_paper_minipc_selective_tick_v1.py',
 'paper_evaluator/v3_paper_cloud_receipt_sync_v1.py',
 'paper_evaluator/v3_paper_shared_candidate_intake_plan_v1.py',
 'paper_evaluator/v3_paper_existing_owner_source_bridge_v1.py',
 'paper_evaluator/v3_paper_intake_receipt_stage_v1.py',
 'paper_evaluator/v3_paper_signed_source_journal_stage_v1.py',
 'paper_evaluator/v3_paper_single_writer_preflight_v1.py',
 'paper_evaluator/v3_paper_minipc_native_launcher_v1.py',
 'market_data/__init__.py',
 $coreSupport,$bundle,$relay
) + $operatorSource
foreach($required in $must){Need ($selected -ccontains $required) 'required tracked V3 dependency absent'}
Need ($selected.Count -ge 20 -and $selected.Count -le 350) 'source allowlist count outside bounded range'

$stageParent=Join-Path $trading 'Staging'
Need (Test-Path -LiteralPath $stageParent -PathType Container) 'existing Staging parent missing'
Need (-not [bool]((Get-Item -LiteralPath $stageParent -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) 'linked Staging parent'
$target=Join-Path $stageParent ('V3Paper-INACTIVE-'+$ExpectedSourceSha.Substring(0,12))
Need (-not (Test-Path -LiteralPath $target)) 'stage target exists: no overwrite or automatic retry'
$manifest=@(
 foreach($rel in $selected){
  $file=Join-Path $source ($rel.Replace('/','\'))
  Need (IsUnder $file $source) 'source path escaped checkout'
  $folder=Split-Path -Parent $file
  Need (-not [bool]((Get-Item -LiteralPath $folder -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) 'linked source folder'
  [pscustomobject]@{
   relative_path=$rel
   sha256=(Fingerprint $file)
  }
 }
)
$report=[ordered]@{
  kind='V3_PAPER_INACTIVE_ISOLATED_SOURCE_STAGE_V1'
  status='READ_ONLY_SOURCE_PREFLIGHT_PASS_NOT_STAGED'
  source_git_sha=$ExpectedSourceSha
  target_directory=(Split-Path $target -Leaf)
  tracked_code_files=$manifest.Count
  source_manifest=$manifest
  source_only=$true
  original_v2r4_unchanged=$true
  task_changes=$false
  supervisor_restart=$false
  model_calls=0
  cloud_cas_performed=$false
  cloud_edge_deployed=$false
  release_proofs_credited=0
  v3_writer_installed=$false
  v3_paper_activated=$false
  real_money_actions=$false
}
if(-not $Stage){
  $report | ConvertTo-Json -Depth 7
  return
}
Need ($Confirm -ceq 'V3_SOURCE_ONLY_INACTIVE_NO_TASKS') 'independent explicit source-only staging confirmation required'
# ONLY a new directory under Staging. Do not touch repos, Runtime,
# Research, backups, the original V2R4 tasks, Secrets, or the relay.
New-Item -ItemType Directory -Path $target -ErrorAction Stop | Out-Null
foreach($item in $manifest){
  $relative=[string]$item.relative_path
  $origin=Join-Path $source ($relative.Replace('/','\'))
  $destination=Join-Path $target ($relative.Replace('/','\'))
  $parent=Split-Path $destination -Parent
  if(-not (Test-Path -LiteralPath $parent -PathType Container)){
    New-Item -ItemType Directory -Path $parent -Force -ErrorAction Stop | Out-Null
  }
  Copy-Item -LiteralPath $origin -Destination $destination -ErrorAction Stop
  Need ((Fingerprint $destination) -ceq [string]$item.sha256) 'staged source checksum mismatch'
}
$report.status='STAGED_INACTIVE_CODE_ONLY_NOT_INSTALLED'
[IO.File]::WriteAllText(
  (Join-Path $target 'v3-paper-inactive-source-manifest.json'),
  (($report | ConvertTo-Json -Depth 7)+[Environment]::NewLine),
  [Text.UTF8Encoding]::new($false)
)
$report | ConvertTo-Json -Depth 7
