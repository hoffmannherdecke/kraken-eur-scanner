# V3 Paper – kostenloser eigener CAS-Operator-Zugang (INACTIVE / Einmal-Einrichtung)

**Originaler Fachowner:** Release Issue #99. **Projektmanager:** Issue #353. Bestehende Rollen `v3_cas_executor`, `v3_cas_audit_writer` und `v3_cas_audit_reader` sind seit 26.10.2026 tatsächlich im produktiven Supabase-Projekt als **NOLOGIN**, ohne Anwendungsmitgliedschaften, vorhanden. Alte V2R4 bleibt aktiv. Dieser Teilauftrag ist die **separate Anmeldung** des menschlich bestätigten V3-CAS-Operators, noch keine Berechtigung zum CAS-Aufruf.

## Architektur

- **Einen** zusätzlichen Namen `v3_cas_operator_login` in Supabase zunächst **NOLOGIN / NOINHERIT / NOBYPASSRLS / CONNECTION LIMIT 1 / PASSWORD NULL**, ohne Mitgliedschaften oder Direktgrants vorbereiten. PostgreSQL17 erlaubt dabei automatisch genau die eingeschränkte `postgres`-Verwaltungsmitgliedschaft `ADMIN TRUE, SET FALSE, INHERIT FALSE`, aber keine Anwendungsmitgliedschaften.
- Die Passwortquelle ist **nur die Windows-Anmeldung des vorhandenen physischen Mini-PC-Besitzers**, nicht `CryptoSupportSvc`, nicht der GitHub-Runner, nicht Supabase `service_role`. Die Source-Datei `tools/minipc-v3-cas-operator-login-INACTIVE.ps1` wird manuell und **nicht als Hintergrundtask** vom interaktiven Windows-Benutzer gestartet.
- `-Stage` erzeugt unter `%LOCALAPPDATA%\V3CasOperator-INACTIVE` eine neue zufällige 256-Bit-Zugangsinformation mit DPAPI **CurrentUser** und geschützter NTFS-DACL, kein Plaintextfile. SQL für den einzigen späteren administrativen Aufruf wird ebenfalls ausschließlich lokal, NTFS-geschützt erzeugt. Dieses SQL enthält einen aus dem Passwort lokal berechneten **SCRAM-SHA-256-Verifier**, **nicht** das Passwort selbst. Ein Verifier ist weiterhin vertrauliches Zugangsmaterial und darf **niemals im Chat, öffentlichen GitHub oder Slack** erscheinen.
- **Neue verbindliche Originalhost-Prüfung vor jeder Enrollment-SQL-Ausführung:** `-VerifyLocal` liest ausschließlich die geschützten lokalen Dateien **unter demselben interaktiven Windows-Benutzer** und bestätigt eine echte DPAPI-Entschlüsselung und Übereinstimmung der aus dem Secret rekonstruierten SCRAM Stored-/Server-Keys mit dem lokalen SQL. Ausgabe **nur** `LOCAL_DPAPI_SCRAM_ROUNDTRIP_PASS` und sichere boolesche Flags, keine Login-Informationen, kein Verifier, kein Dateiinhalte-Export, keine Netzwerkaktion. Ein FAIL ist `HOLD`; dann weder SQL ausführen noch neuerlich eigenmächtig ein Passwort erzeugen.
- Der Mini-PC-Operator öffnet ausschließlich das originale bestehende Supabase-Dashboard des Projekts `nlgzjmqgwueojlyqmoru`, prüft den SQL-Text lokal und führt ihn im SQL Editor selbst aus. Das SQL hat **BEGIN/DO/COMMIT**, prüft drei alte NOLOGIN-Rollen, den eigenen noch gesperrten Einmal-Login, null Mitglieder, null installierte CAS-Funktionen/Audit-Schemas, keine generisch ausführbare öffentliche Funktion; es macht ausschließlich `ALTER ROLE v3_cas_operator_login LOGIN PASSWORD SCRAM_VERIFIER`. **Keine** CAS-Ausführungsrechte, keine Rollenmitgliedschaft und keine Datenänderung.
- Danach kontrolliert der Projekt-Owner **unabhängig und read-only** per bestehendem Supabase-Connector die tatsächliche Rolle `LOGIN`, Passworthash **nur als boolesche Existenzprüfung**, `connlimit=1`, `NOBYPASSRLS`, `NOINHERIT`, null Extra-Mitglieder, keine CAS-Funktion, keine Audit-Schema-Installation und unverändert aktive V2R4. Die tatsächliche Passwort-Login-Verbindung muss separat vom Original-Mini-PC gegen Supabase SSL/Zertifikat und Zugangsidentität geprüft werden; ein Rollenkatalog-Readback ist **keine** authentifizierte Verbindungsprobe.
- Nach bestätigter erfolgreicher Enrollment-Readback **nur** `-RemoveEnrollmentSql` ausführen (entfernt genau die lokale Verifier-SQL-Datei, **nicht** das DPAPI-Passwort). Bei Fehler: keine erneute Generierung, keine neuen Rollen; gezielt die erste Fehlermeldung prüfen. Fällt der Originalhost aus, wird der Zugriff **gesperrt**, bis ein DBA den Zugang kontrolliert mit neuer eigener Anmeldeinformation wiederherstellt. DPAPI allein ist keine unabänderliche TPM-Origin-Signatur oder externes WORM.

