# Strategy Version Map — Aktien & Krypto Chancen

Status: **KANONISCHE STRATEGIE-ÜBERSICHT**  
Stand: 2026-09-29  
Aktive Strategie: `V2R3-2026-09-28`  
Aktive Serie: `PAPER-V2R3-FINAL-20260928T1752Z`

## 1. Zweck

Diese Datei ist die verbindliche Übersicht darüber, **welche Strategieversion wofür steht,
welche Erkenntnisse wohin gehören und wann eine Version aktiviert werden darf**.

Sie ersetzt keine Detaildokumentation und keine To-do-Liste:
- offene Projektarbeit bleibt im `PROJECT_BACKLOG.md`;
- V3-Forschung im `docs/v3-research-framework.md` und GitHub Issue #7;
- die vorbereitete V2R4-Implementierung liegt derzeit in Draft-PR #8.

Bei Widersprüchen gilt:
1. aktive Runtime-Konfiguration für den aktuellen Ist-Zustand;
2. diese Datei für Versionsbeziehungen und Routing;
3. jeweilige Fachdokumentation für Detailregeln;
4. ältere Chats/Notizen nur als Historie.

---

## 2. Versionslandkarte

### V2R3 — aktive, eingefrorene Kontroll-/Paper-Version

**Status:** AKTIV / PAPER ONLY / eingefrorene Vergleichsbasis  
**Start der homogenen Serie:** 2026-09-28 17:52 UTC  
**Series-ID:** `PAPER-V2R3-FINAL-20260928T1752Z`  
**Echtgeld:** deaktiviert

Zweck:
- aktuelle Baseline sauber messen;
- technische Pipeline von Strategieeffekt trennen;
- BUY / WAIT / REJECT plus späteren Kursverlauf auswerten;
- Timing-, Kosten-, Missed-Move- und Datenqualitätsprobleme sichtbar machen.

Wichtige aktive Regeln:
- 0,60 % Taker-Gebühr je Seite als Referenz;
- 50 EUR Scout + 50 EUR Stage 2 **nur weil V2R3 eingefroren ist**;
- Stage 2 braucht explizite Bestätigung;
- Trailing-Stufen: +7 % → 4 %, +12 % → 3 %, +15 % → 2 %;
- Follow-up: 30 / 60 / 120 / 360 Minuten;
- maximal 72 h Haltedauer;
- keine stille Änderung von Entry, Stop, Sizing, Scanner oder Kostenmodell.

Wichtig:
Die 50+50-EUR-Größe ist **keine aktuelle strategische Präferenz**, sondern Teil der
eingefrorenen V2R3-Spezifikation. Sie wird nicht rückwirkend geändert.

Der Zielwert von 20 abgeschlossenen Paper-Trades ist ein **operativer/prospektiver
Meilenstein**, kein statistischer Beweis für Edge. Falls V2R3 zu wenig handelt, muss
ein alternatives, vorab definiertes Abschlusskriterium verwendet werden.

---

### V2R4 — vorbereitete taktische Timing-/Trigger-Version

**Status:** PREPARED / NOT ACTIVE / PAPER ONLY  
**Implementierung:** Draft-PR #8  
**Zweck:** gezielt das in V2R3 erkannte WAIT-/Revalidation-Latenzproblem untersuchen.

V2R4 ist **keine Ersatzbezeichnung für V3**. Sie ist eine eng begrenzte Zwischenversion,
die möglichst wenig an der Strategie ändert und zuerst die Reaktionsgeschwindigkeit
verbessert.

Kernhypothese:
V2R3 filtert viele schlechte Kandidaten korrekt, verpasst aber einzelne gute Moves,
weil ein WAIT häufig erst einmalig am Ende einer 30–60-Minuten-TTL geprüft wird.
Ein gültiger Trigger kann dazwischen auftreten und wieder verschwinden.

Geplanter V2R4-Pfad:
1. Kandidat wird bewertet.
2. WAIT enthält maschinenlesbare Triggerbedingungen.
3. Mini-PC überwacht Kraken-Public-Daten lokal/eventnah.
4. Altrady darf zusätzlich wecken, ist aber nie alleinige Quelle.
5. Trigger-Match führt **nur** zu `FRESH_PAPER_RECHECK_ONLY`.
6. Erst eine frische Gesamtbewertung darf BUY_SCOUT erzeugen.
7. Stage 2 bleibt eine separate Bestätigung.

