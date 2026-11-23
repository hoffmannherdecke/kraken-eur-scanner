[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('Prepare','Stop','Seal','CasApproval','CasReader','PostCasReader','Runtime','Activate','AbortReader','Rollback','Resume')]
    [string]$Phase,
    [Parameter(Mandatory=$true)][string]$WindowDirectory,
    [Parameter(Mandatory=$true)][string]$FixedSha256,
    [string]$CaFile,
    [string]$PostCasTransfer,
    [switch]$PreCasRollback,
    [DateTimeOffset]$ResumeStartedAtUtc
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($env:COMPUTERNAME -ieq 'MINI-PC' -or -not [Environment]::UserInteractive) {
    throw 'ORIGINAL_NOTEBOOK_REQUIRED'
}
Add-Type -AssemblyName System.Security
$utf8 = [Text.UTF8Encoding]::new($false,$true)
$authorityPin = '2e3322131208737c58a82c04764bddf4ebe29481c96c79697183710358a2fc57'
$readerPin = '61d08dd9a925730f213fedc559664dbfe2a3e4f8f1ae77496b385f7d92f3bc55'
$unc = '\\192.168.178.179\Mistral_450\V3-PR682-Authority-Handoff'

function Digest([byte[]]$Bytes) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try { [BitConverter]::ToString($sha.ComputeHash($Bytes)).Replace('-','').ToLowerInvariant() }
    finally { $sha.Dispose() }
}
function Write-Once([string]$Path,[byte[]]$Bytes) {
    $pending = $Path + '.pending-' + [guid]::NewGuid().ToString('N')
    try {
        [IO.File]::WriteAllBytes($pending,$Bytes)
        if ((Digest ([IO.File]::ReadAllBytes($pending))) -cne (Digest $Bytes)) { throw 'TRANSFER_HASH_HOLD' }
        [IO.File]::Move($pending,$Path)
    } finally { if ([IO.File]::Exists($pending)) { [IO.File]::Delete($pending) } }
}
function Read-Object([string]$Path) {
    $bytes = [IO.File]::ReadAllBytes($Path)
    if ($bytes.Length -lt 2 -or $bytes.Length -gt 65536) { throw 'JSON_SIZE_HOLD' }
    $utf8.GetString($bytes) | ConvertFrom-Json -ErrorAction Stop
}
function Assert-Cms([byte[]]$Payload,[byte[]]$Signature,[string]$Pin) {
    $cms = [Security.Cryptography.Pkcs.SignedCms]::new([Security.Cryptography.Pkcs.ContentInfo]::new($Payload),$true)
    $cms.Decode($Signature)
    if (-not $cms.Detached -or $cms.SignerInfos.Count -ne 1 -or
        $cms.SignerInfos[0].DigestAlgorithm.Value -cne '2.16.840.1.101.3.4.2.1' -or
        (Digest $cms.SignerInfos[0].Certificate.RawData) -cne $Pin) { throw 'CMS_PIN_HOLD' }
    $cms.CheckSignature($true)
}
$fixedFile = Join-Path $WindowDirectory 'cutover-fixed-inputs.json'
if ($FixedSha256 -cnotmatch '^[a-f0-9]{64}$' -or
    (Digest ([IO.File]::ReadAllBytes($fixedFile))) -cne $FixedSha256) { throw 'FIXED_INPUT_HASH_HOLD' }
$fixed = Read-Object $fixedFile
if ($fixed.repo_sha -cnotmatch '^[a-f0-9]{40}$' -or -not $fixed.authority_admission_sha256) { throw 'RELEASE_NOT_BOUND' }
$planLeaf = if ($Phase -eq 'Prepare') { 'plan.stage4.json' } elseif ($Phase -eq 'Stop') { 'plan.stop.json' } else { 'plan.cas.json' }
$planFile = Join-Path $WindowDirectory $planLeaf
$plan = Read-Object $planFile
$planHash = Digest ([IO.File]::ReadAllBytes($planFile))
if ($plan.kind -cne 'V3_ONE_TIME_PAPER_RELEASE_PLAN_V1' -or $plan.repo_sha -cne $fixed.repo_sha -or
    $plan.bundle_sha256 -cne $fixed.bundle_sha256 -or $plan.strategy_sha256 -cne $fixed.strategy_sha256 -or
    $plan.series_id -cnotmatch '^PAPER-V3-[0-9]{8}T[0-9]{6}Z$' -or
    $plan.cas_epoch.epoch_id -cnotmatch '^V3CAS-AUDIT-[a-f0-9]{32}$' -or
    $plan.cas_epoch.source_sha256 -cne '989e1657e03867774907f3a1ec9c9f4f84ee70c2d4b7a258cad9dc3e480f0043' -or
    $plan.cas_epoch.caller_acl_sha256 -cne $fixed.caller_acl_sha256) { throw 'PLAN_IDENTITY_HOLD' }