## Windows-Ausführung (erst nach geprüftem geschützt gemergtem Original-Source)

Auf dem Mini-PC als **normal angemeldeter Windows-Benutzer** und ausdrücklich nicht als `CryptoSupportSvc`/GitHub-Runner die von dem konkreten freigegebenen Original-GitHub-Commit heruntergeladene PowerShell-Datei prüfen und ausführen:

```powershell
powershell.exe -NoProfile -File .\tools\minipc-v3-cas-operator-login-INACTIVE.ps1
powershell.exe -NoProfile -File .\tools\minipc-v3-cas-operator-login-INACTIVE.ps1 -Stage
powershell.exe -NoProfile -File .\tools\minipc-v3-cas-operator-login-INACTIVE.ps1 -VerifyLocal
```

**`LOCAL_DPAPI_SCRAM_ROUNDTRIP_PASS` ist Pflicht vor der Nutzung des lokalen SQL.** Nur die bereinigte Ergebnis-Ausgabe (ohne Verifier, Passwort, SQL oder Dateiinhalt) als Erfolg melden. Das lokal entstandene `operator-login-enroll-ONE-TIME.sql` nicht in diesen Chat senden, sondern nur im korrekten eigenen Supabase-Dashboard verwenden. Nach unabhängigem Rollen-Readback:

```powershell
powershell.exe -NoProfile -File .\tools\minipc-v3-cas-operator-login-INACTIVE.ps1 -RemoveEnrollmentSql
```

Falls der Repo-Klon nicht im interaktiven Benutzerprofil liegt: Quelldatei über den vertrauenswürdigen **konkreten Merge-Commit** im Original-GitHub herunterladen und den tatsächlichen lokalen Pfad statt `./tools` angeben. Keine breite Explorer-/GitHub-/Windows-Administratorfreigabe und kein unkontrollierter Remote-One-Liner.

## Release-Grenzen – ausdrücklich offen

Dieses neue Login ist **kein Mitglied** von `v3_cas_executor`, hat kein EXECUTE auf einen V3-CAS-Endpunkt (dessen Source bleibt inaktiv und der Endpunkt existiert nicht) und kann keine V3-Paper-Serie anlegen. Wirkliche unabhängige Identitätsbestätigung braucht später eine geprüfte Originalhost-LIVE-Verbindung und getrennte Signatur/Issuer-Kontrolle. Der echte PREINVOKE-Audit-Intent samt **dauerhafter separater Transaktion, unabhängiger Leser- und signierter externer ACK vor CAS**, der produktive Connector/Credential-Schutz, Rollback-/Stop-/Rearm-Beweis, die ursprünglichen sechs E2E und deine finale V3-Paper-Go-live-Freigabe bleiben getrennte, offene Release-Punkte. Keine zusätzliche Kosten-/Supabase-Dauerlast oder neue Automation.

## 26.10.2026 – unabhängiger tatsächlicher SSL-/PostgreSQL-Loginbeweis (SOURCE INACTIVE)

**Neue datierte Original-Cloud-Baseline:** Die produktive Rolle `v3_cas_operator_login` steht bei unabhängiger lesender Katalogprüfung bereits auf `LOGIN`, `CONNECTION LIMIT 1`, `NOINHERIT`, `NOBYPASSRLS`, Passwortprüfwert vom Typ SCRAM-SHA-256 vorhanden, ohne App-/Executor-Mitgliedschaft; drei bisherige CAS/Audit-Rollen weiterhin `NOLOGIN`; CAS-RPC-/Audit-Schema nicht installiert. Die zusätzliche SQL-Editor-Ausführung meldete `V3_CAS_LOGIN_NOT_PRESTAGED_SAFE_NOLOGIN`, weil der Einmal-SQL-Guard eine noch gesperrte `NOLOGIN`-Rolle verlangt. **SQL nicht nochmals ausführen, keine neue Stage/Passwortausgabe und keine Rolle zurücksetzen.** Katalog-Readback ist ausdrücklich **kein** Passwort-Loginbeweis.

