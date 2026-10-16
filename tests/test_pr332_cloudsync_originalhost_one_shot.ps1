# This CI file parses the original-host one-shot source but NEVER executes the
# script's runtime code, PowerShell TaskScheduler actions, files or processes.
$ErrorActionPreference='Stop'
$path=Join-Path $PSScriptRoot '../tools/minipc-pr332-cloudsync-protected-switch.ps1'
$tokens=$null;$errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile(
  (Resolve-Path $path),[ref]$tokens,[ref]$errors)
if($errors.Count -ne 0){throw ('PR332 operator PowerShell syntax invalid: '+($errors|Out-String))}
$functions=@($ast.FindAll({
 param($item)
 $item -is [Management.Automation.Language.FunctionDefinitionAst] -and
 $item.Name -in @('Require','Get-Pr332TaskXml','Test-Pr332TaskFamily')
},$true))
if($functions.Count -ne 3){throw 'Missing/duplicate pure helpers'}
foreach($item in $functions){. ([Scriptblock]::Create($item.Extent.Text))}
$old='C:\Original\v2r4-paper-cloud-sync.py'
$new='C:\Staging\v2r4-paper-cloud-sync.py'
$xml=@'
<?xml version="1.0"?>
<Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
<RegistrationInfo><Author>Test</Author></RegistrationInfo>
<Triggers><TimeTrigger><StartBoundary>2026-10-16T08:00:00</StartBoundary></TimeTrigger></Triggers>
<Principals><Principal id="Author"><UserId>S-1-5-18</UserId></Principal></Principals>
<Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy></Settings>
<Actions Context="Author">
<Exec><Command>C:\Python\python.exe</Command>
<Arguments>-u "C:\Original\v2r4-paper-cloud-sync.py" --interval-seconds 60</Arguments>
</Exec></Actions></Task>
'@
function Check([bool]$ok,[string]$why){if(-not $ok){throw $why}}
$y=Get-Pr332TaskXml $xml $old $new
[xml]$out=$y
$ns=[Xml.XmlNamespaceManager]::new($out.NameTable)
$ns.AddNamespace('t',$out.DocumentElement.NamespaceURI)
Check ($out.SelectSingleNode('/t:Task/t:Actions/t:Exec/t:Arguments',$ns).InnerText.Contains($new)) 'New staged script not set'
Check (-not $out.SelectSingleNode('/t:Task/t:Actions/t:Exec/t:Arguments',$ns).InnerText.Contains($old)) 'Old script remained'
Check ($out.SelectSingleNode('/t:Task/t:Settings/t:Enabled',$ns).InnerText -eq 'false') 'Task must register Disabled first'
Check ($out.SelectSingleNode('/t:Task/t:Actions/t:Exec/t:Command',$ns).InnerText -eq 'C:\Python\python.exe') 'Python executable changed'
Check ($out.SelectSingleNode('/t:Task/t:Settings/t:MultipleInstancesPolicy',$ns).InnerText -eq 'IgnoreNew') 'MultipleInstances changed'
foreach($bad in @(
 $xml.Replace($old,'C:\Wrong\other.py'),
 $xml.Replace($old,$old+' '+$old),
 $xml.Replace('<Arguments>','<RemovedArguments>').Replace('</Arguments>','</RemovedArguments>'),
 $xml.Replace('</Actions>','<Exec><Command>other.exe</Command><Arguments>hello</Arguments></Exec></Actions>')
)){
 $thrown=$false
 try{$null=Get-Pr332TaskXml $bad $old $new}catch{$thrown=$true}
 Check $thrown 'Unsafe task arguments/actions accepted'
}
$parent=[pscustomobject]@{ProcessId=100;ParentProcessId=1}
$child=[pscustomobject]@{ProcessId=200;ParentProcessId=100}
$indep=[pscustomobject]@{ProcessId=300;ParentProcessId=1}
Check (Test-Pr332TaskFamily @($parent,$child)) 'One proper parent/child rejected'
Check (-not (Test-Pr332TaskFamily @($parent))) 'Single Python accepted'
Check (-not (Test-Pr332TaskFamily @($parent,$indep))) 'Independent Python processes accepted'
Check (-not (Test-Pr332TaskFamily @($parent,$child,$indep))) 'Extra cloud process accepted'
$src=Get-Content -LiteralPath $path -Raw
foreach($required in @(
 'PR332-CLOUDSYNC-ONLY','CLOUDSYNC_ORIGINALHOST_PREFLIGHT=PASS',
 'PR332_CLOUDSYNC_SWITCH=PASS',
 'PR332_ROLLBACK=',
 'switch-attempted.json',
 'WaitNoOldOrNew 35',
 'Require (WaitHealthy $newSource $started $true)',
 'Require (WaitHealthy $oldSource $returnAt $false)'
)){
 Check ($src.Contains($required)) ('Source guard missing: '+$required)
}
Write-Output 'PR332_CLOUDSYNC_ORIGINALHOST_ONE_SHOT_14_PURE_TESTS_PASS'
