# MINI-PC existing file bridge: local selected-file handoff under interactive user identity.
# No service, runner changes, extra ACLs, network requests or background jobs.
[CmdletBinding(DefaultParameterSetName='Export')]
param(
  [Parameter(ParameterSetName='Install',Mandatory=$true)][switch]$Install,
  [Parameter(ParameterSetName='Export',Mandatory=$true)][string]$SourcePath,
  [Parameter(ParameterSetName='Export')][switch]$EvidenceBundle
)
$ErrorActionPreference='Stop'
# SendTo starts a short-lived PowerShell window; display fail-closed errors before exit.
trap {
  $message=[string]$_.Exception.Message
  if(-not $message.StartsWith('HANDOFF_HOLD:')){$message='HANDOFF_HOLD: Windows-Dateizugriff oder Export gescheitert'}
  try{(New-Object -ComObject WScript.Shell).Popup($message,0,'ChatGPT-Dateiexport',16) | Out-Null}catch{}
  Write-Error $message -ErrorAction Continue
  exit 1
}
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$principal=New-Object Security.Principal.WindowsPrincipal($identity)
if($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){
  throw 'HANDOFF_HOLD: Bitte als normal angemeldeter Windows-Benutzer, nicht als Administrator ausfuehren.'
}
$homeDir=[Environment]::GetFolderPath('UserProfile')
if([string]::IsNullOrWhiteSpace($homeDir)){throw 'HANDOFF_HOLD: USERPROFILE fehlt'}
$installDir=Join-Path $env:LOCALAPPDATA 'CryptoSupport\FileHandoff'
$installedScript=Join-Path $installDir 'local_file_handoff.ps1'

