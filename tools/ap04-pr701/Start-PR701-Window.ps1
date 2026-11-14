[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][ValidateSet('MiniPC','Notebook')][string]$Role,
 [Parameter(Mandatory=$true)][string]$WindowPackageRoot,
 [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{64}$')][string]$PlanSha256,
 [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{64}$')][string]$Stage4ScriptSha256,
 [Parameter(Mandatory=$true)][ValidatePattern('^[0-9]{1,20}$')][string]$DecisionCommentId,
 [string]$CaFile
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if(($Role -eq 'MiniPC') -ne ($env:COMPUTERNAME -ieq 'MINI-PC')){throw 'PR701_EXACT_DEVICE_ROLE_REQUIRED'}
. (Join-Path $PSScriptRoot 'Flow-Common.ps1')
$expectedFixedInputsSha256=$fixedHash
if((Hash-File (Join-Path $WindowPackageRoot 'cutover-fixed-inputs.json')) -cne $expectedFixedInputsSha256){throw 'EXACT_PR701_WINDOW_FIXED_HASH_REQUIRED'}
$folder=Join-Path $WindowPackageRoot 'freigabefenster'
$stage4=Join-Path $folder 'pr700-stage4.ps1'
if((Hash-File $stage4) -cne $Stage4ScriptSha256){throw 'STAGE4_SCRIPT_HASH_HOLD'}
$plans=@(Get-ChildItem -LiteralPath $folder -File -Filter 'pr700-stage4-plan-*.json')
if($plans.Count -ne 1 -or (Hash-File $plans[0].FullName) -cne $PlanSha256){throw 'EXACT_STAGE4_PLAN_REQUIRED'}
$plan=Get-Content -LiteralPath $plans[0].FullName -Raw|ConvertFrom-Json
if($plan.repo_sha -cne '46c5abbd6af16266c1229943db973dc9d6b2fb4f' -or $plan.series_id -cnotmatch '^PAPER-V3-[0-9]{8}T[0-9]{6}Z$'){
 throw 'EXACT_PR701_WINDOW_IDENTITY_REQUIRED'
}
$stamp=$plan.series_id.Substring(9)
$end=[DateTimeOffset]::ParseExact($stamp,"yyyyMMdd'T'HHmmss'Z'",[Globalization.CultureInfo]::InvariantCulture,[Globalization.DateTimeStyles]::AssumeUniversal).AddMinutes(10)
if([DateTimeOffset]::UtcNow -ge $end.AddMinutes(-6)){throw 'INSUFFICIENT_WINDOW_BUDGET_NO_STAGE4'}
$launch=@{Role=$Role;DecisionCommentId=$DecisionCommentId}
$sequence=@{}
if($CaFile){$launch.CaFile=$CaFile;$sequence.CaFile=$CaFile}
if($Role -eq 'Notebook'){
    & $stage4 @launch
    $share='\\192.168.178.179\Mistral_450\V3-PR682-Authority-Handoff\PR700-Window-'+$stamp
    do{
      if([DateTimeOffset]::UtcNow -ge $end){throw 'NO_WINDOW_HANDOFF_READBACK_REQUIRED'}
      if(Test-Path -LiteralPath (Join-Path $share 'plan.stage4.json')){break}
      Start-Sleep -Milliseconds 300
    }while($true)
    & (Join-Path $PSScriptRoot 'Notebook-Sequence.ps1') -SeriesStamp $stamp @sequence
    return
}
$local='C:\Users\ADMIN\Trading\Research\V3Paper\PR700-Window-'+$stamp
& (Join-Path $PSScriptRoot 'MiniPC-InitializeWindow.ps1') -WindowPackageRoot $WindowPackageRoot -ExpectedPlanSha256 $PlanSha256
$admin=Read-Host 'Bestehendes PostgreSQL-Administratorpasswort nur lokal' -AsSecureString
try{
    $handoff='D:\V3-PR682-Authority-Handoff\PR700-Stage4-'+$stamp
    do{
      if([DateTimeOffset]::UtcNow -ge $end.AddMinutes(-5)){throw 'STAGE4_HANDOFF_TOO_LATE_NO_DISPATCH'}
      if(Test-Path -LiteralPath (Join-Path $handoff 'approval-envelope.json')){break}
      Start-Sleep -Milliseconds 300
    }while($true)
    & $stage4 -AdminPassword $admin @launch
    & (Join-Path $PSScriptRoot 'MiniPC-Sequence.ps1') -WindowDirectory $local -ExpectedFixedInputsSha256 $expectedFixedInputsSha256 -AdminPassword $admin @sequence
}finally{$admin.Dispose()}
