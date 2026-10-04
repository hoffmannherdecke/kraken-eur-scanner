param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading"),
  [switch]$FromClipboard,
  [switch]$Rotate
)

$ErrorActionPreference = "Stop"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw "Bitte dieses Skript in einer als Administrator gestarteten PowerShell ausführen."
}

$secretDir = Join-Path $TradingRoot "Secrets"
$tokenFile = Join-Path $secretDir "github-actions-dispatch-token.txt"
New-Item -ItemType Directory -Force -Path $secretDir | Out-Null

if ((Test-Path $tokenFile) -and -not $Rotate) {
  Write-Host "GitHub Actions dispatch token file already exists; leaving it unchanged."
  Write-Host ("Token file: " + $tokenFile)
  exit 0
}

$token = $null
if ($FromClipboard) {
  $raw = (Get-Clipboard -Raw)
  if (-not $raw) { throw "Clipboard does not contain a token." }
  $candidate = $raw.Trim()
  if ($candidate -match '\s') { throw "Clipboard must contain only the GitHub token, without extra text." }
  $token = $candidate
} else {
  $secure = Read-Host "GitHub fine-grained PAT (input hidden)" -AsSecureString
  $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
  try {
    $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
  } finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
  }
}

if (-not $token -or $token.Length -lt 20) {
  throw "Token is missing or unexpectedly short."
}
if (-not ($token.StartsWith("github_pat_") -or $token.StartsWith("ghp_"))) {
  throw "Unexpected GitHub token format. Expected a fine-grained github_pat_ token (preferred) or a ghp_ token."
}

[System.IO.File]::WriteAllText(
  $tokenFile,
  $token + [Environment]::NewLine,
  [System.Text.UTF8Encoding]::new($false)
)

& icacls.exe $tokenFile /inheritance:r | Out-Null
& icacls.exe $tokenFile /grant:r "$($env:USERDOMAIN)\$($env:USERNAME):(F)" "*S-1-5-18:(R)" "*S-1-5-32-544:(R)" | Out-Null
if ($LASTEXITCODE -ne 0) {
  throw "Failed to restrict GitHub token file ACL."
}

if ($FromClipboard) {
  Set-Clipboard -Value "[clipboard cleared]"
}

Write-Host ""
Write-Host "=== GITHUB ACTIONS DISPATCH SECRET PREP ==="
Write-Host ("Token file: " + $tokenFile)
Write-Host "Stored locally with restricted ACL; token value was NOT printed."
Write-Host "Required intended scope: ONLY hoffmannherdecke/kraken-eur-scanner; repository permission Actions = Read and write."
Write-Host "No Contents write permission is required by the local cadence guard."
if ($FromClipboard) { Write-Host "Clipboard cleared." }
Write-Host "=== END ==="
