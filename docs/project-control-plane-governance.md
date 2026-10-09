# Project Control-Plane Governance

Status: **CANONICAL / ACTIVE**

## Purpose

The project previously allowed current status to be repeated in several documents. That was useful during rapid development but created a risk that an old sentence could later be mistaken for current authority.

The control plane is now deliberately split by responsibility:

1. `project-current-state.json` — single machine-readable declaration of the **current** strategy/research/control-plane state.
2. Live Supabase/MINI-PC evidence — authoritative for instantaneous runtime health, counters and evidence rows.
3. `docs/master-version-register.md` — version/component/history register.
4. `PROJECT_BACKLOG.md` — open work only; never runtime/status authority.
5. Strategy/research documents — methodology, contracts and dated evidence. Historical wording may remain only when explicitly historical.

## Transition rule

Every material activation, closure, rollback, baseline switch, promotion, strategy-changing Shadow start/stop or real-money release step must update `project-current-state.json` as part of the same bounded change sequence.

A transition is incomplete if runtime changed but the current-state file still declares the predecessor state.

## Monitoring/Evidence/Anwendung — eine kanonische Gesamtzuständigkeit (2026-10-08)

Das vollständige, nach Überschneidungen geprüfte Routing ist
`docs/unified-monitoring-learning-architecture-v1.md`, mit
**26** eindeutig benannten Domänen-/Monitor-Ownership-Einträgen
in `research/monitoring-evidence-routing-v1.json`.
Die bestehende `project-control-plane-guard.yml` testet deren
Autoritäten, wichtige Überlappungen und Fail-soft-Grenzen. Das ist
*ein* Validierungsschritt im bestehenden CI, **kein neuer Watchdog,
Work-Job oder Datensammel-Lauf**.

Es gibt nur die folgenden Verantwortungsübergänge:
- Kraken-Venue- und Execution-Fakten: vorhandene Scanner/Paper-Regeln.
- Marktdaten/News/Hypothesen: nur point-in-time und über bereits
  unabhängig geöffnete Strategie-Analyse-/Integrations-Gates zu
  geprüfter `NOT_EVALUABLE`/`NO_ACTION_WARRANTED`/`REJECT`/
  inaktiver One-change-Test-Disposition. Kein neues Order-/Buy-Veto.
- Quellenqualität: autonomer Research-Steward, nicht Handelsentscheid.
- Betriebsdaten: vorhandene Selbstheilung/Health-Eskalation bzw. ACK,
  nicht künstliche Strategieoptimierung.
- Meilensteincontroller: Review-Readiness/Quittung; Work nur bei
  eigenen Gatebedingungen; Releases ausschließlich nach gesonderter
  Freigabe, nie automatisch aus einer Quellensichtung.

H1-Standalone bleibt gesperrt. 2h-Regime, Marktbreite, BTC-/ETH-
Korrelation und H6 sind keine mehrfach zählbaren Bestätigungen;
H5/News/H11 erzeugen keine parallelen Event-Vetos; H3 und H9
haben unterschiedliche Imbalance-/Execution-Zuständigkeiten.
Die Source-Radar-Aktivierung allein ist kein erfolgreicher E2E-Beleg.
Komponentenstatus bleibt dynamisch in `project-current-state.json`
und Runtime-Evidenz; die Routing-Matrix beansprucht keine aktuelle
Live-Statusautorität.

## Gesamtarchitektur: genau ein Wirkungsweg, getrennte Verantwortlichkeiten (Audit 09.10.2026)

**Betriebskarte / aktuelle Autorität:** `project-current-state.json` ist die **deklarierte** aktive Strategie-/Shadow-/Freigabewahrheit, `public.paper_series` + `public.paper_technical_rotations` + MINI-PC-Heartbeat liefern **aktuelle** Betriebs-/Serien-Fakten, `research/v3-migration-ledger.json` hält die Strategievererbung, `docs/master-version-register.md` ist Historie, `PROJECT_BACKLOG.md` hält offene Arbeit. Git-Historienbelege und eingefrorene Kandidaten-JSON (etwa `v3-h3-shadow-001.json` mit historischem `SHADOW_RUNNING`) sind **keine** Runtime-Gesundheits- oder aktuelle Aktivitätsquelle.

