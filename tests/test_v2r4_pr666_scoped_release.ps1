# Pure offline PR666 originalhost process/task-boundary regression.
# Extract only existing definitions; never execute the release script's entrypoint.
$ErrorActionPreference='Stop'
$src=Get-Content -LiteralPath (Join-Path $PSScriptRoot '..\tools\minipc-v2r4-pr666-inert-code-stage.ps1') -Raw
$begin=$src.IndexOf('function ActiveChildren {')
$end=$src.IndexOf('function Need-Admin {')
if($begin -lt 0 -or $end -le $begin){throw 'PR666_OFFLINE_FUNCTION_BOUNDARY_MISSING'}
Invoke-Expression ($src.Substring($begin,$end-$begin))
$old='C:\Trading\Runtime\v2r4-paper-stage-d8b35a8ec2e6'
$file='v2r4-paper-local-runtime.py'
$stageFile='C:\Trading\Runtime\v2r4-pr666-inert-b4c751fbe9df\v2r4-paper-local-runtime.py'
$script:Samples=@()
function Get-CimInstance {
  [CmdletBinding()]
  param([string]$ClassName)
  if($ClassName -ne 'Win32_Process'){throw 'Unexpected CIM query'}
  return $script:Samples
}
function Assert([bool]$value,[string]$why){if(-not $value){throw ('PR666_OFFLINE_ASSERT: '+$why)}}
function Proc([int]$processId,[string]$name,[string]$commandLine){
  [pscustomobject]@{ProcessId=$processId;Name=$name;CommandLine=$commandLine;CreationDate=[datetime]::UtcNow}
}
$script:Samples=@(
  (Proc 2001 'python.exe' ('python.exe "'+$old+'\v2r4-paper-local-runtime.py" --role candidates')),
  (Proc 2002 'python.exe' ('python.exe "'+$old+'\paper_evaluator\evaluate.py" --out ...')),
  (Proc 2003 'powershell.exe' 'powershell.exe -File C:\Trading\Repos\kraken-eur-scanner\tools\minipc-runtime-supervisor.ps1'),
  (Proc 2004 'python.exe' 'python.exe "C:\Trading\Staging\v2r4-wait-pr326\wait_launcher.py"')
)
$found=@(ActiveChildren)
Assert ($found.Count -eq 3) 'old candidate, evaluator and supervisor must be classified; WAIT excluded'
Assert (@($found|Where-Object {$_.ProcessId -eq 2004}).Count -eq 0) 'WAIT excluded from candidate shutdown'
$script:Samples=@((Proc 2005 'python.exe' 'python.exe "D:\unexpected\v2r4-paper-local-runtime.py" --role candidates'))
Assert (@(ActiveChildren).Count -eq 1) 'unreviewed candidate duplicate must be blocked'
$blocked=$false
try{Quiet 0}catch{if($_.Exception.Message -match 'PR666_HOLD'){ $blocked=$true }}
Assert $blocked 'non-quiesced candidate process cannot be released'
$script:Samples=@((Proc 2004 'python.exe' 'python.exe "C:\Trading\Staging\v2r4-wait-pr326\wait_launcher.py"'))
Quiet 0
$script:TaskState='Ready'
$script:StopCalls=0
function Task {
  param([string]$name)
  [pscustomobject]@{State=$script:TaskState}
}
function Stop-ScheduledTask {
  [CmdletBinding()]
  param([string]$TaskName)
  $script:StopCalls++
  $script:TaskState='Ready'
}
StopBounded 'FakeCandidate'
Assert ($script:StopCalls -eq 0) 'idle task must not be stopped'
$script:TaskState='Running'
StopBounded 'FakeCandidate'
Assert ($script:StopCalls -eq 1) 'running task must stop once'

# Exercise actual Windows PowerShell 5.1 top-level mode selection with StrictMode.
# Previous code raised PropertyNotFoundStrict for a single -Stage mode.
$operator=Join-Path $PSScriptRoot '..\tools\minipc-v2r4-pr666-inert-code-stage.ps1'
$missingRoot=Join-Path $env:TEMP ('pr667-absent-'+[guid]::NewGuid().ToString('N'))
if(Test-Path -LiteralPath $missingRoot){throw 'PR667_TEST_ROOT_EXISTS'}
$testDir=Join-Path $env:TEMP ('pr667-output-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testDir -ErrorAction Stop | Out-Null
try {
  function Invoke-ModeFixture([string[]]$modes) {
    $stdout=Join-Path $testDir 'stdout.txt'
    $stderr=Join-Path $testDir 'stderr.txt'
    $args=@('-NoProfile','-NonInteractive','-ExecutionPolicy','RemoteSigned',
            '-File',$operator,'-TradingRoot',$missingRoot)+$modes
    $p=Start-Process -FilePath 'powershell.exe' -ArgumentList $args -Wait -PassThru -NoNewWindow -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    return [pscustomobject]@{
      ExitCode=$p.ExitCode
      Text=((Get-Content -LiteralPath $stdout -Raw -ErrorAction SilentlyContinue) +
            (Get-Content -LiteralPath $stderr -Raw -ErrorAction SilentlyContinue))
    }
  }
  $single=Invoke-ModeFixture @('-Stage','-Confirm','STAGE_PR666_INERT_ONLY')
  Assert ($single.ExitCode -ne 0) 'nonexistent root must fail without task mutation'
  Assert ($single.Text -match 'Trading root missing') 'single Stage must pass mode gate and hold on missing root'
  Assert ($single.Text -notmatch 'PropertyNotFoundStrict') 'Windows PowerShell 5.1 scalar Count regression'
  $double=Invoke-ModeFixture @('-Stage','-Execute')
  Assert ($double.ExitCode -ne 0) 'conflicting switches must fail'
  Assert ($double.Text -match 'choose exactly one mode') 'conflicting mode must be blocked'
  Assert (-not (Test-Path -LiteralPath $missingRoot)) 'offline tests cannot create trading state'
} finally {
  Remove-Item -LiteralPath $testDir -Recurse -Force -ErrorAction SilentlyContinue
}
Write-Output 'PR666_POWERSHELL51_MODE_GATE_POSITIVE_NEGATIVE_PASS'
Write-Output 'PR666_OFFLINE_QUIESCENCE_POSITIVE_NEGATIVE_PASS'
