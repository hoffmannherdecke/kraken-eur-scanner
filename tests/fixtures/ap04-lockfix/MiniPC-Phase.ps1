[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('PaperPrepare','PaperStop','PaperSealEpoch','PaperCas','PaperActivate','PaperRollback','PaperResume')]
    [string]$Mode,
    [Parameter(Mandatory=$true)][string]$WindowDirectory,
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{64}$')][string]$FixedSha256,
    [Parameter(Mandatory=$true)][string]$NotebookTransfer,
    [string]$CasReaderTransfer,
    [string]$RuntimeTransfer,
    [Security.SecureString]$PostgresPassword,
    [string]$CaFile,
    [switch]$Execute
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($env:COMPUTERNAME -ine 'MINI-PC') { throw 'ORIGINAL_MINIPC_REQUIRED' }
if (-not $Execute) { throw 'EXPLICIT_LOCAL_EXECUTION_REQUIRED' }
$trading = 'C:\Users\ADMIN\Trading'
if ($WindowDirectory -cnotmatch '^C:\\Users\\ADMIN\\Trading\\Research\\V3Paper\\PR700-Window-[0-9]{8}T[0-9]{6}Z$' -or
    $WindowDirectory -cne [IO.Path]::GetFullPath($WindowDirectory)) { throw 'LOCAL_WINDOW_PATH_HOLD' }
