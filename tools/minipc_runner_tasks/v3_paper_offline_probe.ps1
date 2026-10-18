# MINIPC_REVIEWED_TASK_V1
# SHA-pinned bounded Windows support-runner OFFLINE unit test, not live Paper.
# Model, Kraken and Cloud are unittest stubs. No new schedule or writer.
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if ($identity.Name -notmatch '(?i)\\CryptoSupportSvc$' -or
    $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator) -or
    $env:RUNNER_NAME -cne 'MINI-PC-CryptoSupport') {
  throw 'V3_OFFLINE_PROBE_BLOCK: existing restricted Windows runner required'
}
if ([string]::IsNullOrWhiteSpace($env:GITHUB_WORKSPACE) -or
    [string]::IsNullOrWhiteSpace($env:RUNNER_TEMP) -or
    $env:MINIPC_TASK_SANDBOX -cne $env:RUNNER_TEMP) {
  throw 'V3_OFFLINE_PROBE_BLOCK: existing reviewed sandbox absent'
}
$workspace = [IO.Path]::GetFullPath($env:GITHUB_WORKSPACE).TrimEnd('\')
$repo = [IO.Path]::GetFullPath((Join-Path $workspace '_protected_main'))
if (-not $repo.StartsWith($workspace+[IO.Path]::DirectorySeparatorChar,
                           [StringComparison]::OrdinalIgnoreCase) -or
    -not (Test-Path -LiteralPath $repo -PathType Container) -or
    -not (Test-Path -LiteralPath (Join-Path $repo 'paper_evaluator\v3_paper_minipc_selective_tick_v1.py') -PathType Leaf) -or
    -not (Test-Path -LiteralPath (Join-Path $repo 'tests\test_v3_extended_reentry_handoff_regression.py') -PathType Leaf)) {
  throw 'V3_OFFLINE_PROBE_BLOCK: pinned protected checkout absent'
}
$sandbox = [IO.Path]::GetFullPath($env:RUNNER_TEMP)
if (-not (Test-Path -LiteralPath $sandbox -PathType Container) -or
    [bool]((Get-Item -LiteralPath $sandbox -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
  throw 'V3_OFFLINE_PROBE_BLOCK: unsafe temporary data root'
}
# A restricted Windows service account often has a smaller PATH than the
# interactive administrator. Only use an already present executable from PATH
# or a bounded machine-wide installation directory. Never search another
# user's profile, add PATH/ACL permissions, install software or elevate.
$python = $null
$useLauncher = $false
foreach ($name in @('python.exe', 'py.exe')) {
  $command = Get-Command -Name $name -CommandType Application -ErrorAction SilentlyContinue |
    Select-Object -First 1
  if ($null -ne $command -and
      -not [string]::IsNullOrWhiteSpace([string]$command.Source) -and
      (Test-Path -LiteralPath ([string]$command.Source) -PathType Leaf)) {
    $python = [string]$command.Source
    $useLauncher = ($name -ceq 'py.exe')
    break
  }
}
if ($null -eq $python) {
  # Fixed, nonrecursive machine-scoped fallback. No scanning administrator
  # home directories, APPDATA, Trading, Secrets or other user data.
  foreach ($version in @('Python314','Python313','Python312','Python311','Python310')) {
    foreach ($root in @($env:ProgramFiles, $env:SystemDrive)) {
      if ([string]::IsNullOrWhiteSpace($root)) { continue }
      $candidate = Join-Path (Join-Path $root $version) 'python.exe'
      if (Test-Path -LiteralPath $candidate -PathType Leaf) {
        $python = $candidate
        break
      }
    }
    if ($null -ne $python) { break }
  }
}
if ($null -eq $python) {
  throw 'V3_OFFLINE_PROBE_BLOCK: no Python executable visible to restricted Windows owner'
}
if ([bool]((Get-Item -LiteralPath $python -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
  throw 'V3_OFFLINE_PROBE_BLOCK: linked executable forbidden'
}
$cases = @(
  'test_native_parent_child_model_p4_actual_paper_receipt_and_no_retry',
  'test_native_p1_full_model_reject_has_no_fill_and_no_retry',
  'test_native_p1_missing_fill_or_bad_response_id_quarantines_without_spend_retry',
  'test_p1_restart_follows_new_fill_clock_not_old_scanner',
  'test_native_p1_child_paper_cloud_forwarding_uses_same_relay_once',
  'test_native_p1_reject_missed_opportunity_tracks_child_not_parent',
  'test_native_p1_child_wait_watches_fresh_child_ttl_not_old_parent',
  'test_native_p1_stale_source_and_unapproved_budget_do_not_spend'
)
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $python
$psi.Arguments = $(if ($useLauncher) { '-3 ' } else { '' }) + '-B -m unittest tests.test_v3_extended_reentry_handoff_regression.P1NativeModelWriterTests -v'
$psi.WorkingDirectory = $repo
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.EnvironmentVariables['PYTHONDONTWRITEBYTECODE'] = '1'
$psi.EnvironmentVariables['TMP'] = $sandbox
$psi.EnvironmentVariables['TEMP'] = $sandbox
foreach ($name in @('OPENAI_API_KEY','KRAKEN_API_KEY','KRAKEN_API_SECRET',
                    'SUPABASE_SERVICE_ROLE_KEY','SUPABASE_SECRET_KEY',
                    'V3_PAPER_MODEL_KEY','V3_PAPER_RELAY_TOKEN')) {
  if ($psi.EnvironmentVariables.ContainsKey($name)) {
    $psi.EnvironmentVariables.Remove($name)
  }
}
$process = New-Object System.Diagnostics.Process
$process.StartInfo = $psi
try {
  if (-not $process.Start()) {
    throw 'V3_OFFLINE_PROBE_BLOCK: test process unavailable'
  }
  $stdout = $process.StandardOutput.ReadToEndAsync()
  $stderr = $process.StandardError.ReadToEndAsync()
  if (-not $process.WaitForExit(90000)) {
    $process.Kill()
    [void]$process.WaitForExit(3000)
    throw 'V3_OFFLINE_PROBE_BLOCK: bounded test timeout'
  }
  $log = $stdout.GetAwaiter().GetResult() + [Environment]::NewLine +
         $stderr.GetAwaiter().GetResult()
  if ($process.ExitCode -ne 0 -or
      $log -notmatch '(?m)^Ran 8 tests in ' -or
      $log -notmatch '(?m)^OK\s*$') {
    throw 'V3_OFFLINE_PROBE_BLOCK: original P1 offline test suite failed'
  }
  foreach ($case in $cases) {
    if (-not $log.Contains($case + ' (')) {
      throw 'V3_OFFLINE_PROBE_BLOCK: expected P1 test omitted'
    }
  }
} finally {
  $process.Dispose()
}
# Exactly one restricted JSON ACK; do not echo test logs, paths or secrets.
# Even a physical Windows runner test earns ZERO V3 release proof credits.
[pscustomobject][ordered]@{
  kind = 'MINIPC_REVIEWED_TASK_ACK_V1'
  status = 'SUCCESS'
  task = 'v3_paper_offline_probe'
  mutation_scope = 'RESTRICTED'
  checked_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
  original_p1_offline_cases_passed = $cases.Count
  external_model_and_cloud_are_stubs = $true
  unit_tests_use_existing_runner_temp = $true
  live_paper_writer_physically_witnessed = $false
  independent_cloud_receipt_verified = $false
  model_api_spend = $false
  v3_paper_activated = $false
  v2r4_runtime_touched = $false
  real_money_actions = $false
  technical_release_proofs_credited = 0
} | ConvertTo-Json -Compress
