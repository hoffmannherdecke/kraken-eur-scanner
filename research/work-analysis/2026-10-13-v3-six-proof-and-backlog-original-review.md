# V3-Experimental-Paper: Sechs-Proof-Audit und drei historische Originaldispositionen (13.10.2026)

## Zweck und Grenze

Dieser Review konsumiert den neuen projektweiten Router erstmals nachweisbar. Er verändert keine Runtime, keinen Scheduler, keine aktive Paper-Serie und kein Modellbudget. Zum Prüfzeitpunkt **2026-10-13T08:19:49Z** lag das feste Ende der V3-28h-Beobachtung (**2026-10-13T12:00:12.2795431Z**) noch in der Zukunft. Deshalb werden weder physischer Task-Stopp noch neun SHA-Pins noch ein 24h-Cloud-Abschluss vorzeitig quittiert.

V2R4 bleibt alleinige aktive Paper-Strategie; V3 bleibt `BLOCKED_RELEASE_EVIDENCE_NOT_V3_RUNNING`; Echtgeldaktionen bleiben gesperrt.

## PROJECT_CONTEXT_REVIEW_V1

- scopes: `strategy`, `architecture`, `operations`
- commitment_intake: `V3_EXPERIMENTAL_PAPER_SIX_PROOFS`, `historical_backlog_reconciliation`
- Quellen: `project-current-state.json`, `PROJECT_BACKLOG.md`, `docs/v3-controlled-paper-cutover-20261011.md`, `docs/v3-28h-canary-evidence-review-20261013.md`, `tools/v3_experimental_paper_technical_gate.py`, `tools/strategy_successor_gate.py`, Routing und Work-ACK
- nicht ersetzbare Autoritäten: Mini-PC-Task-/Supervisorzustand, vollständige Supabase-Einzelquittungen und explizites Budget-/Release-Gate
- Grenze: Dokumentation/Deduplizierung; keine Aktivierung oder Strategieänderung

## Router-/Work-Handoff

Der aktuelle Router wurde konsumiert und priorisiert korrekt `V3_EXPERIMENTAL_PAPER_SIX_PROOFS`. `V3_CANARY_28H_PHYSICAL_CLOSURE` ist vor seinem festen UTC-Termin nicht fällig. Als zweite sichere Aufgabe wurde ein historischer Dreierblock anhand der Originale geprüft. Der Router-Handoff dieses Laufs ist damit bewiesen; ein physischer V3-Release ausdrücklich nicht.

## Sechs technische Proofs

Der Validator akzeptiert nur sechs eigenständige Zeilen mit `VERIFIED_PHYSICAL_OR_CLOUD_E2E`, vorhandenem `research/`-Artefakt und passender SHA-256. Die Release-Datei `research/successor-strategy-release-evidence-v1.json` fehlt auf `main`; das ist aktuell korrekt fail-closed.

| Proof-ID | Belastbarer Stand | Disposition / nächster Originalbeleg |
|---|---|---|
| `V3_REAL_MODEL_COIN_PIT_P4_INPUT_E2E` | Inaktive Full-Decision-Implementierung und ZRO Modell/P4=`WAIT` sind Kontext, aber keine dedizierte Release-Zeile | **OPEN_REGISTERED** — Original-Request/Response, Coin-PIT, P4 und Pins als eigene Cloud/Host-Evidenz hashen |
| `V3_FAIL_CLOSED_STOP_STAGE2_FEE_WAIT_CONTRACT` | Code/CI und Negativtests, kein realer Host-/Cloud-Pfad | **OPEN_REGISTERED** — echter Pfad mit Stop<Ask, Stage2>Ask, 0,60 % je Seite, Spread/Slippage und WAIT/UNKNOWN-Fail-Closed |
| `V3_JOURNAL_REASONS_ERRORS_6H24H_FOLLOWUP_CENSURE` | 6h EIGEN/ZRO korrekt censored; 24h im letzten belegten Snapshot noch nicht fällig | **OPEN_REGISTERED** — nach 12:00:12Z vollständige Cloud-Einzelquittungen prüfen; fehlend/censored nie als 0-PnL |
| `V3_SINGLE_WRITER_FENCE_CLOUD_CAS_DRYRUN` | RENDER-One-shot belegt Struktur, nicht kontinuierlichen Writer/Cutover-Fence | **OPEN_REGISTERED** — exklusiven Writer/CAS/expect-predecessor-Dry-run und Rückweg physisch belegen |
| `V3_MINIPC_SUPERVISOR_STOP_START_ROLLBACK` | Runbook/Tests vorhanden; physischer ACK fehlt | **OPEN_REGISTERED** — nach fester Endzeit Task-Ende, Supervisor, neun Pins und Rollback prüfen |
| `V3_GITHUB_WORK_ALERT_DYNAMIC_SERIES_ROUTING` | Routing Code/CI-seitig vorbereitet | **OPEN_REGISTERED** — Consumer-Readback auf physisch/cloudseitig verifizierte V3-Serie |

