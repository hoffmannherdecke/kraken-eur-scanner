# Isolated verification. Parse operator bytes without executing device actions.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($PSVersionTable.PSEdition -ne 'Desktop' -or $PSVersionTable.PSVersion -lt [version]'5.1') {
    throw 'AP04_WINDOWS_POWERSHELL_51_REQUIRED'
}
$root = Join-Path (Split-Path $PSScriptRoot -Parent) 'tools/ap04-pr701'
foreach ($line in Get-Content -LiteralPath (Join-Path $root 'SHA256SUMS')) {
    if ($line -cnotmatch '^([a-f0-9]{64})  ([A-Za-z0-9.-]+)$') {
        throw 'AP04_MANIFEST_FORMAT'
    }
    $expected = $Matches[1]
    $path = Join-Path $root $Matches[2]
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ine $expected) {
        throw "AP04_SOURCE_HASH_DRIFT $path"
    }
    if ([IO.Path]::GetExtension($path) -ceq '.ps1') {
        $tokens = $null
        $errors = $null
        $null = [Management.Automation.Language.Parser]::ParseFile($path, [ref]$tokens, [ref]$errors)
        if (@($errors).Count) { throw "AP04_SOURCE_PARSE_HOLD $path" }
    }
}
$starter = [IO.File]::ReadAllText((Join-Path $root 'Start-PR701-Window.ps1'))
$sequence = [IO.File]::ReadAllText((Join-Path $root 'MiniPC-Sequence.ps1'))
$binder = [IO.File]::ReadAllText((Join-Path $root 'MiniPC-BindHandoff.ps1'))
if (-not $starter.Contains('-ExpectedFixedInputsSha256 $expectedFixedInputsSha256') -or
    -not $sequence.Contains('ExpectedFixedInputsSha256=$ExpectedFixedInputsSha256') -or
    -not $binder.Contains('--fixed-inputs $fixedPath --fixed-inputs-sha256 $fixedHash')) {
    throw 'AP04_FIXED_INPUTS_ARGUMENT_CHAIN_DRIFT'
}

$tmp = Join-Path ([IO.Path]::GetTempPath()) ('ap04-ci-' + [guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($tmp)
try {
    $fixed = Join-Path $tmp 'cutover-fixed-inputs.json'
    [IO.File]::WriteAllText($fixed, '{}')
    $plan = Join-Path $tmp 'plan.stop.json'
    [IO.File]::WriteAllText($plan, '{}')
    $missing = Join-Path $tmp 'missing.json'
    $output = Join-Path $tmp 'output'
    $python = (Get-Command python -CommandType Application | Select-Object -First 1).Source
    $errFile = Join-Path $tmp 'stderr.txt'
    try {
        $ErrorActionPreference = 'Continue'
        $null = & $python -I -B (Join-Path $root 'Bind-PostStop.py') $plan $missing $missing $missing $missing $output --fixed-inputs $fixed --fixed-inputs-sha256 ('0' * 64) 2> $errFile
    } finally { $ErrorActionPreference = 'Stop' }
    if ($LASTEXITCODE -eq 0 -or
        (Get-Content -LiteralPath $errFile -Raw) -cnotmatch 'PR701_FIXED_INPUT_DRIFT' -or
        (Test-Path -LiteralPath $output)) {
        throw 'AP04_PYTHON_BINDER_FAILED_TO_REJECT_WRONG_BYTES'
    }
    'AP04_PR701_PS51_BYTE_AND_ARGUMENT_CONTRACT_PASS'
}
finally {
    [IO.Directory]::Delete($tmp, $true)
}
