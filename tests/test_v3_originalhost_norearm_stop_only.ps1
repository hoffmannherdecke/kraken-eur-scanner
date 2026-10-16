# This test NEVER executes the original-host drill or accesses TaskScheduler.
# It parses the source and invokes only a pure task-scope helper.
$ErrorActionPreference='Stop'
$path=Join-Path (Split-Path $PSScriptRoot -Parent) 'tools/minipc-v3-originalhost-norearm-stop-only.ps1'
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile(
  (Resolve-Path $path),[ref]$tokens,[ref]$errors)
if(@($errors).Count -ne 0){throw ('V3_PHYSICAL_STOP_AST_FAIL '+($errors|Out-String))}
$fn=@($ast.FindAll({
  param($item)
  $item -is [Management.Automation.Language.FunctionDefinitionAst] -and
  $item.Name -eq 'Test-ScopedTwo'
},$true))
if($fn.Count -ne 1){throw 'Missing/duplicate pure scope guard'}
. ([Scriptblock]::Create($fn[0].Extent.Text))
$good=@('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait')
if(-not(Test-ScopedTwo $good)){throw 'Correct two-task scope rejected'}
if(-not(Test-ScopedTwo @($good[1],$good[0]))){throw 'Equivalent order rejected'}
$bad=@(
 @(),
 @($good[0]),
 @($good[0],$good[0]),
 @($good[1],$good[1]),
 @($good[0],'CryptoMiniPC-V2R4PaperLifecycle'),
 @($good[0],'CryptoMiniPC-V2R4PaperCloudSync'),
 @($good[0],'CryptoMiniPC-RuntimeSupervisor'),
 @($good[0],'CryptoMiniPC-V3PaperIntake'),
 @($good[0],$good[1],'CryptoMiniPC-V2R4PaperLifecycle')
)
foreach($test in $bad){if(Test-ScopedTwo $test){throw 'Unexpected expanded or corrupted Task scope accepted'}}
$src=Get-Content -LiteralPath $path -Raw
foreach($token in @(
 'if(-not $Execute){',
 'V3_NATIVE_STOP_PREVIEW_ONLY=True',
 'V3-TWO-INTAKE-STOP-ONLY',
 'V3_NATIVE_STOP_PREFLIGHT=PASS',
 'V3_PHYSICAL_NATIVE_NO_REARM=PASS',
 'V3_NEEDS_INDEPENDENT_CLOUD_CHECK_BEFORE_RESTORE=True',
 'V3_WINDOWS_INTAKE_TASKS_REMAIN=DISABLED',
 'ProtectedMarkerWrite $payload $false',
 'ProtectedMarkerWrite $payload $true',
 "Need (WaitSupervisorAndCloud 'QUIESCED'",
 "Disable-ScheduledTask -TaskName $name",
 "Stop-ScheduledTask -TaskName $name",
 'V3_STOPPED_INTAKE=2_OF_2',
 'V3_CAS_IN_THIS_OPERATOR=NEVER'
)){
  if(-not $src.Contains($token)){throw "V3_PHYSICAL_STOP_POLICY_MISSING $token"}
}
if($src.Contains('Enable-ScheduledTask') -or
   $src.Contains('Start-ScheduledTask') -or
   $src.Contains('Register-ScheduledTask') -or
   $src.Contains('Invoke-RestMethod') -or
   $src.Contains('Invoke-WebRequest')){
 throw 'Stop-only operator must not rearm, reinstall, or call Cloud'
}
$allowed=@('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait')
if(@($ast.FindAll({
 param($i) $i -is [Management.Automation.Language.CommandAst] -and
 $i.GetCommandName() -in @('Disable-ScheduledTask','Stop-ScheduledTask')
},$true)).Count -ne 2){throw 'Unexpected number of stop/disable verbs'}
# Regression for originalhost 16-Oct failed preflight: a 63-character
# transcribed SHA256 can NEVER match a real 64-character digest.
# Read complete SHA from previously protected PR332 backup manifest instead.
if($src.Contains('$cloudSha=')){throw 'Unsafe handwritten PR332 cloud SHA still hard-coded'}
foreach($needed in @(
  'PR332-CloudSync-Vorher-20261016-113256-d5c85c73\manifest.json',
  'PR332_CLOUDSYNC_PROTECTED_STAGE_V1',
  'new_source_sha256',
  "^[A-Fa-f0-9]{64}$",
  'new_git_blob_sha1',
  'b97a45d589f6813b28fe94f62fd37e94e764d054',
  'Stop-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue'
)){
 if(-not $src.Contains($needed)){throw "Protected PR332 manifest/no-survivor source check missing: $needed"}
}
if($src.Contains("if([string](Get-ScheduledTask -TaskName $name).State -eq 'Running')")){
 throw 'May not skip Stop-ScheduledTask after disabling a still-running worker'
}
# Evidence-based originalhost supervisor source pin, not a guessed GitHub blob.
# 16 Oct physical Task action SHA is recorded as 64 hex with ...D34BFE36...
$supervisorPin='9B148DB733ED61B9DA673E0E3BB9D319D336CE37FEFF9790D34BFE36B4680EF5'
$wrongSupervisorPin='9B148DB733ED61B9DA673E0E3BB9D319D336CE37FEFF9790D34BEF36B4680EF5'
if($supervisorPin.Length -ne 64 -or -not $src.Contains($supervisorPin) -or
   $src.Contains($wrongSupervisorPin) -or $supervisorPin -eq $wrongSupervisorPin){
 throw 'Originalhost Supervisor SHA identity pin drift or transposition regression'
}
Write-Output 'V3_ORIGINALHOST_SUPERVISOR_64HEX_PIN_REGRESSION_PASS'
Write-Output 'V3_PR334_FULL_PR332_MANIFEST_HASH_PREVIEW_REGRESSION_PASS'
Write-Output 'V3_PHYSICAL_ORIGINALHOST_NO_REARM_STOP_ONLY_PURE_11_SCOPES_PASS'

