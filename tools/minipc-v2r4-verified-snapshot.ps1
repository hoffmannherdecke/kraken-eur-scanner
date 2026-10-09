param(
 [Parameter(Mandatory=$true)][string]$SourceDirectory,
 [Parameter(Mandatory=$true)][string]$ArchivePath
)
# One-shot, inclusive and verified old Paper/H3 archive builder.
# NEVER mutate source bytes. Handles hidden and system files which
# Compress-Archive silently ignores.
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$root=(Get-Item -LiteralPath $SourceDirectory -ErrorAction Stop).FullName.TrimEnd([char]'\',[char]'/')
if(-not(Test-Path -LiteralPath $root -PathType Container)){throw 'Backup source is not a directory'}
if(Test-Path -LiteralPath $ArchivePath){throw 'Refusing to overwrite an existing old-series archive'}
$files=@(Get-ChildItem -LiteralPath $root -Recurse -File -Force -ErrorAction Stop | Sort-Object FullName)
if($files.Count -eq 0){throw 'Refusing to back up an empty old-series directory'}
# No links to locations outside of the frozen source snapshot.
$links=@(Get-ChildItem -LiteralPath $root -Recurse -Force -ErrorAction Stop | Where-Object {
  ([int]$_.Attributes -band [int][IO.FileAttributes]::ReparsePoint) -ne 0
})
if($links.Count -gt 0){throw 'Snapshot input contains an unsupported reparse point'}
$archive=[IO.Compression.ZipFile]::Open($ArchivePath,[IO.Compression.ZipArchiveMode]::Create)
try {
 foreach($f in $files){
   $relative=$f.FullName.Substring($root.Length).TrimStart([char]'\',[char]'/').Replace('\','/')
   if(-not $relative -or $relative.StartsWith('../') -or $relative.StartsWith('/')){throw 'Invalid snapshot relative path'}
   $null=[IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
     $archive,$f.FullName,$relative,[IO.Compression.CompressionLevel]::Optimal)
 }
}finally{$archive.Dispose()}

# Check *every* source file, including hidden ones, inside the actual ZIP.
$archive=[IO.Compression.ZipFile]::OpenRead($ArchivePath)
try {
 $entries=@($archive.Entries|Where-Object{-not [string]::IsNullOrEmpty($_.Name)})
 if($entries.Count -ne $files.Count){throw "Snapshot file count mismatch: expected=$($files.Count) actual=$($entries.Count)"}
 $map=@{}
 foreach($e in $entries){
   if($map.ContainsKey($e.FullName)){throw "Duplicate snapshot entry: $($e.FullName)"}
   $map[$e.FullName]=$e
 }
 $hash=[Security.Cryptography.SHA256]::Create()
 try{
   foreach($f in $files){
     $relative=$f.FullName.Substring($root.Length).TrimStart([char]'\',[char]'/').Replace('\','/')
     if(-not $map.ContainsKey($relative)){throw "Snapshot file missing: $relative"}
     $entry=$map[$relative]
     if($entry.Length -ne $f.Length){throw "Snapshot size mismatch: $relative"}
     $stream=$entry.Open()
     try{$inArchive=([BitConverter]::ToString($hash.ComputeHash($stream))).Replace('-','').ToLowerInvariant()}
     finally{$stream.Dispose()}
     $onDisk=(Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
     if($inArchive -cne $onDisk){throw "Snapshot contents differ: $relative"}
   }
 }finally{$hash.Dispose()}
}finally{$archive.Dispose()}
[pscustomobject]@{
 status='VERIFIED_ALL_SOURCE_FILES'
 file_count=$files.Count
 archive_sha256=(Get-FileHash -LiteralPath $ArchivePath -Algorithm SHA256).Hash.ToLowerInvariant()
}|ConvertTo-Json -Compress