Ziel-Latenz:
- lokaler Fallback-Poll zunächst ca. 10 s;
- technisch vorbereiteter Mindestwert 5 s;
- Trigger → frische Neubewertung Zielgröße <= ca. 20 s;
- tatsächliche Intervalle werden erst nach Mini-PC-/Rate-Limit-Messung festgelegt.

V2R4-Positionsgrößen im Paper-Test:
- B+ / früher Scout: 75 + 75 EUR → 150 EUR gesamt;
- A-: 75 + 75 EUR → 150 EUR gesamt;
- A: erste Stufe 100–125 EUR, bestätigt ca. 200–300 EUR gesamt;
- A+: erste Stufe 150–200 EUR, bestätigt ca. 300–600 EUR gesamt.

Diese Staffel ist eine **Paper-Test-Spezifikation**, keine automatische spätere
Echtgeldfreigabe. Skalierung erfolgt nur mit Setup-Qualität und Bestätigung; niemals
nur, um eine Zielgröße zu erreichen.

Aktivierungsbedingung:
V2R4 darf als **separate Paper-Serie** starten, sobald
- die Mini-PC-Basis stabil ist,
- Uhrzeit/Netzwerk/Watchdog funktionieren,
- ein kleiner End-to-End-Paper-Smoke-Test bestanden ist,
- Trigger-Vertrag und Logging nachweislich funktionieren.

V2R4 muss **nicht** darauf warten, dass V2R3 zwangsläufig 20 abgeschlossene Trades
erreicht. V2R3 bleibt jedoch unverändert als historische/prospektive Vergleichsbasis.

---

### V3 — bereits angelegter größerer Research-/Strategie-Nachfolger

**Status:** ACTIVE RESEARCH / NOT ACTIVE TRADING  
**Kanonische Detailquellen:** `docs/v3-research-framework.md` und GitHub Issue #7  
**Angelegt:** 2026-09-28 nach Literatur-/Methodik-Auswertung, u. a. Stefan Jansen.

V3 ist die **größere nächste Strategiegeneration und der langfristige Nachfolger der V2-Linie**. Sie startet nicht bei null. Der jeweils letzte belastbare Stand aus V2/V2R4 wird als Ausgangsbasis übernommen und mit neuen, nachgewiesenen Verbesserungen aus Research, historischen Tests und prospektiver Shadow/Paper-Evidenz erweitert.

Grundprinzip: **inherit first, replace only with stronger evidence**. Bewährte V2-Bausteine werden standardmäßig weitergeführt. Ein bestehender Baustein wird in V3 nur verändert oder verworfen, wenn eine versionierte Alternative unter realistischen Kosten und sauberer OOS/prospektiver Prüfung einen klaren zusätzlichen Nutzen oder eine relevante Risikoverbesserung zeigt.

Nicht verhandelbare Methodik:
- feste, versionierte Spezifikation;
- point-in-time Daten;
- chronologisches Walk-Forward;
- Purging / Label-Buffer und Feature-Embargo;
- Search Accounting / Trial Ledger für jede getestete Variante;
- Multiple-Testing-/Selection-Bias-Kontrollen, z. B. FDR, Deflated Sharpe,
  Reality-Check/SPA sowie PBO/CPCV soweit Stichprobe genügt;
- versiegelter Holdout erst nach Auswahl/Tuning;
- Holdout danach nicht zum Retuning missbrauchen;
- Signal und State/Conditioning konzeptionell trennen;
- realistische Kraken-EUR-Kosten, Spread, Slippage und Turnover;
- einfache transparente Baselines vor komplexem ML;
- Backtests primär als Falsifikationswerkzeug;
- keine automatische Promotion in Echtgeld.

Aktuelle V3-Research-Prioritäten:
1. Kosten / Break-even / Trial Ledger / Selection Bias;
2. MAE/MFE und regimeabhängige Stop-/Exit-/TTL-Forschung;
3. Cross-Crypto Lead/Lag und Marktbreite;
4. Basis / Premium / Funding / Open Interest;
5. einfache Multi-Horizon Price×Volume-Signale;
6. Orderflow / Tiefe / Imbalance mit Mini-PC/WebSocket;
7. Makro-Event-Risk-Gates;
8. Meta-Gate TAKE / NO-TAKE erst nach genügend sauberen Labels;
9. On-Chain nur nach Daten-/Timing-Preflight;
10. Maker-vs-Taker / Fill-Wahrscheinlichkeit erst vor späterer Execution-Stufe.

