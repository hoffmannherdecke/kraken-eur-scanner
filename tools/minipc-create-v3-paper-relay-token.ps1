param(
  [string]$TradingRoot=(Join-Path $env:USERPROFILE 'Trading'),
  [switch]$Execute
)
$ErrorActionPreference='Stop'
$path=Join-Path $TradingRoot 'Secrets\v3-paper-relay-token.txt'
if(-not $Execute){
  [pscustomobject]@{
    status='PLAN_ONLY_NO_SECRET_READ_OR_WRITE'
    target=$path
    output='ONLY_SHA256_DIGEST_NOT_SECRET'
    cloud_change=$false
  } | ConvertTo-Json
  exit 0
}
$parent=Split-Path $path -Parent
if(-not (Test-Path -LiteralPath $parent -PathType Container)){
  throw 'Existing Trading\Secrets folder must exist; no creation of another secret storage root'
}
if(Test-Path -LiteralPath $path){
  $token=[System.IO.File]::ReadAllText($path,[System.Text.Encoding]::ASCII).Trim()
  if($token.Length -ne 64 -or $token -notmatch '^[0-9a-f]{64}$'){
    throw 'Existing V3 relay secret has wrong format; do not overwrite automatically'
  }
  $state='EXISTING_SECRET_HASH_ONLY'
}else{
  $bytes=New-Object byte[] 32
  $rng=[System.Security.Cryptography.RandomNumberGenerator]::Create()
  try{$rng.GetBytes($bytes)}finally{$rng.Dispose()}
  $token=([System.BitConverter]::ToString($bytes)).Replace('-','').ToLowerInvariant()
  [System.IO.File]::WriteAllText($path,$token,[System.Text.Encoding]::ASCII)
  try{
    $acl=New-Object System.Security.AccessControl.FileSecurity
    $acl.SetAccessRuleProtection($true,$false)
    $identities=@(
      ([System.Security.Principal.WindowsIdentity]::GetCurrent().User),
      ([System.Security.Principal.SecurityIdentifier]::new('S-1-5-18')),
      ([System.Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))
    )
    foreach($id in $identities){
      $rule=[System.Security.AccessControl.FileSystemAccessRule]::new(
        $id,[System.Security.AccessControl.FileSystemRights]::FullControl,
        [System.Security.AccessControl.AccessControlType]::Allow)
      $acl.AddAccessRule($rule)
    }
    [System.IO.File]::SetAccessControl($path,$acl)
  }catch{
    Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
    throw 'Could not lock down the new relay token file; removed it'
  }
  $state='NEW_SECRET_GENERATED_SECURE_ACL'
}
$sha=[System.Security.Cryptography.SHA256]::Create()
try{$digest=([System.BitConverter]::ToString(
  $sha.ComputeHash([System.Text.Encoding]::ASCII.GetBytes($token))
)).Replace('-','').ToLowerInvariant()}finally{$sha.Dispose()}
[pscustomobject]@{
  status=$state
  relay_id='v3-paper-evidence-relay'
  sha256_for_cloud_registration=$digest
  secret_file=$path
  secret_itself_not_displayed=$true
  cloud_registration_still_required=$true
  no_orders=$true
} | ConvertTo-Json -Depth 5
