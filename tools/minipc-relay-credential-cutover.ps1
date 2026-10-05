param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading")
)

$ErrorActionPreference = "Stop"

# The legacy bootstrap cutover was completed on 2026-10-05.
# This historical filename is intentionally retained so old runbooks do not point
# at a missing file, but reruns are now verification-only: no token creation,
# rotation, bootstrap request, task mutation, order path or credential output.

$repo=Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$python=Join-Path $TradingRoot "Runtime\kraken-eur-scanner-venv\Scripts\python.exe"
$statusPath=Join-Path $TradingRoot "Secrets\minipc-status-token.txt"
$shadowPath=Join-Path $TradingRoot "Secrets\shadow-evidence-token.txt"
$statusTool=Join-Path $repo "tools\minipc-status-sync.py"
$shadowTool=Join-Path $repo "tools\v2r4-shadow-cloud-sync.py"

foreach($p in @($repo,$python,$statusPath,$shadowPath,$statusTool,$shadowTool)){
  if(-not (Test-Path $p)){ throw "Required post-cutover path missing: $p" }
}

$statusToken=(Get-Content -LiteralPath $statusPath -Raw).Trim()
$shadowToken=(Get-Content -LiteralPath $shadowPath -Raw).Trim()
if($statusToken.Length -lt 24 -or $shadowToken.Length -lt 24){
  throw "Dedicated relay token missing/too short."
}
if($statusToken -eq $shadowToken){
  throw "Dedicated relay credentials must remain distinct."
}

& $python -m py_compile $statusTool $shadowTool
if($LASTEXITCODE -ne 0){ throw "Python compile failed." }

& $python $statusTool --trading-root $TradingRoot --once
if($LASTEXITCODE -ne 0){ throw "Dedicated status relay one-shot failed." }

& $python $shadowTool --trading-root $TradingRoot --once
if($LASTEXITCODE -ne 0){ throw "Dedicated shadow relay one-shot failed." }

$statusHb=Join-Path $TradingRoot "State\minipc-status-sync-heartbeat.json"
$shadowHb=Join-Path $TradingRoot "State\v2r4-shadow-cloud-sync-heartbeat.json"
foreach($p in @($statusHb,$shadowHb)){
  if(-not (Test-Path $p)){ throw "Relay heartbeat missing: $p" }
}
$a=Get-Content $statusHb -Raw | ConvertFrom-Json
$b=Get-Content $shadowHb -Raw | ConvertFrom-Json
if($a.status -ne "HEALTHY" -or $b.status -ne "HEALTHY"){
  throw "Post-cutover relay heartbeat is not HEALTHY."
}

$sha=[System.Security.Cryptography.SHA256]::Create()
try{
  $statusHash=([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($statusToken)))).Replace('-','').ToLowerInvariant()
  $shadowHash=([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($shadowToken)))).Replace('-','').ToLowerInvariant()
} finally {$sha.Dispose()}

Write-Host ""
Write-Host "=== RELAY POST-CUTOVER VERIFY RESULT ==="
Write-Host "Status: PASS"
Write-Host "Mode: VERIFY_ONLY_NO_ROTATION"
Write-Host "Dedicated credentials: 2"
Write-Host "Raw dedicated tokens printed: NO"
Write-Host ("MINIPC_STATUS_SHA256=" + $statusHash)
Write-Host ("SHADOW_EVIDENCE_SHA256=" + $shadowHash)
Write-Host "Status relay one-shot: HEALTHY"
Write-Host "Shadow relay one-shot: HEALTHY"
Write-Host "Credential mutation: NONE"
Write-Host "Real-money/order actions: NONE"
Write-Host "=== END ==="

Remove-Variable statusToken,shadowToken -ErrorAction SilentlyContinue
exit 0
