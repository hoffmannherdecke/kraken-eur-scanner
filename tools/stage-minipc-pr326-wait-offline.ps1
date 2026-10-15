param(
  [string]$TradingRoot=(Join-Path $env:USERPROFILE 'Trading'),
  [Parameter(Mandatory=$true)][string]$ExpectedSourceSha,
  [switch]$Stage,
  [string]$Confirm=''
)
# PR326 is an INACTIVE code-copy stage, not an installer.
# Never touch the active PR291 package, live tasks, paper states or secrets.
$ErrorActionPreference='Stop'
if($ExpectedSourceSha -notmatch '^[a-f0-9]{40}$'){throw 'Exact 40-character PR source SHA required'}
$source=Split-Path -Parent $PSScriptRoot
$actual=(& git -C $source rev-parse HEAD)
if($LASTEXITCODE -ne 0 -or [string]$actual.Trim() -cne $ExpectedSourceSha){
  throw 'Detached source checkout does not match pinned PR326 SHA'
}
$previous=Join-Path $TradingRoot 'Staging\v2r4-wait-pr291-isolated'
$target=Join-Path $TradingRoot ('Staging\v2r4-wait-pr326-isolated-'+$ExpectedSourceSha.Substring(0,12))
$baseline=@{
  'wait_launcher.py'='C5E43D62976BDF2079A3A0402E57658ABA8A33D427B0CF0D56737565B84DD51D'
  'v2r4_wait_runtime.py'=(Get-FileHash -LiteralPath 'D:\Krypto-Sicherungen\PR326-VORHER-20261015-205743\v2r4_wait_runtime.py' -Algorithm SHA256).Hash
  'v2r4_wait_watcher.py'='38F3843968F1A46D5A2B3F15C50743FED47D97E68C46198574DBD39BF501FD3D'
}
foreach($name in $baseline.Keys){
  $file=Join-Path $previous $name
  if(-not (Test-Path -LiteralPath $file -PathType Leaf)){throw "Missing original PR291 $name"}
  if((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -ine $baseline[$name]){
    throw "Original PR291 hash drift: $name"
  }
}
$python=Join-Path $TradingRoot 'Runtime\kraken-eur-scanner-venv\Scripts\python.exe'
if(-not (Test-Path -LiteralPath $python -PathType Leaf)){throw 'Python environment not found'}
$overlay=[ordered]@{
  'v2r4_wait_runtime.py'='paper_evaluator\v2r4_wait_runtime.py'
  'v2r4_wait_watcher.py'='paper_evaluator\v2r4_wait_watcher.py'
  'kraken_public_budget.py'='market_data\kraken_public_budget.py'
}
foreach($rel in $overlay.Values){
  if(-not (Test-Path -LiteralPath (Join-Path $source $rel) -PathType Leaf)){
    throw "Missing pinned PR326 module $rel"
  }
}
$files=@(Get-ChildItem -LiteralPath $previous -File -Filter '*.py')
if($files.Count -lt 3){throw 'PR291 source package unexpectedly incomplete'}
foreach($f in $files){
  if($f.Attributes -band [IO.FileAttributes]::ReparsePoint){
    throw 'Refuse a linked PR291 file'
  }
}
if(Test-Path -LiteralPath $target){throw 'Do not overwrite existing offline stage'}
if(-not $Stage){
  Write-Output 'PR326_OFFLINE_PREFLIGHT_PASS'
  Write-Output "PR326_SOURCE_SHA=$ExpectedSourceSha"
  Write-Output "PR291_PYTHON_FILES=$($files.Count)"
  Write-Output 'ACTIVE_RUNTIME_UNCHANGED=True'
  exit 0
}
if($Confirm -cne 'INACTIVE_OFFLINE_STAGE_ONLY'){throw 'Explicit offline-only stage confirmation required'}
New-Item -ItemType Directory -Path $target -ErrorAction Stop | Out-Null
$manifestFiles=@()
foreach($f in $files){
  $to=Join-Path $target $f.Name
  Copy-Item -LiteralPath $f.FullName -Destination $to -ErrorAction Stop
  $hash=(Get-FileHash -LiteralPath $to -Algorithm SHA256).Hash
  if($hash -ine (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash){
    throw "Copied PR291 bytes differ: $($f.Name)"
  }
  $manifestFiles+=@([pscustomobject]@{file=$f.Name;origin='PR291';sha256=$hash})
}
foreach($name in $overlay.Keys){
  $from=Join-Path $source $overlay[$name]
  $to=Join-Path $target $name
  Copy-Item -LiteralPath $from -Destination $to -Force -ErrorAction Stop
  $hash=(Get-FileHash -LiteralPath $to -Algorithm SHA256).Hash
  if($hash -ine (Get-FileHash -LiteralPath $from -Algorithm SHA256).Hash){
    throw "Copied PR326 bytes differ: $name"
  }
  $manifestFiles+=@([pscustomobject]@{file=$name;origin='PR326';sha256=$hash})
}
if((Get-FileHash -LiteralPath (Join-Path $target 'wait_launcher.py') -Algorithm SHA256).Hash -ine $baseline['wait_launcher.py']){
  throw 'New stage launcher was unexpectedly altered'
}
foreach($name in @('paper_runtime_control.json','api-key.txt')){
  if(Test-Path -LiteralPath (Join-Path $target $name)){throw "Forbidden control or secret: $name"}
}
& $python -m py_compile (Join-Path $target 'wait_launcher.py') (Join-Path $target 'v2r4_wait_runtime.py') (Join-Path $target 'v2r4_wait_watcher.py') (Join-Path $target 'kraken_public_budget.py')
if($LASTEXITCODE -ne 0){throw 'Offline Python compile failed'}
[ordered]@{
  kind='PR326_INACTIVE_WAIT_STAGE_V1'
  status='ISOLATED_CODE_ONLY_NOT_INSTALLED'
  pinned_git_sha=$ExpectedSourceSha
  original_launcher_sha256=$baseline['wait_launcher.py']
  original_pr291_unchanged=$true
  paper_only=$true
  real_money_actions=$false
  progress_opt_in=$false
  supervisor_opt_in=$false
  tasks_changed=$false
  source_import_system_and_rollback_gate='PENDING'
  files=@($manifestFiles)
} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $target 'pr326-stage-manifest.json') -Encoding UTF8
'=== PR326 OFFLINE STAGE ==='
'STAGING=PASS'
"PINNED_SOURCE_SHA=$ExpectedSourceSha"
"ORIGINAL_FILES_COPIED=$($files.Count)"
"OVERLAY_FILES_VERIFIED=$($overlay.Count)"
'PYTHON_COMPILE=PASS'
'ORIGINAL_PR291_UNCHANGED=True'
'WINDOWS_TASKS_UNCHANGED=True'
'PROGRESS_OPT_IN=False'
'SUPERVISOR_OPT_IN=False'
'NEXT_GATE=ISOLATED_IMPORT_AND_SYSTEM_TEST'
"STAGE_PATH=$target"
'=== END ==='