**Ergebnis:** 0/6 liegen als eigenständige `VERIFIED_PHYSICAL_OR_CLOUD_E2E` Release-Zeilen vor. Das negiert Vorarbeiten nicht, verhindert aber die Gleichsetzung von Code/CI/One-shot/Canary-Zwischenstand mit Releasebeweis. Nächster objektiver Gate: unverändertes Fensterende plus danach möglicher read-only Host-/Cloud-Abgleich.

## Historischer Originalabgleich — erster Dreierblock

Originalsnapshot: `PROJECT_BACKLOG.md` Blob `c589eea9225193397e9ca5dc719f13f44b221afa`. Abschlussautorität: `research/work-analysis/2026-10-07-v2r3-final-review.md` Blob `76c88d0f2583824cb90c57dc00fdbabc26c9539d`; Dispositionen: `research/v2r3/strategy-adjustment-hypotheses-final-20261007.json` Blob `052ccf72d8e4c014cb4e116e9cb75d3a78027863`.

| Original-ID | Verifikation | Endstatus |
|---|---|---|
| `PROJECT_BACKLOG@c589...:L548` | Frozen 1.000er-Kohorte, eine Fingerprintlinie, Intake gestoppt, 946 vollständige 24h-Followups, Finalreview; Master-Register: `CLOSED_COMPLETE / FROZEN` | `COMPLETED_VERIFIED` |
| `PROJECT_BACKLOG@c589...:L550` | Finalreview wertet WAIT, REJECT, BUY_SCOUT, einzigen Trade und 945 reife REJECT-Pfade gemeinsam aus | `COMPLETED_VERIFIED` |
| `PROJECT_BACKLOG@c589...:L551` | Finalreview verbindet 30/60/120/360m/24h MFE/MAE, Missed-Move-/Episode-Dedupe, Stop-Trade und Gebühren; die Ein-Trade-Grenze wird ehrlich als nicht kalibrierbar ausgewiesen | `COMPLETED_VERIFIED` |

Die drei historischen Checkboxen dürfen geschlossen werden. Das reaktiviert V2R3 nicht. Die verbleibenden 79 Vorsortierungen bleiben ungeprüft.

## Ergebnis

- **ERLEDIGT MIT ORIGINALBELEG:** Router-Konsum; drei V2R3-Unterpunkte.
- **UMGESETZT CODE/CI ABER NICHT LIVE:** Teile des V3-Evaluator-, Guard- und Routingpfads.
- **WEITER OFFEN:** sechs physische/cloudseitige Proof-Zeilen; Budget-/Release-Entscheidung; Single-Writer-Cutover.
- **EXAKTER ZEITBLOCKER:** finales 28h-Task-/Pin-/Cloud-ACK nicht vor `2026-10-13T12:00:12.2795431Z`.
- **Nächstes Gate:** danach einmal den vorhandenen read-only Canary-Report mit echten Supabase-Einzelzeilen und physischem Mini-PC-End-ACK ausführen; keine automatische Aktivierung daraus ableiten.

---

## Unabhängiger Live-Nachtrag 14.10.2026, 13:14 UTC / 15:14 MESZ

**Art:** neue, ausschliesslich lesende Supabase-Originalprüfung NACH festem 28h-Ende 13.10. 12:00:12.2795431 UTC. Kein Projektzustands-, Budget-, Scheduler-, Paper-, GitHub-Workflow- oder Mini-PC-Änderungsbeleg. Unveränderte Originalphasen: `public.v3_paper_event_receipts`; einzige aktive Paper-Serie aus `public.paper_series`; V2R4-Entscheidung und Tradingdaten aus `public.paper_candidate_outcomes` und `public.paper_trade_results`. Messzeit `select now()` = `2026-10-14 13:14:06.773373+00`. **Achtung:** GitHub/Cloud-Abfrage allein kann den physischen 28h-Watcher-Task-End-ACK oder die neun Original-Pins nicht bestätigen.

### Nach dem Zeitfenster tatsächlich erhaltene Cloud-Originalquittungen

| Kohorte | Immutable Cloud-Event-IDs | Kandidaten | Status |
| --- | ---: | ---: | --- |
| `PAPER-V3-CANARY-20261011` | **16** (=16 eindeutige `event_id`) | **2**, EIGEN/EUR und ZRO/EUR | Je **ein** `FOLLOWUP_6H=CENSORED` und `FOLLOWUP_24H=CENSORED`, keine `P4_VALIDATION=BUY_SCOUT` und kein `PAPER_FILL` |
| `PAPER-V3-CANARY-WRITER-SMOKE-20261012` | **5** (=5 eindeutige `event_id`) | **1**, RENDER/EUR | Isolierte One-shot-Smokekohorte, kein ersetzender aktiver V3-Writer und kein wirtschaftlicher Full-Model-Fill |