$fixedFile = Join-Path $WindowDirectory 'cutover-fixed-inputs.json'
if ((Get-FileHash -LiteralPath $fixedFile -Algorithm SHA256).Hash -ine $FixedSha256) { throw 'FIXED_HASH_HOLD' }
$fixed = Get-Content -LiteralPath $fixedFile -Raw | ConvertFrom-Json -ErrorAction Stop
if ($fixed.repo_sha -cnotmatch '^[a-f0-9]{40}$' -or $fixed.authority_admission_sha256 -cnotmatch '^[a-f0-9]{64}$') {
    throw 'EXACT_VERSION_AND_ADMISSION_REQUIRED'
}
$stage = Join-Path $trading ('Staging\V3Paper-INACTIVE-'+$fixed.repo_sha.Substring(0,12))
$operator = Join-Path $stage 'tools\v3-one-time-release.ps1'
if ((Get-FileHash -LiteralPath $operator -Algorithm SHA256).Hash -ine $fixed.artifacts.'tools/v3-one-time-release.ps1') {
    throw 'OPERATOR_SOURCE_HOLD'
}
$planLeaf = if ($Mode -eq 'PaperPrepare') { 'plan.stage4.json' } elseif ($Mode -eq 'PaperStop') { 'plan.stop.json' } else { 'plan.cas.json' }
$planPath = Join-Path $WindowDirectory $planLeaf
$plan = Get-Content -LiteralPath $planPath -Raw | ConvertFrom-Json -ErrorAction Stop
$planHash = (Get-FileHash -LiteralPath $planPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($plan.kind -cne 'V3_ONE_TIME_PAPER_RELEASE_PLAN_V1' -or $plan.repo_sha -cne $fixed.repo_sha -or
    $plan.bundle_sha256 -cne $fixed.bundle_sha256 -or $plan.strategy_sha256 -cne $fixed.strategy_sha256 -or
    $plan.series_id -cnotmatch '^PAPER-V3-[0-9]{8}T[0-9]{6}Z$' -or $plan.cas_epoch.epoch_id -cnotmatch '^V3CAS-AUDIT-[a-f0-9]{32}$') {
    throw 'ORIGINAL_PLAN_SCOPE_HOLD'
}
$releaseId = 'V3-ONETIME-' + $plan.cas_epoch.epoch_id.Substring(12)
$handoff = 'D:\V3-PR682-Authority-Handoff\PR700-Window-' + $plan.series_id.Substring(9)
$rules = @{
    PaperPrepare='Prepare';PaperStop='Stop';PaperSealEpoch='Seal';PaperCas='CasApproval'
    PaperActivate='Activate';PaperRollback='Rollback';PaperResume='Resume'
}
function Read-SharedTransferText([string]$Path) {
    for ($attempt = 0; $attempt -lt 3; $attempt++) {
        try {
            return [IO.File]::ReadAllText($Path)
        }
        catch [System.IO.IOException] {
            $win32 = $_.Exception.HResult -band 0xFFFF

            if ($win32 -ne 32 -or $attempt -ge 2) {
                throw
            }

            [Threading.Thread]::Sleep(75)
        }
    }

    throw 'AP04_TRANSFER_READ_HOLD'
}
function Read-Transfer([string]$Path,[string]$Phase) {
    $full = [IO.Path]::GetFullPath($Path)
    if ((Split-Path -Parent $full) -ine $handoff -or (Split-Path -Leaf $full) -cnotmatch ('^'+$Phase+'-[a-f0-9]{64}-[a-f0-9]{32}\.json$')) {
        throw 'MISTRAL_EXACT_TRANSFER_PATH_HOLD'
    }
    $file = Get-Item -LiteralPath $full
    if ($file.PSIsContainer -or $file.Length -le 0 -or $file.Length -gt 160000 -or
        ($file.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'MISTRAL_TRANSFER_FILE_HOLD' }
    $record = Read-SharedTransferText -Path $full | ConvertFrom-Json -ErrorAction Stop
    if ($record.release_id -cne $releaseId -or $record.phase -cne $Phase -or $record.plan_sha256 -cne $planHash) {
        throw 'MISTRAL_TRANSFER_BINDING_HOLD'
    }
    $record
}
function Write-Exact([string]$Path,[byte[]]$Bytes) {
    if ([IO.File]::Exists($Path)) {
        if ([Convert]::ToBase64String([IO.File]::ReadAllBytes($Path)) -cne [Convert]::ToBase64String($Bytes)) {
            throw 'LOCAL_HANDOFF_ALREADY_HAS_DIFFERENT_BYTES'
        }
        return
    }
    $pending = $Path + '.pending-' + [guid]::NewGuid().ToString('N')
    try {
        [IO.File]::WriteAllBytes($pending,$Bytes)
        [IO.File]::Move($pending,$Path)
    } finally { if ([IO.File]::Exists($pending)) { [IO.File]::Delete($pending) } }
}
$decision = Read-Transfer $NotebookTransfer $rules[$Mode]
$receipt = if ($Mode -eq 'PaperCas') { Read-Transfer $CasReaderTransfer 'CasReader' } else { $decision }
$phase = Join-Path $WindowDirectory ($Mode + '-' + [guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($phase)
Write-Exact (Join-Path $phase 'approval.json') ([Convert]::FromBase64String($decision.approval))
Write-Exact (Join-Path $phase 'approval.cms') ([Convert]::FromBase64String($decision.approval_cms))
Write-Exact (Join-Path $phase 'reader.json') ([Convert]::FromBase64String($receipt.reader))
Write-Exact (Join-Path $phase 'reader.cms') ([Convert]::FromBase64String($receipt.reader_cms))
if ($Mode -eq 'PaperActivate') {
    $runtime = Read-Transfer $RuntimeTransfer 'Runtime'
    . (Join-Path $PSScriptRoot 'Flow-Common.ps1')
    Assert-SamePostCasReader $runtime $decision $planHash
    $boot = $plan.runtime_bootstrap
    $runtimePlan = Join-Path $WindowDirectory 'runtime-plan.json'
    $paths = [ordered]@{
        'runtime-approval.json' = $boot.approval_json
        'runtime-approval.cms' = $boot.approval_cms
        'postcas-reader.json' = $boot.host_receipt
        'postcas-reader.cms' = $boot.host_cms
    }
    foreach ($leaf in $paths.Keys) {
        if ($paths[$leaf] -cne (Join-Path $WindowDirectory $leaf)) { throw 'RUNTIME_DESTINATION_DRIFT' }
    }
    if ($boot.admission_json -cne $fixed.authority_admission_path) { throw 'RUNTIME_ADMISSION_DRIFT' }
    Write-Exact $runtimePlan ([IO.File]::ReadAllBytes($planPath))
    Write-Exact $boot.approval_json ([Convert]::FromBase64String($runtime.approval))
    Write-Exact $boot.approval_cms ([Convert]::FromBase64String($runtime.approval_cms))
    Write-Exact $boot.host_receipt ([Convert]::FromBase64String($runtime.reader))
    Write-Exact $boot.host_cms ([Convert]::FromBase64String($runtime.reader_cms))
}
$params = @{
    Mode = $Mode; PackageRoot = $stage; ExpectedReleaseCommit = $fixed.repo_sha
    AuthorityAdmissionJson = $fixed.authority_admission_path
    ExpectedAuthorityAdmissionSha256 = $fixed.authority_admission_sha256
    ApprovalJson = Join-Path $phase 'approval.json'; ApprovalCms = Join-Path $phase 'approval.cms'
    PaperPlanJson = $planPath; RuntimeSpecJson = Join-Path $WindowDirectory 'runtime-spec.json'
    HostReceiptJson = Join-Path $phase 'reader.json'; HostReceiptCms = Join-Path $phase 'reader.cms'
}
if ($CaFile) { $params.CaFile = $CaFile }
if ($Mode -in @('PaperSealEpoch','PaperCas')) {
    if ($null -eq $PostgresPassword) { throw 'LOCAL_SCOPE_CREDENTIAL_REQUIRED' }
    $params.PostgresPassword = $PostgresPassword
} elseif ($null -ne $PostgresPassword) { throw 'UNEXPECTED_CREDENTIAL' }
& $operator @params
