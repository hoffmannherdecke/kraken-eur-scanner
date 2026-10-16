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
Write-Output 'V3_PHYSICAL_ORIGINALHOST_NO_REARM_STOP_ONLY_PURE_11_SCOPES_PASS'