Für **alle vier** gespeicherten 6h-/24h-Einzelquittungen gilt **unverändert**:
`result=CENSORED`, `payload.data.censor_reason=CENSORED_NO_CONTIGUOUS_CLOSED_KRAKEN_1M_PATH`,
`payload.data.path_contiguous_1m_verified=false`,
`payload.data.position_net_pnl_eur=null`.
Die 24h-Quittung EIGEN wurde am **13.10. 06:30:16 UTC** und ZRO am **13.10. 07:45:15 UTC** gespeichert. Die Fristen wurden fachlich erreicht; die tatsächlichen geschlossenen 1m-Preiswege bleiben jedoch lückenhaft. **Nicht zu `0 EUR`, vollständigem Trade-Followup oder nachträglichem MFE-PnL umetikettieren.** Die 72h-Nachbeobachtung wird getrennt verfolgt und verlängert das bereits abgelaufene 28h-Fenster nicht künstlich.

### Originaler produktiver V2R4-Vergleich (kein neues Null-BUY-Wartegate)

`public.paper_series`: Genau **eine aktive** Serie `PAPER-V2R4-20261009T110135Z`; der Vorgänger `PAPER-V2R4-20261007T184255Z` ist `technical_closed`, mit identischer V2R4-Strategierevision. Keine aktive V3-Serie.

Über beide disjunkten V2R4-Abschnitte (echter Strategie-Epochenvergleich, nicht nur technisch rotierte Serie): **3.453 Outcomes, davon 3.439 REJECT, 14 WAIT und 0 BUY** zum Prüfzeitpunkt. `public.paper_trade_results` enthält **keinen V2R4-Trade** (ein historischer V2R3-Trade ist separat erfasst). Dies bestätigt die weiterhin fehlende V2R4-Handelsproduktivität trotz wiederhergestellter Mini-PC-Gesundheit; keine automatische Lockerung von Filtern, Gebühren- oder Stop-Regeln.

### V3-Paper-Release-Gate: tatsächlicher nächster Owner-Schritt

1. **Erreicht:** Tatsächliche 24h-Originalquittungen beider Canary-Kandidaten sind nun read-only nachvollzogen; der bisher nur vor der 24h-Fälligkeit vorhandene Zwischenstand ist abgelöst. Damit endet **nur die Zeitsperre für eine technische Abnahme**, nicht der physische Gate-Bedarf.
2. **Nicht nachgewiesen:** Originaler V3-28h-Windows-Task-Stop (kein heimlicher Restart), alle **9** unveränderten SHA-256-Pins, lokaler Intake/Journaling-/ACK-Abschluss, vollständiger geschlossener Kraken-1m-Kurspfad und sechs **jeweils einzeln** unabhängige technische Paper-Proofs. `research/successor-strategy-release-evidence-v1.json` ist weiterhin **nicht** auf `main`; `0/6 VERIFIED_PHYSICAL_OR_CLOUD_E2E` als Release-Paket, nicht etwa 0 erledigte Code-Vorarbeiten.
3. **Nächster sofort zulässiger Schritt:** Den **bestehenden** `tools/check-minipc-v3-physical-writer-readiness.ps1` und die originale 28h-Task-/9-Pin-/End-ACK-Prüfung **einmal read-only auf dem Mini-PC** gegen die echten Dateien abgleichen; aktuelle Cloud-/Serien-Quittungen unabhängig daneben halten. Die technische V3-CAS-/Single-Writer-Übernahme, Live-Full-Model-Budget und echter V2R4-Intake-Stopp bleiben separate reale Freigabegates.
4. **Nur nach realem fehlenden Beleg:** Bereits vorbereiteten `tools/v3-post-canary-evidence-readonly-report.py` mit den **vollständigen einzelnen** Cloud-Originalzeilen ausführen, nicht mit diesem Kurzbericht oder synthetischen `cloud_rows`. Fehlende unabhängige Quellen-/Hash-/Hostbelege als `OPEN` benennen und nicht als `PASS` erfinden. Reproduzierbare Abnahme ohne zweiten Scheduler, zusätzlichen Shadow-Writer oder weitere künstliche Wochen.
5. **Separate Operationsarbeit:** Gemeinsames Kraken-Public-REST-Budget PR292/PR294 bleibt nach dokumentiertem Stand physisch **nicht enrolled**; zuerst bestehendes SYSTEM-Owner-/Fingerprint-/Rollback-Gate. Die erfolgreiche PR299–301 WS-Shadow-Reparatur ist kein REST-Budget-ACK und keine V3-Freigabe.

**Disposition:** `V3_POST28H_CLOUD_6H24H_CENSORING_READ_ONLY_REVIEWED`; `V3_PHYSICAL_END_ACK_PENDING`; `V3_EXPERIMENTAL_PAPER_RELEASE_BLOCKED_6_INDEPENDENT_PROOFS`; `V2R4_ECONOMIC_NOT_DEMONSTRATED_3453_OUTCOMES_0_BUY_0_TRADE`. Fachlicher Owner bleibt das bestehende V3-P0/P1-Cutover-Gate mit täglichem 10:15-Work und Projekt-Meilensteincontroller – **kein neuer Owner, Task oder Termin**. Echtgeld aus, 50+50 EUR V2R4 Paper unverändert.

---

## Physischer Original-Task-Nachtrag 14.10.2026, Nachmittag MESZ

