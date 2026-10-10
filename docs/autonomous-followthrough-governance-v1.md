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


## 5. Verbindliche Gate→Ausführung→ACK-Nachkontrolle (10.10.2026)

**Fehlerfall:** Ein in Gesprächen zugesagter Meilenstein kann bereits in
`next_control_decisions` stehen, trotzdem erst dann beachtet werden, wenn
der Nutzer danach fragt. Eine Erinnerung, eine Issue-Meldung und eine
ordnungsgemäß gestartete Automations-Runde sind **keine erledigte Arbeit**.

Für jeden neuen materiellen Folgepunkt ist im selben Arbeitsvorgang der
eine bestehende kanonische Owner festzulegen, inklusive `trigger/due_at_utc`,
konkreter eigenständig erlaubter Folgehandlung, eventueller technischer
Abhängigkeiten, nachvollziehbarem Abschlussbeleg und eskalationsfähigem
Nutzer-Gate. Das bestehende tägliche Work (10:15 Europe/Berlin) **zieht
fällige Punkte aktiv** aus dem Current State und Backlog; eine fällige
Entscheidung wartet nicht auf ein neues Chat-Kommando. Ein bekanntes
Gate darf an die nächste reguläre Ausführung gebunden sein; versprochene
punktgenaue Starts sind nur dann korrekt, wenn ein entsprechend
tatsächlich installierter Auslöser existiert.

Für ausdrücklich zeitgebundene, folgenkritische Entscheidungen kann
`next_control_decisions` optional
`due_at_utc`, `followthrough_ack_key`, `followthrough_max_lag_hours`
tragen. Der **bestehende** `autonomous-project-milestones.yml`-Controller
prüft ohne neue Work-Ausführung, ob nach Ablauf der Nachfrist ein
nachprüfbares ACK fehlt. ACK liegt zentral in
`research/work-analysis-state.json#acknowledgements.control_decision_reviews`,
Schlüssel `followthrough_ack_key`; erlaubte Felder
`status: COMPLETED | DECISION_PACKET_READY | BLOCKED_WITH_ACTION`,
`completed_at_utc` (nicht vor `due_at_utc`),
`report` (wirklich vorhandener `research/work-analysis/*.md`-Bericht).
Das ACK wird **erst nach tatsächlicher Analyse/Übergabe** geschrieben;
eine Absichtserklärung gilt nicht. Fehlt es nach Nachfrist, entsteht
dedupliziert `CONTROL_FOLLOWTHROUGH_MISSED` in bestehendem Issue #38
und dem bisherigen Slack-Alarmweg, damit stille Hand-off-Verluste
sichtbar werden. Die Nachfrist ist ein Kontrollmechanismus, keine
künstliche Verlängerung der wirtschaftlichen Strategieprüfung.

**Entscheidungshierarchie:** autonom lesen → im genehmigten reversiblen
Scope erledigen → Nachweis/Ack schreiben → wenn gesonderte Strategie-,
Runtime-, Rechte-, Budget- oder Echtgeldfreigabe nötig ist, einen einzigen
konkreten Entscheidungsvorschlag mit Risiko und Rückweg vorlegen.
Blockiert ein Punkt, andere unabhängige Safe-Work-Punkte weiterführen;
kein mehrfaches Anfragen ohne neue Evidenz. Neue Work-/GitHub-/Mini-PC-
Schleifen und unkontrollierte Strategieaktivierungen bleiben verboten.

**Präzedenz:** Current-State ist nur deklarierte Strategie-Wahrheit,
Mini-PC/Supabase für Echtlauf/Evidenz; Controller-Receipt ist nicht
gleich wirtschaftlicher Trading-Erfolg. Der bestehende tägliche
Work-Lauf ist der Ausführungsowner; GitHub kontrolliert nur Liveness.
Neue Gesprächsinhalte können nur automatisch verwertet werden, wenn
sie bei einer autorisierten Ausführung tatsächlich persistiert wurden.

## 6. Projektweite Ausführung, nicht nur V2R4 (10.10.2026)

**Live in vorhandener Steuerung, keine zusätzliche Daueraufgabe:** 
`research/project-followthrough-routing-v1.json` bindet alle jeweils aktuell registrierten Ströme aus
`research/monitoring-evidence-routing-v1.json` sowie die querschnittlichen Bereiche Architektur,
Wissens-/Backlog-Übergabe, Resilienz, Kosten, physische MINI-PC-Gates, Strategie-Vererbung, Security
und Zustellung an ihre **bereits bestehenden** Owner/Trigger. Neue Ströme dürfen nicht ohne
Owner, nächstes Gate und sichere Übergabe als unbeaufsichtigt gelten. Die bestehenden CI-Gates
prüfen die dynamische Vollständigkeit, ohne einen neuen Scheduler oder Monitor zu starten.

`tools/project_followthrough_router.py` ist ein **read-only Phase-1-Einstieg**
für den bereits eingerichteten täglichen 10:15-Work-Lauf; der bestehende GitHub-Meilensteinlauf
kann dieselbe Route billig prüfen. Der Router erzeugt einen nachweisbaren Due-Entscheidungsplan aus
`project-current-state.json#next_control_decisions`, beurteilt vorhandene AKTUELLE ACKs und
verhindert falsche Abschlüsse ohne tatsächlich vorhandenen Bericht. Er setzt **keine**
Strategie-/Runtime-Änderung um, startet keine neue Task und nimmt keine Freigabe vor.
Für andere offene Punkte dient weiterhin `PROJECT_BACKLOG.md` als einziger Aufgabenbestand;
die 26+ Source/Monitoring-Strecken sind **Zuständigkeiten**, keine 26 neuen täglichen Prüfjobs.
Ein objektiv fälliges Gate soll bei der nächsten ohnehin stattfindenden Work-Runde vorgezogen werden.
Der 72h-V2R4-Gate erhält zusätzlich den vorhandenen einmaligen 20:43-Check, kein Dauerscheduler.

**Pflicht bei jeder neuen substanziellen Erkenntnis im tatsächlich autorisierten Chat/Work:**
Kanonischen Auftrag mit Owner/Trigger/zulässiger Aktion/Evidenz-/Abschlussbeleg im bestehenden Backlog,
Current-State-Gate oder Fachledger ablegen; beim nächsten bestehenden Work-Einstieg selbständig
weiterführen; Ergebnis wirklich ACKen bzw. Blocker und notwendige Nutzeraktion explizit dokumentieren.
Nur echte menschliche Release-Gates melden, keine routinemäßigen Info-Pushs.
GitHub kann **nicht** ohne gesonderte Integration alle privaten Gespräche automatisch auslesen,
unstrukturierte Alt-Backlog-Checkboxen eindeutig einem Fälligkeitszeitpunkt zuordnen oder
fremde Dienste am fehlenden Berechtigungs-Gate vorbei bedienen.

**E2E-Grenze:** Ein CI-grüner Router beweist globale Routing-Abdeckung,
nicht autonome Umsetzung jedes zukünftigen Fachschritts. Echte E2E-Erfolge erfordern jeweils
den belegten Work-/PR-/Merge-/ACK-/Gegenkontrollpfad. Erst danach darf dieser Arbeitszweig
als tatsächlich autonom erledigt gelten. Keine stillen H3/H6-Freigaben, kein Echtgeld.
