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
$tokenFile = Join-Path $secretDir "altrady-webhook-token.txt"
New-Item -ItemType Directory -Force -Path $secretDir | Out-Null

if ((Test-Path $tokenFile) -and -not $Rotate) {
  throw "Token file already exists. Refusing to overwrite it. Use -Rotate only for an intentional rotation."
}

$bytes = New-Object byte[] 32
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try {
  $rng.GetBytes($bytes)
} finally {
  $rng.Dispose()
}
$token = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+','-').Replace('/','_')

[System.IO.File]::WriteAllText(
  $tokenFile,
  $token + [Environment]::NewLine,
  [System.Text.UTF8Encoding]::new($false)
)

# Restrict the secret file to the current user, SYSTEM and local Administrators.
& icacls.exe $tokenFile /inheritance:r | Out-Null
& icacls.exe $tokenFile /grant:r "$($env:USERDOMAIN)\$($env:USERNAME):(F)" "*S-1-5-18:(R)" "*S-1-5-32-544:(R)" | Out-Null
if ($LASTEXITCODE -ne 0) {
  throw "Failed to restrict token file ACL."
}

Set-Clipboard -Value $token

Write-Host ""
Write-Host "=== ALTRADY RELAY SECRET PREP ==="
Write-Host ("Secret file: " + $tokenFile)
Write-Host "Secret generated securely and copied to the Windows clipboard."
Write-Host "The token value is intentionally NOT printed."
Write-Host "Next manual step: paste the clipboard value into Supabase Edge Function secret ALTRADY_WEBHOOK_TOKEN."
Write-Host "Do not paste the token into ChatGPT, GitHub, Slack or logs."
Write-Host "=== END ==="
