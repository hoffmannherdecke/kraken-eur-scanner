[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$WindowDirectory,
 [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{64}$')][string]$ExpectedFixedInputsSha256,
 [Parameter(Mandatory=$true)][Security.SecureString]$AdminPassword,
 [string]$CaFile
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($env:COMPUTERNAME -ine 'MINI-PC'){throw 'ORIGINAL_MINIPC_REQUIRED'}
. (Join-Path $PSScriptRoot 'Flow-Common.ps1')
if($ExpectedFixedInputsSha256 -cne $fixedHash){throw 'PR701_WINDOW_FIXED_ADMISSION_DRIFT'}
$state=Read-Stage4Identity $WindowDirectory
if(-not $WindowDirectory.EndsWith(('PR700-Window-'+$state.stamp),[StringComparison]::Ordinal)){throw 'EXACT_LOCAL_WINDOW_PATH_HOLD'}
$share='D:\V3-PR682-Authority-Handoff\PR700-Window-'+$state.stamp
$owner=Join-Path $WindowDirectory 'stage4-owner-approved.json'
if((Hash-File $owner) -cne (Hash-File (Join-Path $share 'stage4-owner-approved.json'))){throw 'STAGE4_OWNER_HANDOFF_DRIFT'}
$id='V3-ONETIME-'+$state.plan.cas_epoch.epoch_id.Substring(12)
$stem='C:\Users\ADMIN\Trading\State\'+$id
foreach($leaf in ('prepare.attempted','stop.attempted','seal.attempted','cas.attempted','activate.attempted')){
 if(Test-Path -LiteralPath ($stem+'.'+$leaf+'.json')){throw 'PRIOR_PHASE_POSSIBLY_DISPATCHED_USE_READBACK'}
}
$common=@{WindowDirectory=$WindowDirectory;FixedSha256=$fixedHash}
$bind=@{WindowDirectory=$WindowDirectory;ExpectedFixedInputsSha256=$ExpectedFixedInputsSha256}
$executor=@{WindowDirectory=$WindowDirectory;FixedSha256=$fixedHash;AdminPassword=$AdminPassword}
if($CaFile){$common.CaFile=$CaFile;$bind.CaFile=$CaFile;$executor.CaFile=$CaFile}
$phaseScript=Join-Path $PSScriptRoot 'MiniPC-Phase.ps1'
$bindScript=Join-Path $PSScriptRoot 'MiniPC-BindHandoff.ps1'
$prepare=Wait-Phase $share Prepare $state.path $state.end
& $phaseScript -Mode PaperPrepare -NotebookTransfer $prepare -Execute @common
& $bindScript -Phase Prepared @bind
$stopPlan=Join-Path $WindowDirectory 'plan.stop.json'
$stop=Wait-Phase $share Stop $stopPlan $state.end.AddMinutes(-3)
& $phaseScript -Mode PaperStop -NotebookTransfer $stop -Execute @common
do{
 try{
   & $bindScript -Phase PostStop -AdminPassword $AdminPassword @bind
   break
 }catch{
   if($_.Exception.Message -cne 'WAIT_FOR_ORIGINAL_SUPERVISOR_ACK_DO_NOT_REPEAT_STOP' -or
      [DateTimeOffset]::UtcNow -ge $state.end.AddMinutes(-2)){throw}
   Start-Sleep -Seconds 2
 }
}while($true)
$stage='C:\Users\ADMIN\Trading\Staging\V3Paper-INACTIVE-46c5abbd6af1'
$python='C:\Users\ADMIN\Trading\Runtime\kraken-eur-scanner-venv\Scripts\python.exe'
& $python -I -B (Join-Path $PSScriptRoot 'Build-Runtime-Inputs.py') $WindowDirectory $stage --fixed-inputs-sha256 $ExpectedFixedInputsSha256
if($LASTEXITCODE -ne 0){throw 'RUNTIME_INPUT_VALIDATION_HOLD_BEFORE_CAS'}
foreach($leaf in ('runtime-release-packet.json','reviewed-runtime-start-authority.json')){
 Copy-Original (Join-Path $WindowDirectory $leaf) (Join-Path $share $leaf)
}
$plan=Join-Path $WindowDirectory 'plan.cas.json'
$seal=Wait-Phase $share Seal $plan $state.end.AddSeconds(-75)
& $phaseScript -Mode PaperSealEpoch -NotebookTransfer $seal -PostgresPassword $AdminPassword -Execute @common
$ready=Join-Path $share ('seal-'+(Hash-File $plan)+'.ready')
$token=[IO.File]::Open($ready,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
try{$token.WriteByte(1);$token.Flush($true)}finally{$token.Dispose()}
$cas=Wait-Phase $share CasApproval $plan $state.end.AddSeconds(-55)
& (Join-Path $PSScriptRoot 'MiniPC-CasOnce.ps1') -CasApprovalTransfer $cas @executor
& $bindScript -Phase ExecutorClosed -AdminPassword $AdminPassword @bind
$after=[DateTimeOffset]::UtcNow.AddMinutes(10)
$runtime=Wait-Phase $share Runtime $plan $after
$activate=Wait-Phase $share Activate $plan $after
& $phaseScript -Mode PaperActivate -NotebookTransfer $activate -RuntimeTransfer $runtime -Execute @common
'PR701_ACTIVATION_RETURNED_RUNTIME_OBSERVATION_REQUIRED'