$restorePath=Join-Path (Split-Path $PSScriptRoot -Parent) 'tools/minipc-v3-originalhost-norearm-restore-only.ps1'
$rtokens=$null;$rerrors=$null
$rast=[Management.Automation.Language.Parser]::ParseFile(
  (Resolve-Path $restorePath),[ref]$rtokens,[ref]$rerrors)
if(@($rerrors).Count -ne 0){throw ('V3_RESTORE_AST_FAIL '+($rerrors|Out-String))}
$restore=Get-Content -LiteralPath $restorePath -Raw
foreach($needle in @(
 'if(-not $Execute){',
 'V3_OLD_INTAKE_RESTORE_PREVIEW_ONLY=True',
 'RESTORE-PRECAS-V2R4-ONLY',
 'OLD-V2R4-ONLY-AND-V3-CAS-ABSENT',
 'V3_OLD_V2R4_NATIVE_RESTORE=PASS',
 'Enable-ScheduledTask -TaskName $name',
 'Start-ScheduledTask -TaskName $name',
 'V3_V2R4_SUPERVISOR_CLOUDSYNC=HEALTHY_ACTIVE_ORIGINAL',
 'V3_CLOUD_CAS=NEVER_INVOKED_BY_OPERATOR'
)){
 if(-not $restore.Contains($needle)){throw "V3_RESTORE_GUARD_MISSING $needle"}
}
foreach($invalid in @(
 'Disable-ScheduledTask','Stop-ScheduledTask','Register-ScheduledTask',
 'Invoke-RestMethod','Invoke-WebRequest','Start-Process'
)){
 if($restore.Contains($invalid)){throw "V3_RESTORE_DISALLOWED_ACTION $invalid"}
}
$functions=@($rast.FindAll({
 param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
 $node.Name -in @('Need','NewMarker')
},$true))
if($functions.Count -ne 2){throw 'Missing scoped pure restore marker functions'}
foreach($item in $functions){. ([Scriptblock]::Create($item.Extent.Text))}
$original='PAPER-V2R4-20261009T110135Z'
$names=@('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait')
function RestoreFixture{
 [pscustomobject]@{
  kind='V3_EXPERIMENTAL_OLD_INTAKE_FENCE_V1'
  phase='QUIESCED'
  predecessor_series_id=$original
  drill_only=$true
  drill_token=('a'*32)
  paper_only=$true
  orders_enabled=$false
  real_money_actions=$false
  persistent_until_explicit_owner_release=$true
  task_names=$names
 }
}
$valid=RestoreFixture
$good=NewMarker $valid 'ARMED'
if($good.phase -ne 'ARMED'){throw 'Valid QUIESCED cannot rearm with bounded manual intent'}
foreach($setting in @('predecessor_series_id','drill_only','phase','task_names','real_money_actions')){
 $fixture=RestoreFixture
 switch($setting){
  'predecessor_series_id'{$fixture.predecessor_series_id='OLD'}
  'drill_only'{$fixture.drill_only=$false}
  'phase'{$fixture.phase='CLOUD_COMMITTED'}
  'task_names'{$fixture.task_names=@($names[0],'CryptoMiniPC-V2R4PaperLifecycle')}
  'real_money_actions'{$fixture.real_money_actions=$true}
 }
 $refused=$false
 try{$null=NewMarker $fixture 'ARMED'}catch{$refused=$true}
 if(-not $refused){throw "Unsafe restore marker variant accepted: $setting"}
}
Write-Output 'V3_PHYSICAL_ORIGINALHOST_MANUAL_CLOUD_GATED_RESTORE_PURE_6_CASES_PASS'
