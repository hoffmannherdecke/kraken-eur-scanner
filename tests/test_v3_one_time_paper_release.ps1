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
 $inventory.host_mutated -eq $false -and @($inventory.artifacts.PSObject.Properties).Count -eq 11) 'PRODUCTIVE_INVENTORY_NOT_INERT_OR_INCOMPLETE'
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
  $bytes=[Text.Encoding]::UTF8.GetBytes(($row|ConvertTo-Json -Compress))
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
 function Assert-V3PaperOriginalHost {}
 function Get-V3PaperReleaseInventory {return @{}}
 function Open-V3ReleasePackageReadLease {return @()}
 function Assert-V3ReleaseAuthorityAdmission {return 'd'*64}
 function Read-V3ReleaseLocalBytes {return ,[byte[]](123,125)}
 function Assert-V3OneTimeReleaseAuthorization {return $script:authorization}
 function Read-V3PaperIndependentReceipt {return $script:receipt}
 function Read-V3PaperPinnedJson {return $script:plan}
 function Assert-V3PaperRuntimeSpec {}
 function Open-V3PaperIntakePair {return $null}
 function Assert-V3PaperTaskPins {}
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
 $script:receipt=@{state='CAS_COMMITTED_EXACT_SUCCESSOR_SINGLE_ACTIVE';successor_series_id=$script:plan.series_id;
  repo_sha=$script:plan.repo_sha;bundle_sha256=$script:plan.bundle_sha256;strategy_sha256=$script:plan.strategy_sha256}
 function Get-ScheduledTask {
  param($TaskName)
  return @{State='Disabled';Actions=@(@{Arguments=' -I -B "pinned.py" --released-one-shot'})}
 }
 function Enable-ScheduledTask {$script:effects+='enable'}
 function Start-ScheduledTask {$script:effects+='start'}
 $script:effects=@()
 $res=Invoke-V3OneTimePaperRelease -Mode PaperActivate @common
 Need (($script:effects -join ',') -ceq 'fence,enable,start') 'ACTIVATION_ORDER'
 Need ($res.paper_operational_claimed -eq $false) 'FALSE_RUNTIME_ACK'
 Reject {Invoke-V3OneTimePaperRelease -Mode PaperActivate @common} 'already exists'
 Need ($script:effects.Count -eq 3) 'DUPLICATE_ACTIVATION'
 $pw.Dispose()
 Write-Output 'V3_PAPER_RELEASE_OFFLINE_CMS_SQL_LATCH_RESUME_ROLLBACK_PASS'
}finally{Remove-Item $tmp -Recurse -Force;$cert.Dispose();$rsa.Dispose()}