**Quellentyp:** Originaler **read-only** `Get-ScheduledTask` / `Get-ScheduledTaskInfo`-Readback aus der Administrator-PowerShell am Mini-PC (Nutzerfoto). Abgleich mit vorangehender lokaler `check-minipc-v3-physical-writer-readiness.ps1`-Ausgabe und festem originalem Plan; keine Änderung am Host, den neun gepinnten Dateien oder der V3-Release-Freigabe.

| Tatsächlicher Originalwert | Mini-PC-Readback |
| --- | --- |
| Originale Windows-Task-Identität | `CryptoMiniPC-V3CanaryObservation28h` |
| Task-State / Last-Result | `Ready` / `0` |
| LastRun (lokal) | `2026-10-13 13:55:13 +02:00` = `11:55:13Z` |
| NextRunTime | Leer – kein zukünftiger Lauf eingetragen |
| Exakte Zahl Aktionen/Trigger | `1 / 1` |
| Aktion entspricht ursprünglichem Observer | `True` |
| Action-Argumente enthalten `plan.until_utc` | `True` |
| Original-Triggerstart | `2026-10-12T10:00:12+02:00` = `08:00:12Z` |
| Original-Trigger-Repetition.Duration | `P1DT4H` = **28 Stunden** |
| Computed trigger end in UTC | `2026-10-13T12:00:12Z` |
| Unveränderte Manifest-Deadline | `2026-10-13T12:00:12.2795431Z` |
| Abweichung Triggerend/Manifest | ca. **0,28 Sekunden** |
| Letzter Lauf vor geplantem Ende | ca. **4m59s**, LastTaskResult `0` |
| Lokaler Checker enthält die neuen Task-Ausgabefelder? | `False` – ältere lokale read-only Version |
| Vorherige originale Pins/Journaling/ACK | **9/9** Hashes ohne Abweichung; **16** lokale Journal-Quittungen und **16** lokale Cloud-ACKs |
| Vorherige aktive V2R4-Host-Runtime-Konfigurationen | **1**; dies ist kein eigenständiger Writer-Prozess-Fence-Beweis |

**Ursache der vorherigen `null`-Felder:** Der lokale Readiness-Checker ist älter als das aktuelle GitHub-Skript. Die vorher verwendete `Select-Object`-Ausgabe legte nicht vorhandene Eigenschaftsnamen als `null` an; dies war **kein Hinweis auf einen kaputten Original-Task**.

**Gates:** Die Original-Scheduler-/Manifestbedingungen erfüllen inhaltlich den bestehenden **`canary_scheduler_end_candidate_for_independent_review=true`**-Ausdruck: Task `Ready`, letzte Ausführung erfolgreich vor Termin, kein nächster Trigger, exakt eine passende Aktion/ein passender Trigger und 28h-Ende innerhalb 120s Deadline sowie 9 unveränderte SHA-Pins. Eine nochmalige 28h-Beobachtung ist dadurch nicht angezeigt. Die gesonderte **`canary_physical_observer_end_ack_from_this_single_readback`**-Autorisierung bleibt ausdrücklich **`false`**: Eine spätere, unabhängige Ende-ACK-Provenienz ist nicht allein durch diesen Screenshot materialisiert; der Aufgabenplan ist nicht mit sechs eigenständigen V3-Release-Belegen gleichzusetzen.

**Nächste bestehende Aufgabe:** Den physischen Endkandidaten unter dem vorhandenen V3-P0/P1-Owner gegen die **unveränderten Cloud-Einzelquittungen** einordnen und die sechs realen technischen Proof-Zeilen als `VERIFIED_PHYSICAL_OR_CLOUD_E2E` ausschließlich je eigenem unabhängigen Artefakt/Fingerprint vergeben. Priorität: originaler EIGEN/ZRO-Journal-/Cloud-/Censor-Nachweis; Single-Writer-CAS-Dry-run; V2R4 Writer-Fence; eingeschränkte Model-API-Kosten; Stop/Stage2/Fee/WAIT; Work/Alert-Consumer. Weiterhin **0/6 formal freigegebene Release-Beweiszeilen** nach dem derzeitigen Artefaktstand – bereits erfüllte Vorleistungen ausdrücklich nicht wiederholen.

**Disposition:** `V3_28H_ORIGINAL_TASK_SCHEDULE_END_CANDIDATE_PASS`; `V3_28H_DEDICATED_INDEPENDENT_END_ACK_OPEN`; `V3_WRITER_RELEASE_NOT_AUTHORIZED`. Keine neue Runtime, keine Änderung der neun Hash-Pins und kein zweiter 28h-Test. Der ursprüngliche V2R4-Paper-Writer bleibt aktiv und Echtgeld bleibt aus.

---

## 14.10.2026 — Originale Cloud-/Mini-PC-Dateien, 16/16 kryptografisch identisch

