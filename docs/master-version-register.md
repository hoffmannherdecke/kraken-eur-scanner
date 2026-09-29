# MASTER VERSION REGISTER — Aktien & Krypto Chancen

Status: **KANONISCHE KOMPONENTEN-/VERSIONSÜBERSICHT**  
Stand: 2026-09-29  
Zweck: Single Source of Truth für Strategie, Paper, Infrastruktur, Datenpfade und Integrationen.

## Governance

- Kein relevanter Bestandteil wird nur über Chat-Erinnerung verwaltet.
- Jede Mechanik-/Infrastrukturänderung erhält eine eindeutige Version oder einen dokumentierten Draft.
- Eingefrorene Referenzstände bleiben unverändert.
- Unklare Zuordnungen werden als **NICHT VERIFIZIERT / ZUORDNUNG OFFEN** markiert; niemals raten.
- Vor einem Release: aktuelle Version vollständig auswerten → Erkenntnisse klassifizieren → relevante Erkenntnisse migrieren → Smoke-Test → Freigabe → Rollback-Punkt.
- Strategie- und Infrastrukturversionen werden getrennt geführt und miteinander verknüpft.
- V3 gilt erst dann als vollständig integriert, wenn jeder relevante V2/V2R4-Baustein einen Migrationsstatus besitzt.

## Strategie / Paper

| Komponente | Version / ID | Status | Rolle / nächste Aktion |
|---|---|---|---|
| Strategie | `V2R3-2026-09-28` | ACTIVE / PAPER / FROZEN | Aktive Vergleichsbasis; Regeln während Serie nicht ändern |
| Paper-Serie | `PAPER-V2R3-FINAL-20260928T1752Z` | ACTIVE | Aktuelle homogene V2R3-Serie; vollständige Abschlussauswertung vor V2R4-Go-live |
| Strategie | V2R4 | PREPARED / NOT ACTIVE / PAPER ONLY | Nächste operative Paper-Version nach Mini-PC-Basis + E2E-Smoke-Test; Draft-PR #8 |
| Strategie | V3 | ACTIVE RESEARCH / NOT ACTIVE TRADING | Integrierter Nachfolger; Issue #7 + `docs/v3-research-framework.md` |

### Release-Gate V2R3 → V2R4

Vor V2R4-Aktivierung zwingend:
1. V2R3 restlos und gründlich auswerten.
2. BUY/WAIT/REJECT/NO-TRADE, verpasste Chancen, Fehler, Latenzen, MFE/MAE, Kosten/Spread/Slippage und Infrastrukturprobleme berücksichtigen.
3. Erkenntnisse klassifizieren: bestätigen / ändern / neu / verwerfen / weiter testen.
4. Belastbare Erkenntnisse in V2R4-Spezifikation übernehmen.
5. Offene Hypothesen dokumentiert weiterführen.
6. Mini-PC-Infrastruktur separat per V2R3-Shadow/Smoke testen.
7. V2R4 erst danach als eigene Paper-Serie starten.

### Aktuelle neue Erkenntnis 2026-09-29

**„Ersten Impuls verpasst“ ≠ „Trade verpasst“.**  
Pflicht für Auswertung und nächste Version:
- Zeitachse: Bewegungsbeginn → Scanner-Erkennung → Entscheidung → realistischer Entry → weiterer Verlauf.
- Follow-up mindestens 15m / 1h / 4h / 12h / 24h, bei Bedarf mehrere Tage.
- MFE/MAE nach tatsächlicher Erkennung.
- Klassifikation: wirklich zu spät / Continuation / Pullback-Re-Entry / Second Leg / mehrstündiger Trend / korrekt kein Trade / Systemfehler.
- Scanner-Latenz getrennt von zu restriktiver Entry-/Revalidation-Logik messen.
- V2R4: als verpflichtende Mess-/Revalidation-Anforderung und – sofern vor Freigabe validiert – als explizite Paper-Entry-Variante aufnehmen.
- V3: Pflichtpunkt im Migrationsledger.

## Infrastruktur

