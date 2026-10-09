# Autonomes aktives Quellenmanagement: entdecken, bewerten, pflegen, aussortieren und nutzen (v1)

Beschluss: 2026-10-08. Geltung: **dauerhaft** über V2R4, V3, V4+ und nach separater Freigabe auch künftige Echtgeld-Nachfolgeanalysen. Kanonisch für neue Kandidaten: `research/market-source-candidates-v1.json`; **tatsächlich zugelassene Quellen** bleiben im vorhandenen `research/source-registry.json` unter `docs/source-intake-policy.md`. Ergänzung zum bestehenden `docs/market-context-source-fusion-v1.md`.

**Ziel:** Mit möglichst wenigen unabhängigen, brauchbaren Informationen Marktphasen, wichtige Ereignisse und frühe Chancen besser verstehen. **Nicht** jede Seite dauernd abrufen, nicht 30 korrelierte Meinungen zählen, nicht gute BUY-Kandidaten mit zusätzlichen Veto-Filtern aussortieren. Automatisches Quellenmanagement bedeutet Forschungs-/Kontext-Routing, **niemals autonome Änderung der aktiven Handelsstrategie**.

## Präzisierung des Nutzerauftrags: aktives Management statt Quellenrotation (09.10.2026)

**Eigentümer und Aufgabe:** Ich verwalte den gesamten zulässigen **Forschungsquellenbestand** eigenständig, laufend und proaktiv. Das umfasst **auch bislang unbekannte** gute Quellen: gezielte Entdeckung, unabhängige Primärverifikation, Aktualität/Erreichbarkeit, tatsächlichen Früh- und Zusatznutzen, Vergleich bestehender Quellen, qualifizierte Aufnahme, fortlaufende Pflege, begründete Herabstufung/Quarantäne, reversible Ablösung und die Suche nach besseren Alternativen. Die bisherige Liste mit 27 Kandidaten ist **ein Startbestand und keine abgeschlossene Whitelist**. Nicht allein Quellen durch andere ersetzen, sondern Informationslücken erkennen und ein möglichst kleines, qualitativ starkes Gesamtportfolio der Forschungsquellen betreuen.

**Vollautonomie bedeutet im genehmigten Forschungsbereich:** Neue kostenfreie, öffentlich lesbare und rechtmäßig nutzbare Kandidaten sowie begründete Bewertungen/Quarantäne-/Auswahländerungen brauchen nicht jeweils eine manuelle Rückfrage, solange der bestehende Source-Intake und PR/CI/Beweispfad eingehalten werden. Der Nutzer muss weder Quellen vorschlagen noch Erinnerungen auslösen. Bei fehlenden GitHub-Schreibrechten oder nicht belegter technischer Einspeisung `BLOCKED/NOT_EVALUABLE` dokumentieren, nichts als erledigt ausgeben. Ein Quellenwechsel in **aktive Scanner-/Trading-Runtime**, zusätzliche Rechte/Secrets/Kosten oder geänderte BUY/WAIT/REJECT- und Risikoregeln sind ausdrücklich **nicht** Teil dieser Autonomie.

**Tatsächlicher Ausführungspfad:** Der bestehende zweistündliche Quellenradar ist der einzige Beobachtungs- und Quellenpflege-Takt. In seiner ohnehin vorhandenen Wochenrunde muss er nicht nur die gelisteten Quellen, sondern bei begründeter Lücke **mindestens einen bislang unregistrierten Kandidaten gezielt suchen** (sofern öffentlich und im festen Budget verfügbar); unabhängig davon bei relevanten neuen Quellen oder belegten Ausfällen anlassbezogen reagieren. Maximal ein neuer Kandidat pro Woche als regulärer Recherche-Schritt, zusammen mit höchstens zwei aktuellen Piloten/zwei Challenger-Vergleichen; maximale zwei redaktionell tatsächlich gelesene Quellen am Tag bleiben bestehen. Ist keine neue Quelle sinnvoll, explizit `NO_NEW_SOURCE_WARRANTED` im internen Gate statt erfundener Entdeckung. **Kein neuer Job, keine neue Frequenz.** Das automatisch laufende Monitoring kann einen freien Forschungsquellenkatalog nur dann praktisch pflegen, wenn ein echter GitHub-PR/CI-/Feed-E2E-Durchlauf nachgewiesen ist – bis dahin Status `UNATTENDED_E2E_UNVERIFIED`.

