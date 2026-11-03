# Isolated Windows-only syscall proof for the existing PR515 native rename.
# Runs the exact embedded C# body from the still hardlocked original operator.
# NEVER invokes the originalhost cutover, creates ARMED, or edits Trading.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$OperatorSource,
 [Parameter(Mandatory=$true)][string]$ReviewedOperatorGitBlob
)
$ErrorActionPreference='Stop'
if([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT){
 throw 'V3_NATIVE_SMOKE_WINDOWS_ONLY'
}
if($ReviewedOperatorGitBlob -cnotmatch '^[a-f0-9]{40}$'){
 throw 'V3_NATIVE_SMOKE_BLOB_PIN_INVALID'
}
$full=[IO.Path]::GetFullPath($OperatorSource)
if(-not [IO.File]::Exists($full)){throw 'V3_NATIVE_SMOKE_SOURCE_MISSING'}
$actual=@(& git hash-object -- $full 2>$null)
if($LASTEXITCODE -ne 0 -or $actual.Count -ne 1 -or
   [string]$actual[0] -cne $ReviewedOperatorGitBlob){
 throw 'V3_NATIVE_SMOKE_OPERATOR_NOT_EXACT_REVIEWED_BYTES'
}
$src=[IO.File]::ReadAllText($full)
$begin=$src.IndexOf('function Invoke-V3Pr515NativeExclusiveFenceArchiveSOURCE_ONLY(')
if($begin -lt 0){throw 'V3_NATIVE_SMOKE_FUNCTION_NOT_FOUND'}
$end=$src.IndexOf('# Scoped originalhost ARMED marker-only cancel (SOURCE ONLY; no release).',$begin)
# Native helper is nested AFTER the first statement throw of the parent, so
# search only the bounded snippet up to the next native-prereq check.
if($end -ge 0){throw 'V3_NATIVE_SMOKE_HELPER_ESCAPED_PARENT_SCOPE'}
$pre=$src.Substring(0,$begin)
if($pre.LastIndexOf("throw 'V3_PR515_MARKER_ONLY_CANCEL_SOURCE_LOCKED_INDEPENDENT_ABORT_CUSTODY_NOT_WIRED'") -lt 0){
 throw 'V3_NATIVE_SMOKE_PARENT_HARDLOCK_MISSING'
}
$head=$src.Substring($begin,[Math]::Min(12000,$src.Length-$begin))
$match=[regex]::Match($head,"(?s)\$src=@'\r?\n(?<code>.*?)\r?\n'@")
if(-not $match.Success){throw 'V3_NATIVE_SMOKE_EMBEDDED_CSHARP_MISSING'}
$code=$match.Groups['code'].Value
if($code -notmatch 'SetFileInformationByHandle' -or
   $code -notmatch 'GENERIC_READ\|DELETE_ACCESS,0' -or
   $code -notmatch 'FILE_RENAME_INFO_CLASS=3'){
 throw 'V3_NATIVE_SMOKE_UNEXPECTED_NATIVE_ABI'
}
# No production state path appears in this isolated native class body.
if($code -match 'C:\\Users\\ADMIN\\Trading|Get-ScheduledTask|Stop-ScheduledTask'){
 throw 'V3_NATIVE_SMOKE_CSHARP_NOT_ISOLATED'
}
if(-not ('V3Pr515NativeFenceRenameV1' -as [type])){
 Add-Type -TypeDefinition $code -ErrorAction Stop
}
$root=Join-Path ([IO.Path]::GetTempPath()) ('V3-Pr515-NativeSmoke-'+[guid]::NewGuid().ToString('N'))
[IO.Directory]::CreateDirectory($root)|Out-Null
$success=$false
$wrongHashRejected=$false
$existingTargetRejected=$false
$shareConflictRejected=$false
try{
 $data=[byte[]](1..200)
 $hash=[Security.Cryptography.SHA256]::Create()
 try{
  $expected=([BitConverter]::ToString($hash.ComputeHash($data))).Replace('-','').ToLowerInvariant()
 }finally{$hash.Dispose()}
 $a=Join-Path $root 'source-good.bin'
 $b=Join-Path $root 'target-good.bin'
 [IO.File]::WriteAllBytes($a,$data)
 [V3Pr515NativeFenceRenameV1]::RenamePinned($a,$b,$expected)
 $success=(-not [IO.File]::Exists($a) -and [IO.File]::Exists($b) -and
   (Get-FileHash -LiteralPath $b -Algorithm SHA256).Hash.ToLowerInvariant() -ceq $expected)
 $bad=Join-Path $root 'source-bad-hash.bin'
 $badTarget=Join-Path $root 'target-bad-hash.bin'
 [IO.File]::WriteAllBytes($bad,$data)
 try{[V3Pr515NativeFenceRenameV1]::RenamePinned($bad,$badTarget,('0'*64))}
 catch{$wrongHashRejected=([IO.File]::Exists($bad) -and -not [IO.File]::Exists($badTarget))}
 $conflict=Join-Path $root 'source-existing-target.bin'
 $existing=Join-Path $root 'target-existing.bin'
 [IO.File]::WriteAllBytes($conflict,$data)
 [IO.File]::WriteAllBytes($existing,([byte[]](201..255)))
 try{[V3Pr515NativeFenceRenameV1]::RenamePinned($conflict,$existing,$expected)}
 catch{$existingTargetRejected=[IO.File]::Exists($conflict)}
 $shared=Join-Path $root 'source-locked.bin'
 $sharedTarget=Join-Path $root 'target-locked.bin'
 [IO.File]::WriteAllBytes($shared,$data)
 $hold=[IO.File]::Open($shared,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
 try{
  try{[V3Pr515NativeFenceRenameV1]::RenamePinned($shared,$sharedTarget,$expected)}
  catch{$shareConflictRejected=([IO.File]::Exists($shared) -and -not [IO.File]::Exists($sharedTarget))}
 }finally{$hold.Dispose()}
}finally{
 if([IO.Directory]::Exists($root)){
  [IO.Directory]::Delete($root,$true)
 }
}
if(-not($success -and $wrongHashRejected -and $existingTargetRejected -and $shareConflictRejected)){
 throw ('V3_NATIVE_SMOKE_FAIL success={0} wrongHash={1} existingTarget={2} sharing={3}' -f
   $success,$wrongHashRejected,$existingTargetRejected,$shareConflictRejected)
}
[pscustomobject][ordered]@{
 kind='V3_PR515_NATIVE_NTFS_SYSCALL_ISOLATED_SMOKE_V1'
 status='PASS_ISOLATED_WINDOWS_NATIVE_RENAME_NOT_RELEASE'
 exact_operator_git_blob=$ReviewedOperatorGitBlob
 exclusive_handle_rename_pass=$success
 wrong_sha_denied=$wrongHashRejected
 overwrite_denied=$existingTargetRejected
 sharing_conflict_denied=$shareConflictRejected
 originalhost_marker_or_tasks_mutated=$false
 cloud_or_cas_mutated=$false
 independent_custody_verified=$false
 operator_release_authorized=$false
 v3_paper_authorized=$false
}|ConvertTo-Json -Compress
