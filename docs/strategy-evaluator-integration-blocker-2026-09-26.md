# Strategieauswerter: Integrationsblocker

**Prüfzeit:** 2026-09-26 08:22:13 UTC  
**Status:** `STOPPED_EVALUATOR_NOT_WIRED`  
**Folge:** Gate 1 gestoppt. Gate 2 nicht begonnen. Kein Kandidat für einen End-to-End-Aufruf verwendet. Die reguläre Paper-Kandidatensammlung bleibt pausiert.

## Geprüfter Stand

Geprüft wurde `hoffmannherdecke/kraken-eur-scanner`, Commit `2860e4a26a4f2d2b0678264ba6365617500bfa36`.

- `market_data/evaluation_basis(...)` erstellt den gemeinsamen Kraken-Marktdaten-Input. Das ist ein Übergabeobjekt, kein Strategieauswerter.
- `market_data/compare_assessment_paths(...)` nimmt Auswerter als injizierte Callbacks entgegen. Ohne explizite Callbacks verwendet es zweimal `common_market_assessment`; diese Funktion liefert nur deskriptive Mikrostruktur-Labels und bildet keine bestehende V2- oder ALT-Entscheidung ab.
- `market_data/runtime.py` hält `LIVE_EVALUATION_ENABLED` und `REAL_MONEY_ACTIONS_ENABLED` fest auf `False`. Im Repository gibt es keinen produktiven Strategieauswerter und keinen konfigurierten Callback zu Work/ChatGPT.
- Im geprüften Commit existiert `docs/strategy-assessment-contract-v1.md` nicht. Der Code enthält zwar den gemeinsamen Datenumschlag, aber keinen versionierten Vertrag mit einem aufrufbaren Evaluator-Endpunkt.
- In ChatGPT Work existiert eine aktive stündliche Aufgabe „Aktien & Krypto Chancen – Stundencheck“; die Bewertungsregeln liegen im gespeicherten Prompt dieser Aufgabe sowie in den eingefrorenen V2-/ALT-Quelltexten des privaten Library-Testjournals. Die Aufgabe kann über die Automationsoberfläche einmalig mit ihrem gespeicherten Prompt gestartet werden. Diese Startfunktion nimmt aber kein Bewertungsobjekt als Eingabe entgegen und stellt keinen synchron abrufbaren Roh-Output mit Execution-ID für den Scanner bereit. Im GitHub-Scanner ist weder ein Work-Endpunkt noch eine Work-Berechtigung konfiguriert; auch ein Ledger-Append-Endpunkt ist dort nicht angeschlossen.

Damit kann kein belegbarer Pfad von Bewertungsobjekt über den echten bestehenden Auswerter bis zur persistierten Entscheidung hergestellt werden. Ein lokaler Callback, der simulierte Aufruf der ChatGPT-Entscheidung oder die deskriptive Funktion aus `parity.py` wären kein Nachweis und werden nicht als Ersatz verwendet.

## Präzisierung: tatsächlicher Speicherort und Aufrufbarkeit

Der „echte Strategieauswerter“ ist keine Funktion im Scanner-Repository. Die operative Entscheidungslogik liegt als Prompt im aktiven ChatGPT-Work-Stundencheck **„Aktien & Krypto Chancen – Stundencheck“**. Die eingefrorenen V2- und ALT-Regeln/Quellauszüge liegen im privaten Library-Testjournal **„Shadow-Paper-Test-2026-09-24.md“** und im Arbeitsstand **„Aktien-und-Krypto-Strategie-V2-Arbeitsstand-2026-09-24.md“**. Die Work-Aufgabe ist eine echte gespeicherte ChatGPT-Ausführung und kann über die Automationsoberfläche mit ihrem gespeicherten Prompt gestartet werden.

Diese Startmöglichkeit ist jedoch kein Kandidaten-Adapter: Der verfügbare Startaufruf akzeptiert nur die Aufgaben-ID, nicht das versionierte Bewertungsobjekt. Er bestätigt die Anforderung eines Laufs, liefert aber keinen synchron auslesbaren unveränderten Strategie-Output samt stabiler Execution-ID an den Scanner. Ein bloßes Starten würde zudem die gespeicherte Aufgabe mit ihrem eigenen Datenzugriff ausführen, nicht belegen, dass genau das übergebene Bewertungsobjekt geprüft wurde. Die Aufgabe wurde bei dieser Prüfung nicht gestartet; kein Kandidat wurde verwendet.

