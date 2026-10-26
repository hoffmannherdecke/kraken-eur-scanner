# V3 Paper – einfache Notebook-Kontrolle bei einer einzigen Umschaltung

**Aktuelle Entscheidung des Nutzers am 26.10.2026:** Das vorhandene, kennwortgeschützte Windows-Notebook (ein einziger Benutzer) genügt als **praktisch getrennte lokale Zweitkopie** für den einmaligen geplanten Übergang V2R4 → V3 **Paper**. Keine separate Hardware, kein Cloud-Vault, kein zweites laufendes System, keine teure WORM-Ablage und keine Prüfung bei jedem Paper-Kauf. **Nicht für Echtgeld-Release übertragbar.**

Dies ist eine **bewusst begrenzte Risikowahl**, keine Behauptung über Schutz gegen Notebook-Administrator, Malware oder privilegierte Supabase-Änderungen. Es ist ein unabhängiger menschlicher Betriebsblick und eine lokale Hash-Kontrolle, **keine kryptographisch unabhängige Root-of-Trust oder lückenlos garantiertes CAS-Attempt-Protokoll**. Die vorhandene ursprüngliche `security_permissions_and_rls`-Zuständigkeit und Release-Owner [Issue #99](https://github.com/hoffmannherdecke/kraken-eur-scanner/issues/99) bleiben verantwortlich.

## Sehr kurzer Einmalablauf

Bei einer **später separat ausdrücklich freigegebenen** V3-Paper-Umschaltung:

1. Notebook starten und mit dem bisherigen **Windows-Kennwort** anmelden. Keine neuen Benutzer/Kennwörter/VPN/Tokens auf dem Notebook. Aus GitHub genau die geprüfte Version des Projektordners herunterladen; das Skript benötigt nur **Windows PowerShell 5.1**.
2. Auf dem Notebook über die **bereits bestehende** Supabase-Weboberfläche im korrekten Originalprojekt das festgelegte, **nur lesende** `supabase/v3-notebook-onetime-paper-state-READONLY.sql` öffnen. Die **eine** JSON-Zelle `notebook_snapshot` (nicht den gesamten SQL-Editor und kein Kennwort) als `vorher-quell.json` speichern. Nur die JSON-Zelle, nicht das umhüllende `[{"notebook_snapshot":...}]`-Format.
3. Im Projektordner PowerShell ausführen: `powershell.exe -NoProfile -File .\tools\v3-notebook-onetime-paper-witness-INACTIVE.ps1 -Aktion Vorher -Datei "PFAD\vorher-quell.json"`. Das speichert eine **einmalige** lokale Zweitkopie und ihre SHA-256-Prüfsumme unter `Dokumente\V3-Paper-Nachweise`. **Es schaltet nichts um.** Falls V2R4 nicht allein aktiv ist, wird die Vorher-Datei abgewiesen.
4. **Nur nach tatsächlich separat erfüllten und freigegebenen vorhandenen sechs V3-E2E-/CAS-/Originalhost-Gates** wird der eigentliche kontrollierte CAS durch den vorhandenen freigegebenen Operator einmalig ausgeführt. Das Notebook erteilt keine CAS-Autorisierung.
5. Dieselbe lesende SQL-Abfrage nach dem echten Umschaltvorgang erneut ausführen, als `nachher-quell.json` speichern und `-Aktion Nachher -Datei "PFAD\nachher-quell.json"` aufrufen. Anschließend `powershell.exe -NoProfile -File .\tools\v3-notebook-onetime-paper-witness-INACTIVE.ps1 -Aktion Pruefen`. Das liefert nur die Beobachtung `V3_CLOUD_STATUS_BEOBACHTET_NOCH_KEINE_RELEASE_FREIGABE`, `V2R4_CLOUD_STATUS_UNVERAENDERT` oder `UNGEWISS_MANUELL_ABGLEICHEN`, nicht den Befehl zu erneutem CAS.

**Nur zwei Snapshot-Kopien, keine laufende Überwachung.** Ein vorhandener Dateiname kann nicht automatisch überschrieben werden. Bei verlorener Cloud-Antwort, Widerspruch, manipuliertem Hash oder unbekanntem CAS-Ergebnis gilt weiterhin **kein automatischer zweiter CAS-Aufruf und kein alter V2R4-Auto-Rearm**. Nutzer/Release-Owner gleichen den aktuellen Cloud-Zustand gezielt ab. Kein neuer Task, Notebook-Daemon oder Cloud-Worker.

**Wichtige Grenze:** Eine SHA-256-Prüfsumme neben einer Datei entdeckt gewöhnliche versehentliche Änderungen, verhindert aber nicht, dass derselbe berechtigte Notebook-Benutzer beide Dateien manipuliert. Die erfolgreiche Zweitkopie sagt weder, dass die Supabase-Abfrage aus einer wirklich unabhängigen DB-Credential-Sitzung kam, noch dass alle historischen CAS-Aufrufe erfasst wurden. Diese technische Einschränkung wird bei der **Paper-only**-Freigabe bewusst akzeptiert und niemals als formeller unabhängiger WORM-/DBA-Audit-Nachweis ausgegeben.

## Was bewusst unverändert bleibt

- Die produktiven drei separaten Supabase-Actor-Shells aus PR573 sind weiter **NOLOGIN**, die beiden privaten Tabellen aus PR572 bleiben durch FORCE RLS geschützt. Eine neue Anmeldung, ein Privileg oder eine CAS-Ausführung entsteht **nicht** durch dieses Notebook-Werkzeug.
- Die eigentliche Cloud-CAS-Funktion bleibt **uninstalliert**, solange ihr ursprünglicher IAM-/Transaktions-/E2E-Vertrag nicht sicher ausgeführt und getestet werden kann. Ein GitHub-Merge oder lokaler Snapshot ersetzt den Originalhost-/Cloud-Echtbeleg **nicht**.
- V3-Scanner und spätere Paper-Trades laufen **ohne** Notebook-Bestätigungen und ohne erhöhte Latenz. Für dieses Paper-Projekt ist kein Drittanbieter-WORM-/Sigstore-/Cloud-Vault-Abonnement zusätzliche Voraussetzung. Die bisherigen überdimensionierten *optionalen* custody-Ideen werden nicht weiter verfolgt; echte CAS-Doppelausführungs- und Zustandskonsistenzrisiken bleiben wichtig.
- Der reale technische Zielzustand ist ein sicherer, kontrolliert ausgeführter **einmaliger** V2R4→V3-Paper-Wechsel samt sechs ursprünglichen echten E2E-Quittungen, nicht das immer komplexere Aufrüsten einer Sicherheitsinfrastruktur.

**Test:** Die vorhandene Architecture-CI führt `tests/test_v3_notebook_onetime_paper_witness.ps1` mit rein synthetischem JSON in einem temporären Verzeichnis aus: Vorher/Nachher/erneutes Lesen, Verwechslung des Projekts, Duplikat, Manipulation und verweigerte CAS-Autorisierung. Es wird kein Notebook, Windows-Benutzer, Supabase-Projekt oder produktiver CAS berührt.

**Erst bei tatsächlicher Notebook-Anwendung offen:** Download/Quellpin und einmaliger echter Windows-5.1-Nachweis am gewählten Notebook. Bis dahin **SOURCE_ONLY / NO_CAS / NO_PAPER_ACTIVATION**.
