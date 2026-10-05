param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading"),
  [string]$RepoPath = (Join-Path (Join-Path $env:USERPROFILE "Trading") "Repos\kraken-eur-scanner")
)

$ErrorActionPreference = "Stop"

function Add-Finding(
  [System.Collections.Generic.List[object]]$List,
  [string]$Severity,
  [string]$Code,
  [string]$Detail
) {
  $List.Add([pscustomobject]@{
    severity = $Severity
    code = $Code
    detail = $Detail
  })
}

$findings = New-Object System.Collections.Generic.List[object]
$secretsDir = Join-Path $TradingRoot "Secrets"
$logsDir = Join-Path $TradingRoot "Logs"
$stateDir = Join-Path $TradingRoot "State"

$repoResolved = $null
if (Test-Path $RepoPath) {
  $repoResolved = (Resolve-Path $RepoPath).Path.TrimEnd('\')
} else {
  Add-Finding $findings "CRITICAL" "repo_missing" $RepoPath
}

if (-not (Test-Path $secretsDir)) {
  Add-Finding $findings "WARNING" "secrets_dir_missing" $secretsDir
} else {
  $secretsResolved = (Resolve-Path $secretsDir).Path.TrimEnd('\')
  if ($repoResolved -and $secretsResolved.StartsWith($repoResolved,[System.StringComparison]::OrdinalIgnoreCase)) {
    Add-Finding $findings "CRITICAL" "secrets_inside_repo" $secretsResolved
  }

  $expectedNames = @(
    "altrady-webhook-token.txt",
    "minipc-status-relay-token.txt",
    "v2r4-shadow-evidence-token.txt"
  )
  $expectedPaths = @{}
  foreach ($name in $expectedNames) {
    $path = Join-Path $secretsDir $name
    $expectedPaths[$name] = $path
    if (-not (Test-Path $path)) {
      Add-Finding $findings "WARNING" "dedicated_relay_secret_missing" $name
    }
  }

  $hashes = @{}
  foreach ($name in $expectedNames) {
    $path = $expectedPaths[$name]
    if (-not (Test-Path $path)) { continue }
    $value = (Get-Content -LiteralPath $path -Raw).Trim()
    if ($value.Length -lt 24) {
      Add-Finding $findings "CRITICAL" "relay_secret_too_short" $name
      continue
    }
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
      $bytes = [System.Text.Encoding]::UTF8.GetBytes($value)
      $hashes[$name] = ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-','').ToLowerInvariant()
    } finally { $sha.Dispose() }
  }
  if ($hashes.Count -ge 2) {
    $groups = $hashes.GetEnumerator() | Group-Object Value
    foreach ($g in $groups) {
      if ($g.Count -gt 1) {
        Add-Finding $findings "CRITICAL" "relay_secret_reuse" (($g.Group | ForEach-Object { $_.Key }) -join ",")
      }
    }
  }

  foreach ($file in Get-ChildItem -Path $secretsDir -File -ErrorAction SilentlyContinue) {
    try {
      $acl = Get-Acl -LiteralPath $file.FullName
      foreach ($ace in $acl.Access) {
        if ($ace.AccessControlType -ne "Allow") { continue }
        $identity = [string]$ace.IdentityReference
        $rights = [string]$ace.FileSystemRights
        $broad = (
          $identity -match '(^|\\)Everyone$' -or
          $identity -match '(^|\\)Guests$'
        )
        if ($broad -and $rights -match 'Read|Write|Modify|FullControl') {
          Add-Finding $findings "CRITICAL" "broad_secret_acl" ($file.Name + " grants " + $identity + " " + $rights)
        }
      }
    } catch {
      Add-Finding $findings "WARNING" "secret_acl_unreadable" $file.Name
    }
  }
}

if ($repoResolved) {
  Push-Location $repoResolved
  try {
    $tracked = @(& git ls-files 2>$null)
    $forbiddenFiles = @(
      $tracked | Where-Object {
        $_ -match '(^|/)\.env($|\.)' -or
        $_ -match '\.(pem|pfx|p12|key)$'
      }
    )
    foreach ($name in $forbiddenFiles) {
      Add-Finding $findings "CRITICAL" "tracked_sensitive_file" $name
    }

    $patterns = @(
      'hooks\.slack\.com/services/[A-Za-z0-9/_-]{20,}',
      'sb_secret_[A-Za-z0-9_-]{20,}',
      '-----BEGIN ([A-Z0-9 ]+ )?PRIVATE KEY-----'
    )

    foreach ($pattern in $patterns) {
      $hits = @(& git grep -I -l -E -- $pattern 2>$null)
      foreach ($name in $hits) {
        Add-Finding $findings "CRITICAL" "live_secret_pattern_in_repo" $name
      }
    }
  } finally {
    Pop-Location
  }
}

# Search only local operational JSON/log text. Never print the matching secret,
# only the filename containing a forbidden live-secret pattern.
$localPatterns = @(
  'hooks\.slack\.com/services/[A-Za-z0-9/_-]{20,}',
  'sb_secret_[A-Za-z0-9_-]{20,}',
  '-----BEGIN ([A-Z0-9 ]+ )?PRIVATE KEY-----'
)

foreach ($dir in @($logsDir,$stateDir)) {
  if (-not (Test-Path $dir)) { continue }
  foreach ($file in Get-ChildItem -Path $dir -File -Recurse -ErrorAction SilentlyContinue) {
    if ($file.Length -gt 10MB) { continue }
    foreach ($pattern in $localPatterns) {
      try {
        if (Select-String -LiteralPath $file.FullName -Pattern $pattern -Quiet -ErrorAction Stop) {
          Add-Finding $findings "CRITICAL" "live_secret_pattern_in_operational_file" $file.FullName
          break
        }
      } catch {}
    }
  }
}

$critical = @($findings | Where-Object { $_.severity -eq "CRITICAL" }).Count
$warning = @($findings | Where-Object { $_.severity -eq "WARNING" }).Count
$status = if ($critical -gt 0) { "CRITICAL" } elseif ($warning -gt 0) { "WARNING" } else { "HEALTHY" }

Write-Host ""
Write-Host "=== MINI-PC SECRET HYGIENE AUDIT SUMMARY ==="
Write-Host ("Status: " + $status)
Write-Host ("Critical: " + $critical + " | Warning: " + $warning)
if ($findings.Count -eq 0) {
  Write-Host "Findings: none"
} else {
  foreach ($f in $findings) {
    Write-Host ($f.severity + " " + $f.code + " | " + $f.detail)
  }
}
Write-Host "Audit never prints secret values; only filenames/permission findings."
Write-Host "Safety: READ-ONLY AUDIT / NO FILE CHANGES / NO CREDENTIAL ROTATION / NO NETWORK LOGIN"
Write-Host "=== END ==="

if ($critical -gt 0) { exit 2 }
if ($warning -gt 0) { exit 1 }
exit 0