**Wiederverwendung statt Runner-Rechteausweitung:** Genau ein separates manuelles Skript `tools/minipc-v3-cas-operator-auth-probe-INACTIVE.ps1`; bestehende lokale DPAPI-Datei bleibt unverändert. Dieses Skript nutzt **nur bei ausdrücklichem `-Probe`** den angemeldeten interaktiven Windows-Originalbenutzer, nicht `CryptoSupportSvc`, keinen Task und keine Cloud-Service-Role. Es sucht einen *bereits installierten* PostgreSQL-17/18-Client unter `C:\Program Files\PostgreSQL\<Version>\bin\psql.exe`; installiert **nichts** und lädt **nichts** aus dem Netz herunter. Passwort geht nur kurz an das eigens gestartete lokale `psql.exe` als Kindprozess-Umgebung, nicht in Argumente, öffentliche Logs, GitHub oder diesen Chat. Windows-Systemadministratoren können prinzipiell Prozesse beaufsichtigen; das ist keine zusätzliche hardwaregebundene Geheimnisisolation.

Nach **geschütztem PR-Merge und Original-Source-/Windows-AST-Checks** vom eigenen Mini-PC als derselbe interaktive Windows-Benutzer (im Verzeichnis des geprüften Repository-Checkouts) ausführen:

```powershell
powershell.exe -NoProfile -File .\tools\minipc-v3-cas-operator-auth-probe-INACTIVE.ps1
powershell.exe -NoProfile -File .\tools\minipc-v3-cas-operator-auth-probe-INACTIVE.ps1 -Probe
```

**TLS-Pflicht:** `PGSSLMODE=verify-full`, `PGSSLROOTCERT=system` (PostgreSQL 17+) oder über `-CaFile` die originale Supabase-CA aus **Database Settings → SSL Configuration**; keine Herabstufung auf `require` oder `prefer`. Die ursprüngliche direkte Free-Plan-Datenbankverbindung kann IPv6 verlangen. Falls diese nur wegen fehlender IPv6-Verbindung nicht erreichbar ist: Im richtigen bestehenden Supabase-Dashboard **Connect → Session pooler** auswählen, den dort **tatsächlich angezeigten Hostnamen** übernehmen, und `-Probe -Mode SessionPooler -PoolerHost '<ECHTER-HOSTNAME-AUS-CONNECT>'` verwenden. Keine Pooler-Adresse aus Region/Index erraten. Der Skriptcheck verlangt die echte `*.pooler.supabase.com`-Domain und die richtige projektbezogene eigene PostgreSQL-Operatorrolle.

Die einzige SQL-Abfrage ist `SELECT current_user, session_user, (SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid())`; zusätzlich wird in der Session `default_transaction_read_only=on` gesetzt. Nur bei passend bestätigter Rollenidentität, tatsächlichem SSL sowie erfolgreicher CA-/Hostname-Validierung erscheint der sichere Marker `ORIGINALHOST_POSTGRES_SSL_AUTH_PASS`. Fehlender `psql`-Client, Zertifikatsfehler, falscher DPAPI-Kontext, DNS-/IPv6-Probleme und abgelehnte Anmeldung sind **HOLD**, nicht durch Passwort-Neugenerierung, Rollen-Grants oder einen Sicherheits-Bypass zu beheben. Bei Misserfolg nur Fehlerkategorie und sicheren Status mitteilen; keine Secrets/SQL-Dateien/Screenshots mit Zugangsdaten.

**Wichtig:** Ein grünes GitHub-CI bestätigt nur Quelltext und Windows-PowerShell-Syntax. Der tatsächliche Originalhost-PASS bleibt bis zur manuellen echten Ausführung **OFFEN**. Erst nach belegtem authentifiziertem Anmeldenachweis die originale lokale `-RemoveEnrollmentSql`-Bereinigung der Verifier-Einmaldatei durchführen; die DPAPI-Datei behalten. Danach sind der unabhängig signierte dauerhafte PREINVOKE-Audit-ACK, CAS-/Writer-/Stop-/Wiederanlauf- und sechs echte Paper-E2E-Proofs sowie finale ausdrückliche V3-Paper-Freigabe weiterhin offen. Kein neuer Scheduler, Service, Supabase-Projekt, bezahltes Paket oder Trading-Status.