**Wiederaufnahme / Folgepflicht:** Quellenpflege endet nicht bei `PILOT` oder `KEEP`: Der Quellenmanager prüft bei neuen sachlichen Belegen Erreichbarkeit, Aktualität, Verlässlichkeit, Unabhängigkeit und Nutzen erneut, sucht bei belegter Lücke bessere Alternativen und führt relevante Erkenntnisse in bestehende Strategieanalysen zurück. Qualitätsbewertung nach fünf Ereignissen/zwei Zeitfenstern; E2E-Quelle und späterer Handelsmehrwert bleiben ausdrücklich voneinander getrennte Nachweise. Die fachlich begründete Abschlussentscheidung darf daher auch `NO_CHANGE`, `DEFER_WITH_GATE`, `QUARANTINE` oder `REPLACE_RESEARCH_ONLY` heißen. Belege über vorhandenes Issue #7, Kandidatenkatalog und Source-Registry, nicht über ein neues Datenarchiv.

**Maschinenlesbarer Owner:** `research/monitoring-evidence-routing-v1.json#source_quality.activation_followthrough` (`AUTONOMOUS_ACTIVE_SOURCE_MANAGEMENT_E2E_GATE_V1`), offene Aufgaben in `PROJECT_BACKLOG.md`, automatischer Prüfpfad in den **bestehenden** 2h-Aufgabeninstruktionen. Der bestehende Monitoring-Guard schützt Discovery-Wiedervorlage und fehlende Handelsautorität.

## 1. Autorisierte Autonomie und echte Grenzen
- **Selbstständig, ohne neue Nutzerfreigabe zulässig:** öffentliche, erlaubte, kostenfreie/read-only Quellen entdecken; redaktionelle Trennung, zugängliche APIs/Feeds/RSS und Quellendefinitionen prüfen; kleinen read-only Smoke durchführen; Quelle in Forschungs-PILOT/BEOBACHTUNG/QUARANTÄNE setzen; redundante/unzuverlässige *optionale Forschungsquellen* aus dem aktiven Recherche-Mix nehmen und durch besser belegte Kandidaten ersetzen; beweisbasierte Source-Registry-/Katalog-/Governance-Diffs über normalen Branch→PR→CI→Merge vorbereiten und bei allen passenden grünen Guards innerhalb dieses rein forschungsseitigen Umfangs übernehmen.
- **Kein freier Änderungsraum:** weder einen unverzichtbaren Kraken-Datenpfad, Trading-/Konto-/Orderrechte, Secrets, bezahltes Abo, aktiven Scanner, Frozen Series V2R4, H3, H6, Work-Gate noch Strategie-Thresholds ohne separate bestehende Source-Intake-, Sicherheits-, Release- und Nutzer-Gates verändern. Keine automatische Echtgeldfreigabe oder eigenmächtiges Engagement auf Foren.
- Ein Quelle-Switch wirkt zunächst nur auf die **Quellenauswahl der nächsten Forschungs-Runde**, nicht auf BUY/WAIT/REJECT oder frühere Episode-Labels. Jede Änderung bleibt nachvollziehbar/reversibel. Entfernen heißt zunächst `QUARANTINED`/`RETIRED_RESEARCH`, nicht historische Beweise löschen.

## 2. Breite Suche, kleiner aktiver Lesesatz
Drei Informationsschichten:
1. **Primär/Fakt:** Kraken Spot-EUR für Ausführung und Marktphase; SEC/CFTC/Fed/BLS/Treasury/FinCEN/ESMA/BaFin/Exchange/Projekt-Originalmitteilungen für Fakten; ein Artikel verweist nur auf die Primärquelle. Keine dritte Preisquelle überschreibt Kraken.
2. **Redaktionell/aggregiert:** CoinDesk, The Block, Decrypt und Reuters als erste Nachrichten-Piloten. CryptoSlate, Cointelegraph, DL News, Unchained, Blockworks/Messari als Alternativen mit Zulässigkeits-/Qualitätscheck. CoinGecko/CMC als bestehende komprimierte Gesamtmarkt-Crosschecks; DefiLlama/Coinglass als begrenzte aggregierte Risiko-/DeFi-Kontextpiloten. CoinMarketCal/CryptoPanic/Chainalysis/Glassnode/CryptoQuant/TRM/SlowMist/CertiK als Event-/Sicherheits-/Research-Hinweise, einzeln nach Gate.
3. **Communities/Tradingideen:** Reddit r/CryptoCurrency, r/BitcoinMarkets, r/ethfinance, BitcoinTalk, TradingView nur **Frühhinweise oder konträre Hypothesen**; keine ungeprüften Tips, Bots, Paid Promotions oder anonyme Posts als Wahrheit oder BUY-Veto. Coinspeaker-Hype/Presale-/Werbeanteil bewusst zunächst quarantiniert. Trenne bezahlte Pressemitteilungen/Partnerinhalte konsequent von unabhängigem Journalismus.

