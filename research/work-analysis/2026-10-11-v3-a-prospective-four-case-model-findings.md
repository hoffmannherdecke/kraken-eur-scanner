# V3-A: erster begrenzter Vier-Kandidaten-Livetest – fachliche Auswertung

**Beleg:** zwei Nutzerfotos der tatsächlichen Windows-PowerShell-Ausgabe des manuellen Mini-PC-Research-Laufs; zuletzt wurde die lokal gespeicherte JSON-Fallliste per `Get-Content -Raw | ConvertFrom-Json` im Fenster ausgegeben. Die **lokale JSON-Datei selbst liegt nicht als GitHub-/Supabase-Anhang** vor; Werte unten sind vom lesbaren Screenshot transkribiert. Lauf erfolgte nach PR #155 und Gebühren-Guard-Korrektur PR #156. **Nicht** als rückwärts rekonstruierte Live-V2R4-Originalentscheidung oder wirtschaftlichen V3-Freigabe-PASS behandeln.

**Eindeutige Disposition:** `PHYSICAL_BOUNDED_BATCH_FINISHED / 2_COMPARISONS_4_MODEL_HTTP_REQUESTS / BOTH_WAIT / 2_INPUT_ATTACH_SKIPS / NO_BUYS_NO_PAPER_FILLS / ECONOMIC_NOT_DEMONSTRATED`.

## Laufstatus und Budget

- `kind=V3_A_FOUR_CANDIDATE_INPUT_ONLY_MANUAL_BATCH_V1`.
- Ausgabe `status=COMPLETE_UP_TO_FOUR_OR_WINDOW_ELAPSED`, `cases=4`, `completed=2`, `http_model_requests_reserved=4`, `budget_max=8`, `orders=0`, `paper_state_changed=false`, `economic_edge_proven=false`.
- Die verbleibenden vier genehmigten API-Anfragen wurden **nicht** automatisch auf zusätzliche Fälle übertragen; der One-Shot-Report `C:\Users\ADMIN\Trading\Research\v3-a-four-candidate-input-only-20261010.json` ist bereits vorhanden und sperrt einen unkontrollierten Neustart. **Keine** neue Ausführung allein aufgrund dieser Ergebnisse beauftragt.
- Versuchszählung wichtig: Der Batch zählt **alle vier erfassten Kandidaten** gegen `MAX_CASES=4`, auch die zwei Fälle, die beim `COIN_ATTACH` vor dem ersten LLM-Aufruf aussteigen. **Zwei vollständig verglichene Fälle** sind kein vierfacher Modellvergleich.
- Die erfolgreichen Paare sind **zwei unabhängige Modellaufrufe pro Kandidat** auf identischem **späteren** Research-Ticker/Standardkontext, mit nur dem geschlossenen Coin-Entry-Feature im B-Arm. Das ist **nicht** eine Simulation der ursprünglichen offiziellen Paper-Erstentscheidung.
- Quelle und Leitplanken: manueller Research-Prozess, gefrorene V2R4-Baseline, 50 € Scout + 50 € Stage2, 0,60 % Taker je Seite, keine aktive H3/H6/H10-Entscheidungsautorität, keine V3-Aktivierung und keine Echtgeldaktion.

## Entscheidungen aus dem echten lokalen Forschungsprotokoll

| Paar | V2R4-Baseline `decision/setup_lane` | V3-A Coin-Evidence `decision/setup_lane` | Wertung |
|---|---|---|---|
| **TIA/EUR** | `WAIT / EXTENDED` | `WAIT / CONTINUITY` | Neue Daten verändern Setup-Einordnung, **kein BUY** |
| **ATOM/EUR** | `WAIT / IGNITION` | `WAIT / IGNITION` | Die Risiko- und Volumenbegründung wird spezifischer, **kein BUY** |
| **BAT/EUR** | *keine Bewertung* | *keine Bewertung* | `SKIPPED_INPUT_UNAVAILABLE`, `phase=COIN_ATTACH`, `failure_type=ValueError`, **0 Modellanfragen** |
| **USELESS/EUR** | *keine Bewertung* | *keine Bewertung* | `SKIPPED_INPUT_UNAVAILABLE`, `phase=COIN_ATTACH`, `failure_type=ValueError`, **0 Modellanfragen** |

**TIA-Basis-Gründe** laut Bildschirm: `PAIR_ONLINE`, `SPREAD_ACCEPTABLE`, `12H_MOVE_EXTENDED`, `1H_PULLBACK`, `CANDLE_VOLUME_UNAVAILABLE`, `NO_ENTRY_CONFIRMATION`. **TIA-V3-Gründe:** `PAIR_ONLINE`, `SPREAD_ACCEPTABLE`, `PRIOR_MOVE_EXTENDED`, `NEAR_TERM_WEAKNESS`, `15M_VOLUME_SOFT`. Der Coin-Input hat hier insbesondere eine echte negative Volumenbestätigung statt nur `UNAVAILABLE` geliefert. `CONTINUITY` ist bloß eine abweichende Setup-Klassifikation, **kein** besserer Handel per se.

