# MINIPC_REVIEWED_TASK_V1
# Bounded read-only discovery and explicitly requested small-file handoff.
# Only invoked by reviewed private workflow with a validated MINIPC_FILE_V1 request.
$ErrorActionPreference = 'Stop'
$req=[string]$env:MINI_PC_FILE_REQUEST
$id=[Security.Principal.WindowsIdentity]::GetCurrent()
$principal=New-Object Security.Principal.WindowsPrincipal($id)
if($id.Name -notmatch '(?i)\\CryptoSupportSvc$' -or $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator) -or $env:RUNNER_NAME -cne 'MINI-PC-CryptoSupport'){throw 'FILE_ACCESS_DENIED:IDENTITY'}
if($req -cnotmatch '^MINIPC_FILE_V1 \| ([a-f0-9]{40}) \| (SEARCH|EXPORT) \| (TRADING|DOWNLOADS|MISTRAL) \| ([A-Za-z0-9_.-]{3,64}|[A-Za-z0-9_-]{4,512})(?: \| ([a-f0-9]{64}))?$'){throw 'FILE_ACCESS_DENIED:REQUEST'}
$sourceSha=[string]$Matches[1];$mode=[string]$Matches[2];$key=[string]$Matches[3];$selector=[string]$Matches[4];$expected=[string]$Matches[5]
if(($mode -ceq 'SEARCH' -and ($expected -or $selector -cnotmatch '^[A-Za-z0-9][A-Za-z0-9_.-]{2,63}$')) -or
   ($mode -ceq 'EXPORT' -and (!$expected -or $selector -cnotmatch '^[A-Za-z0-9_-]{4,512}$'))){throw 'FILE_ACCESS_DENIED:REQUEST_MODE'}
