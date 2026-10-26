# CI only / disposable temp dir: tests the exact Windows Notebook helper without CAS.
$ErrorActionPreference='Stop'
$root=Join-Path ([IO.Path]::GetTempPath()) ('v3-notebook-test-'+[guid]::NewGuid().ToString('N'))
$archive=Join-Path $root 'NotebookNachweise'
$tool=Join-Path (Split-Path -Parent $PSScriptRoot) 'tools/v3-notebook-onetime-paper-witness-INACTIVE.ps1'
function Assert-Hold([scriptblock]$body,[string]$name) {
  $rejected=$false
  try { & $body | Out-Null } catch { $rejected=$true }
  if (-not $rejected) { throw ('FAIL_NOTEBOOK_EXPECTED_HOLD_'+$name) }
}
function Write-Snapshot([string]$dest,[int]$old,[int]$new,[string]$time,
                        [string]$project='nlgzjmqgwueojlyqmoru') {
  $obj=[ordered]@{
    kind='V3_PAPER_NOTEBOOK_SNAPSHOT_V1'
    project_ref=$project
    observed_at_utc=$time
    active_total=1
    active_v2r4=$old
    active_v3=$new
    audit_intent_count=0
    cas_function_present=$false
  }
  [IO.File]::WriteAllText($dest,($obj | ConvertTo-Json -Compress),
    [Text.Encoding]::UTF8)
}
try {
  [void][IO.Directory]::CreateDirectory($root)
  $pre=Join-Path $root 'vorher-quell.json'
  $post=Join-Path $root 'nachher-quell.json'
  $bad=Join-Path $root 'fremd-quell.json'
  Write-Snapshot $pre 1 0 '2026-10-26T19:00:00Z'
  Write-Snapshot $post 0 1 '2026-10-26T19:01:00Z'
  Write-Snapshot $bad 1 0 '2026-10-26T19:00:00Z' 'wrongproject'
  Assert-Hold { & $tool -Aktion Pruefen -Ablage $archive } 'NO_ARCHIVE'
  Assert-Hold { & $tool -Aktion Vorher -Datei $bad -Ablage $archive } 'PROJECT'
  $before=(& $tool -Aktion Vorher -Datei $pre -Ablage $archive) | ConvertFrom-Json
  if ($before.ergebnis -cne 'GESPEICHERT_VORHER' -or
      $before.cas_ausfuehren_erlaubt -ne $false -or
      $before.aktive_v2r4 -ne 1 -or $before.aktive_v3 -ne 0) {
    throw 'FAIL_NOTEBOOK_BEFORE_RECEIPT'
  }
  $review=(& $tool -Aktion Pruefen -Ablage $archive) | ConvertFrom-Json
  if ($review.ergebnis -cne 'VORHER_GESPEICHERT_KEINE_CAS_FREIGABE' -or
      $review.nachher_vorhanden -ne $false) {
    throw 'FAIL_NOTEBOOK_RESTART_READBACK'
  }
  Assert-Hold { & $tool -Aktion Vorher -Datei $pre -Ablage $archive } 'REPLAY'
  $done=(& $tool -Aktion Nachher -Datei $post -Ablage $archive) | ConvertFrom-Json
  if ($done.ergebnis -cne 'GESPEICHERT_NACHHER' -or $done.v3_freigabe -ne $false) {
    throw 'FAIL_NOTEBOOK_AFTER_RECEIPT'
  }
  $after=(& $tool -Aktion Pruefen -Ablage $archive) | ConvertFrom-Json
  if ($after.ergebnis -cne 'V3_CLOUD_STATUS_BEOBACHTET_NOCH_KEINE_RELEASE_FREIGABE' -or
      $after.nachher_vorhanden -ne $true -or $after.v3_freigabe -ne $false) {
    throw 'FAIL_NOTEBOOK_AFTER_RESTART'
  }
  Assert-Hold { & $tool -Aktion Nachher -Datei $post -Ablage $archive } 'AFTER_REPLAY'
  $archived=Join-Path $archive 'nachher.json'
  [IO.File]::AppendAllText($archived,' ',[Text.Encoding]::ASCII)
  Assert-Hold { & $tool -Aktion Pruefen -Ablage $archive } 'TAMPER'
  Write-Output 'V3_NOTEBOOK_SIMPLE_ONE_TIME_BEFORE_AFTER_TAMPER_REPLAY_PASS_NO_CAS'
} finally {
  if ([IO.Directory]::Exists($root)) {
    [IO.Directory]::Delete($root,$true)
  }
}
