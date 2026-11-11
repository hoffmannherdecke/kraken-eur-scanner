# AP04 source-only integration gate. Never invoke the operator or any release path.
# This fixture's exact bytes are the independently admitted MiniPC-Phase.ps1.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$path = Join-Path $PSScriptRoot 'fixtures/ap04-lockfix/MiniPC-Phase.ps1'
$expected = '160e02cf552da9a1f69cd5dac45362eba10eb705fd0b66ee9abb5484d632b9ea'
$bytes = [IO.File]::ReadAllBytes($path)
$actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -cne $expected -or $bytes.Length -ne 7347 -or
    $bytes[0] -ne 239 -or $bytes[1] -ne 187 -or $bytes[2] -ne 191) {
    throw 'AP04_LOCKFIX_SOURCE_PIN_OR_BOM_HOLD'
}
$text = [Text.Encoding]::UTF8.GetString($bytes,3,$bytes.Length-3)
$tokens = $null
$errors = $null
$ast = [Management.Automation.Language.Parser]::ParseInput($text,[ref]$tokens,[ref]$errors)
if (@($errors).Count -gt 0) { throw 'AP04_LOCKFIX_SYNTAX_HOLD' }
$functions = @($ast.FindAll({
    param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
    $node.Name -ceq 'Read-SharedTransferText'
},$true))
if ($functions.Count -ne 1) { throw 'AP04_LOCKFIX_RETRY_FUNCTION_HOLD' }
$readTransfer = @($ast.FindAll({
    param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
    $node.Name -ceq 'Read-Transfer'
},$true))
if ($readTransfer.Count -ne 1) { throw 'AP04_LOCKFIX_CONSUMER_COUNT_HOLD' }
$readText = [string]$functions[0].Extent.Text
$consumer = [string]$readTransfer[0].Extent.Text
foreach ($s in @(
    'catch [System.IO.IOException]',
    'HResult -band 0xFFFF',
    '$win32 -ne 32 -or $attempt -ge 2',
    '[Threading.Thread]::Sleep(75)',
    'throw'
)) {
    if (-not $readText.Contains($s)) { throw ('AP04_LOCKFIX_RETRY_SEMANTICS_HOLD '+$s) }
}
if (-not $consumer.Contains('Read-SharedTransferText -Path $full') -or
    -not $consumer.Contains('MISTRAL_EXACT_TRANSFER_PATH_HOLD') -or
    -not $consumer.Contains('MISTRAL_TRANSFER_BINDING_HOLD')) {
    throw 'AP04_LOCKFIX_CONSUMER_GUARD_HOLD'
}
foreach ($s in @('ORIGINAL_MINIPC_REQUIRED','EXPLICIT_LOCAL_EXECUTION_REQUIRED',
    'ORIGINAL_PLAN_SCOPE_HOLD','OPERATOR_SOURCE_HOLD','FIXED_HASH_HOLD',
    'LOCAL_WINDOW_PATH_HOLD','UNEXPECTED_CREDENTIAL')) {
    if (-not $text.Contains($s)) { throw ('AP04_LOCKFIX_AUTHORITY_GUARD_HOLD '+$s) }
}
# Execute ONLY the extracted pure read function against isolated synthetic files.
. ([scriptblock]::Create($readText))
$temp = Join-Path ([IO.Path]::GetTempPath()) ('AP04-LOCKFIX-CI-'+[guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($temp)
try {
    $sample = Join-Path $temp 'synthetic.txt'
    [IO.File]::WriteAllText($sample,'SYNTHETIC_ONLY')
    if ((Read-SharedTransferText $sample) -cne 'SYNTHETIC_ONLY') {
        throw 'AP04_LOCKFIX_NORMAL_READ_HOLD'
    }
    try {
        $null = Read-SharedTransferText (Join-Path $temp 'absent.txt')
        throw 'AP04_LOCKFIX_MISSING_FILE_NOT_REJECTED'
    } catch [System.IO.FileNotFoundException] {
        # Non-sharing failures propagate; no fallback or invented payload.
    }
} finally {
    Remove-Item -LiteralPath $temp -Recurse -Force
}
Write-Output 'AP04_LOCKFIX_PINNED_SOURCE_CI_PASS'
Write-Output 'NO_STAGE4_NO_STOP_NO_CAS_NO_WRITER_NO_INSTALL'
