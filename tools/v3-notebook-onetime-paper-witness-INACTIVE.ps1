# V3 PAPER NOTEBOOK: ONE-TIME LOCAL COPY OF CLOUD READ-ONLY STATE.
# Works with built-in Windows PowerShell 5.1: no Python, admin rights, services,
# new passwords, private keys, CAS calls, database access or scheduling.
# This is an owner-controlled second copy, NOT tamper-proof WORM or a go-live ACK.
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)]
  [ValidateSet('Vorher','Nachher','Pruefen')]
  [string]$Aktion,
  [string]$Datei,
  [string]$Ablage = (Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'V3-Paper-Nachweise')
)
$ErrorActionPreference='Stop'
$expected=@('kind','project_ref','observed_at_utc','active_total',
  'active_v2r4','active_v3','audit_intent_count','cas_function_present')
$project='nlgzjmqgwueojlyqmoru'
function Read-ValidatedSnapshot([byte[]]$bytes) {
  if ($bytes.Length -lt 40 -or $bytes.Length -gt 4096) {
    throw 'V3_NOTEBOOK_HOLD: unpassende JSON-Dateigroesse'
  }
  $raw=[Text.Encoding]::UTF8.GetString($bytes)
  # Windows Notepad and Windows PowerShell may add one UTF-8 BOM.
  if ($raw.Length -gt 0 -and $raw[0] -eq [char]0xFEFF) {
    $raw=$raw.Substring(1)
  }
  try {
    $row=ConvertFrom-Json -InputObject $raw -ErrorAction Stop
  } catch {
    throw 'V3_NOTEBOOK_HOLD: ungueltiges Snapshot-JSON'
  }
  if ($null -eq $row -or $row -isnot [pscustomobject]) {
    throw 'V3_NOTEBOOK_HOLD: Snapshot muss ein JSON-Objekt sein'
  }
  $keys=@($row.PSObject.Properties.Name | Sort-Object)
  $wanted=@($expected | Sort-Object)
  if (($keys -join '|') -cne ($wanted -join '|') -or
      $row.kind -cne 'V3_PAPER_NOTEBOOK_SNAPSHOT_V1' -or
      $row.project_ref -cne $project -or
      $row.cas_function_present -isnot [bool]) {
    throw 'V3_NOTEBOOK_HOLD: fremde oder zusaetzliche Snapshot-Felder'
  }
  foreach ($field in @('active_total','active_v2r4','active_v3','audit_intent_count')) {
    $n=$row.$field
    if (($n -isnot [int] -and $n -isnot [long]) -or $n -lt 0 -or $n -gt 1000000) {
      throw 'V3_NOTEBOOK_HOLD: ungueltiger Zaehler'
    }
  }
  if ($row.observed_at_utc -isnot [string] -or
      $row.observed_at_utc -cnotmatch '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$') {
    throw 'V3_NOTEBOOK_HOLD: ungueltiger UTC-Zeitstempel'
  }
  $parsed=[datetime]::MinValue
  if (-not [datetime]::TryParseExact($row.observed_at_utc,
      "yyyy-MM-dd'T'HH:mm:ss'Z'",
      [Globalization.CultureInfo]::InvariantCulture,
      [Globalization.DateTimeStyles]::None,[ref]$parsed)) {
    throw 'V3_NOTEBOOK_HOLD: nicht existierendes UTC-Datum'
  }
  if ($row.active_v2r4 + $row.active_v3 -gt $row.active_total) {
    throw 'V3_NOTEBOOK_HOLD: widerspruechliche aktive Serien'
  }
  return $row
}
function Hash-Bytes([byte[]]$bytes) {
  $sha=[Security.Cryptography.SHA256]::Create()
  try {
    return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-','').ToLowerInvariant()
  } finally { $sha.Dispose() }
}
function Read-Saved([string]$name) {
  $path=Join-Path $Ablage ($name+'.json')
  $pin=Join-Path $Ablage ($name+'.sha256')
  if (-not [IO.File]::Exists($path) -or -not [IO.File]::Exists($pin)) {
    throw 'V3_NOTEBOOK_HOLD: fehlender oder unvollstaendiger Nachweis'
  }
  $data=[IO.File]::ReadAllBytes($path)
  $digest=Hash-Bytes $data
  if ($digest -cne [IO.File]::ReadAllText($pin,[Text.Encoding]::ASCII).Trim()) {
    throw 'V3_NOTEBOOK_HOLD: Nachweis und SHA256 stimmen nicht mehr ueberein'
  }
  $row=Read-ValidatedSnapshot $data
  return @{ snapshot=$row; sha256=$digest }
}
function Save-New([string]$path,[byte[]]$bytes) {
  $stream=[IO.FileStream]::new($path,[IO.FileMode]::CreateNew,
      [IO.FileAccess]::Write,[IO.FileShare]::None)
  try {
    $stream.Write($bytes,0,$bytes.Length)
    $stream.Flush($true)
  } finally { $stream.Dispose() }
}
$Ablage=[IO.Path]::GetFullPath($Ablage)
if ($Aktion -eq 'Pruefen') {
  if (-not [IO.Directory]::Exists($Ablage)) {
    throw 'V3_NOTEBOOK_HOLD: noch keine lokale Ablage'
  }
  $before=Read-Saved 'vorher'
  $afterPresent=[IO.File]::Exists((Join-Path $Ablage 'nachher.json')) -or
    [IO.File]::Exists((Join-Path $Ablage 'nachher.sha256'))
  $status='VORHER_GESPEICHERT_KEINE_CAS_FREIGABE'
  if ($afterPresent) {
    $after=Read-Saved 'nachher'
    if ($after.snapshot.observed_at_utc -lt $before.snapshot.observed_at_utc) {
      throw 'V3_NOTEBOOK_HOLD: Nachher-Snapshot ist aelter als Vorher'
    }
    $status='UNGEWISS_MANUELL_ABGLEICHEN'
    if ($after.snapshot.active_total -eq 1 -and
        $after.snapshot.active_v3 -eq 1 -and
        $after.snapshot.active_v2r4 -eq 0) {
      $status='V3_CLOUD_STATUS_BEOBACHTET_NOCH_KEINE_RELEASE_FREIGABE'
    } elseif ($after.snapshot.active_total -eq 1 -and
              $after.snapshot.active_v2r4 -eq 1 -and
              $after.snapshot.active_v3 -eq 0) {
      $status='V2R4_CLOUD_STATUS_UNVERAENDERT'
    }
  }
  [pscustomobject]@{
    ergebnis=$status
    vorher_sha256=$before.sha256
    nachher_vorhanden=[bool]$afterPresent
    cas_ausfuehren_erlaubt=$false
    v3_freigabe=$false
    externe_manipulationssicherheit_behauptet=$false
  } | ConvertTo-Json -Compress
  return
}
if ([string]::IsNullOrWhiteSpace($Datei) -or
    [IO.Path]::GetExtension($Datei) -cne '.json') {
  throw 'V3_NOTEBOOK_HOLD: -Datei muss eine vorhandene JSON-Datei sein'
}
$source=[IO.Path]::GetFullPath($Datei)
$info=Get-Item -LiteralPath $source -ErrorAction Stop
if ($info.PSIsContainer -or
    [bool]($info.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
    $info.Length -gt 4096) {
  throw 'V3_NOTEBOOK_HOLD: Quell-Datei ungueltig oder verknuepft'
}
$bytes=[IO.File]::ReadAllBytes($source)
$row=Read-ValidatedSnapshot $bytes
if ($Aktion -eq 'Vorher' -and
    ($row.active_total -ne 1 -or $row.active_v2r4 -ne 1 -or $row.active_v3 -ne 0)) {
  throw 'V3_NOTEBOOK_HOLD: Vorher muss genau die aktive V2R4 zeigen'
}
if ($Aktion -eq 'Nachher') {
  $existing=Read-Saved 'vorher'
  if ($row.observed_at_utc -lt $existing.snapshot.observed_at_utc) {
    throw 'V3_NOTEBOOK_HOLD: Nachher-Zeit liegt vor dem Vorher-Beleg'
  }
}
[void][IO.Directory]::CreateDirectory($Ablage)
$folder=Get-Item -LiteralPath $Ablage -Force
if ([bool]($folder.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
  throw 'V3_NOTEBOOK_HOLD: verknuepfte Ablage verweigert'
}
$name=if($Aktion -eq 'Vorher'){'vorher'}else{'nachher'}
$destination=Join-Path $Ablage ($name+'.json')
$pinFile=Join-Path $Ablage ($name+'.sha256')
if ([IO.File]::Exists($destination) -or [IO.File]::Exists($pinFile)) {
  throw 'V3_NOTEBOOK_HOLD: vorhandener Beleg wird nicht ueberschrieben'
}
$digest=Hash-Bytes $bytes
Save-New $destination $bytes
Save-New $pinFile ([Text.Encoding]::ASCII.GetBytes($digest))
$saved=Read-Saved $name
if ($saved.sha256 -cne $digest) {
  throw 'V3_NOTEBOOK_HOLD: Schreibbestaetigung ungueltig'
}
[pscustomobject]@{
  ergebnis=('GESPEICHERT_'+$Aktion.ToUpperInvariant())
  sha256=$digest
  aktive_v2r4=$row.active_v2r4
  aktive_v3=$row.active_v3
  keine_doppelte_automatische_umschaltung=$true
  cas_ausfuehren_erlaubt=$false
  v3_freigabe=$false
} | ConvertTo-Json -Compress
