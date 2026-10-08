# V3 — Marktphasen-/Reversal-Beobachtung und Lernübergabe (v1)

Status: **PERMANENT, GENERATIONSÜBERGREIFENDE PASSIVE OBSERVATION / RESEARCH ONLY**  
Beschluss: 2026-10-08  
Aktive Strategie-/Serienautorität: ausschließlich `project-current-state.json`  
Forschungspfad: `docs/v3-research-framework.md`, bestehendes GitHub Issue #7.

## Dauerhafte Gültigkeit über alle Strategieversionen und Marktzyklen

Diese Fähigkeit ist **dauerhaft** und nicht auf den Abverkauf vom 2026-10-08,
V2R4, V3 oder einen bestimmten Marktzyklus begrenzt. Sie gilt für alle
zukünftigen Paper-, Shadow- und — nach separater Handelsfreigabe —
Echtgeld-Strategiegenerationen (V4, V5, ...), solange sie nicht durch einen
nachweislich validierten Nachfolger ausdrücklich ersetzt wird.

Der Beobachter sucht in **jeder neuen Marktphase** nach wiederkehrenden
wesentlichen Übergängen (erneutes Risk-off, Stabilisierung, bestätigte
Erholung), nicht nur nach einem einmaligen Oktober-Reversal. Ohne belegten
Phasenwechsel keine Meldung und kein Speicherereignis. Das bestehende
Zustandsvokabular bleibt unverändert; weitere Regimeklassen benötigen einen
separat versionierten, geprüften Vertrag. Die ursprüngliche Marktlage ist
lediglich der Anlass, nicht die zeitliche Begrenzung.

Jede Nachfolgerstrategie muss die *Beobachtungs- und Auswertungsfähigkeit*
explizit im jeweiligen predecessor→successor-Migrationsledger disponieren.
Die Vererbung dieses **Forschungspfads** bedeutet **nicht**, dass sein
prognostischer Nutzen oder ein darauf basierender Entry-/Stop-/Sizing-Filter
als validiert gilt. Forschungsergebnisse können auch keinen Mehrwert
zeigen; dann `NO_ACTION_WARRANTED` statt einer erzwungenen Strategieänderung.

## Initialer Referenzpunkt: Markt-Abverkauf am 2026-10-08

Der **erste protokollierte Forschungsanker** steht im bestehenden V3-Research-
Issue #7: `MARKET_REGIME_SEED_V1` vom 2026-10-08,
https://github.com/hoffmannherdecke/kraken-eur-scanner/issues/7#issuecomment-6066250115.
Er konserviert die vorliegenden *öffentlichen CoinGecko-Snapshotdaten*
(Gesamtmarkt 24h -6,31%, BTC ca. -3,32%; mehrere Altcoins deutlich schwächer),
mit beobachteten USD-Kursen, Quelle und echtem `known_at`. Er ist der Beginn
der **Erholungshistorie**, nicht bloß eine nachträgliche Gesprächsnotiz.

WICHTIGE UNTERSCHEIDUNG: Das ist ein `MARKET_REGIME_SEED_V1`
(*CONTEXT_ONLY / NOT_KRAKEN_REGIME_LABEL*), **kein** synthetisch
nachberechnetes `MARKET_REGIME_EPISODE_V1`: keine geprüften
Kraken-EUR-Closed-Bars, kein exakter Sell-off-Beginn, keine Intraday-Basis
oder voll belegte Marktphasen-Übergangszeit. Niemals auf Datum/Zeiten
vor dem tatsächlichen `known_at` zurückdatieren. USD-Preise nicht als
Kraken-EUR-Entry-Kurse verwenden; ein 24h-Verlust beweist weder ein
exaktes lokales Tief noch wann die Trendwende einsetzt.

Beim **nächsten regulären** Watcher-Lauf sind der Seed und vorhandene
`MARKET_REGIME_EPISODE_V1`-Marker zu lesen. Die **erste vollständige,
prospektiv geprüfte Kraken-Spot-EUR-Phase** wird mit dem echten neuen
`observed_at_utc` separat als INITIAL_BASELINE protokolliert, auch wenn
sie ebenfalls `RISK_OFF` lautet: Der Seed zählt nicht als bereits
validierte Kraken-Phase. Danach nur echte bestätigte Phasenwechsel,
ohne gleichförmige 2h-Snapshots zu speichern. Ein etwaiger Abstand
Seed→erstes Kraken-Episode-Label bleibt als Datenlücke kenntlich.

