# Kontrollierter Paper-Strategiewechsel V2R4 → V3 (Nutzerauftrag 11.10.2026)

Status: **V3-PAPER-ZIEL AUSDRÜCKLICH BEAUFTRAGT / ECHTE AKTIVIERUNG WEITERHIN GESPERRT**. Verbindlicher Übergabeindex **innerhalb** der bestehenden V3-P1-Owner-/Control-Plane, kein neuer Cron, keine Shadow-Instanz, kein zweites Paper-Ledger.

### Aktueller Wartungsstand – Korrektur vom 21.10.2026 (Vorrang vor dem historischen Wartungsplan unten)

**ABGESCHLOSSEN am 20.10.2026:** Die physische CPU-/BIOS-/Windows-Wartung des Dell OptiPlex 5060 Micro mit eingebautem Intel i7-8700T, geprüftem Boot/Temperaturverhalten, 32 GB RAM und kontrolliertem V2R4-/Runner-Wiederanlauf wurde auf dem Originalhost durchgeführt. Es gibt **keinen noch anstehenden CPU-/Windows-Wartungstermin** als V3-Paper-Blocker. Originalbelege: [Release-Owner #99 / Wartungsabschluss](https://github.com/hoffmannherdecke/kraken-eur-scanner/issues/99#issuecomment-6299462627) und [Projektmanager #353 / Originalhost-Wartung](https://github.com/hoffmannherdecke/kraken-eur-scanner/issues/353#issuecomment-6298293631). Alte unten stehende Anweisungen „vor dem Wartungstermin“, „Wartungs-Halt“ und der mögliche Termin 22.10. beschreiben die **überholte Planung**, nicht den aktuellen Wartungszustand. Der Read-only-Launcherstatus `BLOCKED_PENDING_MAINTENANCE_AND_ORIGINAL_RELEASE` ist zudem ein historisch benannter **statischer Software-Status**, kein neuer Beweis für offene Hardwarewartung.

**Davon getrennt weiterhin offen:** Die originalhost-seitige Abnahme der **seit dem physischen Stage `1cee8b7...` neu entwickelten, exakten V3-Release-Quellen** (späterer GitHub-Stand u. a. PR #507), unabhängig authentifizierter Task/PID/geladene Bytes/SYSTEM-Owner/Single-Writer-Lock, sechs genuine E2E-Release-Nachweise, gesondert autorisierter Cloud-CAS und abschließende ausdrücklich erteilte Nutzerfreigabe. Das ist **V3-spezifische Release-Integration**, keine erneute CPU-/Windows-Wartung. Historische Source-Staging- und PR419-STOP/Restore-Abnahmen bleiben anerkannt und dürfen nicht ohne konkrete neue Gründe wiederholt werden. USV-Anschluss und spätere Stromausfalltests sind kein V3-Paper-Gate.






#### Zeitbindung des unverbindlichen Host-/Cloud-Abgleichs

Der bestehende duale **Read-only-Preflight** prüft, bevor er den Relay aufruft,
den vom Original-Windows-Readback gemeldeten UTC-Zeitpunkt. Nach der Antwort
werden auch deren authentifizierter UTC-Zeitpunkt und die Konsistenz der
beiden Beobachtungen geprüft. Ein ungültiger, nicht zeitzonenbehafteter,
mehr als 180 Sekunden alter oder deutlich in der Zukunft liegender Befund
wird verworfen; die 10-Sekunden-Toleranz nach vorn betrifft nur diese
Diagnose und ist **keine** Lockerung der strengeren 90-Sekunden-
Originalhost-Prüfung vor einer echten Paper-Phase. Ohne Cloud-Serienwunsch
bleibt die bisherige reine Windows-Vorprüfung unverändert nutzbar.

Auch nach einer verzögerten Relay-Antwort werden **beide** bereits gelesenen
Originalhost-/Cloud-Zeitstempel erneut gegen denselben aktuellen UTC-Zeitpunkt
validiert; andernfalls könnte ein zunächst frischer Host-Befund während des
Netzwerkaufrufs unbemerkt veralten. Diese abschließende Prüfung bleibt rein
diagnostisch und startet keinen V3-Writer.

Diese Zeitprüfung ist **kein zusätzlicher Freigabenachweis**: Zeitliche
Übereinstimmung garantiert weder unterschriebene Prozessherkunft noch
Cloud-CAS/Sechs-Proof-Echtheit oder den abgeschlossenen Wartungstermin.
Die Antwort bleibt blockiert, alle produktiven Writer unverändert.

### Windows-One-Shot: vorhandenen Originalhost-Prüfer vor dem ECHTEN Release-Dispatcher verdrahtet (Source)

Im bestehenden Python-Launcher verbindet
`dispatch_from_original_windows_one_shot` die **schon vorhandene**
lesende Windows-PowerShell-Originalhostprüfung mit dem **einzigen**
`dispatch_after_originalhost_and_cloud_readback`-Pfad. Nur auf
`win32`, mit einem **separaten tatsächlich beglaubigten**
Originalhost-Release-Owner und einer tatsächlich laufenden, passenden
Task-/SYSTEM-Python-Parent-/Launcher-Datei-Identität darf diese
interne Funktion an die bestehenden Native-/Cloud-/Sechs-Proof-Gates
weiterdelegieren. Eine deaktivierte alte `--read-only`-Task,
abweichende Quell-SHA oder fehlender Release-Provider werden **vor**
der eigentlichen Phase zurückgewiesen. Der lesende Originalhost-Bericht
wird **niemals** in eine unabhängige Release-Freigabe umetikettiert.

**Ausdrückliche ausstehende Anbindung:** Der externe physische
Release-Owner muss den wirklich authentifizierten POST-CAS-
Task-/PID-/Loaded-Source-/No-Rearm-/Wartungsbeleg liefern; der
gegenwärtige Originalhost-Prüfer liefert absichtlich nur Hinweise.
Die neue Funktion ist deshalb **noch nicht als Windows-CLI-Start**
freigeschaltet oder physisch installiert und kann das Cloud-CAS oder
die finale Nutzerfreigabe nicht ersetzen. Keine zusätzliche
PowerShell-Funktion, neue Task oder Signaturbehörde entsteht durch
diese rein quellseitige Verdrahtung.

### Keine gemischten V3-Importquellen im künftigen nativen Windows-Start

Der bereits vorhandene native Launcher prüft **vor der Windows-Diagnose
und vor einer künftigen Cloud- oder Paper-Aktion**, ob die tatsächlich
importierten V3-Kernmodule (Candidate-Modell, selektive Paper-Phase,
Cloud-Receipt und ursprünglicher technischer Sechs-Proof-Gate) ihre
Python-Importursprünge innerhalb desselben isolierten Stage-Quellbaums
haben wie der aufrufende native Launcher. `__file__` und
`__spec__.origin` müssen auf genau die vorhandenen regulären,
nicht verlinkten Quell-Dateien zeigen. Ein veralteter oder aus einer
anderen Checkout-Version importierter Modulpfad führt **fail-closed**
zum Abbruch. Kein zweiter Import-Loader, Dateikopie, Runtime-Dienst
oder eigener Release-Owner.

Dieser Laufzeitcheck ergänzt den bei der Wartung schon vorgeschriebenen
vollständigen Transit-Import-/SHA-Pin-Abgleich der tatsächlichen
Release-Dateien. Er ist **nur ein lokaler Integritätsabgleich** der
Importpfade; weder `__file__` noch `__spec__` beweisen unabhängig,
welche Bytecode-Version wirklich ausgeführt wurde, und sie belegen
weder OS-Singleton, Originalhost-Freigabe noch Cloud-CAS. Die sechs
bereits beschlossenen echten technischen Belege, die physische
Wartung und die getrennte letzte Nutzerfreigabe bleiben unverändert.

### Gleiche native Windows-Prozessidentität beim unabhängigen Release-Befund

Die bereits existierende Originalhost-PowerShell-Diagnose berichtet nun zusätzlich
zur Task-Action und zum Launcher-Dateihash die **Python-Parent-Prozess-ID
und dessen OS-Startzeitpunkt**. Dieselbe PID wird unmittelbar im Originalhost
noch einmal über CIM samt tatsächlicher CreationDate, ausführbarer Datei
und Kommandozeile gelesen, bevor die Werte ausgegeben werden. Ein
zwischenzeitlich beendeter Prozess beziehungsweise eine wiederverwendete PID
liefert damit keinen positiven stabilen Prozesshinweis.

Die bestehende Windows→native One-Shot-Funktion fordert beim **später
unabhängig bestätigten** POST-CAS-Release-Owner dieselbe PID **und**
dieselbe OS-Erstellungszeit. Eine vertauschte, fehlende oder fehlerhafte
Identität blockiert vor dem nativen Paper-Worker. Der überarbeitete
lesende Hostbericht ist **kein** eigenständiger Beweis geladener Python-
Modulbytes, OS-Lock-Einzigkeit, Cloud-CAS oder der sechs E2E-Proofs.
Die unabhängige Prozess-/Freigabequelle muss nach Wartung weiterhin
eigenständig physisch abgenommen werden; keine neue Task, kein zweiter
Supervisor, kein Go-Live oder zusätzlicher Proof entsteht hier.

### Windows-Task- und unabhängigen Release-Owner auf identische Quellversion binden

Vor der Phase wird der vorhandene lokale lesende Windows-Befund nun am
**strengen tatsächlichen 90-Sekunden-Release-Zeitfenster** gemessen. Seine
bereits vorhandenen **Task-Action-SHA256** und **Launcher-Datei-SHA256**
müssen anschließend in der **separat zu erstellenden authentischen
POST-CAS-Originalhost-Release-Owner-Antwort** unverändert und exakt
wiederkehren; die beiden Beobachtungszeiten müssen höchstens 90 Sekunden
auseinanderliegen. Bei fehlendem, abweichendem oder veraltetem Nachweis
blockiert die bestehende Windows→native-Phase vor Paper-Arbeit.

Dies verhindert den unzulässigen Mix aus grüner lokaler Task-Diagnose
von Quellversion A und grünem Release-Owner-Report zu Quellversion B.
**Keine zusätzliche unabhängige Proof-Kategorie:** Die gleichen zwei
Quellfingerprints werden innerhalb des bisherigen
`V3_SINGLE_WRITER_FENCE_CLOUD_CAS_DRYRUN`-Original-Release-Belegs
gebunden. Task/Datei-Fingerprint und Zeitabgleich allein beweisen
weiterhin weder die *tatsächlich im Python-Prozess geladenen* Bytes
noch die Herkunft des externen Release-Owners. Letzterer bleibt nach
Wartung, CAS und sechs echten E2E-Belegen eigenständig nachzuweisen.
Diese Quelle ist noch nicht als aktive Windows-CLI installiert.

### Native Paper-Phase: Originalhost-Frische nach dem tatsächlichen Cloud-Readback

**Ausführungspfad, nicht nur Diagnose:** Die bereits vorhandene
`dispatch_after_originalhost_and_cloud_readback`-Funktion wird so
weitergebunden, dass der einmalig extern geprüfte Originalhost-Zeitstempel
auch **nach** dem einen authentifizierten Cloud-Relay-Abruf innerhalb des
vorhandenen nativen Writer-Locks erneut am tatsächlichen UTC-Zeitpunkt
geprüft wird. Altert die ursprüngliche Host-Freigabe dabei über **90 Sekunden**
oder liegt sie in der Zukunft, wird die Paper-Phase abgewiesen. Keine
zweite Cloud-Abfrage, kein zusätzlicher Task, kein Scheduler oder Manager.

Die Quellenänderung ist eine echte zusätzliche Laufzeit-Sperre in der
vorhandenen Phase-Funktion, aber **noch keine installierte oder freigegebene
Windows-Ausführungs-CLI**: Erst unabhängige Originalhost-/Task-/Source-Belege,
sechs echte E2E-Beweise, vollständig durchgeführte Wartung und Cloud-CAS
plus erneute Nutzerfreigabe erlauben den späteren produktiven Start.

### Original-Windows-Task-/Python-Quellenabgleich vor Cloud-One-Shot (weiterhin nur lesend)

Bei einem ausdrücklich angeforderten gekoppelten Windows-/Cloud-One-Shot-Befund
prüft der bestehende Launcher zusätzlich **vor** dem optionalen Relay-Aufruf,
ob die bereits vorhandene originale Windows-Diagnose eine laufende V3-Task,
einen einzelnen beobachteten SYSTEM-/Python-Parent mit zur Task-Aktion
passenden Argumenten, eine nicht mehr auf `--read-only` zeigende Aktion
und dieselben SHA256-Launcherdatei-Bytes wie beim aufrufenden Prozess meldet.
Eine fehlende, deaktivierte oder abweichende Task-/Prozess-/Quellbeobachtung
blockiert das kombinierte Ergebnis, bevor Cloud angesprochen wird. Ohne
ausdrücklichen V3-Cloud-Serienwunsch bleibt die vorhandene Host-only-Diagnose
auch beim deaktivierten V3-Vorbereitungsstand vollständig lesend nutzbar.

**Beweiskategorie ausschließlich Task-/Prozess-/Datei-HINWEIS:** Selbst alle
übereinstimmenden Felder beweisen weder tatsächlich geladenen Python-Code,
ausschließlichen OS-Lock-Writer, Native-Task-Freigabe noch Wartung,
Cloud-CAS, die sechs unabhängigen E2E-Proofs oder den finalen Nutzerbeschluss.
Keine neue Freigabestufe: die echte Originalhost-/Cloud-/Release-Abnahme im
bestehenden Owner #99 bleibt unverändert. Die Task-Aktion wird nicht verändert.

### Originalhost + Cloud: eine rein lesende One-Shot-Vorprüfung

Zusätzlich zum bisherigen `--one-shot-preflight` kann der **gleiche** Launcher jetzt optional
`--one-shot-preflight --proposed-v3-series PAPER-V3-YYYYMMDDTHHMMSSZ`
prüfen. Dabei werden zuerst die vorhandenen **Original-Windows-Hostinformationen**
gelesen und danach ausschließlich der **bereits bestehende authentifizierte
`read_active_paper_series`-Abruf** im einen Edge-Relay aufgerufen. Ein vorhandener
Relay-Schlüssel wird nur aus `V3_PAPER_RELAY_TOKEN` im Prozess-Environment gelesen
(nie aus CLI-Argumenten, niemals im Ergebnis). Die Cloud-`config` und
Zugangsdaten werden nicht ausgegeben.

Fehlt der Schlüssel, ist die Serie unbekannt, nicht aktiv, falsch zugeordnet
oder der Relay unerreichbar, **scheitert die Prüfung**; keine künstlichen
Cloud-Erfolge. Ein positives Remote-Readback ist **nur eine Beobachtung**
und weder echter CAS-Provenienzbeleg noch Windows-PID-/Originalhost-Echtheit,
Wartungs-ACK oder sechs originale technische Releasebelege.
Das Ausgabeobjekt bleibt ausnahmslos
`BLOCKED_PENDING_MAINTENANCE_AND_ORIGINAL_RELEASE` mit
`cloud_cas_independently_proven=false`. Es wird **kein** Windows-Task gestartet,
kein neuer Laufplan installiert, kein Writer ausgeführt und keine
Cloud-Schreibaktion, Modellanforderung oder Paper-Order initiiert.
Die physische Windows-Installation bleibt getrennt und für den vorgesehenen
CPU-/Windows-/Skript-Abnahme reserviert; USV ist optional und ausdrücklich bis zur aktiven Nutzermeldung zurückgestellt.

### Windows-One-Shot-Vorprüfung vor Wartung (ausführbar, streng lesend)

Der **bestehende** Launcher `paper_evaluator/v3_paper_minipc_native_launcher_v1.py` bietet ab diesem Quellenstand den zusätzlichen Modus `--one-shot-preflight`. Er ruft **einmalig** das vorhandene, unveränderte `tools/check-minipc-v3-physical-writer-readiness.ps1` auf dem Original-Windows-Host auf, mit einem **nur für diesen PowerShell-Kindprozess** geltenden `-ExecutionPolicy Bypass`, weil die tatsächliche Windows-Richtlinie das direkte Ausführen von Skripten bereits blockierte. Das ändert weder Windows-Richtlinie noch Task/Supervisor noch V2R4.

Das Ergebnis `V3_NATIVE_WINDOWS_ONE_SHOT_PREFLIGHT_V1` ist stets `BLOCKED_PENDING_MAINTENANCE_AND_ORIGINAL_RELEASE`: Native Task/Prozesshinweise und die bestehenden drei Paper-Phasen werden zwar lesend angezeigt, aber es gibt **keinen** Freigabe-, Modell-, Cloud-, Writer- oder Orderaufruf. Fehler beim Originalhost-Readback werden weitergegeben, nicht durch künstlichen Erfolg verdeckt. Ein neuer ausführbarer Produktiv-CLI-Pfad wird dadurch **nicht** behauptet: Die bestehende zukünftige Funktion `dispatch_after_originalhost_and_cloud_readback` bleibt der alleinige native Phase-Dispatcher und benötigt weiterhin originale, unabhängige Task/PID-/Wartungs-/Cloud-CAS-/Sechs-Proof-Autorität. Das zuerst kommende Wartungsfenster und die ausdrückliche letzte Nutzerfreigabe bleiben verbindlich. Der aktuell physisch bereitgestellte 69-Dateien-Stage (16e270...) wird **nicht** stillschweigend auf diesen Quellstand aktualisiert oder umgepinnt; neues Staging nur im bereits geplanten Wartungs-/Releaseablauf.

### 20.–22.10.2026: Gesamtprojekt-Vorbereitung, kein Fake-Go-live

Für den eventuell am **Donnerstag, 22.10.** möglichen Wartungstermin
hat der Nutzer ausdrücklich die schnellstmögliche Vorbereitung der
gesamten V3-Paper-Technik angeordnet. Die einzige Ausführungsordnung
und der Wartungs-Halt unten bleiben bestehen. Deshalb vor dem Termin
den ursprünglichen technischen Release-Gate-Owner #99 und den
projektweiten Kontext #353 konsolidieren, reale vorhandene und
tatsächlich offene Originale trennen; **nicht** mit weiteren
isolierten Source-/Fingerprint-PRs den produktiven Start suggerieren.

Die ursprüngliche technische Gate-Funktion
`assess_v3_native_source_import_closure` ermittelt statische
transitive lokale Python-Imports und ihre SHA in derselben
bestehenden `tools/v3_experimental_paper_technical_gate.py`,
in der schon das V3-Policy-Bundle inventarisiert wurde. Die Prüfung
ist **nur** ein vorziehbarer Stage-/Source-Abnahmeinput, weder
echte Loaded-Bytes-Provenienz noch eigenständige siebte Probe.
Externe/dynamische Imports, Windows-Task-/Prozessidentität,
Originalhost-E2E, Cloud CAS und die finale Nutzerentscheidung
bleiben beim einzigen tatsächlichen Release-Owner.

**Spätere verbindliche Nutzerkorrektur 20.10.2026:** Der UPS01LCD/USV-Anschluss ist eine optionale Resilienzverbesserung, **keine** V3-Strategie-/Paper-Freigabevoraussetzung. Die einzelne originale USV-Pflichtprüfung im nativen Launcher wird entfernt und gesondert regressionsgetestet; alle übrigen echten CPU-/Windows-/Skript-/V2R4-Restart-/Single-Writer-/Sechs-Proof-/Cloud-CAS-/Rollback- und Nutzerfreigabe-Gates gelten unverändert. Keine falschen positiven USV-Nachweise. Alte USV-Pflichtpassagen in historischen PR-/Checklistenbeschreibungen sind dadurch überholt.

## 20.10.2026 – verbindlicher Wartungs-Halt VOR dem letzten V3-Paper-Go-live-Schritt

**Neue ausdrückliche Nutzerentscheidung:** V3-Codeentwicklung, isolierte GitHub-/Mini-PC-Quellenprüfungen, vorbereitende Tests und Review dürfen bis zur letzten produktiven Paper-Umschaltung weiterlaufen. **Bevor** jedoch der endgültige V3-Paper-Cutover (produktiv wirksames Cloud-CAS, Umstellen/Aktivieren der Windows-Task, Stilllegen der alten V2R4-Neuaufnahme) freigegeben oder ausgelöst wird, **STOPP**: den bereits vorgesehenen Wartungstermin am Dell OptiPlex 5060 Micro durchführen und die noch ausstehenden Skriptversionen einschließlich PR #444 auf dem **Originalhost** übernehmen und tatsächlich abnehmen. Der Nutzer gibt nach dem Wartungs-Readback die finale V3-Paper-Aktivierung getrennt frei. Kein Automatismus und kein zusätzlicher Manager, Scheduler oder siebter unabhängiger V3-Technikbeweis. Die Wartungs-/Originalhost-ACKs werden in die **bestehenden** Proofs `V3_MINIPC_SUPERVISOR_STOP_START_ROLLBACK` (Reboot/Recovery/Fence) und `V3_SINGLE_WRITER_FENCE_CLOUD_CAS_DRYRUN` (gepinntes Writer-/Task-/Quellen-Release) integriert.

**Ausführungsreihenfolge im EINEN bestehenden Wartungsfenster – thematische Checkliste ist nicht die Startreihenfolge:**

1. Vorab: aktuellen GitHub-/Mini-PC-/Cloud-Zustand, tatsächlich laufende V2R4-Tasks, Quellenpins, Original-Windows-Task-Backups, Backup-/Recovery-Voraussetzungen prüfen, bereits echte Wartungs-ACKs verwenden und nur erforderliche Eingriffe terminieren. Die optionale USV ist keine Voraussetzung. Bereits abgenommene PR419 STOP/RESTORE-Drills nicht unnötig wiederholen.
2. Kontolliert **nur für Wartung** Scanner, Runner, V2R4-Lese-/Schreibprozesse und Autostarts/Watchdogs anhalten; Originalserien- und Journalzustand, quiescent PID-Familien und sichere Wiederanlaufmöglichkeit prüfen. **Kein V2R4→V3-CAS** und kein stillschweigender Strategie-Cutover beim Stop für Wartung.
3. Erst danach Windows regulär herunterfahren, stromlos machen und erforderlichen BIOS-Stand vor dem CPU-Wechsel kontrollieren; Intel i7-8700T einbauen, Boot-/Temperatur-/Stabilitätstest durchführen. Im BIOS **AC Power Recovery / Power On** als bevorzugte Wiederanlaufoption prüfen und nur nach Bestätigung setzen; während eines bewusst durchgeführten Wartungs-Shutdowns keinen irrtümlichen Neustart auslösen.
4. Gezielte Windows-11- und Treiber-Updates mit kontrollierten Neustarts abschließen; aktuelle Windows-Updatepause (ursprünglich bis 31.10.2026) anschließend überprüfen und bedarfsgerecht entfernen/anpassen.
5. **Optionale USV: `OPEN_DEFERRED_AWAIT_USER_TRIGGER`.** Keine Installation, Stromausfall- oder Wiederanlaufprobe und kein USV-ACK als Bedingung für Entwicklung, Wartungsabschluss oder experimentellen V3-Paper-Release. Nur wenn der Nutzer Lieferung und Anschlussbereitschaft meldet, im vorhandenen separaten Wartungsrunbook prüfen; bis dahin keine Erinnerung und kein vorgetäuschter USV-Schutz.
6. Ausstehende genehmigte Skriptversion, insbesondere PR #444, kontrolliert auf den Originalhost übernehmen; Source/Action/Originalprozess/Autostart-/No-Rearm-Fingerprints und `SYSTEM`/Rechte, Supervisor, Recovery und CPU-Optimierung im V3-Gesamtkontext abnehmen. Originale Version und Rollback bewahren.
7. **V2R4 zunächst kontrolliert wiederherstellen** und den vorherigen aktiven Paper-/Cloud-/Nachlaufstatus unabhängig prüfen. Nicht denselben Wartungsstop als späteren produktiven V3-Cutover werten; keine Alt-Followups/Exits löschen.
8. Erst danach: tatsächlich verifizierten Wartungs- und Skript-Originalhost-ACK mit finalem gepinnten V3-Quell-SHA in den **bestehenden** technischen Freigabebelegen referenzieren. Separate ausstehende sechs echte E2E-Prüfungen, native One-Shot-Task/PID, Cloud-CAS, Budget und ausdrückliche Paper-Freigabe bleiben verpflichtend. Erst nach positiver vollständiger Abnahme darf der eigentliche V3-Cutover separat beginnen.

**Schutz im bestehenden nativen Launcher:** `dispatch_after_native_release_readback` verweigert einen produktiven Paper-Phasenaufruf ohne plausiblen Originalhost-Wartungs-ACK (CPU/BIOS/Boot/Temperatur, Windows/Treiber/Neustarts, tatsächlich übernommene Skripte/Quellen, vollständiger Wiederanlauf von V2R4/Aftercare), exakte Release-SHA und zeitliche Konsistenz. Das validiert **nur einen Bericht**; die unabhängige Echtheit des physischen Receipts und die sechs echten Proofs müssen der vorhandene Release-Owner separat nachweisen. Keine neue CLI-Freigabe, keine Änderung am deaktivierten V3-Task, keine automatische Cloud-CAS-Installation. Bei fehlendem ACK: `BLOCKED_MAINTENANCE_PENDING`, vorhandene V2R4 bleibt die Paper-Strategie.

## 0. Aktuelle und historische Autorität

- **Frische read-only DB-Abfrage vom 11.10. ca. 07:39 UTC:** Supabase `public.paper_series` genau eine aktive Serie `PAPER-V2R4-20261009T110135Z`, unveränderte Revision `V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION`, 823 neue Kandidaten, historischer erster V2R4-Abschnitt 1.011 Kandidaten, zusammen 1.834, 0 V2R4 Paper-Trades. `minipc_status_current` zuletzt HEALTHY 07:34:26 UTC. Die neue Serie hatte 469 vollständige 24h-Followups bei 469 fälligen, aber noch kein eigenes Fasttrack-Abschlussgate. **Snapshots altern; vor jedem operativen Schritt frisch prüfen.**
- `project-current-state.json.active_strategy` bleibt die absichtlich originale **V2R4-Strategie-/H3-Linie** (technische operative Teilserie dort nur datiert). `project-current-state.json.pending_strategy_transition` = genehmigtes ZIEL, kein Echtzeitstatus.
- V2R4 ursprünglicher 72h Wirtschaftsreview wurde bereits am 10.10. geschlossen: 0 BUYs/0 Trades, nicht durch bloße technische Gesundheit widerlegt. **Nicht auf erneute 1.000 Kandidaten warten**, wenn das wirtschaftliche Ergebnis die Nachfolgeentscheidung bereits rechtfertigt.
- V3 ist aus PR #159/#161/#165/#166 eine **Forschungsarchitektur**: `paper_evaluator/v3_second_leg_policy_candidate_v1.py` erzeugt nur eine unprivilegierte *Eignung zur späteren vollständigen Nachprüfung*; kein eigenständiger V3-Entry-Evaluator, Paper-Writer, vollständiger prüfbarer Stop+Stage2-Kauf, Prospektiv-Shadow oder V3 Paper-Release. PR merge / vorliegende Strategiedokumente sind KEINE Aktivierung.

## 1. Nicht überspringbare Phasen mit genau einem Owner

**Priorität für den ersten V3-Paper-Wechsel (Ziel 13.10. abends / 14.10.):** Die tatsächlich implementierte Ausnahme `tools/strategy_successor_gate.py` → `tools/v3_experimental_paper_technical_gate.py` gilt NUR für die begrenzte experimentelle Paper-Phase. Ihr braucht **keinen profitablen Vorab-BUY, keine künstlichen weiteren Shadow-Wochen und keine vorab gereiften Paper-24h-Nettoergebnisse**, aber sehr wohl den einen originalen FULL-Modell→P4-Pfad und sechs **echte** einzelne physische/Cloud-Techniknachweise samt hashes, limitiertem Modellbudget, physischem Single-Writer-Trockenlauf, sicherem V2R4-Stopp/Recovery und expliziter Freigabe. **B in der Tabelle ist für die spätere ökonomische Promotion und darf den experimentellen Start nicht blockieren.** Eine *bestehende* 28h-Beobachtung darf nur nach realem Ende und physischen Stop-/Pin-ACK als abgeschlossen gelten; bis dahin Vorbereitung ohne Host-Veränderung. Derzeit sind die sechs echten Beweise NICHT als vollständig verifiziert, V3-Paper weiterhin inaktiv.


| Schritt | Owner | Abnahmebeleg | Operative Wirkung |
|---|---|---|---|
| **A: V3-Kern fertigstellen, jetzt** | Bestehendes `PROJECT_BACKLOG.md P1/MINIPC_ANALYTICS_ROLLOUT_V1`, V3 PR161 P0/P1 | Separat versionierter, INAKTIVER vollständiger V3-B-Full-Review: neuer PIT geschlossener 1m/5m/15m OHLC/Volume/ATR/Stopstruktur Input → eigener V3-Entscheidungsweg → Kraken Spot EUR, frischer Ask/Spread, gültiger Stop unter Ask, Stage2 > Ask, Netto nach 0,6 % pro Seite + Slippage. Unit/Nega/Offline-Positive Tests, keine alten 24h-Labels im Prompt, kein Copy-Paste von Eligibility=BUY. **Kein echter Modellcall ohne neues Budget-Gate.** | V2R4 unverändert, V3 weiterhin **nicht** aktiv |
| **B: Wirtschaftliche Nachfolger-Promotion (nach erstem experimentellem Paper)** | Bestehender `research/strategy-learning-causal-gate-v1.json` + `tools/strategy_successor_gate.py` | Prospektiver gematchter Kandidat/Pair/Clock/Fingerprint-V2R4-Kontrollarm gegen **genau EINEN** V3-Policy-Unterschied, gestempeltes 6h/24h-Outcome/False-BUY/Correct-REJECT, **mindestens ein echt risiko-/kosten-validierbarer BUY**, valide Paper-Fill/Stop/Stage2-Simulation, fünf individuelle Release-Artefakte `VERIFIED_PIT_E2E_PASS`. Negative Evidenz → STOP/REWORK, nicht fiktiver PASS. **Dies ist KEINE Vorbedingung für den ersten `EXPERIMENTAL_PAPER_ONLY`-Start.** | Erst nach echter experimenteller Paper-Evidenz die wirtschaftliche Strategie-Promotion, kein zweiter Writer |
| **C: Freigabe / operativer Cutover** | Bestehendes Release-/Mini-PC-/Supabase-Owner-Gate | Release-Evidence `research/successor-strategy-release-evidence-v1.json` nach echtem Gate, exakt gepinnte Code+Strategie-SHA, Paper-only, Single Writer, safe Stop/Start, Mini-PC-Verifikation, gleichzeitige Cloud-Linie. Krypto-Modellbudget ggf. gesondert freigeben. **Erst hier alte Neuaufnahme tatsächlich stoppen.** | V2R4 intake OFF **physisch** (nicht bloß Supabase-Status), V3 eine einzige neue aktive Paper-Serie |
| **D: Nachlauf und Abschluss** | Bestehender 10:15-Work Owner/Control Plane | Alte V2R4 Pending-/offene Paper-Fills, STOP/TTL und 6h/24h Followups zum ursprünglichen Trade/Serie fortführen und historisch korrekt als COMPLETE, OPEN oder CENSORED quittieren; Quarantäne falls fehlende Wiederherstellung. Neue V3 echte Prospektiventscheidung, Paper-End-to-End, Watchdog+Scanner+Slack/Cloud-ACK. `project-current-state.json`, Release-Register, `research/v3-migration-ledger.json`, `research/work-analysis-state.json` sowie Work-Prompts **erst mit echten Belegen** auf V3-AKTIV ändern. | Erst dann `V3_PAPER_ACTIVE_VERIFIED`, nie aus PR/CI allein |

## 1aa. P0 Früh-Erkennung muss vor V3-Paper physisch bis zur Modellentscheidung reichen (Nutzerentscheidung 18.10.)

**Release-kritische Bedingung im bestehenden #99 / V3_EXPERIMENTAL_PAPER_SIX_PROOFS, kein neuer Scheduler oder siebtes Gate.** Ein schneller WebSocket-Shadow allein genügt nicht: `public.v2r4_shadow_evidence` enthält 25.692 originale Events 01.–18.10.2026, p50 Feed→Shadow 1,721 s, p90 2,953 s, p99 3,963 s. In den letzten 7 Tagen: 14.342 Ereignisse/463 Paare, 2.693 `would_request_fresh_recheck=true`, aber `fresh_recheck_invoked=true` in **0** Fällen. Dies ist korrekt, solange Shadow `SHADOW_OBSERVE_ONLY` bleibt, **beweist aber noch nicht** den schnellen produktiven V3-Modellpfad. 116 Event-Snapshots zeigten bereits ret10m≥5 %, 31 ≥10 %; wiederholte Events ≠ einzigartige Kaufchancen. Nur 2.693 Events in `STANDARD_EXECUTION_GATE`, 11.649 in `WATCH_ONLY` ohne verifizierte Tiefe. `scanner_detection_evidence` letzter Stand 06.10., nicht als 18.10.-Baseline ausgeben.

**Muss im vorhandenen Release-Proof `V3_JOURNAL_REASONS_ERRORS_6H24H_FOLLOWUP_CENSURE` plus `V3_MINIPC_SUPERVISOR_STOP_START_ROLLBACK` mit Original-Mini-PC/Cloud-Belegen sichtbar sein:**
1. Feed-Eingang `source_pair_received_at`, Erstsignal, originäre Candidate-ID und `known_at` → bestehender *einziger* V3-Candidate-/PIT-Entry-Consumer → frische Coin-1m/5m/15m-/ATR-/Stop-Features → Full-Model/P4-Entscheid (BUY/WAIT/REJECT/UNKNOWN). Latenzen getrennt messen: Marktbewegungsbeginn→Signal (nur falls kausal beobachtet), Feed→Shadow, Shadow→V3-Eligibility, Eligibility→Modellantwort, Modell→P4/Journal. Kein alter 15-/30m-Poll darf den ersten zulässigen V3-Eingang unbemerkt verzögern. Fehlende Originale bleiben `UNKNOWN`, nicht 0s.
2. Über mehrere aufeinanderfolgende reale Live-Ticks mit echter Unterbrechung/Recovery prüfen: Feed-/Pair-Abdeckung, Dedupe, Replay/Restart, Quellenalter, 1m-/5m-Closed-Bar-Zeit, zulässige Trigger und echte WAIT-TTL-Ticks. Bei Gap keine Nachfüllung historischer Kerzen als prospektives Capture. Nur ein Writer, keine Shadow-Modellaufrufe, keine zusätzlichen API-Kosten. Negative Regression muss ein simuliertes `early_signal_seen` ohne originale V3-Consumer-/Model-/Cloud-ACKs als **BLOCKED** behandeln.
3. **Wirtschaftlicher Vergleich**, nach tatsächlicher V3-Paper-Freigabe unter `V3_PAPER_NET_ECONOMIC_REVIEW`: nach Pair+Zeit-Episode entdoppelte **alle** Signale (auch Fehlsignale), erste verfügbare V2R4-/15/30m-Sichtung vs frühester V3-PIT-Entscheid, WAIT-Rechecks und echte Modell-/P4-BUYs; plausible Kraken-EUR-Ask-/Spread-/Tiefe-/Stop-/Stage2-Fills, 0,60 % Taker je Seite + Slippage, 6h/24h/72h Nachlauf. Kennzahlen `median/p90 movement-to-decision delay`, `additional eligible episodes/week`, `additional independently justified BUY/week`, `false-BUY and net outcomes`. Retrospektives MFE von 10–20 % darf niemals als sicherer BUY oder Gewinn bezeichnet werden. Wenn echte V3-BUY-/Exitpfade fehlen: `NOT_EVALUABLE`, **nicht** `PASS` und **nicht** `0 zusätzliche profitable Trades`.
4. Die existierende frühe 5m-CONTINUITY-Forschung (`paper_evaluator/v3_p3_early_5m_continuity_research_v1.py`) **nur als isolierten Vergleich** zur 15m-Regel prüfen, nicht heimlich in die aktive/frozen V2R4 oder V3-Baseline übernehmen. Falls schnellere Feed-Ereignisse weiter 0 echte Modell-BUYs ergeben, Entscheidungs-/Feature-/WAIT-Engpass als separaten Fehler identifizieren; nicht allein die WebSocket-Geschwindigkeit feiern.

**Status am 18.10.:** Original-Feed→Shadow-Latenz belegt, durchgehender V3-Feed→Full-Model/P4→Cloud-ACK **NICHT** belegt; kein aktives V3 Paper, kein behaupteter Netto-Trade-Erfolg. Vor Freigabe technische E2E-/Recovery-/Negativprobe erforderlich; nach Start wirtschaftliche Maturity ohne künstliches 72h-Vorstart-Warten. Dieser Abschnitt ergänzt ausschließlich die bestehenden sechs Proofs und den vorhandenen wirtschaftlichen Folgeowner.

## 1a. Verbindliche vollständige V2R4-Lernpfadübernahme: V3 WAIT + No-BUY + 6h/24h/72h (Nutzerentscheidung 18.10.)

**Pflicht bei jeder V3-Paper-Abnahme, kein weiteres siebtes Gate.** Der Nutzer hat ausdrücklich verlangt, dass die bereits in V2R4 eingeführte WAIT-/Trigger-Nachverfolgung und die nachträgliche Auswertung auch **nicht gekaufter** Kandidaten vollständig, nicht nur deklarativ, in V3 eingehen. Dies wird im vorhandenen dritten der sechs technischen Belege `V3_JOURNAL_REASONS_ERRORS_6H24H_FOLLOWUP_CENSURE` und in `tools/v3_experimental_paper_technical_gate.py` geprüft; einziger Release-Owner [#99](https://github.com/hoffmannherdecke/kraken-eur-scanner/issues/99#issuecomment-6246230916). Bestehende Module und Scheduler/Single-Writer wiederverwenden, keine neue WAIT-Instanz, keinen zusätzlichen Cloud-Collector/Work-Lauf oder API-Kostenpfad.

**Originaler Fehlerhinweis:** Der TIA/EUR-Canary vom 16.10.2026 hatte eine tatsächlich gesicherte `WAIT_RECHECK: WAIT`-Quittung, aber `WAIT_EXPIRY: UNKNOWN_DID_NOT_CAPTURE_COMPLETE_TTL_NO_NEGATIVE_INFERENCE`. Die Kennzeichnung ist korrekt **fail-closed**, beweist aber gerade **keine** durchgehende Beobachtung der gesamten Modell-TTL. Nie zu `NO_TRIGGER`, `REJECT`, richtig vermiedenem Verlust oder verpasstem sicherem Gewinn umdeuten.

**Innerhalb der bestehenden technischen V3-Freigabe vor Cutover tatsächlich nachzuweisen:** Original-Kandidat und Full-Modell/P4-`WAIT`, originale geschlossene frische Kraken-EUR-5m-Kerzen mit zeitkorrekten, wiederholten WAIT-Ticks über den vorhandenen *einen* Native-Owner, korrekte fristbezogene Trigger-Recheck-Berechtigung (ohne automatischen Modellkauf), `UNKNOWN` bei verspäteten/fehlenden Ticks, sowie Weitergabe von BUY und allen NO-BUY (`WAIT/REJECT/SKIP/UNKNOWN`) an die **bestehenden** prospektiven 1m-Kraken-Pfad- und 6h/24h/72h-Followup-Module. Identität `candidate_id/series_id/pair/event_time` und eigene originale Missingness-ACKs behalten. Kein rückdatiertes Kraken-Backfill, PnL oder späteres MFE/MAE im Entscheidungsmodell. Laufzeit-/Pfadprüfung und originaler Mini-PC-Receipt müssen gegen denselben Kandidaten und Serie im unabhängig gelesenen Supabase-/Cloud-Journal nachvollziehbar sein. Das veröffentlichte technische Proof-Schema verlangt jetzt beide unabhängigen Herkunftsrollen und die expliziten WAIT-/No-BUY-/Altfolgen-Prüfpunkte. **Hash-konsistentes Fixture, GitHub-CI oder selbstgesetztes `true` ist ohne originäre Host-/Cloud-Verifikation kein PASS.**

**Pre-Release darf nicht künstlich 72h echten wirtschaftlichen Ausgang verlangen:** Technische Vollständigkeit der bestehenden Beobachtungs-/Wiederanlauf- und Nachlaufkette samt Negativfällen vor Freigabe testen, kein erfundener Maturity-PASS. Nach dem echten V3-Start bei tatsächlicher Fälligkeit den kandidatengebundenen 6h-, 24h- und 72h-Pfad mit `MATURE_COMPLETE` oder bei nicht reparabler Originalquellenlücke `CENSORED` quittieren; davor `PENDING`/offenen Recovery-Status erhalten. **CENSORED ist kein 0-PnL, und No-BUY-MFE ist kein erzielter Gewinn.** Wenn originale Intervalle/Cloud-Sync/Paper-Lifecycle fehlen, Status `OPEN/BLOCKED` und konkrete einzelne Abhilfe im vorhandenen Owner, niemals `V3_PAPER_ACTIVE_VERIFIED` oder Profitabilität daraus ableiten.

**Altserie getrennt:** Beim Wechsel V2R4-Candidates und alter V2R4-WAIT-Neurecheck wirklich stoppen/fencen; zuvor offene WAITs belegbar terminal zuordnen oder ausdrücklich `UNKNOWN` belassen. Schon begonnene V2R4-Lifecycle-/STOP-/Exit- und 6h/24h/72h-Followups bleiben **unter der originalen V2R4-Serien-ID** funktionsfähig, mit Original-Cloud-ACK nach `CLOUD_COMMITTED`. Die neue V3-Kette ist kein Freibrief für zusätzliche vorzeitige Modellaufrufe oder eine zweite Paper-Strategie.

**Wiederverwendete Komponenten:** `paper_evaluator/v3_paper_minipc_selective_tick_v1.py` (ein selektiver Tick / Nachlauf), `v3_paper_wait_observer_v1.py` (TTL-PIT, UNKNOWN), `v3_paper_minipc_closed_1m_capture_v1.py` (prospektive Quellbelege), `v3_paper_missed_opportunity_followup_v1.py` (No-BUY), `v3_paper_minipc_followup_v1.py` (Buy-Lifecycle), `tools/v2r4-paper-cloud-sync.py` (Altfolgen). Die Originale und ein physischer Einsatz-/Cloud-ACK entscheiden, nicht ein neues Konzeptpapier.

## 1b. Nutzerentscheidung 17.10.: CPU-Optimierungen zusammen mit V3-Go-live, soweit technisch sicher möglich

**Verbindliches Ziel:** Die bereits entwickelten CPU-Verbesserungen nicht durch einen isolierten V2R4-Produktivwechsel aktivieren. Stattdessen ihren tatsächlichen Nutzen und die jeweils benötigten Komponenten im bestehenden **einen** V3-Paper-Release vorbereiten, inaktiv testen und bei dessen ohnehin erforderlichem kontrolliertem Cutover gemeinsam übernehmen. **Die Integration ist noch NICHT betriebsbereit und kein V3-Release-ACK.** Vor dem Go-live sollen technische Eignung, Rollback, reale Quelle/Bündel-Fingerprints und Nachpflege tatsächlich geklärt und in vorhandenen Release-Belegen abgenommen sein. Nutzerfreigabe für Entwicklung ist keine implizite Freigabe für Cloud-CAS, Windows-Task-Umstellung, bezahlte Modellaufrufe oder Echtgeldeinsätze.

**Echte getrennte Rollen statt blinder Cache-Kopie:**

1. **V2R4-Candidates (Neuaufnahme):** Die bisher CPU-intensive `tools/v2r4-paper-local-runtime.py --mode candidates`-Schleife wird nach korrektem V3-Single-Writer-Cutover dauerhaft *fenced und gestoppt*. Ihr Wegfall ist die primäre künftige Entlastung; ihre PR360/382-Caches sind dann im abgeschalteten Vorgänger **nicht mehr auszuführen**. Vorher sicherstellen: keine erneute Aktivierung über Supervisor/Tasks, keine zwei Writer und keine neuen alten Entscheidungen. PR382 ist nicht bereits im gepinnten produktiven Oct09-Code aktiv.
2. **V2R4 PR326 WAIT vs. echte Alt-Nachpflege strikt trennen:** Beim V3-Cutover werden **Candidates und PR326 WAIT gemeinsam im bestehenden No-Rearm-Fence kontrolliert gestoppt** (siehe `tools/minipc-v3-originalhost-norearm-stop-only.ps1`). Die bereits vorhandene `tools/v2r4-paper-cloud-sync.py::run_closed_aftercare_once` verweigert nach Cutoff jede neue V2R4-Kandidatenentscheidung, jede neue WAIT-Nachprüfung und jeden neuen Paper-Entry. **PR326-WAIT darf nach dem Commit gerade NICHT als fortlaufender Alt-Nachpflege-Worker laufen.** Die alten WAIT-Pläne sind vor dem Stop anhand echter lokaler Originale auf offen/abgelaufen/bearbeitet/unklar zu prüfen; unbewiesene potenzielle Trigger niemals als `NO_TRADE`, abgeschlossen oder realen Verlust verbuchen. Ihre konkrete terminale Zuordnung bzw. Nichtfortsetzbarkeit ist Teil des bestehenden sechsfachen V3-Journal-/STOP-/Recovery-Gates, kein siebtes Gate. **Getrennt davon** laufen geschützte Lifecycle-/Exit-/STOP-/TTL- und 6h/24h/72h-Historien-Folgeprozesse unter ihrer ursprünglichen Serien-ID weiter; der bestehende geschützte PR332-CloudSync übernimmt erst nach echtem `CLOUD_COMMITTED` die strenge `sync_closed_original_followups`-Spur. Die CPU-Cache-Arbeiten **PR360-WAIT und PR382-Candidates werden beim V3-Go-live nicht in stillgelegte Alt-Intake-Prozesse installiert**: deren CPU-Schleifen sollen vollständig entfallen. Ein späterer grundlegend anderer Alt-WAIT-Owner oder geänderte WAIT-Entscheidung wäre ein eigener fachlicher Eingriff, nicht Teil dieser CPU-Migration.
3. **V3-neuer Single-Writer / selektive WAIT- und Followup-Journale:** Seine tatsächlich verwendeten Source-Module und Schleifen (u. a. `paper_evaluator/v3_paper_minipc_one_candidate_v1.py`, `v3_paper_minipc_selective_tick_v1.py`, `v3_paper_wait_observer_v1.py`, `v3_paper_minipc_followup_v1.py`) eigenständig auf unnötige JSON-Scans, wiederholtes Parsing und wachsende Datenmengen prüfen. Schon selektive, kandidatenbezogene Verarbeitung nicht durch einen zusätzlichen Pauschal-Cache oder Hintergrundscanner verkomplizieren. Nur nach **nachgewiesenem Mehrwert und Byte-/Identitäts-/PIT-/TTL-/Followup-Parität** den kleinstmöglichen optimierten Code in den wirklich genutzten, neuen V3-Release-Bundle aufnehmen.

**Ein gemeinsamer Releasevorgang; keine siebte Freigabe:** Technische CPU-Kompatibilität innerhalb der **bestehenden sechs** V3-Belege prüfen: `V3_SINGLE_WRITER_FENCE_CLOUD_CAS_DRYRUN` (Alt-/Neu-Owner, alte Intake-Sperre), `V3_MINIPC_SUPERVISOR_STOP_START_ROLLBACK` (identische Windows Task-/PID-/Quell-Fingerprints, Recovery), `V3_JOURNAL_REASONS_ERRORS_6H24H_FOLLOWUP_CENSURE` (keine verpassten/korrumpierten Daten), dazu exakte Quell- und Runtime-Hashes im einen echten Releasepaket. Keine zweite V2R4→V2R4-Cloud-Rotation, zweite Arbeitsqueue oder zusätzliche Abwartefrist nur wegen CPU. Bestehendes `Issue #353` (Quell-/CPU-Befund) liefert technische Vorarbeit an den originalen V3-Release-Owner `Issue #99`; der eigentliche V3-Go-live hat **genau einen** verantwortlichen Release-Owner.

**Messung und ehrliche Abnahme:** Die vorliegende einmalige Originalhost-V2R4-CPU-Stichprobe (`46,5 %` Durchschnitt, `86 %` Spitze; 22 Python-PIDs = 11 sichtbare Parent/Child-Paare) ist nur Vorher-Evidenz und wird nicht allein der Dokumentation wegen wiederholt. Beim ohnehin fälligen V3-Poststart-ACK einen zeitnahen, bezüglich aktiver Kandidaten-/WAIT-/Followup-Mengen und p95-Verarbeitungslatenz eingeordneten CPU-/Gesundheits-Readback durchführen; zusätzlich Original-Altfolgen und V3 Cloud-Receipts nachweisen. **Keinen garantierten Prozentgewinn oder vollständiges Live-CPU-PASS vor realem Start behaupten.** Pre-Go-live-Status: `CPU_V3_INTEGRATION_PREPARED_AND_TESTED` nur bei tatsächlich nachgewiesenem Einzelkomponenten-/Bundle-Review; Poststart-Status: `CPU_V3_LIVE_BENEFIT_VERIFIED` nur bei wirklichem Host+Cloud-Nachweis.

**Go/No-Go bei technischer Unvereinbarkeit:** Kein riskanter Last-Minute-Hotpatch. Scheitert das sichere gemeinsame CPU-Bundle oder die geschützte Alt-WAIT-Übernahme, bleibt diese Änderung **inaktiv** und der V3-Release-Owner legt vor dem Cutover die konkrete Abweichung mit Auswirkungen, nächstem kleinen sicheren Schritt und V3-Start-/Warte-Option zur ausdrücklichen Entscheidung vor. Eine bloße Performance-Möglichkeit hebt keines der sechs bestehenden Paper-/Recovery-Gates auf. Geht die V3 ohne Cache-Zusatz aus bereits belegbar deutlich niedriger CPU-Last hervor, gilt der nachgewiesene Wegfall des Vorgänger-Scanners als technischer Nutzen; nicht genutzte V2R4-Module werden nicht unnötig weiter optimiert.

## 1a. Verbindlicher Recovery-Abnahmevertrag aus physischem No-Rearm-Test vom 16.10.2026

Der reale **PRE-CAS Paper-Drill** zeigte kein spontanes Scheitern der V2R4-Strategie: Candidates und WAIT wurden absichtlich für den V3-Stopp deaktiviert; die Wiederherstellung erlitt erst einen fehlerhaften atomaren Markerwechsel (Null-Backup bei `File.Replace`), einen falschen `powershell.exe`-Scriptpfad-Alarm sowie eine verzögerte Worker-Heartbeat-Quittung. Der tatsächliche Lauf belegt **manuellen** sicheren Rückweg: Stop/No-Network-Hold → reparierter `QUIESCED`-Marker mit `ARMED`-Backup → zwei erneut laufende, separat fortschreitende HEALTHY-Worker-Heartbeats → Marker-Entfernung → Supervisor HEALTHY / CloudSync ACTIVE_ORIGINAL. Supabase wurde unabhängig geprüft: genau die alte V2R4-Serie aktiv, **0** V3-Serie/Rotation, kein CAS. Der **ungehinderte Ende-zu-Ende-Auto-Rollback ist durch dieses Ereignis NICHT bewiesen**.

Dauerhafte **technische V3-Paper-Release-Grenze, ohne siebten Beleg und ohne zusätzliche Wochen:** Der bestehende Nachweis `V3_MINIPC_SUPERVISOR_STOP_START_ROLLBACK` in `tools/v3_experimental_paper_technical_gate.py` verlangt ab sofort im originalen, unabhängig gegengeprüften Mini-PC-Receipt: (1) exakt gepinnte ursprüngliche Task-/Operator-Identität; Candidates/WAIT ausschließlich im Stop, Lifecycle und alte Followups erhalten; (2) echte unbekannte Python-Worker fail-closed, bloße PowerShell-Skriptpfaderwähnung kein falscher Worker; (3) unterbrochener Markerwechsel nur mit identischem Test-Owner, atomarer Sicherung, korrektem `ARMED`/`QUIESCED`-Status und kontrolliertem Rückweg; (4) bei verzögerter oder unvollständiger Startquittung Marker **nicht** vorschnell entfernen und **keine** blinde Wiederholung/zweiten Writer auslösen; (5) nach Wiederanlauf zwei vorwärtslaufende Candidates-/WAIT-Heartbeats, Supervisor HEALTHY, CloudSync `ACTIVE_ORIGINAL`, Marker `ABSENT`, nur die eine ursprüngliche V2R4-Cloud-Serie und **kein** V3-CAS/Echtgeld. Das echte Original-Receipt muss von der bestehenden Release-Instanz gegen den physischen Host verglichen werden; selbst signiertes Fixture/CI genügt nicht.

Weitere Störfälle (Strom, Internet, Drittanbieter) werden entlang `docs/project-wide-outage-recovery-v1.md` zunächst isoliert/offline getestet, niemals als riskante neue Live-Fehlerinjektion am aktiven V2R4. **Keine automatische V3-CAS-Freigabe** aus dem nun gesunden V2R4, keine Eigenaktivierung der Stop-/Restore-Operatoren und keine Wiederholung des heutigen Tests nur für einen Grünstatus. Offene echte Nachweise bleiben offen, bis der bestehende Owner sie in der nächsten ohnehin notwendigen physischen Release-Runde abnimmt.

## 2. Reihenfolge der physischen Mini-PC-Übernahme, erst **nach** A + technischem `EXPERIMENTAL_PAPER_ONLY`-Gate (§7) **oder** A+B für wirtschaftliche Promotion

1. Vor-ACK: neuen gültigen V3-Bundle-Hash/Release-Evidenz, Zugriff/Host/Heartbeat, lokale Task-Namen und Start-/Restore-Sicherungen **read-only** prüfen. Genau einen Cloud-Status in Supabase, aktuelle V2R4-Serie/Fingerprint, offenen Paper-WAIT/Position/Stop-/Stage2-/Followup-Zustand und Outbox/Dedupe auflisten. **Nie** eine fragliche Stop-/Exit-Nachpflege verlorengehen lassen. Keine alten V2R4-REST-Schreibaktionen mit V3-Serien-ID ausführen.
2. Intake-Fence: Neuen Kandidateneingang in V2R4 lokal am Besitzer/Task pausieren; ACK aus dem **tatsächlich gestoppten** Mini-PC-Service/Task abwarten; ausstehende Auswertung idempotent entweder dem Vorgänger zuordnen oder explizit censored/logisch abgearbeitet. Scanner, Read-only-Kraken, Sensor-/H10-/Source-Forschung und bereits laufende historische Followups **nicht** mit abschalten.
3. Atomic release: dokumentierte **separat geprüfte** Supabase-Transition mit erwarteter aktiver Vorgänger-ID, Status-/Writer-Fence und maximal einer aktiven Strategie-Serie; neue echte V3-Bundle-Hashes; lokale Scheduler/Task registrieren und physisch neuen V3-Paper-Writer starten. Nicht die am 09.10. nur für eine V2R4-TECHNIK-Rotation freigegebene Edge-Funktion oder das alte V2R4-Erstinstallationsskript als V3-Freigabe missbrauchen.
4. Folge-ACK: V2R4 läuft **nicht neu an** (inkl. Supervisor-/Watchdog-Selfheal), keine neuen V2R4-Entscheidungen nach Cutoff, kein zweiter Writer, Supabase genau 1 ACTIVE **V3**, ein echter neuer frischer V3-Kandidat durch vollständigen Evaluator/WAIT-/Paper-Ledger, separate Alt-Followups korrekt. Bei begrenztem Fehler: fail-closed kein Echtgeld, kein doppelter gleichzeitiger Writer, Ausgangslage anhand sicherem Rollback wiederherstellen (bestehende alte V2R4-Serien-ID nicht durch heimliche Runtime-Neubindung verfälschen); Risiko einer Auswertungslücke dokumentieren. **Nie** blind Status-Tabelle auf `closed` setzen, während V2R4 Mini-PC weiter schreibt.
5. Erst bei vollständigem ACK Work/Quellen-Radar/Alerts auf die neue **aktive** V3-Revision umschalten. Dauerhafte alte Paper-Quellen für historische E2E-/Outcome-Vergleiche behalten; keine zusätzlichen Work-Zyklen/Tests einrichten.

## 3. Weitere bislang leicht vergessene Übergaben

- Die laufenden Scanner-Trigger, Kraken-EUR Pair-Status, Slack `SCANNER_CANDIDATE_V1 REVIEW_ONLY_NOT_ORDER`, Supabase-RLS/Service-Token, Self-Hosted Runner, MINI-PC Watchdog/Supervisor, 04:00 Backups, WireGuard, Backup/Rollback, Throttles, 45min Dublettenschutz und separate Monitor-/Statusüberwachung sind **Komponenten der Infrastruktur**, nicht eine neue Strategie-Version. Sie sollen erhalten bleiben und nur notwendige versionsgebundene Endpunkte/Serien-IDs nach physischer Probe wechseln. Keine weiteren Berechtigungen/Secrets voraussetzen.
- Die künftig separate vollautonome **KI-Shadow-Architektur** bleibt fremd und unabhängig; keine Änderung der ursprünglichen V2R4/V3-Originale aus diesem Konzept.
- Quellen-H10/Smart Money, H11/Polymarket, P5 Quellensteward und Marktregime laufen als Forschungs-/Beobachterpfade weiter, sind **keine neuen BUY-Vetos**. H1 bleibt verworfen, H3-001 archiviert und H6 nicht automatisch aktiv. Keine H-Mehrfachaktivierung als „V3 komplett“.
- **Zeit:** Fasttrack gilt ohne künstliche Mindestdauer, wenn unabhängige, risiko-/netto- und Followup-reife Evidenz fertig ist; fehlende unabhängige Belege sind keine Erlaubnis zur Zahlenschönung. Vergleich derselben V2R4-Fingerprint über die 2 technischen V2R4-Teilserien; ihre 72h Uhr wird nicht neu gestartet.
- Monitoring-/Work-Solltakt unverändert: bestehender täglicher 10:15-Work und bestehende 2h-Krypto-Markt-/Quellenaufgabe. Die Aufgaben erhalten nachweisbaren **Wechselauftrag** und Versionserkennungsregel, keine neue Work-/GitHub-/MINI-PC-Automation.

## 4. Scharfer Statuskontrakt

**Freigabepfad sauber unterscheiden:** `EXPERIMENTAL_PAPER_ONLY` benutzt die sechs `tools/v3_experimental_paper_technical_gate.py::PROOFS` und ist zuerst technisch nachweis- und freigabepflichtig; ein profitabler Vorabkauf ist dabei nicht gefordert. Die später wirtschaftlich bewiesene *Strategie-Promotion* verwendet dagegen die fünf `research/strategy-learning-causal-gate-v1.json`-Kausalnachweise. Beide Pfade dürfen niemals aus grüner CI, versuchsweiser Modellantwort, Null-Quellenlage oder bloßem Ablauf der Canary-Frist automatisch Runtime/CAS/Cloud umstellen.


Nur diese Zustände: `V3_PREPARED_INACTIVE` → `V3_ONE_CHANGE_SHADOW_ACTIVE_VERIFIED` (nur mit sicherem eigenem, aktiven tatsächlichen Shadow) → `V3_RELEASE_ELIGIBLE` (belegte Full-Decision-E2E, Kosten, Freigabe) → `V2R4_INTAKE_PHYSICALLY_STOPPED` → `V3_PAPER_ACTIVE_VERIFIED`. Nie einen Zustand durch Dokument-Commit oder Github-CI-SUCCESS allein behaupten. Im aktuellen Snapshot gilt **`V3_PREPARED_INACTIVE`**, Supabase ACTIVE V2R4. Der Nutzer hat V3 PAPER als Ziel freigegeben, nicht Echtgeld oder Freibrief für ungedeckte Modell-API-Ausgaben.

## 5. GitHub/Cloud/Slack-Benachrichtigungshärtung vor dem Cutover (11.10.2026)

**Konkreter Vorabcheck:** Die zuletzt 400 GitHub-Läufe in `kraken-eur-scanner` enthielten **keinen fehlgeschlagenen planmäßigen Überwachungslauf**. Zwei fehlgeschlagene `V2R4 PR validation`-Versuche waren `pull_request`-Tests und keine wiederholt laufende Produktionsüberwachung. Das ist eine **zeitlich begrenzte** Stichprobe, kein genereller Zukunfts- oder Zustellgarant. `kraken-readonly-bridge` hatte zuletzt erfolgreiche Read-only-Snapshot-Läufe, `canonical-evaluator-runtime-v1` zuletzt am 08.10. erfolgreiche historische Ausführungen und bleibt kein neuer V3-Writer. Supabase 11.10. ~07:39 UTC: V2R4 allein active. Kein Secret-, DB-Schema- oder Mini-PC-Betriebseingriff vorgenommen.

**Heute in GitHub ohne aktiven Strategiewechsel vorbereitet:**

1. `paper-series-completion-watch.yml` bindet sich zuerst an `public.paper_series` mit **genau einer** aktiven Serie, vergleicht deren Serien-ID und Revision mit der konkreten `paper_series_completion_readiness` statt blind `rows[0]` zu lesen; unfertige oder widersprüchliche V3-Readiness führt zu klar erkennbarer Fail-Closed-Evidenz. Bisher irreführende Meldung `V2R3-Paper-Abschlussgate` wird dynamisch aus der **real aktiven V2R4/V3-Revision** mit Serien-ID erzeugt. Supabase `paper_series_completion_watch` bleibt nur serienbezogen, kein neuer Table/Job.
2. `tools/project_milestone_controller.py`: historische V2R4-Epochen-/H3-Wirtschaftsgates sind **nur für die aktive V2R4** zuständig. Neuer V3-Zweig braucht **vorher** deklarierte `V3_PAPER_ACTIVE_VERIFIED`, physisch/cloudseitiges ACK und identisches aktives `paper_series_completion_readiness`-ID/Revisionspaar. Danach keine alten V2R4-Low-Trade-Nachrichten, sondern nur verifizierte V3-Collection-/V3-Reife-Mitteilung. Kein neues Modell, BUY oder Aktivierungsrecht. Die bisherige Code-/Release-/Validator-Umstellung auf den neuen V3-Active-State bleibt **Teil des tatsächlichen separaten Release-Gates**, nicht durch diese Vorbereitungsänderung erledigt.
3. `minipc-daily-status.yml` nennt künftig die reale operative PAPER-Serien-ID und wechselt **erst nach echt aktivem V3-Datensatz** von V2R4-Shadow-Eventzahlen auf V3-`candidate_outcomes`/`completed_trades`. Bestehende `minipc_daily_status`-Pflichtspalten `shadow_events`, `completed_outcomes`, `active_outcomes` sind in Supabase `NOT NULL`: für V3 werden deshalb deren historische/obsolete Zahlen als **explizit nicht anwendbare** Legacy-0 mit `payload.legacy_v2r4_shadow_applicable=false` abgelegt; die echten V3-Kennzahlen stehen als solche im Text. Keine unzulässigen `NULL`-Werte oder falschen V2R4-Stats.
4. `tools/paper_series_transition_guard.py`, vorhandener Projekt-Guard und gezielte Tests verhindern veraltete View-Identitäten, zwei aktive Serien, falschen Modell-/Strategiestatus, falsche Version in Slack und V3-Meilensteine ohne tatsächlichen Release-ACK. Kein neuer Workflow oder weiteres Sendeintervall.

**Lassen wir unverändert, weil die aktuelle V2R4 sie noch benötigt:** Scanner `scan.yml`, `process-health.yml` inkl. bereits vorhandener Dedupe-/Grace-Regeln gegen GitHub-Mail bei fachlichem CRITICAL, MINI-PC Cloud-Health-Alarm, Paper-Alert-Relay (hat bereits `SKIP_NO_ACTIVE_V2R4_SERIES`), 2h-Source/Marktregime, passives H10 und bestehende Supabase-Recovery. Alte H1/H3/H6-Prüfworkflows haben aktuell keine produktive Dauer-Schedule; sie dürfen nicht durch blindes erneutes `workflow_dispatch` zum Test/Release missbraucht werden. Legacy-`V2R4`-Tasks auf dem Mini-PC **erst nach echtem Cutover-Fence** ändern.

**Verbleibender realer V3-Abnahmepunkt (unbedingt):** Vor physischer V3-Aktivierung über die dann reale Supabase Cloud-V3-Serie prüfen, dass die allgemeine `paper_series_completion_readiness` tatsächlich **die neue V3-Revisions- und Serien-ID** mit einem einzigen Datensatz liefert, `paper_model_usage_guard` und `paper_series_completion_watch` V3 nicht in alte V2R4-IDs zurückfallen, V3-Trade-/Followups in den bestehenden Ledger konsistent geschrieben und Mini-PC-Supervisor-/Alert-Checks nicht mehr auf fehlende V2R4-Neuaufnahmen bestehen. Anschließend einmal **gezielt** vorhandene Monitor- und E2E-Läufe prüfen, aber keine neuen Dauer-Runs/Tests/Benachrichtigungen. Bei echter Cloud-/Mailstörung und fehlender V3-Maturity: kein `V3_PAPER_ACTIVE_VERIFIED` behaupten oder alte V2R4 physisch ohne geprüften Rückweg ausschalten.

## 6. Re-Audit und bewusst chancenorientierte V3-P3-Forschungsänderung 11.10., abends

Die damals aktive Paper-Serie ist nach neuer direkter Supabase-Abfrage **V2R4** `PAPER-V2R4-20261009T110135Z`; V2R3 ist `closed_complete`. Die heute geprüften 420 V2R4-Erstfälle: 238 WAIT, 182 REJECT, 0 BUY; 40 Nachchecks, davon 38 `EXTENDED`; 189 verfallene WAITs, 0 strukturierte Coin-PIT-/Stop-Inputs im historischen V2R4-Consumer. Einen alten V2R3-Job/Stopp gibt es **nicht** als zu schließenden aktiven Writer.

**Neue konkrete V3-Forschungs-Option**: Die V3-P3-Standardregel wartet für frühe CONTINUITY auf den neuen 15m-Schluss nach ursprünglichem Signal; neue `paper_evaluator/v3_p3_early_5m_continuity_research_v1.py` nutzt, als **getrenntes** Ein-Regel-Experiment, einen **neuen geschlossenen 5m-Schluss** bei alter bereits geschlossener 15m-Basis und identischen Volume≥1,2, ATR/Stop, Spread, Anti-Chase und P4-Gebühren/Stage2-Gates. Der vollständige P4-Validator überprüft diese Sonderberechtigung samt echten Bar-Uhrzeiten/Preisen und kann nur nach explizitem vollständigem Modellvotum einen Kaufvertrag zurückgeben. Tests sind rein offline; keine Live-Strategie- oder Runner-Änderung.

Die erkannten Lücken aus der wochenlangen Datensammlung bleiben ehrlich **OFFEN**, insbesondere 751 nicht vollständig gereifte Alt-Followups nach technischer Rotation, nur vorbereitete noch nicht physisch journalisierte V3-Phasendiagnose und nicht existierender operativer V3-Paper-Writer. Dem ausdrücklichen Nutzerziel, V3 zügig als Paper ausprobieren zu dürfen, folgt deshalb **keine reine Cloud-SQL-Serienumschaltung** ohne realen V3-Writer/Stop-/P4-/Followup-/Cloud-/Supervisor-ACK und einen Rückweg. Der bestehende aktive V2R4-Pfad bleibt bis zu sämtlichen A–D-Evidenzpunkten alleiniger Paper-Writer. Die Zustimmung zum kontrollierten Paper-Wechsel ist erteilt und wird nicht einfach als „fehlende Zustimmung“ abgetan; die ausstehenden Punkte sind **technisch/fachliche Release-Gates**. Work-/GitHub-Status rebindet erst auf `V3_PAPER_ACTIVE_VERIFIED`, nicht bei PR/CI.

## 7. Experimentelles Paper-Gate ≠ wirtschaftliche Freigabe (11.10.2026)

**Konkret beseitigter konzeptioneller Zirkelschluss:** Die Pflicht, **bereits VOR der ersten experimentellen Paper-Serie einen profitablen echten BUY und ausgereifte wirtschaftliche Erfolgsdaten nachzuweisen**, vereitelt ausgerechnet den Paper-Versuch, dessen Zweck diese Datenproduktion ist. Darum besitzt \`tools/strategy_successor_gate.py\` neu neben dem **unveränderten strengeren ökonomischen Nachfolger-Promotion-Gate** einen ausschließlich für V3-Revisionen separaten, **technik- und safetyzentrierten** Status \`EXPERIMENTAL_PAPER_ONLY\`. Dies ist kein automatischer Wechsel/keine Anwendung auf die alte V2R4-Strategie.

- Experimentelles Paper darf mit nachweislich **0 vorherigen BUYs** beginnen, wenn die technische Ein- und Ausgabe, echter Kraken Coin-PIT zum vollständigen Modell-/P4, Stop-/Stage2-/Kosten-Fail-Closed, **pro-Kandidat nicht verlorene Phasen-/Reason-/WAIT-Journals**, bereits vor Start geprüfte 6h/24h-/Censoring-Followup-Provenienz, ein exklusiver Writer und CAS-Cloud-Übergang, Mini-PC-Supervisor-Rollback sowie GitHub-/Work-Serienrouting **alle tatsächlich vor dem Cutover in sechs unabhängigen E2E-Beweisartefakten** vorliegen.
- Der neue Freigabemodus fordert eine exakt gepinnte V3-Revision und 64-stellige SHA256-Bundle- und Strategie-Fingerprints, **begrenzte Kandidaten-/Modell-HTTP-/Zeitkontingente**, deduplizierte Pair-/Clock-Episoden, unveränderte 0,60 % je Seite + Spread/Slippage, 50+50 EUR, echte FULL-MODEL-Autorität und ausdrücklich separat autorisierte API-Kosten. Ohne echte Einzelbelege \`EXPERIMENTAL_PAPER_BLOCKED\`.
- **Keine Kreisschleife**: Vor der physischen Aktivierung ist ein **nachgewiesener Dry-Run** des exklusiven Stop/Start-Fences Pflicht; das echte \`V3_PAPER_ACTIVE_VERIFIED\` wird **erst danach** anhand tatsächlicher Mini-PC-/Cloud-ACKs bestätigt. Niemals vor dem Cutover ein bereits abgeschlossenes Post-Cutover-ACK fordern oder vorgaukeln.
- Eine unbekannte oder negative Rendite im experimentellen Paper ist **keine** Freigabe zur Echtgeldphase und nicht gleichbedeutend mit anschließendem \`READY_WITH_EXPLICIT_PAPER_APPROVAL\` für die endgültige validierte Strategie. Die wirtschaftliche Nachfolger-Promotion nach fünf geprüften kausalen Evidence-Gates bleibt getrennt und streng. Fehlende 6h/24h Followups müssen \`PENDING\`/\`CENSORED\`, nie 0 % oder „profitabel“ heißen.
- **Bislang fehlen die sechs realen physischen/cloudseitigen technischen Belege** für eine laufende V3-Paper-Runtime. Deshalb keine tatsächliche Freigabe/keine V3-Serienumschaltung durch diesen PR allein. Nutzerfreigabe zur Paper-Zielstrategie liegt vor; feste Zahlencaps und neuer API-Kostenrahmen sind vor Ausführung konkret einzuholen, nicht aus dem alten PR186-Lauf zu übernehmen. Der aktuelle Paper-Writer V2R4 bleibt allein aktiv, bis ein sicherer Cutover operativ erfolgt.

## 7. All-Day V3 experimentelle Paper-Version: Code vorbereitet, NICHT physisch gestartet

Neuer einzig kanonischer Strategieentwurf: `research/v3/v3-experimental-paper-all-lessons-bundle-20261011.json` mit Revision `V3-EXPERIMENTAL-PAPER-20261011-ALL-LESSONS-001`. Nutzer hat ausdrücklich das Ziel eines mutigeren **experimentellen Paper-Tests** und kontrollierten Cutovers freigegeben; die Hypothesen können getestet werden, auch wenn ihre spätere Nettowirkung noch **nicht** feststeht. Dies ist **keine** Freigabe zur Umgehung von Gebühren/Stop oder Echtgeld-Ausführung. Die sechs V3-Einstiegswege sind als **`paper_policy_selected=true` und `runtime_enabled=false`** gekennzeichnet; PR/CI allein dürfen diese Flags, Supabase und Mini-PC nicht aktivieren.

**Vor Cutover muss die eigentliche physische V3-Kette verbunden und nachgewiesen sein:** Eindeutiger Source-Kandidat → Kraken-Spot-EUR-geschlossene 1/5/15m-Evidenz/ATR/Low/AssetPairs-PIT → genau eine V3-Familienberechtigung (atomarer Kandidat+Clock-Dedupe/HTTP-Kostenreservierung) → tatsächlicher neuer V3-Modell-Prompt + API-Response/Request-Uhrzeit und Unterursachen/Errors → vollständige P4-Stop/Stage2/Kostenprüfung → **append-only pro Kandidat, inklusive SKIP/UNKNOWN vor Modell** → separater Paper-Writer und 6/24h geordneter Closed-1m-Stop-first/Stage2/Gebühren/Slippage-Pfad → Cloud-ACK/Maturity/Followup-Continuity der alten V2R4-Serie. Der neue Python-Pathwise-Auswerter liefert **nur konservative Modellschätzungen**, keine realen Börsenfills. Jede Phase ist mit Erfolg, Fehler und verifizierbarer Datenquelle zu quittieren; GitHub-CI allein ist keine physische E2E.

**Operator-Grenze:** Keine zweite V3-CLOUD-ACTIVE-Serie bei noch schreibendem V2R4; keine SQL-only-Statusrotation; alte V2R4-Followups und WAIT nicht abschneiden, alte bereits zensierte 751 24h-Horizonte nicht als Nullrendite reparieren. Wirklicher Mini-PC V2R4-STOP-FENCE/Prozess-ACK → Cloud atomarer V3-Einzelwriter → V3-Supervisor/Slack und GitHub/Work versionsgerecht nur nach echter neuer Host+Cloud-ACK. Bis dahin weiterhin **V2R4 PAPER aktiv und V3 nicht aktiv**. Budgetlimits für neuen echten Modellbetrieb müssen als feste Obergrenzen getrennt belegt sein; alten einmaligen PR186-Lauf nicht recyceln.

## 6. Vom Nutzer am 12.10. konkret bestätigter V3-Paper-Startumfang: fünf nützliche Quellenrollen

**Einheitlicher Zielzustand beim frühestmöglichen, separat genehmigten Cutover (13./14.10. angestrebt, KEIN garantierter Termin):**
- **H10 Smart Money:** Bereits bestehender prospektiver Hyperliquid-Owner; authentische, coin-genaue bekannte Original-Fills/Konsens als unterstützender Kontext. Für einen selbstständigen *positiven* Kandidaten müssen unabhängige Wallet-/Netto-Buy-/Nicht-Self-Dealing-/Signatur- und Kraken-Kausalprüfungen **wirklich erfüllt** sein. Quelle gesund oder 26 Wallets abgefragt ist allein kein positives Handelssignal. Keine Verzögerung des V3-Paper-Wechsels allein wegen des ersten noch ausstehenden ≥3-Wallet-Belegs.
- **H11 Polymarket:** Exakt vorab relevant gemappte Ereignisse und originale bekanntzeitliche Wahrscheinlichkeitsänderung als möglicher unterstützender Eintrag; eigener Kaufkandidat nur nach validiertem direktem Coin-Impact **plus** unabhängiger frischer Kraken-Bestätigung. Fünf beliebige Märkte nicht pauschal als Kryptorichtung lesen. Forschungsproben ohne passenden Eventbeleg bleiben neutral und verhindern kein Paper.
- **Marktphasen-Radar:** Existierender 2h-Marktphasen-Owner liefert echtes RISK_OFF / STABILIZATION / RECOVERY / RISK_ON als Kontext für Timing, verbleibende Bewegung und Unsicherheit des Coin-Setups; keine neue zeitliche Pauschal-Sperre und keine V2R4-Risiko-Umgehung.
- **News/amtliche Ereignisse:** Primär bestätigte echte coin-relevante Fakten können als positive Evidenz stützen oder über separaten Eigentümer-genehmigten Source-Katalysator einen *neuen* Kandidaten erzeugen; redaktionelle Meinung, alte Schlagzeile oder allgemeine Stimmung sind keine automatische Stop-/Kaufautorität.
- **Aktives autonomes Quellenmanagement:** Bestehender 2h-Owner entdeckt/pilotiert/bewertet/prüft/quarantiniert/ersetzt Quellen **eigenständig im freigegebenen Forschungsquellenmix** und bietet dem V3-Model nur geprüfte, zeitlich korrekte, unabhängige Signale an. Runtime-Source-Replacement, Feed-Secrets, kostenpflichtige Abos, neue Schedules, Risikoregeln und Handelsstrategie bleiben separate Release-Gates. Erster unbeaufsichtigter Quellen-Pilot und echter PR→CI→Merge→Quelle-wird-vom-Consumer-genutzt-ACK sind noch NICHT als erledigt nachgewiesen.

**Bereits existierende Codepfade:** `paper_evaluator/v3_paper_context_bridge_v1.py` (PIT plus Paar), `paper_evaluator/v3_experimental_paper_model_prompt_v1.py` (fünf Rollen in der echten V3-Full-Model-Prompt), `paper_evaluator/v3_paper_positive_source_entry_v1.py` (streng geprüfter H10/H11/amtliche positive Kandidat), `paper_evaluator/v3_paper_minipc_one_candidate_v1.py` (vorhandener Einzel-Writer), `docs/market-source-autonomy-v1.md` und `research/monitoring-evidence-routing-v1.json#source_quality`. KEINE parallele Scoring-Engine, kein neuer Poller, keine pauschale Multisignal-BUY-Abstimmung.

**Abnahme ohne künstliche neue Shadow-Wochen:**
1. V3-Paper-Kernrelease A/B/C aus §1 bleibt das *einzige* aktive Release-Gate; keine H3/H6-/H10-H11-Wirksamkeits-Proof-Pflicht als zusätzliche Startblockade.
2. Beim einzigen konkreten physischen Mini-PC-Start/Modell-Nachweis einen Snapshot `FULL_REVIEW_ELIGIBILITY.optional_context_states` und `actual_optional_context_with_source_clock` für genau **H10/H11/market_phase_radar/news_sentiment/source_stewardship** prüfen. Pro Feld `AVAILABLE_PIT_CONTEXT_ONLY` **nur mit echter Owner-/PIT-Quittung**, sonst ehrliches `NOT_AVAILABLE/STALE/UNVERIFIED/NOT_ASSOCIABLE`. Ein echter validierter positiver Katalysator ist ein **zusätzliches** Gate, nicht durch bloßes Kontext-Flag bewiesen.
3. Wenn ein tatsächlich vorhandener Source-Fakt in einer Full-Modell-Paper-Entscheidung material ist: Modell-`reason_codes` auf kausalen Coin-Bezug prüfen, mit Kraken/Stop/Stage2/0,6 % je Seite plus Spread/Slippage und echter P4-Quittung verbinden, bei späteren 6h/24h-Followups den Mehrwert bewerten; bei leeren Quellen keinen künstlichen Testfall oder neuen Bezahl-API-Aufruf nur für die fünf Rollen durchführen.
4. Nach Cutover **bestehende** 10:15-/2h-Work-/Issue-#7-/Meilenstein-Owner weiterverwenden, gezielte Lücken neben laufender V3 Paper beheben. Kein eigenmächtiger nächster Strategie- oder H-Modul-Release und kein zweiter Single-Writer.

**Status dieser Konkretisierung:** `SOURCE_ROLES_SPECIFIED_FOR_V3_PAPER_START` und `FULL_MODEL_PROMPT_INACTIVE_CI_ONLY`, **nicht** `FIVE_LIVE_OWNER_FEEDS_CONFIRMED` oder `V3_PAPER_ACTIVE`. Die echte Produktivwirkung und autonome Research-Quelle→Consumer-ACK bleiben offen bis konkreter Betriebsnachweis.

### 6a. Verbindlicher V3-Go-live-Szenariotest: Smart-Money-Folgeeintritt nach Scanner-WAIT/REJECT (Nutzerentscheidung 18.10.)

**Vor dem V3-EXPERIMENTAL-PAPER-Cutover innerhalb der vorhandenen sechs technischen E2E-Belege prüfen, nicht bloß als Forschungsabsicht dokumentieren.** Ein nachweislich und *prospektiv* qualifizierter Trader kauft tatsächlich einen konkreten Coin, den unser Scanner zuvor erkannt, aber nicht gekauft hat. Der frische, vom Original-Owner zeitgestempelte H10/Smart-Money-Nettokauf muss den **bestehenden** Kandidaten zur **erneuten vollständigen V3-Kaufbewertung** bringen können: Original-Scanner-/WAIT-/REJECT-ID → verifizierte Wallet-/Fill-/Trader-Provenienz und Freshness → passender online handelbarer Kraken Spot-EUR-Coin sowie aktueller geschlossener Coin-PIT → echtes vollständiges Modell mit nachvollziehbaren `reason_codes` → P4 Stop/Stage2/0,6 % pro Seite + Spread/Slippage/Liquidität → bei gültigem `BUY_SCOUT` **bestehender einzelner V3-Paper-Writer mit deduplizierter 50-EUR-Quittung**. Kein neues H10-Polling, keine Parallel-Paper-Engine, keine alte REJECT-Umschreibung: der neue Decision-Clock/Trigger wird eigenständig journalisiert.

**Smart-Money-Vertrauensbasis:** Ein Trader darf nur als zuverlässig gelten, soweit überprüfbare *vor dem Signal bekannte* unabhängige Historie, Nettoergebnisse nach Kosten, Stichprobengröße, zeitliche Streuung, Wallet-Identität, echte Netto-Käufe, möglicher Hedging-/Self-Dealing-/Copy-Latenz-Bias und direkter Coin-/Kraken-Bezug dies erlauben. Hohe historische Trefferquote oder ein einzelner Whale-Fill ist kein Kaufbeweis. H10 bleibt im Regelbetrieb eine **optionale** Quelle: nicht verfügbare, nicht zuordenbare oder verspätete Signale sind transparent `NOT_AVAILABLE/UNKNOWN` und **kein pauschales BUY-Veto**.

**Abnahmekontrollen als Teil des bestehenden Gates, ohne Warten auf ein zufälliges Live-Ereignis:** Ein vollständig begründeter positiver, punktzeitkorrekter Testfall muss den frischen Modell→P4→**kontrollierten** physischen Single-Writer-Paper-Receipt-Pfad beweisen; negative Gegenproben (unzuverlässige Trader-Historie, isolierte/falsche Wallet, bereits eingepreister Move, unklare Coin-Zuordnung, verspätetes Fill, ungültiger Stop/Spread) dürfen **keinen** erzwungenen Kauf erzeugen und müssen Ursache sowie fehlende Daten unveränderlich journalisieren. Kontrollierte Test-Fills nicht als echte marktprospektive Gewinne verbuchen. Fehlender erfolgreicher Live-H10-Wirtschaftsnachweis/50-Event-Outcome-Join ist **keine separate siebte Freigabesperre**; technische Routenabnahme dieser konkret vom Nutzer geforderten Situation ist hingegen **offen bis belegt**. Kein automatischer V3-Cutover, V2R4 bleibt unverändert. Dokumentation/CI alleine ergibt ausdrücklich kein `PASS`.


## 8. V3-spezifisches, inaktives Cloud-CAS-Transaktionsgerüst (13.10.2026, vor 14:00)

**Nur Review-/GitHub-Code; weder Supabase-Migration noch Edge-Deployed noch Freigabe.** Das vorhandene historische `rotate_v2r4_technical_paper` ist **nicht** der V2R4→V3-Strategiewechsel und darf dafür nicht benutzt werden. Die neue eigenständige **inaktive Vorlage**
`supabase/v3-experimental-paper-atomic-cas-INACTIVE-20261013.sql`
enthält ausschließlich eine separate bedingte Funktion `rotate_v2r4_to_v3_experimental_paper`. Kein neues Journal, keine neue Cloud-Tabelle, kein zusätzlicher Paper-Writer, kein zusätzlicher Work-Job. **Sogar bei versehentlicher Migration bleibt dem `service_role` die Ausführung ausdrücklich entzogen**; ein echtes Schema-Deployment ist dennoch untersagt, bis ein fachlich-/technisch unabhängiges Freigabegate vollständig ist.

Die SQL-Vorlage ist gegen das am 13.10. aus der realen Cloud **nur lesend** abgefragte bestehende `public.paper_series`/`paper_candidate_outcomes`/`paper_trade_results`-Schema konstruiert. Eine erfolgreiche statische GitHub-Prüfung ist kein syntaktisch ausgeführter PostgreSQL-Test und kein tatsächlicher Cloud-CAS. Sie prüft den erwarteten `paper_series_single_active_idx`, sperrt in einer Transaktion die alte Serienzeile und alte Beweistabellen, bindet den erwarteten echten V2R4-Vorgänger, ursprüngliche SHA-40/64-/Strategie-/Bundle-Werte, exakte Alt-Kandidaten-/Trade-Anzahlen und jüngsten `updated_at` sowie den neuen V3-Serien-/Test-/Release-/P4-Bundle-Fingerprint. Nur bei übereinstimmenden Live-Werten darf die alte Serie geschlossen und eine einzige neue aktive V3-Serie **in derselben** DB-Transaktion eingetragen werden; sonst wird beides zurückgerollt. Alte originalen Paper-Trades, WAITs und 6h/24h/72h-Followups werden dabei **nicht** verschoben, gelöscht oder umetikettiert.

**Noch notwendige, echte Gates vor jeder Installation/Ausführung:**
1. Original-Canary-Ende **13.10. 14:00:12.2795431 MESZ** tatsächlich am Mini-PC nachweisen, neun Code-SHAs sowie Windows-Task-Originaltrigger kontrollieren, keine Quell-/Script-Re-Pins. V2R4 weiterhin die einzige aktive Paper-Serie, bis die wirkliche Übergabe bewusst freigegeben ist.
2. Verantwortliche für alte V2R4-STOP-/WAIT-/Pending-/6h24h72h-Followups konkret an die **alte** unveränderte Serien-ID binden; Cloud-Outbox, aktive Paper-Fills, das bereits vorhandene `paper_series_completion_readiness` und Supervisor-/Task-Neustartverhalten auf genau diesen Übergang testen. Der neue Altstatus `strategy_cutover_closed` ist nur ein **Vorschlag**, muss von allen vorhandenen View-/RLS-/Relay-/Daily-/Work- und Backlog-Verbrauchern geprüft und nötigenfalls als kanonischer Status angepasst werden; nie ohne solchen Test in Produktion annehmen.
3. Die Vorlage zunächst in einer **separaten nichtproduktiven Postgres-Testtransaktion/isolierten Testdatenbank** syntaktisch und mit realistischen Fällen ausführen: richtige Vorgänger-SHA/Anzahl, veränderte `updated_at`, doppelter Nachfolger, fehlender Unique-Index, zweite aktive Serie, falsch gedrehte Risiko-/Budget-Felder, konkurrierender Update/Commit, SQL-Abbruch, unbekannter HTTP-Ausgang. Kein echtes Supabase-Schreiben am aktiven Projekt während des Canary; später keine Testmutation an den realen produktiven Paper-Serien.
4. Vor einer späteren Cloud-Deployment-/EXECUTE-Freigabe eigenen überprüften **V3-Edge-Operator mit zwei unabhängigen Authentifizierungen** an die bereits bestehende physische Mini-PC-Owner-/Quarantänelogik anschließen; Host-Snapshot/Supervisor-Rearm-Fence/Single-Writer/Alt-Followup-Owner extern echt validieren, aktuellen aktiven Cloud-Vorgänger frisch ermitteln und die sechs getrennten echten `VERIFIED_PHYSICAL_OR_CLOUD_E2E`-Belege einschließlich realem Modell/P4-Original separat kontrollieren. Die von SQL übergebenen booleschen Konfigurationsangaben sind **keine** unabhängige physische Quittung.
5. Erst nach **gesonderter ausdrücklicher Paper-Releaseentscheidung und neuer expliziter Modellbudgetfreigabe** ist ein wirkliches Cutover eine andere, eigenständig zu freigebende Aufgabe. Bei fehlender/unklarer Cloud-Commit-Antwort strikt `CLOUD_AMBIGUOUS_QUARANTINE_BOTH_WRITERS`; keinerlei automatische CAS-Wiederholung, alter Wiederanlauf oder zweiter Writer. Nach echtem Commit NIE blind auf alte aktive V2R4 zurücksetzen. Nachlauf über vorhandenen 10:15-Work- und Projekt-Followthrough-Owner mit unabhängigen Host/Cloud ACKs.

**Unveränderter Fortschrittsstatus nach SQL-Vorlagen-PR:** `V3_PREPARED_INACTIVE` / `BLOCKED_RELEASE_EVIDENCE_NOT_V3_RUNNING`. Ein gemergtes SQL-Dokument ist weder deploytes CAS noch ausgeführter Dryrun, physischer Stopp oder V3-Paper-Aktivierung.

### Zwingender Alt-Followup-Relay-Nachweis vor jedem realen V3-Cutover (13.10., 13 Uhr, READ-ONLY-Befund)

**Konkret bestätigter Cloud-Kompatibilitätsblocker:** Der vorhandene `supabase/functions/v2r4-paper-evidence-relay/index.ts`-Zweig `action="sync"` verlangt `series.status==="active"` (Zeilen 172–203); der vorhandene `tools/v2r4-paper-cloud-sync.py` nutzt ausschließlich diese `sync`-Aktion für Outcomes und Trade-Updates. Der in der inaktiven V3-CAS-SQL vorgeschlagene alte Status `strategy_cutover_closed` wird daher vom **heutigen** Relay zurückgewiesen. V2R4-Altergebnisse würden nach einem unvorbereiteten echten Serienwechsel trotz vorhandener lokaler Journal-/Positionsbelege nicht mehr in die Cloud gelangen. **Die inaktive V3-CAS-Vorlage ist dadurch absichtlich NICHT deploy- oder releasefähig.**

Im ursprünglichen sechsteniligen V3-Release-Gate verlangt der bereits vorhandene einzelne CAS-Beleg deshalb ab jetzt ausdrücklich zwei getrennte Quellrollen: Der Mini-PC muss einen realen, getrennten unveränderten **ALT-FOLLOWUP-Owner** nachweislich weiter betreiben, der keine alten Neuaufnahmen zulässt und nicht durch den Supervisor still aktiviert wird. Die Cloud muss mit originalgetreuen Quittungen beweisen, dass bei der geschlossenen Vorgängerserie **(a)** ein existierendes historisches 6h/24h/72h-Followup erfolgreich aktualisiert wird, **(b)** ein originaler offener V2R4-Trade/STOP/Exit sicher abschließt und **(c)** ein neu hinzukommender V2R4-Kandidat nach dem Cutover ausdrücklich abgewiesen wird. Diese drei Beweise müssen vor jedem V3-Start in einer unabhängig getesteten Cloud-/Mini-PC-Version inaktiv und später echt erbracht werden.

**Aktuelle Umsetzung dieses Schritts:** Nur die bereits vorhandene V3-Freigabe wird **fail-closed** verschärft; der derzeit aktive V2R4-Relay und alle laufenden Tasks bleiben **unverändert**. Eine wirksame Relay-/Host-Followup-Fortführung ist weiterhin eine konkrete technische Implementations- und physische Freigabeabhängigkeit mit dem **bestehenden** V3-Single-Writer-Cutover-Owner; ein grüner synthetischer GitHub-Test ist kein realer historischer Closed-Series-Ack. Keine Parallel-Datenhaltung, kein zweiter Scanner, keine neue Work-Schleife, keine Veränderung der neun ursprünglichen Canary-Pins.

### Vorbereiteter, NICHT deployter Altserien-Relay-Empfang (13.10.2026, nach #282)

Im **ursprünglichen** `supabase/functions/v2r4-paper-evidence-relay/index.ts` wurde ausschließlich als inaktiver GitHub-Code ein separater `action="sync_closed_original_followups"`-Zweig ergänzt. Der produktive `action="sync"`-Zweig für die aktuelle aktive V2R4-Paper-Serie ist unverändert. Eine spätere Inbetriebnahme dieses neuen Zweigs ist **nicht** automatisch durch GitHub-Merge oder PR-/CI-Test genehmigt.

- Verlangt die **beiden bestehenden** Relay-Credentials `X-Shadow-Evidence-Token` und `X-MiniPC-Status-Token`, die ursprüngliche echte alte Serien-ID/Revision/Release-SHA, den konkreten bisher NICHT aktiven Altstatus `strategy_cutover_closed` und **genau einen** inzwischen tatsächlich `active` gewordenen V3-Nachfolger.
- Nur kleine Batches, **keine UPSERTs/INSERTs/DELETEs**; jedes alte Candidate-/Trade-`candidate_id` muss im unveränderten `series_id` bereits existieren. Alte Eröffnungs-/Originalentscheidungsinformationen und zuvor als vollständig quittierte Horizonte bleiben unveränderlich; alte `WAIT→REJECT`-Folgedisposition ist möglich, **neuer** V2R4-BUY/Stage2/Neuaufnahme NICHT. Originale alte Trades können nur als bereits bekannte Positionen endgültig `CLOSED` quittiert werden, nicht neu eröffnet werden.
- Parallele oder veraltete Cloud-Schreibversuche müssen mittels der bestehenden Datenzeilen-`updated_at`-Optimistic-CAS-Bedingung fehlschlagen. Jede alte Closed-Followup-/Trade-Quittung bleibt ein Originalfall und wird nie einer neuen V3-Serien-ID zugeschrieben.

**Noch OFFEN, nicht als `VERIFIED_PHYSICAL_OR_CLOUD_E2E` behaupten:** Der derzeit aktive Mini-PC-Sync sendet bislang ausschließlich `action="sync"` und ist nicht an diese neue geschlossene Altserien-Aktion angebunden. Vor einem echten V3-CAS fehlen mindestens noch (1) separat genehmigter Edge-Deploy/Authentifizierungs-/Integritäts- und negativer HTTP-E2E-Test auf isolierten Testdaten, (2) abgesicherter *originaler* Mini-PC-Alt-Followup-/Exit-Sender mit fail-closed Umschaltung erst NACH echtem physischem V2R4-Intake-Fence, (3) echte vollständige WAIT/Trade-/6/24/72h-Cloud-ACKs nach Alt-Close und Ablehnung alter neuer Kandidaten, (4) echte Prüfung gegen alle Downstream-Verbraucher und die Nachlauf-/Work-Owner. Keine Neu-Tasks/zweite Relays/Cloudtabellen dafür einrichten.

Die 28h-Original-CANARY-Aufgabe bis **13.10. 14:00:12.2795431 CEST** und ihre neun SHA-Pins sowie V2R4-aktives Paper und Quellen bleiben unangetastet. Der bestehende V3-Six-Proofs-Release-Guard (#282) verhindert das echte V3 Paper ohne diese unabhängigen alten Cloud-Beweise.

### Mini-PC-Alt-Followup-Sender: read-only Payload-Vorschau (13.10., vor echtem Canary-Stopp)

Der **bestehende** Originalsender `tools/v2r4-paper-cloud-sync.py` bekommt nur einen zunächst **vollständig inaktiven reinen Vorschau-Modus** `--preview-closed-original`. Normaler Aufruf/aktive V2R4-`action=sync`/bestehende Windows-Task bleiben unverändert. Die Vorschau verwendet die vorhandenen ORIGINAL-`paper_runtime_control.json`, `paper_decisions`, `paper_followups`, `paper_positions` und erzeugt bis zu 20 Elemente je künftigem `sync_closed_original_followups`-Payload **ausschließlich im Speicher**, ohne Token-Leseversuch, Netzwerk, Heartbeat-Datei, Journaleingriff, neuer Alert oder Auftrag an GitHub/Work. Die CLI-Ausgabe enthält nur Zahl/Status, keine Kandidatenbelege.

Das künftige reale Mini-PC-Owner-Fenster muss **nach** dem unveränderten Original-Canary-Ende den echten alten Dateipfad, die unabhängig überprüfte Original-V2R4-Release-SHA, die verbindlich vorgeschlagene (noch NICHT aktive) `PAPER-V3-YYYYMMDDTHHMMSSZ`-ID und den exakt freizugebenden späteren Cloud-Cutover-Zeitpunkt liefern. Ohne diese vier konkreten Werte scheitert die Vorschau ausdrücklich; kein erfundener Beispiel-SHA und keine implizite Ableitung aus dem veralteten GitHub-`paper_runtime_control.json`.

Die Vorschau akzeptiert nur Paper-only-V2R4-Originale, deren ursprüngliche Candidate-Erstellung/Trade-Eröffnung **vor** dem benannten späteren Cutover lag, ursprüngliche V2R4-Followup-Strukturen oder bereits endgültig geschlossene Original-Positionen. **Sie prüft NICHT**, ob ein Original in der Cloud bereits existiert oder ob die physische V2R4-Neuaufnahme wirklich gestoppt ist. Diese unabhängigen Original-ACKs müssen der spätere existierende Relay-Owner und das sechs-Proofs-CAS-Gate weiterhin erbringen. Insbesondere ist die eigentliche Netzwerk-Versandumschaltung bewusst **noch nicht im bisherigen Mini-PC-Worker aktiviert**; es gibt derzeit lediglich die überprüfbare Payload-Vorschau. Vor original 13.10.2026 14:00:12.2795431 CEST kein Mini-PC-`git pull`, keine Aufgaben-, neuen Script- oder Tokenänderungen.

**Tatsächlicher Supabase-Originalbefund 13.10., ca. 13:51 MESZ:** 22 laufende V2R4-`PAPER_FOLLOWUP_V2`-Originale besitzen noch kein `updated_at_utc`; untersuchte Beispiele haben `horizons={}` und `WAIT_PENDING` oder eine vorläufige REJECT-Dispositionskennung. Die vorbereitete read-only Mini-PC-Vorschau sendet diese NICHT als fertige oder zensierte Rendite, zählt sie gesondert unter `pending_unstamped_followups_not_promoted` und setzt die Prüfung der anderen gültigen Originale fort. Existieren dagegen bereits **nichtleere** ursprüngliche Horizon-Daten ohne Originalzeitstempel, gilt dies als widersprüchlich und stoppt die Vorschau. Der spätere physische Owner hält diese 22 bzw. dynamisch neuen Fälle in der originalen alten V2R4-Serie zur ehrlichen Reifung/Followup oder eindeutigen Source-Censor-Quittung offen. Keine Zeitstempel ergänzen, keine 0-Rendite synthetisieren.

## 15.10.2026 – Quellidentität des V3-Nachfolgers vor echtem Paper-Cutover (source-only, PR322)

Die aktuelle Original-Mini-PC-Prüfung vom 15.10. belegt eine valide PR320-READ-ONLY-WAIT-Prozessfamilie, vier ursprüngliche laufende Aufgaben, Hash-geprüftes Candidates/WAIT-Backup, Supervisor Git-Blob und 59-Sekunden-Heartbeat sowie `NONE` vor der V3-Fence-Phase. Der neue GitHub-Fence-Vertrag PR321 fordert separat Windows- und Supervisor-No-Rearm-ACK. Das ist **kein physischer Stop**, keine reale V3-Runtime und keine der sechs vollständig authentischen V3-Paper-E2E-Release-Quittungen (0/6).

Das kanonische Strategiebündel `research/v3/v3-experimental-paper-all-lessons-bundle-20261011.json` bleibt `CODE_READY_INACTIVE_RUNTIME_NOT_ACTIVATED`; die expliziten Eintrittsmodule haben `runtime_enabled=false`. GitHub-Quellprüfung zeigte die 18 tatsächlich referenzierten Python-Dateien vorhanden. Das bestehende `tools/v3_experimental_paper_technical_gate.py` berechnet jetzt optional über `assess_v3_experimental_source_inventory(root)` eine **reproduzierbare Source-Only-Inventur**: SHA256 des exakten JSON-Bundle-Dateiinhalts, sortierte Liste der SHA256-Dateiinhalte sämtlicher vom Bundle direkt referenzierter `.py`-Dateien plus der bestehenden V3-Paper-Kernankermodule und ein SHA256 des kanonischen Inventur-Payloads. Referenzpfade werden im Repository eingeschränkt; fehlende, symbolisch umgeleitete, übergroße oder unsichere Quellen sowie versehentlich aktiv gesetzte Bundle-Familien blockieren. Das ist eine Provenienz-VORBEREITUNG, **kein** vollständiger transitiver Import-/Dependency-Audit und **kein** bereits formal freigegebener Code-/Strategie-Fingerprint.

**Explizite Grenze:** Die Quell-Kandidatenprüfsummen aus dem GitHub-Stand sind nicht die noch separat zu prüfenden `proposed_v3_repo_sha`, `proposed_v3_bundle_sha256` und `proposed_v3_strategy_sha256` eines authentischen V3-Releasepakets. Niemals alte V2R4-Hashes oder CI-Fixture-Werte als V3-Nachfolger-Identität ausgeben. Eine neue V3 Cloud Paper-Serie existiert noch nicht. Das endgültige versionierte V3-Paper-Release muss unabhängig die Runtime-/Live-Full-Model/P4- und Kostenketten, begrenzte neue Modell-HTTP-Budgetfreigabe, sechs echte externe E2E-Belege, originale Kandidaten/WAIT-Fence-/Rollback-Vorabprüfung, 6h/24h-Nachlauf, CAS-Dryrun und denselben Source-Commit belegen. Kein Windows Stop/Task-, Cloud-, Budget- oder Echtgeld-Eingriff durch diese source-only-Funktion.

Owner bleibt die bestehende V3-P0/P1-/Issue-#99-/10:15-Work-Kontrollschiene, keine zweite Versionsregistratur und keine zusätzliche Automatisierung. Nächste wertvolle Arbeit: die realen einzelnen technischen V3-E2E-Beweispfade am vorhandenen Mini-PC/journal- und Cloud-Owner binden; sobald sie authentisch erfolgreich sind, diese hier ermittelten Quellinputs im EINEN kanonischen echten Releasepaket nach Originalhost-ACK fixieren und den bereits genehmigten reversiblen PRE-CAS-STOP/Rollback-Versuch ausführen.


## 16.10.2026 – verbindlicher Realstand nach PR348 (physisch/cloud read-only, kein Paper-Cutover)

Dieser **zeitlich neuere** Originalbefund ersetzt ausschließlich veraltete
Annahmen in den obigen datierten Arbeitsschritten. Ältere Test-/Freigabebelege
bleiben unverändert und dürfen nicht als neue Testaufträge verstanden werden.

**Bereits tatsächlich vorhanden, nicht nochmals installieren oder wiederholen:**

- Der **laufende** originale Mini-PC-Scheduled-Task
  `CryptoMiniPC-V2R4PaperCloudSync` verwendet den geschützten
  `Trading\Staging\PR332-CloudSync-20261016-113256-d5c85c73\v2r4-paper-cloud-sync.py`
  mit vom Originalhost abgelesenem **SHA256**
  `7B3635E4A052D9CA4295DD64184D4BF8B8BC5BB4AD16DF1000D866D59473A3550`.
  Das stimmt mit dem bereits bestätigten PR332-Mini-PC-Installationsmanifest
  überein. **Nicht** aus dem alten, bewusst eingefrorenen produktiven Git
  `b37f872...` ableiten, welche CloudSync-Quelldatei effektiv läuft.
  Die neue Fassung enthält `original_cloud_sync_fence_lane`,
  `run_closed_aftercare_once` und den fail-closed-Wechsel erst bei
  `CLOUD_COMMITTED`. Der gesonderte Shadow CloudSync läuft weiterhin.
- Supabase **tatsächlich veröffentlicht**: `v2r4-paper-evidence-relay`
  **ACTIVE Version 9**, einschließlich
  `sync_closed_original_followups` mit zweiter Authentifizierung,
  alter Originalserien-Identität und der Sperre gegen neue V2R4-Kandidaten.
  Abgerufene Edge-`index.ts`-Bytes sind **identisch** mit aktuellem GitHub
  (`28.446` Zeichen). Kein erneutes Edge-Deployment ohne neuen Befund.
- Ebenfalls bereits **ACTIVE**: `v3-paper-evidence-relay` **Version 1**.
  Dessen echter Edge-Source-Stand ist ebenfalls byteidentisch mit GitHub
  (`6.053` Zeichen), kann CANARY-Receipts annehmen und verweigert
  Nicht-CANARY-Receipts bei nicht aktiver passender V3-Paper-Serie.
- Die bestehende EIGEN/ZRO-28h-Beobachtung ist abgeschlossen:
  672 von 672 originale lokale JSON-Snapshots waren bei der lesenden
  Host-Prüfung fehler- und konfliktfrei; pro Paar 1705 rechtzeitig bezeugte
  individuelle 1m-Kerzen, längster zusammenhängender Abschnitt 1690 Minuten.
  Dies ist **keine** gültige rückwirkende 6h-/24h-Entry-Abdeckung für alte
  vor Beobachtungsstart gefällte Modellentscheidungen.
- Echte historische V3-CANARY-Journale: 21 von 21 Originalhost↔Cloud
  Inhalts-/Semantiknachweise bereits abgeschlossen; früherer echter ZRO-API-
  Modellentscheid und P4 ergaben WAIT. Nicht erneut kostenpflichtig ausführen,
  sofern kein eigenständiger neuer Freigabenachweis nachweislich fehlt.
- PR344–348 wurden source-only zusammengeführt; deren finale GitHub-main-
  Source-Version ist `41e088023657ff92a010387e81a07cc8ba4a1156`.
  Ein separates Mini-PC-`V3Stage\source-41e08802` wurde real geprüft:
  **31/31** zielgerichtete Windows-Offline-Tests PASS, Worktree CLEAN,
  produktiver V2R4-HEAD unverändert. Diese Tests beweisen **nicht** einen
  realen Prozessabsturz, einen live bezahlten neuen Modellaufruf oder
  einen aktivierten V3-Paper-Writer.

**Unabhängige Supabase-Abfrage 16.10.2026, 18:04 UTC:** genau eine aktive
`PAPER-V2R4-20261009T110135Z`; **keine** `PAPER-V3-...`-Serienzeile;
bestehender Unique-Active-Index vorhanden;
`rotate_v2r4_to_v3_experimental_paper` **nicht installiert**.
Der jüngste hochgeladene Mini-PC-Snapshot hatte CloudSync und Supervisor
`HEALTHY`. Nur eine zeitgebundene Statusaufnahme, keine Dauer-Garantie.

**Verbindlicher aktueller Restauftrag am EINEN vorhandenen V3-P0/P1-
Release-Owner (Issue #99 / bestehender 10:15-Work-Kontrollpfad):**

1. Nicht den bisherigen 28h-Beobachter, keinen alten CANARY-Smoke und
   keinen zweiten Scheduler aktivieren. Den bereits entwickelten EINEN
   Kandidat→geschlossene Kraken-1m-Quelle→vollständige Modell/P4-Entscheidung→
   Paper-Journal→6h/24h/72h→Cloud-ACK-Strang zu einem **releasegebundenen
   tatsächlichen V3-PAPER-Writer** mit eigener Serien-/Owner-Identität
   integrieren. Die heutigen CANARY-only-Codefunktionen nicht bloß durch
   Entfernen einer Namenssperre zu Live-PAPER deklarieren; echte Laufzeit-
   Eingabe-/Budget-/No-Rearm-/Single-Writer-Grenzen müssen belegt sein.
2. Fehlende **Originale** gegen die exakt **sechs bereits vorhandenen**
   technischen Freigaben prüfen; Mini-PC/Cloud/GitHub/Work-Quellrollen,
   Release-Pins und frische aktive Cloud-Serie festhalten. Den alten
   Protected-CloudSync und das bereits deployte Relay unverändert
   **wiederverwenden**, den echten geschlossenen V2R4-Alt-Followup-/Exit-
   Nachweis vor Freigabe der Rotation gesondert erbringen.
3. Die noch **nicht** installierte V3-Cloud-CAS-Funktion / physische
   Task-Owner-Änderung / echter neuer kostenpflichtiger Modell-Aufruf /
   V3-Paper-Cutover erfordern weiterhin ihre jeweils gesonderte ausdrückliche
   Freigabe. Keine Cloud-Serienrotation oder produktiven Task-Mutationen
   allein aus einer CI-/Dokumentations-Freigabe.
4. Paper startet erst mit **freigegebenem echten Original-Releasepaket**,
   Paper-only 50+50 EUR und nachgewiesenem Alt-Followup-Schutz. Echtgeld
   ist ausdrücklich nicht Gegenstand dieses Schritts.

**Kein neuer Projektmanager, keine siebte Freigabe, keine zusätzlichen
Abwartewochen und keine Wiederholung der bereits erledigten 21/21-, 28h-,
31/31-, PR326-/PR332-/PR341–348-Prüfungen.** Diese Ergänzung ist nur
Dokumentations-/Kontext-Konsolidierung, keine Runtime-/Cloud-Änderung.