V3-Sizing-Prinzip:
Nicht einfach „hoher Score = viel Geld“. Zu testen ist Sizing als Funktion aus
Signalqualität, Volatilität, Stop-Distanz, Risikobudget und Konzentrations-Cap.
Fractional Kelly ist höchstens spätere Research-Variante, kein Default.

V3-Promotion:
`RESEARCH → PRECHECK → OFFLINE_TEST → frozen candidate → SHADOW/PAPER → promotion review`

Eine V3-Aktivierung erfolgt **nicht nach Kalenderdatum**. Sie braucht robuste
historische/OOS-Evidenz plus prospektive Evidenz und einen expliziten Promotion-Schritt.

---

## 3. Verhältnis V2R4 ↔ V3

V2R4 und V3 laufen nicht gegeneinander.

**V2R4** beantwortet primär:
> Können wir mit derselben Grundidee gute Trigger rechtzeitig sehen und ausführen,
> ohne die Schutzfilter breit zu lockern?

**V3** beantwortet primär:
> Welche Signale, States, Stops, Exits, Kostenmodelle und Sizing-Regeln erzeugen
> nach sauberer Validierung tatsächlich robusten Netto-Mehrwert?

Erkenntnisse aus V2R4 fließen nicht nur als lose Evidenz in V3 ein, sondern erfolgreiche und weiterhin passende V2R4-Bausteine werden **als vererbte Baseline-Komponenten** in den V3-Kandidaten übernommen. Dazu gehören:
- tatsächliche Triggerlatenz;
- WAIT→Trigger→BUY-Konversion;
- MFE/MAE;
- False Trigger;
- Kosten nach früherem Entry;
- Performance je Setup- und Größenklasse;
- Mini-PC-/Altrady-/Kraken-Latenz und Feed-Qualität.

V2R4 darf daher taktisch vor V3 starten, ohne V3 zu ersetzen. Sobald ein V3-Kandidat gebaut wird, basiert er auf dem **besten bis dahin validierten V2/V2R4-Gesamtstand**, nicht auf einer leeren Forschungsarchitektur.

---

## 4. Routing-Regel für neue Erkenntnisse

Damit nichts mehr im falschen Kontext landet:

### Gehört nach V2R4, wenn …
- es hauptsächlich WAIT-/Trigger-/Revalidation-Latenz verbessert;
- es schnellere lokale Beobachtung ermöglicht;
- es die bestehende Grundlogik weitgehend erhält;
- es eine kleine, klar isolierbare Timing-/Scout-Änderung ist.

### Gehört in V3 Research, wenn …
- neue Signal-/Feature-Familien entstehen;
- Regime-/State-Logik wesentlich geändert wird;
- Stop/TTL/Exit methodisch neu gestaltet wird;
- Sizing/Risikobudget grundlegend geändert wird;
- Funding/OI/Basis, Lead/Lag, Orderflow, On-Chain, Makro oder ML neu eingebaut wird;
- mehrere Mechanikänderungen gegenüber der Baseline nötig wären.

### Gehört in Infrastruktur/Backlog, wenn …
- es Watchdog, Recovery, Backup, Netzwerk, Logging, Supabase, Slack, API-Kosten,
  Windows, Autostart, Stromausfall oder allgemeine Mini-PC-Zuverlässigkeit betrifft;
- es keine Trading-Regel verändert.

Infrastrukturverbesserungen können V2R4/V3 **ermöglichen**, sind aber selbst keine
Strategieversion.

---

## 5. Mini-PC-Rolle

Der Dell OptiPlex 5060 Micro ist die spätere 24/7-Basis.

Reihenfolge:
1. Windows/BIOS/Treiber/Uhrzeit/Netzwerk;
2. automatisches Wiederanlaufen nach Stromausfall;
3. unbeaufsichtigter Runtime-Start/Fernzugriff;
4. Logging, Backup, Watchdog und Recovery;
5. Kraken-Public-/Realtime-Daten;
6. Altrady als zusätzlicher, nicht exklusiver Trigger;
7. GitHub/API/Slack/Supabase schlank anbinden;
8. V2R4-Smoke-Test;
9. V2R4-Paper-Serie;
10. historische Backtest-/V3-Research-Schicht weiter ausbauen;
11. Self-hosted Runner und spätere Trading-API erst nach stabilem Grundbetrieb.

