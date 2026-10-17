param(
  [Parameter(Mandatory=$true)][string]$SourceRoot,
  [string]$TradingRoot=(Join-Path $env:USERPROFILE 'Trading'),
  [switch]$Stage,
  [string]$Confirm=''
)
# Issue353 / PR357+360: read-only preflight unless explicitly staged.
# NOT a Paper/Windows task installer, source sync, or release authorization.
$ErrorActionPreference='Stop'
$pin='c8f37da865314ac91d36c786b66d107aad4a28d1'
$trading=[IO.Path]::GetFullPath($TradingRoot)
$source=[IO.Path]::GetFullPath($SourceRoot)
$oldCandidate=Join-Path $trading 'Runtime\v2r4-paper-stage-d8b35a8ec2e6\v2r4-paper-local-runtime.py'
$oldWait=Join-Path $trading 'Staging\v2r4-wait-pr326-isolated-c660ebb87a39'
$target=Join-Path $trading ('Staging\v2r4-cache-inert-'+$pin.Substring(0,12))

function Need([bool]$yes,[string]$why) {
  if(-not $yes){throw ('CACHE_STAGE_BLOCKED: '+$why)}
}
function Hash([string]$path) {
  Need (Test-Path -LiteralPath $path -PathType Leaf) ('Missing '+(Split-Path $path -Leaf))
  $item=Get-Item -LiteralPath $path -Force
  Need (-not [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) ('Linked file '+$item.Name)
  (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToUpperInvariant()
}
function VerifyTask([string]$name,[string]$expected) {
  $task=Get-ScheduledTask -TaskName $name -ErrorAction Stop
  Need ([string]$task.State -eq 'Running') ('Not Running '+$name)
  Need (@($task.Actions).Count -eq 1) ('Unexpected actions '+$name)
  Need ([string]$task.Principal.UserId -in @('SYSTEM','NT AUTHORITY\SYSTEM','S-1-5-18')) ('Owner changed '+$name)
  # Match against actual argument string WITHOUT printing it (secrets possible).
  $arguments=([string]$task.Actions[0].Arguments).Replace('/','\').ToLowerInvariant()
  Need ($arguments.Contains($expected.ToLowerInvariant())) ('Task original source changed '+$name)
}
Need (Test-Path -LiteralPath $source -PathType Container) 'Independent source missing'
Need (Test-Path -LiteralPath $trading -PathType Container) 'Trading root missing'
Need ($source -ine (Join-Path $trading 'Repos\kraken-eur-scanner')) 'Never update/use dirty original repository'
Need (-not ($source.StartsWith((Split-Path $oldCandidate -Parent),[StringComparison]::OrdinalIgnoreCase))) 'Refuse original Candidate stage as source'
Need (-not ($source.StartsWith($oldWait,[StringComparison]::OrdinalIgnoreCase))) 'Refuse original WAIT stage as source'
$head=(& git -C $source rev-parse HEAD 2>$null)
Need ($LASTEXITCODE -eq 0 -and $head -and ([string]$head).Trim() -ceq $pin) 'Source is not exact reviewed PR360 merge'
$root=(& git -C $source rev-parse --show-toplevel 2>$null)
Need ($LASTEXITCODE -eq 0 -and $root -and [IO.Path]::GetFullPath(([string]$root).Trim()) -ieq $source) 'Source is not repository root'
$changed=@(& git -C $source status --porcelain --untracked-files=normal 2>$null | Where-Object { $_ })
Need ($LASTEXITCODE -eq 0 -and $changed.Count -eq 0) 'Pinned checkout is dirty'
$oldCandidateHash=Hash $oldCandidate
Need ($oldCandidateHash.StartsWith('8371CAB2D7D18F96')) 'Original Candidate changed'
Need ((Hash (Join-Path $oldWait 'v2r4_wait_runtime.py')) -ceq 'C84533E1042C9D89D6F6EDC31DD22DE6DD3AB3B7AAE2B202EF344495A72BA6A2') 'Original PR326 WAIT changed'
Need ((Hash (Join-Path $oldWait 'v2r4_wait_watcher.py')) -ceq '9EEE3F9CA8E669AD8DA690DA7A2C53E781EE618594783D08A50FCD5623F670BD') 'Original PR326 watcher changed'
Need ((Hash (Join-Path $oldWait 'wait_launcher.py')) -ceq 'C5E43D62976BDF2079A3A0402E57658ABA8A33D427B0CF0D56737565B84DD51D') 'Original PR326 launcher changed'
VerifyTask 'CryptoMiniPC-V2R4PaperCandidates' $oldCandidate
VerifyTask 'CryptoMiniPC-V2R4PaperWait' (Join-Path $oldWait 'wait_launcher.py')

# Only two new source modules. Preserve exactly the existing PR326 launcher
# and dependent watcher/public-budget code. Never copy private state or keys.
$files=@(
  @{path=(Join-Path $source 'tools\v2r4-paper-local-runtime.py');dest='candidate\v2r4-paper-local-runtime.py';role='REVIEWED_CACHE'},
  @{path=(Join-Path $source 'paper_evaluator\v2r4_wait_runtime.py');dest='wait\v2r4_wait_runtime.py';role='REVIEWED_CACHE'},
  @{path=(Join-Path $oldWait 'wait_launcher.py');dest='wait\wait_launcher.py';role='ORIGINAL_PR326'},
  @{path=(Join-Path $oldWait 'v2r4_wait_watcher.py');dest='wait\v2r4_wait_watcher.py';role='ORIGINAL_PR326'},
  @{path=(Join-Path $oldWait 'kraken_public_budget.py');dest='wait\kraken_public_budget.py';role='ORIGINAL_PR326'}
)
$inventory=@(foreach($f in $files){
  [ordered]@{file=$f.dest;role=$f.role;sha256=(Hash $f.path)}
})
Need (-not (Test-Path -LiteralPath $target)) 'Stage target exists; refuse repeat/overwrite'
$report=[ordered]@{
  kind='V2R4_CPU_CACHE_INERT_STAGE_V1'
  status='READ_ONLY_PREFLIGHT_PASS_NOT_STAGED'
  source_git_sha=$pin
  original_candidate_sha256=$oldCandidateHash
  target_name=(Split-Path $target -Leaf)
  files=$inventory
  no_control_or_keys=$true
  task_mutations=$false
  runtime_activated=$false
  rollback_and_host_cpu_proof='PENDING'
}
if(-not $Stage) {
  $report | ConvertTo-Json -Depth 6
  return
}
Need ($Confirm -ceq 'INERT_CPU_CACHE_STAGE_ONLY') 'Stage requires exact inert-only confirmation'
# A distinct directory: no active stage, task, state, secret or network mutations.
New-Item -ItemType Directory -Path $target -ErrorAction Stop | Out-Null
foreach($f in $files){
  $dest=Join-Path $target $f.dest
  $parent=Split-Path $dest -Parent
  if(-not (Test-Path -LiteralPath $parent)) {
    New-Item -ItemType Directory -Path $parent -ErrorAction Stop | Out-Null
  }
  Copy-Item -LiteralPath $f.path -Destination $dest -ErrorAction Stop
  Need ((Hash $dest) -ceq (Hash $f.path)) ('Copy integrity failed '+$f.dest)
}
foreach($forbidden in @('paper_runtime_control.json','api-key.txt','wait\paper_runtime_control.json','wait\api-key.txt','candidate\paper_runtime_control.json','candidate\api-key.txt')){
  Need (-not (Test-Path -LiteralPath (Join-Path $target $forbidden))) 'Accidental runtime control/secret'
}
$report.status='STAGED_INERT_NOT_EXECUTED'
[IO.File]::WriteAllText(
  (Join-Path $target 'cpu-cache-stage-manifest.json'),
  ($report | ConvertTo-Json -Depth 6)+[Environment]::NewLine,
  [Text.UTF8Encoding]::new($false)
)
$report | ConvertTo-Json -Depth 6
