# Dauerhafter autonomiegetriebener Projekt-Follow-through — sichere Ausführung v1

Beschluss 2026-10-08. **Dieser Vertrag ist keine installierte autonome KI-Coding-Instanz** und gibt GitHub Actions keine freien Schreib-/Handelsrechte. Ziel ist eine funktionierende **Übergabe** zwischen neuer Nutzer-/Audit-Erkenntnis, kanonischer Aufgabe, objektivem Fälligkeitsgate, automatischer Umsetzung *im bestehenden freigegebenen Work-Lauf* und überprüfbarem Abschluss. Operative Current-State-Wahrheit bleibt `project-current-state.json`.

## 1. Verbindlicher Umgang mit neuen Gesprächen und Findings

Jede neue **materielle** Nutzerentscheidung, Auditbeobachtung, Fehlerursache, offene Entwicklung oder neue Strategiefrage wird **im selben entsprechenden Arbeitsvorgang** kanonisch eingetragen (oder bei schon vorhandenem Eintrag eindeutig verlinkt): `PROJECT_BACKLOG.md` führt offene Arbeit; die jeweilige Fachdokumentation enthält technische Regeln; `research/v3-migration-ledger.json` verantwortet langfristige Strategievererbung. Nur eine kanonische Aufgabe pro Identität, keine weiteren verteilten To-do-Listen. Ein ausdrücklich abgelehnter/aufgeschobener Punkt bekommt ein begründetes `NO_ACTION` / `DEFERRED_WITH_GATE` statt stillen Verlusts. Das kann **nur für Inhalte garantiert werden, die ein autorisierter Chat-/Work-Prozess tatsächlich gesehen hat**; unbekannte Unterhaltungen werden nicht magisch von GitHub gelesen.

Ein neuer/noch offener Eintrag enthält mindestens: **Problem, erwünschter Nutzen, Eigentümer, erlaubter nächster Schritt, exakte Abhängigkeit, Daten-/Evidenzgate, was automatisch erlaubt ist, wie der Abschluss nachgewiesen wird, ggf. echter Nutzer-Entscheidungsbedarf**. Für die eng eingegrenzte **auto-ausführbare** Klasse liegt die maschinenlesbare Liste in `research/autonomous-implementation-queue-v1.json`; manuelle/strategische Arbeit bleibt im bestehenden Backlog, keine Konkurrenz.

## 2. Autonomie-Stufen

- **Stufe A — sofort selbstständig:** Lesen, Prüfen, Quellenqualität/Research-Routing, Dokumentations- und Konfigurationswidersprüche erkennen; einmalige eng begrenzte öffentliche API-Smokes; kanonische Docs/Backlog korrigieren; inaktives Experiment/Tests/Guard vorbereiten. Codeänderungen nur versioniert als kleiner Branch→PR→alle relevanten CI-Gates, mit rollbackfähiger Commit-Evidenz. Innerhalb klar genehmigten Forschungs-/Dokumentationsumfangs können grüne PRs wie bisher selbstständig übernommen werden.
- **Stufe B — technisch begrenzter Implementation-Pilot:** Der bestehende tägliche Work-Lauf macht erst den bisherigen **billigen** Phase-1-Gate. Ergänzend kann er **höchstens zwei** vom deterministischen `tools/select-autonomous-implementation.py` als `READY_SAFE_WORK` freigegebene kleine Aufgaben aus dem **einzigen** maschinenlesbaren Safe-Work-Katalog bearbeiten. Ist nichts fällig, endet Phase 1 unverändert; bei Fälligkeit ist das ein *separater* kleiner autorisierter Umsetzungsgrund, **kein neues schweres Strategieanalyse-Gate**. Höchstens **ein** offener Umsetzungspilot-Branch gleichzeitig; kein zweiter Work-Run, keine zusätzliche Task/Action, keine tiefe Markt-/Newsrecherche. Bestehende Meilenstein- und Quellenradar-Schedules bleiben unverändert.
- **Stufe C — weiterhin Freigabegrenze:** strategische Ein-/Ausstiege, H3/H6-Schattenstart oder Promotion, sonstige Runtime-/Scanner-/Policy-/Stop-/Sizing-/Echtgeldmodifikation, Secrets, neue Rechte, bezahlte Anbieter, destruktive Aktionen, Live-Trading benötigen vorher eigenständige Evidence-/Release-/Nutzerentscheidung. „Allgemeine Freigabe“ ist **keine** Aufhebung bestehender Sicherheitsgates.

