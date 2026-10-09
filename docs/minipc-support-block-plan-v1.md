# MINI-PC SUPPORT V1 — Umsetzungsblöcke und Wiederaufnahme (09.10.2026)

**Status 09.10.2026, 15:45 MESZ:** Architektur/Blockplan; **Block 1 physische read-only Inventur PASS; Control-Plane-Abgleich bleibt offen**. Keine produktive GitHub-Migration, kein neuer Runner/Service, keine KI installiert. Autoritatives offenes Gate: `PROJECT_BACKLOG.md` P4 `MINIPC_SUPPORT_V1`; zugehöriger Vertrag: `docs/github-capacity-and-cost-strategy-v1.md`.

## Unveränderliche Ziele und Grenzen

1. Bestehende V2R4-Paper-, V3-H3-/H10-Shadow-, Scanner-, Supervisor-, Backup-, Cloud-Sync- und Sicherheits-Gates erhalten Vorrang; keine stillen Änderungen an Strategie, aktiver Release-Identität, Secrets, Echtgeld oder Work-Automation.
2. Nur sachlich geeignete **private, regelmäßig abrechnende** GitHub-Aufgaben schrittweise auf Mini-PC auslagern, zuerst `kraken-readonly-bridge`-Snapshot (GitHub-Hosted bisher `:10/:40` = 48 Jobs/Tag), nicht den öffentlichen Scanner. Rechenbeispiel: bis zu 1.440 gerundete Hosted-Minuten/30 Tage, falls vollständiger Umzug und 1 billable minute/Job; ohne tatsächliche Billing-Daten **nicht als realisierte Ersparnis** darstellen. Aktuelles Nutzer-Budget 10 USD/Stop-Usage nicht verändern.
3. 16 GB vorhandener RAM **blockiert den Start nicht**. 32 GB RAM sind kurzfristig vom Nutzer vorgesehen, **noch nicht als eingebaut oder getestet markieren**. Ein zusätzlicher ressourcenbegrenzter Job maximal zur gleichen Zeit. CPU/RAM-/Disk-Messung und Lastspitzen entscheiden; Trading-Last geht vor. Keine neue Hardware, kein Docker/WSL/VM oder neue Dauer-Scheduler erforderlich.
4. Vollständige Unabhängigkeit ehrlich darstellen: Self-hosted GitHub Actions verlagert Rechenarbeit und Kosten, **nicht** den GitHub-Scheduler, Workflow-Queue oder Artifact-Backend. Auch Netz- und Stromausfälle des Mini-PCs bleiben möglich. Bei privater Konto-Snapshot-Blindzeit dürfen Accountdaten nicht als frisch gelten; V2R4/H3 dürfen nicht vom Snapshot abhängig werden.
5. Autonomer, sich selbst programmierender KI-Trading-Agent bleibt **ausdrücklich zurückgestellt, nie vergessen** und benötigt später separate isolierte Architektur und ausschließlich read-only Input aus dem bestehenden Projekt. **Zusätzliche Option, kein Agentenstart:** kleiner lokaler **KI-Systemberater** (z. B. Ollama + ein kleines quantisiertes Qwen-Modell) für offline/begrenzte Analyse von ausdrücklich freigegebenen, redigierten Status- und Log-Auszügen. Denkbare Fragen: häufige Prozessneustarts, ähnliche Fehlerursachen, plötzlicher CPU-/RAM-Anstieg. Ausschließlich erklärender Vorschlag; keine Restart-/Schreib-/Secret-/Netz-/Repo-/Order-/Scheduler-Rechte. Nachweisbare Qualität, CPU-Geschwindigkeit und Rest-RAM nach Trading-Last testen; Modellgröße und RAM-Verbrauch anhand konkret gewählter Version und Kontext ermitteln, **keine pauschale Dateigröße als Ressourcengarantie**. Nur nach stabilem Offload/Gate und gesonderter Nutzerentscheidung aktivieren, **keine KI-Installation jetzt**.

## Die geplanten Arbeitsblöcke — nur bei Bedarf weitergehen

