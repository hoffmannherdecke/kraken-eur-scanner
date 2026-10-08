# Gesamtarchitektur-Audit: Überwachung, Evidenz und kontrollierte Strategieanwendung (v1)

Auditstand: 2026-10-08. **Verbindlicher Architektur-/Research-Vertrag, kein neuer Runtime-Mechanismus.**
Maschinenlesbare Verantwortungsmatrix: `research/monitoring-evidence-routing-v1.json`.
Quellen- und Qualitätsrollen: `research/source-registry.json`,
`research/market-source-candidates-v1.json`,
`docs/market-context-source-fusion-v1.md`,
`docs/market-source-autonomy-v1.md`.
Aktiv-/Shadow-Zustand **nur** `project-current-state.json`;
Echtlauf-/Evidenzzahlen ggf. Supabase/MINI-PC. Frühere Dokumente können
historische Zustände enthalten und sind hierfür nicht autoritativ.

## 1. Gefundene Überlappungen und verbindliche Zusammenlegung

| Informationsklasse | Bereits vorhandener Baustein | Neuer/zweiter Baustein | EIN Verantwortlicher / Resultat |
|---|---|---|---|
| Kraken-EUR-Tradability/Preise | WS/REST/AssetPairs/Scanner | CoinGecko, CMC, Coinbase, Altrady | **Kraken** bleibt alleinige Venue-/EUR-/Order-Condition-Wahrheit. WS/REST sind technische Redundanz, andere Daten nur Plausibilisierung und Trigger; kein zweites Preis-/Tradability-Veto |
| Breite / Relative Stärke / Lead-Lag | V2R4-Kontext; **H1 als alleiniger Entscheider verworfen** | 2h-Marktphasen-Lernradar; CoinGecko/CMC; H6 | **Regime-Radar** beschreibt *nur* prospektive Makrophasen (Quelle: geschlossene Kraken-EUR-Kerzen), H1 bleibt diagnostisch. H6 testet eine separierte *Price×Volume*-Hypothese. Gemeinsamer Faktor-/Feature-Katalog vor V3-Test; keine zwei Stimmen für denselben BTC/ETH-Move |
| Derivate / OI / Funding / Squeeze | Kraken Futures/Binance, H2 | CMC globale Derivate | **H2** ist alleiniger späterer mechanischer Research-Owner. CMC vergleicht aggregierte Risikoindikatoren nur mit Zeit-/Einheitenabgleich, nicht als zusätzlicher H2-Gate |
| FOMC / CPI / Regulierung / News | FOMC-H5 und offizieller Fed-/SEC-Kontext | Redaktionelle Medien / CFTC/BLS/Treasury / Macro-Newsradar | **Originalbehörde** ist für Termin/Fakt autoritativ; Nachrichten sind Hinweise. **H5** besitzt allein die mögliche spätere *Event-Risk-Strategiemechanik* (noch Precheck). Kein automatischer Risk-Off-Kaufblock aus News und zusätzlich H5 |
| Eventwahrscheinlichkeiten | H5 offizielle Makrotermine | H11 Polymarket | H11 prognostische Marktmeinung = isolierte Forschung; das *tatsächliche* behördliche Ereignis bleibt offizieller Fakt. Kein H11↔H5-Doppelveto |
| Orderbuch, Spread, Liquidität | aktive **H3**-Shadow-/Kraken-L2-Auswertung | H9 Maker/Taker-Fill-Modell; V2R4-Kosten | **H3** prüft allein Orderbuch-/Imbalance-Zusatznutzen. **H9** ist ein davon getrennter späterer Fill-/Execution-Cost-Test, keine wiederholte Depth-Entscheidung. Bestehende Kraken-Kosten-/Tradability-Gates unverändert |
| On-Chain / Smart Money | H8 CoinMetrics EOD | H10 Hyperliquid / Arkham / Nansen | **H8 = Netzwerknutzung/EOD**; **H10 = Händler-/Walletaktivität**. Unterschiedliche Zeiten, Coverage und Fehlermuster; Korrelation oder gleiche Token-Bewegung nicht doppelt zählen |
| Meta-Entscheidung / Filter | V2R4 WAIT/REJECT, früher H1-Entscheider | H7 TAKE/NO-TAKE + eventuelle Quellen-/Regimefilter | **H7** nur nach eigenem Label-/Kosten-/Holdout-Gate. Alle H-Signale sind Inputs, **nicht unabhängig kumulierbare Veto-Regeln**. Kein Modelltraining auf einer bereits nach Resultat selektierten Pilotquelle |
| Quellenbewertung | Source-Steward Medien-, Foren- und Fact-Score | Marktphasen-/V3-Strategie-Lernreview | **Source-Steward = Quellengüte**, **gated Work-/V3-Review = tatsächlicher Netto-Trade-Nutzen**. Source KEEP darf niemals automatisch Strategie PROMOTE bedeuten |
| Kandidaten-/Trade-Produktivität | Paper-Lifecycle, WAIT-Expiry, Missed-Move-Audit | Marktphasen-Episoden und Medien-Ereignisse | **Mature Paper-Outcomes** sind einziger Bewertungsnenner; externe Events nur **known-at**-Segmentierung. Review misst BEIDE Seiten: vermiedene Verlusttrades und verpasste Gewinner/Kaufkonversion |
| Infrastruktur-Health / Kosten | Mini-PC Watchdog/Recovery, GitHub Deadman, Supabase-Retention, API-Cost-Guard | täglicher GitHub-Milestone-Controller / Work | **Operations** behebt/es­kaliert echte Fehler und markiert OK, erzeugt **kein** Markt-/Strategie-Signal. **Milestone Controller** beurteilt nur fällige strategische Reviews; Work bewertet tief **nur** bei eigenständig geöffnetem bestehendem Gate, kein doppelter Status-Scanner |