**ATOM-Basis-Gründe:** `ONLINE_PAIR`, `SPREAD_ACCEPTABLE`, `FAST_MOVE_ALREADY_OCCURRED`, `WEAK_MULTI_PERIOD_CONTINUITY`, `MARKET_CONTEXT_MIXED`, `STRUCTURE_AND_REMAINING_MOVE_UNCONFIRMED`. **ATOM-V3-Gründe:** `PAIR_ONLINE`, `LOW_SPREAD`, `SHORT_TERM_VOLUME_WEAK`, `MOMENTUM_CONFLICT`, `COST_HURDLE`. Kein stärkerer BUY trotz spezifizierter Volumen-/Momentum-/Gebührenhürden.

Bei den beiden vollständig verglichenen Fällen ist in der Screenshot-Ausgabe `V3Stop` jeweils **leer**. Ein *gültiger* strukturbasierter `stop_eur`-/Stage2-/Netto-Einstiegsplan ist damit **nicht nachgewiesen**. Der Befund lässt keinen tatsächlichen Kaufsignal-/Fill-/PNL-Nachweis zu.

## Warum zwei Eingaben ausfielen – präzise Grenze des Wissens

In `paper_evaluator/v3_bounded_four_candidate_compare.py` erfolgt `phase=COIN_ATTACH` bei `attach_to_future_evaluator(candidate, standard, coin_evidence, snapshot_at)`. Der Adapter `paper_evaluator/v3_entry_handoff_probe.py` validiert unter anderem Pair-Identität, Known-at/Observed-at/Decision-Uhrzeiten, Verfallszeit, `COMPLETE`-/`VALID`-Status aller 1m/5m/15m-Frames, geschlossene Kurse, Volumenrelation, ATR14 und strukturelles Low. **Das laufende Batch-Protokoll speichert für solche Skips nur `failure_type=ValueError` und `phase=COIN_ATTACH`** – welcher konkrete Validator versagt hat, ist damit **nicht belegbar**. Nicht behaupten, dass BAT/USELESS keine realen Bars haben oder handelsfachlich `REJECT` wären. Beide zählen als **fehlgeschlagene Research-Input-Validierung**, nicht als modellbewertete Nichtkäufe.

## Entwicklungsentscheidung ohne neue Test-/Kosten-Schleife

1. **A-Lieferpfad fachlich bestätigt, wirtschaftliche Konversion noch nicht:** Zwei echte Coin-Input-Modellvergleiche führten zu `WAIT→WAIT`, null BUYs. Die Inputmerkmale sind sichtbar ins Modell gelangt und erklären Volumen-/Momentum-Schwächen. Dies ist kein Nachweis, dass eine offensivere V3 schlecht wäre; **n=2** ist dafür nicht repräsentativ.
2. **Zuerst Qualität des Coin-Adapters bewerten, ohne neue Modellaufrufe:** Der 50%-Skips-Anteil dieser kleinen Stichprobe ist ein sinnvoller lokaler Hinweis auf notwendige Provenienz-/Freshness-/Completeness-Diagnose. Für zukünftige, **separat freigegebene** Forschung nur sichere `COIN_ATTACH`-Untergründe (PIT, Stale, Volume, ATR, Pair), ohne rohe API-/Secret-Daten erfassbar machen. Kein erneutes Ausführen dieses *bereits abgeschlossenen* und durch den Research-Report gesperrten Budgets.
3. **V3-A ökonomisch nicht promoted; B-Hypothese offen und separat:** Behalte unverändert Kosten, 50+50 €, Anti-Chase/Stop/WAIT. Erst anhand sauberer prospektiver Input- und tatsächlicher Entry-/Stop-/Stage2-/Netto-Belege gesondert beurteilen, ob ein einziger WAIT- oder EXTENDED-Policy-Kandidat sinnvoll ist. Nicht beide gleichzeitig und nicht die komplette H1-H11-Liste aktivieren.
4. **Follow-ups und Quantifizierung:** Auch bei späterer 6h/24h-Nachbeobachtung die beiden verglichenen Kandidaten nach Paar/Zeit identifizieren und MAE/MFE vom Ask vom tatsächlich ausführbaren Netto-Trade strikt trennen. Für exakte `candidate_id`-/`known_at`-/Snapshotwerte ist das auf dem Mini-PC bereits vorhandene Research-JSON die autoritative Quelle, **nicht** dieses Screenshot-Transkript. Keine Nachreichung lokaler Forschungsrohdateien durch GitHub-Controlling behaupten.

**Status:** `PHYSICAL_INPUT_ONLY_RESEARCH_FINDINGS_RECORDED / ECONOMIC_GATE_NOT_PASSED`; rein dokumentierter Forschungscheckpoint. Die dauerhafte Übernahme auf `main` wird erst nach erfolgreicher GitHub-Prüfung bestätigt. **V2R4 bleibt aktiv** und unverändert, H3/H6 nicht aktiv und V3 Paper/Shadow/Echtgeld ausdrücklich nicht freigegeben.