### Block 1 — JETZT / reine Bestandsaufnahme (circa 15–30 Minuten aktive Arbeit)

- [x] GitHub-Private-Bridge, aktuelle Read-only-Workflows, vorhandene Mini-PC-Supervisor- und Preflight-Skripte sowie bestehende Outage-/Kapazitätsverträge *lesen*; vorhandene große `minipc-local-core-gate.ps1`, `minipc-next-user-step.ps1`, `minipc-post-recovery-gate.ps1` nicht für bloße Kapazitätsprüfung aufrufen, weil sie auch Eingriffe/Schreibaktionen/Tests enthalten.
- [x] Eigenes kurzes, read-only Mini-PC-Inventurskript zur Wiederverwendung in diesem Repo vorbereitet: `tools/minipc-support-readonly-inventory.ps1`. Keine Adminrechte, Netzaufrufe, Secret-Ausgabe, Task-Starts, Dateischreibvorgänge oder `git pull`.
- [x] Auf Mini-PC **nach Prüfung des lokalen Git-Status** einmal die aktuelle Repo-Version sicher auf Stand bringen, falls `main`, clean worktree und Fast-Forward möglich: `git -C "$HOME\Trading\Repos\kraken-eur-scanner" status --short --branch`, dann `git -C "$HOME\Trading\Repos\kraken-eur-scanner" pull --ff-only`. **Bei fremder Änderung/Fehler stoppen**, nicht Reset/Force. Kein Paper-App-Installer, kein Runtime-Fingerprint-Überschreiben.
- [x] Das Inventurskript einmalig aus normaler PowerShell auf Mini-PC starten: `& "$HOME\Trading\Repos\kraken-eur-scanner\tools\minipc-support-readonly-inventory.ps1"`. Ausgabe darf zur gemeinsamen Einordnung als Text oder Screenshot übermittelt werden. Sie enthält nur summarische Hardware-/Task-/Health-Metadaten; keine Secrets.
- [x] Kurz messen: real 16/32 GB, RAM frei, CPU-Snapshot und bei realem Scan-Intervall, C:/D:-Reserve, letzte Health-Frische, Task-Ergebnisse, vorhandener Runner ja/nein. Nicht von einem einzelnen CPU-Snapshot auf garantierte Dauerreserve schließen.
- [ ] Bevor neue produktive Last hinzugefügt wird: **kanonische Statusdatei mit gegenwärtiger Cloud-Wahrheit abgleichen**. Im read-only Projektvergleich 09.10. 15:19 MESZ: Supabase `paper_series` hat `PAPER-V2R4-20261009T110135Z` als `active`, Vorgänger `PAPER-V2R4-20261007T184255Z` als `technical_closed`; H3-001 `FROZEN_TECHNICAL_CUTOVER`. Das ältere `project-current-state.json` verweist noch auf die Vorgängerserie/H3-001 als laufend. Zuerst nach neuerem Release-/H3-Nachfolgerbeleg schauen; nur evidenzbelegte Control-Plane-Korrektur über bestehenden Governancepfad, keine Strategie-/Serienmutation.
- **Blockabschluss:** konkrete Runtime-Ressourcen- und Statusdaten, kein Eingriff in Paper-/Shadow-Runtime; Entscheidung `READY_FOR_BLOCK_2` oder `STOP_REASON` mit genau einer nächsten Handlung.

### Tatsächlich geprüfter Mini-PC-Iststand — 09.10.2026, 15:45 MESZ

**Physische Belege:** Nutzer-Screenshots des einmaligen `MINIPC_SUPPORT_READONLY_BASELINE_V1`-Laufs nach `git fetch` + erfolgreichem `git pull --ff-only origin main` auf zuvor lokal sauberem `main`. Erststart wurde von Windows-Skriptausführungsrichtlinie blockiert, darauffolgende einmalige Ausführung mit prozesslokalem `powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ...` erfolgreich. **Keine permanente Windows-ExecutionPolicy-Veränderung, keine Git-Reset-/Force-Operation, kein Trading- oder Task-Neustart, kein Secret-Zugriff.**

