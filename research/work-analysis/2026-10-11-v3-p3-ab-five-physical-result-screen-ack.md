# V3 P3 Standard/Experimental – abgeschlossener Originalreport, 11.10.2026

## Nachweis und genaue Grenze

**Neuer Belegstatus: USER_UPLOADED_ORIGINAL_JSON_PARSED_AND_HASHED.** Das lokale Testende war bereits zuvor durch das PowerShell-Foto um ca. 19:49 MESZ bestätigt (PR #187). Die anschließend im Chat hochgeladene, tatsächlich mit einem JSON-Parser vollständig gelesene Datei `v3-p3-ab-five-http10-6h-20261011.json` ist **4.730 Bytes** groß und besitzt den **SHA-256 `6a0fe8aeda0aab083d957edc27f85e190419a99588a936f1cde18568abbfc485`**. Dateipfad am Mini-PC laut Foto: `C:\Users\ADMIN\Trading\Research\v3-p3-ab-five-http10-6h-20261011.json`. Der Hash belegt den analysierten Upload, **nicht** eine unabhängige API-/Kraken-/Windows-Attestation. Die Originaldatei liegt als Nutzeranhang im Chat, ihre Rohinhalte wurden **nicht** in GitHub committed. Screenshot ist jetzt nur die ergänzende physische Abschlussbestätigung.

Freigabe/Technik: PR #186, `V3_P3_AB_FIVE_HTTP10_6H_RESEARCH_V1`, **einmalig** maximal fünf qualifizierte Original-CONTINUITY-Setups, 10 Modell-HTTP-Versuche inklusive Retries, 360 Minuten Fenster; ursprüngliche V2R4-Paper-Serie ist ausschließlich lesender Bezug. `started_at_utc=2026-10-11T13:38:27.308286+00:00`, letzte gespeicherte Fallentscheidung `2026-10-11T17:45:53.984321+00:00`; Endzustand `FINISHED_FIVE_QUALIFIED_OR_SIX_HOUR_WINDOW`. Erreicht wurde **das Fünferlimit**; nicht behaupten, volle sechs Stunden seien verstrichen. Freigabe ist mit dem ausgeführten einmaligen Prozess **verbraucht**; keine Freigabeübertragung aus fünf unbenutzten potenziellen HTTP-Versuchen.

## Dateigeprüfter Abschluss

| Kriterium | Wert im Originalreport |
| --- | ---: |
| Qualifizierte Fälle / OpenAI-HTTP-Versuche reserviert | **5 / 5** |
| Standard-P3 eligible / Experimental nur incremental eligible | **5 / 0** |
| Originale Modellentscheidungen `WAIT` / `BUY_SCOUT` / `REJECT` | **5 / 0 / 0** |
| Full-P4-Status `FULL_WAIT_VALIDATED_OFFLINE` | **5** |
| `observed_origins` / `no_review` / `invalid_input` | **38 / 30 / 3** |
| `metadata_fail` im JSON | **0 (nicht zuverlässig gezählt, siehe unten)** |
| `orders` / `paper_changed` / `paper_writer_started` | **0 / false / false** |
| `economic_edge_proven` / `actual_6h_24h_net_outcomes_verified` | **false / false** |

Alle fünf Fälle gehören zur bisherigen technischen Paper-Serie `PAPER-V2R4-20261009T110135Z` als Ausgangskohorte und tragen `eligible_arm=STANDARD`, `experimental_status=BASELINE_ALREADY_ELIGIBLE_NOT_INCREMENTAL`, `model_setup_lane=CONTINUITY` sowie eine echte Modell-`response_id`. Das belegt **fünf modellbasierte WAIT-Verträge** im Forschungsweg, keine tatsächlichen Transaktionen, keinen positiven Buy-/Stop-/Stage2-E2E und keine matched Experimental-Alpha-Messung.

## Fünf Fälle und eindeutige Deutung der vorhandenen Reason-Codes

| Originalcoin | Echter Modellentscheid | Charakteristische Codes (nicht vollständig) |
| --- | --- | --- |
| EIGEN/EUR | WAIT | `MICROSTRUCTURE_DEPTH_LIMITED`, `RECENT_ADVANCE_RAISES_CHASE_RISK`, `1M_VOLUME_WEAK`, `REMAINING_MOVE_UNCONFIRMED`, `FEES_REQUIRE_ROOM_TO_RUN` |
| XLM/EUR | WAIT | `5M_VOLUME_ELEVATED`, `15M_VOLUME_WEAK`, `COST_EDGE_UNCONFIRMED` |
| RENDER/EUR | WAIT | `EXTENDED_AFTER_RECENT_RUN`, `15M_VOLUME_BELOW_BASELINE`, `NET_EDGE_UNCONFIRMED` |
| CC/EUR | WAIT | `PERSISTENT_6H_CONTEXT`, `SHORT_TERM_WEAKNESS`, `FOLLOW_THROUGH_UNCONFIRMED`, `FEE_HURDLE_REQUIRES_MORE_ROOM` |
| MON/EUR | WAIT | `5M_VOLUME_ELEVATED`, `1H_MOMENTUM_SOFT`, `1M_VOLUME_WEAK`, `COST_EDGE_UNCONFIRMED` |

**Befund zur vermuteten Inkonsistenz:** Der File-Parser findet unter den fünf Fällen **kein einziges `5M_VOLUME_WEAK`**. Tatsächlich waren die positiven Hard-Checks der Standard-Eligibility auf der **geschlossenen 5m-Volumenrelation ≥1,2**. Schwaches **1m-** oder **15m-Volumen** ist damit logisch vereinbar; XLM und MON nennen ausdrücklich `5M_VOLUME_ELEVATED`. Es ist **kein technischer Widerspruch** zwischen 5m-Gate und den im Report gespeicherten anderen Zeitraumurteilen nachgewiesen. Ob die Einzelurteile empirisch berechtigt oder zu konservativ sind, erfordert die PIT-Originalbars und die vollständige zeitgleich an das Modell gelieferte Kontext-/Preisstruktur; die Reportdatei enthält weder Zahlenreihen noch komplette Modellantworten.

**Begrenzte wirtschaftliche Interpretation:** Mehrere Modelle geben schwache Trendfolge, Chase-Risiko, nicht ausreichend belegte Restbewegung und die mindestens **1,20 % Taker-Fees round-trip plus Spread und Slippage** als Gründe für WAIT an. Kein verifizierter kostenbereinigter Nettoertrag, kein Fill, keine Gewinn-/False-BUY-Rate. Mehr Modell-WAITs sind **kein** beweisbarer Erfolg oder Scheitern eines gelockerten Volumengates; mangels Experimental-Inkrementalfall wurde das isolierte A/B-Delta **nicht getestet**.

## Evidenzgrenzen im bestehenden Runner (technisch anhand Repo-Code geprüft, keine weiteren Eingriffe)

1. `no_review=30` ist ein reiner Zähler ohne Einzelfall-ID/konkrete gescheiterte Standard-/Experimental-Checks. **Nicht** behaupten, diese 30 seien durch dieselbe technische oder fachliche Regel gesperrt; deshalb keine Gate-Anpassung aus der Zahl.
2. `invalid_input=3` entsteht aus einem breiten `except Exception` vor der Modellberechtigung, ohne Provenienz von Stage/Fehlertyp; die **konkreten drei Ursachen sind nicht rekonstruierbar**. `metadata_fail` wird im aktuellen Runner zwar mit 0 initialisiert, aber **nicht hochgezählt**: `metadata_fail=0` ist **kein belastbarer AssetPairs-Fehlerfrei-Nachweis**.
3. Die in den Fällen gespeicherte `decision_at_utc` bezeichnet die **vor dem HTTP** bestimmte Review-/Eligibility-Uhrzeit. Der P4-Validator erhält intern eine spätere `received_at`-Uhrzeit, doch diese finale Bewertungszeit, der genaue WAIT-TTL und die modellierten deterministischen `watch_conditions` werden **nicht** dauerhaft pro Fall gespeichert. Die vollständige zeitliche Modell-PIT-Nachprüfbarkeit bleibt deshalb begrenzt. Case `known_at_utc` und `decision_at_utc` differieren im Upload um ca. **0,18–0,22 Sekunden**; das ist **keine** dokumentierte HTTP-Latenz.
4. Die fünf Cases haben eine ursprüngliche Candidate-Age zur gespeicherten Eligibility von **182 bis 871 Sekunden**, Quelle nur Reportzeiten. Das weist **nicht** den gesamten Kraken→Model→P4→6/24h-Economics-Weg bis zum Nettoergebnis nach.
5. Verfügbare `reason_codes` sind begrenzt auf die vom Runner persistierten bis zu **acht Codes**. Sie sind Begründungslabels, keine unabhängigen beweisenden Preis-/Volumenmessungen. `FULL_WAIT_VALIDATED_OFFLINE` validiert einen realen Modell-Output gegen P4, aber erzeugt **keinen** simulierten Orderpfad.

## Verbindlicher Folgeschritt – kein weiterer physischer Modelllauf autorisiert

**P0/P3/P4/P8 Owner, vorhandenem 10:15-Work-/Projektcontrolling zugeordnet:** Ergebnis als `VERIFIED_UPLOADED_JSON` markieren und **ohne weitere Tests, Modelle oder Orders** die nun bekannte Evidenzlücke priorisieren. Für eine *zukünftige* separat freizugebende Runde vorab festlegen: (a) Standard- und Experimental-Eligibility einschließlich scheiternder Gate-Namen je Kandidat (minimal aggregiert), (b) getrennte Phasenfehler bei frischer Coin-PIT / Kraken AssetPairs / 15m-Historie, (c) getrennte Eligibility- und P4-Response-Timestamps sowie gültige `WAIT`-TTL und deterministische Watch-Conditions ohne Geheimnisse, (d) echter optionaler virtueller BUY-Outcome-Pfad inklusive konservativer Kosten und späteren 6h-/24h-Followups. **Diese Verbesserung ist ein Backlog-/Entwicklungsbefund, keine Freigabe eines neuen Runs.** Keine Nachträgliche Rekonstruktion von fehlenden Preisen behaupten, keine Modell-HTTP-Versuche, keine V2R4-/Mini-PC-/Cloud-/Scheduler-/Echtgeld-Mutation.

**V2R4 bleibt einzige aktive Paper-Strategie.** Keine V3-Paper-Freigabe und kein Experiment nach diesem abgeschlossenen Fünferlauf. Der vorherige Screenshot-Status `SCREENSHOT_ACK_ONLY` und seine Aufforderung, die Datei erst hochzuladen, sind durch diesen tatsächlich gelesenen Originalupload **überholt**.

## Follow-up 11.10. – künftiger Diagnosevertrag als **reine Offline-Implementierung**

Der vorhandene P0/P3/P4/P8-Folgeauftrag ist ohne neue Modell-/Mini-PC-Freigabe in `paper_evaluator/v3_p3_future_diagnostics_offline_v1.py` und `tests/test_v3_p3_future_diagnostics_offline_v1.py` umgesetzt. Der isolierte Code ist **nicht** in den verbrauchten Teststarter, den aktiven V2R4-Paper-Pfad oder irgendeinen Scheduler eingebunden. Es gibt **keinen** neuen physischen Lauf.

- `review_diagnostic`: legt für **denselben** Standard-/Experimental-Resultatsnapshot den genauen Status und die fehlgeschlagenen Namen der acht bestehenden Standard-Hard-Checks offen. Unvollständig/inkonsistent belegte acht Checks ergeben `UNKNOWN`, niemals aus Schweigen ein BUY/Experimental-Approval. Unverändertes Standard-Gate 5m-Volumen ≥1,2; Experimental ausschließlich 1,0–<1,2, sofern nur diese eine Prüfung nicht bestand.
- `phase_failure`: feste technische Stufen für ersten Kraken-Ticker, optionale Quellen, 1m/5m/15m Coin-PIT, geschlossene 15m-Historie, neuen Ticker, Handoff, **Kraken-Spot-EUR-AssetPairs**, P3-Review, Modell und P4. Nur Exception-Klasse, nie Fehlertext, API-Key, URL, Modell-Prompt oder rohe Marktpreise; AssetPairs-Fehler können erstmals separat gezählt werden. Dies repariert **nicht rückwirkend** die drei unbekannten Fehler des abgeschlossenen Runs.
- `full_review_receipt`: verlangt explizit geordnete und frische PIT-/Metadata-/Ticker-/Eligibility-/Modellrequest-/Modellantwort-/P4-Uhrzeiten, gültige Response-ID, echte P4-Statusidentität und ordnungsgemäße WAIT-TTL sowie deterministische Watch-Conditions aus der vorhandenen Metrik-/Operator-Allowlist. Wenn etwas fehlt, **kein** positiver Telemetrienachweis. Antwort-Latenz wird als Request→Response ausgewiesen, nicht mit `eligibility_at` verwechselt; keinerlei P&L-/API-/BUY-Fill-Nachweis.
- **Nicht erreicht:** Die Funktionen laufen nur über übergebene Testfixtures und werden absichtlich **noch nirgends an das reale Modell oder die Mini-PC-Pipeline verdrahtet**. GitHub-CI beweist Format/Negativfälle, weder künftige reale 30/3 Ursachen, 6h/24h-Followups noch wirtschaftliches Alpha. Erst ein *neues*, ausdrücklich autorisiertes zukünftiges Shadow-/Modellfenster dürfte die neue Instrumentierung physisch benutzen. Eine bloße Prüfung ist keine Freigabe.

Unverändert: **0 weitere** Modellcalls/Orders, genau eine aktive V2R4-Paper-Strategie, 0 V3-Paper-Promotion, 0 Runtime-/H3-/H6-/Runner-/Work-Zeitänderungen. Die bereits verbrauchte PR-#186-Freigabe bleibt **geschlossen**.
