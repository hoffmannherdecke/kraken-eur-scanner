# V2 → V2R3 → V2R4 → V3: wirtschaftliche Stellschrauben statt pauschaler BUY-Lockerung (11.10.2026)

**Evidenz-/Entscheidungsstatus:** `NEW_CURRENT_READONLY_V2R4_STRATIFIED_SNAPSHOT / PRIORITIZED_ONE_CHANGE_V3_RESEARCH_VARIANTS / NOT_RELEASE_APPROVED`. Einmalige ausdrücklich beauftragte *strategische Neubewertung* aller Strategien im Licht des aktuellen 11.10.-Datenstands und der abgeschlossenen V3-B-Fünferläufe. **Keine** produktive Schwelle verändert, kein neues Budget/Shadow/Model aufgerufen, keine Echtgeldaktionen, keine neue Work- oder GitHub-Überwachung. Bestehender V3-P2/P3/P4-Owner und vorhandene Causal-Gates behalten Vorrang. Vermeidet weiteren generischen Null-BUY-Auditzyklus: diese Datei enthält zusätzlich **neue zahlenmäßig stratifizierte V2R4-Sensitivität** samt konkret abgegrenzten Varianten.

## 1. Zeitlich und kausal richtige Vergleichsbasis

| Version/Phase | Beleg | Beobachtete echte Handelbarkeit |
|---|---|---|
| V2/V2R2 frühe Explorations-Paper | 20 zurückgewiesene Frühfälle, 3 mit ≥+5 % 6h MFE, 7/20 mit MAE≤−3 %; Papier nur kleines N, keine exakte neue Baseline | Verpasste Impulse und erhebliche Fehlkaufrisiken parallel; keine Profitabilitätsbehauptung |
| V2R3 eingefrorener 1.000er Originalabschluss, 07.10. | 942 initial WAIT; final 999 REJECT/1 BUY_SCOUT; einziger MON/EUR-Trade −1,5462 EUR/−3,0924 % netto, 0 weitere BUYs; 291 24h MFE≥+5 %, auf 174 Paare/6h-Episoden kollabiert | WAIT-Überziehungszeit p50 348s/p90 1.203s und konservativer Full BUY-Entscheider; ex-post Spitzenerträge nicht kaufbar |
| V2R4 Original-72h-Kohorte, 10.10. | 1.677 Kandidaten, 1.086 WAIT, 946 WAIT expiry ohne Model Recheck, 127 true Trigger-Rechecks, 0 BUY/Trades | Schnellere technische Trigger/Tradability haben **die BUY-Semantik nicht substanziell verändert**; strukturiert übergebene eigene 1/5/15m OHLC/ATR/Volume fehlten initial |
| **V2R4 aktuelle additive technische Serie**, SQL read-only 11.10. nach 11:25 UTC | **1.864 eindeutige Kandidaten** über `PAPER-V2R4-20261007T184255Z` (1.011) und `PAPER-V2R4-20261009T110135Z` (853), identische Strategie; **1.189 initial WAIT, 675 initial REJECT, 0 initial/finale BUYs**; 1.038 `V2R4_WAIT_EXPIRY_V1`, 141 `V2R4_LOCAL_TRIGGER_RECHECK_V1`, 0 BUY, verbleibende 10 nicht als finalized expiring interpretieren. **Nicht** mit dem 72h-Stichtag vermischen. | Aktuell ca. 87,3 % aller initialen WAIT ohne ausgelösten Recheck, ca. 11,9 % mit tatsächlichem Recheck; Trigger allein löst BUY-Blockade nicht |
| V3-A und V3-B 11.10. | V3-A veränderte Input, aber nicht Kaufmodell, keine BUY-Evidenz; zwei separate V3-B-One-Shots **5/0/0 + 5/0/0** (Originalkandidaten / matched full evaluator / Model HTTP), V3-B prüfte nur EXTENDED Second-Leg Eligibility; im zweiten vier bis sechs Rechecks je Original, 2 echte Markt-Nichtbestätigungen, 3 UNKNOWN mit 1/5/15m VALID. | Weder vollständiges V3-Multi-Lane-Modell noch Kosten-/BUY-/Stop-/Stage2-Proof getestet; keine Strategiepromotion |

Originale: `research/work-analysis/2026-10-11-no-buy-decision-logic-consolidated-root-cause-audit.md`, `2026-10-07-v2r3-final-review.md`, `2026-10-10-v2r4-original-72h-productivity-review.md`, `2026-10-10-v2r4-to-v3-economic-learning-handoff.md`, `2026-10-11-v3b-shadow5-second-gate-triage.md` und `research/strategy-learning-causal-gate-v1.json`.