| Messung | Ergebnis |
|---|---|
| Windows | Windows 11 Pro |
| RAM | 15,8 GB erkannt; 8,6 GB frei, 32 GB **noch nicht verbaut** |
| CPU | 7 % Momentanauslastung; **keine Peak-/Lastzeit-Messung** |
| C: | NTFS, 172,1 GB frei / 237,4 GB gesamt |
| D: | NTFS, 305,4 GB frei / 465,8 GB gesamt |
| lokaler Watchdog | `HEALTHY`, geprüft um 15:44:27 MESZ |
| Windows-Aufgaben | 17 `CryptoMiniPC-*` gefunden; mehrere laufende Dauerjobs zeigen `last_result=267009` (Windows Task Scheduler SCHED_S_TASK_RUNNING; **kein Fehlerindikator**) |
| V3 H3 001 | `CryptoMiniPC-V3H3Shadow001` derzeit `Disabled`; letzter Task-Ergebniscode `267014` (0x41306, vorheriger Task wurde beendet). Die deaktivierte Aufgabe ist konsistent mit dem separat bestätigten H3-001-Freeze nach technischer Paper-Rotation; Code allein beweist keinen normalen Abschluss. **Nicht selbsttätig reaktivieren** |
| GitHub Runner | kein `actions.runner*`-Dienst gefunden; `existing_github_runner_services=0` |
| Lesender Prüflauf | `read_only=true`, `changes_made=false` |

**Entscheidung:** `BASELINE_PASS_WITH_CONTROL_PLANE_FOLLOWUP`. Die verfügbaren 8,6 GB RAM und niedrige einmalige CPU-Momentanauslastung erlauben **einen manuellen, kurzzeitigen, harmlosen Einzeljob ohne Secrets**, nicht den Nachweis dauerhafter CPU-/RAM-Headroom oder einer bereits betriebsfähigen Self-Hosted-Runner-/Failover-Lösung. Bei 16 GB RAM ist kein automatischer Stopp notwendig. Die Doku-/Control-Plane-Staleness nach Paper-Rotation bleibt als vor jeder produktiven Migration zu klärender Punkt bestehen. H3 001 bleibt gefroren.

### Block 2 — isolierter, harmloser lokaler Executor (circa 45–90 Minuten)

- [ ] Entscheiden Windows-Aufgabe vs. GitHub Self-Hosted-Runner anhand bestehender GitHub-Actions-Snapshot-/Artifact-Konsumenten. Den bereits bei GitHub erzeugten **privaten** 1-Tages-Artifactvertrag erhalten; lokaler Python-Task ohne GitHub-Job stellt das GitHub-Artifact nicht automatisch bereit.
- [ ] Für Pilot eigener eingeschränkter Windows-Kontext, isolierter Arbeitsordner, Begrenzung 1 gleichzeitiger Job, Timeout, Ressourcenpriorität und kurze lokale Retention. Keine Admin-/Schreibrechte auf aktives Trading und keine produktiven Secrets.
- [ ] GENAU EIN manueller harmloser Lauf (lokale Systemmetadaten/öffentliche Daten) ohne Kraken Account-Key. Unnötige Rekursion, Startup-Autostart, weitere Runner oder dauerhafte Diagnostik vermeiden.
- **Blockabschluss:** Pilot PASS (ohne Trading-Latenz/Restart-Regression) oder sauberer Abbruch.

### Block 3 — privater Kraken-Snapshot und wirklich unabhängiger Rückfall (circa 1,5–3 Stunden)

