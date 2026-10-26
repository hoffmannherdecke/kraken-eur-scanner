# V3 Paper – kostenloser eigener CAS-Operator-Zugang (INACTIVE / Einmal-Einrichtung)

**Originaler Fachowner:** Release Issue #99. **Projektmanager:** Issue #353. Bestehende Rollen `v3_cas_executor`, `v3_cas_audit_writer` und `v3_cas_audit_reader` sind seit 26.10.2026 tatsächlich im produktiven Supabase-Projekt als **NOLOGIN**, ohne Anwendungsmitgliedschaften, vorhanden. Alte V2R4 bleibt aktiv. Dieser Teilauftrag ist die **separate Anmeldung** des menschlich bestätigten V3-CAS-Operators, noch keine Berechtigung zum CAS-Aufruf.

## Architektur

- **Einen** zusätzlichen Namen `v3_cas_operator_login` in Supabase zunächst **NOLOGIN / NOINHERIT / NOBYPASSRLS / CONNECTION LIMIT 1 / PASSWORD NULL**, ohne Mitgliedschaften oder Direktgrants vorbereiten. PostgreSQL17 erlaubt dabei automatisch genau die eingeschränkte `postgres`-Verwaltungsmitgliedschaft `ADMIN TRUE, SET FALSE, INHERIT FALSE`, aber keine Anwendungsmitgliedschaften.
- Die Passwortquelle ist **nur die Windows-Anmeldung des vorhandenen physischen Mini-PC-Besitzers**, nicht `CryptoSupportSvc`, nicht der GitHub-Runner, nicht Supabase `service_role`. Die Source-Datei `tools/minipc-v3-cas-operator-login-INACTIVE.ps1` wird manuell und **nicht als Hintergrundtask** vom interaktiven Windows-Benutzer gestartet.
- `-Stage` erzeugt unter `%LOCALAPPDATA%\V3CasOperator-INACTIVE` eine neue zufällige 256-Bit-Zugangsinformation mit DPAPI **CurrentUser** und geschützter NTFS-DACL, kein Plaintextfile. SQL für den einzigen späteren administrativen Aufruf wird ebenfalls ausschließlich lokal, NTFS-geschützt erzeugt. Dieses SQL enthält einen aus dem Passwort lokal berechneten **SCRAM-SHA-256-Verifier**, **nicht** das Passwort selbst. Ein Verifier ist weiterhin vertrauliches Zugangsmaterial und darf **niemals im Chat, öffentlichen GitHub oder Slack** erscheinen.
- Der Mini-PC-Operator öffnet ausschließlich das originale bestehende Supabase-Dashboard des Projekts `nlgzjmqgwueojlyqmoru`, prüft den SQL-Text lokal und führt ihn im SQL Editor selbst aus. Das SQL hat **BEGIN/DO/COMMIT**, prüft drei alte NOLOGIN-Rollen, den eigenen noch gesperrten Einmal-Login, null Mitglieder, null installierte CAS-Funktionen/Audit-Schemas, keine generisch ausführbare öffentliche Funktion; es macht ausschließlich `ALTER ROLE v3_cas_operator_login LOGIN PASSWORD SCRAM_VERIFIER`. **Keine** CAS-Ausführungsrechte, keine Rollenmitgliedschaft und keine Datenänderung.
- Danach kontrolliert der Projekt-Owner **unabhängig und read-only** per bestehendem Supabase-Connector die tatsächliche Rolle `LOGIN`, Passworthash **nur als boolesche Existenzprüfung**, `connlimit=1`, `NOBYPASSRLS`, `NOINHERIT`, null Extra-Mitglieder, keine CAS-Funktion, keine Audit-Schema-Installation und unverändert aktive V2R4. Die tatsächliche Passwort-Login-Verbindung muss separat vom Original-Mini-PC gegen Supabase SSL/Zertifikat und Zugangsidentität geprüft werden; ein Rollenkatalog-Readback ist **keine** authentifizierte Verbindungsprobe.
- Nach bestätigter erfolgreicher Enrollment-Readback **nur** `-RemoveEnrollmentSql` ausführen (entfernt genau die lokale Verifier-SQL-Datei, **nicht** das DPAPI-Passwort). Bei Fehler: keine erneute Generierung, keine neuen Rollen; gezielt die erste Fehlermeldung prüfen. Fällt der Originalhost aus, wird der Zugriff **gesperrt**, bis ein DBA den Zugang kontrolliert mit neuer eigener Anmeldeinformation wiederherstellt. DPAPI allein ist keine unabänderliche TPM-Origin-Signatur oder externes WORM.

## Windows-Ausführung (erst nach geprüftem geschützt gemergtem Original-Source)

Auf dem Mini-PC als **normal angemeldeter Windows-Benutzer** und ausdrücklich nicht als `CryptoSupportSvc`/GitHub-Runner die von dem konkreten freigegebenen Original-GitHub-Commit heruntergeladene PowerShell-Datei prüfen und ausführen:

```powershell
powershell.exe -NoProfile -File .\tools\minipc-v3-cas-operator-login-INACTIVE.ps1
powershell.exe -NoProfile -File .\tools\minipc-v3-cas-operator-login-INACTIVE.ps1 -Stage
```

**Nur die Ausgabe (ohne Verifier, ohne Dateiinhalt) als Erfolg melden.** Das lokal entstandene `operator-login-enroll-ONE-TIME.sql` nicht in diesen Chat senden, sondern nur im korrekten eigenen Supabase-Dashboard verwenden. Nach unabhängigem Rollen-Readback:

```powershell
powershell.exe -NoProfile -File .\tools\minipc-v3-cas-operator-login-INACTIVE.ps1 -RemoveEnrollmentSql
```

Falls der Repo-Klon nicht im interaktiven Benutzerprofil liegt: Quelldatei über den vertrauenswürdigen **konkreten Merge-Commit** im Original-GitHub herunterladen und den tatsächlichen lokalen Pfad statt `./tools` angeben. Keine breite Explorer-/GitHub-/Windows-Administratorfreigabe und kein unkontrollierter Remote-One-Liner.

## Release-Grenzen – ausdrücklich offen

Dieses neue Login ist **kein Mitglied** von `v3_cas_executor`, hat kein EXECUTE auf einen V3-CAS-Endpunkt (dessen Source bleibt inaktiv und der Endpunkt existiert nicht) und kann keine V3-Paper-Serie anlegen. Wirkliche unabhängige Identitätsbestätigung braucht später eine geprüfte Originalhost-LIVE-Verbindung und getrennte Signatur/Issuer-Kontrolle. Der echte PREINVOKE-Audit-Intent samt **dauerhafter separater Transaktion, unabhängiger Leser- und signierter externer ACK vor CAS**, der produktive Connector/Credential-Schutz, Rollback-/Stop-/Rearm-Beweis, die ursprünglichen sechs E2E und deine finale V3-Paper-Go-live-Freigabe bleiben getrennte, offene Release-Punkte. Keine zusätzliche Kosten-/Supabase-Dauerlast oder neue Automation.