In späteren **ohnehin zulässigen** Analysen dürfen wir den Seed
zur Einordnung eines bekannten breiten Abverkaufs und zum Vergleich
späterer Erholung nutzen. Die punktgenaue Zuordnung zu Paper-/Live-
Einzelentscheidungen ist aber erst ab **damals tatsächlich bekannten,
separat bestätigten** Kraken-Episoden zulässig. Kein im Nachhinein
rekonstruiertes Episode-Label, keine Strategie-/Orderwirkung; bei
unzureichendem E2E-Nachweis `NOT_EVALUABLE`.

## Zweck und Abgrenzung

Nach einem breiten Altcoin-Abverkauf soll das Projekt zwischen anhaltendem
Risk-off, beginnender Stabilisierung und belastbarer Erholung unterscheiden
können — **ohne** einen zweiten Scanner, eine zweite Strategie, zusätzliche
Work-Läufe oder laufende V2R4-/H3-Regeln zu verändern. Beobachtung ist kein
Kaufsignal. Nur eine spätere, bereits gegatete Auswertung kann einen
möglichen Lerneffekt als Hypothese behandeln. Das ist weder kontinuierliches
Selbsttuning noch bereits nachgewiesene Verbesserung.

## Bestehende Quellen wiederverwenden

- Primäre Preise/Zeiten: bestehende öffentliche Kraken-Spot-EUR-Daten mit
  vollständig geschlossenen 15m-Bars, niemals USD-Kurse als EUR ausgeben.
- BTC/ETH/SOL plus kleiner, vorab festgelegter *Referenzkorb* aus liquiden
  EUR-Paaren (z. B. AVAX, ENA, FET, AAVE, KSM, TRAC, AERO, ZRO).
  Ein nicht existentes, gesperrtes oder fehlendes Paar ist `missing`, keine Nullrendite.
- Bereits vorhandene kandidatenspezifische Regime-/Breitenkontexte und
  V2R4-Follow-ups sind die späteren Analysequellen. H1-Breitenforschung
  ist als eigenständige Entscheidungsautorität **abgelehnt**: weder H1
  reaktivieren noch fehlende globale Marktbreite aus kleinem Korb behaupten.
- Der zusätzliche Referenzkorb ist nur **Proxy**; Quelle, Stichprobenumfang,
  Fehlwerte, Kursbar-Endzeit und Abfragezeit werden dokumentiert.
  Keine neue Datenquelle/Secrets/Orderrechte; kein Raw-OHLC-Archiv.

## Beobachtung / kompakter Übergabevertrag

Vorhandene sparsame Marktphasen-Beobachtung (ca. alle 2h, außerhalb Work)
klassifiziert nur bei genügend Daten:
`RISK_OFF`, `STABILIZING`, `RECOVERY_CONFIRMED` oder `UNKNOWN`.
Mindestens zwei getrennte Beobachtungsmerkmale müssen sich über mindestens
zwei Stunden **abgeschlossener** Kurshistorie bestätigen, z. B.
BTC-Struktur und relative Erholung eines ausreichenden Anteils des
Referenzkorbs; optional belegter Volumen-/Derivatedruck.
Ein kurzes technisches Bounce/Einzelcoin-Anstieg ist keine Bestätigung.
Es gibt **keinen** starren BTC-Preis oder automatisch wirksamen Score.

