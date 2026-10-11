# V3: passive Kontextintegration – Smart Money, Polymarket, Quellen, Regime (11.10.2026)

**Status:** INAKTIVE, DIREKT NUTZBARE RESEARCH-VORBEREITUNG. Kein automatischer Strategiewechsel, Shadow-/Paper-Start, Handel oder neuer Scheduler.

**Bereits vorhandene fachliche Owner behalten Vorrang:** `research/v3/v3-consolidated-strategy-integration-plan-20261011.json#optional_context_fusion` ist der *eine* V3-Ablauf-/Rollenindex unter PR #161. Aktuelle Stream-Evidenz steht allein in `research/monitoring-evidence-routing-v1.json`, Quellenadmission allein in `research/source-registry.json` und `research/market-source-candidates-v1.json`, Status/Next Gate der Forschungskomponenten allein in `research/v3-migration-ledger.json`. Historische Arbeit im bestehenden V3-Forschungsrahmen. Das neue `tools/v3_context_fusion_preflight.py` ist ein kleiner **read-only** Validator/Provenienzfilter für diese bereits existierenden Daten. Es fügt keine News-, Preis- oder Wallet-Datenquelle hinzu.

## Strategieidee – warum nicht alle Quellen zu BUY-Gates werden

Das erste wirtschaftliche Problem ist die nachweislich unproduktive V2R4-Einstiegslogik. V3 muss deshalb zuerst P0-Datenqualität und P1 einen neuen vollständigen, im One-change-Vergleich getesteten Second-Leg-Einstieg lösen. Weitere Informationen dürfen nicht als sieben neue unabhängige Bestätigungspflichten **jeden** Kandidaten zu WAIT/REJECT machen. Kostenmodelle, Stop, Stage2 und echte Kraken-Spot-EUR-Handelbarkeit bleiben harte *bestehende* Schutzvoraussetzungen. Das Vorhandensein eines Signals ist weder Kaufempfehlung noch Beweis von Mehrertrag. Fehlende optionale Quellen bleiben neutral.

## Getrennte, vorhandene Verantwortlichkeiten

