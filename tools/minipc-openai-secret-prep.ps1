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
$keyFile = Join-Path $secretDir "openai-api-key.txt"
New-Item -ItemType Directory -Force -Path $secretDir | Out-Null

if ((Test-Path $keyFile) -and -not $Rotate) {
  Write-Host "OpenAI API key file already exists; leaving it unchanged."
  Write-Host ("Key file: " + $keyFile)
  exit 0
}

$key = $null
if ($FromClipboard) {
  $key = (Get-Clipboard -Raw).Trim()
  if (-not $key) { throw "Clipboard does not contain a key." }
} else {
  $secure = Read-Host "OpenAI API key (input hidden)" -AsSecureString
  $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
  try {
    $key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
  } finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
  }
}

if (-not $key -or $key.Length -lt 20) {
  throw "OpenAI API key is empty/too short."
}

[System.IO.File]::WriteAllText(
  $keyFile,
  $key + [Environment]::NewLine,
  [System.Text.UTF8Encoding]::new($false)
)

& icacls.exe $keyFile /inheritance:r | Out-Null
& icacls.exe $keyFile /grant:r "$($env:USERDOMAIN)\$($env:USERNAME):(F)" "*S-1-5-18:(R)" "*S-1-5-32-544:(R)" | Out-Null
if ($LASTEXITCODE -ne 0) {
  throw "Failed to restrict OpenAI key file ACL."
}

if ($FromClipboard) {
  Set-Clipboard -Value ""
}

Write-Host ""
Write-Host "=== OPENAI LOCAL SECRET PREP ==="
Write-Host ("Key file: " + $keyFile)
Write-Host "Key stored with restricted ACL for local evaluator use."
Write-Host "Key value was not printed."
if ($FromClipboard) { Write-Host "Clipboard cleared." }
Write-Host "=== END ==="
