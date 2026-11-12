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
 'ApprovedPinsSha256','Start-Sleep -Milliseconds 200','PR710_WINDOW_SOURCE_BYTE_PIN_HOLD',
 'PR710_WINDOW_STALE_ORIGINAL_HOLD','NO_PRODUCTION_EFFECT')){
 if(-not $coordinatorSource.Contains($required)){throw "PR710_COORDINATOR_CONTRACT_MISSING: $required"}
}
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