## 2. Neue **echte** stratifizierte V2R4-24h-Daten (read-only Supabase 11.10.)

Maturity-Grenze `followup.opportunity_audit.horizons.1440.complete=true` (unreife Kandidaten ausdrücklich zensiert). Renditen am ursprünglichen Evaluator-Ask, nicht an einem späteren Triggerpreis oder realem Paper-Fill. **Jede Zeile enthält korrelierte Kandidaten derselben Coins**; zusätzliche Episodenkontrolle nach Paar/UTC-6h:

| Initiale Kohorte bzw. spätere Recheckroute | 24h-reif | p50 MFE | p50 MAE | p50 Endschluss | 24h MFE≥5 % | MAE≤−5 % | Paar/6h Episoden |
|---|---:|---:|---:|---:|---:|---:|---:|
| Alle | 803 | +3,943 % | −5,144 % | −1,746 % | 337 | 412 | 484 |
| WAIT ohne Trigger bis TTL (`V2R4_WAIT_EXPIRY_V1`) | 429 | +3,191 % | −4,731 % | −1,206 % | 152 | 208 | 265 |
| WAIT **echter** `V2R4_LOCAL_TRIGGER_RECHECK_V1` | 69 | +7,862 % | −3,379 % | +0,877 % | 47 | 22 | 53 |

**Interpretation:** Recheck-Trigger sind bereits eine sinnvolle *selektive* Vorauswahl (47/69 mit MFE≥5 %, 22/69 mit ≥5 % zwischenzeitlichem Gegenlauf, bei Paar/6h entdoppelt 36/53 Episoden mit ≥5 % MFE und 18/53 mit ≤−5 % MAE). Das spätere MFE ist aber **nicht** das am Trigger verfügbare Restpotenzial, und der mediane spätere Endschluss +0,877 % liegt **unter** den 1,20 % Kraken Taker-Roundtrip **ohne** Spread/Slippage. *Post-treatment self-selection*; keine kausale Differenz, keine 69 potenziell rentablen Trades.

**Nach initialer Setup-Lane in 803 gereiften 24h-Kandidaten:**

| Lane | n | MFE≥5 % | MAE≤−5 % | p50 MAE | p50 Endschluss |
|---|---:|---:|---:|---:|---:|
| EXTENDED | 476 | 196 | **268** | **−6,01 %** | −2,20 % |
| CONTINUITY | 183 | 74 | 66 | −3,36 % | −0,23 % |
| REVERSAL | 51 | 25 | 21 | −4,08 % | +1,04 % |
| IGNITION | 35 | 17 | 21 | −5,47 % | −2,71 % |
| NONE | 58 | 25 | 36 | −7,17 % | −3,19 % |

**Interpretation:** EXTENDED ist die mit Abstand größte, zugleich bei historischen MAE besonders gefährliche Lane; blindes Abschalten von Anti-Chase/Restpotenzial/Stop ist falsch. CONTINUITY wäre als **separat** gelernter neuer frischer Einstieg vorrangig zu testen: niedrigere beobachtete MAE und weniger negative Schlusskurse als EXTENDED, aber Median-Endschluss ebenfalls **nicht kostenpositiv**. REVERSAL kleines N, nur +1,04 % Endschluss < Gebühr-only; keines rechtfertigt sofortige BUY-Freigabe. Episoden/UTC-Strata, negative matched Controls, Lookahead und echter Stop-vor-MFE werden bei jeder Variante geprüft.

**V2R4-Model-Grundkürzel (1864 Fälle):** Quellfreitext enthält zahlreiche mehrfache, nicht normalisierte und **auch positive** Codes (`spread_acceptable`, `pair_online`). Häufige *negative* Muster: unsicheres Restpotenzial (`insufficient_remaining_move_evidence` 126, `remaining_move_unconfirmed` 124, `remaining_move_unverified` 122), ausgeweiteter früherer Move, fehlende Volumenbestätigung (`volume_confirmation_missing` 94, `no_volume_confirmation` 69), fehlende strukturelle Stop-Evidenz (`no_structural_stop_evidence` 62 plus Synonyme), schwache BTC/ETH-/Makroregime- oder Momentumfaktoren. **Keine Summierung dieser Codes zu unabhängigen Kausalvetos**, keine Lockerung nur aufgrund Codefrequenz.

## 3. Echte Stellschrauben, streng nach Rendite-Risiko und Evidenz sortiert

### A. Höchste Priorität: P2 **zeitabhängiges WAIT statt terminales TTL** (`WAIT_FRESH_REVIEW_ONLY_V1`)