| Komponente | Version / Stand | Status | Verknüpfung |
|---|---|---|---|
| Mini-PC Hardware | Dell OptiPlex 5060 Micro, i5-8500T, 16 GB, 256 GB SSD | RECEIVED / NOT CONFIGURED | künftige 24/7-Basis |
| Betriebssystem | Windows 11 Pro | TO VERIFY ON DEVICE | ermöglicht RDP-Host |
| Netzwerk lokal | LAN über FRITZ!Box 7590 AX | PLANNED | primärer Dauerpfad |
| Interner Fernzugriff | Windows RDP im LAN | PLANNED / EARLY SETUP | sehr früh nach Basis-Setup aktivieren |
| Externer Fernzugriff | FRITZ!Box-VPN/WireGuard → internes RDP | PLANNED | kein direktes RDP-Portforwarding |
| Stromausfall-Recovery | Dell BIOS AC Recovery = Power On geplant | TO CONFIGURE / TEST | 24/7-Wiederanlauf |
| Watchdog/Recovery | lokaler Supervisor + unabhängiger Fallback | PLANNED | keine Strategieänderungen durch Watchdog |
| Altrady | zusätzlicher Echtzeit-Trigger | PLANNED | niemals alleiniger Trigger/SPOF |
| Kraken realtime | Public REST/WebSocket lokal | PLANNED | primäre Marktwahrheit |
| GitHub Cloudpfad | bestehend | ACTIVE | unabhängiger Fallback bleibt erhalten |
| Slack Push | bestehender Pfad, echter iPhone-Push noch E2E nachzuweisen | OPEN | nur handlungs-/fehlerrelevante Pushs |
| ChatGPT Desktop/Work | Installation geplant; Work sparsam | PLANNED | Work nur bei echtem Desktop-/Browsermehrwert |

## GitHub

Aktuell verbundene Repositories:
- `hoffmannherdecke/kraken-eur-scanner` — aktiver Scanner/Paper-Hauptpfad und kanonischer Backlog.
- `hoffmannherdecke/kraken-readonly-bridge` — private read-only Kraken-Kontosnapshots.
- `hoffmannherdecke/canonical-evaluator-runtime-v1` — archivierter historischer Referenzpfad, nicht aktiv.

Wichtige Referenzen:
- `PROJECT_BACKLOG.md`
- `docs/strategy-version-map.md`
- `docs/v3-research-framework.md`
- Draft-PR #8 — V2R4 Fast WAIT Triggers / Mini-PC
- Issue #7 — V3 Research Track

## Supabase

Stand 2026-09-29:
- Projekt vorhanden und **ACTIVE_HEALTHY**, Region `eu-west-1`, Postgres 17.
- Tabellen:
  - `public.paper_series`
  - `public.paper_candidate_outcomes`
  - `public.paper_trade_results`
- Migrationen:
  - `20260928165535_create_paper_archive_tables`
  - `20260928173804_allow_unverified_paper_trade_status`
- RLS ist auf allen drei Tabellen aktiviert; aktuell existieren keine RLS-Policies. Das ist bis zur bewusst definierten Zugriffsschicht fail-closed und wird nicht vorschnell geöffnet.\n- **Aktuelle Integrationslücke:** Die vorhandenen `paper_candidate_outcomes`-Zeilen gehören derzeit zu `PAPER-V2R2-20260928T1640Z`; für die aktive V2R3-Serie ist noch kein Outcome dort archiviert. Das ist als Sync-/Persistenzpunkt beim Mini-PC/Supabase-Setup zu prüfen, nicht als Strategieergebnis zu interpretieren.
- Supabase bleibt sekundäre State-/Ergebnis-/Research-Schicht; kein Single Point of Failure und keine zweite Rohdatenkopie.

## V3 Migration Ledger — Pflichtstatus

Jeder relevante V2/V2R4-Baustein erhält genau einen Status:
- `INHERITED_UNCHANGED`
- `INHERITED_MODIFIED`
- `REPLACED_BY_TESTED_V3_COMPONENT`
- `REJECTED_WITH_EVIDENCE`
- `NOT_APPLICABLE`
- `OPEN_RESEARCH`

## Speicher-/Ablageregel für Chat-Beschlüsse

Wenn der Nutzer „bitte speichern“, „merk dir das“ oder sinngleich sagt:
1. Inhalt sichern.
2. Fachlich klassifizieren.
3. Der richtigen Komponente/Version/Registerebene zuordnen.
4. Abhängigkeiten dokumentieren.
5. Bei unklarer Zuordnung nicht raten, sondern **ZUORDNUNG OFFEN** markieren.
