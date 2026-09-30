# Mini-PC Preflight / Inbetriebnahme-Runbook

Status: **PREPARED BEFORE FIRST BOOT**  
Stand: 2026-09-29  
Gerät: Dell OptiPlex 5060 Micro — i5-8500T / 16 GB RAM / 256 GB SSD / Windows 11 Pro erwartet  
Netz: LAN, FRITZ!Box 7590 AX

## Ziel

So früh wie möglich vom direkten Arbeiten am Gerät auf Fernadministration wechseln, danach den Mini-PC schrittweise zur stabilen 24/7-Basis ausbauen. Keine V2R4-Aktivierung beim ersten Boot.

## Bereits vorab verifiziert

- Windows 11 Pro kann als Microsoft-Remotedesktop-Host dienen.
- Dell OptiPlex 5060 besitzt im BIOS `AC Recovery` mit `Power On` / `Power Off` / `Last Power State`; für 24/7 ist `Power On` vorgesehen.
- GitHub-Hauptpfade und V2R4-Draft existieren.
- Supabase-Projekt ist aktiv/gesund und besitzt bereits Paper-Archivtabellen.
- V2R3 ist technisch als aktive Paper-Serie registriert: `PAPER-V2R3-FINAL-20260928T1752Z`.

## Phase A — direkt am Gerät, nur das Nötigste

1. Hardware prüfen: Netzteil, LAN, Monitor, Tastatur/Maus.
2. BIOS öffnen:
   - Datum/Uhrzeit plausibel.
   - `AC Recovery = Power On`.
   - Boot-/Secure-Boot-Einstellungen zunächst nicht unnötig verändern.
3. Windows starten:
   - Edition tatsächlich Windows 11 Pro bestätigen.
   - Windows Update vollständig durchführen.
   - Dell-Treiber/BIOS-Version prüfen und nur kontrolliert aktualisieren.
   - Zeitsynchronisation prüfen.
   - SSD-Zustand / freier Speicher / Ereignisanzeige grob prüfen.
4. Rechner eindeutig benennen.
5. Starkes lokales/Windows-Kennwort sicherstellen.
6. LAN-Verbindung prüfen.

## Phase B — interner Fernzugriff sehr früh

1. FRITZ!Box: dem Mini-PC eine stabile DHCP-Zuordnung/reservierte IPv4 geben.
2. Windows Remotedesktop aktivieren.
3. Netzwerkprofil/Firewall so prüfen, dass RDP nur im vorgesehenen privaten Netz erreichbar ist.
4. Vom Laptop im selben LAN per PC-Name und zusätzlich testweise per interner IP verbinden.
5. Neustart des Mini-PCs und erneuten RDP-Zugriff testen.

**Gate:** Erst wenn interner RDP-Zugriff nach Neustart zuverlässig funktioniert, wird die weitere Einrichtung überwiegend vom Laptop erledigt.

## Phase C — 24/7-Basis

- Schlafmodus/unerwünschtes Energiesparen deaktivieren.
- Automatischen Neustart/Wiederanlauf nach Stromverlust praktisch testen.
- Windows Update/Neustart-Verhalten kontrollieren.
- Defender/Firewall aktiv lassen.
- keine automatische Echtgeld- oder Trading-Ausführung.
- Verzeichnisstruktur anlegen:
  - Runtime
  - State
  - Logs
  - Temp
  - Archive/Backup
  - Secrets getrennt von Repo/Logs
- TTLs/Log-Rotation/Speicherlimits von Anfang an vorsehen.

## Phase D — externer Fernzugriff

Zielpfad:
`Laptop außerhalb Heimnetz → FRITZ!Box VPN/WireGuard → Heim-LAN → internes RDP → Mini-PC`

Regeln:
- keine direkte RDP-Portfreigabe ins Internet.
- VPN getrennt vom lokalen RDP testen.
- echter Außentest über Mobilfunk/iPhone-Hotspot.
- erst als bestanden markieren, wenn Verbindung nach Mini-PC-Neustart ebenfalls klappt.