- [ ] `kraken-readonly-bridge/.github/workflows/refresh.yml`: `ubuntu-latest`, `actions/checkout@v7`, `actions/setup-python@v7`, `bridge.py`, `actions/upload-artifact@v4`; `bridge.py` prüft exakt `query-funds`, `query-open-trades`, `query-closed-trades` und liefert `kraken_snapshot.json`. Windows-/Bash-Verhalten, Python, Schlüsselbereitstellung nur in privatem Isolat, GitHub Artifact-Verbraucher/Frische/TTL vor Änderung verifizieren. Keine live Secrets in öffentliche Repos, PowerShell-Ausgabe oder Dokumente.
- [ ] Default-Erfolg zuerst lokal **nicht-produktiv** überprüfen, niemals 2 aktive autoritative Snapshot-Writers. Für Überwachung/Fallback echte GitHub-Run-Ausführung/Artifact-Erzeugung/Frische und Heartbeat messen, nicht bloß Schedule-Start oder Runner-Online. Cloud-Health aktuell alle 4 Stunden kann keinen schnellen Failover garantieren; ausfallsichere Fallback-Entscheidung vor Migration definieren und mit Billing-Kosten abwägen. **Runner-Offline darf nicht zu 24h-Queue-Starvation führen**. Eine feste Cloud-Fallback-Ausführung zu jedem 4h-Check kann bereits verlorene Snapshot-Zwischenintervalle nicht rückwirkend herstellen.
- [ ] Ein einziger autoritativer Publisher je Snapshotfenster, Idempotenz/Ereigniszeit, Backoff und begrenzte Cloud-Dispatch-Rate; keine automatische Erhöhung des 10-USD-Budgets. Rollback: GitHub-hosted `ubuntu-latest` und ursprüngliche Schedule-/Secret-/Artifact-Semantik versioniert wiederherstellen.
- [ ] Zwei natürliche vollständige E2E-Zyklen mit Nachweis für Artefaktfrische, zugelassene Key-Rechte, Backup/Health, lokalen Verbrauch und Wiederanlauf; kein ungeprüfter absichtlicher Strom-/Netzausfall. Ohne sicheren Rückfall **keine** produktive Verlagerung, auch falls die Einsparung attraktiv wirkt.
- **Blockabschluss:** `MIGRATION_PROVEN` mit Meßwerten oder `STAY_CLOUD_HOSTED`.

### Block 4 — Stabilitätsnachweis, optionale spätere Mini-KI (circa 20–40 Minuten späterer Review)

- [ ] Aus mehreren regulären Läufen GitHub Billing (Account-weit), Supervisor-Warnungen, Ressourcen-Headroom und Snapshot-Frische bewerten. Keine neuen Work-/GitHub-Poller; Nutzer gegebenenfalls um **einen** Billing-Screenshot bitten, falls der Verbrauch sonst nicht beweisbar ist.
- [ ] Nur wenn stabil: abgrenzen, ob und wie der kleine **nur beratende** Ollama/Qwen-Systemdiagnostiktest (auf Abruf, ohne dauernden Modellprozess, keine sensitiven Rohlogs) einen Zusatznutzen gegenüber vorhandenen regelbasierten Watchdogs bringt. Test zu einem späteren Zeitpunkt gesondert freigeben; Ergebnis `HELPFUL`, `NOT_WORTH_RESOURCES` oder `DEFERRED`.
- [ ] Großer autonomer KI-Trading-/Coding-Agent bleibt separates Langfrist-Vorhaben ohne Aktivierung.

## Fortsetzen ohne wieder bei null zu starten

Nächster Schritt nach diesem Checkpoint: **Block 1** Control-Plane-Abgleich auf Basis der bestehenden Supabase-/GitHub-Release-Evidenz abschließen; danach **Block 2**, zuerst die kleinste risikoarme Executor-/Artifact-Variante festlegen. Das Inventurskript **nicht erneut** ausführen, sofern kein konkreter neuer Befund oder RAM-Einbau dies verlangt. Nie ganze Ketten erneut testen, nie unfertig voraussetzen, kein Agentenbetrieb. Rollen: Assistent bereitet sichere GitHub-Dokumentation/-CI und lesende Cloudprüfungen vor; Nutzer führt nur physische Mini-PC-Schritte aus, die ohne direkten Zugriff anders nicht möglich sind.

**Zeitbild:** Kein 6-Stunden-Dauerblock nötig. Die aktiven Arbeiten verteilen sich auf kurze Sitzungen; in Summe grob 4–6 Stunden, eventuell 6–8 bei echten Rückfall-/Windows-/Secret-Sicherheitsproblemen. Zwischen regulären E2E-Läufen kann Warte-/Beobachtungszeit liegen. Keine garantierte Endzeit.
