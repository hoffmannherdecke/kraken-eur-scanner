# MINI-PC CryptoSupport one-task availability installer (administrator only).
# Installs a DISABLED scheduled task by default, never autostarts a runner.
param(
  [ValidatePattern('^[a-f0-9]{40}$')]
  [string]$ApprovedPublicMainSha = '',
  [switch]$Remove
)
$ErrorActionPreference = 'Stop'
$taskName = 'CryptoSupport - Bounded Runner Window'
$serviceName = 'actions.runner.hoffmannherdecke-kraken-readonly-bridge.MINI-PC-CryptoSupport'
$root = 'C:\ProgramData\CryptoSupportGuard'
$hook = Join-Path $root 'pre_job.ps1'
$pinPath = Join-Path $root 'approved-private-workflow-sha.txt'
$window = Join-Path $root 'bounded_window.ps1'
$pin = '28bdddccd7d917151958c4b64461dc6289e71eca'

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw 'WINDOW_INSTALL_BLOCK: administrator required'
}
$svc = Get-CimInstance Win32_Service -Filter "Name='$serviceName'"
if (!$svc -or $svc.State -ne 'Stopped' -or $svc.StartMode -ne 'Disabled' -or
    $svc.StartName -ne '.\CryptoSupportSvc') {
  throw 'WINDOW_INSTALL_BLOCK: runner must be Stopped/Disabled before changes'
}
$currentTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($Remove) {
  if (!$currentTask) { throw 'WINDOW_REMOVE_BLOCK: scheduled task missing' }
  if ($currentTask.State -ne 'Disabled') {
    throw 'WINDOW_REMOVE_BLOCK: disable task and stop any active instance first'
  }
  Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction Stop
  if (Test-Path -LiteralPath $window -PathType Leaf) {
    Remove-Item -LiteralPath $window -Force -ErrorAction Stop
  }
  Write-Output 'WINDOW_TASK_REMOVED; RUNNER_STILL_STOPPED_DISABLED'
  return
}
if (!$ApprovedPublicMainSha) {
  throw 'WINDOW_INSTALL_BLOCK: protected main SHA is required'
}
if ($currentTask) { throw 'WINDOW_INSTALL_BLOCK: task already exists, never overwrite' }
if (Test-Path -LiteralPath $window) {
  throw 'WINDOW_INSTALL_BLOCK: local window file exists, never overwrite'
}
if (!(Test-Path -LiteralPath $root -PathType Container) -or
    !(Test-Path -LiteralPath $hook -PathType Leaf) -or
    !(Test-Path -LiteralPath $pinPath -PathType Leaf)) {
  throw 'WINDOW_INSTALL_BLOCK: existing protected pre-job gate missing'
}
$acl = Get-Acl -LiteralPath $root -ErrorAction Stop
if (!$acl.AreAccessRulesProtected) {
  throw 'WINDOW_INSTALL_BLOCK: guard directory ACL inheritance enabled'
}
if (([IO.File]::ReadAllText($pinPath)).Trim() -cne $pin) {
  throw 'WINDOW_INSTALL_BLOCK: incorrect approved private workflow SHA'
}
if ([Environment]::GetEnvironmentVariable('ACTIONS_RUNNER_HOOK_JOB_STARTED','Machine') -cne $hook) {
  throw 'WINDOW_INSTALL_BLOCK: local prejob hook is not configured'
}
$serviceKey = "HKLM:\SYSTEM\CurrentControlSet\Services\$serviceName"
$serviceEnv = @((Get-ItemProperty -LiteralPath $serviceKey).Environment)
if ($serviceEnv -cnotcontains 'PSExecutionPolicyPreference=Bypass') {
  throw 'WINDOW_INSTALL_BLOCK: runner-local execution policy missing'
}
$url = "https://raw.githubusercontent.com/hoffmannherdecke/kraken-eur-scanner/$ApprovedPublicMainSha/tools/minipc_runner_guard/bounded_window.ps1"
$created = $false
try {
  Invoke-WebRequest -Uri $url -UseBasicParsing -OutFile $window -ErrorAction Stop
  $created = $true
  $src = [IO.File]::ReadAllText($window)
  if (!$src.StartsWith('# MINI-PC CryptoSupport bounded availability task, v1.')) {
    throw 'WINDOW_INSTALL_BLOCK: source header did not match reviewed source'
  }
  $tokens = $null
  $errors = $null
  [void][Management.Automation.Language.Parser]::ParseFile($window,[ref]$tokens,[ref]$errors)
  if (@($errors).Count -ne 0) { throw 'WINDOW_INSTALL_BLOCK: invalid source syntax' }

  $powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
  $arguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + $window + '"'
  $action = New-ScheduledTaskAction -Execute $powershell -Argument $arguments
  # Choose 20m period because GitHub rejects event comments older than 10m.
  # Eleven-minute window leaves a maximum nine-minute offline interval.
  $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(20) -RepetitionInterval (New-TimeSpan -Minutes 20) -RepetitionDuration (New-TimeSpan -Days 3650)
  $settings = New-ScheduledTaskSettingsSet -Disable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 20)
  $account = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
  Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $account -Description 'Guarded temporary service availability for source-reviewed development jobs; no runtime/trading rights' -ErrorAction Stop | Out-Null

  $readback = Get-ScheduledTask -TaskName $taskName -ErrorAction Stop
  if ($readback.State -ne 'Disabled' -or $readback.Principal.UserId -notin @('SYSTEM','S-1-5-18')) {
    throw 'WINDOW_INSTALL_BLOCK: scheduler readback not disabled as SYSTEM'
  }
  $status = Get-CimInstance Win32_Service -Filter "Name='$serviceName'"
  if ($status.State -ne 'Stopped' -or $status.StartMode -ne 'Disabled') {
    throw 'WINDOW_INSTALL_BLOCK: service changed during installer'
  }
  Write-Output 'WINDOW_TASK_INSTALLED_DISABLED; RUNNER_STILL_STOPPED_DISABLED'
  Write-Output 'NO_UNATTENDED_WINDOW_ENABLED_BEFORE_FINAL_APPROVAL'
} catch {
  if ($created) {
    $candidate = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($candidate -and $candidate.State -eq 'Disabled') {
      Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $window -Force -ErrorAction SilentlyContinue
  }
  throw
}