Kein einzelner Dienst darf alleiniger Trigger oder Single Point of Failure sein.
GitHub-Cloudpfad bleibt als unabhängiger Fallback erhalten.

---

## 6. Echtgeld- und Execution-Grenze

Aktuell:
- keine neuen Echtgeld-Entries;
- keine V2R4-/V3-Automatik mit Echtgeld;
- keine Leverage-Erweiterung.

Spätere Trading-API:
- minimale Rechte;
- keine Withdrawal-Rechte;
- persistenter Kill-Switch;
- Startup-Reconciliation;
- stale-data rejection;
- Duplicate-/Size-/Price-Deviation-Gates;
- Order-Lifecycle-State-Machine;
- Circuit Breaker;
- echter E2E-Alarm-, Recovery- und Rollback-Nachweis.

Strategie-Evidenz und technische Execution-Sicherheit müssen **separat** bestanden sein.

---

## 7. Umgang mit neuen Erkenntnissen bis zur Mini-PC-Inbetriebnahme

Neue Auswertungen aus V2R3, Literatur, historischen Daten oder Fehlerfällen werden
weiter aufgenommen.

Aber:
- V2R3 bleibt unverändert;
- V2R4 darf vor Aktivierung dokumentiert verbessert werden, sofern Änderungen
  explizit versioniert bleiben;
- größere Research-Ideen gehen in die V3 Candidate Registry / Issue #7;
- keine Produktionslogik ändert sich automatisch;
- CRV/ICP und ähnliche bereits gesehene Fälle sind Discovery-Beispiele, keine
  unabhängige Holdout-Validierung.

---

## 8. Entscheidungsregel bei Unklarheit

Wenn künftig unklar ist, welche Version gemeint ist:

- **„laufende Strategie / aktueller Paper-Test“ = V2R3**
- **„schnellere Mini-PC-/WAIT-/Trigger-Variante“ = V2R4**
- **„neue Strategie aus Literatur, Backtests und Research“ = V3**

Diese Begriffe sollen künftig nicht mehr vermischt werden.


## 9. V3 Inheritance Policy — bewährte V2-Erkenntnisse vollständig überführen

Für die spätere V3-Konstruktion gilt verbindlich:

1. **Best-known V2 baseline**
   - Ausgangspunkt von V3 ist der letzte belastbare, dokumentierte Gesamtstand aus V2/V2R4.
   - Bewährte Entry-, Filter-, Kosten-, Risk-, Trigger-, Logging- und Recovery-Erkenntnisse werden nicht neu erfunden.

2. **Erkenntnisgewichtung**
   - Bereits prospektiv oder historisch belastbar bestätigte V2-Erkenntnisse erhalten höheres Anfangsvertrauen als neue, noch ungetestete V3-Hypothesen.
   - Reine Altlasten oder nur intuitive V2-Regeln erhalten keinen automatischen Schutz.

3. **Replace-by-evidence**
   - Ein V2-Baustein bleibt Default, bis eine neue Alternative ihn in sauberer Prüfung robust schlägt oder das Risiko materiell verbessert.
   - Ein neues Feature darf eine alte Regel ergänzen, bevor es sie ersetzt.

4. **V3 = Integration, nicht Parallelwelt**
   - V3 besteht am Ende aus dem besten Mix aus:
     - validierten V2/V2R4-Erkenntnissen,
     - neuen V3-Forschungsbausteinen,
     - Mini-PC-/Realtime-Erkenntnissen,
     - historischen Kraken-Tests,
     - prospektiven Shadow/Paper-Ergebnissen.
   - Ziel ist eine **einheitliche neue Strategie**, keine Sammlung unabhängiger Experimente.

5. **Migration Ledger**
   - Für jeden relevanten V2/V2R4-Baustein wird dokumentiert:
     - übernommen,
     - modifiziert,
     - ersetzt,
     - verworfen,
     - noch offen.
   - Jede Abweichung vom geerbten Stand braucht einen nachvollziehbaren Evidenzgrund.

6. **Keine Wissenslücke beim Versionswechsel**
   - Beim späteren V3-Release muss ein expliziter V2/V2R4→V3-Diff existieren.
   - Keine zuvor gewonnene relevante Erkenntnis darf allein deshalb verloren gehen, weil sie aus einem älteren Chat, Test oder Versionszweig stammt.