**Begrenzung:** Bestehende 2h-Marktphasen-Radar-Aufgabe bleibt die einzige neue Forschungs-Schedulerfläche; in normalen Runden bereits vorhandenes Kraken-EUR-Regime und höchstens zwei bestehende kompakte CoinGecko/CMC-Aggregate, nicht alle Medien. Maximal **zwei unterschiedliche Nachrichtenquellen pro täglichem regulärem Quellen-/News-Check**, vorzugsweise eine redaktionelle und eine offizielle/primäre. Bei einem belegten besonders relevanten Ereignis höchstens gezielter dritter Primärbeleg. Der Nutzer wird nur bei bereits nach bestehender Melderegel tatsächlich nötiger Handlung informiert, nicht wegen der Quelle.

## 3. Dauerhafter autonomer Qualitätszyklus, ohne zusätzlichen Work-Lauf
- **Täglich** in **einer vorhandenen** 2h-Runde mit 08:00–10:00 UTC: wenige crypto-relevante Schlagzeilen/Ereignisse, Quellenzeit, Primärbestätigung, Dedupe und Relevanz prüfen. Normale Runden bleiben ohne News-Vollscan. Bei datenbasiertem schweren Abverkauf/Rebound gezielter On-demand Check möglich; keine zusätzliche Aufgabe.
- **Wöchentlich** in derselben ohnehin fälligen Montag-Runde: gezielte aktive Suche nach höchstens **einer bisher unbekannten** möglicherweise nützlichen Quelle bei einer belegten Informationslücke sowie Vergleich von **höchstens zwei** Piloten und **höchstens zwei** Warte-/Challenger-Quellen anhand konkreter relevanter Ereignisse prüfen. Wenn der Wochengate-Lauf fehlt, nichts als geprüft ausgeben. Keine künstlichen 2-/4-Wochen-Wartefristen: Umfang nach tatsächlich überprüfbaren Fällen; wenn zu wenig, `INSUFFICIENT_EVIDENCE`.
- **Generationenübergreifend** bei ohnehin geöffneter Paper-/V3-/Live-Analyse: konkret prüfen, ob eine Quelle unabhängig früher/korrekter **entscheidungsrelevante** Fakten liefert, *nicht* ob sie nur bullish klingt oder nachträglich einen Gewinner erklärt. Noch nicht bekannter Kontext darf keine rückwirkende Verbesserung begründen.

## 4. Evidenz, Score und Entscheidungen
Pro **materiellem** unabhängig verifiziertem Ereignis kompakt speichern: `source_id`, `first_seen_utc`, `source_published_at_utc`, `primary_url`, `topic/asset`, `claim`, `official_confirmed_at_utc` (oder UNKNOWN), `freshness`, `correct/false/unknown`, `duplicate_of` (falls vorhanden), `actual_decision_value`, `reason`. Werbe-/Sponsoring-Status, bekannte Access-/Preislimits und Mehrwert gegenüber dem bereits vorhandenen Kraken-/Fed-/CoinGecko-Kontext gehören dazu. Für Reddit: Verifizierer ist stets extern/primär.
Bewertung **pro Quellengattung getrennt**, niemals News-Medium gegen Kraken-API im gleichen Ranking:
- **40 %** Genauigkeit + Primärquellen-Nachweis;
- **25 %** zusätzliche relevante/frühere Information gegenüber bereits verwendeten Quellen;
- **15 %** datierte Aktualität, Zugriff/Zuverlässigkeit;
- **10 %** niedrige Duplikat-/Werbe-/Gerüchtequote;
- **10 %** Kosten, Kontingent/Compliance und einfache Handhabung.
Scores sind erst **nach mindestens fünf unabhängig überprüften relevanten Ereignissen aus mindestens zwei voneinander getrennten Erfassungszeitfenstern** zulässig; sonst `NOT_EVALUABLE`, keine scheinpräzise Rangliste. Mehrfachveröffentlichung derselben Agenturmeldung zählt nicht mehrfach. Fehlende Ereignisse dürfen nicht als Falschmeldung gewertet werden. Die Qualität von Marktaggregaten misst Metrikdefinition/As-of/Abdeckung/Fehler und nicht redaktionelle Prognoseleistung.
- **Promote/Keep:** Wiederholte belegte Verlässlichkeit **und** echter inkrementeller Nutzen; kostenlos/erlaubt, E2E-Read-Pfad plus Fail-soft, keine Kollision mit Source-Registry. Nur Forschungskontext.
- **Quarantine/Demote:** Nachgewiesene Falschzitate, manipulative Promotion, unsichere oder rechtswidrige Datenzugänge sofort Forschungsquarantäne; sonst bei **mindestens drei materiell falschen, durch Originalquelle belegten Fakten aus mindestens zehn bewertbaren, unabhängigen Ereignissen** (nicht bloß unterschiedliche Meinungen/Zeithorizonte) Quelle aus Pilot entfernen und Ersatz vorbereiten. Kürzere Stichprobe: vorläufige Warnung, nicht künstlich automatisch löschen.
- **Retire/Replace:** Über mehrere echte Fälle redundant, kein zusätzlicher Erkenntniswert, wiederholt stale/Paywall/Auth-Ausfall oder negatives Verhältnis Nutzen/Aufwand; nur Forschungs-Source-Routing ändern. Eine Quelle darf später mit neuen Belegen erneut qualifizieren. Kein automatischer Downgrade bloß wegen abweichender Einschätzung zu `UNKNOWN`.
- **Kein Alpha per Quelle:** Eine Quelle mit guter Nachrichtenqualität ist noch **kein profitables Handelssignal**. Profit/Trade-Frequenz/False-REJECT/Missed-Move/Overfitting in separaten V3-One-change-/Releasegates prüfen; H1 als Standalone bleibt verworfen.

