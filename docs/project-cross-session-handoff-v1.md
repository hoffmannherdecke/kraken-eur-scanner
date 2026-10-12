# Projektweiter Kontext- und Arbeits-Followthrough — Korrektur 12.10.2026

## Anspruch und Ursache

Der Nutzer hat am 10./11./12. Oktober **korrekt** ein allumfassendes, chatübergreifendes System gefordert: V2/V2R3/V2R4/V3/V4+, alle H-Bausteine, Quellen, Hardware, Cloud, Entwicklerarbeit, Risiken und laufende Aufgaben sollen die früheren Nutzerentscheidungen und tatsächlichen bereits installierten Komponenten kennen. Diese Erwartung wurde mit PR136–138 und PR162–163 **nicht in vollem Umfang eingelöst**. Dort existierten (a) Zuordnungs-/Aufgabenrouter und (b) ein optionaler Quellenabruf; aber kein flächendeckend verpflichtender Kontext-Review jedes neuen fachlichen GitHub-PRs. Der Router belegte nur das Vorhandensein einer Handoff-Anweisung. Ein CI-PASS belegt kein semantisches Lesen oder autonome E2E-Ausführung. GitHub kann fremde ChatGPT-Unterhaltungen und nicht verfügbare Work-Prompts nicht abrufen.

**Kein Formulierungsfehler des Nutzers.** Die Implementierung und teils die Abschlusskommunikation waren enger als der Auftrag.

## Architektur: bestehende Eigentümer, keine zweite Datenbank

- Deklarierte Versions-/Strategiewahrheit: `project-current-state.json` (as_of-Zeit nicht als automatische Frischegarantie behandeln).
- Operative aktuelle Wahrheit: bestätigtes Mini-PC-/Supabase-Live-Readback und unveränderliche Cloud-Evidenz; keine historische Momentaufnahme als live ausgeben.
- Historie/Entscheidungen: `docs/master-version-register.md`, `research/v3-migration-ledger.json`, V3 P0–P9/19-Lektionen und jeweilige eigentliche Evidenzquellen.
- Offene Arbeit: **nur** `PROJECT_BACKLOG.md`; nachweisbare Work-Entscheidungen `research/work-analysis-state.json`.
- Alle Querschnittsbereiche: die vorhandenen 26 Monitoringströme plus weitere Bereichs-Routen in `research/project-followthrough-routing-v1.json`.
- Source-Lookup: bestehendes `tools/context_before_action.py`, alle vier Scopes. Kein separater Datenmanager, kein neuer Hintergrunddienst.

## Verbindliche Pfade

**GitHub-PR, gleichgültig welcher Fachbereich:** Neuer kleiner PR-Guard `.github/workflows/project-context-change-gate.yml` wird für **jeden** PR gestartet, statt die große alte Control-Plane-Suite bei unwichtigen Dateien laufen zu lassen. Er ermittelt die tatsächlich geänderten Dateien, fordert die betroffenen vier Scopes auf und baut die aktuellen Quellenpakete. Die PR-Beschreibung enthält **einen** strukturierten `PROJECT_CONTEXT_REVIEW_V1`-Block mit Source-Fingerprints, aktuell gelesenen Originalquellen, wiederverwendeter Implementierung, Konflikten, Freigabegrenze, Evidenz und Abschluss. Fehlende, stumme oder veraltete Kontextübergabe fällt durch. Template per `python tools/project_context_change_guard.py --template --base HEAD^1 --head HEAD`. Ein validiertes Review beweist **nur strukturelle Konsistenz der Selbstauskunft**, weder semantische Wahrheit noch Tests/Laufzeit. Ein Reviewfeld ist keine Handelsfreigabe. Branch-Protection muss den neuen CI-Check als required markieren, damit Merges außerhalb des PR-Pfads nicht vorbeikommen; wenn administrativer Schutz nicht nachgewiesen ist, bleibt diese **Enforcement-Lücke offen**.

**Bestehender 10:15-Work-Lauf:** Bei jedem relevanten Gate zuerst `main` abrufen, vier Scopes für die konkret betroffene Arbeit wählen und den Quellenpaket-Builder auf dem echten Checkout ausführen bzw. relevante Originale anhand desselben Indexes aus GitHub lesen; gegen gespeicherte ACKs, Backlog und reale Runtime abgleichen. Keine fiktiven ACKs. Auch aktuell bereits bearbeitete Teilkomponenten nicht als neu zu bauen einstufen. Nur ein bestehender Work-Lauf und ein Folge-Owner.

**Bestehender 2h-Markt- und Quellenmanager:** Research-/Strategy-/Architecture-Kontext vor Source-Registry-PRs, aktives Quellenauswahl-Management nur mit Beleg/Scope und bestehendem Source-Owner; keinen neuen Poller und keine positive Kauf-Freigabe aus Forschung.

**Andere neue Chats:** Keine Plattformfunktion kann in diesem Repository garantieren, dass jede unbekannte ChatGPT-Unterhaltung automatisch eingelesen oder auf einen GitHub-Guard wartet. Verbindlicher Einstieg für jeden mit dem Repository befassten Agenten ist `AGENTS.md` und das Stichwort `KRYPTO-PROJEKTKONTEXT`. Dann aktuellen `main` mit passendem Scope über den GitHub-Connector abrufen; persönlicher Gesprächskontext kann ergänzen, ersetzt die Quellen nicht. Neu vereinbarte Erkenntnisse **im selben Vorgang** einem vorhandenen Fach-Owner kanonisch zuordnen, sonst bleibt Chatübernahme `UNVERIFIED`. Das ist der ehrliche technische Rand, kein unsichtbar funktionierendes Chat-Import-System.

## Nicht aufweichen

Der bestehende 28h-CANARY (festes Ende 13.10.2026 14:00:12 MESZ), V2R4-Paper, H1/H3/H6-Sperren, H5/H10/H11-Source-Provenienz, Modellbudget, Echtgeld und echte Cloud-Single-Writer-Autorität bleiben unverändert. Keine neuen Schedules, Hintergrundprozesse oder Mini-PC-Befehle. Keine blinden starren Wartezeiten: minimale echte Evidenz und Ack.

## Messbares E2E-Abnahmekriterium

1. Künstlicher neuer PR in einem nicht-V3-Bereich ohne Review wird durch den PR-Guard abgewiesen; mit falschem Source-Fingerprint ebenso.
2. Gültige PR mit wirklich dokumentierter Wiederverwendung und Conflict-Resolution erhält den PR-Gate-PASS, alte CI-Suites bleiben ungestört.
3. **Separat** nächsten tatsächlich ausgeführten 10:15-Work-Lauf und 2h-Quellen-Work-Lauf gegen aktuellen Scope, originale Quellen, echte Aktion und ACK überprüfen. Ohne diese Beobachtung NICHT `CROSS_SESSION_AUTONOMY_E2E_PASS` behaupten.
4. PR-Merges müssen nachweislich vom required branch protection Gate abhängig sein. Die bloße Existenz eines Workflows reicht nicht.
5. Unbekannte zukünftige Chats bleiben Plattformgrenze; nur wirklich gespeicherte Nutzerentscheidungen gelten als automatisch auffindbar. Keine behauptete passive Hintergrundüberwachung über Chats.

Dieses Verfahren gilt fachlich umfassend, kann aber weder KI-Semantik noch unbekannte private Chats technisch garantieren.