**Zwei unabhängige Originalquellen:** (a) echte lesende Supabase-SQL-Abfrage der unveränderlichen Canary-Einzelzeilen `public.v3_paper_event_receipts`, gefiltert auf `series_id='PAPER-V3-CANARY-20261011'`, (b) Nutzerfoto der Administrator-PowerShell auf dem Mini-PC, welche nur das bestehende `Trading/Research/V3Paper/cloud-ack.json` und die exakt zugeordneten 16 `journal/<event_id>.json`-Dateien eingelesen hat. Kein Cloud-/lokaler Inhalt wurde geändert.

Für **beide** Quellen wurde derselbe eindeutige Serien-Fingerabdruck gebildet:

1. Die 16 verschiedenen 64-stelligen `event_id` lexikografisch sortieren (ASCII-/C-Reihenfolge).
2. Pro ID eine Zeile mit `event_id + '|' + lowercase SHA256(raw JSON bytes)` erzeugen. Cloudseitig entspricht der Inhaltshash dem Feld `content_sha256`; lokal ist es `Get-FileHash -Algorithm SHA256` über die existierende Original-Journaldatei `<event_id>.json`.
3. Zeilen mit genau einem LF (`0x0A`) verbinden, **kein** angehängtes Newline, UTF-8 kodieren, abschließend SHA256 bilden. Keine dynamischen Markt- oder Metadaten hinzufügen.

**Authentifizierter Cloud-Check:** Count=16, distinct `event_id`=16, Aggregat-SHA256 `b2f8a0c145e52ab1690bca2b43d75eb1077ee981543d6f0a165d4f76318b58d4`. Berechnet mit:

```sql
select count(*) as receipt_count,
       count(distinct event_id) as distinct_ids,
       encode(sha256(convert_to(
          string_agg(event_id || '|' || content_sha256, E'\n'
                     order by event_id collate "C"), 'UTF8')),'hex')
          as identity_content_sha256
from public.v3_paper_event_receipts
where series_id='PAPER-V3-CANARY-20261011';
```

**Unabhängiger Original-Mini-PC-Nachweis:** `CloudACKs=16`, `JournalDateien=16`, Original-SHA256 aus exakt den zu 16 ACK-IDs gehörigen Dateien identisch mit obigem Wert, PowerShell-Ergebnis `V3_CANARY_ORIGINAL_16_CLOUD_BYTES_MATCH`. Lokale zusätzliche Daten-/Quelldateien wurden weder verarbeitet noch kopiert.

**Disposition:** `V3_28H_CANARY_16_IMMUTABLE_ORIGINAL_LOCAL_CLOUD_CONTENT_HASH_MATCH_PASS` für das Byte-/Identitäts-Matching dieser fixierten EIGEN/ZRO-Canary-Kohorte. Dies ist ein **echter, nachprüfbarer Teilbeleg** für `V3_JOURNAL_REASONS_ERRORS_6H24H_FOLLOWUP_CENSURE`; **nicht** die vollständige Proof-Zeile `VERIFIED_PHYSICAL_OR_CLOUD_E2E`, solange Originalfehler-/Reason-/Followup-Felder und vorgeschriebene E2E-Hüllen der sechs Release-Proofs nicht je separat authentifiziert und freigegeben wurden.

Die bereits vorhandenen 6h-/24h-Originalverläufe bleiben fachlich `CENSORED_NO_CONTIGUOUS_CLOSED_KRAKEN_1M_PATH`, keine wirtschaftliche Nullrendite; die fünf separaten RENDER-One-shot-Belege bleiben ausgeschlossen. Die Original-28h-Windows-Task-Abnahme ist nach PR303 zeitlich/technisch ein positiver **Endkandidat**, aber eine gesonderte unabhängige Ende-ACK bleibt offen. Keine zusätzliche 28h-Testphase; **keine** Veränderung an neun SHA-256-Pins, Original-V2R4-Paper-Writer, Cloud-CAS, Kraken REST-Budget, Modellausgaben oder Echtgeldfreigabe.

**Owner/Folgeschritt:** Bereits vorhandenes V3-P0/P1-Six-Proof-Gate und 10:15-Work-/Milestone-Controller. Aus diesen echten Belegen eine vollständige `V3_JOURNAL_REASONS_ERRORS_6H24H_FOLLOWUP_CENSURE`-Quittung nur mit passenden originalen Reason/Error/Future-/Censor-Records einschließlich Fingerprint bilden; separat alle weiteren Proofs durch den bestehenden Owner prüfen. Keine neuen Watcher, Scheduler, Tabellen oder Aufgabenregistrierung.

---

## 14.10.2026 — Sicherer V3-Paper-Cutover: originale sechs Beweis-Gates und echter Supabase-CAS-Vorcheck

**Datum/Quellen:** Direkte, ausschließlich lesende Supabase-Abfragen am 14.10. nach Original-28h-Ende; GitHub-`main` nach PR #304; bereits dokumentierter physischer Mini-PC-Original-Fingerprint `b2f8a0c145e52ab1690bca2b43d75eb1077ee981543d6f0a165d4f76318b58d4`. Abgeglichen mit den **existierenden** sechs `PROOFS` in `tools/v3_experimental_paper_technical_gate.py`, `tools/paper_series_transition_guard.py`, dem **inaktiven** Original-CAS-Entwurf `supabase/v3-experimental-paper-atomic-cas-INACTIVE-20261013.sql` sowie dessen bestehenden Offline-Negativtests. Keine neue Architektur oder Laufzeit.