## Phase E — Entwicklungs-/Runtime-Basis

Nach stabilem Remotezugriff:
1. Git installieren/verifizieren.
2. Python-Version bewusst festlegen und verifizieren; nicht blind mehrere Versionen mischen.
3. Repositories klonen:
   - `kraken-eur-scanner`
   - `kraken-readonly-bridge` nur soweit lokal nötig
   - archivierten `canonical-evaluator-runtime-v1` nicht als aktiven Runtime-Pfad verwenden.
4. Lokale Environment-/Secrets-Struktur anlegen.
5. Keine API-Secrets in Git, Slack oder Chat kopieren.
6. Tests/Smoke-Test zunächst read-only und paper-only.

## Phase F — Watchdog / Logging / Recovery

Vor Realtime-Strategie:
- Prozess lebt?
- Daten frisch?
- Queue bewegt sich?
- Output plausibel?
- stale/feed-disconnected/degraded/stopped unterscheiden.
- begrenzter Self-Heal nur für eindeutige technische Fehler.
- Neustart-Reconciliation testen.
- Internet-Ausfall + Wiederkehr testen.
- kein blindes Replay alter Kandidaten.
- Backup/Restore-Smoke-Test.

## Phase G — Daten und Integrationen

Reihenfolge:
1. Kraken Public REST/WebSocket lokal.
2. Altrady als **zusätzlicher** Trigger, nie exklusiv.
3. Supabase schlank als sekundäre State-/Ergebnisschicht. Dabei ausdrücklich prüfen, warum aktuell noch keine V2R3-Outcomes in `paper_candidate_outcomes` liegen; Sync-/Persistenzpfad erst nach E2E-Nachweis als funktionsfähig markieren.
4. GitHub/API/Slack.
5. ChatGPT Desktop installieren; Work nur für Aufgaben mit echtem Rechner-/Browserkontext.
6. Uptime Kuma/Grafana nur bei belegtem Zusatznutzen.

## Phase H — V2R3 → neue Infrastruktur → V2R4

1. V2R3 bleibt bis dahin unverändert.
2. Dieselbe V2R3-Logik kurz über die neue Infrastruktur shadow/smoke testen.
3. Latenz, Zeitstempel, Persistenz, Watchdog und Rückkanäle prüfen.
4. V2R3 vollständig auswerten und Erkenntnisse migrieren.
5. Draft-PR #8 / V2R4-Spezifikation gegen alle bis dahin gewonnenen Erkenntnisse prüfen.
6. Ein kleiner E2E-Paper-Smoke-Test.
7. Erst danach V2R4 als separate aktive Paper-Serie.

## Informationen, die erst am Gerät erhoben werden müssen

Diese Werte werden beim ersten Start erfasst und ins Versionsregister übernommen:
- Service Tag / genaue Hardware-Revision.
- aktuelle BIOS-Version.
- exakte Windows-Build-/Edition.
- SSD-Modell/Zustand.
- aktuelle interne IP/MAC.
- FRITZ!OS-Version der 7590 AX.
- tatsächlich verfügbare CPU-/RAM-/Disk-Auslastung im Grundbetrieb.
- installierte Python/Git/PowerShell/winget-Versionen.
- gemessene Latenz zu Kraken, Supabase und GitHub.
- Verhalten nach Stromverlust, Neustart und Internetunterbrechung.

## Work-Credits

- keine zusätzlichen Work-Credits vorsorglich kaufen.
- Basis-Setup, LAN, RDP, Energie und Sicherheit ohne Work erledigen.
- Work erst bei echtem Mehrwert für Browser-/Datei-/Desktopkontext verwenden.
- falls vor der regulären Freischaltung keine Credits verfügbar sind, erst dann gezielt nachkaufen.

## Inbetriebnahme-Stand 2026-09-30

Erster realer Aufbau des Dell OptiPlex 5060 Micro:

