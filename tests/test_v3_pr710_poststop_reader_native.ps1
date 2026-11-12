# PR710: native Windows PowerShell 5.1 offline read-only Reader tests.
$ErrorActionPreference='Stop'
$source=Join-Path $PSScriptRoot '../tools/v3-poststop-notebook-reader-extension-INACTIVE.ps1'
$tokens=$null;$errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile($source,[ref]$tokens,[ref]$errors)
if(@($errors).Count -ne 0){throw ('PR710_NOTEBOOK_SYNTAX_HOLD: '+($errors|Select-Object -First 1).Message)}
$coordinator=Join-Path $PSScriptRoot '../tools/v3-poststop-triple-reader-window-INACTIVE.ps1'
$otherTokens=$null;$otherErrors=$null
$null=[System.Management.Automation.Language.Parser]::ParseFile($coordinator,[ref]$otherTokens,[ref]$otherErrors)
if(@($otherErrors).Count -ne 0){throw ('PR710_COORDINATOR_PARSE_HOLD: '+($otherErrors|Select-Object -First 1).Message)}
$coordinatorSource=[IO.File]::ReadAllText($coordinator)
foreach($required in @('Assert-V3PostStopOwnerAdmittedCurrentHostTripleCms',
 'ApprovedPinsSha256','Start-Sleep -Milliseconds 200','PR710_POLICY_FIELDS_OR_UNTRUSTED_LIVE_SHA_HOLD',
 'PR710_WINDOW_STALE_ORIGINAL_HOLD','NO_PRODUCTION_EFFECT')){
 if(-not $coordinatorSource.Contains($required)){throw "PR710_COORDINATOR_CONTRACT_MISSING: $required"}
}
$pinsAst=@($otherTokens)
$helper=@([Management.Automation.Language.Parser]::ParseFile($coordinator,[ref]$otherTokens,[ref]$otherErrors).FindAll({
 param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
 $node.Name -eq 'Get-V3PostStopVerifiedLivePins'
},$true))
if($helper.Count -ne 1){throw 'PR710_CMS_FIRST_PIN_HELPER_MISSING_HOLD'}
. ([scriptblock]::Create($helper[0].Extent.Text))
$policy=[pscustomobject]@{
 series_id='PAPER-V3-20261111T105211Z';epoch_id='V3CAS-AUDIT-f27cce0ba68043b480e4f97698dd2901'
 source_sha256=('a'*64);epoch_fence_sha256=('b'*64);caller_acl_sha256=('c'*64)
 local_fence_file_sha256=('d'*64);candidates_xml_sha256=('e'*64)
 wait_xml_sha256=('f'*64);cloudsync_xml_sha256=('1'*64);writer_xml_sha256=('2'*64)
 host_certificate_sha256=('3'*64);cloud_certificate_sha256=('4'*64)
 owner_review_sha256=('5'*64);observation_nonce='0123456789abcdef0123456789abcdef'
}
$fake=[byte[]](1..450 | ForEach-Object {$_ % 251})
$held=$false
try{
 $null=Get-V3PostStopVerifiedLivePins -Approved $policy -HostPayload $fake -CloudPayload $fake -OriginalHostCms $fake -NotebookHostCms $fake -CloudCms $fake
}catch{$held=$true}
if(-not $held){throw 'PR710_UNVERIFIED_LIVE_CMS_ACCEPTED'}
$policy | Add-Member -NotePropertyName host_payload_sha256 -NotePropertyValue ('6'*64)
$held=$false
try{
 $null=Get-V3PostStopVerifiedLivePins -Approved $policy -HostPayload $fake -CloudPayload $fake -OriginalHostCms $fake -NotebookHostCms $fake -CloudCms $fake
}catch{$held=$true}
if(-not $held){throw 'PR710_SELF_APPROVED_EPHEMERAL_SHA_ACCEPTED'}

$raw=[IO.File]::ReadAllText($source)
foreach($required in @(
 'PostStopHostReader','PostStopCloudReader','ObservationNonce',
 'V3_POSTSTOP_CURRENT_INDEPENDENT_HOST_READER_V1',
 'V3_POSTSTOP_CURRENT_INDEPENDENT_CLOUD_READER_V1',
 'read_forward_t0_current_v1','read_committed_pre_stop_inhibit_v1',
 'BEGIN TRANSACTION READ ONLY','verify-full',
 'CheckSignature($true)','ce256281af6d36eb883dd2cb34594d0f2231e32a33f58e668d327814c7cfdb40',
 '2e3322131208737c58a82c04764bddf4ebe29481c96c79697183710358a2fc57',
 '61d08dd9a925730f213fedc559664dbfe2a3e4f8f1ae77496b385f7d92f3bc55',
 'V3_POSTSTOP_HOST_BYTE_HOLD','V3_POSTSTOP_READER_FRESHNESS_HOLD'
)){if(-not $raw.Contains($required)){throw "PR710_READER_CONTRACT_MISSING: $required"}}
if($raw.Contains('ForwardT0SignedCurrent -and $PostStopCloudReader')){
 throw 'PR710_WRONG_RECEIPT_MODE_REUSED'
}
$fn=@($ast.FindAll({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
 $node.Name -eq 'Assert-V3PostStopFreshReader'},$true))
if($fn.Count -ne 1){throw 'PR710_READER_FRESH_FUNCTION_COUNT_HOLD'}
. ([scriptblock]::Create($fn[0].Extent.Text))
$valid=[ordered]@{
 kind='V3_POSTSTOP_CURRENT_INDEPENDENT_HOST_READER_V1'
 observation_nonce='0123456789abcdef0123456789abcdef'
 observed_at_utc=([datetime]::UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'",[Globalization.CultureInfo]::InvariantCulture))
}
$json=$valid|ConvertTo-Json -Compress
$null=Assert-V3PostStopFreshReader $json $valid.observation_nonce $valid.kind
function Expect-Hold([string]$Value,[string]$Nonce,[string]$Kind){
 $caught=$false
 try{$null=Assert-V3PostStopFreshReader $Value $Nonce $Kind}catch{$caught=$true}
 if(-not $caught){throw 'PR710_READER_FAIL_CLOSED_NEGATIVE_MISSING'}
}
Expect-Hold $json 'ffffffffffffffffffffffffffffffff' $valid.kind
Expect-Hold $json $valid.observation_nonce 'V3_CAS_FORWARD_T0_CURRENT_CATALOG_READONLY_V1'
$valid.observed_at_utc=([datetime]::UtcNow.AddSeconds(-75).ToString("yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'",[Globalization.CultureInfo]::InvariantCulture))
Expect-Hold ($valid|ConvertTo-Json -Compress) $valid.observation_nonce $valid.kind
$valid.observed_at_utc=([datetime]::UtcNow.AddSeconds(20).ToString("yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'",[Globalization.CultureInfo]::InvariantCulture))
Expect-Hold ($valid|ConvertTo-Json -Compress) $valid.observation_nonce $valid.kind
Write-Output 'PR710_POSTSTOP_NATIVE_PS51_READER_PARSE_AND_FRESHNESS_NEGATIVES_PASS'
