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
3. Supabase schlank als sekundäre State-/Ergebnisschicht.
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