| V3-Rolle | Tatsächlicher Stand aus vorhandener Evidenz | Jetzt sinnvoll | Konkretes nächstes Fachgate |
|---|---|---|---|
| **P0/P1 Core Entry** | V3-B-Eligibility als inaktiver Code, noch kein neuer vollständiger wirtschaftlich überprüfter BUY | Zuerst echte Coin-PIT-Inputs und Second-Leg-Vollreview bei gleichem Kandidaten/Uhr/Ask/Stop/Stage2/Fees | Bestehender PR161 P0/P1-Owner, eigener ONE-CHANGE-Test |
| **H10 Smart Money** | Öffentliche Hyperliquid-Daten, eingefrorene Wallet-Kohorte, laufende passive Erfassung, erster Review; Signalvorlauf aufgrund 30min-Takt zu grob für Hochfrequenz-Entry; kein profitabler Kraken-Join belegt | Bereits vorhandene Capture **nutzen**, nicht verdoppeln; streng vorab bekannte AssetPairs/Erstbeobachtungszeit und Falschpositiv-Kontrollen | `research/v3/h10-kraken-outcome-context-join-contract-v1.json`: 50 post-freeze gültige Events (40 Primary/10 Control) an 3 UTC-Tagen mit 24h-Outcomes; erst dann separates H10-Wirkungsgate |
| **H11 Polymarket** | Gamma/CLOB read-only und zwei Zeitproben erfolgreich; Buchdaten änderten sich, Midpoint/Spread damals nicht; keine Marktpreisprognose | Als **Ereignis-/Unsicherheitsquelle** in V3-Forschung sichtbar halten; keine direkte „Crypto goes up/down“-Ableitung | Neues vorab festgelegtes Event-Relevanz-/Zeitfenster-Sampling und danach PIT-Outcome-Assoziation; bestehendes H11-Fachgate |
| **P5 Quellenmanagement** | Vorhandener 2h-Forschungsauftrag plus Monday-Steward-Fenster; ein vollständig unbeaufsichtigter Source-Discovery→Bewertung→PR→Quittung-Zyklus nicht nachgewiesen | Bisherigen Arbeitsauftrag **weiterverwenden**; neue bisher unbekannte Quellen erlauben, unnütze/überlappende Quellen quarantänisieren, Verifikation per Primärquelle, keine Runtime-Quellen ersetzen | Bestehendes `source_quality`-E2E, 5 unabhängige relevante Ereignisse über mindestens 2 Zeitfenster vor belastbarem Score, reversible Source-Entscheidung |
| **P6 Marktphasen** | Passive BTC/ETH/Kraken-EUR-Phasenbeobachtung mit erster GitHub-Evidenz | Prospektive zeitstempelte Risikophase getrennt nach Markt-/Coin-Cluster mit späteren mature 6h/24h-Outcomes verbinden | Nachweis eines *zusätzlichen* Netto-Nutzens über bestehende BTC/ETH/Breadth-Baseline, sonst NO_ACTION |
| **H2 Derivate** | Öffentliche Kraken-Futures/Binance-Vorprüfungen; Binance Zusatzquelle, nicht Kraken-Preisautorität | Funding/OI als passive Kontextspur; Liquidationen/Korrelation nicht als neue autonome Vetos | Eigenes PIT-associiertes H2-One-change-Fachgate nach Vorprüfung |
| **H5 Makro/News** | FOMC-Zeiten/Quellen als Vorprüfung; Headlines/Veröffentlichungen nicht vollautomatisch E2E | Amtliche Ereignisuhr als Zeitkontext, Presse nur Lead mit Primärprüfung | Eigenes Ereignis-/False-Alert-Gate, keine doppelte News-Veto-Schicht |
| **H8 On-Chain** | Zwei known-at Erhebungen und erste bounded Quelle; heterogene Coverage, SOL fehlte | Langsame Nutzungsindikatoren nicht mit Wallet-Trades (H10) verwechseln | Zusätzliche echte PIT-Zyklen mit Vergleich, nicht historisch rückfüllen |
| **H1/H3/H6/H7/H9** | H1 standalone verworfen, H3-001 archiviert/deferred, H6 nicht aktiv, H7/H9 später | Nichts automatisch einschalten; H9 bleibt eigener Execution-/Kostenpfad und H6 darf Coin-Volume nicht duplizieren | H3 separate Wiederfreigabe; H6 nach vorgeschriebenem Gate; H7/H9 bei reifen Outcomes |

## Praktischer Datenvertrag: on-demand, keine Zusatzläufe

`python tools/v3_context_fusion_preflight.py` prüft, ob alle neun bestehenden Zusatzkontext-Routen auf einen echten fachlichen Owner und den bestehenden Streamvertrag zeigen und H1/H3/H6/Real-Money-Sperren gelten. Es legt *keine* neue Datenbank oder Preiszeitreihe an.

Optionales nur lokal erzeugtes, prospektives Eingabeformat für einen ohnehin fälligen V3-Research-Review:

```json
{
  "kind": "V3_OPTIONAL_CONTEXT_PROBE_V1",
  "pair": "XBT/EUR",
  "decision_at_utc": "2026-10-11T10:30:00Z",
  "evidence_refs": [
    {
      "stream_id": "smartmoney_h10",
      "pair": "XBT/EUR",
      "source_event_at_utc": "2026-10-11T10:02:00Z",
      "first_seen_at_utc": "2026-10-11T10:15:00Z",
      "retrieved_at_utc": "2026-10-11T10:15:01Z",
      "known_at_utc": "2026-10-11T10:15:01Z",
      "kraken_pit_mapping_verified": true,
      "evidence_ref": "EXAMPLE_NOT_A_REAL_H10_CAPTURE_ROW"
    }
  ]
}
```

