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
  }

$rdpRuleDetails=@()
foreach($rule in @($rdpRules)){
  $addr=@($rule | Get-NetFirewallAddressFilter -ErrorAction SilentlyContinue | Select-Object -ExpandProperty RemoteAddress)
  $port=@($rule | Get-NetFirewallPortFilter -ErrorAction SilentlyContinue)
  $localPorts=@($port | Select-Object -ExpandProperty LocalPort -ErrorAction SilentlyContinue)
  $protocols=@($port | Select-Object -ExpandProperty Protocol -ErrorAction SilentlyContinue)
  $rdpRuleDetails += [pscustomobject]@{
    DisplayName=$rule.DisplayName
    DisplayGroup=$rule.DisplayGroup
    Profile=[string]$rule.Profile
    Enabled=[bool]$rule.Enabled
    Direction=[string]$rule.Direction
    Action=[string]$rule.Action
    RemoteAddress=@($addr)
    LocalPort=@($localPorts)
    Protocol=@($protocols)
  }
}
$rdpPublicAllow=@($rdpRuleDetails | Where-Object {$_.Profile -match '(^|,| )Public($|,| )|^Any
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

$defenderHealthy=($null -ne $def -and [bool]$def.RealTimeProtectionEnabled -and [bool]$def.AntivirusEnabled)
$firewallProfilesHealthy=([bool]$domainEnabled -and [bool]$privateEnabled -and [bool]$publicEnabled)
$securityReviewStatus=if(-not $defenderHealthy){"REVIEW_DEFENDER"}elseif(-not $firewallProfilesHealthy){"REVIEW_FIREWALL_PROFILE"}elseif(@($rdpPublicAnyRemote).Count -gt 0){"REVIEW_RDP_PUBLIC_ANYREMOTE"}else{"PASS_BASELINE"}

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
    rdp_allow_rules=$rdpRuleDetails
    rdp_public_allow_rule_count=@($rdpPublicAllow).Count
    rdp_any_remote_rule_count=@($rdpAnyRemote).Count
    rdp_public_any_remote_rule_count=@($rdpPublicAnyRemote).Count
    any_remote_inbound_allow_filter_count=@($allowInbound).Count
  }
  defender=[ordered]@{
    status=$def
    registered_antivirus_products=$avProducts
  }
  security_review=[ordered]@{
    status=$securityReviewStatus
    defender_healthy=[bool]$defenderHealthy
    firewall_profiles_enabled=[bool]$firewallProfilesHealthy
    rdp_public_any_remote_review_required=(@($rdpPublicAnyRemote).Count -gt 0)
    changes_performed=$false
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
foreach($p in @($profiles)){Write-Host ("  "+$p.Name+": inbound="+$p.DefaultInboundAction+" outbound="+$p.DefaultOutboundAction)}
Write-Host ("RDP allow rules: "+@($rdpRuleDetails).Count+" | Public/Any profile="+@($rdpPublicAllow).Count+" | RemoteAddress Any="+@($rdpAnyRemote).Count+" | Public+AnyRemote="+@($rdpPublicAnyRemote).Count)
foreach($r in @($rdpRuleDetails)){
  Write-Host ("  RDP "+$r.DisplayName+" | profile="+$r.Profile+" | remote="+(@($r.RemoteAddress)-join ',')+" | port="+(@($r.LocalPort)-join ','))
}
Write-Host ("All enabled inbound allow filters with RemoteAddress Any: "+@($allowInbound).Count)
if($def){Write-Host ("Defender realtime="+$def.RealTimeProtectionEnabled+" antivirus="+$def.AntivirusEnabled+" signatures="+$def.AntivirusSignatureLastUpdated)}
Write-Host ("Security review: "+$securityReviewStatus)
Write-Host ("Registered AV products: "+@($avProducts).Count)
Write-Host ("Project native apps detected: "+@($projectApps).Count)
foreach($a in $projectApps){Write-Host ("  "+$a.DisplayName+" "+$a.DisplayVersion)}
Write-Host ("Pending reboot: "+($rebootReasons.Count -gt 0)+" reasons="+($rebootReasons -join ','))
Write-Host ("CryptoMiniPC tasks: "+@($cryptoTasks).Count)
Write-Host ("Report: "+$out)
Write-Host "READ ONLY / NO FIREWALL OR DEFENDER CHANGE / NO APP CHANGE / NO REBOOT"
})
$rdpAnyRemote=@($rdpRuleDetails | Where-Object {@($_.RemoteAddress) -contains 'Any'})
$rdpPublicAnyRemote=@($rdpRuleDetails | Where-Object {
  ($_.Profile -match '(^|,| )Public($|,| )|^Any
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
) -and (@($_.RemoteAddress) -contains 'Any')
})

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