**Eine einzige vorgeschlagene Policyänderung:** Nach altem WAIT-Ablauf bleibt ursprünglicher Kauf **nicht** autorisiert und die historische Entscheidung final. Wird später jedoch eine **eigenständig neue, abgeschlossene und zeitlich danach bekannte** Kraken-Spot-EUR-Kerzen-/Volumen-/Preisstruktur bestätigt, darf eine **separate vollständige Neubewertung** auf dem späteren Snapshot angefordert werden. Eine abgelaufene WAIT-Condition allein oder eine spätere 24h-MFE reicht **nicht**. Keine generelle TTL-Verlängerung, kein laufender Daueralarm, keine automatische Order und kein Recycling einer alten WATCH-Condition. Reuse der bestehenden Validatoren, keinen parallelen neuen Watcher. Vergleich exakt auf denselben Kandidaten, Paar, Zeit/Uhrzeit, Kosten und V2R4-Baseline; stale/UNKNOWN → kein Recheck. **Diese Variante ist eine Lockerung der Terminalität, nicht des Risikos.**

Warum zuerst? Aktuell 1.038/1.189 WAIT initial ohne tatsächlichen Recheck; 429 gereifte WAIT-Abgelaufene enthalten 152 MFE≥5 %, aber 208 MAE≤−5 %. Kein ungefilterter Buy, sondern gezielte spätere Wiederzulassung zur vollen Prüfung.

### B. Zweite isolierte Hypothese: P3 **CONTINUITY/Breakout bestätigt statt binärem Soft-Factor-Veto** (`CONTINUITY_FRESH_PROOF_SOFT_CONTEXT_V1`)

Nur wenn der Kandidat eine **jetzt** bekannte geschlossene neue 5m-/15m-Struktur, sachlich bestätigtes Volumen, plausible neue Kursbasis und handelbare Kosten/Stop-/Stage2-Kriterien hat, soll ein ansonsten schwaches optionales Zusatzsignal (z.B. breite Marktstimmung, News nicht verfügbar, passiv fehlende H10/H11-Kontexte) **nicht allein endgültig blockieren**. Noch ist unbewiesen, dass der derzeitige Prompt diese Faktoren überhaupt als Einzel-Hard-Veto nutzt; der Test muss ein solches Veto im tatsächlichen Entscheider erst *kausal* isolieren, bevor dessen Rolle geändert wird. **Andere Hard-Gates niemals optionalisieren**. Lane CONTINUITY (183 24h-reife; MAE p50 −3,36 %) vor der gefährlicheren EXTENDED-Lane untersuchen, nicht alle Setups gleichzeitig lockern.

### C. Nur nach separater Bestätigung: P3 **neue BASE nach EXTENDED, nicht pauschales Anti-Chase-Aus** (`EXTENDED_NEW_BASE_STRUCTURAL_RESET_V1`)

Einen ursprünglich verlängerten Move nach einer wirklich neuen abgeschlossenen Konsolidierung als **neuen Entscheidungszeitpunkt** behandeln, ohne die alte 6h-/12h-Überhitzung ewig als eigenständiges Ausschlusskriterium weiterzuführen. Second-Leg V3-B lieferte bisher **0 geeignete Full-Review-Fälle**; erst technische UNKNOWN-/Volume-Behandlung und valide neue PIT-Structure voneinander trennen. Wegen EXTENDED MAE p50 −6,01 % keine Erhöhung unmittelbarer BUY-Freigaben, keine unbestätigten Pullbacks und kein bewusstes FOMO-Chasing.

### D. Echte 1m/5m/15m-Kerzen/ATR-Stopdaten zum **entscheidenden Modellconsumer** übertragen

Das ist **kein Lockerungshebel**, sondern die technische Voraussetzung, die die Risikoplanung ohne erfundene Stops verbessern kann. 0/1731 V2R4-Kandidaten hatten initialen strukturierten Coin-Evidence-Consumer im alten Audit; einzelne V3-A-Tests mit demselben BUY-Modell blieben WAIT. Ohne Nachweis des Full-Model-Coin-Consumers und eines tatsächlich validen Stop-/Stage2-Plan kann B nicht sinnvoll wirtschaftlich bewerten. Fehlende optionale externe Quellen neutral, fehlende **Pflicht-Stops** fail-closed.

## 4. Bewusst **NICHT** pauschal lockern

