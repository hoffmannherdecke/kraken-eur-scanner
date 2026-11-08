# Offline operator fault injection; never contacts a host, Cloud or task.
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$root=Split-Path $PSScriptRoot -Parent
Import-Module (Join-Path $root 'tools/v3-one-time-release-authorization.psm1') -Force
. (Join-Path $root 'tools/v3-one-time-paper-release.ps1')
function Need($x,$why){if(-not $x){throw $why}}
function Reject([scriptblock]$f,[string]$message){
 try{& $f;throw 'EXPECTED_REJECTION_MISSING'}catch{
  if($_.Exception.Message -notlike ('*'+$message+'*')){throw}
 }
}
foreach($file in @('tools/v3-one-time-paper-release.ps1','tools/v3-one-time-release.ps1')){
 $t=$null;$e=$null
 $null=[Management.Automation.Language.Parser]::ParseFile((Join-Path $root $file),[ref]$t,[ref]$e)
 Need ($e.Count -eq 0) 'PAPER_PARSE_FAILURE'
}
$inventoryWire=& (Join-Path $root 'tools/v3-one-time-release.ps1') -Mode PaperInventory -PackageRoot $root
$inventory=$inventoryWire|ConvertFrom-Json
Need ($inventory.production_authorized -eq $false -and $inventory.cloud_contacted -eq $false -and
 $inventory.host_mutated -eq $false -and @($inventory.artifacts.PSObject.Properties).Count -eq 14) 'PRODUCTIVE_INVENTORY_NOT_INERT_OR_INCOMPLETE'
# .NET Framework PowerShell 5.1 resolves CMS from System.Security.
if($null -eq ('System.Security.Cryptography.Pkcs.SignedCms' -as [type])){
 Add-Type -AssemblyName System.Security
}
# Real ephemeral CMS signature, pin and freshness tests; no mock verifier.
$rsa=[Security.Cryptography.RSA]::Create(2048)
$req=[Security.Cryptography.X509Certificates.CertificateRequest]::new('CN=OFFLINE-NOT-RELEASE-AUTHORITY',$rsa,
 [Security.Cryptography.HashAlgorithmName]::SHA256,[Security.Cryptography.RSASignaturePadding]::Pkcs1)
