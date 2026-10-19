# MINIPC_MANUAL_ADMIN_SETUP_ONLY
# One-time host-side setup. DO NOT run inside the GitHub runner or schedule it.
# Only creates C:\CryptoSupport\Workspace when ABSENT, adds three scoped ACLs.
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'WORKSPACE_SETUP_BLOCK: elevated PowerShell required'
}
$parent = 'C:\CryptoSupport'
$target = 'C:\CryptoSupport\Workspace'
if (-not [IO.Directory]::Exists($parent)) {
    throw 'WORKSPACE_SETUP_BLOCK: expected existing CryptoSupport parent missing'
}
$parentInfo = New-Object IO.DirectoryInfo($parent)
if (($parentInfo.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
    throw 'WORKSPACE_SETUP_BLOCK: unsafe parent reparse point'
}
if ([IO.Directory]::Exists($target) -or [IO.File]::Exists($target) -or
    (Test-Path -LiteralPath $target)) {
    throw 'WORKSPACE_SETUP_BLOCK: workspace exists; inspect rather than overwrite ACL'
}
$account = "$env:COMPUTERNAME\CryptoSupportSvc"
$sid = (New-Object Security.Principal.NTAccount($account)).Translate(
    [Security.Principal.SecurityIdentifier])
$systemSid = New-Object Security.Principal.SecurityIdentifier('S-1-5-18')
$adminsSid = New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')
$flags = [Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
         [Security.AccessControl.InheritanceFlags]::ObjectInherit
$none = [Security.AccessControl.PropagationFlags]::None
$allow = [Security.AccessControl.AccessControlType]::Allow

# On a NEW directory only; no inherited cross-project ACLs.
$acl = New-Object Security.AccessControl.DirectorySecurity
$acl.SetAccessRuleProtection($true, $false)
foreach ($who in @($systemSid, $adminsSid)) {
    $rule = New-Object Security.AccessControl.FileSystemAccessRule(
        $who, [Security.AccessControl.FileSystemRights]::FullControl,
        $flags, $none, $allow)
    [void]$acl.AddAccessRule($rule)
}
$restrictedRule = New-Object Security.AccessControl.FileSystemAccessRule(
    $sid, [Security.AccessControl.FileSystemRights]::Modify,
    $flags, $none, $allow)
[void]$acl.AddAccessRule($restrictedRule)

$created = $false
try {
    $created = $true
    $dir = [IO.Directory]::CreateDirectory($target)
    if (($dir.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'WORKSPACE_SETUP_BLOCK: unexpected workspace reparse point'
    }
    $dir.SetAccessControl($acl)
    $fresh = (New-Object IO.DirectoryInfo($target)).GetAccessControl(
        [Security.AccessControl.AccessControlSections]::Access)
    $rules = @($fresh.GetAccessRules($true, $false,
        [Security.Principal.SecurityIdentifier]))
    $restricted = @($rules | Where-Object {
        $_.IdentityReference.Value -ceq $sid.Value -and
        $_.AccessControlType -eq $allow -and
        ($_.FileSystemRights -band [Security.AccessControl.FileSystemRights]::Modify) -eq
        [Security.AccessControl.FileSystemRights]::Modify
    })
    if (-not $fresh.AreAccessRulesProtected -or $rules.Count -ne 3 -or
        $restricted.Count -ne 1) {
        throw 'WORKSPACE_SETUP_BLOCK: ACL readback differs, rollback needed'
    }
    Write-Output 'WORKSPACE_SETUP=PASS'
    Write-Output 'PATH=C:\CryptoSupport\Workspace'
    Write-Output 'RESTRICTED_ACCOUNT=CryptoSupportSvc'
    Write-Output 'SCOPE=MODIFY_WORKSPACE_ONLY'
    Write-Output 'WINDOW_OR_RUNNER_TASKS_CHANGED=FALSE'
} catch {
    if ($created) {
        try {
            $existing = New-Object IO.DirectoryInfo($target)
            if ($existing.Exists -and
                ($existing.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0 -and
                @([IO.Directory]::EnumerateFileSystemEntries($target)).Count -eq 0) {
                [IO.Directory]::Delete($target)
                Write-Output 'ROLLBACK=EMPTY_NEW_WORKSPACE_REMOVED'
            } else {
                Write-Output 'ROLLBACK=MANUAL_REVIEW_REQUIRED'
            }
        } catch { Write-Output 'ROLLBACK=MANUAL_REVIEW_REQUIRED' }
    }
    throw
}