Historischer Alias-Hinweis: frühere historische Second-Leg-`H2`-Replay-Berichte
und die jetzige V3-`H2`-Derivate-Hypothese sind **verschiedene Forschungsfragen**;
nur exakte versionierte Kennungen dürfen zusammengeführt werden.

## 2. Gemeinsame Evidenz-/Anwendungsstrecke

`Primärquelle / Sensor → Normalisieren + timestamp/coverage → de-duplizierter
Beleg → eindeutiger verantwortlicher Owner → bestehendes Domänengate →
kleinster erlaubter nächster Schritt → Ack/Lineage`.

Nur vier **fachlich verschiedene Konsequenzen**:
1. **Technik/Health/Speicherung:** `AUTO_REMEDIATE_WITHIN_EXISTING_POLICY`,
   `ESCALATE_ACTIONABLE` oder `ACK_HEALTHY`. Keine Paper-Entscheidung.
2. **Quelle/Medien:** `SOURCE_KEEP`, `SOURCE_QUARANTINE`,
   `SOURCE_REPLACE` oder `NOT_EVALUABLE`; nur Research-Routing.
3. **Markt/Strategy-Evidence:** `NOT_EVALUABLE`,
   `NO_ACTION_WARRANTED`, `REJECT_WITH_EVIDENCE` oder
   `PREPARE_ONE_CHANGE_TRIAL` im bestehenden V3-/V4+-Ledger,
   ausschließlich nach reifen *known-at* Fällen und Netto-Kosten.
4. **Reifes Release-/Strategie-Gate:** expliziter inaktiver Kandidat,
   ein einzelner Shadow, danach gesonderter Integrationskandidat mit
   Interaktions-/Ausfall-/Low-Trade-Regression und anschließend
   bestehende gesonderte Release-/Nutzerfreigabe. Niemals Auto-Promotion.

**Idempotenz:** Schlüssel je `(domain, source_event_id, asof, candidate_or_series,
hypothesis_version, review_gate)`, außer bei echten veränderten Fakten.
Ein Event kann mehreren unabhängigen *Forschungsfragen* dienen, darf aber
pro Faktor, UTC-Zeitfenster und Ursachenereignis nicht mehrfach zum Beweis
werden. Kein Zählen von gleichlautenden CoinDesk/Reuters-Zitaten oder
CoinGecko/CMC-Marktcap als unabhängige Signale. Früherer Review-ACK
bleibt gültig; keine erneute Work-Runde bloß wegen neuer Source-Scores.

## 3. Regeln gegen gegenseitige Aushebelung

- **Kompetenztrennung:** Ein Sensor stellt einen überprüfbaren Fakt/Snapshot
  bereit; nur sein klar genannter Domänen-Owner legt Bedeutung fest.
  Zusätzliche Recherche-/Quellen-Scores haben **null** direkte
  `BUY/WAIT/REJECT`-Autorität. H1-Standalone bleibt verworfen.
- **Fehler-/Freshness-Trennung:** fehlende zusätzliche Daten → `UNKNOWN`
  im betreffenden Feature, **nicht** negative Signalstärke oder neuer
  Risiko-Veto; primäre Kraken-Qualitäts-/Tradability-Sicherheitsregeln
  dürfen weiterhin korrekt fail-closed bleiben.
- **Regime-Zeitachsen:** 2h-Episoden sind *Forschung zur Marktphase*, nicht
  15m-Entry-Trigger. UTC `source_published_at` ≠ `observed_at`
  ≠ letzter geschlossener Bar; keine Nachinformation in ein Entrylabel.