$cert=$req.CreateSelfSigned([datetimeoffset]::UtcNow.AddMinutes(-1),[datetimeoffset]::UtcNow.AddMinutes(10))
$pin=Get-V3ReleaseSha256 $cert.RawData
$tmp=Join-Path ([IO.Path]::GetTempPath()) ('v3-paper-test-'+[guid]::NewGuid().ToString('N'))
$null=New-Item $tmp -ItemType Directory
try{
 $ctx=[pscustomobject]@{commit=('a'*40);authorization=@{claims=@{release_id='V3-ONETIME-test';bindings=@{reader_certificate_sha256=$pin;plan_sha256=('b'*64)}}}}
 $r=[ordered]@{release_commit=('a'*40);release_id='V3-ONETIME-test';plan_sha256=('b'*64);observed_at_utc=[datetimeoffset]::UtcNow.ToString('o');state='TEST_ONLY'}
 function SaveSigned($row){
  $bytes=[Text.Encoding]::UTF8.GetBytes(($row|ConvertTo-Json -Depth 12 -Compress))
  $cms=[Security.Cryptography.Pkcs.SignedCms]::new([Security.Cryptography.Pkcs.ContentInfo]::new($bytes),$true)
  $signer=[Security.Cryptography.Pkcs.CmsSigner]::new($cert)
  $signer.DigestAlgorithm=[Security.Cryptography.Oid]::new('2.16.840.1.101.3.4.2.1')
  $cms.ComputeSignature($signer)
  [IO.File]::WriteAllBytes((Join-Path $tmp 'receipt.json'),$bytes)
  [IO.File]::WriteAllBytes((Join-Path $tmp 'receipt.cms'),$cms.Encode())
 }
 SaveSigned $r
 $valid=Read-V3PaperIndependentReceipt $ctx (Join-Path $tmp 'receipt.json') (Join-Path $tmp 'receipt.cms')
 Need ($valid.state -ceq 'TEST_ONLY') 'REAL_CMS_PROVIDER_FAILED'
 $ctx.commit='c'*40
 Reject {Read-V3PaperIndependentReceipt $ctx (Join-Path $tmp 'receipt.json') (Join-Path $tmp 'receipt.cms')} 'CURRENT_RECEIPT_HOLD'
 $ctx.commit='a'*40;$r.observed_at_utc=[datetimeoffset]::UtcNow.AddSeconds(-91).ToString('o');SaveSigned $r
 Reject {Read-V3PaperIndependentReceipt $ctx (Join-Path $tmp 'receipt.json') (Join-Path $tmp 'receipt.cms')} 'CURRENT_RECEIPT_HOLD'
 $r.observed_at_utc=[datetimeoffset]::UtcNow.AddMinutes(1).ToString('o');SaveSigned $r
 Reject {Read-V3PaperIndependentReceipt $ctx (Join-Path $tmp 'receipt.json') (Join-Path $tmp 'receipt.cms')} 'CURRENT_RECEIPT_HOLD'
 $r.observed_at_utc=[datetimeoffset]::UtcNow.ToString('o');SaveSigned $r
 [IO.File]::AppendAllText((Join-Path $tmp 'receipt.json'),' ')
 Reject {Read-V3PaperIndependentReceipt $ctx (Join-Path $tmp 'receipt.json') (Join-Path $tmp 'receipt.cms')} 'signature'
 # Genuine signed Cloud witness and separately signed operating lease.
 $commit='a'*40
 $id='V3-ONETIME-'+('b'*32)
 $sid='PAPER-V3-20261108T110000Z'
 $plan=@{series_id=$sid;bundle_sha256=('c'*64);strategy_sha256=('d'*64);
  cas_request=@{new_v3_config=@{}}}
 $cloud=[ordered]@{kind='V3_PAPER_RELEASE_EPOCH_READER_V1';state='CAS_COMMITTED_EXACT_SUCCESSOR_SINGLE_ACTIVE';
  release_commit=$commit;release_id=$id;plan_sha256=('e'*64);repo_sha=$commit;successor_series_id=$sid;
  bundle_sha256=$plan.bundle_sha256;strategy_sha256=$plan.strategy_sha256;observed_at_utc=[datetimeoffset]::UtcNow.ToString('o')}
 foreach($key in @('preinvoke_epoch_id','preinvoke_intent_id','preinvoke_request_sha256',
   'preinvoke_source_sha256','preinvoke_fence_sha256','preinvoke_inhibit_receipt_sha256')){
  $cloud[$key]='fixture-'+$key
  $plan.cas_request.new_v3_config[$key]=$cloud[$key]
 }
 SaveSigned $cloud
 $cloudJson=Join-Path $tmp 'cloud.json';$cloudCms=Join-Path $tmp 'cloud.cms'
 Move-Item (Join-Path $tmp 'receipt.json') $cloudJson
 Move-Item (Join-Path $tmp 'receipt.cms') $cloudCms
 $packetPath=Join-Path $tmp 'packet.json'
 $packetBytes=[Text.Encoding]::UTF8.GetBytes('{"primary_decision_route":"FREE_RULE_P4","bounded_research_scope":{"max_candidates":4,"max_observation_days":1}}')
 [IO.File]::WriteAllBytes($packetPath,$packetBytes)
 $static=[ordered]@{native_task_action_sha256=('a'*64);native_task_launcher_file_sha256=('b'*64);
  approved_six_proof_release_packet_sha256=('a'*64);runtime_release_packet_file_sha256=(Get-V3ReleaseSha256 $packetBytes);
  six_external_original_e2e_proofs_approved=$true;
  successor_series_assignment=@{release_owner='https://github.com/hoffmannherdecke/kraken-eur-scanner/issues/99';
   decision='ISSUED_FOR_EXACT_RUNTIME_RELEASE';independent_decision_reference='https://github.com/hoffmannherdecke/kraken-eur-scanner/issues/99#issuecomment-1';
   successor_series_id=$sid;repo_sha=$commit;code_fingerprint_sha256=$plan.bundle_sha256;strategy_fingerprint_sha256=$plan.strategy_sha256};
  maintenance_release_repo_sha=$commit;maintenance_receipt_kind='V3_EXISTING_MINIPC_MAINTENANCE_ORIGINALHOST_ACK_V1';
  maintenance_receipt_sha256=('c'*64);maintenance_completed_at_utc=[datetimeoffset]::UtcNow.AddDays(-1).ToString('o');
  maintenance_cpu_bios_boot_thermal_originalhost_pass=$true;maintenance_windows_drivers_reboots_originalhost_pass=$true;
  maintenance_scripts_originalhost_source_ack_pass=$true;maintenance_v2r4_restart_and_aftercare_originalhost_pass=$true;
  paper_only=$true;real_money_actions=$false}
 $artifacts=@{'tools/a.ps1'=('a'*64);'tools/b.ps1'=('b'*64)}
 $claims=[ordered]@{kind='V3_ONE_TIME_RELEASE_AUTHORIZATION_V1';release_id=$id;scope='V3_PAPER_RUNTIME_REPEATED';
  base_commit='5b1789e349b157d06d3109c5f0ff10d95154bf81';release_commit=$commit;
  not_before_utc=[datetime]::UtcNow.AddSeconds(-5).ToString("yyyy-MM-dd'T'HH:mm:ss'Z'");
  expires_at_utc=[datetime]::UtcNow.AddMinutes(5).ToString("yyyy-MM-dd'T'HH:mm:ss'Z'");
  project_ref='nlgzjmqgwueojlyqmoru';computer_name='MINI-PC';trading_root='C:\Users\ADMIN\Trading';artifacts=$artifacts;
  bindings=@{reader_certificate_sha256=$pin;plan_sha256=$cloud.plan_sha256;
   host_receipt_sha256=(Get-V3ReleaseSha256 ([IO.File]::ReadAllBytes($cloudJson)));start_authority=$static}}
 function ReadRuntimeFixture {
  SaveSigned $claims
  $payload=[IO.File]::ReadAllBytes((Join-Path $tmp 'receipt.json'))
  $cmsBytes=[IO.File]::ReadAllBytes((Join-Path $tmp 'receipt.cms'))
  return (Assert-V3OneTimeReleaseAuthorization -Payload $payload -Cms $cmsBytes -ReviewedAuthorityCertificateSha256 $pin `
   -Scope V3_PAPER_RUNTIME_REPEATED -ExpectedReleaseCommit $commit -ExpectedArtifacts $artifacts)
 }
 $startupContext=[pscustomobject]@{commit=$commit;authorization=(ReadRuntimeFixture);plan=$plan}
 $observedCloud=Read-V3PaperIndependentReceipt $startupContext $cloudJson $cloudCms
 $startLease=Get-V3PaperRepeatedStart $startupContext @{release_packet=$packetPath} $observedCloud
 Need ($startLease.scope -ceq 'V3_PAPER_RUNTIME_REPEATED') 'SIGNED_START_REQUIRES_LIVE_TASK'
 $observedCloud.successor_series_id='PAPER-V3-20261108T120000Z'
 Reject {Get-V3PaperRepeatedStart $startupContext @{release_packet=$packetPath} $observedCloud} 'START_CLOUD_RECEIPT_HOLD'
 $observedCloud.successor_series_id=$sid
 [IO.File]::AppendAllText($packetPath,' ')
 Reject {Get-V3PaperRepeatedStart $startupContext @{release_packet=$packetPath} $observedCloud} 'START_PROOF_BINDING_HOLD'
 $claims.expires_at_utc=[datetime]::UtcNow.AddSeconds(-1).ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
 Reject {ReadRuntimeFixture} 'APPROVAL_EXPIRED_OR_FUTURE_HOLD'
 # Durable latch is crash-safe and cannot be reopened as a second attempt.
 Write-V3PaperReceipt (Join-Path $tmp 'attempt.json') @{state='DISPATCH_UNKNOWN'}
 Reject {Write-V3PaperReceipt (Join-Path $tmp 'attempt.json') @{state='RETRY'}} 'already exists'
 Need ((Get-Content (Join-Path $tmp 'attempt.json') -Raw|ConvertFrom-Json).state -ceq 'DISPATCH_UNKNOWN') 'UNKNOWN_OVERWRITTEN'
 # Typed SQL encoding prevents quotes, dollar tags, Unicode and backslashes
 # in config/test identifiers from escaping a data literal.
 $request=[ordered]@{}
 foreach($key in @('expected_old_series_id','expected_old_release_sha','expected_old_strategy_sha256','expected_old_runtime_sha256',
  'expected_old_candidate_count','expected_old_trade_count','expected_old_last_outcome_updated_at','expected_old_last_trade_updated_at',
  'proposed_v3_series_id','proposed_v3_test_id','proposed_v3_revision','cutover_at_utc','new_v3_config',
  'reviewed_new_repo_sha','reviewed_new_bundle_sha256','reviewed_new_strategy_sha256')){$request[$key]='x'}
 $request.expected_old_candidate_count=2;$request.expected_old_trade_count=0
 $request.expected_old_last_trade_updated_at=$null
 $request.new_v3_config=@{attack="'; DROP TABLE public.paper_series; --";unicode='ü'}
 $sql=Get-V3PaperCasCallSql ([pscustomobject]$request)
 Need (-not $sql.Contains('DROP TABLE')) 'SQL_INJECTION'
 Need ($sql.Contains('NULL::timestamptz')) 'NULL_TYPED_TIMESTAMP_LOST'
 Need (([regex]::Matches($sql,'convert_from\(decode\(')).Count -eq 15) 'RPC_ARGUMENT_LOST'
 $request.extra='forbidden'
 Reject {Get-V3PaperCasCallSql ([pscustomobject]$request)} 'EXACT_16_ARGUMENTS'
 $original=[IO.File]::ReadAllText((Join-Path $root 'supabase/v3-experimental-paper-atomic-cas-INACTIVE-20261013.sql'))
 $released=Get-V3PaperCasInstallSql $original @{authorization=@{expires_at=[datetimeoffset]::UtcNow.AddMinutes(1)}}
 Need ($released.Contains("session_user <> 'postgres'")) 'INSTALL_IDENTITY_GATE_MISSING'
 Need ($released.Contains('GRANT v3_cas_executor TO v3_cas_executor_actor WITH INHERIT FALSE, SET TRUE, ADMIN FALSE')) 'EXECUTOR_BINDING_MISSING'
 $body=[regex]::Match($original,'(?s)as \$v3_atomic_cas\$(.*?)\$v3_atomic_cas\$;').Value
 Need ($body.Length -gt 1000 -and $released.Contains($body)) 'ORIGINAL_ATOMIC_CAS_CHANGED'
 Reject {Get-V3PaperCasInstallSql 'altered' @{authorization=@{expires_at=[datetimeoffset]::UtcNow}}} 'SEAM_DRIFT'
 # Resume/rollback decisions are exercised below with mock native boundaries;
 # these mocks are confined to this test script, absent from CLI parameters.
 function Import-Module {
  param($Name,[switch]$Force,$Scope)
  if([IO.Path]::GetFileName($Name) -cne 'v3-one-time-release-authorization.psm1'){
   Microsoft.PowerShell.Core\Import-Module -Name $Name -Force:$Force
  }
 }
 function Assert-V3PaperOriginalHost {}
 function Get-V3ReleaseSha256([byte[]]$Bytes){
  $hasher=[Security.Cryptography.SHA256]::Create()
  try{return ([BitConverter]::ToString($hasher.ComputeHash($Bytes))).Replace('-','').ToLowerInvariant()}
  finally{$hasher.Dispose()}
 }
 function Get-V3PaperReleaseInventory {return @{'paper_evaluator/v3_paper_minipc_native_launcher_v1.py'=('e'*64)}}
 function Open-V3ReleasePackageReadLease {return @()}
 function Assert-V3ReleaseAuthorityAdmission {return 'd'*64}
 function Read-V3ReleaseLocalBytes {return ,[byte[]](123,125)}
 function Assert-V3OneTimeReleaseAuthorization {
  param($Scope)
  if($Scope -ceq 'V3_PAPER_RUNTIME_REPEATED'){
   if($script:runtime.expires_at -le [datetimeoffset]::UtcNow){throw 'V3_RELEASE_APPROVAL_EXPIRED_OR_FUTURE_HOLD'}
   return $script:runtime
  }
  return $script:authorization
 }
 function Read-V3PaperIndependentReceipt {return $script:receipt}
 function Read-V3PaperPinnedJson($path){
  if($path -ceq 'runtime.json'){return $script:runtimeSpec}
  return $script:plan
 }
 function Assert-V3PaperRuntimeSpec {}
 function Open-V3PaperIntakePair {return $null}
 function Assert-V3PaperTaskPins {}
 function Assert-V3PaperEpochPlan {return @{epoch_id='V3CAS-AUDIT-'+('9'*32);source_sha256=('2'*64);
  caller_acl_sha256=('3'*64);fence_sha256=(Get-V3ReleaseSha256 ([byte[]](123,125)))}}
 function Assert-V3PaperEpochReceipt {}
 function Assert-V3PaperProcesses {}
 function Assert-V3PaperFence {return @{phase='QUIESCED'}}
 function Get-V3PaperStateBase {return (Join-Path $tmp 'run')}
 function Get-V3PaperFencePath {return (Join-Path $tmp 'fence.json')}
 function Get-ScheduledTask {return @{State='Disabled'}}
 function Disable-ScheduledTask {$script:effects+='disable'}
 function Stop-ScheduledTask {$script:effects+='stop'}
 function Invoke-V3ReleasePg {throw 'UNEXPECTED_DATABASE_CALL'}
 $script:authorization=@{expires_at=[datetimeoffset]::UtcNow.AddMinutes(1);approval_sha256=('d'*64);
  claims=@{release_id='test';bindings=@{plan_sha256=('b'*64);runtime_spec_sha256=('c'*64);reader_certificate_sha256=('d'*64)}}}
 $script:plan=@{kind='V3_ONE_TIME_PAPER_RELEASE_PLAN_V1';repo_sha=('a'*40);series_id='PAPER-V3-20261106T120000Z';bundle_sha256=('b'*64);strategy_sha256=('c'*64)}
 $script:receipt=@{state='UNKNOWN'};$script:effects=@()
 $common=@{PackageRoot=$root;ExpectedReleaseCommit=('a'*40)}
 $oldPlan=$script:plan
 $script:plan=[pscustomobject]($script:plan.Clone())
 $script:plan | Add-Member NoteProperty supersession ([pscustomobject]@{
  prior_epoch_id='V3CAS-AUDIT-'+('8'*32);prior_commit=('a'*40);prior_terminal_sha256=('1'*64);
  installed_cas_sha256=('2'*64);installed_issuer_sha256=('3'*64);installed_reader_sha256=('4'*64)})
 $script:plan.series_id='PAPER-V3-'+[datetimeoffset]::UtcNow.AddMinutes(-11).ToString("yyyyMMdd'T'HHmmss'Z'")
 $openPw=ConvertTo-SecureString 'OFFLINE-NOT-A-CREDENTIAL' -AsPlainText -Force
 Reject {Invoke-V3OneTimePaperRelease -Mode PaperOpenEpoch -PostgresPassword $openPw @common} 'SUCCESSOR_SERIES_OUTSIDE_CAS_WINDOW'
 Need (@(Get-ChildItem -LiteralPath $tmp -Filter 'run*.epoch.attempted.json').Count -eq 0) 'EXPIRED_EPOCH_CREATED_DISPATCH_LATCH'
 $script:plan.series_id='PAPER-V3-'+[datetimeoffset]::UtcNow.ToString("yyyyMMdd'T'HHmmss'Z'")
 Need ((Get-V3PaperSupersessionSettings $script:plan).prior_epoch_id -ceq $script:plan.supersession.prior_epoch_id) 'FRESH_SIGNED_EPOCH_NOT_PREPARABLE'
 $openPw.Dispose()
 $script:plan=$oldPlan
 $res=Invoke-V3OneTimePaperRelease -Mode PaperResume @common
 Need ($res.automatic_retry -eq $false -and -not $res.cas_attempted) 'RESUME_REDISPATCHED'
 Reject {Invoke-V3OneTimePaperRelease -Mode PaperActivate @common} 'COMMITTED_INDEPENDENT_READER_REQUIRED'
 Reject {Invoke-V3OneTimePaperRelease -Mode PaperRollback @common} 'TERMINAL_ABORT_REQUIRED'
 Write-V3PaperReceipt (Join-Path $tmp 'run.cas.attempted.json') @{state='DISPATCH_UNKNOWN'}
 $res=Invoke-V3OneTimePaperRelease -Mode PaperResume @common
 Need ($res.cas_attempted -eq $true -and $script:effects.Count -eq 0) 'UNKNOWN_RESUME_MUTATED'
 $res=Invoke-V3OneTimePaperRelease -Mode PaperRollback @common
 Need ($res.old_intake_rearmed -eq $false -and ($script:effects -join ',') -ceq 'disable,stop') 'POST_CAS_REARMED_OLD_WRITER'
 # Successful STOP and CAS plumbing; faults preserve their create-new latches.
 Remove-Item (Join-Path $tmp 'run.cas.attempted.json')
 $script:receipt=@{state='PRESTOP_INHIBITED_OLD_ONLY_NO_ATTEMPTS'}
 function Assert-V3PaperFence {return @{phase='ARMED'}}
 function Set-V3PaperFence {$script:effects+='fence'}
 $script:effects=@()
 [IO.File]::WriteAllBytes((Join-Path $tmp 'fence.json'),[byte[]](123,125))
 $script:plan.series_id='PAPER-V3-'+[datetimeoffset]::UtcNow.AddMinutes(-11).ToString("yyyyMMdd'T'HHmmss'Z'")
 Reject {Invoke-V3OneTimePaperRelease -Mode PaperStop @common} 'SUCCESSOR_SERIES_OUTSIDE_CAS_WINDOW'
 Need ($script:effects.Count -eq 0 -and -not [IO.File]::Exists((Join-Path $tmp 'run.stop.attempted.json'))) 'EXPIRED_SERIES_STOP_MUTATED_TASKS'
 $script:plan.series_id='PAPER-V3-'+[datetimeoffset]::UtcNow.ToString("yyyyMMdd'T'HHmmss'Z'")
 $res=Invoke-V3OneTimePaperRelease -Mode PaperStop @common
 Need ($res.kind -ceq 'V3_PAPER_STOP_QUIESCED_LOCAL_ACK') 'STOP_POSITIVE_MISSING'
 Need (($script:effects -join ',') -ceq 'disable,disable,stop,stop,fence') 'STOP_SCOPE_OR_ORDER'
 Reject {Invoke-V3OneTimePaperRelease -Mode PaperStop @common} 'already exists'
 function Assert-V3PaperFence {return @{phase='QUIESCED'}}
 $request.Remove('extra');$request.expected_old_series_id='PAPER-V2R4-20261009T110135Z'
 $request.proposed_v3_series_id=$script:plan.series_id
 $request.reviewed_new_repo_sha=$script:plan.repo_sha
 $request.reviewed_new_bundle_sha256=$script:plan.bundle_sha256
 $request.reviewed_new_strategy_sha256=$script:plan.strategy_sha256
 $request.new_v3_config=[pscustomobject]@{preinvoke_epoch_id=('V3CAS-AUDIT-'+('a'*32));preinvoke_intent_id='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';
  preinvoke_request_sha256=('a'*64);preinvoke_source_sha256=('b'*64);preinvoke_fence_sha256=('c'*64);preinvoke_inhibit_receipt_sha256=('d'*64)}
 $script:plan.cas_request=[pscustomobject]$request
 $script:receipt=@{state='SEALED_INTENT_INHIBIT_STOP_CONFIRMED'}
 foreach($key in $request.new_v3_config.PSObject.Properties.Name){$script:receipt[$key]=$request.new_v3_config.$key}
 $script:sqlCalls=@()
 function Invoke-V3ReleasePg {
  param($Sql,$Password,$Ca,$Actor)
  $script:sqlCalls+=@{sql=$Sql;actor=$Actor}
  if($script:sqlCalls.Count -eq 1){return '2026-11-06T12:00:00Z'}
  return ('{"ok":true,"kind":"V3_EXPERIMENTAL_PAPER_ATOMIC_CAS_V1","successor_series_id":"'+$script:plan.series_id+'"}')
 }
 $pw=ConvertTo-SecureString 'OFFLINE-NOT-A-CREDENTIAL' -AsPlainText -Force
 $res=Invoke-V3OneTimePaperRelease -Mode PaperCas -PostgresPassword $pw @common
 Need ($script:sqlCalls.Count -eq 2 -and $script:sqlCalls[0].sql.Contains('append_dispatch_unknown_v1') -and
  $script:sqlCalls[1].sql.Contains('rotate_v2r4_to_v3_experimental_paper') -and
  $script:sqlCalls[1].sql.Contains('statement_timeout')) 'CAS_COMMIT_ORDER_OR_DEADLINE'
 Reject {Invoke-V3OneTimePaperRelease -Mode PaperCas -PostgresPassword $pw @common} 'already exists'
 Need ($script:sqlCalls.Count -eq 2) 'CAS_REPLAY_DISPATCHED'
 $script:receipt=@{kind='V3_PAPER_RELEASE_EPOCH_READER_V1';state='CAS_COMMITTED_EXACT_SUCCESSOR_SINGLE_ACTIVE';successor_series_id=$script:plan.series_id;
  repo_sha=$script:plan.repo_sha;bundle_sha256=$script:plan.bundle_sha256;strategy_sha256=$script:plan.strategy_sha256}
 foreach($key in $request.new_v3_config.PSObject.Properties.Name){$script:receipt[$key]=$request.new_v3_config.$key}
 $nativeLauncher=Join-Path $root 'paper_evaluator\v3_paper_minipc_native_launcher_v1.py'
 $script:nativeArguments=(Get-V3PaperNativeActionPrefix $root)+' --runtime-spec "pinned.json"'
 Need ($script:nativeArguments.StartsWith('-I -B ',[StringComparison]::Ordinal)) 'PREPARED_NATIVE_PREFIX_DRIFT'
 function Get-ScheduledTask {
  param($TaskName)
  if(-not $TaskName){return $script:otherWriters}
  return @{State='Disabled';Actions=@($script:nativeAction)}
 }
 function Enable-ScheduledTask {$script:effects+='enable'}
 function Start-ScheduledTask {$script:effects+='start'}
 $script:effects=@()
 $script:otherWriters=@()
 $common.RuntimeSpecJson='runtime.json'
 $script:runtimeSpec=@{kind='V3_NATIVE_REPEATED_PAPER_RUNTIME_SPEC_V1';paper_plan='plan.json';release_packet='proof.json'}
 $script:plan.runtime_bootstrap=@{approval_json='runtime-approval.json';approval_cms='runtime-approval.cms';
  admission_json='admission.json';host_receipt='cas-reader.json';host_cms='cas-reader.cms'}
 $common.ExpectedAuthorityAdmissionSha256=Get-V3ReleaseSha256 ([byte[]](123,125))
 $script:nativeAction=@{Execute='python.exe';WorkingDirectory=$root;Arguments=$script:nativeArguments}
 $runtimeBindings=$script:authorization.claims.bindings.Clone()
 $runtimeBindings.host_receipt_sha256=$common.ExpectedAuthorityAdmissionSha256
 $runtimeBindings.start_authority=@{native_task_action_sha256=(Get-V3PaperTaskActionSha256 $script:nativeAction);
  native_task_launcher_file_sha256=('e'*64)}
 $script:runtime=@{claims=@{release_id='test';bindings=$runtimeBindings};approval_sha256=('9'*64);
  not_before=[datetimeoffset]::UtcNow.AddMinutes(-1);expires_at=[datetimeoffset]::UtcNow.AddMinutes(5)}
 function Get-V3PaperNativeActionArguments {return $reviewedArguments}
 $reviewedArguments=$script:nativeArguments
 foreach($drift in @((' '+$reviewedArguments),
                    ($reviewedArguments -replace '--released-one-shot','--released-one-shot-extra'),
                    ($reviewedArguments.Replace($nativeLauncher,(Join-Path $root 'other.py'))))){
  $script:nativeAction.Arguments=$drift
  Reject {Invoke-V3OneTimePaperRelease -Mode PaperActivate @common} 'REVIEWED_DISABLED_NATIVE_ACTION_REQUIRED'
 }
 Need ($script:effects.Count -eq 0) 'DRIFTED_ACTIVATION_MUTATED_TASKS'
 $script:nativeAction.Arguments=$reviewedArguments
 $script:receipt.preinvoke_request_sha256='f'*64
 Reject {Invoke-V3OneTimePaperRelease -Mode PaperActivate @common} 'ACTIVATION_REQUEST_DRIFT'
 Need ($script:effects.Count -eq 0) 'DRIFTED_CAS_RECEIPT_MUTATED_TASKS'
 $script:receipt.preinvoke_request_sha256=$request.new_v3_config.preinvoke_request_sha256
 $expires=$script:runtime.expires_at
 $script:runtime.expires_at=[datetimeoffset]::UtcNow.AddSeconds(-1)
 Reject {Invoke-V3OneTimePaperRelease -Mode PaperActivate @common} 'APPROVAL_EXPIRED'
 $script:runtime.expires_at=$expires
 function Get-V3PaperRepeatedStart {}
 $script:runtime.claims.bindings.host_receipt_sha256='0'*64
 Reject {Invoke-V3OneTimePaperRelease -Mode PaperActivate @common} 'START_BYTES_HOLD'
 $script:runtime.claims.bindings.host_receipt_sha256=$common.ExpectedAuthorityAdmissionSha256
 $script:otherWriters=@(@{TaskName='CryptoMiniPC-V3PaperOtherWriter';TaskPath='\';State='Ready'})
 Reject {Invoke-V3OneTimePaperRelease -Mode PaperActivate @common} 'COMPETING_NATIVE_WRITER_HOLD'
 $script:otherWriters=@()
 Need ($script:effects.Count -eq 0) 'INVALID_RUNTIME_MUTATED_TASKS'
 function Get-ScheduledTask {
  param($TaskName)
  if(-not $TaskName){return $script:otherWriters}
  return @{State='Running';Actions=@($script:nativeAction)}
 }
 function Assert-V3PaperFence {return @{phase='QUIESCED'}}
 $healthContext=@{authorization=$script:authorization;plan=$script:plan}
 Need ($null -eq (Get-V3PaperRepeatedHealth $healthContext $script:runtime $script:nativeAction ([datetimeoffset]::UtcNow))) 'MISSING_HEARTBEAT_ACCEPTED'
 function Get-ScheduledTask {
  param($TaskName)
  if(-not $TaskName){return $script:otherWriters}
  return @{State='Disabled';Actions=@($script:nativeAction)}
 }
 function Get-V3PaperRepeatedHealth {return @{kind='V3_PAPER_ORIGINALHOST_RUNTIME_READBACK_V1';paper_operational_claimed=$false}}
 $res=Invoke-V3OneTimePaperRelease -Mode PaperActivate @common
 Need (($script:effects -join ',') -ceq 'fence,enable,start') 'ACTIVATION_ORDER'
 Need ($res.paper_operational_claimed -eq $false) 'FALSE_RUNTIME_ACK'
 Reject {Invoke-V3OneTimePaperRelease -Mode PaperActivate @common} 'already exists'
 Need ($script:effects.Count -eq 3) 'DUPLICATE_ACTIVATION'
 $pw.Dispose()
 # Separate disposable recovery fixture for expiry after Prepare but before STOP.
 Remove-Item (Join-Path $tmp 'run.stop.attempted.json'),(Join-Path $tmp 'run.cas.attempted.json')
 function Assert-V3PaperFence {return @{phase='ARMED'}}
 function Get-ScheduledTask {
  param($TaskName)
  if($TaskName -ceq 'CryptoMiniPC-V3PaperSingleWriter'){return @{State='Disabled'}}
  return @{State='Running'}
 }
 $script:effects=@()
 $script:receipt=@{state='UNKNOWN'}
 Reject {Invoke-V3OneTimePaperRelease -Mode PaperRollback @common} 'TERMINAL_ABORT_REQUIRED'
 Need ([IO.File]::Exists((Join-Path $tmp 'fence.json'))) 'PRESTOP_FENCE_ARCHIVED_WITHOUT_TERMINAL_RECEIPT'
 $script:receipt.state='PRECAS_ABORT_SEALED_OLD_ONLY_ZERO_ATTEMPTS'
 $res=Invoke-V3OneTimePaperRelease -Mode PaperRollback @common
 Need ($res.kind -ceq 'V3_PAPER_PRESTOP_EXPIRED_FENCE_ARCHIVED' -and $script:effects.Count -eq 0 -and
  [IO.File]::Exists((Join-Path $tmp 'fence.json.test.rollback'))) 'PRESTOP_ARCHIVE_REARMED_OR_LOST_FENCE'
 # Fault after the first task restart must preserve the original fence and
 # create-new attempt latch. Never reopen automatically after a partial restore.
 Remove-Item (Join-Path $tmp 'run.rollback.attempted.json'),(Join-Path $tmp 'fence.json.test.rollback')
 [IO.File]::WriteAllBytes((Join-Path $tmp 'fence.json'),[byte[]](123,125))
 Write-V3PaperReceipt (Join-Path $tmp 'run.stop.attempted.json') @{state='TEST'}
 function Assert-V3PaperFence {return @{phase='QUIESCED'}}
 function Get-ScheduledTask {return @{State='Disabled'}}
 function Start-ScheduledTask {throw 'SIMULATED_RESTORE_START_FAILURE'}
 Reject {Invoke-V3OneTimePaperRelease -Mode PaperRollback @common} 'SIMULATED_RESTORE_START_FAILURE'
 Need ([IO.File]::Exists((Join-Path $tmp 'fence.json'))) 'FAILED_RESTORE_REMOVED_FENCE'
 Need ([IO.File]::Exists((Join-Path $tmp 'run.rollback.attempted.json'))) 'FAILED_RESTORE_ATTEMPT_LOST'
 Reject {Invoke-V3OneTimePaperRelease -Mode PaperRollback @common} 'already exists'
 Remove-Item (Join-Path $tmp 'run.rollback.attempted.json')
 function Start-ScheduledTask {$script:effects+='restore-start'}
 function Wait-V3PaperOriginalIntakeRestore {
  Need ([IO.File]::Exists((Join-Path $tmp 'fence.json'))) 'FENCE_REMOVED_BEFORE_WORKER_ACK'
  throw 'SIMULATED_MISSING_RESTORE_HEARTBEAT'
 }
 Reject {Invoke-V3OneTimePaperRelease -Mode PaperRollback @common} 'SIMULATED_MISSING_RESTORE_HEARTBEAT'
 Need ([IO.File]::Exists((Join-Path $tmp 'fence.json'))) 'STALE_HEARTBEAT_REMOVED_FENCE'
 Remove-Item (Join-Path $tmp 'run.rollback.attempted.json')
 function Wait-V3PaperOriginalIntakeRestore {
  Need ([IO.File]::Exists((Join-Path $tmp 'fence.json'))) 'FENCE_REMOVED_BEFORE_WORKER_ACK'
  $script:effects+='two-original-heartbeats'
 }
 $res=Invoke-V3OneTimePaperRelease -Mode PaperRollback @common
 Need ($res.kind -ceq 'V3_PAPER_PRECAS_RESTORE_REQUESTED_AFTERCARE_ACK_PENDING' -and
  [IO.File]::Exists((Join-Path $tmp 'fence.json.test.rollback'))) 'CONFIRMED_WORKERS_NOT_ARCHIVED'
 Write-Output 'V3_PAPER_RELEASE_OFFLINE_CMS_SQL_LATCH_RESUME_ROLLBACK_PASS'
}finally{Remove-Item $tmp -Recurse -Force;$cert.Dispose();$rsa.Dispose()}
