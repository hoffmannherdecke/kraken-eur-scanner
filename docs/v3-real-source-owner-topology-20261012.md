# V3 reale Quellen-Owner-Zuordnung – 12.10.2026, Mini-PC + GitHub + Supabase

## Zweck
Der Nutzer hat auf dem realen Mini-PC per **READ ONLY** `Get-ScheduledTask` festgestellt, dass es keine eigenständig benannten H5-, H10- oder H11-Windows-Aufgaben gibt. Der einzige Treffer `ReconcileLanguageResources` ist ein fremder Windows-Systemtask, der wegen der ungenauen Teilzeichenfolge `Source` in `Resources` im Filter erschien. Das ist **kein Fehler und kein Grund für neue Mini-PC-Aufgaben**. Der Mini-PC war zum Zeitpunkt der Aufnahme noch auf Git-Commit `b37f87211` (PR #220), während PR #221 bis #228 auf GitHub bereits Code/Tests/Projektstatus aktualisierten; keine automatische Installation auf dem Host daraus ableiten.

## Was durch echtes Lesen belegt ist

| Baustein | Nachgewiesener aktueller Ort | Tatsächliche Befugnis | Explizit nicht bewiesen |
| --- | --- | --- | --- |
| **H10 Smart Money, 30-Min.-Erfassung** | Existierende GitHub-basierte Quelle, Supabase `public.v3_h10_capture_batches`, `v3_h10_fill_events`, `v3_h10_wallet_asset_5m`, `v3_h10_asset_consensus_30m`; `capture_path=GITHUB_BOOTSTRAP_30M` | Nur recherchierende Fill-/Wallet-/Konsens-Erfassung | Kein authentifizierter positiver Owner-Katalysator, kein angetasteter Scanner-Gate, kein BUY |
| **H10-Konsens-Lesefunktion** | Supabase Edge `v3-paper-h10-context-read`, Zustand `ACTIVE`, liest bestehende `v3_h10_asset_consensus_30m` | Autorisierte Ausgabe `H10_PIT_CONTEXT_ONLY`; erschafft keine neuen Fill-Signale | Keine eigenständige laufende H10-Quelle, keine geprüften Netto-BUY-Signale mit Self-Dealing-Check |
| **H11 Polymarket** | Bereits dokumentierte prospektive Fünf-Bücher-Erfassung im bestehenden Projekt | Raw-Market-/Kontextaufnahme | Kein nachgewiesenes direkt coin-positives Markt-Wahrscheinlichkeitsdelta samt zeitgleichem Kraken-Eintritt; kein dedizierter Windows-Task nachgewiesen |
| **H5 Makro/Kalender** | Bestehende projektinterne Makrokalender-/Kontextaufnahme | Kalender-/Ereigniskontext | Kein überprüftes aktuelles amtliches Primärereignis mit direktem Coin-Profiteur; kein dedizierter Windows-Task nachgewiesen |
| **V3 Single-Paper-Writer** | Nur offline geprüfte Module, plus erfolgreicher **einmaliger** realer Mini-PC-Scanner→Kraken→Cloud-ACK-Nachweis aus PR220/221 | Kein dauerhafter Writer aktiviert | Keine dauerhaft aktive V3-Quelle/Strategie, keine Modell-/BUY-/P4-/6h24h-Profitgarantie |

**Direktes Supabase-READ-ONLY-Ergebnis um 12.10.2026 11:32:14 UTC:** H10-Erfassung `HEALTHY`, beobachtet um 11:31:39 UTC; 401 gespeicherte Erfassungsbatches, 1.430 einzelne Fill-Events, 48 Batches in den vorausgegangenen 24h, 26 von 26 Wallet-Abfragen im jüngsten Batch erfolgreich, 0 Batch-Fehler. Der historische Fehlerbestand zeigt 2 ältere HTTP-Fehler vom 06.10.2026. `v3_h10_asset_consensus_30m` zeigte im zuletzt lesbaren PRIMARY-BTC-Zeitfenster **nur eine** unabhängige aktive Wallet: Das reicht ausdrücklich nicht für die V3-H10-Eintrittsregel mit mindestens drei unabhängig geprüften Wallets, mindestens USD 10.000 bestätigtem Netto-Buy, echter Fill-Herkunft und unabhängiger Nicht-Self-Dealing-Prüfung. Eine erfolgreiche 26-Wallet-*Abfrage* darf **nicht** zu 26 positiven Kauf-Wallets umdeklariert werden.

Supabase listet die bestehenden aktiven Edge-Dienste, darunter `v3-paper-evidence-relay` und `v3-paper-h10-context-read`. Ein erreichbarer Cloud-Endpunkt ist noch kein selbstständiger Quellen-Producer. Die Ausführung des GitHub-Bootstraps ist über vorhandene H10-Capture-Belege verifiziert; ohne eindeutige Workflow-/Owner-Sender-Referenz wird **keine einzelne GitHub-Workflow-Datei als bewiesen benannt**. `cron.job` ist in dieser DB nicht vorhanden; aus der Abwesenheit von `pg_cron` darf keine Aussage abgeleitet werden, dass ein existierender GitHub-Task nicht läuft.

## Architekturentscheidung / konkrete Folgearbeit

1. **Bestehenden H10-Collector unangetastet lassen.** Keinen zweiten H10-Scanner, Task, Mini-PC-Wallet-Poller, Edge-Producer oder neuen 30-Minuten-Zeitplan bauen. Erst die vorhandene GitHub-Owner-Prozessdefinition identifizieren; der jüngste H10-Capture belegt bereits tatsächliche Aktivität.
2. **Das echte Qualifikationsproblem zuerst lösen:** Pro eindeutigem H10-Coin und Originalereignis unabhängige Wallet-/Fill-Qualität, kausale Nettozuflüsse und Self-Dealing-Prüfung mit echter Primärprovenienz belegen. Nur dann die mit PR228 vorbereitete Signierfunktion auf dem **wirklichen Sender** mit getrennt verwahrtem Owner-Key ausführen. **Keine Schlüsselanlage oder Berechtigungsänderung nur aus dieser Analyse.**
3. **H11/H5 getrennt von H10 behandeln.** Nicht von Polymarket-Büchern/Kalendern auf einen vorhandenen unabhängigen positiven Signalproduzenten schließen; lediglich ihre bisherigen Kontextpfade weiterverwenden. Erfordert eigene fachliche Quellen- und Authentifizierungsevidenz.
4. **Genau EIN V3-Single-Writer:** Er prüft nach Signierung die Owner-HMACs nochmals, schreibt `SOURCE_INPUT:FIRST:UNKNOWN` und nur mit der echten Signatur `SOURCE_INPUT:OWNERAUTH:PASS` in dasselbe immutable Journal; anschließend nur auf tatsächlich frischen Kraken-Daten volle P0-Eignung, Modell **nur nach neuer konkreter Freigabe**, P4 und wirtschaftliche Folgen; separate exakte Cloud-ACKs. **Kein dauerhafter Writer, CAS/Paper-Wechsel oder Echtgeld durch diese Dokumentation.**
5. **28h-Original-Watcher respektieren:** Seine neun SHA-gepinnten Dateien und Endzeit 13.10.2026 14:00:12 MESZ bleiben unangetastet; lokal nicht reflexartig `git pull`, Tasks installieren oder gepinnte Pfade anfassen. Nach seinem fixen Ende physische Endprüfung und dann gezielte, sichere Aktualisierung – ohne unnötige Work-Schleifen.

## Statuslogik gegen spätere Vergessensfehler

- `PHYSICAL_ONE_SHOT_SCANNER_E2E_PASS`: RENDER/EUR 5 Cloud-ACKs, einmal physisch gezeigt und in Supabase geprüft.
- `H10_CLOUD_CAPTURE_ACTIVE_CONTEXT_ONLY`: echter 30m-Fill-Capture und Cloud-Reader, jedoch keine signierte positive H10-Quelle.
- `H11_H5_POSITIVE_SOURCE_RUNTIME_UNPROVEN`: rohe Kontexte, kein qualifizierter Live-Sender-/Signaturbeleg.
- `CONTINUOUS_V3_WRITER_NOT_ACTIVATED`: kein Beweis für permanenten V3-Single-Writer, kein Modell-/Paper-/BUY-Release.

**Followthrough:** im kanonischen `pending_strategy_transition.v3_original_intake_e2e_gate` und im existierenden 10:15-Work-/Meilensteincontroller; keine neue Erinnerung/Schedule. Erst die echten Source-Owner- und physische Runtime-ACK-Evidenz schließen die betreffenden Gates.
