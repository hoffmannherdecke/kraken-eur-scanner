# Projektweiter Ausfall- und Wiederanlaufvertrag v1 (08.10.2026)

**Gilt für alle gegenwärtigen und künftigen Krypto-Projektkomponenten.** Ein Drittanbieter-/Netz-/Strom-/Prozessausfall ist ein **normaler Betriebszustand**, kein Anlass für Strategieänderungen, künstlichen Datenersatz oder endlose Neustartketten. Diese Version ergänzt vorhandene einzelne Watchdogs; sie darf keine bestehenden Safety-/Release-/Frozen-Series-Gates umgehen. Die maschinenlesbare Domänenmatrix ist `research/global-outage-recovery-contract-v1.json`.

## Fünf technische Prinzipien

1. **Isolation / bulkheads:** GitHub privat nur Kontostand/Orderhistorie; öffentlicher Scanner, Mini-PC, Paper und H3/H10 bleiben unabhängig. Fehlende optionale Medien-/H*-Quellen = `UNKNOWN`, **niemals** neuer Kauf-Veto. Fehlen die autoritativen Kraken-Preise oder tradability = bestehende Kraken-Sicherheitsgates greifen; keine stale Fallback-Kurse.
2. **Persist before ACK:** Kandidaten/Event-IDs, `known_at`, UTC-Datum, WAL/Queue, einzelne Paper-Entscheidungen und TTL bleiben lokal stabil/atomar. Auf Supabase-500/429/Timeout nicht als `synced` markieren. Nach Rückkehr nur idempotent dieselben Schlüssel wiederholen, keine doppelte Paper-Order, keine doppelte Slack-Alert-/Work-Aufgabe.
3. **Zeit ist Teil der Wahrheit:** Gaps bleiben `GAP_UNKNOWN` / `NOT_EVALUABLE` / `MISSED_DURING_OUTAGE`. Prospektive Entries nie nachträglich aus altem Auslöser mit frischem Preis simulieren; unvollständiges MFE/MAE niemals 100 % vollständig deklarieren. Fällige Paper-WAIT-TTL sauber reconciliation/expiry, keine nachträglichen Trigger.
4. **Bounded self-heal:** Gespeicherte Restart-**Versuche** auch wenn Verifikation fehlschlägt; exponentielle Abkühlzeit bis höchstens 60 Minuten. Bei nachweislich nicht verfügbarem Kraken-Transport laufende abhängige Prozesse nicht wegen fehlender Tickdaten fortlaufend abschießen. Prozessstop/-start nur für erlaubte Tasknamen und idempotente lokale Inputs. Getrennt melden: Source down, Task down, Lag/backlog und tatsächlich akzeptierte neue Ergebnisse. Kein automatisches Vergrößern von Work-/GitHub-/paid-Quoten oder Aktivieren zusätzlicher Runner.
5. **Fachlich gesicherte Rückkehr:** `UPSTREAM_RECOVERED` ist nicht gleich `OUTPUT_VALID`. Reihenfolge: Quelle wieder erreichbar → fresh point-in-time → persistierte Inbox mit dedup + Altersregeln reconciliert → offene WAIT-/Follow-up-Fristen geprüft → Cloud-Acks gültig → zwei unabhängige reguläre Vital-/Output-Proben → `HEALTHY_RESTORED` oder `DEGRADED_GAP`. Nur tatsächlich gestörter Bereich eskalieren; korrekt verpasste Beobachtungen sind akzeptabel.

## Globaler State-Graph

`HEALTHY → SOURCE_DOWN / LOCAL_DOWN → RECOVERING → RECONCILING → HEALTHY_RESTORED → HEALTHY`.

Wenn unersetzliche Marktdaten fehlten: `RECONCILING → DEGRADED_GAP → HEALTHY_RESTORED` für **zukünftige** Samples; der historische Gap bleibt im Research erhalten. Wiederholte Recovery-Fehler mit Cooldown/echter Ursache → `ACTION_REQUIRED`, ohne Warmschleifen. Kein anderer Status darf ohne Nachweis als HEALTHY gemeldet werden.

## Versions- und Integrationsgates

- **Sofort umsetzbar ohne MINI-PC-Umschaltung:** verbindlicher Vertrag, maschinenlesbare Domänenmatrix, negative Tests, GitHub-Guard und Backlog. Keine neuen Zeitpläne oder heavy Work.
- **Kleiner local-only Sicherheitsfix im Repo:** `tools/minipc-runtime-supervisor.ps1` merkt auch unbestätigte Restartversuche und wendet persistierten Backoff an; bei gestörter Quelle kein mehrfaches Restart unnötig laufender abhängiger Prozesse. Muss vor lokaler Anwendung syntaktisch und technisch in einer kontrollierten MINI-PC-Runde geprüft werden.
- **Kleiner prospective-only Datenfix im Repo:** `tools/v2r4-paper-local-runtime.py` markiert uralte wiedergefundene Scanner-Events explizit als verpasste Evidenz (niemals nachträglich evaluieren) und lässt gültige frische Events unverändert. Grenze 15 Minuten entspricht dem bereits dokumentierten Prospektivitätsfenster des früheren Canonical-Bridge-Handovers; vor Deployment gegen V2R4-Timing/Latency und Paper-Freeze prüfen, kein heimlicher Regelwechsel.
- **Nachgelagert und komponentenweise ohne Architektur-Neustart:** einzelne noch unbelegte durable-Ack-/Backlog-/Status-Kanten der Matrix bei bestehendem jeweiligen Gate testen; künstlicher Netz- oder Stromausfall ausschließlich in isolierter Testumgebung, nie produktive Prozesse absichtlich unterbrechen. Pro Domäne genau ein E2E-Szenario für `SOURCE_DOWN→RECOVERING→ACK`, eine Rückstands-/Dedupe-Probe, eine ungültiger-Input-PIT-Probe und einen bereits gesicherten Restore-Pfad. First full matrix E2E **NOT YET VERIFIED**; verifizierte Stände nicht auf alle Domänen verallgemeinern.

## Hintergrund – Beobachtung vom 08.10.

Privates GitHub-Konto-Snapshot war etwa 71 Min. nicht verfügbar, während öffentliche Scanner/Paper/Shadow/Supabase weiterliefen. Unabhängig zeigte der Mini-PC `WARNING/DEGRADED`, lokale V2R4WSShadow/Windows-PaperCandidates wurden vom Supervisor wiederholt neu gestartet; ob das kausal mit GitHub zusammenhängt, ist **nicht belegt**. Aktive PAPER-V2R4 und H3-Shadow bleiben eingefroren.

**Stop-Regeln:** Keine Orders, kein ungefragter Live-/PAPER-Release oder aktive Strategy-Threshold-Änderung; kein höheres Secret-Recht, kein zusätzlicher Scheduler/Work-Run, keine private Kontodatenkopie ins öffentliche Repo. Die Probe für neue Safety-Codeversion ist erst nach kontrolliertem Mini-PC-Test und separate Freigabe abgeschlossen.