function Assert-NoReparse([string]$path) {
  $full=[IO.Path]::GetFullPath($path)
  $current=$full
  while($current){
    if(Test-Path -LiteralPath $current){
      $item=Get-Item -LiteralPath $current -Force -ErrorAction Stop
      if([bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)){
        throw 'HANDOFF_HOLD: Reparse-Point/Junction nicht erlaubt'
      }
    }
    $parent=[IO.Path]::GetDirectoryName($current)
    if(!$parent -or $parent -eq $current){break}
    $current=$parent
  }
}
function Assert-SafeFileName([string]$name) {
  if($name -notmatch '^[A-Za-z0-9][A-Za-z0-9_. -]{0,99}$' -or
     $name -match '(?i)(secret|password|passwd|token|credential|private|\.env|\.key|\.pem|\.pfx|\.p12|id_rsa|cert|auth|apikey|api.key|wallet|seed)' -or
     $name -ieq 'origin-sha256.json'){
    throw 'HANDOFF_HOLD: Dateiname gesperrt'
  }
}
function Assert-SafeContent([byte[]]$bytes) {
  if($bytes.Length -lt 1 -or $bytes.Length -gt 2097152){
    throw 'HANDOFF_HOLD: Nur Dateien von 1 Byte bis 2 MiB'
  }
  $utf8=[Text.UTF8Encoding]::new($false,$true)
  try{$decoded=$utf8.GetString($bytes)}catch{throw 'HANDOFF_HOLD: Nur gueltiger UTF-8-Text'}
  if($decoded -match '(?i)(password|passwd|secret|api[_-]?key|token|authorization|bearer|private.key|BEGIN [A-Z ]*PRIVATE KEY|postgres(?:ql)?://|SUPABASE_|sk-[A-Za-z0-9]{10})'){
    throw 'HANDOFF_HOLD: Moegliche Zugangsdaten oder vertrauliche Inhalte'
  }
  if($decoded.IndexOf([char]0) -ge 0){throw 'HANDOFF_HOLD: Binaerinhalt gesperrt'}
}
if($Install){
  if(-not $env:LOCALAPPDATA -or -not $env:APPDATA){throw 'HANDOFF_HOLD: Benutzerprofil unvollstaendig'}
  Assert-NoReparse $installDir
  [void][IO.Directory]::CreateDirectory($installDir)
  if((Get-Item -LiteralPath $MyInvocation.MyCommand.Path).FullName -ine $installedScript){
    [IO.File]::Copy($MyInvocation.MyCommand.Path,$installedScript,$true)
  }
  $sourceHash=(Get-FileHash -LiteralPath $MyInvocation.MyCommand.Path -Algorithm SHA256).Hash
  $copyHash=(Get-FileHash -LiteralPath $installedScript -Algorithm SHA256).Hash
  if($sourceHash -cne $copyHash){throw 'HANDOFF_HOLD: Installationskopie unterscheidet sich'}
  $sendTo=Join-Path $env:APPDATA 'Microsoft\Windows\SendTo'
  Assert-NoReparse $sendTo
  if(-not (Test-Path -LiteralPath $sendTo -PathType Container)){throw 'HANDOFF_HOLD: SendTo nicht vorhanden'}
  $shortcut=Join-Path $sendTo 'ChatGPT - gepruefter Dateiexport.lnk'
  $shell=New-Object -ComObject WScript.Shell
  $link=$shell.CreateShortcut($shortcut)
  $link.TargetPath=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
  # Explorer SendTo appends the selected file to shortcut arguments automatically.
  $link.Arguments='-NoProfile -ExecutionPolicy Bypass -File "'+$installedScript+'" -SourcePath'
  $link.WorkingDirectory=$homeDir
  $link.Description='Ausgewaehlte Datei unter Benutzerrechten sicher nach Downloads\ChatGPT-Uebergabe exportieren'
  $link.Save()
  if(-not(Test-Path -LiteralPath $shortcut -PathType Leaf)){throw 'HANDOFF_HOLD: SendTo-Verknuepfung fehlt'}
  $bundleShortcut=Join-Path $sendTo 'ChatGPT - signierte Nachweise.lnk'
  $bundleLink=$shell.CreateShortcut($bundleShortcut)
  $bundleLink.TargetPath=$link.TargetPath
  $bundleLink.Arguments='-NoProfile -ExecutionPolicy Bypass -File "'+$installedScript+'" -EvidenceBundle -SourcePath'
  $bundleLink.WorkingDirectory=$homeDir
  $bundleLink.Description='Signierte Originalnachweise und SHA256-Manifest aus einem ausgewaehlten Ordner uebergeben'
  $bundleLink.Save()
  if(-not(Test-Path -LiteralPath $bundleShortcut -PathType Leaf)){throw 'HANDOFF_HOLD: Nachweis-Verknuepfung fehlt'}
  Write-Output 'MINIPC_USER_HANDOFF_INSTALLED'
  Write-Output ('SCRIPT_SHA256='+$copyHash.ToLowerInvariant())
  Write-Output ('SENDTO='+$shortcut)
  return
}