$roots=@{TRADING='C:\Users\ADMIN\Trading';DOWNLOADS='C:\Users\ADMIN\Downloads';MISTRAL='\\192.168.178.179\Mistral_450'}
$root=[string]$roots[$key]
$deadline=[DateTime]::UtcNow.AddSeconds(75)
function Check-Time {if([DateTime]::UtcNow -gt $deadline){throw 'FILE_UNAVAILABLE:TIME_LIMIT'}}
function Assert-RealDirectory([string]$path) {
  # The share root itself is never skipped by the ancestor walk (UNC root equals PathRoot).
  $rootItem=Get-Item -LiteralPath $path -Force -ErrorAction Stop
  if(-not $rootItem.PSIsContainer -or ($rootItem.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'FILE_ACCESS_DENIED:REPARSE_ROOT'}
  $current=$path
  $stack=New-Object 'System.Collections.Generic.List[string]'
  while($current -and $current -ne [IO.Path]::GetPathRoot($current)){
    $stack.Insert(0,$current)
    $parent=[IO.Path]::GetDirectoryName($current)
    if($parent -eq $current){break};$current=$parent
  }
  foreach($entry in $stack){
    $info=Get-Item -LiteralPath $entry -Force -ErrorAction Stop
    if(-not $info.PSIsContainer -or ($info.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'FILE_ACCESS_DENIED:REPARSE'}
  }
}
function Assert-Path([string]$relative) {
  if($relative.Length -gt 260 -or $relative -match '[\x00-\x1f]' -or
     $relative -match '[:*?"<>|]' -or $relative.StartsWith('\') -or $relative.StartsWith('/') -or
     $relative -match '(^|[\\/])(\.|\.\.)([\\/]|$)' -or $relative -match '/'){throw 'FILE_ACCESS_DENIED:PATH'}
  $full=[IO.Path]::GetFullPath((Join-Path $root $relative))
  $prefix=$root.TrimEnd('\')+'\'
  if(-not $full.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)){throw 'FILE_ACCESS_DENIED:ESCAPE'}
  Assert-RealDirectory ([IO.Path]::GetDirectoryName($full))
  $file=Get-Item -LiteralPath $full -Force -ErrorAction Stop
  if($file.PSIsContainer -or ($file.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'FILE_ACCESS_DENIED:REPARSE_FILE'}
  return $file
}
function Safe-Name([string]$name) {
  if($name -match '(?i)(secret|password|passwd|token|credential|private|\.env|\.key|\.pem|\.pfx|\.p12|id_rsa|cert|auth|apikey|api.key|wallet|seed)'){return $false}
  return $name -cmatch '^[A-Za-z0-9_. -]{1,100}$' -and $name -notmatch '^\.' 
}
function Result([string]$state,[object[]]$files,[string]$exportFile) {
  # Reuse the single original runner ACK. File outcome is a bounded detail, not a second ACK protocol.
  [pscustomobject][ordered]@{
    kind = 'MINIPC_REVIEWED_TASK_ACK_V1'
    status = 'SUCCESS'
    task = 'file_access_bounded'
    mutation_scope = 'RESTRICTED'
    checked_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
    reviewed_git_sha = $sourceSha
    file_status = $state
    mode = $mode
    root_key = $key
    files = @($files)
    export_ready = [bool]$exportFile
    local_file = $exportFile
    local_filesystem_writes = [bool]$exportFile
    writes_outside_workspace = [bool]$exportFile # Runner temporary artifact staging only; never source modifications.
    service_or_task_mutations = $false
    new_permissions = $false
    active_runtime_release = $false
    trading_orders_permitted = $false
    secrets_used = $false
  } | ConvertTo-Json -Compress -Depth 6
}
try {
  Assert-RealDirectory $root
  if($mode -ceq 'SEARCH'){
    $queue=New-Object 'System.Collections.Generic.Queue[string]'
    $queue.Enqueue($root)
    $visited=0;$found=New-Object System.Collections.ArrayList
    while($queue.Count -gt 0 -and $visited -lt 1200 -and $found.Count -lt 20){
      Check-Time
      $directory=$queue.Dequeue()
      # Lazy enumeration: never materialize an unbounded directory before applying the 1200-entry cap.
      try {
        $items=[IO.DirectoryInfo]::new($directory).EnumerateFileSystemInfos()
        foreach($item in $items){
        Check-Time;$visited++;if($visited -gt 1200){break}
        if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){continue}
        if($item.PSIsContainer){
          if($directory.Substring($root.Length).Split('\').Count -lt 8){$queue.Enqueue($item.FullName)}
          continue
        }
        if($item.Name.IndexOf($selector,[StringComparison]::OrdinalIgnoreCase) -lt 0){continue}
        if(-not (Safe-Name $item.Name)){continue}
        if($item.Length -lt 0 -or $item.Length -gt 2097152){continue}
        $rel=$item.FullName.Substring($root.Length).TrimStart('\')
        $segments=$rel.Split('\')
        if(@($segments | Where-Object {-not (Safe-Name $_)}).Count -gt 0){continue}
        try {
          $verified=Assert-Path $rel
          $digest=(Get-FileHash -LiteralPath $verified.FullName -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
          [void]$found.Add([pscustomobject][ordered]@{relative_path=$rel;size=[long]$verified.Length;sha256=$digest})
        }catch{continue}
        if($found.Count -ge 20){break}
        }
      } catch [System.UnauthorizedAccessException] { continue }
        catch [System.IO.IOException] { continue }
    }
    $state=if($found.Count -eq 0){'NOT_FOUND'}elseif($queue.Count -gt 0 -or $visited -ge 1200){'PARTIAL_LIMIT'}else{'FOUND'}
    Result $state @($found.ToArray()) ''
  }else{
    # A separate authenticated EXPORT request binds one relative path to its previously observed SHA.
    $bytes=$selector.Replace('-','+').Replace('_','/')
    $bytes=$bytes+('='*((4-($bytes.Length%4))%4))
    $rel=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($bytes))
    if(-not $rel -or $rel -match '[^\x20-\x7e]' -or $rel -match '[^A-Za-z0-9_. \\-]'){throw 'FILE_ACCESS_DENIED:ENCODING'}
    $segments=$rel.Split('\')
    if(@($segments | Where-Object {-not (Safe-Name $_)}).Count -gt 0){throw 'FILE_ACCESS_DENIED:SENSITIVE_NAME'}
    $file=Assert-Path $rel
    if($file.Length -gt 65536 -or $file.Length -lt 1){throw 'FILE_ACCESS_DENIED:EXPORT_SIZE'}
    if([IO.Path]::GetExtension($file.Name).ToLowerInvariant() -cnotin @('.txt','.md','.csv','.json')){throw 'FILE_ACCESS_DENIED:EXPORT_TYPE'}
    $hash=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
    if($hash -cne $expected){throw 'FILE_HASH_MISMATCH'}
    $body=[IO.File]::ReadAllBytes($file.FullName)
    if($body.Length -ne $file.Length -or [BitConverter]::ToString(([Security.Cryptography.SHA256]::Create()).ComputeHash($body)).Replace('-','').ToLowerInvariant() -cne $expected){throw 'FILE_HASH_MISMATCH'}
    $text = [Text.UTF8Encoding]::new($false,$true)
    try{$decoded=$text.GetString($body)}catch{throw 'FILE_ACCESS_DENIED:BINARY'}
    if($decoded -match '(?i)(password|passwd|secret|api[_-]?key|token|authorization|bearer|private.key|BEGIN [A-Z ]*PRIVATE KEY|postgres(?:ql)?://|SUPABASE_|sk-[A-Za-z0-9]{10})'){throw 'FILE_ACCESS_DENIED:SENSITIVE_CONTENT'}
    $temp=[string]$env:RUNNER_TEMP
    if(-not $temp -or -not (Test-Path -LiteralPath $temp -PathType Container)){throw 'FILE_UNAVAILABLE:TEMP'}
    $dest=Join-Path $temp ('minipc-authorized-'+[guid]::NewGuid().ToString('N')+'.txt')
    [IO.File]::WriteAllBytes($dest,$body)
    if((Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash.ToLowerInvariant() -cne $expected){
      Remove-Item -LiteralPath $dest -Force -ErrorAction SilentlyContinue;throw 'FILE_HASH_MISMATCH'
    }
    Result 'EXPORT_STAGED' @([pscustomobject]@{relative_path=$rel;size=[long]$file.Length;sha256=$hash}) $dest
  }
}catch [System.UnauthorizedAccessException]{Result 'ACCESS_DENIED' @() ''}
 catch [System.Management.Automation.ItemNotFoundException]{Result 'NOT_FOUND' @() ''}
 catch {
   $msg=[string]$_.Exception.Message
   $state=if($msg.StartsWith('FILE_ACCESS_DENIED:')){'ACCESS_DENIED'}elseif($msg -ceq 'FILE_HASH_MISMATCH'){'HASH_MISMATCH'}elseif($msg.StartsWith('FILE_UNAVAILABLE:')){'UNAVAILABLE'}else{'UNAVAILABLE'}
   Result $state @() ''
}
