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