Dieses Beispiel ist **synthetisch** und darf nie als echten Trader-Event interpretiert werden. Wenn eine der Zeitangaben fehlt, `known_at` vor tatsächlicher Beobachtung oder nach der Strategieentscheidung liegt, oder die damalige Kraken-EUR-Zuordnung nicht gegeben ist, lautet die Zuordnung `NOT_EVALUABLE` bzw. `NOT_ASSOCIABLE` statt positivem Signal. Doppelte Evidence-IDs werden erkannt. Eventmärkte erfordern einen **vor der Kursantwort festgelegten** Bezug zu einem Kraken-Paar. Quellenbewertung ist **überhaupt keine Coin-Eigenschaft**. Auch `PIT_TIME_ADMISSIBLE_RESEARCH_ONLY` beweist NICHT, dass die referenzierte externe Zeile existiert, dass H10-Signal rechtzeitig genug für echten Entry war oder dass ein Trade profitabel wäre: solche Fakten benötigen separate Originaldaten und spätere risk-/fee-adjustierte Rückschau ohne Look-ahead.

**Die engste nachfolgende Nutzung:** vorhandener H10-Hyperliquid-Collector, bestehendes Marktphasen-/Quellenradar und fachliche H11-Precheck-Captures können diese Struktur bei ohnehin fälligen V3-Reviews wiederverwenden. Keine erneuten Poller/Work-Jobs, kein automatischer Import beliebiger API-Daten in den laufenden Paper-Evaluator. Vor der tatsächlichen V3-Strategieintegration mindestens eigener PIT-Quellen-Smoke mit belegtem Input→Review-Entscheid→fachlichem ACK.

## Reihenfolge ohne künstliche Fristen

1. **Parallel ab sofort, ohne Runtimeänderung:** bestehende H10-Kohorte, Marktphasenbeobachtung und 2h-Steward *passiv* fortführen; Quellenqualität mit nachprüfbaren Entscheidungen und reversibler Research-only-Aufnahme steuern.
2. **Nach tatsächlicher Reife:** H10-Join mit zeitgerechter Kraken-EUR-Preis-/Spread-/Kosten-/False-Positive-Kontrolle; H11 zunächst Zeitfenster-/Relevanzvertrag (fünf zufällige Gamma-Märkte taugen nicht für einen Krypto-Richtungstrade). H2/H5/H8 nur separat, wenn ein inkrementeller Erkenntnishebel erkennbar ist.
3. **Core V3-B zuerst wirtschaftlich prüfen:** eine echte, risiko-/kostenbereinigte neue Entry-Entscheidungslogik statt Quellen-Sammlung. Danach höchstens **eine** zusätzliche H-Komponente per One-change prospektiv auf identischem Kandidaten/Zeituhr/V2R4-Baseline testen.
4. **Integration nur selektiv:** Positive Quelle nicht mit positiver Tradergebnis-Wirkung verwechseln, Negativkontrollen und Fehltrades einbeziehen, reife 6h/24h-Follow-ups verlangen. Kein fester Wartezeitraum bei ausreichender Evidenz; fehlende Evidenz führt zu begründetem Aufschub, nicht zu Fake-PASS. Erst danach eigenständig freizugebender V3-Shadow-/Paper-Schritt; Echtgeld später separat.

## Negativkontrollen / Schutz

- H10 ist Hyperliquid-**Traderaktivität**, H8 ist Netzwerk-/On-Chain-**Nutzung**; keine gegenseitige Proxy-Verwechslung.
- Polymarket-Wahrscheinlichkeit ohne präreigistrierten Krypto-Ereigniszusammenhang ist **kein** Signal für XBT/EUR, und Book-Hash-Änderung ohne Midpoint-Änderung ist **kein** Kursimpuls.
- Mehrere korrelierte Medien oder Aggregatoren geben **keine Mehrheitsvoten**; Kraken Spot EUR bleibt Primärautorität für Ausführung.
- Ein fehlender optionaler Sensor darf BUY weder erzeugen noch verhindern; fehlende *erforderliche* Kraken-/Stop-/Kosten-Daten blockieren die spätere Ausführung weiterhin wie bisher.
- Keine Shadow-Doppelserie, H3/H6-Reaktivierung, Secrets, API-Abos, Budgeterhöhung oder Orders. Dies ist eine **reine Verknüpfung bestehender Research-Owner**, keine automatische V3-Aktivierung.

**Verbindliche Kontrollmethode:** `tools/v3_context_fusion_preflight.py` und `tests/test_v3_context_fusion_preflight.py` laufen unter dem bisherigen `project-control-plane-guard.yml` bei Änderungen an PR161-Plan, Source-Routing und relevanten Contracts.
