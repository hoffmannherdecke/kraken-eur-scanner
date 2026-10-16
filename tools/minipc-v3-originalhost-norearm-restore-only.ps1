param(
 [string]$TradingRoot='C:\Users\ADMIN\Trading',
 [switch]$Execute,
 [string]$Confirm='',
 [string]$IndependentCloudReadback=''
)
# Manual original V2R4 rollback AFTER ChatGPT independently confirms Cloud
# exactly one active old series + V3 CAS absent / never invoked. NO HTTP here.
# Default is preview. A QUIESCED marker MUST persist until V2R4 fully healthy.
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath($TradingRoot).TrimEnd('\')
$names=@('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait')
$original='PAPER-V2R4-20261009T110135Z'
$fence=Join-Path $root 'State\v3-experimental-paper-old-intake-fence.json'
$legacy=Join-Path $root 'State\v2r4-technical-cutover-maintenance.json'
$supFile=Join-Path $root 'State\minipc-runtime-supervisor.json'
$cloudFile=Join-Path $root 'State\v2r4-paper-cloud-sync-heartbeat.json'
$hb=@(
 (Join-Path $root 'State\v2r4-paper-candidate-runtime-heartbeat.json'),
 (Join-Path $root 'State\v2r4-paper-wait-runtime-heartbeat.json')
)
function Need([bool]$Ok,[string]$Why){if(-not $Ok){throw $Why}}
function Fresh([string]$File,[int]$MaxAge=160){
  $r=Get-Content -LiteralPath $File -Raw -ErrorAction Stop|ConvertFrom-Json
  $age=([datetime]::UtcNow-([datetime]$r.checked_at_utc).ToUniversalTime()).TotalSeconds
  Need ($age -ge -5 -and $age -le $MaxAge) 'Original-host heartbeat missing or stale'
  return $r
}
function NewMarker([object]$Current,[string]$Phase) {
  Need ($Current.kind -eq 'V3_EXPERIMENTAL_OLD_INTAKE_FENCE_V1' -and
        $Current.predecessor_series_id -eq $original -and
        $Current.drill_only -eq $true -and
        [string]$Current.drill_token -match '^[a-f0-9]{32}$' -and
        $Current.paper_only -eq $true -and
        $Current.orders_enabled -eq $false -and
        $Current.real_money_actions -eq $false -and
        $Current.persistent_until_explicit_owner_release -eq $true -and
        (@($Current.task_names|Sort-Object) -join '|') -ceq
        ((@($names|Sort-Object)) -join '|')) 'Original marker owner/scope invalid'
  Need ($Current.phase -eq 'QUIESCED') 'Not an original physical QUIESCED drill'
  $Current.phase=$Phase
  return $Current
}
function AtomicMarkerChange([object]$Current){
  $temp=$fence+'.'+[guid]::NewGuid().ToString('N')+'.tmp'
  [IO.File]::WriteAllText($temp,($Current|ConvertTo-Json -Depth 5),
     [Text.UTF8Encoding]::new($false))
  $acl=Get-Acl -LiteralPath $fence
  Set-Acl -LiteralPath $temp -AclObject $acl
  [IO.File]::Replace($temp,$fence,$null,$true)
}
function ScriptFromTask([object]$Task){
  Need (@($Task.Actions).Count -eq 1 -and [string]$Task.TaskPath -eq '\') 'Not exactly one native root Task action'
  Need ([string]$Task.Principal.UserId -in @('SYSTEM','NT AUTHORITY\SYSTEM','S-1-5-18')) 'Task SYSTEM principal drift'
  $m=@([regex]::Matches([string]$Task.Actions[0].Arguments,'"([^"]+\.py)"'))
  Need ($m.Count -eq 1 -and [string]$Task.Actions[0].Execute -match '(?i)(?:^|[\\/])pythonw?\.exe$') 'Expected native Python script not unique'
  return $m[0].Groups[1].Value
}
function ReadNative([string]$Name,[string]$State) {
  Need ($Name -in $names) 'Unsupported Task'
  $t=Get-ScheduledTask -TaskName $Name -ErrorAction Stop
  Need ([string]$t.State -eq $State -and
    [string]$t.Settings.MultipleInstances -eq 'IgnoreNew') ('Native Task state not '+$State)
  return $t
}
function FamilyPids([string[]]$Sources){
  $all=@(Get-CimInstance Win32_Process -ErrorAction Stop)
  $roots=@($all|Where-Object {
    $line=([string]$_.CommandLine).Replace('\','/')
    @($Sources|Where-Object {
      $line.IndexOf($_.Replace('\','/'),[StringComparison]::OrdinalIgnoreCase) -ge 0
    }).Count -gt 0
  })
  $ids=@($roots|ForEach-Object {[int]$_.ProcessId})
  do{
    $before=$ids.Count
    $ids=@($ids + @($all|Where-Object {$_.ParentProcessId -in $ids}|
      ForEach-Object {[int]$_.ProcessId}) | Sort-Object -Unique)
  }while($ids.Count -ne $before)
  return @($ids)
}
Need ($root -ieq 'C:\Users\ADMIN\Trading') 'Not the original Trading host path'
Need (-not(Test-Path -LiteralPath $legacy)) 'Foreign maintenance marker'
Need (Test-Path -LiteralPath $fence -PathType Leaf) 'No original V3 QUIESCED marker'
$marker=Get-Content -LiteralPath $fence -Raw -ErrorAction Stop|ConvertFrom-Json
$null=NewMarker $marker 'QUIESCED'
$supervisor=Fresh $supFile;$cloud=Fresh $cloudFile
Need ($supervisor.status -eq 'WARNING' -and
  $supervisor.v3_paper_old_intake_fence.mode -eq 'QUIESCED' -and
  $cloud.status -eq 'HEALTHY' -and
  $cloud.mode -eq 'V3_PRECOMMIT_NO_NETWORK_HOLD' -and
  $cloud.cloud_updated -eq $false) 'QUIESCED original host no-network preflight missing'
$sourcePaths=@()
foreach($name in $names){$sourcePaths+=@(ScriptFromTask (ReadNative $name 'Disabled'))}
Need (@(FamilyPids $sourcePaths).Count -eq 0) 'Original intake process still running'
# Restoration must match the distinct intact 15-Oct Candidates and post-PR326
# 16-Oct WAIT original native Task action/arguments, not merely Task names.
$origFolders=@(Get-ChildItem -LiteralPath (Join-Path $root 'Backups') -Directory|
  Where-Object {$_.Name -like 'V3-Intake-Original-20261015-073139-*'})
$waitFolders=@(Get-ChildItem -LiteralPath (Join-Path $root 'Backups') -Directory|
  Where-Object {$_.Name -like 'V3-WAIT-PR326-Current-20261016-*'})
Need ($origFolders.Count -eq 1 -and $waitFolders.Count -eq 1) 'Original backup vintage ambiguously located'
$prior=Get-Content (Join-Path $origFolders[0].FullName 'backup-manifest.json') -Raw |ConvertFrom-Json
$post=Get-Content (Join-Path $waitFolders[0].FullName 'backup-manifest.json') -Raw |ConvertFrom-Json
$expectedCandidates=@($prior.tasks|Where-Object {$_.task_name -eq $names[0]})
Need ($expectedCandidates.Count -eq 1) 'Original Candidates backup manifest invalid'
$proofs=@(
 [pscustomobject]@{name=$names[0];path=(Join-Path $origFolders[0].FullName 'Candidates.task.xml');sha=$expectedCandidates[0].xml_sha256},
 [pscustomobject]@{name=$names[1];path=(Join-Path $waitFolders[0].FullName 'WAIT.task.xml');sha=$post.xml_sha256}
)
foreach($proof in $proofs){
 Need ((Get-FileHash -LiteralPath $proof.path -Algorithm SHA256).Hash -eq [string]$proof.sha) 'Native rollback file SHA drift'
 [xml]$old=Get-Content -LiteralPath $proof.path -Raw
 $ns=[Xml.XmlNamespaceManager]::new($old.NameTable)
 $ns.AddNamespace('t',$old.DocumentElement.NamespaceURI)
 $cmd=$old.SelectSingleNode('/t:Task/t:Actions/t:Exec/t:Command',$ns)
 $arguments=$old.SelectSingleNode('/t:Task/t:Actions/t:Exec/t:Arguments',$ns)
 Need ($null -ne $cmd -and $null -ne $arguments) 'Native backup executable/action absent'
 $live=Get-ScheduledTask -TaskName $proof.name
 Need (@($live.Actions).Count -eq 1 -and
       [string]$live.Actions[0].Execute -ceq [string]$cmd.InnerText -and
       [string]$live.Actions[0].Arguments -ceq [string]$arguments.InnerText) 'Protected original native Task action changed'
}
foreach($name in @('CryptoMiniPC-V2R4PaperLifecycle','CryptoMiniPC-V2R4PaperCloudSync')){
 Need ([string](Get-ScheduledTask -TaskName $name).State -eq 'Running') 'Protected aftercare task unhealthy'
}
Write-Output 'V3_OLD_INTAKE_RESTORE_PREFLIGHT=PASS'
if(-not $Execute){Write-Output 'V3_OLD_INTAKE_RESTORE_PREVIEW_ONLY=True';return}
Need ($Confirm -ceq 'RESTORE-PRECAS-V2R4-ONLY') 'Exact manual rollback action gate absent'
Need ($IndependentCloudReadback -ceq 'OLD-V2R4-ONLY-AND-V3-CAS-ABSENT') 'Independent external Cloud readback acknowledgment absent'
$modified=$false
try{
 $armed=NewMarker $marker 'ARMED'
 AtomicMarkerChange $armed
 $armedAt=[datetime]::UtcNow
 # Still marked ARMED, Supervisor cannot rearm unexpectedly.
 foreach($name in $names){Enable-ScheduledTask -TaskName $name -ErrorAction Stop|Out-Null;$modified=$true}
 foreach($name in $names){Start-ScheduledTask -TaskName $name -ErrorAction Stop}
 $end=(Get-Date).AddSeconds(210)
 $healthy=$false
 do{
   Start-Sleep -Seconds 4
   $rows=@($names|Where-Object {[string](Get-ScheduledTask -TaskName $_).State -eq 'Running'})
   $good=($rows.Count -eq 2)
   if($good){
     foreach($path in $hb){
       try{
         $h=Fresh $path 190
         $good=$good -and ($h.status -eq 'HEALTHY') -and
           ([datetime]$h.checked_at_utc).ToUniversalTime() -gt $armedAt
       }catch{$good=$false}
     }
   }
   $healthy=$good
 }while(-not $healthy -and (Get-Date) -lt $end)
 Need $healthy 'Both original Task running/heartbeat fresh did not recover'
 # Only our exact owned pre-CAS marker can be cleared after rearm.
 $confirmMarker=Get-Content -LiteralPath $fence -Raw |ConvertFrom-Json
 Need ($confirmMarker.drill_token -eq $marker.drill_token -and
       $confirmMarker.phase -eq 'ARMED') 'Marker owner or phase changed before removal'
 Remove-Item -LiteralPath $fence -Force -ErrorAction Stop
 $normalTime=[datetime]::UtcNow
 $normal=$false
 $end=(Get-Date).AddSeconds(180)
 do {
   Start-Sleep -Seconds 4
   try{
     $s=Fresh $supFile 170;$c=Fresh $cloudFile 170
     $normal=$s.status -eq 'HEALTHY' -and
       $s.v3_paper_old_intake_fence.mode -eq 'NONE' -and
       $c.status -eq 'HEALTHY' -and
       $c.v3_fence_cloud_sync_lane -eq 'ACTIVE_ORIGINAL' -and
       $c.series_id -eq $original -and
       ([datetime]$s.checked_at_utc).ToUniversalTime() -gt $normalTime -and
       ([datetime]$c.checked_at_utc).ToUniversalTime() -gt $normalTime
   }catch{$normal=$false}
 }while(-not $normal -and (Get-Date) -lt $end)
 Need $normal 'Normal-mode fresh Supervisors/CloudSync follow-up not yet proven'
 Write-Output 'V3_OLD_V2R4_NATIVE_RESTORE=PASS'
 Write-Output 'V3_ORIGINAL_INTAKE_TASKS=RUNNING_2_OF_2'
 Write-Output 'V3_MARKER=ABSENT'
 Write-Output 'V3_V2R4_SUPERVISOR_CLOUDSYNC=HEALTHY_ACTIVE_ORIGINAL'
 Write-Output 'V3_CLOUD_CAS=NEVER_INVOKED_BY_OPERATOR'
}catch{
 Write-Warning ('V3_MANUAL_RESTORE_REVIEW_REQUIRED: '+$_.Exception.Message)
 # NO automatic new emergency change here; status may be partial. If the
 # marker was removed after Task recovery, do not recreate an unknown marker.
 # If marker remains ARMED, it protects against Supervisor double restarts.
 throw
}
