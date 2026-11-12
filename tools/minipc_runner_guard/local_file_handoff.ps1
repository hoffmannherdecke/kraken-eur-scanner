# MINI-PC existing file bridge: local selected-file handoff under interactive user identity.
# No service, runner changes, extra ACLs, network requests or background jobs.
[CmdletBinding(DefaultParameterSetName='Export')]
param(
  [Parameter(ParameterSetName='Install',Mandatory=$true)][switch]$Install,
  [Parameter(ParameterSetName='Export',Mandatory=$true)][string]$SourcePath
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
  Write-Output 'MINIPC_USER_HANDOFF_INSTALLED'
  Write-Output ('SCRIPT_SHA256='+$copyHash.ToLowerInvariant())
  Write-Output ('SENDTO='+$shortcut)
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
