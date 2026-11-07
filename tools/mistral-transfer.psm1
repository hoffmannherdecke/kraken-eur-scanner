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
  # String composition is intentional: offline CI runs on Linux without a D: drive.
  $root=$root.TrimEnd('\\')+'\\'+$RelativeDirectory.TrimStart('\\')
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
 $sourceHash=(Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
 $sourceStream=[IO.File]::Open($item.FullName,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
 try {
  $targetStream=[IO.File]::Open($target,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
  try {$sourceStream.CopyTo($targetStream);$targetStream.Flush($true)}
  finally {$targetStream.Dispose()}
 } finally {$sourceStream.Dispose()}
 $targetHash=(Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
 if($sourceHash -cne $targetHash){throw 'MISTRAL_TRANSFER_SHA256_MISMATCH'}
 [pscustomobject]@{
  kind='MISTRAL_VERIFIED_FILE_TRANSFER_V1'
  role=$Role; relative_directory=$RelativeDirectory; file=$DestinationName
  sha256=$targetHash
  bytes=(Get-Item -LiteralPath $target).Length
  release_authorized=$false
 }
}
Export-ModuleMember -Function Get-MistralTransferRoot,Assert-MistralTransferAccess,Copy-MistralVerifiedFile