### Echte Mindestvoraussetzungen für die einzige aktive Serie (ohne Datenbankänderung)

- Supabase zeigt **exakt eine aktive** `public.paper_series`: `PAPER-V2R4-20261009T110135Z`, V2R4-Strategierevision. Keine aktive V3-Serie.
- Der **bestehende** `public.paper_series_single_active_idx` ist in der echten Datenbank vorhanden: `to_regclass(...) is not null = true`. Das beweist zunächst den Indexnamen, **keinen erfolgreichen konkurrierenden CAS-Dry-run**.
- Die für das originale V2R4-Release notwendigen Felder `config.release_repo_sha`, `strategy_fingerprint_sha256`, `runtime_bundle_fingerprint_sha256` sind in der aktiven Cloud-Serie vorhanden; `paper_only=true`, `real_money_actions_enabled=false`, `automatic_activation_allowed=false`. Die jeweiligen 40-/64-stelligen *Werte* wurden in dieser Vorprüfung bewusst nicht für ein neues Release autorisiert.
- Die eigene neue Function `public.rotate_v2r4_to_v3_experimental_paper(text,text,text,text,bigint,bigint,timestamptz,text,text,text,timestamptz,jsonb,text,text,text)` ist in **Supabase NICHT installiert** (`to_regprocedure(...) is not null = false`). Der GitHub-Entwurf ist ausdrücklich INACTIVE/REVOKED. **Kein APPLY/GRANT, RPC-Aufruf, Test-Transaction-Rollback oder Deployment erfolgt.**
- Der inaktive Entwurf sieht originalen Vorgänger-ROW-LOCK, exakte Repo-/Strategie-/Runtime-Hashes, aktuellen Kandidaten-/Trade-/LastUpdate-Checkpoint, eine atomare `strategy_cutover_closed`→V3-`active`-Transaktion und ausschließlich Paper mit `50+50` EUR vor. Bestehende Offline-Tests kontrollieren Text-/Fail-Closed-Verträge, **nicht** die tatsächliche physische Entsperrung.

### Sechs voneinander unabhängige technische Proofs (keine vermischten PASS-Labels)

| Verbindlicher `PROOFS`-ID | Heute *tatsächlich* belegte Vorarbeit | Noch erforderlicher Originalnachweis; Status |
| --- | --- | --- |
| `V3_REAL_MODEL_COIN_PIT_P4_INPUT_E2E` | Canary 16 unveränderliche ACKs; aus Original-Phasen 1 `MODEL_REQUEST=PASS`, 1 `MODEL_RESPONSE=PASS`, 1 `P4_VALIDATION=WAIT`, 1 `MODEL_REQUEST=SKIP`; keine `BUY_SCOUT`- und keine `PAPER_FILL`-Quittung. Ein gemeldetes Modellresultat ist weder Modellbudget- noch P4-Positivbeleg. | Ein echter einzelner quell-/zeitkorrekter Original-Mini-PC-Input→Full-Model→P4-Prüfpfad inklusive Kosten-/Stop-/Stage2-Review und unabhängiger Source-ACK; `OPEN`. |
| `V3_FAIL_CLOSED_STOP_STAGE2_FEE_WAIT_CONTRACT` | Schon implementierte V3 initial-/pathwise-economics-/WAIT-Verträge und CI-Negativtests; keine an echten Originalen gegengezeichnete technische E2E-Quittung. | Tatsächliche physische Original-Fehler- und normale WAIT-/Stop-/Stage2-/0,60%-Gebühren-Grenzfälle mit Pinned Source, `OPEN`. |
| `V3_JOURNAL_REASONS_ERRORS_6H24H_FOLLOWUP_CENSURE` | **16/16 Cloud/Host event_id+Byte-SHA256-Match nachgewiesen**, 4 fällige 6h-/24h-Quittungen `CENSORED`, `CENSORED_NO_CONTIGUOUS_CLOSED_KRAKEN_1M_PATH`; PnL unbekannt und NICHT 0. Der feste 28h-Zeitplan ist als Endkandidat PASS. | Proof-Hülle mit echten Reason-/Error-/Censor-Einzeloriginalen und separat authentifiziertem Mini-PC-/Supabase-Source-ACK; unabhängige Observer-End-ACK weiterhin offen. **TEILBELEG PASS, Proof-Zeile `OPEN`**. |
| `V3_SINGLE_WRITER_FENCE_CLOUD_CAS_DRYRUN` | Cloud: genau eine V2R4 aktive Serie, Single-Active-Index vorhanden, originale Release-Konfigurationsschlüssel korrekt; Cloud-V3-CAS-Funktion **nicht** deployed. `tools/paper_series_transition_guard.py` und inaktives SQL besitzen Offline-Guards. | Gleicher exakter alter/neuer Fingerprint physisch und Cloud, originaler Writer-Fence/Supervisor-Rearm/Backups/alte Followups, ausdrücklich **kein** CAS-Commit, echte Cloud-Index-/Stale-Vorgänger-/Rollback-Belege. `OPEN`. |
| `V3_MINIPC_SUPERVISOR_STOP_START_ROLLBACK` | Funktionierender existierender SYSTEM-Supervisor und abgeschlossene unabhängige PR299–301-WSShadow-Reparatur; dies ist **kein V3-Writer-Rollback-Nachweis**. | Separater geplanter V3-Owner-Stop/Start-/Crash-/Supervisor-Rearm-/Rollback-Negativbeleg ohne V2R4-Produktion zu gefährden; `OPEN`. |
| `V3_GITHUB_WORK_ALERT_DYNAMIC_SERIES_ROUTING` | Bestehende versionierte Alert-/Completion-Routing-Guards, CI und 10:15 Work; keine zweite Automatisierung. | Originales GitHub-/Work-E2E dynamische V3-Serien-/Revisions-Konsistenz und FAIL-CLOSED-Beleg ohne aktiven V3-Writer oder fingierte ACK; `OPEN`. |