- Rechnername: `MINI-PC`.
- Windows 11 Pro gestartet und vollständig aktualisiert; automatische Updates bleiben aktiv, aggressive/optionale Vorschauupdates nicht priorisiert.
- Lokales Benutzerkonto mit Kennwort vorhanden; automatische Windows-Anmeldung für den 24/7-Betrieb eingerichtet.
- FRITZ!Box-DHCP-Reservierung: interne IPv4 `192.168.178.179`.
- Keine direkte RDP-Portfreigabe ins Internet.
- Windows Remotedesktop aktiviert; interner RDP-Test auf `192.168.178.179` erfolgreich.
- FRITZ!Box-WireGuard-Konfiguration auf dem Notebook eingerichtet; echter Außentest via Mobilfunk/iPhone-Hotspot noch offen.
- Windows-Energie: Bildschirm 15 Minuten, Standby = Nie, Ruhezustand = Nie, Energiesparmodus = Aus, Energiestatus = Ausbalanciert.
- BIOS: `AC Recovery = Power On` gesetzt. Praktischer Stromausfall-/Wiederanlauf-Test bewusst auf später nach finaler Geräteplatzierung verschoben.
- Dell Command | Update 5.7.2 installiert. Dell-/Intel-Treiberstand aktualisiert; danach meldet DCU „System auf neuestem Stand“. Geräte-Manager ohne gelbe Warnsymbole.
- Lokale Projektstruktur unter `%USERPROFILE%\Trading` angelegt: `Runtime`, `State`, `Logs`, `Temp`, `Archive`, `Backup`, `Secrets`, `Repos`.
- Git 2.55.0 und Python 3.13.15 installiert; `python` und `py` zeigen beide auf 3.13.15.
- Kanonisches Repository `hoffmannherdecke/kraken-eur-scanner` nach `%USERPROFILE%\Trading\Repos\kraken-eur-scanner` geklont.
- Repository-Check: Branch `main`, clean working tree, `origin` korrekt, Stand bei Commit `c6a93610` (`[paper-runtime] persist active-series state`).
- ChatGPT im Browser auf dem MINI-PC angemeldet, damit Befehle direkt kopiert werden können.

Noch offen aus diesem Block:
- echter externer WireGuard/RDP-Test außerhalb des Heimnetzes,
- praktischer Stromausfall-/Wiederanlauf-Test,
- SSD-/Ereignisanzeige-/Grundlast-Check,
- lokale Python-Runtime/venv und Smoke-Test,
- danach Watchdog/Logging/Recovery und Integrationen gemäß Runbook.

## Effizienzregel für weitere Inbetriebnahme

Ab 2026-09-30 gilt für die weitere MINI-PC-Inbetriebnahme:

- ChatGPT übernimmt alle Prüfungen selbst, die über GitHub, GitHub Actions, Supabase, Slack, öffentliche APIs/Marktdaten oder reine Code-/Konfigurationsanalyse möglich sind.
- Der Nutzer soll nur noch Tests ausführen, die zwingend den konkreten MINI-PC, dessen Windows-/Zertifikats-/Netzwerk-/BIOS-Zustand oder den echten Heimnetz-/VPN-Pfad betreffen.
- Mehrere lokale Einzelprüfungen werden nach Möglichkeit in einem einzigen read-only Sammeltest gebündelt.
- Dafür liegt `tools/minipc-selftest.ps1` im kanonischen Repo. Das Skript verändert keine Systemkonfiguration und schreibt nur einen Diagnosebericht nach `%USERPROFILE%\Trading\Logs`.
- Kein wiederholtes manuelles Copy/Paste einzelner Diagnosebefehle, wenn dieselbe Evidenz über den Sammeltest oder direkt aus verbundenen Systemen erhoben werden kann.

### Lokaler Sammeltest 2026-09-30 18:58

`tools/minipc-selftest.ps1` erfolgreich auf dem MINI-PC ausgeführt.