## 5. Begrenztes Änderungs- und Speicherprotokoll
- Kanonisch ein kleines Katalog-JSON (`research/market-source-candidates-v1.json`) und das bestehende Quellenregister; kein neuer Nachrichtenspeicher, DB-Tabelle, Scanner oder GitHub-Workflow. Bei neuen Quellen niemals die gesamte Datenbank/Weltgeschichte sammeln.
- Nur **materielle Statuswechsel**/`SOURCE_STEWARD_DECISION_V1` in bestehendem GitHub V3-Research-Issue #7 (maximal kompakter Kommentar mit Evidenz-URLs, Quelle, Vorher/Nachher, Grund, Datum, next gate); kein Kommentar bei unveränderter Woche und keine Routine-Pushmeldungen. Eine Entscheidung maximal einmal je Quelle/Evidenzzustand; kein Wiederholungslauf.
- Source-Registry-Aktivität und eine tatsächlich **technisch regelmäßig funktionierende** Versorgung sind verschieden. Vor Aktiv-Nennung einmal echten unbeaufsichtigten Read+Zeitstempel+Failsoft prüfen; ansonsten Status `PILOT_READ_ONLY` oder `ACCESS_CHECK_REQUIRED`.
- Versionierte Quelldiff-Änderung als Branch/PR, vorhandene Validierungschecks, Provenance-Referenz und rollbackfähiger Merge; **keine neuen Rechte**, keine Löschung von Evidenz und keine geheime Runtimeänderung. Relevante V3-Lerneffekte ins bestehende Migrationsledger übernehmen, nicht eigene Strategie forcieren.

## 6. Pflichtübergabe: Quellen-Erkenntnis → Strategie-Nutzenprüfung

**Verbindlicher, generationsübergreifender Schließkreis.** Gute Quellen dauerhaft
zu lesen ist **nicht** das Projektziel; ihre materiellen Erkenntnisse müssen bei
einem ohnehin offenen V2R4-/V3-/V4+- bzw. späteren Live-Nachfolger-Analyse-Gate
eine begründete Entscheidung erhalten. Der Source-Steward bleibt eigenständig
für **Qualität / Source-Routing**; nur der bereits vorhandene Strategie-
Analyse-/Releasepfad ist verantwortlich für **Trading-Inkrementalnutzen**.
Das eine öffnet nie das Gate des anderen. Keine neue Work-Aufgabe.

1. **Erfassung / echter Kenntniszeitpunkt:** nur relevanter, neu belegter Claim
   oder Marktphasenwechsel. Provenienz `source_id`, `first_seen_utc`,
   `publication_utc`, `source_asof_utc`, `primary_evidence_url`,
   betroffene Kraken-Spot-EUR-Assets/Thema, Wirkungshypothese,
   Duplikate/Unsicherheit und `source_e2e_verified`; sonst
   `NOT_EVALUABLE`. Kompaktes bestehendes Issue #7, kein Raw-News-Archiv.