```text
Kraken-EUR Spot + unabhängiger GitHub-Scanner + MINI-PC WS + Altrady-Wake-Hinweis
  -> eindeutiger Kandidat (UTC/known-at, Source, Venue, Liveness, Dedupe)
  -> genau EINE laufende, eingefrorene V2R4-Paper-Entscheidungslogik
     -> BUY_SCOUT: 50+50 simuliert, echte Stop-/Stage-2-/Kosten-Evidenz
     -> WAIT: alle eingefrorenen Kurs+Volumenbedingungen -> nur bei Match echter KI-Recheck
     -> REJECT: Grund + späterer Kurs-/Risiko-Verlauf, niemals erfundener Trade
  -> Mini-PC Lifecycle/Backup -> Supabase aktuelle Teilserie + historisch eingefrorene Teilserien
  -> Strategie-Epochen-Review (ALLE technischen Teilserien; Trade-, MAE-/Kosten-/Chance-Funnel)
  -> Forschungs-/Freigabegate: genau EIN aktiver strategieändernder Shadow
     -> prospektiver Ein-Änderungs-Vergleich -> explizite Paper-Freigabe
     -> gesondertes Sicherheits-/Nutzer-Gate vor JEGLICHER Echtgeldstrategie

Parallel, OHNE Handelsautorität: H10/H11/Marktphasen/Quellen als Research-Evidenz.
Außerhalb der Trading-Semantik: Watchdog, Cloud-Fallback, Slack, Backup, Actions-Kosten.
```