Bestätigt:
- Defender läuft automatisch; alle Windows-Firewallprofile sind aktiv.
- Ethernet-IP `192.168.178.179/24` aktiv.
- DNS-Auflösung für `api.kraken.com` funktioniert.
- TCP/443 zu Kraken erfolgreich.
- PowerShell-HTTPS gegen Kraken AssetPairs: HTTP 200.
- Repo und venv vorhanden; Git `main` auf `origin/main`, sauberer Status.
- Python 3.13.15 / pip 26.2.1 in der venv funktionieren.
- Python-HTTPS gegen Kraken AssetPairs: HTTP 200. Der zuvor einmal beobachtete `CERTIFICATE_VERIFY_FAILED`-Fehler ist damit aktuell **nicht reproduzierbar** und gilt nicht mehr als aktiver Blocker.
- Systemlaufwerk C: 237,4 GB gesamt / 185,1 GB frei.

Beobachtungen ohne aktuellen Blocker-Status:
- Ereignisanzeige enthält u. a. ältere DCOM-10010-Einträge, einen Intel-Grafikdienst-Timeout, einen TPM-WMI-1040-Eintrag sowie während der Einrichtung fehlgeschlagene Updateversuche. Diese werden vor Produktivsetzung nochmals gegen neue, nach der Einrichtung entstandene Ereignisse abgegrenzt.
- Die `Get-ComputerInfo`-Ausgabe meldet `Windows 10 Pro / WindowsVersion 2009 / Build 26200`; die tatsächlich verwendete Oberfläche/Einrichtung ist Windows 11. Exakte Edition/Build daher später einmal direkt mit `winver` bzw. einer zweiten OS-Abfrage verifizieren, bevor der Runbook-Punkt final geschlossen wird.

Damit ist Phase E (lokale Git/Python-Runtime + read-only Smoke-Test) im Wesentlichen bestanden. Offen bleiben vor allem die echten physischen/Netzpfad-Tests sowie Phase F/G.

### Watchdog / Logging / Recovery baseline prepared 2026-09-30

Cloud side verified:
- `.github/workflows/process-health.yml` runs on the scheduled watchdog cadence and performs bounded technical self-heal only; it cannot enable real-money actions or alter strategy.
- `.github/workflows/scanner-startup-recovery.yml` is an independent one-shot fallback for scheduled scanner `startup_failure`, with loop protection.
- Latest verified health audit after recovery: scanner successful, paper runtime successful, zero orphan candidates, zero overdue WAITs, zero missing position states. Remaining status is `WARNING` solely because V2R3 still has 0 `BUY_SCOUT` across 530 terminal decisions; that is a strategy/test finding, not an infrastructure failure.

Local baseline prepared in the repository:
- `tools/minipc-watchdog.ps1`: every-run local health probe for disk, repo/venv presence, DNS/TCP/HTTPS to Kraken, Python HTTPS/TLS path and Git identity. Writes only `Trading\State\minipc-health.json` and `Trading\Logs\minipc-watchdog.log`; no configuration changes, no process restart, no Git mutation, no trading action.
- `tools/minipc-log-cleanup.ps1`: bounded cleanup only inside `Trading\Logs` and `Trading\Temp` (defaults: 14 days / 2 days).
- `tools/install-minipc-baseline-tasks.ps1`: registers SYSTEM tasks `CryptoMiniPC-Health` (every 5 minutes + startup) and `CryptoMiniPC-LogCleanup` (daily 04:20), then performs an immediate health run.
- `tools/uninstall-minipc-baseline-tasks.ps1`: explicit rollback for both scheduled tasks.

Deliberately **not** enabled yet:
- no automatic restart/self-heal of a local scanner process until the concrete local runtime process/heartbeat contract exists;
- no automatic Git pull/reset;
- no Altrady dependency;
- no real-money execution.

Next local user action: pull the repository once and run the baseline-task installer from an elevated PowerShell. After its immediate health report is verified, Phase F baseline can be marked active.