# EVIDENCE BUNDLE: explicit file or selected directory with bounded depth, no
# implicit traversal outside selection, private keys, network upload or signing.
function Assert-EvidenceName([string]$name) {
  if($name -notmatch '^[A-Za-z0-9][A-Za-z0-9_. -]{0,119}$' -or
     $name -match '(?i)(^\.|(^|[_. -])(secret|password|passwd|token|credential|apikey|wallet|seed|privatekey|id_rsa)([_. -]|$)|\.env|\.key|\.pem|\.pfx|\.p12|\.kdbx|\.asc)' -or
     $name -ieq 'evidence-manifest-sha256.json'){
    throw 'HANDOFF_HOLD: Nachweisdateiname gesperrt'
  }
}
function Get-Sha256Bytes([byte[]]$content) {
  $hash=[Security.Cryptography.SHA256]::Create()
  try {return ([BitConverter]::ToString($hash.ComputeHash($content))).Replace('-','').ToLowerInvariant()}
  finally {$hash.Dispose()}
}
function Export-EvidenceBundle([string]$selected) {
  $source=[IO.Path]::GetFullPath($selected)
  Assert-NoReparse $source
  $item=Get-Item -LiteralPath $source -Force -ErrorAction Stop
  $isFolder=[bool]$item.PSIsContainer
  $root=if($isFolder){$source}else{[IO.Path]::GetDirectoryName($source)}
  $candidates=New-Object 'System.Collections.Generic.List[object]'
  if($isFolder) {
    # Explicitly selected folder, maximum two descendant levels and 80 entries.
    $pending=New-Object 'System.Collections.Generic.Queue[object]'
    $pending.Enqueue([pscustomobject]@{path=$source;depth=0})
    $visited=0
    while($pending.Count -gt 0){
      $node=$pending.Dequeue()
      Assert-NoReparse $node.path
      foreach($child in [IO.DirectoryInfo]::new($node.path).EnumerateFileSystemInfos()){
        $visited++
        if($visited -gt 120){throw 'HANDOFF_HOLD: Nachweisordner zu viele Eintraege'}
        if($child.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'HANDOFF_HOLD: Nachweis-Reparse gesperrt'}
        Assert-EvidenceName $child.Name
        if($child -is [IO.DirectoryInfo]){
          if($node.depth -ge 2){throw 'HANDOFF_HOLD: Nachweisordner zu tief'}
          $pending.Enqueue([pscustomobject]@{path=$child.FullName;depth=$node.depth+1})
        }else{$candidates.Add($child)}
      }
    }
  }else{$candidates.Add($item)}
  if($candidates.Count -lt 1 -or $candidates.Count -gt 80){throw 'HANDOFF_HOLD: Nachweisdateienanzahl unzulaessig'}

  $textExtensions=@('.json','.txt','.md','.csv','.log','.xml','.yml','.yaml','.sha256','.sha','.manifest','.ini','.cfg','.sql')
  $signatureExtensions=@('.p7s','.p7m','.cms','.sig','.der','.cer','.crt')
  $supportExtensions=@('.pdf')
  $records=New-Object 'System.Collections.Generic.List[object]'
  $checked=New-Object 'System.Collections.Generic.List[object]'
  $total=0L
  foreach($candidate in $candidates){
    Assert-NoReparse $candidate.FullName
    Assert-EvidenceName $candidate.Name
    $relative=$candidate.FullName.Substring($root.TrimEnd('\').Length).TrimStart('\')
    foreach($segment in $relative.Split('\')){Assert-EvidenceName $segment}
    $extension=[IO.Path]::GetExtension($candidate.Name).ToLowerInvariant()
    if($extension -cnotin ($textExtensions+$signatureExtensions+$supportExtensions)){
      throw 'HANDOFF_HOLD: Nachweis-Dateityp unzulaessig'
    }
    if($candidate.Length -lt 1 -or $candidate.Length -gt 8388608){
      throw 'HANDOFF_HOLD: Nachweisdatei ueber 8 MiB'
    }
    $total += $candidate.Length
    if($total -gt 33554432){throw 'HANDOFF_HOLD: Nachweispaket ueber 32 MiB'}
    $before=(Get-FileHash -LiteralPath $candidate.FullName -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
    $bytes=[IO.File]::ReadAllBytes($candidate.FullName)
    if($bytes.Length -ne $candidate.Length -or (Get-Sha256Bytes $bytes) -cne $before){
      throw 'HANDOFF_HOLD: Nachweisdatei waehrend Lesen veraendert'
    }
    if($extension -cin $textExtensions) {
      # Fail closed on clearly credential-bearing text; no claim of complete PII scanning.
      $utf8=[Text.UTF8Encoding]::new($false,$true)
      try{$decoded=$utf8.GetString($bytes)}catch{throw 'HANDOFF_HOLD: Nachweistext nicht UTF-8'}
      if($decoded.IndexOf([char]0) -ge 0 -or
         $decoded -match '(?i)(password\s*[:=]|passwd\s*[:=]|secret\s*[:=]|api[_-]?key\s*[:=]|bearer\s+[a-z0-9._-]+|BEGIN [A-Z ]*PRIVATE KEY|postgres(?:ql)?://|SUPABASE_SERVICE_ROLE_KEY|sk-[A-Za-z0-9]{10})'){
        throw 'HANDOFF_HOLD: Vertrauliche Nachweisdaten erkannt'
      }
    }elseif($extension -cin $signatureExtensions) {
      # Do not sign or assert CMS validity. Allow only signed/certificate-shaped
      # binary files; reject private-key containers by extension/name above.
      if($bytes.Length -gt 8388608){throw 'HANDOFF_HOLD: Signatur zu gross'}
    }
    $after=(Get-FileHash -LiteralPath $candidate.FullName -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
    if($after -cne $before){throw 'HANDOFF_HOLD: Nachweisdatei geaendert'}
    $checked.Add([pscustomobject]@{relative_path=$relative;bytes=$bytes;sha256=$before;size=[long]$bytes.Length;kind=$(if($extension -cin $signatureExtensions){'SIGNATURE_OR_CERTIFICATE'}elseif($extension -cin $supportExtensions){'SUPPORT_BINARY'}else{'TEXT_EVIDENCE'})})
  }
  $downloads=Join-Path $homeDir 'Downloads'
  Assert-NoReparse $downloads
  if(-not(Test-Path -LiteralPath $downloads -PathType Container)){throw 'HANDOFF_HOLD: Downloads-Ordner fehlt'}
  $handoff=Join-Path $downloads 'ChatGPT-Uebergabe'
  Assert-NoReparse $handoff
  [void][IO.Directory]::CreateDirectory($handoff)
  $folder=Join-Path $handoff ('signed-evidence-'+[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')+'-'+[guid]::NewGuid().ToString('N'))
  [void][IO.Directory]::CreateDirectory($folder)
  try {
    foreach($entry in $checked){
      $dest=Join-Path $folder $entry.relative_path
      $parent=[IO.Path]::GetDirectoryName($dest)
      [void][IO.Directory]::CreateDirectory($parent)
      [IO.File]::WriteAllBytes($dest,$entry.bytes)
      if((Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash.ToLowerInvariant() -cne $entry.sha256){
        throw 'HANDOFF_HOLD: Nachweiskopie SHA256 abweichend'
      }
      $records.Add([pscustomobject][ordered]@{relative_path=$entry.relative_path;sha256=$entry.sha256;size_bytes=$entry.size;type=$entry.kind})
    }
    $manifest=[pscustomobject][ordered]@{
      kind='MINIPC_SIGNED_EVIDENCE_HANDOFF_V1'
      source_root=$source
      source_identity=$identity.Name
      exported_at_utc=[DateTimeOffset]::UtcNow.ToString('o')
      entry_count=$records.Count
      total_bytes=$total
      files=@($records.ToArray())
      original_files_modified=$false
      signatures_verified=$false
      authenticity_requires_existing_independent_verifier=$true
      user_review_required=$true
    }
    $manifestFile=Join-Path $folder 'evidence-manifest-sha256.json'
    [IO.File]::WriteAllText($manifestFile,($manifest|ConvertTo-Json -Depth 7),[Text.UTF8Encoding]::new($false))
    # Convenience archive of the already checked copies + manifest. It does not
    # add authority and is never auto-uploaded or sent to GitHub.
    Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction Stop
    $archivePath=Join-Path $handoff ('signed-evidence-'+[guid]::NewGuid().ToString('N')+'.zip')
    [IO.Compression.ZipFile]::CreateFromDirectory($folder,$archivePath,[IO.Compression.CompressionLevel]::Optimal,$false)
    if((Get-Item -LiteralPath $archivePath -ErrorAction Stop).Length -lt 1){
      throw 'HANDOFF_HOLD: Nachweis-ZIP ist leer'
    }
    [IO.File]::Copy($archivePath,(Join-Path $folder 'UPLOAD_PACKAGE.zip'))
    [IO.File]::Delete($archivePath)
    Write-Output 'MINIPC_SIGNED_EVIDENCE_HANDOFF_EXPORT_PASS'
    Write-Output ('FILES='+$records.Count)
    Write-Output ('FOLDER='+$folder)
    Write-Output 'Manifest und Originalkopien pruefen. CMS-Signaturen sind NICHT kryptografisch verifiziert.'
    & explorer.exe $folder
  }catch{
    if(Test-Path -LiteralPath $folder -PathType Container){
      [IO.Directory]::Delete($folder,$true)
    }
    throw
  }
}
if($EvidenceBundle){
  if(-not(Test-Path -LiteralPath $SourcePath)){throw 'HANDOFF_HOLD: Nachweisdatei oder Ordner fehlt'}
  Export-EvidenceBundle $SourcePath
  return
}

# The normal file-selection entrypoint. No admin, no new service and no source ACL modifications.
if(-not(Test-Path -LiteralPath $SourcePath -PathType Leaf)){
  throw 'HANDOFF_HOLD: Quelldatei nicht gefunden oder nicht lesbar'
}
$full=[IO.Path]::GetFullPath($SourcePath)
Assert-NoReparse $full
$file=Get-Item -LiteralPath $full -Force -ErrorAction Stop
if($file.PSIsContainer){throw 'HANDOFF_HOLD: Nur einzelne Dateien'}
Assert-SafeFileName $file.Name
$ext=[IO.Path]::GetExtension($file.Name).ToLowerInvariant()
if($ext -cnotin @('.txt','.md','.csv','.json','.log','.xml','.yml','.yaml')){
  throw 'HANDOFF_HOLD: Dateityp nicht fuer Direktexport zugelassen'
}
if($file.Length -lt 1 -or $file.Length -gt 2097152){
  throw 'HANDOFF_HOLD: Dateigroesse nicht zugelassen'
}
$shaBefore=(Get-FileHash -LiteralPath $full -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
$bytes=[IO.File]::ReadAllBytes($full)
Assert-SafeContent $bytes
$shaBytes=([BitConverter]::ToString(([Security.Cryptography.SHA256]::Create()).ComputeHash($bytes))).Replace('-','').ToLowerInvariant()
$shaAfter=(Get-FileHash -LiteralPath $full -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
if($shaBefore -cne $shaBytes -or $shaAfter -cne $shaBytes -or $file.Length -ne $bytes.Length){
  throw 'HANDOFF_HOLD: Datei waehrend der Pruefung veraendert'
}
$downloads=Join-Path $homeDir 'Downloads'
Assert-NoReparse $downloads
if(-not(Test-Path -LiteralPath $downloads -PathType Container)){throw 'HANDOFF_HOLD: Downloads-Ordner fehlt'}
$handoff=Join-Path $downloads 'ChatGPT-Uebergabe'
Assert-NoReparse $handoff
[void][IO.Directory]::CreateDirectory($handoff)
$folder=Join-Path $handoff (([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ'))+'-'+[guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($folder)
$dest=Join-Path $folder $file.Name
$receiptFile=Join-Path $folder 'origin-sha256.json'
try{
  [IO.File]::WriteAllBytes($dest,$bytes)
  if((Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash.ToLowerInvariant() -cne $shaBytes){
    throw 'HANDOFF_HOLD: Kopie und Quelle sind nicht byteidentisch'
  }
  $receipt=[pscustomobject][ordered]@{
    kind='MINIPC_FILE_PROVENANCE_V1'
    source_path=$full
    source_identity=$identity.Name
    filename=$file.Name
    sha256=$shaBytes
    size_bytes=[long]$bytes.Length
    exported_at_utc=[DateTimeOffset]::UtcNow.ToString('o')
    original_modified=$false
    sensitive_content_screen='BOUNDED_TEXT_PATTERN_V1'
    user_review_required=$true
  }
  [IO.File]::WriteAllText($receiptFile,($receipt|ConvertTo-Json -Depth 4),[Text.UTF8Encoding]::new($false))
  Write-Output 'MINIPC_USER_HANDOFF_EXPORT_PASS'
  Write-Output ('FOLDER='+$folder)
  Write-Output ('SHA256='+$shaBytes)
  Write-Output 'Vor dem ChatGPT-Upload beide Dateien noch einmal inhaltlich pruefen.'
  & explorer.exe $folder
}catch{
  if(Test-Path -LiteralPath $dest -PathType Leaf){[IO.File]::Delete($dest)}
  if(Test-Path -LiteralPath $receiptFile -PathType Leaf){[IO.File]::Delete($receiptFile)}
  throw
}
