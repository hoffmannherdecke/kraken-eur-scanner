# MINIPC_REVIEWED_TASK_V1
# No file content reads, filenames in output, host writes or credentials.
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if ($identity.Name -notmatch '(?i)\\CryptoSupportSvc$' -or
    $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator) -or
    $env:RUNNER_NAME -cne 'MINI-PC-CryptoSupport') {
  throw 'HOST_ACCESS_BOUNDARY_BLOCK: unexpected runner identity'
}
$serviceRoot = 'C:\CryptoSupport'
$restrictedRoot = 'C:\Users\ADMIN\Trading\Secrets'
# Positive basic read-only probe; never print filenames or file contents.
try {
  [void][System.IO.Directory]::GetFileSystemEntries($serviceRoot)
} catch {
  throw 'HOST_ACCESS_BOUNDARY_BLOCK: isolated support workspace unreadable'
}
# Directory enumeration is tested without emitting or opening any file content.
# If the confidential directory can be enumerated the security gate FAILS.
$directoryListingAllowed = $false
try {
  [void][System.IO.Directory]::GetFileSystemEntries($restrictedRoot)
  $directoryListingAllowed = $true
} catch [System.UnauthorizedAccessException] {
  $directoryListingAllowed = $false
} catch {
  throw 'HOST_ACCESS_BOUNDARY_UNVERIFIED: unexpected protected path access error'
}
if ($directoryListingAllowed) {
  throw 'HOST_ACCESS_BOUNDARY_FAIL: protected directory listing permitted'
}
Write-Host 'HOST_ACCESS_BOUNDARY_V1: support_read=true, protected_directory_listing_denied=true; content_read_not_tested'
[pscustomobject][ordered]@{
  kind = 'MINIPC_REVIEWED_TASK_ACK_V1'
  status = 'SUCCESS'
  task = 'access_boundary_probe'
  mutation_scope = 'RESTRICTED'
  support_directory_read = $true
  protected_directory_listing_denied = $true
  content_read_not_tested = $true
  no_files_modified = $true
  secrets_or_files_emitted = $false
  checked_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
} | ConvertTo-Json -Compress