2. **Einmaliges Wirkungsrouting:** Bei *ohnehin* geöffnetem Analyse-Gate
   identische Fälle auf vorhandenem Baseline-Kandidatenstrom zeitlich
   korrekt abgleichen: BUY/WAIT/REJECT, gereifte MFE/MAE, False
   REJECT/Missed Move, Cost/Slippage, Trade-Frequenz, mögliche neue
   Kandidaten und Fehltrades. Quelle gegen **bereits bekannte**
   Kraken-/BTC-/ETH-/Breadth-/News-Information abgleichen. Keine
   nachträglichen Newslabels, kein im Nachhinein ausgesuchter Gewinner.
3. **Inkrementalitätsprüfung:** Vor separatem Test exakt **eine**
   Anwendungshypothese spezifizieren: z. B. frühere selektive
   Gegenbewegungserkennung, bestätigtes Risikoevent, echter
   Coin-/Sektor-Katalysator oder begründete WAIT-Revalidation.
   Gleichzeitig messen, ob ein zusätzlicher Filter gute BUYs zerstört.
   Negative/fehlende Quellen erzeugen keinen neuen Handels-Blocker.
4. **Pflichtdisposition statt Endlosbeobachtung:** Nach tatsächlicher
   Evidenzprüfung genau eine Entscheidung mit Beleg, Datum und
   nächstem erlaubtem Gate:
   `NO_ACTION_WARRANTED` (kein Mehrwert / doppelt),
   `NOT_EVALUABLE` (fehlt bekanntzeitliche/reife Basis, kleinsten
   sinnvollen nächsten Evidenz-Gate nennen, **nicht** extra Work
   anstoßen), `PREPARE_ONE_CHANGE_TRIAL` (nach reifen, konsistenten
   Anzeichen: versionierter **inaktiver** V3-/Nachfolger-Kandidat,
   eingefrorene Kosten-/Holdout-/Trade-Quote-/False-Reject-Gates)
   oder `REJECT_WITH_EVIDENCE` (nach geprüftem Negativergebnis).
   Pilot-Erfolg = **Quellengüte**, nicht automatisch `PREPARE`.
5. **Ausführung und Aufbewahrung:** Wo genehmigt, den Folgeschritt
   *im selben bereits geöffneten Analysevorgang* autonom erledigen
   (verknüpfter Research-Claim, One-change-Precheck, Versionsledger,
   deduplizierter Ack im `research/work-analysis-state.json`);
   nicht auf eine neue Nutzerfrage schieben. Benötigte Strategie-/
   Release-Freigaben explizit eskalieren; keine stille Aktivierung.
   Quellenergebnisse veralten nicht still: bei der nächsten
   einschlägigen Strategie-Integrations-/Releaseprüfung müssen sie
   explizit disponiert oder mit konkretem, nicht kalenderbasiertem
   Datenmaturitäts-Gate nach V4+ weitergegeben werden. Fehlende
   Quellen-E2E-Funktion darf keinen V3-Promotion-Gate künstlich sperren.

Die Forschungsspur bleibt unabhängig von der Wirksamkeit: Eine
hochqualitative Nachrichtenquelle ohne Handelssignal darf als
**Kontextquelle** erhalten bleiben; ein bestätigter Trading-Nachteil
erzwingt `NO_ACTION_WARRANTED` bzw. `REJECT_WITH_EVIDENCE`.
Wegen mehr Quellen **niemals** automatisch breitere Kaufveto-Ketten
erzeugen. Handelsänderungen ausschließlich über bewährte
Version-/Shadow-/Paper-/Freigabeprozesse.

## 7. Erste Bestandsaufnahme (2026-10-08)
Öffentliche Web-Zugänglichkeit/Quelle bzw. aktuelle Berichte wurden für Teile des Katalogs geprüft; **kein** hier aufgeführtes Nachrichtenmedium ist dadurch bereits als autonomer API-/RSS-Feed in unserer Scanner-/Mini-PC-Runtime belegt. CoinDesk/The Block/Decrypt/Reuters und DefiLlama/CoinGlass sind **Pilot-Vorschläge**, kein Live-Schalten. [CoinDesk](https://www.coindesk.com/) trennt sichtbare redaktionelle Rubriken und sponsored content; [CoinMarketCal](https://coinmarketcal.com/) bietet Event-Kalender; [DefiLlama](https://defillama.com/) liefert DeFi- und Stablecoin-Aggregate. Bei Reddit warnt selbst r/CryptoCurrency vor Marktmanipulation und Scams. Blockworks/Messari erfordern wegen berichteter 2026-Geschäftsmodelländerungen einen neuen Angebotscheck. Kein bezahltes Abonnement oder verstecktes Scraping gestartet.