## 3. Objektive Fälligkeit, Re-Entranz und Schutz vor Endlosschleifen

Kanonischer Scope der ersten Safe-Work-Klasse: (i) **H10 Outcome-Join-Vertrag vor Forschungsperformanceauswertung**, nur wenn H10-Erstreview dokumentiert und Vertrag noch nicht auf `main` existiert; (ii) fehlender Adapter für **neue** maschinenlesbare `next_control_decisions` im Current-State; (iii) Adapter für eine legitim erklärte neue aktive Shadow-Version. Gate-Prüfer liest **nur Git-gehaltene State-/Queue-/Dateievidenz**, keine Supabase- oder GitHub-API/Secrets. Bei Abweichungen `BLOCKED`, nicht nach Gefühl losprogrammieren. H10 ist ausdrücklich reine Research-Vorbereitung, **nicht** neue Tradingmechanik oder paralleler strategieändernder Shadow.

Der ausführende Work-Lauf muss pro tatsächlichem Versuch einen **identifizierbaren Artefakt-/PR-Abschluss** liefern oder eine eindeutige Blockade mit kleinster Folgehandlung in einem bestehenden Backlog-/Ack-Feld sichern. Bei Fehlern dürfen keine täglichen Neuversuche ohne geänderte Evidenz entstehen; nutze die bestehende `research/work-analysis-state.json` mit `autonomy_task_attempts` (Task-ID+Gate-Fingerprint+PR/Blocked/Completed). Ein `BLOCKED`-Fingerprint bleibt bis fachlich **neuer** Beleg vorliegt abgeschlossen. `README`-/Docs- oder PR-Plan ohne tatsächlich erforderlichen Code gilt nicht als fiktiver Runtimeerfolg. Nach erfolgreicher Änderung muss das zugehörige Gate geschlossen sein (z. B. angelegter H10-Vertrag oder unterstützte Adapter-ID), sonst ist die Arbeit unvollständig.

Entwicklungsarbeiten sind nicht auf feste 7-Tage-Wartefenster festgelegt: kleinster sinnvoller Test, echter CI-Gate, sofort zulässiger Folgeschritt. Bei fehlender Datenmaturität `WAIT_FOR_EVIDENCE`, kein Work-Spam. Andere unabhängige, erlaubte Safe-Work-Aufgaben dürfen den blocked Pfad überholen.

## 4. Wiederkehrende Verantwortungsprüfung ohne weitere Ressourcen

Der vorhandene GitHub `project-control-plane-guard.yml` prüft vor relevanten Merges `tools/select-autonomous-implementation.py`, maschinenlesbare Queue und negative Tests. Der bestehende GitHub-Meilensteincontroller meldet weiterhin **nur** belegte Readiness/Eskalation, programmiert selbst keine neue Strategie. Die bestehende tägliche Work-Automation liest den Safe-Gate-Schalter nur *kurz* und führt rein reversible kleine Arbeiten bei `READY_SAFE_WORK` selbstständig aus; alles andere (Scanner, Shadow, Paper, Quelle, Health, Supabase-Runtime) läuft weiterhin außerhalb Work.

Klar trennen:
`DISCOVERED→PERSISTED→READY_SAFE_WORK→SAFE_IMPLEMENTATION_PR→CI/REVIEW→MERGED+GATE_CLOSED` oder
`DISCOVERED→GATED_EVIDENCE_WAIT→NOT_EVALUABLE` bzw.
`DISCOVERED→USER_RELEASE_DECISION_PACKET→AUTHORIZED_CHANGE`.

**Kein Ghost-Executor:** Ein Repo-Vertrag oder eingeplanter Task beweist keine autonome Bearbeitung. Erst ein echter Work-Lauf mit selektiertem sicheren Gate und einem fertig gemergten PR/CI-Nachweis belegt, dass die neue Umsetzungsstrecke tatsächlich funktioniert. Der **erste unbeaufsichtigte** Safe-Work-E2E-Run ist gesondert nachzuweisen; bis dahin Status *IMPLEMENTATION_ROUTE_PREPARED / E2E_PENDING*.