$stamp = $plan.series_id.Substring(9)
$id = 'V3-ONETIME-' + $plan.cas_epoch.epoch_id.Substring(12)
$handoff = Join-Path $unc ('PR700-Window-'+$stamp)
if (-not (Test-Path -LiteralPath $handoff -PathType Container)) { throw 'MISTRAL_HANDOFF_REQUIRED' }
$end = [DateTimeOffset]::ParseExact($stamp,"yyyyMMdd'T'HHmmss'Z'",[Globalization.CultureInfo]::InvariantCulture,[Globalization.DateTimeStyles]::AssumeUniversal).AddMinutes(10)
if ($PSBoundParameters.ContainsKey('ResumeStartedAtUtc')) {
    $phaseNow = [DateTimeOffset]::UtcNow
    if ($PreCasRollback -or $Phase -in @('AbortReader','Rollback','Resume') -or
        $plan.series_id -cne 'PAPER-V3-20261123T122357Z' -or
     $plan.cas_epoch.epoch_id -cne 'V3CAS-AUDIT-a7cf89799379456bbd9ab513f13689e4' -or
     $plan.repo_sha -cne '46c5abbd6af16266c1229943db973dc9d6b2fb4f' -or
     $plan.cas_epoch.source_sha256 -cne '989e1657e03867774907f3a1ec9c9f4f84ee70c2d4b7a258cad9dc3e480f0043' -or
     $plan.cas_epoch.fence_sha256 -cne 'a0be95f3a25327fa86c87b46bf7726d80a86cb3cb80b913a6f317e8c42873ba5' -or
     $plan.cas_epoch.caller_acl_sha256 -cne '6f0d59c57f3f7ce3d54f5c674c0d41c342a2a08b9a86001e59353d772f5f66f0' -or
        ($Phase -eq 'Prepare' -and $planHash -cne '3af0dc8ddb4de5f067a6ffff3238480d13783c39701cfab30f13df9c0e145166') -or
        $ResumeStartedAtUtc -lt $end -or $ResumeStartedAtUtc -gt $phaseNow) {
        throw 'AP05A_RESUME_PHASE_BINDING_HOLD'
    }
    if ($Phase -in @('Prepare','Stop','Seal','CasApproval','CasReader')) {
        $end = $ResumeStartedAtUtc.AddMinutes(10)
        if ($phaseNow.AddSeconds(20) -ge $end) { throw 'AP05A_RESUME_PHASE_EXPIRED_HOLD' }
    }
}
$rules = @{
    Prepare=@('V3_PAPER_PREPARE','PRESTOP_INHIBITED_OLD_ONLY_NO_ATTEMPTS')
    Stop=@('V3_PAPER_STOP','PRESTOP_INHIBITED_OLD_ONLY_NO_ATTEMPTS')
    Seal=@('CLOUD_STAGE5_EPOCH_SEAL','STOP_CONFIRMED_INTENT_COMMITTED')
    CasApproval=@('V3_PAPER_CAS','SEALED_INTENT_EXECUTOR_INHIBITED')
    CasReader=@('','SEALED_INTENT_INHIBIT_STOP_CONFIRMED')
    PostCasReader=@('','CAS_COMMITTED_EXACT_SUCCESSOR_SINGLE_ACTIVE')
    Runtime=@('V3_PAPER_RUNTIME_REPEATED','CAS_COMMITTED_EXACT_SUCCESSOR_SINGLE_ACTIVE')
    Activate=@('V3_PAPER_ACTIVATE','CAS_COMMITTED_EXACT_SUCCESSOR_SINGLE_ACTIVE')
    AbortReader=@('','PRECAS_ABORT_SEALED_OLD_ONLY_ZERO_ATTEMPTS')
    Rollback=@('V3_PAPER_ROLLBACK','CAS_COMMITTED_EXACT_SUCCESSOR_SINGLE_ACTIVE')
    Resume=@('V3_PAPER_RESUME','CAS_COMMITTED_EXACT_SUCCESSOR_SINGLE_ACTIVE')
}
$rule = $rules[$Phase]
if ($PreCasRollback) {
    if ($Phase -notin @('Rollback','Resume')) { throw 'ROLLBACK_STATE_SCOPE_HOLD' }
    $rule[1] = 'PRECAS_ABORT_SEALED_OLD_ONLY_ZERO_ATTEMPTS'
}
$reader = Join-Path $PSScriptRoot 'v3-notebook-cas-audit-original-readonly-witness-INACTIVE.ps1'
if ((Digest ([IO.File]::ReadAllBytes($reader))) -cne '76ce704d5a44e757de85bdcb890bcf2f2e90f7824a60e1af6e5e4f10c377dae7') {
    throw 'READER_SOURCE_HASH_HOLD'
}
if ($rule[0]) {
    Write-Host "$Phase / $($rule[0]) / $($plan.series_id) / $planHash"
    $confirmation = "SIGN-$($rule[0])"
    if ((Read-Host "Nur diesen Scope nach eigener Pruefung mit $confirmation bestaetigen") -cne $confirmation) {
        throw 'SCOPE_NOT_APPROVED'
    }
}
if ($Phase -in @('Runtime','Activate')) {
    $previous = Read-Object $PostCasTransfer
    if ($previous.phase -cne 'PostCasReader' -or $previous.release_id -cne $id -or
        $previous.plan_sha256 -cne $planHash) { throw 'EXACT_POSTCAS_TRANSFER_REQUIRED' }
    $readBytes = [Convert]::FromBase64String($previous.reader)
    $readCms = [Convert]::FromBase64String($previous.reader_cms)
} else {
    $readerArgs = @('-NoProfile','-ExecutionPolicy','RemoteSigned','-File',$reader,
        '-PaperReleaseSignedCurrent','-PaperPlanJson',$planFile,'-PaperReleaseId',$id,
        '-ReviewedNotebookCertificateSha256',$readerPin)
    if ($CaFile) { $readerArgs += @('-CaFile',$CaFile) }
    $result = & "$PSHOME\powershell.exe" @readerArgs
    if ($LASTEXITCODE -ne 0) { throw 'INDEPENDENT_READER_HOLD' }
    $readback = ($result -join "`n") | ConvertFrom-Json -ErrorAction Stop
    if ($readback.kind -cne 'V3_NOTEBOOK_SIGNED_PRECOMMIT_READER_TRANSFER_V1' -or
        $readback.certificate_sha256 -cne $readerPin) { throw 'READER_TRANSFER_HOLD' }
    $readBytes = [IO.File]::ReadAllBytes((Join-Path $readback.local_directory 'reader.json'))
    $readCms = [IO.File]::ReadAllBytes((Join-Path $readback.local_directory 'reader.cms'))
}
Assert-Cms $readBytes $readCms $readerPin
$readRow = $utf8.GetString($readBytes) | ConvertFrom-Json -ErrorAction Stop
if ($readRow.state -cne $rule[1] -or $readRow.release_id -cne $id -or
    $readRow.plan_sha256 -cne $planHash -or $readRow.release_commit -cne $fixed.repo_sha) { throw 'READER_PHASE_HOLD' }
