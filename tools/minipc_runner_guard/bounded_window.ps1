# MINI-PC CryptoSupport bounded availability task, v1.
# One SYSTEM scheduled invocation opens a short guarded Windows service window.
# Not a runner, agent, order service or self-updating script.
$ErrorActionPreference = 'Stop'
$serviceName = 'actions.runner.hoffmannherdecke-kraken-readonly-bridge.MINI-PC-CryptoSupport'
$root = 'C:\ProgramData\CryptoSupportGuard'
$hook = Join-Path $root 'pre_job.ps1'
$pinPath = Join-Path $root 'approved-private-workflow-sha.txt'
$approvedPrivateSha = '92007df015f45ddf2cb8a296e00e0f592a883606'
$runnerDir = 'C:\CryptoSupport\actions-runner'
$serviceKey = "HKLM:\SYSTEM\CurrentControlSet\Services\$serviceName"
$workerName = 'Runner.Worker.exe'
$windowSeconds = 660 # eleven minutes; workflow has its own eight-minute max
$drainSeconds = 480 # leave up to eight minutes for an already running worker
$started = $false

function Assert-Window([bool]$condition,[string]$reason) {
  if (-not $condition) { throw "WINDOW_BLOCK:$reason" }
}

$me = [Security.Principal.WindowsIdentity]::GetCurrent()
Assert-Window ($me.User.Value -ceq 'S-1-5-18') 'task_not_system'
$svc = Get-CimInstance Win32_Service -Filter "Name='$serviceName'" -ErrorAction Stop
Assert-Window ($null -ne $svc) 'service_missing'
Assert-Window ($svc.State -ceq 'Stopped' -and $svc.StartMode -ceq 'Disabled') 'service_not_safe'
Assert-Window ($svc.StartName -ceq '.\CryptoSupportSvc') 'wrong_service_user'
Assert-Window (Test-Path -LiteralPath $hook -PathType Leaf) 'local_hook_missing'
Assert-Window (Test-Path -LiteralPath $pinPath -PathType Leaf) 'local_pin_missing'
Assert-Window (([IO.File]::ReadAllText($pinPath)).Trim() -ceq $approvedPrivateSha) 'local_pin_mismatch'
Assert-Window ([Environment]::GetEnvironmentVariable('ACTIONS_RUNNER_HOOK_JOB_STARTED','Machine') -ceq $hook) 'machine_hook_mismatch'
$serviceEnvironment = @((Get-ItemProperty -LiteralPath $serviceKey -ErrorAction Stop).Environment)
Assert-Window ($serviceEnvironment -ccontains 'PSExecutionPolicyPreference=Bypass') 'runner_process_policy_missing'
Assert-Window (Test-Path -LiteralPath $runnerDir -PathType Container) 'original_runner_missing'

try {
  Set-Service -Name $serviceName -StartupType Manual -ErrorAction Stop
  Start-Service -Name $serviceName -ErrorAction Stop
  $started = $true
  Set-Service -Name $serviceName -StartupType Disabled -ErrorAction Stop
  Write-Output 'WINDOW_OPEN: pinned low-privilege runner service started; Windows start mode DISABLED'
  Start-Sleep -Seconds $windowSeconds
  $polls = [int][math]::Ceiling($drainSeconds / 10)
  for ($i = 0; $i -lt $polls; $i++) {
    $workers = @(Get-CimInstance Win32_Process -Filter "Name='$workerName'" -ErrorAction Stop |
      Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith(
        $runnerDir + '\', [StringComparison]::OrdinalIgnoreCase) })
    if ($workers.Count -eq 0) { break }
    Start-Sleep -Seconds 10
  }
  Write-Output 'WINDOW_CLOSE: after bounded worker-drain'
}
finally {
  # Always attempt a stop even if starting or the read-only worker poll fails.
  try { Stop-Service -Name $serviceName -ErrorAction Stop } catch {
    Write-Output 'WINDOW_STOP_FAILED: manual host inspection needed'
  }
  try { Set-Service -Name $serviceName -StartupType Disabled -ErrorAction Stop } catch {
    Write-Output 'WINDOW_DISABLE_FAILED: manual host inspection needed'
  }
  $final = Get-CimInstance Win32_Service -Filter "Name='$serviceName'" -ErrorAction Stop
  if ($final.State -cne 'Stopped' -or $final.StartMode -cne 'Disabled') {
    throw 'WINDOW_FINAL_CHECK_FAILED: service not Stopped/Disabled'
  }
  Write-Output 'WINDOW_SAFE_PAUSE_ACK: Stopped Disabled; other local tasks unchanged'
}
