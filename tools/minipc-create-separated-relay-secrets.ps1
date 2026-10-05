param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading"),
  [switch]$Rotate
)
$ErrorActionPreference = "Stop"
$secretDir = Join-Path $TradingRoot "Secrets"
New-Item -ItemType Directory -Force -Path $secretDir | Out-Null

function New-RelaySecret([string]$FileName) {
  $path = Join-Path $secretDir $FileName
  if ((Test-Path $path) -and -not $Rotate) {
    throw "$FileName already exists. Use -Rotate only for an intentional coordinated rotation."
  }

  $bytes = New-Object byte[] 32
  [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
  $token = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+','-').Replace('/','_')
  [System.IO.File]::WriteAllText($path, $token, [System.Text.UTF8Encoding]::new($false))

  $acl = New-Object System.Security.AccessControl.FileSecurity
  $acl.SetAccessRuleProtection($true,$false)
  $user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
  $acl.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule(
    $user,'FullControl','Allow'
  )))
  $acl.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule(
    'SYSTEM','FullControl','Allow'
  )))
  Set-Acl -Path $path -AclObject $acl

  $sha = [System.Security.Cryptography.SHA256]::HashData([System.Text.Encoding]::UTF8.GetBytes($token))
  $hex = -join ($sha | ForEach-Object { $_.ToString('x2') })
  [pscustomobject]@{
    file = $FileName
    sha256 = $hex
    secret_length = $token.Length
  }
}

$result = @(
  New-RelaySecret "shadow-evidence-token.txt"
  New-RelaySecret "minipc-status-token.txt"
)

[pscustomobject]@{
  kind = "MINIPC_SEPARATED_RELAY_SECRET_HASHES_V1"
  generated_at_utc = (Get-Date).ToUniversalTime().ToString("o")
  secrets = $result
  note = "Only these SHA-256 hashes are safe to copy back; never share file contents."
} | ConvertTo-Json -Depth 5