- 0,60 % Taker je Seite plus echte Spread/Slippage, online Kraken Spot-EUR, Orderminimum/Liquidität/realer Ask.
- Struktureller Stop **unter** dem Ask, Stage2-Bestätigung **über** dem Ask und reale TTL; 50+50€ Paper, kein Score-only BUY.
- Kein pauschales Absenken der 5m-Volumenquote 1,2; die V3-B-Evidenz TIA/ARB zeigte zugleich keinen 15m-Reclaim und keine frische 5m Fortsetzung – ein Einzelvolumen-Floor wäre kein valider BUY.
- Keine pauschale `AND`→`OR`-Änderung direkt im BUY und kein generalisierter Anti-Chase-Off-/Market-Down-Ignore-Schalter.
- Keine stillen H3/H6-, H10/H11-BUY-Vetos, keine Echtgelderlaubnis, keine neue Strategieparallelaktivierung.
- Rückblicks-MFE ohne Zeitpfad und Fill darf nicht als wahrscheinlicher Nettogewinn verkauft werden.

## 5. Wie eine Lockerung messbar getestet werden muss

**Jeweils ein** inaktiver, versionierter `One-Change`-Entscheider mit datiertem Frozen-V2R4-Kontrollarm: konkrete neue Eligibility statt versprochenem Mehr-BUY. Prospektive `observed_at_utc / known_at_utc`-PIT-Snapshots, selbes Paar/echter neuer Entscheidungszeitpunkt, vollständig vorhandene Kraken Pair/Ticker/15m-/5m-Daten, kosten-/spread-/slippagebereinigte Bewertung, vorab identische Stop-/Stage2- und andere Risk-Guards. Zähle gesondert (1) zusätzliche frische Full-Reviews, (2) **risikogültige** neue BUY_SCOUT, (3) tatsächliche Paper Fill/Stage2/Stop- und 6h/24h-Verläufe, (4) **zusätzliche schlechte BUYs/Stops**, (5) Einzigartigkeit nach Pair/6h, Tages-/Regimediversität. Kosten-, Model-Call-, Budget-/Shadow-Limits und Release-Linie wie bestehender `research/strategy-learning-causal-gate-v1.json`.

**Reihenfolge:** Zuerst **nur P2 WAIT-FRESH-REVIEW** als INAKTIVEN Offline-Policy-Kandidaten mit gültigen und ungültigen Beispielfällen und ohne Modell/HTTP; dann P3 CONTINUITY unabhängig; dann höchstens ein getrennter neuer EXTENDED-Ansatz. Keine weitere allgemeine Ursachenanalyse vor echtem One-Change-Diff und fachlichen Negativtests. Ein neuer kostenpflichtiger oder physischer Shadow/Strategie-Paper-Rollout braucht ausdrückliches eigenständiges Freigabegate.

**Autonomie/Owner:** bestehender `PROJECT_BACKLOG.md` V3 P2/P3 mit bestehendem GitHub-Meilensteincontroller/daily 10:15 Work; neues Forschungsdokument ist kein neues System/Task-Autopilot. V2R4 bleibt bis erfolgreich kontrolliertem V3-PAPER-Release allein aktiv.

## 6. Nachtrag: P3 CONTINUITY vor einer pauschalen Soft-Veto-Lockerung neu geprüft (11.10.)

Neue READ-ONLY-Abfrage derselben zwei V2R4-Serien: **434 CONTINUITY** (426 initial WAIT, 8 initial REJECT). Bloße Freitext-Suche in `payload.decision.decision.reason_codes`: **100** Kandidaten mit irgendwo erwähntem Macro/Market/Regime/News/Major-Faktor, aber **434/434** zugleich wenigstens einem Begriff aus Struktur/Stop/Volumen/Kosten/Spread/Late/Remaining-Move/ATR/Liquidität; **0 ohne irgendeine solche Zusatz-Erwähnung**. Diese Gruppen sind *nicht disjunkt* und enthalten **positive** Begriffe wie `spread_acceptable`; deshalb KEIN Beweis, dass Soft-Faktoren nie blockieren. Sie beweisen insbesondere **nicht**, dass gerade der Makro-Veto die alleinige letzte BUY-Hürde ist.

**Strategische Konsequenz:** P3 CONTINUITY als genau eine **später separat** zu entwickelnde/inaktiv zu testende frische, verifizierte 5m/15m-Preis-/Volumen-/Trendfortsetzungs-Review-Hypothese. Nicht den allgemeinen Markt-/Regime-/News-Einfluss abschalten und nicht Soft-Vetos erfinden. Die P2-Paper-Stop-/Gebühren-Validierung aus PR #179 wiederverwenden und von einem realen prospektiven Gegenkontrollarm erst beweisen lassen, ob zusätzliche **kostenbereinigte, tatsächlich ausführbare** BUYs bei akzeptablem Fehlkaufrisiko entstehen. Sonstige Familien IGNITION/EXTENDED/REVERSAL bleiben getrennt; H3/H6 unverändert. Keine P3-Modell-Calls/Shadow/Trading-Aktivierung durch diesen Nachtrag.
