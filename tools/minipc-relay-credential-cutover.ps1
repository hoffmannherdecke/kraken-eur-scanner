param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading")
)

$ErrorActionPreference = "Stop"

$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$principal=New-Object Security.Principal.WindowsPrincipal($identity)
if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){
  throw "Bitte in einer als Administrator gestarteten PowerShell ausführen."
}

$repo=Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$python=Join-Path $TradingRoot "Runtime\kraken-eur-scanner-venv\Scripts\python.exe"
$legacyPath=Join-Path $TradingRoot "Secrets\altrady-webhook-token.txt"
$statusPath=Join-Path $TradingRoot "Secrets\minipc-status-token.txt"
$shadowPath=Join-Path $TradingRoot "Secrets\shadow-evidence-token.txt"
$statusPending=$statusPath+".pending"
$shadowPending=$shadowPath+".pending"
$statusTool=Join-Path $repo "tools\minipc-status-sync.py"
$shadowTool=Join-Path $repo "tools\v2r4-shadow-cloud-sync.py"
$statusEndpoint="https://nlgzjmqgwueojlyqmoru.supabase.co/functions/v1/minipc-status-relay"
$shadowEndpoint="https://nlgzjmqgwueojlyqmoru.supabase.co/functions/v1/v2r4-shadow-evidence-relay"
$statusTask="CryptoMiniPC-StatusSync"
$shadowTask="CryptoMiniPC-V2R4ShadowCloudSync"
$supervisorTask="CryptoMiniPC-RuntimeSupervisor"

foreach($p in @($repo,$python,$legacyPath,$statusTool,$shadowTool)){
  if(-not (Test-Path $p)){ throw "Required path missing: $p" }
}

Push-Location $repo
try{
  if((git status --porcelain).Count -ne 0){ throw "Repository working tree is not clean." }
  git fetch origin main
  git checkout main
  git pull --ff-only origin main
  if($LASTEXITCODE -ne 0){ throw "Fast-forward pull failed." }
} finally { Pop-Location }

$legacy=(Get-Content -LiteralPath $legacyPath -Raw).Trim()
if($legacy.Length -lt 24){ throw "Legacy bootstrap token missing/too short." }