**Statusabgleich nach dem 09.10.-Cutover (belegte Momentaufnahme):**
- Ursprünglicher V2R4-Strategiestart **07.10. 18:42:55 UTC**, 72h-Produktivitätsreview **10.10. 18:42:55 UTC**. Alte `PAPER-V2R4-20261007T184255Z` ist `technical_closed`, mit **1.011** Outcomes/**0** Trades und **260/260 fälligen vollständigen 24h-Follow-ups** bis zum Cutover. Technisch neue `PAPER-V2R4-20261009T110135Z` läuft mit **derselben Strategie-/Risikoregel** weiter. Die Gesamtbewertung darf die Zähler **nicht** nur auf die aktuelle Teilserie reduzieren. Erstes Strategie-Epochenreview ist ausdrücklich ein *früher Review*, **keine** automatische V2R4-Finalfreigabe.
- Der physische Mini-PC-Health-Snapshot **09.10. 19:49:26 UTC** enthält `v3_h3_shadow=ARCHIVED_001_FROZEN_ORIGINAL_BASELINE_NO_REBIND`. Cloud-H3-Status wurde zuletzt **11:00:03 UTC** generiert, `public.v3_h3_shadow_evidence` enthält **0** Datensätze. Das ist ein nach dem Cutover **archivierter, nicht abgeschlossener** H3-Versuch; **kein** erreichter Fixed-Review-Meilenstein, keine Kausaldivergenz und keine H6-Freigabe. Historische Aktivierungsbelege bleiben unverändert, statt rückwirkend zu einem Erfolg umgeschrieben zu werden. H6 bleibt als nächster strategieändernder Versuch bis zur expliziten H3-Archivent­scheidung und eigenem Gate gesperrt.
- V3 `coin_specific_entry_evidence_provenance` ist eine inaktive geteilte *Daten-Schnittstelle*. `late_chase_protection` enthält die davon **getrennte** spätere `EXTENDED`-Second-Leg-Hypothese. Kein doppelter H6-Volumenvote, kein neuer Reversal-Entscheider, kein automatischer BUY. Zuerst separater Daten-A-Test, danach nach H3-Reconciliation ggf. isolierter Policy-B-Test, beide mit echten Netto-/Stop-/BUY-Nachweisen.
- Von den **66 registrierten** GitHub-Workflows sind derzeit **9** als `ACTIVE_RUNTIME`/laufende Kontrollfläche klassifiziert. Die übrigen sind historische, manuelle, Prüf- oder Research-Workflows und **keine 57 gleichzeitig laufenden Tradingstrategien**. Der detaillierte Owner-/Dedupe-Vertrag für 26 Forschungs-/Monitoringströme liegt bereits unter `docs/unified-monitoring-learning-architecture-v1.md`; **kein** zweiter Scheduler, kein doppeltes Ops-System.

**Verbindliche Bereinigungsregel:** Beim nächsten *technischen* Cutover gehören die Shadow-Aktivitätsdisposition, Archiv-/Snapshotstatus, unveränderter Strategie-Fingerprint, alte/neue Supabase-Serien und die Epochen-Produktivitätsuhr **zur gleichen Abschlusssequenz**. Ein über `SHADOW_RUNNING` eingefrorener historischer Kandidatenvertrag darf niemals allein eine laufende Shadow-Instanz behaupten. Ein archivierter H3-Fall darf weder eine ständige `STALE`-Alarmflut erzeugen noch bei der automatischen H6-Freigabe als bestandener Fixed Review gelten. Die Runtime-Frozen-Artefakte dürfen nur in einer **separat genehmigten neuen Version** geändert werden.

## Abgleich ausdrücklich gespeicherter Vereinbarungen / Wiederauffindbarkeit — 09.10.2026

**Umfang und Sicherheitsgrenze:** Diese Querverweisliste ist ein **datiertes Audit der nachprüfbar wiedergefundenen Nutzervereinbarungen** (Sept./Okt. 2026) und *keine* zusätzliche oder konkurrierende Strategie-/Statusautorität. GitHub allein kann keine früheren Chatverläufe lesen oder die in ChatGPT separat konfigurierten Automations-Prompts validieren. Die beabsichtigte Wiederverwendung wird pro Punkt am tatsächlichen Einstieg gemessen: **gespeichert → rechtzeitig gelesen → Gate mit Evidenz → richtige Aktion/Ack**, niemals allein an einer Textdatei. Aktueller Stand stets `project-current-state.json`, historische Strategiefakten nur aus unveränderlicher Provenienz, Live-Status aus MINI-PC/Supabase.

| Dauerabrede / Ursprung | Kanonischer Inhalt, fachlicher Owner | Tatsächlicher automatischer Wiederaufgriff / Status 09.10. |
| --- | --- | --- |
| **Strategieerkenntnisse für jede nächste V2/V3/V4+ und spätere Echtgeldversion dauerhaft vererben** (04.10.) | `docs/test-strategy-runbook.md` §§12.2–12.4; `research/v3-migration-ledger.json`; `docs/strategy-version-map.md`; `research/strategy-learning-causal-gate-v1.json` | Bestehender PR-/Current-State-Guard fordert Successor-Dispositions und echte Daten-/BUY-/Kosten-Evidenz; täglicher Work-Analysepfad liest diese Quellen. **Technisch implementierte Freigaberegel, nicht bewiesener Trading-Mehrwert.** |
| **Trade-Produktion wichtiger als Health; kein endloser Null-Trade-Paperlauf** (08.–09.10.) | `project-current-state.json#next_control_decisions[V2R4-PRODUCTIVITY-REVIEW]`, `PROJECT_BACKLOG.md` P1, `tools/strategy_epoch_lineage.py` | Echter täglicher `autonomous-project-milestones.yml`-Controller aggregiert ursprüngliche V2R4-Strategie-Epoche samt archivierten technischen Abschnitten; 72h ab 07.10. 18:42:55 UTC, 10.10. 18:42:55 UTC frühes Pflichtreview, nicht neue Runde ab 09.10.; **0 BUY/Trades = wirtschaftlich nicht demonstriert**. Kein automatischer Stop/Strategiewechsel. |
| **V2R3 → V2R4 nicht als zusätzliche Signalfreigabe ausgeben**; 50+50 EUR, Anti-Chase, 0,60% je Seite; echte Entry-Datenfrage | `research/v2r3/strategy-adjustment-hypotheses-final-20261007.json`, `research/v2r4/paper_strategy_spec_v2r4_release_candidate.json`, V3 `late_chase_protection` im Migrationsledger | V2R4 ist eingefrorene WAIT-/Trigger-Timing-Isolation mit **unbewiesenem Profitabilitätsnutzen**; vor Nachfolgerrelease isolierte Coin-OHLC-/Volumen-/ATR-Input-A-Studie und separat spätere EXTENDED-Second-Leg-B-Policy, keine Doppel-H6-/H3-/H4-/H7-Signale. V2R4-Trade-Fix **offen**. |
| **Fasttrack: so kurz wie möglich, so lange wie nötig** (05.10.) | `docs/fasttrack-evidence-diversity-policy.md` + `supabase/evidence-diversity-fasttrack-v2.sql`; Release-/Work-Gates | Mindestanzahl und 24h-Reife/Zeitdiversität statt starrer Kalenderfrist; Abschluss nach frühem Strategiereview nicht vortäuschen. Deployment-/Supabase-Readiness separat prüfen. |
| **Nur ein strategieändernder Shadow; H1→H3→H6, H10/H11 passiv** | `project-current-state.json#strategy_changing_shadow_wip`, `research/v3/shadow-candidates`, `docs/v3-research-framework.md` | H1 als Standalone verworfen; H3-001 am 09.10. physisch **ARCHIVED_INCOMPLETE**, 0 prospektive Cloud-Rows; H6 wartet auf explizites H3-Archiv-/Folgegate und darf *nicht* allein wegen `active=[]` starten. H10-Sensor läuft getrennt. |
| **Mehr Marktphasen- und Informationsquellen dauerhaft lernen und wirksam nutzen** (08.–09.10.) | `docs/market-context-source-fusion-v1.md`, `research/v3/market-phase-reversal-observation-v1.md`, `research/market-source-candidates-v1.json`, `research/monitoring-evidence-routing-v1.json`, Issue #7 | Bestehender **2h-Marktradar** hat Kraken-EUR-15m-Episoden-E2E: initial #6068682341 und mehrere bestätigte Phasenwechsel. Erstes Research-Capture belegt, **kein** Kauf-/Outcome-Alpha. Wöchentlicher Source-Steward, News/Quellentausch und echte Outcome-Join-Kausalität noch zu belegen; kein neues Veto bei optionalen Datenlücken. |
| **Selbständiger Fortschritt statt auf jeden Nutzerbefehl warten; kein Work-Verbrauch ohne Gate** (08.–09.10.) | `docs/autonomous-followthrough-governance-v1.md`, `research/autonomous-implementation-queue-v1.json`, `research/work-analysis-state.json`, `PROJECT_BACKLOG.md` | **EIN** bestehender Work-Lauf 10:15, billiges Vor-Gate, maximal 2 `READY_SAFE_WORK`-Tasks, maximal ein Safe-PR. Erster echter abgeschlossener Test: **H10-Join PR #96**, als COMPLETED quittiert. Keine unbegrenzte Coding-Instanz und keine Garantie, dass unzugängliche Gespräche automatisch entdeckt werden. |
| **Ausfälle sicher behandeln, Recovery-Prinzipien später im echten Echtgeldpfad beweisen** (08.–09.10.) | `docs/project-wide-outage-recovery-v1.md`, `research/global-outage-recovery-contract-v1.json`, `PROJECT_BACKLOG.md#LIVE_RESILIENCE_INHERITANCE_GATE`, Issue #99 | 17-Domänen-Vertrag und Code-/CI-Belege vorhanden. Zusätzliche lokale Supervisor-Deployment- und Source-Gap-/Recovery-Gates bleiben **offen**. Spätere Order-/Fill-/Positions-Reconciliation und Kill-Switch sind **NICHT durch Paper-Health bewiesen**; wöchentlicher schlanker Resilienz-Folgecheck plus Release-Gate. |
| **GitHub-Kapazität, Runner-Entlastung, Ausgabenbremse, keine unnötige Hardwarekomplexität** (08.–09.10.) | `docs/github-capacity-and-cost-strategy-v1.md`, MINI-PC Support Block 1–3, `PROJECT_BACKLOG.md#CAPACITY_GROWTH_GATE` | Block 3 **STAY_CLOUD_HOSTED** für private Kraken-Read-only-Snapshots nach tatsächlichem Billing-Check. Begrenzter Runner nur abgeschlossener/gestoppter sicherer Pilot, kein produktiver Ersatz. Laufende **monatliche Kapazitätsfrühwarnung** am 10./20.; 10-USD-Stop-Usage als Nutzergrenze, nicht automatisch erhöhbar. Tatsächliches Billing bleibt UI-Beleg, keine GitHub-API-Behauptung. |
| **Zwei KI-Ziele strikt getrennt; großer selbstentwickelnder Agent unabhängig**, kleines Ollama/Qwen optional | `docs/github-capacity-and-cost-strategy-v1.md` `MINI-PC SUPPORT V1`; `PROJECT_BACKLOG.md#CAPACITY_GROWTH_GATE` | Eigenständiger KI-Agent **nur künftiges Konzept**, isoliertes eigenes Repo/Paper-Ledger und ausschließlich lesender Zugriff auf das bestehende Krypto-System. **Weder gestartet noch in die Hauptstrategie eingebaut.** Kleiner Qwen/Ollama-Helfer nur fakultativ und ressourcen-/sicherheitsgated. |
| **Datensparsamkeit, keine unnötigen Doppelablagen, Schutz bei Secret/Account-Rechten** | `docs/storage-retention-policy.md`, `docs/unified-monitoring-learning-architecture-v1.md`, GitHub Least-Privilege PR #65, Supabase RLS/Grants | 26 eindeutige Quellen-/Monitoring-Owner dokumentiert und CI-validiert; Rentention-/RLS-/Least-Privilege-Verträge und Nachweise vorhanden. **Nicht** jeder zukünftige Mini-PC-Cleanup oder Live-Security-Check ist schon durchgeführt. |
| **Vereinbarung wird später wirklich eingebracht, nicht nur gespeichert** (29.09., 04./08./09.10.) | Diese Tabelle ist **nur Retrieval-Wegweiser**, fachlicher Owner bleibt jeweilige kanonische Datei; `PROJECT_BACKLOG.md` hält offene Konsequenz und konkretes Gate | Die bestehenden ChatGPT-Automationsanweisungen `Krypto Paper – gezielte Analyse` (täglich 10:15) und `Krypto Marktphasen- und Quellenradar` (2h) wurden am **09.10. nach H3-Archiv/PR #96** wegen nachgewiesener veralteter Statusbehauptungen aktualisiert, **Zeitpläne unverändert**. Externe Task-Prompts sind **nicht Teil der GitHub-Dateien**; nach jedem materiellen Status-/Strategieübergang dort erneut auf feste veraltete Aussagen prüfen. Der nächste tatsächliche Lauf der aktualisierten Prompts ist noch nicht als E2E-PASS bewiesen. |

**Neue unverzichtbare Checkliste für alle ausdrücklich vereinbarten dauerhaften Festlegungen**, ohne zweiten Backlog: (1) Fachautorität und Version/Scope prüfen; (2) nur *einen* bestehenden Owner/Backlog/Research-Gate verwenden; (3) unabhängigen Runtime-/Task-Prompt als tatsächlichen Leser benennen; (4) Zustand `DOCUMENTED_ONLY`, `GUARDED`, `RUNTIME_EVIDENCED`, `RESEARCH_PENDING`, `USER_RELEASE_PENDING` oder `CLOSED_WITH_PROOF` eindeutig unterscheiden; (5) bei Änderung von Status/Startuhr/Shadow/Reife-/Kosten-Gate **auch bestehende externe Automation-Prompts** auf eingefrorene, inzwischen falsche Annahmen kontrollieren; (6) CI-/PR-/E2E-/Ack-Beleg und konkretes Weiterverwendungsereignis sichern oder offen lassen. Es wird **keine** neue Task, kein unabhängiger Datenspiegel und keine Echtgeldermächtigung erzeugt. Die tatsächliche Projektverantwortung liegt nicht bei einer Markdown-Tabelle; jeder Fach-Owner bleibt verbindlich.

## Strategy-changing Shadow WIP limit

At most **one** Shadow/Paper experiment that can alter a strategy decision may be active at a time.

Passive observational research may run in parallel only when it has no decision authority and cannot change the active strategy, order state, sizing, entry, exit, stop or risk gate.

This keeps causal attribution clean and prevents two successor branches from competing for the same baseline at once.

## Baseline replay rule

For every strategy-changing Shadow candidate, a claimed causal decision divergence is valid only when a same-snapshot baseline control replay reproduces the official baseline decision.

This rule generalizes the protection already used by H3 and is permanent for V3 and later generations. A model/evaluator instability must not be counted as candidate value.

## Integration rule

One-change testing remains mandatory for component attribution. After individual components are reviewed, any retained components must be tested again in a separately versioned **integration candidate** before promotion. Individually useful components are not assumed to be jointly useful.

## Status-document rule

Documents may describe historical states, but current status must not be inferred from them when they conflict with `project-current-state.json`.

New documents should reference the current-state file instead of copying active strategy IDs, active series IDs, active Shadow IDs or next-control decisions unless the duplicate is explicitly a dated release record.

## Workflow surface

`docs/workflow-registry.json` classifies every GitHub Actions workflow by lifecycle and role. The registry is audited by `tools/validate-workflow-registry.py`.

Historical/manual/validation workflows may remain in the repository for provenance and recovery without being part of the active runtime control surface.

## Safety boundary

Nothing in this governance file authorizes real-money trading, private order rights, leverage, automatic promotion or automatic strategy activation.

## Projektweite Resilienz-/Recovery-Sicherheitsnorm (08.10.2026)

`docs/project-wide-outage-recovery-v1.md` und
`research/global-outage-recovery-contract-v1.json` gelten für
bestehende und künftige Produktions-, Paper-, Shadow-, Forschungs-
und spätere Echtgeld-Dienste. Ein einzelner GitHub-/Kraken-/
Internet-/Supabase-/Mini-PC-Ausfall darf weder fremde Komponenten
zum Stillstand bringen noch alte Kandidaten neu evaluieren,
unvollständige Daten vortäuschen oder einen Restart-Sturm auslösen.
Grenze: Recovery darf ursprüngliche Feed-/Freshness-/Freeze-/
Order-/Release-Regeln nicht verändern. Vor lokaler Supervisor-
Installation Parser- und physischen Gate-Safe-Smoke; Proof E2E offen.

## Autonomes Follow-through mit begrenzter eigenständiger Implementierung (2026-10-08)

Der Nutzer hat ausdrücklich autorisiert, innerhalb **bestehender**
Sicherheits-, Rechte-, Freeze- und Release-Gates sichere Projekt-
Weiterentwicklungen ohne erneute Chat-Nachfrage vorzubereiten und
umzusetzen. Kanonischer Vertrag `docs/autonomous-followthrough-governance-v1.md`.
Ergänzend zu GitHub-Milestone-Readiness und bestehenden
`docs/test-strategy-runbook.md`-Konsequenzregeln existiert nun
`research/autonomous-implementation-queue-v1.json` (kleiner
**allowlisted** Safe-Work-Katalog). Der pure Python-Selektor
`tools/select-autonomous-implementation.py` prüft ausschließlich
aus `project-current-state.json`, Quellbelegen und vorhandenen
Repo-Dateien, ob z. B. der H10-PIT-Join-Contract fehlt oder ein
genuine neuer Gate-Adapter programmiert werden muss.
`READY_SAFE_WORK` ist ein kleiner, eigenständiger *Umsetzungsgrund*
innerhalb der **bereits täglich geplanten** Work-Phase 1,
kein schweres Open-Market-Analyse-Gate.

Nur maximal zwei bereits genehmigte kleine Aufgaben / bestehenden
Work-Lauf, maximal ein laufender Implementierungs-PR, nie
Spontan-Live- oder Strategieänderung. Nach auswertbarem Ergebnis
unbedingt echten CI/PR/Gate-Closed-Nachweis oder `BLOCKED`
mit Dedupe im bestehenden Work-Ack. Derselbe blockierte
Gate-Fingerprint darf nicht täglich den gleichen schweren
Work-Aufwand auslösen. Keine neuen Work-/GitHub-Schedules,
keine Repo-Secret- oder MINI-PC-Rechte. Vollständiger erster
Work-E2E-Implementierungsnachweis noch offen.

## Autonomous milestone controller (2026-10-08)

Workflow: `.github/workflows/autonomous-project-milestones.yml`; engine:
`tools/project_milestone_controller.py`. Runs once daily via GitHub Actions,
independent of ChatGPT Work. Manual dispatch inspects only; scheduled runs may
post *one* milestone receipt to the relevant existing GitHub issue and an
optional Slack signal. No new issue/backlog, Supabase schema, timer service,
Mini-PC task or recurring Work invocation is introduced.

- Current declared strategy/shadow authority: `project-current-state.json`.
  Live evidence authority: Supabase completion and H3 status views.
- The controller requires exact strategy, series, baseline and fixed policy
  matches, timely H3 evidence, immutable Paper rules and at most one active
  strategy-changing Shadow. Missing or contradictory inputs fail closed.
- V2R4 final review is surfaced only when the actual registered sample,
  temporal-diversity and maturity gate is complete. A distinct early
  **low-trade** review is raised once the series has >=72h, >=100 candidates,
  >=30 completed 24h follow-ups and still 0 completed Paper trades.
- H3 fixed review is surfaced only after its frozen sample/capture gate,
  stop condition and follow-up readiness. H6 remains queued pending H3
  review; never starts as a second strategy-changing Shadow.
- H10 first review is already complete; its next concrete research milestone
  is the preregistered point-in-time Kraken-EUR outcome/context join and
  false-positive label contract. Observation/capture continues independently.
- Each ready milestone carries a deterministic stable event key based on the
  milestone and frozen candidate/series identity; prior bot receipts in
  GitHub issue comments suppress duplicate notifications. These comments
  are receipt/history only, not a second task authority.
- Automatic work here is **evidence collection, eligibility checking,
  classification, review readiness and escalation**. A ready review must
  be conducted and its findings dispositioned under the existing
  analysis-to-consequence rule. This gate controller is *not* a trading,
  strategy-editing, PR-merging, shadow-starting or automatic release engine.
  Autonomous engineering may follow validated, low-risk plans separately;
  any material strategy promotion, new shadow activation, live/private
  exchange rights and sizing changes still require the existing release gates.
- The workflow has read-only repo contents and Supabase GET access. The
  only write permission is existing GitHub issue comments; the optional
  Slack notification is a one-way webhook. No secrets are emitted to
  diagnostics. Any absence of live evidence produces a failed control check,
  never a guessed pass.
- Changes to this controller use branch -> minimal tests -> validated PR ->
  merge; never mid-series tuning or direct runtime-to-main writes.

## Permanent decision: phased autonomous development (2026-10-08)

The approved direction is to grow from **automatic readiness detection** toward
**autonomous, bounded engineering execution** across V3, V4+ and later
real-money successor research. This is a roadmap, **not** authorization to
deploy an autonomous coding agent or modify active trading mechanics today.

**Timing rule (confirmed 2026-10-08):** Dates such as 2026-10-09/10 are
planning estimates, not deadlines, minimum waiting periods, or automatic
approval triggers. Advance as soon as the applicable evidence/quality,
safety, dependency, cost and release gates are verifiably satisfied; defer
when they are not. Reassess when relevant new evidence arrives instead of
restarting tests or waiting for the calendar. A successful first scheduled
controller run is a technical input, not by itself approval to launch an
autonomous coding agent. If a gate needs more evidence, keep collection
bounded and the active V2R4/H3 contracts frozen; if a safety-critical gate
fails, remain blocked. The controller does not currently launch autonomous
engineering work by itself. No extra Work runs, schedules or notifications
are authorized by this timing clarification.

Sequence, without an arbitrary waiting period:

1. **Prove the new controller:** observe at least one successful real scheduled
   run, confirm milestone delivery/dedup where a legitimate event exists, and
   verify fail-closed handling of missing/stale/conflicting evidence. Reuse
   existing checks rather than adding a separate monitoring loop.
2. **Select one narrow, repeatable pilot** from the canonical
   `PROJECT_BACKLOG.md`, with a preregistered acceptance test, strict scope,
   bounded costs and no access to exchange order credentials. Assess actual
   engineering benefit before scaling to more task categories.
3. **Isolated implementation:** future agent may draft code/tests/docs only on
   an isolated branch, run the smallest relevant smoke, and open a reviewable
   PR. No direct writes to `main`, self-granted rights, unbounded retry loops,
   new secrets, live runtime mutation or autonomous PR merge by default.
4. **Versioned, gate-based expansion:** after the pilot passes, admit only
   explicitly allowlisted classes of low-risk, reproducible development
   tasks. Unknown tasks, unsupported future H components or unclear evidence
   go to a documented planning/review gate rather than speculative codegen.
5. **Strategic and trading authority remains separate:** material
   parameter/entry/exit/stop/sizing/universe changes require a distinct
   version, valid frozen evidence, migration/holdout controls, CI, rollback
   and the already documented human release gate. Real-money activation,
   private order rights and elevated risk always need separate explicit
   approval; neither successful CI nor autonomous coding implies permission.

This principle is permanent and extends to future generations. Work is not
the executor or polling substrate; use economical GitHub/MINI-PC/Supabase
infrastructure only if/when a separately approved pilot design demonstrates
a safe bounded implementation. Do not create another competing task list,
scheduler or persistent service merely to express this roadmap.

## Permanent market-regime learning lineage — from 2026-10-08

The existing passive market-regime observation and point-in-time episode
analysis, `research/v3/market-phase-reversal-observation-v1.md`, is a
**cross-generation research capability**, not a temporary response to the
October 2026 sell-off. Preserve it for every successor paper/shadow strategy
and, if real-money trading is separately released, for each live successor.
Future migrations must explicitly disposition its continued use, validated
replacement or evidence-based retirement using the regular lineage ledger;
silently dropping the capability is not allowed.

Do not confuse persistence of observation with proof of trading alpha:
the episode markers have no authority over entries, exits, sizing, scans,
promotions or live orders. Their only downstream effect is on an otherwise
already-eligible, bounded evaluation (including later real-fill/cost
evidence), using known-at timestamps and no hindsight leakage. No additional
ChatGPT Work run, push, parallel strategy, raw market archive or independent
control plane is created for this rule. Safety, candidate freezes,
pre-registered tests and live-release gates remain in force.