**Formal weiter 0/6 `VERIFIED_PHYSICAL_OR_CLOUD_E2E`-Zeilen.** Dies ist nicht `0/6` Vorarbeiten. Für den *experimentellen* ersten V3-Paper-Start ist vorab **kein profitabler BUY** und **keine erneute 28h-Frist** erforderlich; wirtschaftliche Strategie-Promotion bleibt späteres eigenes Kausalgate.

### Wichtigster tatsächlicher Integrationsblocker vor einem Wechsel

Der originale CAS-Entwurf setzt bei altem `paper_series`-Status `strategy_cutover_closed`. Bestehende **aktuelle** V2R4-Consumer/Relays unterstützen den gesonderten `sync_closed_original_followups`-Pfad **als Code-/Offline-Vertrag**, aber die echte Cloud-/Host-E2E-Erlaubnis für **offene alte WAIT-/Trade-/STOP-/Stage2-Nachläufe** und den physischen Supervisor-Ausschluss des neuen V2R4-Intake wurden bislang nicht unabhängig quittiert. Deshalb **nicht** blind den CAS-Entwurf installieren oder V2R4 aussetzen: sonst besteht Datenverlust-/Doppel-Writer-Risiko. Bei unklarem Commit-Ergebnis nach bestehendem `assess_v3_cutover_recovery`: beide Writer in Quarantäne, niemals automatischer neuer CAS-Versuch.

**Direkter nächster Owner-Arbeitsauftrag (ohne neue Scheduler/Frist):** Bestehender V3-P0/P1-/10:15-Work-/Milestone-Controller nimmt die vorhandenen originalen 16 Host-/Cloud-Matchbelege als **Teilerfolg in Proof 3** auf, vervollständigt als erstes dessen Reason/Error/Followup-Provenienz und bereitet separat auf dem bereits vorhandenen Original-V2R4-Writer nur eine **READ-ONLY** Writer-Fence-/Supervisorschutz-Kontrolle für Proof 4 vor. Danach pro Proof tatsächliche Quelle/Fingerprint/ACK, keine Phasenverwechslung; gesonderte Freigabe erst bei sechs unabhängigen Vollbelegen. Keine Modell-, CAS-, Runtime-, Task-, Budget- oder Echtgeldaktion durch diesen Bericht.

**Betriebsbeobachtung getrennt:** Eine einmalige Supabase-WARNUNG betraf am 14.10. um 16:24 MESZ den Altrady-Lese-Timeout (`altrady_trigger_heartbeat: DEGRADED`). Ein späterer erneuter Statusnachweis lag bei Berichtsschluss nicht gesichert vor. Der laufende V3-Release-Owner wird deswegen nicht auf spontane Reparaturen umgestellt; vorhandenen Issue99-Health-Owner bei Persistenz/Repeat verwenden.

---

## 14.10.2026 — Original Mini-PC TASK Owner-/Restart-Fence-Ermittlung nach PR305

**Physischer Originalbeleg:** Nutzer-Foto einer Administrator-PowerShell auf dem echten Mini-PC nach **READ-ONLY** `Get-ScheduledTask` / `Get-ScheduledTaskInfo` und SHA256(`Execute|Arguments|WorkingDirectory`), Endmarker `V3_V2R4_OWNER_READONLY_MAPPING_DONE`. Folgende vier **existierende** Windows-Tasks wurden vollständig erfasst, jeweils `State=Running`, genau **eine Task-Aktion**, `LastTaskResult=267009` (Windows Task Scheduler `0x41301` = Aufgabe läuft). Eigener 64-stelliger Task-Aktions-SHA256 jeweils in der originalen PowerShell-Ausgabe. Diese Hashes wurden **noch nicht** mit einer von der physischen Task unabhängigen erwarteten Installer-Aktionsversion abgeglichen, sind somit keine Release-Pins.

