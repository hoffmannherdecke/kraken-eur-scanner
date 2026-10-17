# MINI-PC Runner: kostenloser Schutz ohne GitHub-Pro-Abo (17.10.2026)

**Beschluss:** Kein GitHub-Pro-/Team-/Enterprise-Abonnement, keine jährliche oder monatliche Gebühr. Private Repositories bleiben privat. Der bestehende Windows-GitHub-Runner `MINI-PC-CryptoSupport` im privaten Repository `hoffmannherdecke/kraken-readonly-bridge` bleibt zunächst `Stopped/Disabled`. Alles andere ist keine durch die Abonnement-Freigabe gedeckte Änderung.

## Minimale Alternative: Windows-eigene Schranke vor jedem Job

GitHub dokumentiert `ACTIONS_RUNNER_HOOK_JOB_STARTED` als lokalen Pre-Job-Hook: Exit-Code ungleich Null blockiert den vollständigen Job, **bevor dessen Schritte laufen** ([GitHub Docs](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/run-scripts)). Der Hook liegt **außerhalb** des Runner-Workspace in `C:\ProgramData\CryptoSupportGuard\pre_job.ps1` und wird über eine Windows-Maschinen-Umgebungsvariable konfiguriert, nicht durch eine GitHub-Workflowdatei.

Der Hook erlaubt ausschließlich:

1. Originales privates Repository, genau `.github/workflows/minipc-reviewed-project-task.yml@refs/heads/main`, Event `issue_comment`, Runner `MINI-PC-CryptoSupport`, Windows-Nichtadminkonto `CryptoSupportSvc`.
2. **Festen und lokal als Datei gespeicherten GitHub-Workflow-COMMIT-SHA** `28bdddccd7d917151958c4b64461dc6289e71eca`. Jeder Workflow-Änderung im privaten, ungeschützten Repository ändert den Commit SHA und der Runner verweigert dann die neue Version, bis der Admin **nach tatsächlicher Quellprüfung** den lokalen Pin aktualisiert. Andere private Jobs erhalten keinen Self-hosted Runner-Zugriff über dieses Konto, insbesondere nicht unreviewte PR-Workflows, Pushes oder freie Dispatches.
3. Exakten, frischen (max. zehn Minuten) ursprünglichen privaten Issue-#13-Kommentar vom GitHub-Owner über die App `chatgpt-codex-connector` im Format `MINIPC_TASK_V1 | <gemergte SHA> | <bekannter taskname>`.
4. Der existierende private generische Workflow selbst prüft die SHA als Vorfahren des **geschützten öffentlichen** Hauptrepository-`main`, nutzt eine geprüfte reguläre `tools/minipc_runner_tasks/*.ps1`-Quelldatei und ein eingeschränktes Windows-Konto. **Keine freien PowerShell-Befehle aus dem Kommentar.**

## Einmalig, unter Aufsicht auf Windows

Die vorhandene Datei `tools/minipc_runner_guard/install_guard.ps1` ist ein rein vorbereitender Admin-Installer. Er akzeptiert nur einen explizit gepinnten Commit des **geschützten** öffentlichen Quellrepositories, lädt daraus die genau zugehörige Hook-Datei in ein neues `C:\ProgramData\CryptoSupportGuard` und sperrt Verzeichnisrechte auf SYSTEM/Admin volle Rechte sowie **nur Lesen/Ausführen** für `CryptoSupportSvc`. Prüft vorher `Stopped/Disabled`, genau dieses Windows-Konto, Runner-Verzeichnis und bestehende Konfigurationskollisionen. Installiert den Windows-Maschinen-Hook, aber **startet den Runner nicht**, legt keinen neuen Windows-Task an und schaltet keinen Autostart ein. Der Rückbau (`-Remove`) erfordert ebenfalls Adminrechte und einen zuvor deaktivierten Runner.

**Diese Phase ist erst nach einem echten lokalen Installer-ACK umgesetzt.** Der Merge der Source allein ist KEINE Host-Installation. Vor einem echten Dauerstart müssen ein erlaubter Job und ein unerlaubter Job unter aktivem Hook getestet werden; der unerlaubte Job muss im Setup mit `LOCAL_PREJOB_DENIED` bereits vor seinem ersten Schritt scheitern. Danach echte Rückkehr zu `Stopped/Disabled` prüfen. Bei fehlender Hook-Ausführung **STOP**. Kein direktes Aktivieren von `Automatic`.

## Grenzen

- GitHub Free stellt den privaten Branchschutz weiterhin nicht bereit. Eine lokale Workflow-SHA-Freigabeliste vermindert dessen Auswirkungen **nur auf diesen Mini-PC-Runner**. Sie ersetzt keine Regeln zum Zusammenführen, keine zweite Entwickler-Review, keinen sicheren Softwarelieferkettenprozess.
- GitHub Self-hosted Runner sind **keine isolierten VMs**; ein legitim autorisierter Job bleibt Codeausführung unter `CryptoSupportSvc`. Die nachgewiesene Verweigerung der `Trading\Secrets`-Verzeichnisauflistung belegt keine vollständige Nichtlesbarkeit aller einzelnen Dateien.
- Der Runner hat ursprünglich Änderungsrechte auf `C:\CryptoSupport`. Installer prüft zwar vorhandenen lokalen `.env`-Hook-Konflikt und installiert den Hook außerhalb, garantiert aber noch nicht, dass alle übrigen Runner-Konfigurationsdateien gegen ein späteres autorisiertes Skript manipulationssicher sind. **Ein dauerhafter unbeaufsichtigter Betrieb ist somit NICHT vorweg genehmigt**.
- Jeder gezielt später erlaubte Quelltask ist vor Ausführung auf Zugriffsbedarf und Änderungen an Trading/Secrets/Runtime zu prüfen. Echtgeld, Kraken-Keys, Supabase-Service-Rollen, Windows-Admins, neue Kostenbudgets, V2R4-/V3-Cutover und Trading bleiben außerhalb dieser Pilotautorität.
- Keine Änderung am Cloud-hosted Kraken Read-only Snapshot, übrigen GitHub-CI-Jobs, V3-/CPU-Projekt, Work-Läufen oder Supabase. Kein GitHub-Pro-Abo, keine neue Software-Abonnementgebühr, keine KI-API-Anfragen für den Hook. Normale Strom-/Netz-/GitHub-Kontingente gelten weiter.

**Nächster kleiner Gate:** Originales GitHub-CI und Merge des Hook-Quellcodes → einmaliger Admin-Installationsnachweis am Mini-PC → kontrollierter positiver und negativer Jobtest → erst dann über die kostenlose automatische Bereitstellung (z. B. kurze lokale Bereitschaftsfenster) entscheiden, statt ungeschützt 24/7 einzuschalten.

**Owner:** Einziger Gesamtautomations-Owner [Hauptprojekt #353](https://github.com/hoffmannherdecke/kraken-eur-scanner/issues/353); privater Original-Runner-Audit [Bridge #13](https://github.com/hoffmannherdecke/kraken-readonly-bridge/issues/13).