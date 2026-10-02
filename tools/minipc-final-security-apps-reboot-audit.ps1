# Final read-only MINI-PC commissioning audit.
param(
  [string]$TradingRoot = "",
  [switch]$Execute,
  [string]$Confirm = ""
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

if([string]::IsNullOrWhiteSpace($TradingRoot)){
  $homeRoot=if($env:USERPROFILE){$env:USERPROFILE}else{$HOME}
  if([string]::IsNullOrWhiteSpace($homeRoot)){throw "Unable to resolve user home directory."}
  $TradingRoot=Join-Path $homeRoot "Trading"
}
$ExpectedConfirm="AUDIT_MINIPC_FINAL_SECURITY_APPS_REBOOT"
$logs=Join-Path $TradingRoot "Logs"

$plan=[ordered]@{
  kind="MINIPC_FINAL_SECURITY_APPS_REBOOT_AUDIT_V1"
  status=$(if($Execute){"READY_TO_EXECUTE"}else{"PLAN_ONLY"})
  read_only=$true
  firewall_changes=$false
  defender_changes=$false
  app_installs_or_removals=$false
  reboot=$false
  scheduled_task_changes=$false
}
if(-not $Execute){$plan|ConvertTo-Json -Depth 5;exit 0}
if($Confirm -ne $ExpectedConfirm){throw "Execution blocked. Re-run with -Confirm $ExpectedConfirm"}

New-Item -ItemType Directory -Force -Path $logs|Out-Null

$profiles=Get-NetFirewallProfile | Select-Object Name,Enabled,DefaultInboundAction,DefaultOutboundAction
$allowInbound=Get-NetFirewallRule -Enabled True -Direction Inbound -Action Allow -ErrorAction SilentlyContinue |
  Get-NetFirewallAddressFilter -ErrorAction SilentlyContinue |
  Where-Object {$_.RemoteAddress -contains "Any"} |
  Select-Object -ExpandProperty InstanceID -ErrorAction SilentlyContinue
$publicEnabled=(Get-NetFirewallProfile -Name Public).Enabled
$privateEnabled=(Get-NetFirewallProfile -Name Private).Enabled
$domainEnabled=(Get-NetFirewallProfile -Name Domain).Enabled

$rdpRules=Get-NetFirewallRule -Enabled True -Direction Inbound -Action Allow -ErrorAction SilentlyContinue |
  Where-Object {
    $_.DisplayGroup -match 'Remote Desktop|Remotedesktop' -or
    $_.DisplayName -match 'Remote Desktop|Remotedesktop'
  } |
  Select-Object DisplayName,DisplayGroup,Profile,Enabled,Direction,Action

$def=$null
try{
  $def=Get-MpComputerStatus | Select-Object AMServiceEnabled,AntivirusEnabled,AntispywareEnabled,BehaviorMonitorEnabled,IoavProtectionEnabled,NISEnabled,RealTimeProtectionEnabled,AntivirusSignatureLastUpdated,QuickScanAge,FullScanAge
}catch{}

$avProducts=@()
try{
  $avProducts=Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct -ErrorAction Stop |
    Select-Object displayName,pathToSignedProductExe,productState
}catch{}

$apps=@()
$keys=@(
  'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
  'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
  'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*'
)
foreach($k in $keys){
  try{
    $apps += Get-ItemProperty $k -ErrorAction SilentlyContinue |
      Where-Object {$_.DisplayName} |
      Select-Object DisplayName,DisplayVersion,Publisher,InstallLocation
  }catch{}
}
$projectApps=$apps | Where-Object {
  $_.DisplayName -match 'Slack|GitHub Desktop|Altrady|ChatGPT'
} | Sort-Object DisplayName -Unique

$rebootReasons=@()
$rebootKeys=@(
 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending',
 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired',
 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager'
)
if(Test-Path $rebootKeys[0]){$rebootReasons+='CBS_REBOOT_PENDING'}
if(Test-Path $rebootKeys[1]){$rebootReasons+='WINDOWS_UPDATE_REBOOT_REQUIRED'}
try{
  $pfr=(Get-ItemProperty $rebootKeys[2] -Name PendingFileRenameOperations -ErrorAction SilentlyContinue).PendingFileRenameOperations
  if($pfr){$rebootReasons+='PENDING_FILE_RENAME_OPERATIONS'}
}catch{}

$cryptoTasks=Get-ScheduledTask -ErrorAction SilentlyContinue |
  Where-Object {$_.TaskName -like 'CryptoMiniPC-*'} |
  Select-Object TaskName,State

$report=[ordered]@{
  schema_version=1
  kind="MINIPC_FINAL_SECURITY_APPS_REBOOT_AUDIT_V1"
  status="PASS_READ_ONLY_AUDIT_COMPLETE"
  checked_at_utc=[DateTime]::UtcNow.ToString("o")
  firewall=[ordered]@{
    profiles=$profiles
    domain_enabled=[bool]$domainEnabled
    private_enabled=[bool]$privateEnabled
    public_enabled=[bool]$publicEnabled
    rdp_allow_rules=$rdpRules
    any_remote_inbound_allow_filter_count=@($allowInbound).Count
  }
  defender=[ordered]@{
    status=$def
    registered_antivirus_products=$avProducts
  }
  native_project_apps=$projectApps
  reboot=[ordered]@{
    pending_reboot=($rebootReasons.Count -gt 0)
    reasons=$rebootReasons
    crypto_minipc_tasks=$cryptoTasks
  }
  guardrails=[ordered]@{
    firewall_changed=$false
    defender_changed=$false
    app_installed_or_removed=$false
    reboot_performed=$false
    scheduled_task_changed=$false
    orders=$false
    real_money_actions=$false
  }
}

$stamp=Get-Date -Format "yyyyMMdd-HHmmss"
$out=Join-Path $logs ("minipc-final-security-apps-reboot-audit-"+$stamp+".json")
[System.IO.File]::WriteAllText($out,($report|ConvertTo-Json -Depth 12),(New-Object System.Text.UTF8Encoding($false)))

Write-Host ""
Write-Host "=== MINI-PC FINAL READ-ONLY AUDIT COMPLETE ==="
Write-Host ("Firewall profiles: Domain="+$domainEnabled+" Private="+$privateEnabled+" Public="+$publicEnabled)
if($def){Write-Host ("Defender realtime="+$def.RealTimeProtectionEnabled+" antivirus="+$def.AntivirusEnabled)}
Write-Host ("Registered AV products: "+@($avProducts).Count)
Write-Host ("Project native apps detected: "+@($projectApps).Count)
foreach($a in $projectApps){Write-Host ("  "+$a.DisplayName+" "+$a.DisplayVersion)}
Write-Host ("Pending reboot: "+($rebootReasons.Count -gt 0)+" reasons="+($rebootReasons -join ','))
Write-Host ("CryptoMiniPC tasks: "+@($cryptoTasks).Count)
Write-Host ("Report: "+$out)
Write-Host "READ ONLY / NO FIREWALL OR DEFENDER CHANGE / NO APP CHANGE / NO REBOOT"
