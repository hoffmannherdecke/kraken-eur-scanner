# MINI-PC V3-A: echter Coin-Evidence-/One-Shot-Vergleich mit ZRO/EUR

**Nachweisdatum:** 10.10.2026, ca. 20:49 UTC. **Belegtyp:** vom Nutzer vorgelegtes PowerShell-Foto der lokalen Mini-PC-Ausgabe; nachträglicher rein lesender Abgleich des **originalen** Kandidaten in Supabase `public.paper_candidate_outcomes`. **Kein** dauerhaft gespeichertes maschinenlesbares Paar der beiden Modell-Responses nachgewiesen; dieser Bericht ist eine sorgfältige Transkription des sichtbaren Kurzoutputs, nicht fiktiv archivierte Raw-Evidenz.

## 1. Technischer Verlauf und Grenzen

- Der erste `-Execute`-Versuch brach als `BLOCKED_PRECONDITION_OR_SOURCE / ValueError` ab. Er ist **kein** erfolgreicher V3-Vergleich; genaue damalige Ursache wurde nicht bewiesen. Kein Hinweis auf Orders; Modellaufruf-Anzahl dieses Fehlversuchs aus dessen Ausgabe **nicht nachgewiesen**.
- Die gezielte Diagnoseverbesserung wurde mit [PR #148](https://github.com/hoffmannherdecke/kraken-eur-scanner/pull/148) und drei erfolgreichen CI-Prüfungen in `main` übernommen. Der anschließende **lokale** `-DiagnoseOnly` ergab `INPUT_READY_NO_MODEL_CALLS_NOT_A_STRATEGY_PASS`: echter **TIA/EUR**-Handoff, abgeschlossene `1m/5m/15m`-Bars jeweils `VALID`, `COMPLETE`, gefrorene Dateien mit Hashes abgeglichen, 0 Modelle, 0 Orders, kein Secretzugriff und keine V2R4-Änderung.
- Im nachfolgenden separat manuell gestarteten `-Execute` wählte das Skript einen **anderen frischen Kandidaten: ZRO/EUR** mit kanonischer ID `20261010-204153-ZRO-EUR-r193618174847939`. `status=ISOLATED_MODEL_PAIR_COMPLETE_NOT_A_PROFITABILITY_RESULT`, `model_calls=2`, `same_candidate_same_ticker_same_standard_context=true`, `coin_evidence_only_changed_input=true`, `active_v2r4_changed=false`, `active_h3_changed=false`, `automatic_promotion=false`, `paper_positions_created=0`, `real_orders=0`, `valid_paper_trade_proven=false`, `economic_edge_proven=false`; lokaler Wrapper `FINISHED_PAPER_UNCHANGED`.
- `source_series_id=PAPER-V2R4-20261009T110135Z`, `source_strategy_revision=V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION`. Keine V3-Paper-, H3-, H6- oder Echtgeldaktivierung.

## 2. Getrennte Entscheidungsarten – keine falsche Baseline

| Entscheidung | Datenzeit und Funktion | Ergebnis | Gründe (aus sichtbarer Ausgabe bzw. Originaldaten) |
|---|---|---|---|
| **Offizielles produktives V2R4-Paper-Original** | Kandidatenereignis `2026-10-10T20:41:53.691428Z`; `public.paper_candidate_outcomes.evaluated_at=20:42:21.066736Z` | `REJECT / EXTENDED` | `late_acceleration_fomo_risk`, `remaining_move_unsubstantiated`, `structural_stop_unavailable`, `no_volume_confirmation` |
| **Neu erzeugter Research-Baseline-Modellaufruf** | Späterer **einheitlicher** Modell-Snapshot ca. `20:48:58Z`, **ohne** neue Coin-Entry-Evidence | `WAIT / IGNITION` | `PAIR_ONLINE`, `LIQUIDITY_GATE_PASS`, `TIGHT_SPREAD`, `IGNITION_UNCONFIRMED`, `ENTRY_EFFICIENCY_UNCLEAR`, `STOP_NOT_DEFINED`; zwei WAIT-Conditions |
| **Neu erzeugter Research-Modellaufruf mit Coin-Entry-Evidence** | **Derselbe spätere Snapshot** ca. `20:48:58Z`; neue Coin-Daten zu diesem Zeitpunkt bekannt | `WAIT / CONTINUITY` | `WEAK_RECENT_VOLUME`, `BELOW_RECENT_CLOSE`, `RECLAIM_CONFIRMATION_NEEDED`; zwei WAIT-Conditions |

Bei beiden Research-Entscheidungen: `expected_remaining_move_pct=null`, `risk_reward_after_costs=null`, `valid_stop_below_ask=false`, `valid_stage2_above_ask=false`; damit **keine** valide ausführbare BUY-/Stop-/Stage2-Kette. Das vorangegangene TIA-Eingangspreflight und der vollständige ZRO-Modellvergleich sind **nicht** derselbe Kandidatenfall. Die lokale Ausgabestruktur markiert ausdrücklich `baseline_is_new_independent_replay_not_official_original_decision=true`.

**Zeitmethodik:** Zwischen offizieller Erstentscheidung `20:42:21Z` und Research-Vergleich `20:48:58Z` liegen ca. **6 Minuten 37 Sekunden**. `evidence_known_at_utc=2026-10-10T20:48:58.063081Z`; die später erhobenen Coin-Bars sind **kein rückwirkend verfügbares Feature** der Erstentscheidung um `20:42:21Z`. Die beiden Research-Varianten haben untereinander den gleichen späteren Entscheidungs-/Ticker-Kontext; sie dürfen **nicht** als kausaler Nachweis gegenüber der offiziellen früheren V2R4-Entscheidung gewertet werden. Ein einzelner neuer KI-Modellaufruf pro Arm unterliegt zusätzlich Stichproben-/Modellvarianz.

## 3. Belastbare Folgerung für V3

1. **Physische Mini-PC-Input-Integration bestanden:** genau ein echter Kraken-Spot-EUR-Kandidat wurde im isolierten Modell-Vergleich mit 1m/5m/15m geschlossenem Coin-Kontext verarbeitet; die Entscheidungen unterscheiden sich **in Setup-Lane und Gründen**. Neue Input-Information **ist** im Modell angekommen. Dies ersetzt weder einen echten V3-Paper-Trade noch den prospektiven Nachweis des wirtschaftlichen Mehrwerts.
2. **Keine verbesserte BUY-Konversion belegt:** Research-Vergleich `WAIT→WAIT`, 0 BUY. Die neue Lagebestimmung benennt gerade konkrete fehlende Volumen-/Reclaim-Bestätigung. Nicht die Schutzfilter blind lockern.
3. **Geplante Preis-/Stopp-Fähigkeit bleibt offen:** Beide Research-Varianten haben keinen validierten Stop/Stage2/After-Cost-CRV. Aus diesem Einzelfall folgt **nicht**, dass OHLC/ATR unmöglich als Stopbasis taugt oder ein ganz neuer Stop-Algorithmus sofort freizuschalten sei: benötigter Stop muss beim nächsten wirtschaftlichen Evaluator-/Risk-Gate als echte Preistrade-Evidenz nachgewiesen werden.
4. **Kausal sauberer nächster Schritt:** Bestehenden **V3-A-Owner** von `MORE_TESTING_REQUIRED` auf **`PHYSICAL_INPUT_AND_MODEL_HANDOFF_PASS_ECONOMIC_NOT_PROVEN` als Unterevidenz** anreichern, aber `migration_status=MORE_TESTING_REQUIRED` beibehalten. Ein einzelnes `WAIT/WAIT` rechtfertigt weder Wiederholungs-Loop noch automatisches B-Policy-Experiment. Für prospektive Entscheidungsevidenz müssen Kandidat/Ticker/Feature `known_at` in einem **vorab** kontrollierten Zeitpunkt erfasst werden und anschließend BUY→simulierter Fill→Stop→Netto verfolgt werden. Verfügbarkeit eines Features 7 Minuten später ist nicht `known_at` am Ursprung.
5. **Keine unzulässige Promotion:** Nur einmalig punktuelle Diagnose und dieser dokumentierte E2E; neuer Shadow, neues Paper, H3/H6, gelockerte Kauf- oder Stopregeln, Echtgeld und neue Scheduler bleiben gesperrt. Nutzerfreigabe für spätere separate Runtime-/Strategieänderungen und die bestehende wirtschaftliche Freigabe sind nicht ersetzt.

**Eindeutige Disposition:** `V3_A_PHYSICAL_INPUT_E2E_PASS / V3_A_ONE_CANDIDATE_DECISION_DELTA_WAIT_TO_WAIT / CAUSAL_PROSPECTIVE_ECONOMIC_GATE_OPEN / NO_V3_ACTIVATION`.

**Kanonische Folge-Owner:** `research/v3-migration-ledger.json#coin_specific_entry_evidence_provenance`, `research/strategy-learning-causal-gate-v1.json#v3_opportunity_first_research`, `docs/minipc-analytics-rollout-v1.md`, `PROJECT_BACKLOG.md#MINIPC_ANALYTICS_ROLLOUT_V1`.

**Datenherkunftshinweis:** Die PowerShell-Ausgabe ist vom Nutzer als Foto im Gespräch geliefert, **nicht** als GitHub-CI-Log oder Supabase-V3-Experimenttabelle zu behandeln. Der ursprüngliche V2R4-Datenbankeintrag wurde ausdrücklich unabhängig read-only gegenprüft. Keine behauptete dauerhafte Speicherung beider Modell-Responses.
