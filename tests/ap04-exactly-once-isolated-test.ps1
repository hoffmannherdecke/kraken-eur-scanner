# AP04 focused offline test. Does not call any release operator or GitHub.
[CmdletBinding()]param(
 [string]$CandidatePath='C:\Users\ADMIN\Downloads\AP04-GitHub-Dispatch-Handoff-EXACTLY-ONCE-REVIEW.ps1'
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version 2
$root=Join-Path $env:TEMP ('AP04-LATCH-ISOLATED-'+[guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($root)
try {
  $tokens=$null;$errors=$null
  [void][Management.Automation.Language.Parser]::ParseFile($CandidatePath,[ref]$tokens,[ref]$errors)
  if(@($errors).Count -ne 0){throw 'AP04_PATCH_PARSE_HOLD'}
  $ast=[Management.Automation.Language.Parser]::ParseFile($CandidatePath,[ref]$tokens,[ref]$errors)
  $functions=@($ast.FindAll({param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
    $node.Name -ceq 'New-AP04DispatchAttemptLatch'
  },$true))
  if($functions.Count -ne 1){throw 'AP04_EXACTLY_ONCE_FUNCTION_NOT_UNIQUE_HOLD'}
  $functionText=[string]$functions[0].Extent.Text
  foreach($required in @('[IO.FileMode]::CreateNew','Flush($true)','DISPATCH_ATTEMPT_ALREADY_PRESENT_OR_UNKNOWN_NO_RETRY')) {
    if(-not $functionText.Contains($required)){throw ('AP04_LATCH_SOURCE_MISSING:'+ $required)}
  }
  $gate=Join-Path $root 'go.signal'
  $worker={param($functionText,$gate,$root)
    $ErrorActionPreference='Stop'
    . ([scriptblock]::Create($functionText))
    while(-not [IO.File]::Exists($gate)){Start-Sleep -Milliseconds 10}
    $bytes=[Text.Encoding]::UTF8.GetBytes('{"retry_authorized":false}')
    try {
      $null=New-AP04DispatchAttemptLatch -Root $root -Series 'PAPER-V3-TEST' -Receipt $bytes
      'CREATED'
    } catch {
      if($_.Exception.Message -ceq 'DISPATCH_ATTEMPT_ALREADY_PRESENT_OR_UNKNOWN_NO_RETRY'){'DENIED'}
      else {throw}
    }
  }
  $a=Start-Job -ScriptBlock $worker -ArgumentList $functionText,$gate,$root
  $b=Start-Job -ScriptBlock $worker -ArgumentList $functionText,$gate,$root
  try {
    [IO.File]::WriteAllText($gate,'go')
    $finished=Wait-Job -Job @($a,$b) -Timeout 20
    if(@($finished).Count -ne 2){throw 'AP04_CONCURRENCY_TIMEOUT_HOLD'}
    $results=@()
    $results+=@(Receive-Job -Job $a)
    $results+=@(Receive-Job -Job $b)
    if(@($results|Where-Object {$_ -ceq 'CREATED'}).Count -ne 1 -or @($results|Where-Object {$_ -ceq 'DENIED'}).Count -ne 1){throw ('AP04_CONCURRENCY_HOLD:'+($results -join ','))}
    Write-Host 'AP04_ATOMIC_CONCURRENT_ONE_WINNER_PASS'
    # Persistence test: a new process attempt against the existing file must fail closed.
    $retry=Start-Job -ScriptBlock $worker -ArgumentList $functionText,$gate,$root
    try {
      $null=Wait-Job -Job $retry -Timeout 10
      $out=@(Receive-Job -Job $retry)
      if($out.Count -ne 1 -or $out[0] -cne 'DENIED'){throw 'AP04_RESTART_REPLAY_HOLD'}
      Write-Host 'AP04_PERSISTED_UNKNOWN_NO_RETRY_PASS'
    } finally {Remove-Job -Job $retry -Force -ErrorAction SilentlyContinue}
  } finally {Remove-Job -Job @($a,$b) -Force -ErrorAction SilentlyContinue}
  Write-Host 'AP04_EXACTLY_ONCE_ISOLATED_SOURCE_TEST_PASS'
  Write-Host 'NO_STAGE4_NO_STOP_NO_CAS_NO_WRITER'
} finally {
  # Only the disposable, randomly named test fixture is removed.
  Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}
