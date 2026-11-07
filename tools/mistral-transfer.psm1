# Source-only, project-wide Mistral_450 transport contract.
# No SMB credential changes, drive mappings, task mutations, or release authorization.
Set-StrictMode -Version Latest

function Get-MistralTransferRoot {
 [CmdletBinding()]
 param([Parameter(Mandatory=$true)][ValidateSet('MiniPc','Notebook')][string]$Role,
       [string]$RelativeDirectory='')
 $root=if($Role -ceq 'MiniPc'){'D:\'}else{'\\192.168.178.179\Mistral_450'}
 if($RelativeDirectory) {
  if([IO.Path]::IsPathRooted($RelativeDirectory) -or
     $RelativeDirectory -match '(^|[\\/])\.\.([\\/]|$)' -or
     $RelativeDirectory -match '(^|[\\/])\.([\\/]|$)' -or
     $RelativeDirectory -match '[:*?"<>|]' -or
     $RelativeDirectory.StartsWith('\\') -or $RelativeDirectory.StartsWith('/')){
   throw 'MISTRAL_INVALID_RELATIVE_DIRECTORY'
  }
  $root=Join-Path $root $RelativeDirectory
 }
 return $root
}

function Assert-MistralTransferAccess {
 [CmdletBinding()]
 param([Parameter(Mandatory=$true)][ValidateSet('MiniPc','Notebook')][string]$Role,
       [string]$RelativeDirectory='')
 $root=Get-MistralTransferRoot -Role $Role -RelativeDirectory $RelativeDirectory
 if($Role -ceq 'MiniPc') {
  if($env:COMPUTERNAME -cne 'MINI-PC'){throw 'MISTRAL_WRONG_DEVICE_MINIPC'}
 } elseif($env:COMPUTERNAME -ceq 'MINI-PC'){
  throw 'MISTRAL_WRONG_DEVICE_NOTEBOOK'
 }
 try {
  if(-not (Test-Path -LiteralPath $root -PathType Container -ErrorAction Stop)){
   throw 'MISTRAL_DIRECTORY_NOT_ACCESSIBLE'
  }
 } catch {
  if($_.Exception.Message -ceq 'MISTRAL_DIRECTORY_NOT_ACCESSIBLE'){throw}
  throw ('MISTRAL_DIRECTORY_ACCESS_FAILED: '+$_.Exception.GetType().Name)
 }
 return $root
}

function Copy-MistralVerifiedFile {
 [CmdletBinding()]
 param([Parameter(Mandatory=$true)][ValidateSet('MiniPc','Notebook')][string]$Role,
       [Parameter(Mandatory=$true)][string]$RelativeDirectory,
       [Parameter(Mandatory=$true)][string]$SourceFile,
       [Parameter(Mandatory=$true)][string]$DestinationName)
 # Input is an explicitly designated original file; no directory scans or overwrite.
 if($DestinationName -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$' -or
    $DestinationName -in @('.','..')){throw 'MISTRAL_INVALID_DESTINATION_NAME'}
 $root=Assert-MistralTransferAccess -Role $Role -RelativeDirectory $RelativeDirectory
 $item=Get-Item -LiteralPath $SourceFile -ErrorAction Stop
 if($item.PSIsContainer){throw 'MISTRAL_SOURCE_NOT_FILE'}
 $target=Join-Path $root $DestinationName
 if(Test-Path -LiteralPath $target){throw 'MISTRAL_NO_OVERWRITE'}
 $bytes=[IO.File]::ReadAllBytes($item.FullName)
 $sourceHash=[Security.Cryptography.SHA256]::HashData($bytes)
 $stream=[IO.File]::Open($target,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
 try {$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}
 finally {$stream.Dispose()}
 $readback=[IO.File]::ReadAllBytes($target)
 $hash=[Security.Cryptography.SHA256]::HashData($readback)
 if(-not [Linq.Enumerable]::SequenceEqual[byte]($sourceHash,$hash)){
  throw 'MISTRAL_TRANSFER_SHA256_MISMATCH'
 }
 [pscustomobject]@{
  kind='MISTRAL_VERIFIED_FILE_TRANSFER_V1'
  role=$Role; relative_directory=$RelativeDirectory; file=$DestinationName
  sha256=([Convert]::ToHexString($hash)).ToLowerInvariant()
  bytes=$readback.Length
  release_authorized=$false
 }
}
Export-ModuleMember -Function Get-MistralTransferRoot,Assert-MistralTransferAccess,Copy-MistralVerifiedFile