function New-Token {
  $bytes=New-Object byte[] 32
  $rng=[System.Security.Cryptography.RandomNumberGenerator]::Create()
  try{$rng.GetBytes($bytes)}finally{$rng.Dispose()}
  return [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+','-').Replace('/','_')
}

function Write-Secret([string]$Path,[string]$Token){
  [System.IO.File]::WriteAllText($Path,$Token+[Environment]::NewLine,[System.Text.UTF8Encoding]::new($false))
  & icacls.exe $Path /inheritance:r | Out-Null
  & icacls.exe $Path /grant:r "$($env:USERDOMAIN)\$($env:USERNAME):(F)" "*S-1-5-18:(R)" "*S-1-5-32-544:(R)" | Out-Null
  if($LASTEXITCODE -ne 0){ throw "Failed to restrict ACL: $Path" }
}

function Invoke-Bootstrap([string]$Endpoint,[string]$Header,[string]$Legacy,[string]$NewToken){
  $headers=@{}
  $headers[$Header]=$Legacy
  $body=@{new_token=$NewToken} | ConvertTo-Json -Compress
  return Invoke-RestMethod -Method Post -Uri ($Endpoint+"?mode=bootstrap_dedicated_credential") -Headers $headers -ContentType "application/json" -Body $body -TimeoutSec 30
}

$supervisorWasEnabled=$false
try{
  $st=Get-ScheduledTask -TaskName $supervisorTask -ErrorAction SilentlyContinue
  if($st){
    $supervisorWasEnabled=($st.State -ne "Disabled")
    Stop-ScheduledTask -TaskName $supervisorTask -ErrorAction SilentlyContinue
    Disable-ScheduledTask -TaskName $supervisorTask | Out-Null
  }
  Stop-ScheduledTask -TaskName $statusTask -ErrorAction SilentlyContinue
  Stop-ScheduledTask -TaskName $shadowTask -ErrorAction SilentlyContinue

  if(Test-Path $statusPath){ throw "Dedicated status token already exists; refusing unintended rotation." }
  if(Test-Path $shadowPath){ throw "Dedicated shadow token already exists; refusing unintended rotation." }
  Remove-Item $statusPending,$shadowPending -Force -ErrorAction SilentlyContinue

  $statusToken=New-Token
  $shadowToken=New-Token
  if($statusToken -eq $shadowToken -or $statusToken -eq $legacy -or $shadowToken -eq $legacy){
    throw "Dedicated token uniqueness guard failed."
  }

  Write-Secret $statusPending $statusToken
  Write-Secret $shadowPending $shadowToken

  $statusBootstrap=Invoke-Bootstrap $statusEndpoint "X-MiniPC-Status-Token" $legacy $statusToken
  if(-not $statusBootstrap.ok -or $statusBootstrap.credential_state -ne "DEDICATED_ENABLED"){
    throw "Status relay credential bootstrap failed."
  }
  Move-Item -LiteralPath $statusPending -Destination $statusPath

  $shadowBootstrap=Invoke-Bootstrap $shadowEndpoint "X-Shadow-Evidence-Token" $legacy $shadowToken
  if(-not $shadowBootstrap.ok -or $shadowBootstrap.credential_state -ne "DEDICATED_ENABLED"){
    throw "Shadow relay credential bootstrap failed."
  }
  Move-Item -LiteralPath $shadowPending -Destination $shadowPath

  & $python -m py_compile $statusTool $shadowTool
  if($LASTEXITCODE -ne 0){ throw "Python compile failed." }

  & $python $statusTool --trading-root $TradingRoot --once
  if($LASTEXITCODE -ne 0){ throw "Dedicated status relay one-shot failed." }

  & $python $shadowTool --trading-root $TradingRoot --once
  if($LASTEXITCODE -ne 0){ throw "Dedicated shadow relay one-shot failed." }

  Start-ScheduledTask -TaskName $statusTask
  Start-ScheduledTask -TaskName $shadowTask

  $deadline=(Get-Date).AddSeconds(45)
  $ok=$false
  while((Get-Date) -lt $deadline){
    Start-Sleep -Seconds 2
    $statusHb=Join-Path $TradingRoot "State\minipc-status-sync-heartbeat.json"
    $shadowHb=Join-Path $TradingRoot "State\v2r4-shadow-cloud-sync-heartbeat.json"
    if((Test-Path $statusHb) -and (Test-Path $shadowHb)){
      try{
        $a=Get-Content $statusHb -Raw | ConvertFrom-Json
        $b=Get-Content $shadowHb -Raw | ConvertFrom-Json
        $ageA=((Get-Date).ToUniversalTime()-([datetime]$a.checked_at_utc).ToUniversalTime()).TotalSeconds
        $ageB=((Get-Date).ToUniversalTime()-([datetime]$b.checked_at_utc).ToUniversalTime()).TotalSeconds
        if($a.status -eq "HEALTHY" -and $b.status -eq "HEALTHY" -and $ageA -lt 30 -and $ageB -lt 30){$ok=$true;break}
      }catch{}
    }
  }
  if(-not $ok){ throw "Fresh HEALTHY relay heartbeats not observed after restart." }

  $sha=[System.Security.Cryptography.SHA256]::Create()
  try{
    $statusHash=([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($statusToken)))).Replace('-','').ToLowerInvariant()
    $shadowHash=([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($shadowToken)))).Replace('-','').ToLowerInvariant()
  } finally {$sha.Dispose()}

  Write-Host ""
  Write-Host "=== RELAY CREDENTIAL CUTOVER RESULT ==="
  Write-Host "Status: PASS"
  Write-Host "Dedicated credentials: 2"
  Write-Host "Shared Altrady token changed: NO"
  Write-Host "Raw dedicated tokens printed: NO"
  Write-Host ("MINIPC_STATUS_SHA256=" + $statusHash)
  Write-Host ("SHADOW_EVIDENCE_SHA256=" + $shadowHash)
  Write-Host "Status relay one-shot: HEALTHY"
  Write-Host "Shadow relay one-shot: HEALTHY"
  Write-Host "Persistent tasks: RESTARTED"
  Write-Host "Real-money/order actions: NONE"
  Write-Host "=== END ==="
}
finally{
  Remove-Variable statusToken,shadowToken,legacy -ErrorAction SilentlyContinue
  if($supervisorWasEnabled){
    Enable-ScheduledTask -TaskName $supervisorTask -ErrorAction SilentlyContinue | Out-Null
    Start-ScheduledTask -TaskName $supervisorTask -ErrorAction SilentlyContinue
  }
}
