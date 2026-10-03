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
$keyFile = Join-Path $secretDir "openai-admin-key.txt"
New-Item -ItemType Directory -Force -Path $secretDir | Out-Null

if ((Test-Path $keyFile) -and -not $Rotate) {
  Write-Host "OpenAI Admin API key file already exists; leaving it unchanged."
  Write-Host ("Key file: " + $keyFile)
  exit 0
}

$key = $null
if ($FromClipboard) {
  $raw = (Get-Clipboard -Raw)
  if (-not $raw) { throw "Clipboard does not contain a key." }
  $matches = [regex]::Matches($raw.Trim(), 'sk-admin-[A-Za-z0-9_-]{20,}')
  $unique = @($matches | ForEach-Object { $_.Value } | Select-Object -Unique)
  if ($unique.Count -ne 1) {
    throw "Clipboard must contain exactly one OpenAI Admin API key beginning with sk-admin-."
  }
  $key = $unique[0]
} else {
  $secure = Read-Host "OpenAI Admin API key (input hidden)" -AsSecureString
  $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
  try {
    $key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
  } finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
  }
}

if (-not $key -or -not $key.StartsWith("sk-admin-")) {
  throw "Unexpected key format. Expected an OpenAI Admin API key beginning with sk-admin-."
}

[System.IO.File]::WriteAllText(
  $keyFile,
  $key + [Environment]::NewLine,
  [System.Text.UTF8Encoding]::new($false)
)

& icacls.exe $keyFile /inheritance:r | Out-Null
& icacls.exe $keyFile /grant:r "$($env:USERDOMAIN)\$($env:USERNAME):(F)" "*S-1-5-18:(R)" "*S-1-5-32-544:(R)" | Out-Null
if ($LASTEXITCODE -ne 0) {
  throw "Failed to restrict OpenAI Admin key file ACL."
}

if ($FromClipboard) {
  Set-Clipboard -Value "[clipboard cleared]"
}

Write-Host ""
Write-Host "=== OPENAI ADMIN SECRET PREP ==="
Write-Host ("Key file: " + $keyFile)
Write-Host "Stored locally with restricted ACL; value was not printed."
Write-Host "IMPORTANT: this is an Admin API credential. It is not exposed to Work/Codex/GitHub."
if ($FromClipboard) { Write-Host "Clipboard cleared." }
Write-Host "=== END ==="