$readerAge = ([DateTimeOffset]::UtcNow - [DateTimeOffset]::Parse([string]$readRow.observed_at_utc)).TotalSeconds
if ($readerAge -lt 0 -or $readerAge -gt 75) { throw 'READER_TOO_OLD_FOR_TRANSFER' }
$out = [ordered]@{release_id=$id;phase=$Phase;plan_sha256=$planHash;
    reader=[Convert]::ToBase64String($readBytes);reader_cms=[Convert]::ToBase64String($readCms)}
if ($rule[0]) {
    $now = [DateTimeOffset]::UtcNow
    $until = $now.AddMinutes(3)
    if ($Phase -in @('Prepare','Stop','Seal','CasApproval') -and $end -lt $until) { $until = $end }
    $bindings = [ordered]@{plan_sha256=$planHash;reader_certificate_sha256=$readerPin}
    if ($Phase -in @('Prepare','Runtime','Activate')) {
        $bindings.runtime_spec_sha256 = Digest ([IO.File]::ReadAllBytes((Join-Path $WindowDirectory 'runtime-spec.json')))
    }
    if ($Phase -eq 'Runtime') {
        $runtime = Read-Object (Join-Path $WindowDirectory 'reviewed-runtime-start-authority.json')
        if ($runtime.plan_sha256 -cne $planHash -or
            $runtime.explicit_lease_hours -notin (1..95) -or
            $runtime.start_authority.runtime_release_packet_file_sha256 -cne
                (Digest ([IO.File]::ReadAllBytes((Join-Path $WindowDirectory 'runtime-release-packet.json'))))) {
            throw 'RUNTIME_REVIEW_REQUIRED_FOR_EXACT_PACKET'
        }
        $bindings.host_receipt_sha256 = Digest $readBytes
        $bindings.start_authority = $runtime.start_authority
        $until = $now.AddHours([int]$runtime.explicit_lease_hours)
    }
    if ($until -le $now.AddSeconds(20)) { throw 'APPROVAL_TOO_LATE_HOLD' }
    $authorizedRuntimeArtifacts = [ordered]@{}
    $exactRuntimePins = @{
      'supabase/v3-cas-audit-stage4-followup-release.sql' = '3cb150387ee4569b9826bbf5e4091ccf78981a44c0c3bbf83faeef959fc7002f'
      'supabase/v3-experimental-paper-atomic-cas-INACTIVE-20261013.sql' = '989e1657e03867774907f3a1ec9c9f4f84ee70c2d4b7a258cad9dc3e480f0043'
      'tools/v3-one-time-paper-release.ps1' = 'aecd031a189bd6431b8d6f2656f2c2b8bc7c2bcfbd287d6ef636b082e5b3f68c'
      'tools/v3-one-time-release.ps1' = 'fe3d55e0299a7cd83647a6fed4580cb3956dda062402dd2e79f24cc88aae07d8'
    }
    if (@($fixed.artifacts.PSObject.Properties).Count -ne 14) { throw 'PR737_AUTHORIZATION_ARTIFACT_COUNT_HOLD' }
    foreach ($artifact in $fixed.artifacts.PSObject.Properties) {
      if ($artifact.Name -cnotmatch '^(tools|supabase|paper_evaluator)/[A-Za-z0-9_./-]+$' -or $artifact.Name.Contains('..') -or
          [string]$artifact.Value -cnotmatch '^[a-f0-9]{64}$') { throw 'PR737_AUTHORIZATION_ARTIFACT_PIN_HOLD' }
      $authorizedRuntimeArtifacts[$artifact.Name] = if ($exactRuntimePins.ContainsKey($artifact.Name)) { $exactRuntimePins[$artifact.Name] } else { [string]$artifact.Value }
    }
    if (@($authorizedRuntimeArtifacts.Keys).Count -ne 14) { throw 'PR737_AUTHORIZATION_ARTIFACT_COUNT_HOLD' }
    $claims = [ordered]@{
        kind='V3_ONE_TIME_RELEASE_AUTHORIZATION_V1';release_id=$id;scope=$rule[0]
        base_commit='5b1789e349b157d06d3109c5f0ff10d95154bf81';release_commit=$fixed.repo_sha
        not_before_utc=$now.AddSeconds(-5).ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
        expires_at_utc=$until.ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
        project_ref='nlgzjmqgwueojlyqmoru';computer_name='MINI-PC';trading_root='C:\Users\ADMIN\Trading'
        artifacts=$authorizedRuntimeArtifacts;bindings=$bindings
    }
    $certs = @(Get-ChildItem Cert:\CurrentUser\My | Where-Object {
        $_.HasPrivateKey -and $_.NotBefore.ToUniversalTime() -le $now.UtcDateTime -and
        $_.NotAfter.ToUniversalTime() -gt $now.UtcDateTime -and (Digest $_.RawData) -ceq $authorityPin
    })
    if ($certs.Count -ne 1) { throw 'AUTHORITY_CERT_REQUIRED' }
    $bytes = $utf8.GetBytes(($claims | ConvertTo-Json -Depth 24 -Compress))
    $cms = [Security.Cryptography.Pkcs.SignedCms]::new([Security.Cryptography.Pkcs.ContentInfo]::new($bytes),$true)
    $signer = [Security.Cryptography.Pkcs.CmsSigner]::new($certs[0])
    $signer.DigestAlgorithm = [Security.Cryptography.Oid]::new('2.16.840.1.101.3.4.2.1')
    $signer.IncludeOption = [Security.Cryptography.X509Certificates.X509IncludeOption]::EndCertOnly
    $cms.ComputeSignature($signer)
    $sig = $cms.Encode()
    Assert-Cms $bytes $sig $authorityPin
    $out.approval = [Convert]::ToBase64String($bytes)
    $out.approval_cms = [Convert]::ToBase64String($sig)
}
$leaf = "$Phase-$planHash-$([guid]::NewGuid().ToString('N')).json"
$path = Join-Path $handoff $leaf
Write-Once $path ($utf8.GetBytes(($out | ConvertTo-Json -Depth 10 -Compress)))
Write-Output $path
