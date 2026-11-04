param(
  [string]$TradingRoot=(Join-Path $env:USERPROFILE 'Trading'),
  [string]$SourceRoot='',
  [switch]$Stage,
  [string]$Confirm=''
)
# Issue #353 / #99 / PR #666: scoped, immutable *inert* candidate code stage.
# Does not register/stop/start/rebind tasks or alter Cloud, series, or paper state.
# Productive task switch remains a separately approved release operation.
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$pin='b4c751fbe9df468360a7683961aaf46228c3b944'
$oldRel='Runtime\v2r4-paper-stage-d8b35a8ec2e6'
$oldFile='v2r4-paper-local-runtime.py'
$oldSha='8371CAB2D7D18F9651E604DBAB88768F77B2DFF5EB88565122858F6428DC50D0'
$series='PAPER-V2R4-20261009T110135Z'
$root=[IO.Path]::GetFullPath($TradingRoot)
if(-not $SourceRoot){$SourceRoot=Join-Path $root 'Repos\kraken-eur-scanner'}
$source=[IO.Path]::GetFullPath($SourceRoot)
$old=Join-Path $root $oldRel
$target=Join-Path $root ('Runtime\v2r4-pr666-inert-'+$pin.Substring(0,12))
$sourceFile=Join-Path $source 'tools\v2r4-paper-local-runtime.py'
$targetFile=Join-Path $target $oldFile
$manifest=Join-Path $target 'pr666-immutable-stage-manifest.json'
function Need([bool]$Ok,[string]$Message){if(-not $Ok){throw ('PR666_STAGE_HOLD: '+$Message)}}
function Hash([string]$Path){
  Need (Test-Path -LiteralPath $Path -PathType Leaf) ('missing file '+$Path)
  $item=Get-Item -LiteralPath $Path -Force
  Need (-not [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) 'linked file'
  (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToUpperInvariant()
}
Need (Test-Path -LiteralPath $source -PathType Container) 'reviewed source directory absent'
Need (Test-Path -LiteralPath $old -PathType Container) 'frozen original runtime absent'
Need ((Hash (Join-Path $old $oldFile)) -ceq $oldSha) 'original candidate bytes differ'
$head=(& git -C $source rev-parse HEAD 2>$null)
Need ($LASTEXITCODE -eq 0 -and ([string]$head).Trim() -ceq $pin) 'source commit mismatch'
$top=(& git -C $source rev-parse --show-toplevel 2>$null)
Need ($LASTEXITCODE -eq 0 -and [IO.Path]::GetFullPath(([string]$top).Trim()) -ieq $source) 'source must be checkout root'
$dirty=@(& git -C $source status --porcelain --untracked-files=normal 2>$null | Where-Object { $_ })
Need ($LASTEXITCODE -eq 0 -and $dirty.Count -eq 0) 'source checkout dirty'
$newHash=Hash $sourceFile
Need ($newHash -cne $oldSha) 'no PR666 candidate delta'
$taskNames=@('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperLifecycle')
$tasks=[ordered]@{}
foreach($name in $taskNames){
  $task=Get-ScheduledTask -TaskName $name -ErrorAction Stop
  Need (@($task.Actions).Count -eq 1) ('unexpected task actions '+$name)
  Need ([string]$task.Principal.UserId -in @('SYSTEM','NT AUTHORITY\SYSTEM','S-1-5-18')) ('task principal drift '+$name)
  $args=[string]$task.Actions[0].Arguments
  Need ($args.Replace('/','\').Contains((Join-Path $old $oldFile))) ('task not bound to frozen candidate code: '+$name)
  $tasks[$name]=[ordered]@{
    original_action_sha256=([BitConverter]::ToString(
      ([Security.Cryptography.SHA256]::Create()).ComputeHash([Text.Encoding]::UTF8.GetBytes(
        ([string]$task.Actions[0].Execute + [char]10 + $args + [char]10 + [string]$task.Actions[0].WorkingDirectory)
      ))).Replace('-','').ToLowerInvariant()
    state=[string]$task.State
  }
}
# Unrelated WAIT and CloudSync are not altered or included as release inputs.
$report=[ordered]@{
  kind='V2R4_PR666_CANDIDATES_LIFECYCLE_INERT_STAGE_V1'
  status='READ_ONLY_READY_NOT_STAGED'
  commit=$pin
  series_id=$series
  predecessor_file_sha256=$oldSha.ToLowerInvariant()
  successor_file_sha256=$newHash.ToLowerInvariant()
  predecessor_runtime=$old
  inert_runtime=$target
  task_action_evidence=$tasks
  tasks_mutated=$false
  cloud_mutated=$false
  series_mutated=$false
  productive_install=$false
  next='SEPARATE_GUARDED_TASK_SWITCH_APPROVAL_AND_IMPLEMENTATION'
}
Need (-not (Test-Path -LiteralPath $target)) 'target already exists; never overwrite or reuse'
if(-not $Stage){$report|ConvertTo-Json -Depth 8;return}
Need ($Confirm -ceq 'STAGE_PR666_INERT_ONLY') 'staging confirmation required'
# Never copy private data, runtime control, tokens or mutable state into the new stage.
# Only this one source file is new. It can be executed later with the original
# --app-root and --trading-root, but cannot become active by staging alone.
New-Item -ItemType Directory -Path $target -ErrorAction Stop|Out-Null
try {
  Copy-Item -LiteralPath $sourceFile -Destination $targetFile -ErrorAction Stop
  Need ((Hash $targetFile) -ceq $newHash) 'stage hash readback failed'
  $report.status='INERT_SINGLE_FILE_STAGED_NO_TASK_MUTATION'
  [IO.File]::WriteAllText($manifest,($report|ConvertTo-Json -Depth 8)+[Environment]::NewLine,[Text.UTF8Encoding]::new($false))
  Need ((Hash $targetFile) -ceq $newHash) 'post-manifest file changed'
  # This directory is single-purpose and must never be used as an app root.
  $report.manifest_sha256=(Hash $manifest).ToLowerInvariant()
} catch {throw ('PR666_INERT_STAGE_INCOMPLETE_NO_LIVE_CHANGE: '+$_.Exception.Message)}
$report|ConvertTo-Json -Depth 8