**Fehlende externe Komponente/Berechtigung:** Es fehlt eine von ChatGPT Work unterstützte, für den Scanner freigegebene Aufrufbrücke zur bestehenden Aufgabe: strukturierte Eingabe des unveränderten V1-Bewertungsobjekts, auslesbare Ausführungs-ID und unverändertes Ergebnisobjekt sowie autorisierter Append-Schreibpfad ins bestehende private Paper-Ledger. Im aktuellen Runner ist weder dieser Work-Endpunkt noch die nötige Work-Authentifizierung/Autorisierung vorhanden. Der bloße run_now-Start der Automation ersetzt diese Schnittstelle nicht.

## Konkrete fehlende Fähigkeit

Der kleinste fehlende Baustein ist **ein ausdrücklich freigegebener, aufrufbarer Adapter zum echten bestehenden Auswerter**, der:

1. das versionierte Bewertungsobjekt unverändert annimmt,
2. den bestehenden Work-/ChatGPT-Auswerter tatsächlich ausführt,
3. dessen unbearbeitetes Ergebnisobjekt samt Entscheidung, Begründung/Status und stabiler Ausführungs-ID zurückliefert,
4. Input und Output über Candidate-ID sowie Event-/Replay-ID eindeutig verknüpft,
5. den vollständigen Aufrufnachweis und beide unveränderten Objekte append-only im bestehenden privaten Paper-Ledger persistiert.

Dieser Baustein muss den vorhandenen Strategieauswerter aufrufen; er darf dessen Logik nicht nachbauen oder abändern. Bis diese Schnittstelle erreichbar und ein echter Aufruf samt Ledger-Schreibvorgang nachgewiesen ist, darf kein prospektiver Testkandidat aufgenommen werden.

## Lösbarkeit in Work/ChatGPT

**Mit der derzeit verfügbaren Umgebung: nein.** Der bestehende Strategieauswerter ist hier nicht als aufrufbares Tool oder API exponiert. Ein normaler Chat-Aufruf wäre manuell und lieferte keinen technischen Aufrufnachweis für die automatisierte Pipeline.

**Grundsätzlich: nur nach expliziter Bereitstellung einer solchen Callable-Schnittstelle.** ChatGPT-GPT-Aktionen können ein GPT mit externen APIs verbinden; das allein stellt jedoch keinen von einem Scanner auslösbaren API-Aufruf eines bestehenden Work-Auswerters bereit. Ein beliebiger Model-API-Aufruf wäre zudem nicht automatisch derselbe Auswerter. Vor Testfreigabe muss nachgewiesen werden, dass der Adapter den unveränderten bestehenden Auswerter ausführt und in das bestehende Ledger schreibt.

## Unverändert

V2, ALT, Bewertungslogik, Regeln, Schwellenwerte, Echtgeld-Sperre und Zeitpläne wurden nicht verändert. Es wurde kein Kandidat gesammelt, keine Entscheidung erzeugt und keine Paper- oder Echtgeldorder aktiviert.

## Nachweise

- [Gemeinsame Marktdatenschicht und expliziter Evaluator-Blocker](https://github.com/hoffmannherdecke/kraken-eur-scanner/blob/2860e4a26a4f2d2b0678264ba6365617500bfa36/market_data/README.md)
- [Paritätsfunktion mit injizierten Callbacks und deskriptivem Default](https://github.com/hoffmannherdecke/kraken-eur-scanner/blob/2860e4a26a4f2d2b0678264ba6365617500bfa36/market_data/parity.py)
- [Fest geschlossene Laufzeit-Gates](https://github.com/hoffmannherdecke/kraken-eur-scanner/blob/2860e4a26a4f2d2b0678264ba6365617500bfa36/market_data/runtime.py)
- [OpenAI: GPT-Aktionen konfigurieren](https://help.openai.com/en/articles/9442513-configuring-actions-in-gpts)
