# Offline source regression only. No existing SMB account or host is touched.
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
Import-Module (Join-Path $PSScriptRoot '../tools/mistral-transfer.psm1') -Force
function Must([bool]$ok,[string]$code){if(-not $ok){throw "MISTRAL_TEST_FAILED_$code"}}
function Deny([scriptblock]$f,[string]$code){$did=$false;try{& $f|Out-Null}catch{$did=$true};Must $did $code}
Must ((Get-MistralTransferRoot MiniPc) -ceq 'D:\') 'MINIPC_LOCAL_PATH'
Must ((Get-MistralTransferRoot Notebook) -ceq '\\192.168.178.179\Mistral_450') 'NOTEBOOK_UNC_IP'
Must ((Get-MistralTransferRoot Notebook 'V3-Cloud-Release') -ceq '\\192.168.178.179\Mistral_450\V3-Cloud-Release') 'FIXED_HANDOFF'
foreach($bad in @('..\etc','./other','M:\foo','\host\share','/abs','part:bad')) {
 Deny { Get-MistralTransferRoot Notebook $bad } ('REJECT_'+$bad)
}
Deny { Copy-MistralVerifiedFile Notebook 'V3-Cloud-Release' 'missing.file' '../evil' } 'BAD_LEAF'
# Regression guard for generated scripts: no mapped drive, hostname UNC, or volume-label equivalence.
$module=Get-Content (Join-Path $PSScriptRoot '../tools/mistral-transfer.psm1') -Raw
Must (-not $module.Contains('Get-Volume')) 'NO_VOLUME_LABEL_ASSUMPTION'
Must (-not $module.Contains('New-PSDrive')) 'NO_DRIVE_MAPPING'
Write-Host 'MISTRAL_OFFLINE_CONTRACT_PASS'
