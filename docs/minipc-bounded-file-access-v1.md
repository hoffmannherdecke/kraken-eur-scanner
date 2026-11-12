# Mini-PC-Dateisuche: eingeschränkter Task-Vertrag (Entwicklungsstand)

Owner: [#353](https://github.com/hoffmannherdecke/kraken-eur-scanner/issues/353). Quellcode wird über den vorhandenen privaten `MINIPC_TASK_V1`-Runner bereitgestellt. Kein zusätzlicher Runner, kein neuer Scheduler, keine Trading-Rechte.

**Deployment-Gate:** Bis öffentlicher und privater PR geprüft und gemergt, der lokale Prejob samt exakt passender privater Workflow-SHA in einem gebundenen Hostvorgang aktualisiert und ein echter Originalhost-E2E-Lauf bestanden ist, bleibt `MINIPC_FILE_ACCESS_E2E_PASS` **OFFEN**. Die existierende lokale SHA-Pinnung darf nicht vorzeitig geändert werden.

## Typisierte neue Nachrichten

Nur im bestehenden privaten Issue #13, ausschließlich durch den authentisierten Owner/GitHub-App-Kanal:

- `MINIPC_FILE_V1 | <main-commit-sha> | SEARCH | TRADING | <safe-basename-substring>`
- `MINIPC_FILE_V1 | <main-commit-sha> | SEARCH | DOWNLOADS | <safe-basename-substring>`
- `MINIPC_FILE_V1 | <main-commit-sha> | SEARCH | MISTRAL | <safe-basename-substring>`
- `MINIPC_FILE_V1 | <main-commit-sha> | EXPORT | <root-key> | <base64url-encoded-relative-path> | <exact-sha256>`

Die Suchvariable ist ein einzelner ASCII-Dateinamenabschnitt von 3–64 Zeichen, **kein Glob, keine Regex, kein Windows- oder PowerShell-Code**. EXPORT ist immer ein **neuer, separat beauftragter Owner-Kommentar** nach Sichtung einer Suche und Auswahl exakt eines Dateienpfades und seiner SHA256; SEARCH exportiert nichts. Base64url dient nur zur transportierten relativen Pfadangabe, **nicht** als Sicherheitsfreigabe. Die Task dekodiert und prüft jede Pfadkomponente erneut. Freie absolute Pfade, Elternsegmente, Reparse-Points und weitere Roots werden abgelehnt.

Quellwurzeln sind ausschließlich `C:\Users\ADMIN\Trading`, `C:\Users\ADMIN\Downloads` und `\\192.168.178.179\Mistral_450`. Kein M:, keine Volume- oder Laufwerkserkennung.

Limits: 75 Sekunden Task-Deadline (zusätzlich 8-Minuten-Workflow-Timeout), 1200 besuchte Einträge, maximal 20 Metadatentreffer, 2 MiB Hash-Dateigröße, bis 8 Verzeichnisebenen. Export nur eine maximal 64 KiB große UTF-8-Textdatei mit begrenzter Dateiendung und verbotenem Secret-/Schlüsselwortmuster; bei Unsicherheit nicht exportieren. Suche meldet relative Pfade nur bei bestandener Dateinamenprüfung; Logs befinden sich im privaten Repository. Der Export wird unter einem zufälligen Dateinamen in `RUNNER_TEMP` abgelegt und nur per gesondertem privatem Workflow-Artefakt mit 1 Tag Retention bereitgestellt, nicht im öffentlichen Hauptrepository. Ein gültiger Exportbefehl stellt die zusätzliche ausdrückliche einzelne Dateiauswahl dar.

**Hinweis:** Die Text-/Secret-Prüfung ist eine zusätzliche Sperre, keine Garantie zur vollständigen Geheimniserkennung. Bis zur gesonderten Sicherheitsabnahme sind Exporttests nur mit ausdrücklich nichtvertraulichen Testdateien zu betreiben.

Fehlerzustände: `ACCESS_DENIED`, `NOT_FOUND`, `UNAVAILABLE`, `HASH_MISMATCH`; unvollständige Suche `PARTIAL_LIMIT`. Kein Fehler autorisiert automatisch einen zweiten Runnerlauf oder die ACL-Erweiterung. Originalhostzustand und GitHub-Online/Idle sind **vor** genau einem SHA-gepinnten Auftrag zu prüfen; nach dem Fenster wieder Stopped/Disabled.

## Diff-Abnahme / Host-Gate

1. Bestehenden privaten Workflow und lokalen Prejob auf dasselbe freigegebene Revision-Paar umstellen; das vorhandene `approved-private-workflow-sha.txt` und den lokalen `bounded_window.ps1`-Pin in einem kontrollierten, rücknehmbaren Eingriff konsistent halten. Keine ungenehmigte Prejob-Aktualisierung aus CI.
2. Drei kleine unkritische Testdateien **bestehend oder nach separater Freigabe** an den drei Roots auswählen, SEARCH auf jedes Root und SHA256-Readback prüfen.
3. Negative Tests: ungültige Nachrichten, Traversal, Reparse-Point, unzulässiger Dateityp, Größenlimit, ungültiger SHA und unautorisierter Export (kein Artefakt). Keine Änderung an Trading-Dateien.
4. Eine **ausdrücklich freigegebene** neutrale Testdatei per eigenem EXPORT-Kommentar über privates kurzlebiges Artifact übernehmen; vom normalen Chat über Connector abrufen, lokal SHA256 vergleichen.
5. SafePause-Stopp/Disabled und das Fehlen jeder neuen Runtime-/Rechteänderung prüfen. Nur danach `MINIPC_FILE_ACCESS_E2E_PASS` und den Original-Run in #353 dokumentieren.

Die vorhandenen Basisabnahmen von Runner, USV, V3 und Workspace werden nicht wiederholt.
## Ein-Schritt-Direktexport (ab PR #715/#716, privater Bridge-PR #23)

Zusätzlich zum unveränderten zweistufigen SEARCH/EXPORT unterstützt die vorhandene Bridge
`MINIPC_FILE_V1 | <public-main-sha> | DIRECT | <root-key> | <base64url-relative-path>`.
Die ausgewählte einzelne Datei muss durch das eingeschränkte Dienstkonto lesbar sein und
alle unveränderten Pfad-, Typ-, Größen-, UTF-8-/ZIP- und Secret-Prüfungen bestehen.
`DIRECT` benötigt keine vorherige SEARCH-Runde, vergibt aber auch keine neuen Rechte.
Im bestehenden kurzlebigen privaten GitHub-Artefakt liegen die byteidentische Datei
unter ihrem Originalnamen und `origin-sha256.json` mit Root-Alias, relativem Pfad,
SHA256, Größe, Quell-Commit und UTC-Kopierzeit. Ein kollidierender Quelldateiname
`origin-sha256.json` wird zurückgewiesen. Der Bericht ist ein Herkunftsbeleg,
keine unabhängige digitale Signatur und keine Garantie auf Geheimnisfreiheit.

Die authentisierte private Issue-#13-Berechtigung, die begrenzte Runner-Verfügbarkeit,
der lokale pin-gebundene Prejob und SafePause bleiben erforderlich.
Für eine spätere Geräteinstallation müssen der lokale Prejob, die Workflow-Pin-Datei
und die im Fensteroperator fest hinterlegte private SHA konsistent auf der
genehmigten privaten Merge-Revision liegen. Quell-CI allein ist kein Host-E2E-Nachweis.

## Dauerhafte Dateiuebergabe unter Windows-Benutzeridentitaet (lokaler Bedienadapter)

Der bestehende Runner-Export MINIPC_FILE_V1 laeuft absichtlich unter CryptoSupportSvc. Der Originalhost-Test #66 (Run 43196668233) meldete SOURCE_READ/UNAVAILABLE, weil das Dienstkonto die Testdatei nicht lesen konnte. Das ist kein Anlass fuer allgemeine Datei-ACL-Erweiterungen.

Der lokale Bedienadapter tools/minipc_runner_guard/local_file_handoff.ps1 ist Teil der bestehenden Datei-Bridge. Er erstellt weder Dienst, Runner, Scheduler, Netzwerkverbindung noch weitere Zugriffsberechtigungen.

Einmalige Installation als normal angemeldeter Windows-Benutzer: einen Source/CI-geprueften gepinnten Skriptstand laden und -Install ausfuehren. Damit wird die bestehende Windows Explorer > Rechtsklick > Senden an-Verknuepfung ChatGPT - gepruefter Dateiexport eingerichtet. Der Adapter liegt unter %LOCALAPPDATA%\CryptoSupport\FileHandoff.

Jeder Export: Eine konkrete Datei im Explorer markieren, Senden an > ChatGPT - gepruefter Dateiexport. Die Kopie und die Herkunftsdatei origin-sha256.json landen in einem zufaelligen Unterordner von %USERPROFILE%\Downloads\ChatGPT-Uebergabe. Der Benutzer kontrolliert die Datei und laedt sie selbst in ChatGPT hoch. Keine automatische Datenuebertragung.

Sicherheitsgrenzen: laufendes normales Benutzerkonto und dessen vorhandene Leserechte; Originaldateien und ACLs unveraendert. Sperren fuer Junction-/Reparse-Pfade, sensible Namen, UTF-8/Binaer-Inhalte, auffaellige Geheimnismuster, bestimmte Text-Endungen, 2-MiB-Grenze. SHA256 wird vor/nach dem Quelllesen sowie am Export verglichen. Herkunftsbeleg enthaelt Quelle, Konto, UTC, Hash und Bytezahl. Vertrauliche Inhalte duerfen nicht hochgeladen werden; Musterpruefung kann weder alle Geheimnisse erkennen noch jede harmlose Datei durchlassen.

Host-Abnahme: Nach CI, genau einmaliger lokaler Installation, Testexport einer neutralen Textdatei, Quell-/Export-SHA256-Gleichheit und Nutzerpruefung des Pakets erst MINIPC_USER_HANDOFF_E2E_PASS. Runner-Bridge-E2E und Benutzer-Handoff-E2E bleiben getrennte Nachweise; Source-CI ist kein Installationsbeleg.
