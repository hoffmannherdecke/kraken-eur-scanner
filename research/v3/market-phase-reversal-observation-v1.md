# V3 — Marktphasen-/Reversal-Beobachtung und Lernübergabe (v1)

Status: **PASSIVE OBSERVATION / RESEARCH ONLY**  
Beschluss: 2026-10-08  
Aktive Strategie-/Serienautorität: ausschließlich `project-current-state.json`  
Forschungspfad: `docs/v3-research-framework.md`, bestehendes GitHub Issue #7.

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

Bei einer ohnehin aufgrund von Kandidatenreife, Trade-Frequenz oder
Forschungs-Meilensteinen geöffneten V2R4-/V3-Analyse:
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
   in den permanenten Strategie-Linien-/Migrationspfad routen.
   Materiale Änderungen benötigen erst punktgenauen Offline-Test,
   ggf. prospektiven Shadow, Kostenanalyse, Release-Gate und Freigabe.

## Schutz-/Kostenregeln

Keine neue Work-Analyse nur weil ein Phasenereignis vorliegt.
Keine neue Paper-Serie, kein paralleler strategieändernder Shadow,
keine H1-Rückaktivierung, keine Änderung laufender Scanner-/Entry-/
Stop-/Sizing-/V2R4-/H3-Parameter. Keine Orders oder Echtgeldaktionen.
Nur wenige kompakte Ereignisse statt periodischem Rohdaten-Logging;
alle Fachdaten bleiben in ihren bisherigen begrenzt aufbewahrten
autoritativen Quellen. Nach ausreichender Evidenz auch `NO_CHANGE`
als valides Ergebnis akzeptieren.
