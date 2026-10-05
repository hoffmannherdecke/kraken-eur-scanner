param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading"),
  [switch]$Rotate
)

$ErrorActionPreference = "Stop"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw "Bitte dieses Skript in einer als Administrator gestarteten PowerShell ausführen."
}

$secretDir = Join-Path $TradingRoot "Secrets"
New-Item -ItemType Directory -Force -Path $secretDir | Out-Null

$targets = @(
  @{ relay_id="minipc-status-relay"; file=(Join-Path $secretDir "minipc-status-relay-token.txt") },
  @{ relay_id="v2r4-shadow-evidence-relay"; file=(Join-Path $secretDir "v2r4-shadow-evidence-token.txt") }
)

function New-RelayToken {
  $bytes = New-Object byte[] 32
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
  return [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+','-').Replace('/','_')
}

function Get-Sha256Hex([string]$Value) {
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try {
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Value)
    return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-','').ToLowerInvariant()
  } finally { $sha.Dispose() }
}

$rows = @()
foreach ($target in $targets) {
  $path = [string]$target.file
  if ((Test-Path $path) -and -not $Rotate) {
    throw "Dedicated token file already exists: $path. Use -Rotate only for an intentional rotation."
  }

  $token = New-RelayToken
  [System.IO.File]::WriteAllText($path, $token + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
  & icacls.exe $path /inheritance:r | Out-Null
  & icacls.exe $path /grant:r "$($env:USERDOMAIN)\$($env:USERNAME):(F)" "*S-1-5-18:(R)" "*S-1-5-32-544:(R)" | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "Failed to restrict token ACL: $path" }

  $rows += [pscustomobject]@{
    relay_id = [string]$target.relay_id
    token_sha256 = Get-Sha256Hex $token
    token_file = $path
  }
}

if ($rows[0].token_sha256 -eq $rows[1].token_sha256) {
  throw "Cryptographic RNG collision / duplicate relay tokens detected."
}

$result = [pscustomobject]@{
  kind = "MINIPC_DEDICATED_RELAY_SECRET_SPLIT_V1"
  status = "PREPARED"
  token_values_printed = $false
  shared_altrady_token_modified = $false
  relay_hashes = @($rows | ForEach-Object {
    [pscustomobject]@{ relay_id=$_.relay_id; token_sha256=$_.token_sha256 }
  })
}

$result | ConvertTo-Json -Depth 5
Write-Host "Dedicated token values were NOT printed and were NOT copied to clipboard."
Write-Host "Keep the two token files only under Trading\Secrets."
