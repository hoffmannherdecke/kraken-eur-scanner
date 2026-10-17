# Administrator-only one-time installation of LOCAL, fail-closed runner job hook.
# No runner service activation and no recurring fee/task; rollback: -Remove.
param(
  [ValidatePattern('^[a-f0-9]{40}$')]
  [string]$ApprovedPublicMainSha = '',
  [switch]$Remove
)
$ErrorActionPreference = 'Stop'
$serviceName = 'actions.runner.hoffmannherdecke-kraken-readonly-bridge.MINI-PC-CryptoSupport'
$runnerRoot = 'C:\CryptoSupport\actions-runner'
$guardDir = 'C:\ProgramData\CryptoSupportGuard'
$hookPath = Join-Path $guardDir 'pre_job.ps1'
$pinPath = Join-Path $guardDir 'approved-private-workflow-sha.txt'
$workflowSha = '28bdddccd7d917151958c4b64461dc6289e71eca'
$varName = 'ACTIONS_RUNNER_HOOK_JOB_STARTED'
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw 'INSTALL_BLOCK: run only in administrator PowerShell'
}
$svc = Get-CimInstance Win32_Service -Filter "Name='$serviceName'"
if ($null -eq $svc -or $svc.State -ne 'Stopped' -or
    $svc.StartMode -ne 'Disabled' -or
    $svc.StartName -ne '.\CryptoSupportSvc') {
  throw 'INSTALL_BLOCK: runner must be Stopped/Disabled as CryptoSupportSvc'
}
if ($Remove) {
  $existing = [Environment]::GetEnvironmentVariable($varName,'Machine')
  if ($existing -and $existing -cne $hookPath) {
    throw 'UNINSTALL_BLOCK: other system hook configured'
  }
  if ($existing -ceq $hookPath) {
    [Environment]::SetEnvironmentVariable($varName,$null,'Machine')
  }
  if (Test-Path -LiteralPath $guardDir -PathType Container) {
    Remove-Item -LiteralPath $guardDir -Recurse -Force
  }
  Write-Host 'LOCAL_PREJOB_GUARD_REMOVED; RUNNER_REMAINS_DISABLED'
  return
}
if (-not $ApprovedPublicMainSha) {
  throw 'INSTALL_BLOCK: reviewed protected main source SHA is mandatory'
}
if (-not (Test-Path -LiteralPath $runnerRoot -PathType Container)) {
  throw 'INSTALL_BLOCK: original runner directory missing'
}
if (Test-Path -LiteralPath $guardDir) {
  throw 'INSTALL_BLOCK: guard directory exists; no overwrite'
}
if ([Environment]::GetEnvironmentVariable($varName,'Machine')) {
  throw 'INSTALL_BLOCK: other machine-level runner hook already present'
}
$dotEnv = Join-Path $runnerRoot '.env'
if (Test-Path -LiteralPath $dotEnv -PathType Leaf) {
  if (Select-String -LiteralPath $dotEnv -Pattern '^\s*ACTIONS_RUNNER_HOOK_JOB_STARTED\s*=' -Quiet) {
    throw 'INSTALL_BLOCK: runner dotenv already overrides job-start hook'
  }
}
$svcSid = (New-Object Security.Principal.NTAccount('MINI-PC','CryptoSupportSvc')).Translate(
  [Security.Principal.SecurityIdentifier]).Value
New-Item -Path $guardDir -ItemType Directory -ErrorAction Stop | Out-Null
try {
  & icacls.exe $guardDir /inheritance:r | Out-Null
  if ($LASTEXITCODE -ne 0) { throw 'INSTALL_BLOCK: inheritance removal failed' }
  & icacls.exe $guardDir /grant:r '*S-1-5-18:(OI)(CI)(F)' '*S-1-5-32-544:(OI)(CI)(F)' ("*$svcSid" + ':(OI)(CI)(RX)') | Out-Null
  if ($LASTEXITCODE -ne 0) { throw 'INSTALL_BLOCK: protected directory ACL failed' }
  # Fetch exactly the owner-approved, Git-immutable public main source.
  $url = "https://raw.githubusercontent.com/hoffmannherdecke/kraken-eur-scanner/$ApprovedPublicMainSha/tools/minipc_runner_guard/pre_job.ps1"
  Invoke-WebRequest -Uri $url -UseBasicParsing -OutFile $hookPath -ErrorAction Stop
  $content = [IO.File]::ReadAllText($hookPath)
  if (-not $content.StartsWith('# MINI-PC protected local GitHub runner pre-job gate, v1.')) {
    throw 'INSTALL_BLOCK: immutable downloaded source header mismatch'
  }
  $tokens = $null
  $errors = $null
  [void][Management.Automation.Language.Parser]::ParseFile($hookPath,[ref]$tokens,[ref]$errors)
  if (@($errors).Count -ne 0) { throw 'INSTALL_BLOCK: source parse error' }
  [IO.File]::WriteAllText($pinPath, $workflowSha + [Environment]::NewLine)
  [Environment]::SetEnvironmentVariable($varName,$hookPath,'Machine')
  if ([Environment]::GetEnvironmentVariable($varName,'Machine') -cne $hookPath) {
    throw 'INSTALL_BLOCK: hook machine environment setting missing'
  }
  $check = Get-CimInstance Win32_Service -Filter "Name='$serviceName'"
  if ($check.State -ne 'Stopped' -or $check.StartMode -ne 'Disabled') {
    throw 'INSTALL_BLOCK: runner state changed unexpectedly'
  }
  Write-Host 'LOCAL_PREJOB_GUARD_INSTALLED; PRIVATE_WORKFLOW_PINNED; RUNNER_STILL_STOPPED_DISABLED'
} catch {
  [Environment]::SetEnvironmentVariable($varName,$null,'Machine')
  Remove-Item -LiteralPath $guardDir -Recurse -Force -ErrorAction SilentlyContinue
  throw
}