- **Produktivität:** keine automatische Filteraddition; ein
  möglicher verbesserten Reversal/News-/H-Faktor muss die Anzahl und
  Nettoqualität tatsächlicher Kandidaten/BUYs, verpasste Moves,
  Kosten, Fehltrades und Datenabdeckung *zusammen* verbessern.
  Einseitige Precision-Bewertung bei null BUYs ist unzureichend.
- **Ein Experiment zur Zeit:** H3 bleibt einziger aktiver
  strategieändernder Shadow, H6 nach festem H3-Review; die anderen
  H2/H4/H5/H7/H8/H9/H10/H11/H1 können ausschließlich in ihren
  separat dokumentierten passiven oder vorbereitenden Status laufen.
  Kein Bündel von vermeintlich unabhängigen Filtern; bei späterem
  Integrationskandidaten Wechselwirkungen und Gesamt-Trade-Rate prüfen.
- **Speicherung/Kosten:** Github Issue #7 für kleine materielle
  Forschungsereignisse; Supabase/local für aktuelle/selektionierte
  Candidate-/Outcome-Evidenz; Repo für Verträge/Releases; keine
  doppelte News-/Markt-Rohdatenablage, kein zusätzlicher Scheduler/Workjob.
- **Widersprüche:** Primärautorität, Source-As-of und Dataset-/Methodik
  prüfen. Konflikt `DISAGREEMENT_OR_STALE` oder `NOT_EVALUABLE`;
  niemals Mittelwert, Abstimmung oder „Mehr Quellen = mehr Vertrauen“.

## 4. Verbindliche Auswertung/Abschlussregel

Bei **jedem ohnehin offenen, echten Strategieanalyse-/Integrationsgate**
bestehende Belege gezielt nach Domäne priorisieren; nur solche mit
ausreichender Bekanntzeit/Reife und möglichem inkrementellem Effekt lesen.
Jeder **materielle** Befund muss eine dokumentierte Folgehandlung oder
`NOT_EVALUABLE` / `NO_ACTION_WARRANTED` / `REJECT_WITH_EVIDENCE`
haben. Erfolgreicher technischer Monitor → betrieblicher ACK, nicht
künstlich ein zusätzliches Strategietraining.

**Praktische Umsetzung:** Die bestehende tägliche Work-Analyse erkennt
ihre Gates wie bisher unabhängig anhand `project-current-state.json`
und bestehender Reife-/Meilensteine. Ein Beobachtungsereignis öffnet
niemals selbst Work, darf aber bei gültigem Gate nicht wegen einer
isolierten Quellen-Datenbank ignoriert werden. Der Source-Steward
speichert nur qualifizierte Forschungs-Hinweise und bewertet Quellen,
nicht Trade-Performance. Freigegebene sichere Folgearbeiten innerhalb
des bestehenden Gates werden automatisch erledigt; für tatsächlich
genehmigungspflichtige Strategie-/Liveänderung entsteht das vorhandene
Entscheidungspaket.

**E2E-Ehrlichkeit:** Das Repo bestätigt aktuelle Monitor-/Forschungs-
*Verträge*, nicht zwingend tatsächliche unbeaufsichtigte Radar-
Ausführung. Im GitHub Research-Issue #7 liegt derzeit nur der
`MARKET_REGIME_SEED_V1`-Eintrag vom 08.10., keine nachgewiesene
`MARKET_REGIME_EPISODE_V1` und keine
`SOURCE_STEWARD_DECISION_V1`. Der vorhandene 2h-Task ist zwar
aktiviert, sein sichtbarer Last-run-Wert liegt derzeit noch vor der
neuen Aufgabenfassung. **Daher kein Vermerk „live vollständig
integriert“**. Ein erster echter unbeaufsichtigter Quellen-Read,
Kraken-EUR-Episodenmarker sowie erster erfolgreich geprüfter
Quelle→Outcome→Disposition-Fall sind noch ausstehende
**E2E-Akzeptanznachweise**, und zwar im bereits bestehenden
Projekt-Backlog ohne neue Kontrollschleife.

## 5. Änderungshoheit

Dieser Vertrag ordnet Überwachung und Auswertung neu, aktiviert
aber keine zuvor abgelehnten H1-Logiken, neuen Buy/Reject-/H5-Risk-
oder H7-Meta-Gates, keine realen Orders und keine neue Datenquelle.
`project-current-state.json` bleibt für die aktuelle V2R4/H3-
Situation unverändert. Neue Quellen werden nur nach Source-Intake
technisch angebunden; neue Strategie-Funktionen nur nach
One-change-/Shadow-/Integrations-/Release-Gates. Für V4+ und
separat freigegebene Echtgeldnachfolger gilt dieselbe
Lineage/Feedback-Trennung.
