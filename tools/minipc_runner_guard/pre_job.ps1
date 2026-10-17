# MINI-PC protected local GitHub runner pre-job gate, v1.
# Installed ONCE by administrator outside the GitHub runner workspace.
# A nonzero exit blocks the actual job before any workflow steps.
$ErrorActionPreference = 'Stop'

function Assert-Gate([bool]$ok, [string]$reason) {
    if (-not $ok) { throw "LOCAL_PREJOB_DENIED:$reason" }
}
$root = 'C:\ProgramData\CryptoSupportGuard'
$pinFile = Join-Path $root 'approved-private-workflow-sha.txt'
Assert-Gate (Test-Path -LiteralPath $pinFile -PathType Leaf) 'pin_missing'
$pin = ([IO.File]::ReadAllText($pinFile)).Trim()
Assert-Gate ($pin -cmatch '^[a-f0-9]{40}$') 'invalid_pin'
Assert-Gate ($env:GITHUB_REPOSITORY -ceq 'hoffmannherdecke/kraken-readonly-bridge') 'wrong_repo'
Assert-Gate ($env:GITHUB_WORKFLOW_REF -ceq 'hoffmannherdecke/kraken-readonly-bridge/.github/workflows/minipc-reviewed-project-task.yml@refs/heads/main') 'wrong_workflow_ref'
Assert-Gate ($env:GITHUB_WORKFLOW_SHA -ceq $pin) 'unapproved_workflow_revision'
Assert-Gate ($env:GITHUB_WORKFLOW -ceq 'MINI-PC reviewed project task (restricted reusable execution)') 'wrong_workflow_name'
Assert-Gate ($env:GITHUB_EVENT_NAME -ceq 'issue_comment') 'wrong_event'
Assert-Gate ($env:GITHUB_REF -ceq 'refs/heads/main') 'wrong_ref'
Assert-Gate ($env:RUNNER_NAME -ceq 'MINI-PC-CryptoSupport') 'wrong_runner'

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
Assert-Gate ($identity.Name -match '(?i)\\CryptoSupportSvc$') 'wrong_windows_identity'
Assert-Gate (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) 'elevated_account'

$eventPath = [string]$env:GITHUB_EVENT_PATH
Assert-Gate (-not [string]::IsNullOrWhiteSpace($eventPath)) 'event_path_missing'
Assert-Gate (Test-Path -LiteralPath $eventPath -PathType Leaf) 'event_missing'
$eventFile = Get-Item -LiteralPath $eventPath -Force
Assert-Gate ($eventFile.Length -gt 0 -and $eventFile.Length -le 1048576) 'event_size'
$eventData = [IO.File]::ReadAllText($eventPath) | ConvertFrom-Json
Assert-Gate ($eventData.action -ceq 'created') 'wrong_action'
Assert-Gate ($eventData.issue.number -eq 13) 'wrong_issue'
Assert-Gate ($eventData.repository.full_name -ceq 'hoffmannherdecke/kraken-readonly-bridge') 'wrong_event_repo'
Assert-Gate ($eventData.comment.user.login -ceq 'hoffmannherdecke') 'wrong_actor'
Assert-Gate ($eventData.comment.author_association -ceq 'OWNER') 'wrong_association'
Assert-Gate ($eventData.comment.performed_via_github_app.slug -ceq 'chatgpt-codex-connector') 'wrong_connector'
$body = [string]$eventData.comment.body
Assert-Gate ($body -cmatch '^MINIPC_TASK_V1 \| [a-f0-9]{40} \| [a-z][a-z0-9_-]{0,39}$') 'wrong_request_type'
$created = [DateTimeOffset]::MinValue
Assert-Gate ([DateTimeOffset]::TryParse([string]$eventData.comment.created_at, [ref]$created)) 'timestamp_invalid'
$age = ([DateTimeOffset]::UtcNow - $created.ToUniversalTime()).TotalSeconds
Assert-Gate ($age -ge -60 -and $age -le 600) 'expired_request'
Write-Output 'LOCAL_PREJOB_V1_APPROVED: pinned workflow and authenticated fresh reviewed task'