| Original Task | Physischer letzter Task-Start, Mini-PC-Ortszeit | Laufend; tatsächliche Rolle laut vorhandenem Installer |
| --- | --- | --- |
| `CryptoMiniPC-V2R4PaperCandidates` | 14.10. 16:09:46 | `v2r4-paper-local-runtime.py --mode candidates`: neue Kandidatenaufnahme/Entscheidungen |
| `CryptoMiniPC-V2R4PaperWait` | 14.10. 15:41:46 | `v2r4_wait_runtime.py --execute-recheck`: ausstehenden WAIT neu prüfen; kann *neue Entscheidungen* nach alten Signalen erzeugen |
| `CryptoMiniPC-V2R4PaperLifecycle` | 13.10. 20:59:46 | `v2r4-paper-local-runtime.py --mode lifecycle`: alter Paper-Positionen-Lebenszyklus/Followups |
| `CryptoMiniPC-V2R4PaperCloudSync` | 09.10. 20:15:46 | `v2r4-paper-cloud-sync.py`: Cloud-Sync der V2R4-Originale |

**Architekturabgleich mit echtem Quellcode:** `tools/install-minipc-v2r4-paper-runtime.ps1` registriert diese vier Aufgaben als `SYSTEM`, `-AtStartup`, `-MultipleInstances IgnoreNew`, mit taskseitigem RestartCount=3, RestartInterval=1m. Die **tatsächlichen** Task-Aktionsargumente sind aus dem Foto ausschließlich gehasht (keine Rohbefehle/Secrets offengelegt), und ihre Übereinstimmung mit dem Installer muss durch physischen, weiterhin **nur lesenden** Script-/Argument-Check gesondert bestätigt werden.

**Neuer, konkreter V3-Blocker aus dem vorhandenen Original-Supervisor-Code:**
- `tools/minipc-runtime-supervisor.ps1` überwacht und kann **alle vier** oben genannten V2R4-Tasks neustarten. Sein bestehendes Wartungsfile `State/v2r4-technical-cutover-maintenance.json` akzeptiert aber nur `PAPER-V2R4-20261007T184255Z` und den damals gepinnten alten Repository-SHA. Die **jetzt** aktive Serie `PAPER-V2R4-20261009T110135Z` passt **nicht**; die alte technische Wartungslogik für V3 weder blind kopieren noch zum automatischen Schutz vor Wiederanlauf behaupten. Auch Windows-Task-Recovery muss beim Cutover separat abgesichert werden. **Noch keine Änderung des Supervisor-Codes oder aktiver Task-Konfiguration.**
- Ein sicherer V2R4→V3-Wechsel erfordert **neue V2R4-Intake-Sperre** für Candidates und insbesondere WAIT-Recheck und Supervisor-/Windows-Rearm, während bestehende Lifecycle-/Followup-/Exit-Originale weiterhin ihre historische Serien-ID behalten. CloudSync verwendet aktuell in `run_once` die Aktion `sync`, die bei geschlossenem V2R4-Status Cloudseitig nicht mehr normal akzeptiert wird. Der schon vorhandene **inaktive** `closed_original_readonly_preview`-/`sync_closed_original_followups`-Vertrag ist kein physisch aktivierter Nachlauf und kein belegter nahtloser Sync.
- `Running` und `267009` bedeuten nur laufende Windows-Aufgaben; sie sind **keine** verifizierte aktuelle Heartbeat-Qualität, kein exakter Worker/Parent-Prozess-Beleg, keine gewährleistete Task-Aktionsidentität und keine bestätigte Quiesce-/Rollback-Quittung. Alle vier bleiben unverändert am Laufen.
- Das original Supabase-CAS ist weiterhin **UNINSTALLED**, V2R4 **einzige** aktive Paper-Serie, Echtgeld **OFF**. Bisher **0/6** formal separat authentifizierte V3-Release-E2E-Proofs. Dieser Schritt ist eine echte Teilvorleistung für `V3_SINGLE_WRITER_FENCE_CLOUD_CAS_DRYRUN` und `V3_MINIPC_SUPERVISOR_STOP_START_ROLLBACK`, jedoch noch **keine** Freigabe.

**Nächster konkreter Arbeitsauftrag an existierenden V3-P0/P1-/10:15-Work-Milestone-Owner:** Eine einheitliche **read-only physische** Task-Aktions-/Executable-/Heartbeat-Alter-/Task-SYSTEM-Prüfung ohne Veröffentlichung von Argumenten/Secrets auf den vier bestehenden Tasks. Dann anhand tatsächlicher Task-Identitäten und Quelle (nicht Namen alleine) den minimalen V3-scoped physischen Intake-/WAIT-Fence entwerfen, im vorhandenen Supervisor-Schutz idempotent/Fail-Closed kapseln und den **separaten** historischen Followup-/Exit-Cloud-Pfad originalquittieren, bevor irgendein Stop, Runtime-Release oder CAS-Deploy erfolgt. CI-/Entwurfstests allein beweisen das nicht. **Kein neues Task-/Cloud-Service-/Work-Intervall**.
