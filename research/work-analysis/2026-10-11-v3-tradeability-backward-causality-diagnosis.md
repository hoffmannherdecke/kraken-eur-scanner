# V2R4 → V3: rückwärts geprüfte Handelbarkeit – Diagnose nach 0 BUYs (11.10.2026)

## Auftragsgrenze und Beleglage

Nutzerfrage: Hat die Summe unserer Hürden eine faktische Handelsblockade konstruiert? Drei gedachte profitable Marktverläufe sind technisch denkbar, doch wie wahrscheinlich und wirtschaftlich sinnvoll wäre ein echter kompletter Trade? **Nur Lesen/Analyse.** Keine Änderung an Scanner, V2R4-Paper, Modellprompt, P3-P4-Hard-Gates, V3-Runtime, Mini-PC, Orders, Modellbudget oder automatischen Work-Läufen.

**Quellen:** direkt lesendes Supabase SQL am 11.10.2026 (Projekt `nlgzjmqgwueojlyqmoru`, öffentliche `paper_candidate_outcomes` und `paper_series`; disjunkte V2R4-Serien `PAPER-V2R4-20261007T184255Z` und `PAPER-V2R4-20261009T110135Z`; zweite ist technische Rotation **gleicher** Strategie); vorhandene GitHub-Modell-/Review-Validatoren; die gehashte, vom Nutzer hochgeladene echte `v3-p3-ab-five-http10-6h-20261011.json` (PR #188). **Analytischer Snapshot N=2.102 V2R4-Erstfälle:** laufende Produktion, daher kein dauerhaft statischer Gesamtzähler. Maturitätsanalysen nur auf **921 tatsächlich vollständigen 24h-Followups**; diese sind aus ursprünglichem Kandidaten-Ask, **nicht** aus einem späteren V3-Kaufask. Kohorten enthalten mehrfach ähnliche Coin-/Zeitfenster, sind nicht automatisch unabhängig. Supabase und GitHub sind hier Befundquellen, nicht Buy-Freigabe.

## Befund 1: realer Funnel blockiert BUY, Ursache nicht nur Vorfilter

- **2.102 Erstentscheidungen, 0 BUY**, **1.321 initial WAIT**, **781 initial REJECT**. Das oberste `paper_candidate_outcomes.decision` ist oftmals die **finale** Entscheidung und unterschlägt die ursprünglichen WAITs: immer `payload.decision.decision.decision` lesen.
- Die WAIT-Nachbehandlung zeigt aktuell **1.131 TTL-Expiries** und **164 echte `V2R4_LOCAL_TRIGGER_RECHECK_V1`**; davon im Modell-Nachentscheid **0 BUY**, 161 REJECT und 3 WAIT. Diese Zahlen sind nicht als unabhängige zusätzliche Kandidaten zu addieren.
- **153/164 = 93,3 % der echten Rechecks** erhielten beim Nachentscheid `setup_lane=EXTENDED` (Vorläufer u.a. CONTINUITY und IGNITION). Besonders aufschlussreich sind u.a. 56 initiale CONTINUITY → beim Trigger EXTENDED-REJECT und ein weiterer CONTINUITY → EXTENDED-WAIT. Der Trigger wird dadurch potenziell zum **Zeitpunkt, an dem die erwartete Bestätigung erstmals als verspäteter Einstieg bewertet wird**. Dies ist eine plausibel starke, aber noch nicht kausal experimentell bestätigte **Bestätigungsfalle**: zunächst WAIT für stärkere Bewegung, danach EXTENDED/LATE_CHASE/NET_EDGE.
- Recheck-Reason-Codes umfassen häufig `LATE_CHASE` (64), `LATE_CHASE_RISK` (25), `INSUFFICIENT_REMAINING_MOVE_EVIDENCE` (24) sowie mehrfach fehlende Strukturstopps und Kostenveto. Reason-Codes sind vom Modell erzeugt, mit Synonymen/Überlappung, **keine unabhängigen harten Gate-Attributionen**.

## Befund 2: historische Stop-/OHLC-Information ist im V2R4-Erstmodell nicht entscheidungsreif

- In der **aktuellen Menge von 2.102** V2R4-`payload.decision.decision_context` ist der Schlüssel `coin_entry_evidence` **0-mal vorhanden** (obwohl `kraken_execution_ticker` durchgängig vorhanden ist), und `payload.decision.decision.stop_eur` **0-mal nicht null**.
- Das tatsächlich aktive V2R4-Evaluatorprompt fordert **strukturelle bzw. ATR-basierte Stops**, genügend Restpotenzial, Fees und einen separaten Stage-2-Trigger. Ohne ausdrücklich modellbereite aktuelle Coin-1m/5m/15m-OHLC/ATR-Referenzen droht eine selbstverstärkende Ablehnung: das System verlangt belastbare Stop-Evidenz, stellt sie im klassischen Consumer nicht strukturiert bereit.
- Aus Reason-Code-Musterklassifikation (**heuristische Regex, keine kausale Entscheidungszuordnung**) werden allein unter initialen EXTENDED 793/1.119 und unter CONTINUITY 294/493 mit negativen Formulierungen zu STOP/ATR/Kerzen markiert. Ebenso zahlreiche Kosten-/Restpotenzial-Labels. Diese Labels können co-auftreten, sind nicht disjunkt und stellen **keine** definitive Einzelblockerzählung dar.
- **Wichtige Gegenprobe:** In PR #186 erreichten fünf reale Kraken-Coin-PITs einen echten V3-Modell-WAIT samt P4-`FULL_WAIT_VALIDATED_OFFLINE` (EIGEN, XLM, RENDER, CC, MON), obwohl alle acht P3-Standard-Eignungsprüfungen erfolgreich waren. Also: Fehlende Coin-Evidenz ist ein **sehr starker V2R4-Engpass**, aber **nicht die alleinige Ursache** der fünf V3-WAITs.

## Befund 3: die bisher real abgelehnten fünf V3-Kandidaten waren binnen einer Stunde keine offensichtlichen Gebührengewinner

Nutzer-Originalreport: fünf V3-Fälle, alles `STANDARD`, null echte Experimental-Inkremente; `WAIT` an tatsächlichem Modell, null BUY. Zusätzliche direkte read-only Supabase-Abfrage derselben `candidate_id` zeigt für den **ursprünglichen Scanner-Ask** in den ersten **60 Minuten ab Kandidat** folgende *maximalen* zwischenzeitlichen Bruttobewegungen:

| Coin | 60m-MFE vom initialen Scanner-Kandidaten-Ask | Vollständig? |
| --- | ---: | --- |
| EIGEN/EUR | +0,263 % | Ja |
| XLM/EUR | +0,345 % | Ja |
| RENDER/EUR | +0,901 % | Ja |
| CC/EUR | +0,881 % | Ja |
| MON/EUR | noch keine 60m-Pfadbestätigung | Nein |

Bereits **0,60 % Taker je Seite = 1,20 % round-trip**, dazu realer Spread und Slippage. Alle vier vollständigen 60m-MFE lagen **unter reinen Gebühren**. Dies stützt den vorsichtigen WAIT *für ein hypothetisches kurzfristiges Trading ab ursprünglichem Scanner-Kurs*, beweist **nicht** die individuelle Richtigkeit des späteren V3-P4-WAIT (anderer Einstieg und Entscheidungszeitpunkt, kein modellzeitgleicher ASK-Pfad, keine ex ante Stop-/Stage2-Simulation). Kein Recht, aus fehlendem 60m-Potenzial auf 24h-Nichtprofitabilität zu schließen.

## Befund 4: Märkte bieten ex post Chancen, aber nicht notwendigerweise realisierbare kostengedeckte Trades

Direct SQL unter **921 vollständigen 24h-Followups** (nicht alle 2.102 bereits 24h-reif; nicht nach Kandidaten/Paaren unabhängig dedupliziert):

| Ursprünglicher V2R4-Typ | Reif N | 24h MFE mindestens +5 % | 24h MAE mindestens -5 % | Median 24h Schlussbewegung | Median 60m MFE |
| --- | ---: | ---: | ---: | ---: | ---: |
| CONTINUITY | 222 | 93 | 71 | **+0,202 %** | **+0,738 %** |
| EXTENDED | 540 | 229 | 286 | **-1,882 %** | **+0,804 %** |
| IGNITION | 39 | 20 | 21 | -0,796 % | +0,969 % |
| REVERSAL | 55 | 27 | 22 | +1,042 % | +0,823 % |
| NONE | 65 | 30 | 36 | -2,628 % | +0,667 % |

**Interpretation:** CONTINUITY ist aus dieser Stichprobe der begründbare *erste Forschungsprioritätskandidat* (weniger schwere Downside-Fälle als EXTENDED, vergleichsweise bessere 24h-Schlussbewegungen). Aber selbst der CONTINUITY-Median von +0,202 % vom ursprünglichen Ask liegt **unter** Gebühren. Das 60m-MFE aller fünf Gruppen im Median von +0,667…0,969 % liegt ebenso unter 1,20 % Gebühren. **Ein Brutto-MFE +5 % kann zeitlich erst nach -5 % Drawdown auftreten, an STOP/TTL/Stage2 scheitern und ex post nicht handelbar sein.** Positive MFE-Spitzen sind keine Nachweise für tatsächliche Netto-P&L.

**Gebührenarithmetik:** Selbst im idealisierten 0,1%-Spread und 0,08%-Slippage je Seite sind ~1,46 % Gesamtreibung vor einer positiven Netto-Erwartung zu berücksichtigen. Die derzeitige V3-P4-BUY-Kontrolle fordert formell einen positiven Netto-Restweg und positiven Kosten/Risiko-Quotienten, **aber kein kalibriertes Mindest-Risikoverhältnis >1**; mehr zulässige BUYs wären deshalb kein ausreichendes Qualitätsziel.

## Drei rückwärts plausible Handelssituationen – und die echte Hürde

1. **P3 frühe CONTINUITY:** Ein erster starker, frischer 15m-Schluss oberhalb der Vorbasis mit 5m-Verhältnis ≥1,2, engen EUR-Bid/Ask, kleiner ATR-Ausdehnung und Stop unter Ask ist technisch zulässig. Der Modellentwurf muss *am selben PIT-Clock* realistische verbleibende Bewegung **nach** Gebühren und eine Stage2-Bestätigung oberhalb Ask finden. **Engpass:** selbst nach 8/8 Hard-Gates kamen in 5 realen Fällen nur WAIT wegen 1m/15m-Dynamik, Momentum, Kosten und Chase; positive Struktur ist **nur Review-Berechtigung**, nicht automatisch erwartbarer Gewinn.
2. **P1 echte zweite Basis:** Nach anfänglichem Schub entsteht **neue** 1–3h-Basis mit 4–12 vollständig geschlossenen 15m-Kerzen, neuem frischem Reclaim bei Volumen ≥1,2 und zulässiger ATR-Ausdehnung/Stopreferenz; vorangegangene Rally wird nicht blind als neuer Impuls verkauft. **Engpass:** Basis plus Bestätigung können den Entry teuer machen; P1-Paper und tatsächliche modell-/netto-konforme BUYs sind weiterhin nicht physisch bewiesen.
3. **P2 nach abgelaufenem WAIT:** Ein altes WAIT endet wirklich; *erst ein neu bekannter unabhängiger* 15m-Schluss nach Ablauf bei Volumen ≥1,2 darf einen neuen Review eröffnen, ohne alte TTL zu verlängern. **Engpass:** V2R4 erlebte massenhaft Expiries und Rechecks, aber im Recheck klassifizierte das Modell 93 % als EXTENDED. Diese Lane muss nach legitimer neuer Struktur zeitlich differenziert werden, darf aber Anti-Chase oder Kaufkosten nicht überstimmen.

**Ergebnis:** Ein vollständiger Trade ist technisch möglich (P3/P2/P1/P4-Offline-Positivfixture), aber die gegenwärtige **operative Abfolge** kann Chancen faktisch wegfiltern. Es liegt **keine** empirische Evidenz vor, dass ein beliebiger gelockerter Volumen-, Chase- oder Stop-Gate netto profitable Deals erzeugt.

## Schlussfolgerung und geordnete Handlung (kein unautorisierter Trade/Shadow)

**Höchste Sicherheit für Diagnose:** Die V2R4-Conversion ist tatsächlich nahe null (2.102 → 0 BUY), und der aktive Erstmodellpfad hat keine strukturierte Coin-1m/5m/15m-ATR-Evidenz. **Höchste plausible Strategieblockade:** Anforderung *Bestätigung vor Einstieg* und darauffolgende *Ablehnung wegen zu später Bewegung*, insbesondere die 153/164 EXTENDED-Reklassifikationen. **Bestätigter Gegeneinwand:** Vier der ersten fünf echten V3-WAITs hatten während der anschließenden ersten 60 Minuten aus Scannerpreis nicht einmal das Gebührenminimum als maximale Bruttobewegung.

**Empfohlene Reihenfolge für bereits bestehende V3-P0/P3/P4/P8-Owner und 10:15-Work**:

1. **P0 Priorität: echten Coin-PIT-/ATR-/Stop-Beweis am tatsächlichen Consumer** liefern: gleiche zur Modellentscheidung zeitlich bekannte geschlossene 1m/5m/15m-EUR-Bars, ATR, aktuelle Bid/Ask, Spot-EUR Paarminimum, Quellenfrische, Ausfallrisiken; nichts antizipieren. Schon bestehende P0- und PR #185-Schutzguards weiterverwenden; keine doppelte Input-Pipeline erfinden.
2. **P3/P4 kausale Ablehnungsattribution statt globaler Lockerung:** Mit PR #189 fertig vorbereiteter **inaktiver Offline-Telemetrie** künftig *pro Kandidat* acht Hard-Gates, failed check, WAIT vs REJECT vs BUY, konkrete Modell-/Cost-/Stop-Lücke, Model-Zeit/P4-Zeit, Trigger und Restpotenzial am selben Clock aufzeichnen; spezielle Variable „original CONTINUITY → später EXTENDED; echter neues 15m-Close?; bereits aufgelaufene Preisstrecke/ATR“; optionaler Kontext ist *kein* verstecktes technisches BUY-Veto.
3. **Ein klarer experimenteller Vergleich statt pauschalem Risikoabbau**: A unveränderte Standard-Regeln mit vollständigen PIT-Daten, B exakt eine frühere, dennoch frische **Review-Zeitpunkt-/Lane-Behandlung** (ohne Anti-Chase/Cost/Stop-Lockerung), C separat später das bestehende isolierte P3-Volumenexperiment 1,0–<1,2 als eigene Erklärung. Keine gleichzeitige Mischung, kein vorzeitiges P1/P2/H3/H6-Promoting. Experiment muss denselben tatsächlich bekannten Markt-/Modell-Clock, mehr als 1h-Followup, 6h/24h-Simulation, conservative Stop-vor-Ziel-/Stage2-Ordering, ggf. 72h Strategiezeit-Horizont nutzen.
4. **P4 Wirtschaftlichkeit bewahren und aufwerten**: 0,60 % Fee pro Seite, Spread/Slippage, gültiger EUR Mindestauftrag, struktureller Stop und tatsächlicher Stage2-Trigger bleiben obligatorisch. Vor Paper-Freigabe nicht nur `net_edge_pct>0` und `risk_reward_after_costs>0`, sondern empirisch tragfähige **positive Nettoerwartung bei realistischer Verlustquote** nachweisen; das ist Forschungs-/Modellvergleich, **noch keine** neue Live-Schwelle. Maker-Kostenreduktion höchstens später als selbständiger Execution-Eingriff mit Fill-/Missed-Fill-Risiko prüfen, niemals stillschweigend in Paper annehmen.
5. **Ausführungsgates**: Einmalige PR #186 Freigabe ist **verbraucht**, PR #189 liefert bisher ausschließlich nicht integrierte Offline-Telemetrie. Keine neue Live-Strategie, V3-Paper, API-/Shadow-Runde, Mini-PC-Lauf, H-Baustein oder Echtgeld-Order ohne separaten ausdrücklichen Scope-/Kosten-/Release-Gate. Kein neuer Work-Lauf oder Scheduler. **V2R4 bleibt nur Paper.** Wenn neuer Umfang genehmigt wird, erst den zukünftigen Instrumentierungs-Consumer sicher nachweisen, danach begrenzten echten P0→P3/P4 Same-Clock-Test und zeitlich gereifte Netto-Outcomes; mindestens eine echte positive, validierte Buy-Path-Durchleitung ist notwendig, bevor wirtschaftliche Aussage möglich wird.

**Priorisiertes Fazit:** Nicht „Sicherheit abschalten“, sondern **fehlende Entscheidungsgrundlage beseitigen + späten Modell-EXTENDED-Kippmoment kausal messen + nach realen Kosten und Stop-Pfaden nachweisen, wo tatsächlich noch Erwartungswert bleibt**. Erst wenn eine einzige gezielte Abweichung verlässlich mehr qualifizierte positive Netto-Trade-Pfade liefert, darf sie eine eigene Paper-Release-Empfehlung bekommen.
