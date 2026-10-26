# MINIPC_REVIEWED_TASK_V1
# Exact originalhost Windows staging of ONE inactive CAS witness archive child
# inside previously authorized restricted Workspace. No CAS, cloud, scheduler,
# Windows admin, paid service, live trading or production intent is touched.
$ErrorActionPreference = 'Stop'
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$p = New-Object Security.Principal.WindowsPrincipal($id)
if ($id.Name -notmatch '(?i)\\CryptoSupportSvc$' -or
    $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator) -or
    $env:RUNNER_NAME -cne 'MINI-PC-CryptoSupport') {
  throw 'V3_WITNESS_STAGE_BLOCK: existing restricted Windows runner required'
}
if ([string]::IsNullOrWhiteSpace($env:GITHUB_WORKSPACE) -or
    [string]::IsNullOrWhiteSpace($env:RUNNER_TEMP) -or
    $env:MINIPC_TASK_SANDBOX -cne $env:RUNNER_TEMP) {
  throw 'V3_WITNESS_STAGE_BLOCK: bounded original sandbox required'
}
$checkout = [IO.Path]::GetFullPath(
  (Join-Path $env:GITHUB_WORKSPACE '_protected_main'))
$workspace = [IO.Path]::GetFullPath($env:GITHUB_WORKSPACE).TrimEnd('\')
if (-not $checkout.StartsWith(
      $workspace + [IO.Path]::DirectorySeparatorChar,
      [StringComparison]::OrdinalIgnoreCase)) {
  throw 'V3_WITNESS_STAGE_BLOCK: trusted source path absent'
}
$helper = Join-Path $checkout 'tools\v3_cas_originalhost_spool_probe_INACTIVE.py'
foreach ($relative in @(
    'tools\v3_cas_preinvoke_protocol_INACTIVE.py',
    'tools\v3_cas_local_spool_INACTIVE.py',
    'tools\v3_cas_originalhost_spool_probe_INACTIVE.py')) {
  $file = Join-Path $checkout $relative
  $item = Get-Item -LiteralPath $file -Force -ErrorAction Stop
  if ($item.PSIsContainer -or [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
    throw 'V3_WITNESS_STAGE_BLOCK: reviewed source file missing or linked'
  }
}
$parent = 'C:\CryptoSupport\Workspace'
$archive = Join-Path $parent 'V3CasWitness-INACTIVE'
# Refuse remote/removable/non-NTFS or nearly-full volumes: a local audit
# cannot be staged on an ambiguous filesystem.
$volume = [IO.DriveInfo]::new('C')
if (-not $volume.IsReady -or $volume.DriveFormat -cne 'NTFS' -or
    $volume.AvailableFreeSpace -lt (100 * 1024 * 1024)) {
  throw 'V3_WITNESS_STAGE_BLOCK: original local NTFS storage unavailable'
}
foreach ($folder in @('C:\CryptoSupport', $parent)) {
  $item = Get-Item -LiteralPath $folder -Force -ErrorAction Stop
  if (-not $item.PSIsContainer -or
      [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
    throw 'V3_WITNESS_STAGE_BLOCK: existing approved Workspace not safe'
  }
}
# Do not broaden existing security. The original approved Workspace has
# a protected explicit non-admin ACL. No new parent/Trading ACL mutations.
function Assert-ExpectedAcl([string]$folder) {
  $acl = Get-Acl -LiteralPath $folder -ErrorAction Stop
  if (-not $acl.AreAccessRulesProtected) {
    throw 'V3_WITNESS_STAGE_BLOCK: inherited broad folder ACL possible'
  }
  $rules = @($acl.GetAccessRules(
      $true, $true, [Security.Principal.SecurityIdentifier]))
  $accepted = @('S-1-5-18', 'S-1-5-32-544', [string]$id.User.Value)
  $selfCanWrite = $false
  foreach ($rule in $rules) {
    if ($rule.AccessControlType -ne
        [Security.AccessControl.AccessControlType]::Allow) { continue }
    $subject = [string]$rule.IdentityReference.Value
    if ($subject -notin $accepted) {
      throw 'V3_WITNESS_STAGE_BLOCK: unexpected permitted ACL principal'
    }
    if ($subject -ceq [string]$id.User.Value -and
        ($rule.FileSystemRights -band
           [Security.AccessControl.FileSystemRights]::WriteData) -ne 0) {
      $selfCanWrite = $true
    }
  }
  if (-not $selfCanWrite) {
    throw 'V3_WITNESS_STAGE_BLOCK: restricted owner has no scoped write'
  }
}
Assert-ExpectedAcl $parent
$created = $false
if ([IO.Directory]::Exists($archive)) {
  $existing = Get-Item -LiteralPath $archive -Force -ErrorAction Stop
  if (-not $existing.PSIsContainer -or
      [bool]($existing.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
    throw 'V3_WITNESS_STAGE_BLOCK: unsafe preexisting archive'
  }
} elseif ([IO.File]::Exists($archive)) {
  throw 'V3_WITNESS_STAGE_BLOCK: archive collides with file'
} else {
  [void][IO.Directory]::CreateDirectory($archive)
  $created = $true
}
$item = Get-Item -LiteralPath $archive -Force -ErrorAction Stop
if (-not $item.PSIsContainer -or
    [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
  throw 'V3_WITNESS_STAGE_BLOCK: archive root unsafe'
}
# The new child inherits the explicit *approved* Workspace ACL. It is
# intentionally not an independent WORM store or approved signer.
$childAcl = Get-Acl -LiteralPath $archive -ErrorAction Stop
$effectiveParent = Get-Acl -LiteralPath $parent -ErrorAction Stop
# Inheritance on child is allowed ONLY from exact protected parent.
if (-not $effectiveParent.AreAccessRulesProtected) {
  throw 'V3_WITNESS_STAGE_BLOCK: parent ACL changed during setup'
}
# Check all effective Allow ACL entries, including inherited entries.
$childRules = @($childAcl.GetAccessRules(
    $true, $true, [Security.Principal.SecurityIdentifier]))
$accepted = @('S-1-5-18', 'S-1-5-32-544', [string]$id.User.Value)
$selfCanWrite = $false
foreach ($rule in $childRules) {
  if ($rule.AccessControlType -ne
      [Security.AccessControl.AccessControlType]::Allow) { continue }
  $who = [string]$rule.IdentityReference.Value
  if ($who -notin $accepted) {
    throw 'V3_WITNESS_STAGE_BLOCK: archive ACL not isolated'
  }
  if ($who -ceq [string]$id.User.Value -and
      ($rule.FileSystemRights -band
        [Security.AccessControl.FileSystemRights]::WriteData) -ne 0) {
    $selfCanWrite = $true
  }
}
if (-not $selfCanWrite) {
  throw 'V3_WITNESS_STAGE_BLOCK: archive scoped write unavailable'
}
if (@([IO.Directory]::GetFileSystemEntries($archive)).Count -ne 0) {
  # Never touch a prior production or uncertain epoch. Explicit review only.
  throw 'V3_WITNESS_STAGE_BLOCK: archive not initially empty'
}
# Use the existing restricted machine-wide Python discovery method, without
# looking in another user's profile or installing any package.
$python = $null
$useLauncher = $false
foreach ($name in @('python.exe','py.exe')) {
  $cmd = Get-Command -Name $name -CommandType Application -ErrorAction SilentlyContinue |
    Select-Object -First 1
  if ($null -ne $cmd -and
      -not [string]::IsNullOrWhiteSpace([string]$cmd.Source) -and
      (Test-Path -LiteralPath ([string]$cmd.Source) -PathType Leaf)) {
    $python = [string]$cmd.Source
    $useLauncher = ($name -ceq 'py.exe')
    break
  }
}
if ($null -eq $python) {
  foreach ($version in @('Python314','Python313','Python312','Python311','Python310')) {
    foreach ($disk in @($env:ProgramFiles,$env:SystemDrive)) {
      if ([string]::IsNullOrWhiteSpace($disk)) { continue }
      $candidate = Join-Path (Join-Path $disk $version) 'python.exe'
      if (Test-Path -LiteralPath $candidate -PathType Leaf) {
        $python = $candidate
        break
      }
    }
    if ($null -ne $python) { break }
  }
}
if ($null -eq $python -or
    [bool]((Get-Item -LiteralPath $python -Force).Attributes -band
      [IO.FileAttributes]::ReparsePoint)) {
  throw 'V3_WITNESS_STAGE_BLOCK: restricted preinstalled Python unavailable'
}
# A UUID child belongs ONLY to this one job. The real archive root receives
# zero production records; the child contains only synthetic test identities.
$probe = Join-Path $archive ('v3probe-' + [guid]::NewGuid().ToString('N'))
if ([IO.Directory]::Exists($probe) -or [IO.File]::Exists($probe)) {
  throw 'V3_WITNESS_STAGE_BLOCK: impossible probe collision'
}
[void][IO.Directory]::CreateDirectory($probe)
$probeItem = Get-Item -LiteralPath $probe -Force -ErrorAction Stop
if (-not $probeItem.PSIsContainer -or
    [bool]($probeItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
  throw 'V3_WITNESS_STAGE_BLOCK: probe path invalid'
}
# Even a transient test child must not acquire unreviewed inherited permissions.
$probeAcl = Get-Acl -LiteralPath $probe -ErrorAction Stop
foreach ($ace in @($probeAcl.GetAccessRules(
    $true, $true, [Security.Principal.SecurityIdentifier]))) {
  if ($ace.AccessControlType -eq
      [Security.AccessControl.AccessControlType]::Allow -and
      [string]$ace.IdentityReference.Value -notin $accepted) {
    throw 'V3_WITNESS_STAGE_BLOCK: probe child permission drift'
  }
}
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $python
$prefix = if ($useLauncher) { '-3 ' } else { '' }
$psi.Arguments = $prefix + '-B -S "' + $helper + '" "' + $probe + '"'
$psi.WorkingDirectory = $checkout
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.EnvironmentVariables['PYTHONDONTWRITEBYTECODE'] = '1'
$psi.EnvironmentVariables['PYTHONNOUSERSITE'] = '1'
$psi.EnvironmentVariables['PYTHONPATH'] = Join-Path $checkout 'tools'
$psi.EnvironmentVariables['TMP'] = $env:RUNNER_TEMP
$psi.EnvironmentVariables['TEMP'] = $env:RUNNER_TEMP
foreach ($secret in @(
    'OPENAI_API_KEY','KRAKEN_API_KEY','KRAKEN_API_SECRET',
    'SUPABASE_SERVICE_ROLE_KEY','SUPABASE_SECRET_KEY',
    'V3_PAPER_MODEL_KEY','V3_PAPER_RELAY_TOKEN')) {
  if ($psi.EnvironmentVariables.ContainsKey($secret)) {
    $psi.EnvironmentVariables.Remove($secret)
  }
}
$proc = New-Object System.Diagnostics.Process
$proc.StartInfo = $psi
try {
  if (-not $proc.Start()) {
    throw 'V3_WITNESS_STAGE_BLOCK: isolated test process unavailable'
  }
  $stdout = $proc.StandardOutput.ReadToEndAsync()
  $stderr = $proc.StandardError.ReadToEndAsync()
  if (-not $proc.WaitForExit(60000)) {
    $proc.Kill()
    [void]$proc.WaitForExit(3000)
    throw 'V3_WITNESS_STAGE_BLOCK: bounded synthetic file test timed out'
  }
  $resultText = $stdout.GetAwaiter().GetResult().Trim()
  $errorText = $stderr.GetAwaiter().GetResult()
  if ($proc.ExitCode -ne 0 -or
      $resultText -cne 'V3_LOCAL_WITNESS_REAL_ORIGINALHOST_SANDBOX_PROBE_PASS' -or
      -not [string]::IsNullOrWhiteSpace($errorText)) {
    throw 'V3_WITNESS_STAGE_BLOCK: real NTFS file-chain test failed'
  }
} finally {
  $proc.Dispose()
}
# Remove precisely TWO newly generated and physically verified synthetic
# files, no wildcard or recursive deletion. An unexpected item => HOLD
# and retain all material for later separate review, never repair silently.
$items = @([IO.Directory]::GetFileSystemEntries($probe))
$expected = @((Join-Path $probe '000001.json'),
              (Join-Path $probe '000002.json'))
if ($items.Count -ne 2 -or
    @($items | Where-Object { $_ -notin $expected }).Count -ne 0) {
  throw 'V3_WITNESS_STAGE_BLOCK: unrecognized child content'
}
foreach ($file in $expected) {
  $f = Get-Item -LiteralPath $file -Force -ErrorAction Stop
  if ($f.PSIsContainer -or
      [bool]($f.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
      $f.Length -gt 2048 -or $f.Length -le 0) {
    throw 'V3_WITNESS_STAGE_BLOCK: generated child not a safe test file'
  }
}
foreach ($file in $expected) { [IO.File]::Delete($file) }
if (@([IO.Directory]::GetFileSystemEntries($probe)).Count -ne 0) {
  throw 'V3_WITNESS_STAGE_BLOCK: synthetic child not empty'
}
[IO.Directory]::Delete($probe, $false)
if (@([IO.Directory]::GetFileSystemEntries($archive)).Count -ne 0) {
  throw 'V3_WITNESS_STAGE_BLOCK: inactive archive not empty after probe'
}
# Only safe counts/booleans; no raw paths, receipts, Windows SIDs or secrets.
[pscustomobject][ordered]@{
  kind = 'MINIPC_REVIEWED_TASK_ACK_V1'
  status = 'SUCCESS'
  task = 'v3_cas_witness_archive_stage'
  mutation_scope = 'RESTRICTED'
  checked_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
  inactive_archive_created = $created
  inactive_archive_exists = $true
  parent_ntfs_acl_scoped_to_existing_three_principals = $true
  archive_ntfs_acl_scoped_to_existing_three_principals = $true
  physical_originalhost_ntfs_two_synthetic_intents_readback = $true
  synthetic_files_safely_cleaned = $true
  archive_empty_no_real_audit_intents = $true
  backup_and_powerloss_durability_proven = $false
  external_worm_custody_proven = $false
  originalhost_signer_authenticated = $false
  exclusive_cloud_cas_coverage_proven = $false
  cloud_cas_authorized = $false
  old_writer_auto_rearm_allowed = $false
  native_restore_authorized = $false
  technical_v3_e2e_release_proofs_credited = 0
  v3_paper_activated = $false
  trading_orders_permitted = $false
  active_v2r4_runtime_modified = $false
  no_new_windows_admin_or_task = $true
  no_paid_service_or_network_api = $true
} | ConvertTo-Json -Compress -Depth 4
