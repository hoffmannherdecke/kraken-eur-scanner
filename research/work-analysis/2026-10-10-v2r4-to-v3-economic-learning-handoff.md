# V2R4 → V3: wirtschaftliche Lernübergabe vor dem Strategiewechsel (10.10.2026)

**Art:** abgegrenzter read-only Nachtrag zum *bereits abgeschlossenen* originalen 72h-Gate (PR #144). **Disposition:** `ECONOMIC_NOT_DEMONSTRATED / RETAIN_RISK_GUARDS / PRIORITIZE_INPUT_ONLY_V3_A`. Dies ist **kein** zweites 72h-Abschluss-ACK und kein V3-Release-PASS. Keine aktive V2R4-, H3-, H6-, Paper-, Shadow- oder Echtgeldänderung.

## Quellen und Beobachtungsgrenze

Supabase `public.paper_series`, `paper_candidate_outcomes` (initiale `payload.decision.decision`, `payload.recheck.kind`, `followup.opportunity_audit.horizons.1440`), `paper_trade_results` und `paper_series_completion_readiness`, autorisiert **nur lesend** am 10.10.2026 gegen 20:05 UTC abgefragt. Die feste **erste-Entscheidung-Kohorte** ist `evaluated_at < 2026-10-10T20:00:00Z`; Snapshotwerte können sich durch nachträglich gereifte Follow-ups/Rechecks weiter ändern. Supabase bestätigt nur einen aktiven V2R4-Paper-Abschnitt, **keinen aktiven V3-Shadow/Release**. Vorgänger und Folgeserie sind disjunkte technische Abschnitte **derselben V2R4-Strategie** (unveränderter Fingerprint), keine zwei unabhängigen Strategieversuche.

| Evidenz | Stand dieser Kohorte |
|---|---:|
| Vorgänger `PAPER-V2R4-20261007T184255Z` (technisch geschlossen) | 1.011 Kandidaten |
| Aktiver technischer Abschnitt `PAPER-V2R4-20261009T110135Z` | 685 Kandidaten |
| Insgesamt / Paare | **1.696 einzigartige Kandidaten / 96 Paare** |
| Erste Entscheidung WAIT / REJECT / BUY | **1.096 / 600 / 0** |
| WAIT → TTL ohne Modell-Recheck | **956** (87,2 % von WAIT) |
| WAIT → echter deterministischer Trigger + Modell-Recheck | **127** (11,6 % von WAIT; **0 BUY**) |
| Noch offener WAIT ohne dokumentierten Recheck/TTL | **13** |
| Persistierte Paper-Trades | **0** |
| Strukturiertes Coin-Entry-Evidence-Feld am Erstentscheid | **0/1.696** |
| Vollständig gereifte 24h-Follow-ups | **436** |
| 24h zwischenzeitliches MFE ≥ +5 % / MAE ≤ −5 % | **178 / 300** |
| Dieselben Fälle mit *beiden* Extremen | **98** |
| **Nur optimistischer Suchproxy**: MFE ≥ +5 %, MAE ≥ −3 %, 24h-Schluss > +1,2 %, Eingangsspread ≤ 0,5 % | **32 Ereignisse in 24 Paar-Stunden** |

**Denominator-Kontrakt:** Kandidat-ID statt Recheck-Event zählen. Bei 1.096 WAIT gelten 956+127+13=1.096. Die **436 reifen** sind keine 1.696 vollständig ausgewerteten Fälle. MFE/MAE sind vom **ursprünglichen Ask** rückblickend beobachtete Bewegungen – nicht tatsächlicher Einstieg, Fill, Netto-Gewinn oder beweisbare Stop-Reihenfolge. Paar-Stunden sind ein erster Cluster-Schutz, kein unabhängiges Trade-Sample. Der Proxy setzt lediglich die **1,20 % Roundtrip-Takergebühren** (0,60 % pro Seite) als Grobhürde an; er enthält **keinen** belegten tatsächlichen Entry, Stop, Spread-/Slippage-Abzug, Stage-2-Fill oder Exit. Der Proxy **darf nicht** als 32 Gewinne bezeichnet werden.

## Übertragbare Ursachenhypothesen und Schutzbefunde

1. **Zwei getrennte Konversionsengpässe, keine Einzelursache behaupten.** 87,2 % der initialen WAIT-Fälle enden ohne echten Modell-Recheck; die 127 tatsächlich revalidierten Fälle enden ebenfalls ohne BUY. V3 muss daher *sowohl* Trigger-/TTL-Abdeckung *als auch* Entscheidungsfähigkeit **nach einem legitimen Trigger** nachweisen. Bloß mehr Scanner-Kandidaten oder schnellere GitHub-/Mini-PC-Läufe lösen die beobachtete Modell-zu-BUY-Nullrate nicht.
2. **Verifizierter Feature-Handoff-Mangel, Ursache der Null-BUY-Rate aber noch nicht kausal bewiesen.** Alle 1.696 initialen Decisions haben Kraken-EUR-Ticker/Broad-Market-Kontext, jedoch kein strukturiertes `candidate_entry_evidence` mit zur damaligen Uhrzeit geschlossenen **coin-eigenen** 1m/5m/15m-Kerzen, Volumenrelation, ATR14 und lokalem Risikotief im Evaluator-Kontrakt. Auch preislich begründete Stop-/Stage2-Preise liegen initial nicht vor. Die bestehenden WAIT-Sensor-Kerzen können trotzdem technisch vorhanden sein – **Verfügbarkeit irgendwo** ist nicht **belegter PIT-Feature-Input beim Modell**. Das ist der kleinste sinnvolle V3-A-Test: **ein** zusätzlicher, bereits vorbereiteter deskriptiver Eingang, sonst gleicher Evaluator/WAIT/Risiko.
3. **Anti-Chase/Verlustvermeidung nicht versehentlich ausbauen.** Unter 436 gereiften 24h Fällen fielen **300** zwischenzeitlich um ≥5 % vom Ausgangs-Ask; 98 zeigten *beide* Richtungen um mindestens 5 %. Die Kategorie `EXTENDED` umfasst **861** Kohortenkandidaten; 270 haben gereifte 24h, davon **195** mit MAE ≤−5 % und **111** mit MFE ≥+5 % (überlappend). Das weist auf sehr volatilen, pfadabhängigen Handel hin; es ist **kein** Anlass, EXTENDED pauschal freizugeben oder den Stop-/Spread-/Fee-Schutz abzubauen.
4. **Verpasste Chancen als Kandidatenliste, nicht als Profitnachweis.** Die 32 retrospektiven „günstigen“ Proxies sind nur Kandidaten für einen strikt bekannten-zum-Zeitpunkt-Pfadvergleich. Neue V3-Käufe müssen **vor** späterem Kursverlauf mit echtem Kraken-EUR Ask/Spread, kausaler Kerzenzeit, plausibler Struktur-/ATR-Invalidierung, stop-basiertem EUR-Risiko, ggf. Stage2 und **nach Kosten** erzeugt werden. Adverse/False-BUY-Rate, nicht nur BUY-Anzahl, muss gegenüber Baseline kontrolliert werden.
5. **Keine verdeckte V3-Vollfreigabe.** H1-Standalone bleibt verworfen, H3-001 archiviert/inconclusive, H6 separat gesperrt; Volume-Kontext im Coin-Entry-Adapter ist **keine zusätzliche H6-Stimme** und ATR ist **keine automatische H4-Stop-Policy**. Optionales Derivate-/Smart-Money-/News-Material darf die Kraken-EUR-Preisautorität nicht ersetzen. Tatsächliche kontospezifische Handelbarkeit ist aus öffentlichem Kraken-Paarstatus allein nicht bewiesen.

## Konkreter, begrenzter V3-Übergabeauftrag

- **A – zuerst, kein kompletter V3-Start:** `MINIPC_ANALYTICS_ROLLOUT_V1` / vorhandene `paper_evaluator/successor_coin_entry_evidence_v1.py` und `tools/run-minipc-v3-entry-model-compare.ps1`. Ein realer bekannter Kandidat, striktes `known_at ≤ Entscheidung`, vollständige geschlossene Coin-Bars, Volume, ATR, Local-Low, Null-/Stale-/Mismatch-Negativfall; isoliert **gleicher** V2R4-Evaluator und WAIT/TTL/50+50/Fees. Keine neuen Daueraufgaben oder Datenquellen. Fehlende Daten `UNKNOWN`, kein erfundener Trigger. Mini-PC-Physik-E2E noch **nicht** belegt.
- **B – nur bei befundener A-Evidenz:** Falls selbst mit PIT-Coin-Evidence weiterhin kein ökonomisch vertretbarer BUY entsteht, die existierende `EXTENDED`-Second-Leg-*Recheck-Zulassung* als **separaten** einzigen Policy-Unterschied testen; nicht einfach Preise jagen oder 5m-Volumen-/Strukturtrigger pauschal lockern. Auch dann neuer unveränderlicher Vergleichs-Fingerprint, gleicher Kandidat/Snapshot.
- **C – alleiniger prospektiver ökonomischer Beweis:** Nur mit eigener Nutzer-/Release-Freigabe **ein** neuer strategieändernder Shadow, nicht zwei Paper-Writer. Vergleiche prospektiv passende Paar-/Zeitkohorten über WAIT→Trigger→Recheck→BUY→Fill→Stop/Stage2/Exit und Netto nach 0,60 %/Seite, Spread/Slippage, 6h/24h MAE/MFE, Fehlkäufe, falsche REJECTs, Datenlücken. Bei 0 BUY nach hinreichender Reife erneut **ökonomisch** stoppen/gezielt disponieren, nicht künstlich verlängern.
- **V2R4-Cutover separat:** Nutzer will keine unbefristete Null-Trade-Sammlung. New-Intake stoppen erst durch geprüfte physische Lifecycle-/Single-Writer-Sequenz, mit Abschluss offener Follow-ups und Erhalt der technischen Linien. Bis verifizierter Umstellung ist V2R4 **aktiv**. Ein Dokument-Merge beendet keine Runtime.

**Kanonische Vererbung:** `research/v3-migration-ledger.json` Komponenten `v2r4_event_driven_wait_wakeup`, `coin_specific_entry_evidence_provenance`, `late_chase_protection` und `stop_trailing_ttl_exit_logic`; Entscheidungs-/Freigabehärte in `research/strategy-learning-causal-gate-v1.json`; Ausführungseingang `PROJECT_BACKLOG.md#MINIPC_ANALYTICS_ROLLOUT_V1` und `docs/minipc-analytics-rollout-v1.md`. Keine doppelte neue Strategie-/Backlog-Instanz.

**Abschlusskategorie dieser Aufgabe:** `LEARNING_HANDOFF_COMPLETED_EVIDENCE_ONLY`; `V3_PHYSICAL_E2E_UNVERIFIED`; `V3_ECONOMIC_EDGE_UNPROVEN`; `V2R4_INTAKE_STILL_ACTIVE`.