Nur eine **neue, materiell verifizierte Marktphasenänderung** (oder einmalige
Initial-Baseline) wird als einzelner komprimierter Kommentar im
**bestehenden** V3 Research Issue #7 hinterlegt. Das Marker-Präfix lautet
`MARKET_REGIME_EPISODE_V1`. Mindestinhalt:
`observed_at_utc`, `last_closed_bar_end_utc`,
`source=kraken_spot_public_eur`, `state`, `prior_state`,
`btc_structure`, `reference_pairs_valid/total`, `breadth_proxy`,
`confirmation_window`, `supporting_features`, `unknowns` und
`authority=RESEARCH_ONLY_NO_ORDERS`.
Gleiche unveränderte Lage nicht wiederholt posten; bei unzureichender
Datenlage **keine** neue Bestätigung und **kein** Ersatz durch Schätzwerte.
Der Kommentar ist ein knappes Forschungsevent, **keine**
Sekundärdatenbank, kein unveränderliches Handelslabel.
Alte Ereignisse niemals nachträglich „schöner“ umklassifizieren.

Keine Nutzer-Pushs, keine GitHub-Workflow-/Scanner-Änderungen,
keine Datei-/Supabase-Schreibvorgänge pro Scan. Ein ausgefallener Beobachter
darf V2R4/Scanner/H3 weder blockieren noch beeinflussen.
Falls zukünftige technische Persistenz/Leistung nachzuweisen ist,
bleibt ein begrenzter Lesetest vor weiterer Freigabe notwendig.

## Verbindung zum realen Lernen (nur am vorhandenen Analyse-Gate)

Bei einer ohnehin aufgrund von Kandidatenreife, Trade-Frequenz, Live-Review oder
Forschungs-Meilensteinen geöffneten Analyse von V2R4, V3 oder jeder späteren Paper-,
Shadow- und Echtgeld-/Nachfolgerstrategie:
1. Markierte Events aus Issue #7 dedupliziert lesen. Nur Ereignisse
   berücksichtigen, die **vor** dem jeweiligen Kandidaten/Entry beobachtet
   und nachweislich bekannt waren (kein rückwirkendes Phasenlabel).
2. Bei ausreichender Kohorte Outcomes nach damaligem Regime segmentieren:
   BUY/WAIT/REJECT, Trade-Quote, verpasste 6h/24h-Bewegungen, MFE/MAE,
   Zeit bis zum Reclaim, Fehltrades, Kosten, Spread/Slippage und
   Datenvollständigkeit. Gegen die *bereits bestehende* Regimeinformation
   abgleichen, nicht alles doppelt messen.
3. Alternative Erklärung (globale Korrelation, volatiler Bounce, Coin-
   Selektionsbias, Lücken, Zeitverzug) und tatsächlichen
   Inkrementalnutzen offen ausweisen. Nur mit vorher festgelegten,
   testbaren Kriterien eine V3-Research-Hypothese bzw. inaktiven
   Nachfolger-Vorschlag erzeugen; sonst `NO_ACTION_WARRANTED`.
4. Unter `docs/test-strategy-runbook.md` §12 weiterverarbeiten und
   in den permanenten Strategie-Linien-/Migrationspfad routen,
   einschließlich echter Live-Fills, Kosten, Risikoereignisse und verworfener
   Chancen, sofern die Echtgeldphase überhaupt separat aktiviert wurde.
   Materiale Änderungen benötigen erst punktgenauen Offline-Test,
   ggf. prospektiven Shadow, Kostenanalyse, Release-Gate und Freigabe.

## Schutz-/Kostenregeln

Keine neue Work-Analyse nur weil ein Phasenereignis vorliegt. Langfristig
kein eigener Worker, zusätzlicher Scanner oder periodischer Vollmarkt-Archivjob.
Ein bestehender Beobachtungstask darf ressourcenschonend weiterlaufen; sein
Ausfall muss alle produktiven Handels-/Paper-/Shadow-Abläufe unberührt lassen.
Keine neue Paper-Serie, kein paralleler strategieändernder Shadow,
keine H1-Rückaktivierung, keine Änderung laufender Scanner-/Entry-/
Stop-/Sizing-/V2R4-/H3-Parameter. Keine Orders oder Echtgeldaktionen.
Nur wenige kompakte Ereignisse statt periodischem Rohdaten-Logging;
alle Fachdaten bleiben in ihren bisherigen begrenzt aufbewahrten
autoritativen Quellen. Nach ausreichender Evidenz auch `NO_CHANGE`
als valides Ergebnis akzeptieren.
