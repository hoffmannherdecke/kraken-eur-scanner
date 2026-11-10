# AP04 scoped GitHub -> original PR701 starter handoff; NOT RELEASE APPROVED.
# This file is a candidate only. Do not deploy or run -Dispatch without separate byte-specific owner admission.
[CmdletBinding(DefaultParameterSetName='ReadOnly')]
param(
    [Parameter(ParameterSetName='Dispatch',Mandatory=$true)][switch]$Dispatch,
    [Parameter(ParameterSetName='ReadOnly')][switch]$ReadOnly,
    [Parameter(ParameterSetName='HistoricalTest')][switch]$HistoricalTest,
    [string]$ArchivePath = 'C:\Users\ADMIN\Downloads\KRYPTO-V3-PR701-Fenster.zip',
    [string]$StarterPath = 'C:\Users\ADMIN\Downloads\KRYPTO-V3-PR701-Freigabeuebergabe\Start-PR701-FromWindowArchive.ps1',
    [string]$ApprovedHandoffSha256 = '',
    [Parameter(ParameterSetName='Dispatch',Mandatory=$true)][string]$CaFile,
    [Parameter(ParameterSetName='Dispatch',Mandatory=$true)][long]$AdmissionCommentId,
    [int]$MaxPollSeconds = 15
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version 2
$clock=[Diagnostics.Stopwatch]::StartNew()
$zip=$null
function Hold([string]$reason) { throw ('AP04_DISPATCH_HANDOFF_HOLD:'+$reason) }
function Read-ZipJson([string]$name) {
    $entries=@($script:zip.Entries | Where-Object { $_.FullName.Replace('\','/') -ceq $name })
    if($entries.Count -ne 1) { Hold ('ARCHIVE_ENTRY_COUNT_'+$name+'_'+$entries.Count) }
    if($entries[0].Length -gt 131072) { Hold ('OVERSIZED_ENTRY_'+$name) }
    $reader=New-Object System.IO.StreamReader($entries[0].Open())
    try { return ($reader.ReadToEnd() | ConvertFrom-Json -ErrorAction Stop) }
    finally { $reader.Dispose() }
}
function Compare-Decision([object]$actual,[object]$expected) {
    foreach($name in @('kind','decision','scope','release_commit','successor_series_id','plan_sha256','dry_run_sha256')) {
        if([string]$actual.$name -cne [string]$expected.$name) { Hold ('OWNER_BINDING_'+$name) }
    }
}
function New-AP04DispatchAttemptLatch([string]$Root,[string]$Series,[byte[]]$Receipt) {
    # The SAME function is tested concurrently in an isolated disposable directory.
    $path=Join-Path $Root ('AP04-Stage4-Dispatch-Attempt-'+$Series+'.json')
    try {
        $stream=[IO.File]::Open($path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    } catch [IO.IOException] {
        throw 'DISPATCH_ATTEMPT_ALREADY_PRESENT_OR_UNKNOWN_NO_RETRY'
    }
    try { $stream.Write($Receipt,0,$Receipt.Length);$stream.Flush($true) }
    finally { $stream.Dispose() }
    return $path
}
try {
    if($env:COMPUTERNAME -cne 'MINI-PC') { Hold 'ORIGINALHOST_REQUIRED' }
    if($MaxPollSeconds -lt 0 -or $MaxPollSeconds -gt 30) { Hold 'POLL_BOUND' }
    if(!(Test-Path -LiteralPath $ArchivePath -PathType Leaf)) { Hold 'ARCHIVE_MISSING' }
    if(!(Test-Path -LiteralPath $StarterPath -PathType Leaf)) { Hold 'STARTER_MISSING' }
    $expectedStarter='8b1d20ecf6d61ca22a3ad1b6d01da293fd26da23180ffa92ce00875e29de33a5'
    $starterSha=(Get-FileHash -LiteralPath $StarterPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if($starterSha -cne $expectedStarter){ Hold 'STARTER_BYTES_NOT_APPROVED' }
    $thisScriptSha=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if($Dispatch -and ($ApprovedHandoffSha256 -cnotmatch '^[a-f0-9]{64}$' -or $ApprovedHandoffSha256 -cne $thisScriptSha)) { Hold 'HANDOFF_BYTES_NOT_ADMITTED' }
    if($Dispatch) {
        if($CaFile -cne 'C:\\Users\\ADMIN\\Downloads\\prod-ca-2021.crt' -or !(Test-Path -LiteralPath $CaFile -PathType Leaf)) { Hold 'APPROVED_CA_FILE_REQUIRED' }
        [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
        $admissionUrl='https://api.github.com/repos/hoffmannherdecke/kraken-eur-scanner/issues/comments/'+$AdmissionCommentId
        $admissionComment=Invoke-RestMethod -Uri $admissionUrl -Headers @{'User-Agent'='PR701-AP04-Admission';'Accept'='application/vnd.github+json'} -TimeoutSec 8
        if([string]$admissionComment.id -cne [string]$AdmissionCommentId -or
           [string]$admissionComment.user.login -cne 'hoffmannherdecke' -or
           [string]$admissionComment.html_url -cne ('https://github.com/hoffmannherdecke/kraken-eur-scanner/issues/99#issuecomment-'+$AdmissionCommentId)) { Hold 'HANDOFF_ADMISSION_PROVENANCE' }
        $admission=$admissionComment.body | ConvertFrom-Json -ErrorAction Stop
        if([string]$admission.kind -cne 'AP04_HANDOFF_BYTE_ADMISSION_V1' -or
           [string]$admission.decision -cne 'APPROVED_FOR_AP04_SCOPED_DISPATCH' -or
           [string]$admission.handoff_sha256 -cne $thisScriptSha -or
           [string]$admission.release_commit -cne '46c5abbd6af16266c1229943db973dc9d6b2fb4f') { Hold 'HANDOFF_ADMISSION_BINDING' }
    }

    Add-Type -AssemblyName System.IO.Compression
    $archiveSha=(Get-FileHash -LiteralPath $ArchivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    $zip=[IO.Compression.ZipFile]::OpenRead($ArchivePath)
    $launch=Read-ZipJson 'window-launch-inputs.json'
    $template=Read-ZipJson 'freigabefenster/pr700-stage4-owner-decision-template.json'
    $series=[string]$launch.series_id
    if($series -cnotmatch '^PAPER-V3-(\d{8}T\d{6}Z)$') { Hold 'SERIES_FORMAT' }
    $stamp=[string]$Matches[1]
    $t0=[DateTime]::ParseExact($stamp,"yyyyMMdd'T'HHmmss'Z'",[Globalization.CultureInfo]::InvariantCulture,[Globalization.DateTimeStyles]::AssumeUniversal -bor [Globalization.DateTimeStyles]::AdjustToUniversal)
    $cutoff=$t0.AddMinutes(4)
    $expiry=$t0.AddMinutes(10)
    if([string]$launch.release_commit -cne '46c5abbd6af16266c1229943db973dc9d6b2fb4f') { Hold 'RELEASE_COMMIT' }
    if([string]$launch.stage4_plan_sha256 -cne [string]$template.plan_sha256){ Hold 'PLAN_HASH' }
    if([string]$template.successor_series_id -cne $series -or [string]$template.release_commit -cne [string]$launch.release_commit) { Hold 'ARCHIVE_TEMPLATE_BINDING' }
    if([string]$template.kind -cne 'PR700_SERIES_AND_STAGE4_DECISION_V1' -or [string]$template.decision -cne 'ISSUED_FOR_EXACT_RUNTIME_RELEASE' -or [string]$template.scope -cne 'CLOUD_STAGE4_EPOCH_OPEN') { Hold 'TEMPLATE_SCOPE' }
    foreach($v in @([string]$template.plan_sha256,[string]$template.dry_run_sha256,[string]$launch.stage4_script_sha256)) {
        if($v -cnotmatch '^[0-9a-f]{64}$') { Hold 'HASH_FORMAT' }
    }
    if($HistoricalTest) {
        if($series -cne 'PAPER-V3-20261110T084225Z'){ Hold 'HISTORICAL_FIXTURE_SERIES' }
        [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
        $historicUrl='https://api.github.com/repos/hoffmannherdecke/kraken-eur-scanner/issues/comments/6762984107'
        $historic=Invoke-RestMethod -Uri $historicUrl -Headers @{'User-Agent'='PR701-AP04-Historical-Test';'Accept'='application/vnd.github+json'} -TimeoutSec 8
        if([string]$historic.id -cne '6762984107' -or [string]$historic.user.login -cne 'hoffmannherdecke' -or [string]$historic.html_url -cne 'https://github.com/hoffmannherdecke/kraken-eur-scanner/issues/99#issuecomment-6762984107'){ Hold 'HISTORICAL_PROVENANCE' }
        $d=$historic.body | ConvertFrom-Json -ErrorAction Stop
        Compare-Decision $d $template
        $negative=$template | ConvertTo-Json -Depth 10 | ConvertFrom-Json
        $negative.successor_series_id='PAPER-V3-INVALID'
        $rejected=$false
        try { Compare-Decision $d $negative } catch { $rejected=$true }
        if(!$rejected){ Hold 'NEGATIVE_SERIES_NOT_REJECTED' }
        $negative.successor_series_id=$template.successor_series_id
        $negative.plan_sha256=('0'*64)
        $rejected=$false
        try { Compare-Decision $d $negative } catch { $rejected=$true }
        if(!$rejected){ Hold 'NEGATIVE_PLAN_HASH_NOT_REJECTED' }
        $negative.plan_sha256=$template.plan_sha256
        $negative.dry_run_sha256=('0'*64)
        $rejected=$false
        try { Compare-Decision $d $negative } catch { $rejected=$true }
        if(!$rejected){ Hold 'NEGATIVE_DRY_HASH_NOT_REJECTED' }
        if([DateTime]::UtcNow -lt $cutoff){ Hold 'HISTORICAL_EXPIRY_TEST_INVALID' }
        $arguments=@{ Role='MiniPC';WindowArchiveSha256=$archiveSha;DecisionCommentId=[long]$historic.id }
        if($arguments.WindowArchiveSha256 -cne $archiveSha -or $arguments.DecisionCommentId -ne [long]6762984107){ Hold 'HISTORICAL_ARGUMENT_BINDING' }
        $zip.Dispose();$zip=$null
        $clock.Stop()
        Write-Output 'AP04_HISTORICAL_INTEGRATED_HANDOFF_TEST_PASS'
        Write-Output ('HISTORICAL_HANDOFF_SECONDS='+[math]::Round($clock.Elapsed.TotalSeconds,3))
        Write-Output 'NEGATIVE_SERIES_PLAN_DRYRUN_AND_EXPIRY_PASS'
        Write-Output 'NO_STARTER_EXECUTION_NO_RELEASE'
        return
    }
    if([DateTime]::UtcNow -ge $cutoff) { Hold 'INSUFFICIENT_WINDOW_BUDGET' }
    # GitHub ISSUE #99 authentic REST read, no gh dependency. Never trust a supplied comment ID.
    [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
    $headers=@{'User-Agent'='PR701-AP04-Originalhost';'Accept'='application/vnd.github+json';'X-GitHub-Api-Version'='2022-11-28'}
    $uri='https://api.github.com/repos/hoffmannherdecke/kraken-eur-scanner/issues/99/comments?per_page=100&since='+[Uri]::EscapeDataString($t0.ToString('yyyy-MM-ddTHH:mm:ssZ'))
    $deadline=[DateTime]::UtcNow.AddSeconds($MaxPollSeconds)
    $selected=$null
    do {
        if([DateTime]::UtcNow -ge $cutoff) { Hold 'WINDOW_CUTOFF_BEFORE_OWNER' }
        $comments=@(Invoke-RestMethod -Uri $uri -Headers $headers -Method Get -TimeoutSec 8 -ErrorAction Stop)
        # Fail closed if pagination might have hidden a relevant decision.
        if($comments.Count -ge 100){ Hold 'OWNER_COMMENTS_PAGINATION_REQUIRED' }
        foreach($comment in $comments) {
            if([string]$comment.user.login -cne 'hoffmannherdecke') { continue }
            if([string]$comment.html_url -cnotmatch '^https://github\.com/hoffmannherdecke/kraken-eur-scanner/issues/99#issuecomment-([0-9]+)$') { continue }
            if([string]$comment.id -cne [string]$Matches[1]) { continue }
            $created=[DateTimeOffset]::Parse([string]$comment.created_at).UtcDateTime
            if($created -lt $t0 -or $created -ge $cutoff) { continue }
            try { $candidate=$comment.body | ConvertFrom-Json -ErrorAction Stop } catch { continue }
            $keys=@('kind','decision','scope','release_commit','successor_series_id','plan_sha256','dry_run_sha256')
            $same=$true
            foreach($key in $keys) { if([string]$candidate.$key -cne [string]$template.$key) { $same=$false;break } }
            if(!$same){ continue }
            if($null -ne $selected) { Hold 'MULTIPLE_EXACT_OWNER_DECISIONS' }
            $selected=$comment
        }
        if($null -ne $selected) { break }
        if([DateTime]::UtcNow -ge $deadline) { Hold 'OWNER_DECISION_NOT_FOUND' }
        Start-Sleep -Milliseconds 500
    } while($true)
    # Close the archive before invoking any existing operator.
    $zip.Dispose();$zip=$null
    if([DateTime]::UtcNow -ge $cutoff) { Hold 'INSUFFICIENT_WINDOW_BUDGET_BEFORE_DISPATCH' }
    $argsBound=@{Role='MiniPC';WindowArchiveSha256=$archiveSha;DecisionCommentId=[long]$selected.id}
    if($Dispatch) { $argsBound.CaFile=$CaFile }
    $clock.Stop()
    Write-Output 'AP04_GITHUB_DISPATCH_HANDOFF_PREPARED'
    Write-Output ('COMMENT_ID='+$selected.id)
    Write-Output ('ARCHIVE_SHA256='+$archiveSha)
    Write-Output ('SERIES='+$series)
    Write-Output ('HANDOFF_SECONDS='+[math]::Round($clock.Elapsed.TotalSeconds,3))
    Write-Output ('REMAINING_SECONDS='+[math]::Round(($expiry-[DateTime]::UtcNow).TotalSeconds,2))
    if(!$Dispatch) {
        Write-Output 'AP04_READONLY_NO_STARTER_EXECUTION'
        return
    }
    # An original-host durable, series-scoped attempt latch is created atomically BEFORE
    # any starter call. Two callers race on FileMode.CreateNew: exactly one wins.
    # Never remove or reset on failure, timeout, restart or UNKNOWN. This is the
    # handoff-attempt barrier, not a replacement for original Stage4/Cloud gates.
    $journalRoot='D:\V3-PR682-Authority-Handoff'
    $rootItem=Get-Item -LiteralPath $journalRoot -Force -ErrorAction Stop
    if(-not $rootItem.PSIsContainer -or ($rootItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        Hold 'DISPATCH_JOURNAL_ROOT_UNSAFE'
    }
    if([DateTime]::UtcNow -ge $cutoff) { Hold 'WINDOW_CUTOFF_BEFORE_ATTEMPT_LATCH' }
    $attempt=[ordered]@{
        kind='AP04_ORIGINALHOST_DISPATCH_ATTEMPT_V1'
        successor_series_id=$series
        release_commit=[string]$launch.release_commit
        archive_sha256=$archiveSha
        plan_sha256=[string]$template.plan_sha256
        dry_run_sha256=[string]$template.dry_run_sha256
        decision_comment_id=[long]$selected.id
        created_at_utc=[DateTime]::UtcNow.ToString('o')
        outcome='ATTEMPTED_OUTCOME_UNKNOWN_UNTIL_INDEPENDENT_READBACK'
        retry_authorized=$false
    }
    $latchBytes=[Text.UTF8Encoding]::new($false).GetBytes(($attempt | ConvertTo-Json -Compress))
    $latchPath=New-AP04DispatchAttemptLatch -Root $journalRoot -Series $series -Receipt $latchBytes
    Write-Output 'AP04_DURABLE_DISPATCH_ATTEMPT_LATCH_CREATED'
    # The original starter retains all CAS, Stage4, reader, authority and time gates.
    # Do not repeat even if original starter fails or returns an unknown outcome.
    & $StarterPath @argsBound
    if(!$?) { Hold 'ORIGINAL_STARTER_OUTCOME_UNKNOWN_NO_RETRY' }
}
catch {
    Write-Output ('AP04_GITHUB_DISPATCH_HANDOFF_HOLD='+$_.Exception.Message)
    throw
}
finally { if($null -ne $zip){$zip.Dispose()} }
