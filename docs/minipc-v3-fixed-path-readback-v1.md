# Mini-PC: feste V3-Pfadabfrage statt manueller PowerShell
Stand 19.10.2026. Owner bleibt Issue #353 und privater Runner Issue #13.

Die vorhandene GitHub→Mini-PC-Schnittstelle kann nur explizit geprüfte Aufgaben ausführen. Die neue Funktion `v3_fixed_paths_readonly` prüft ohne Argumente ausschließlich die drei festen bekannten Verzeichnisse `C:\Users\ADMIN\Trading`, `...\Staging` und `...\V3Stage` auf Existenz, Reparse-Points, lokalen `.git`-Marker und festen V3-Launcher-Marker. Kein rekursives Scannen, keine Datei-Inhalte, keine Namenliste, keine Schreiboperationen, keine Git-Kommandos. Ausgabe nur feste Root-Keys und typisierte Zustände. Bei fehlendem Zugriff `ACCESS_DENIED` bzw. `UNAVAILABLE` statt stillschweigender Erfolgsmeldung.

Nach geschütztem Merge: bei tatsächlichem Diagnosebedarf den vorhandenen privaten `MINIPC_TASK_V1 | <merged main SHA> | v3_fixed_paths_readonly`-Weg verwenden, einen Originalhost-ACK prüfen und dann in künftigen Chats für diese Frage zuerst diesen Task nutzen. Kein zweiter Runner, Scheduler, Work-Lauf, Adminrecht oder Trading-Eingriff. Der unabhaengige Workspace-Schreibtest wurde im Originaljob #39283677017 erfolgreich nachgewiesen; kein allgemeines Dateirecht.

Die Aufgabe ist bewusst **kein** allgemeiner Remote-PowerShell-Interpreter. Für andere häufige lokale Befunde gilt Reuse zuerst, dann begrenzte weitere Aufgaben mit Review. Vor jedem manuellen PowerShell-Auftrag im Chat die vorhandene GitHub-Lesequelle und freigegebene Runner-Aufgabe prüfen.

## Datierter Originalhost-Status, 19.10.2026

PR #443 und Erweiterung PR #444 sind gemergt. Der eingeschraenkte Windows-Originaljob [#39313293207](https://github.com/hoffmannherdecke/kraken-readonly-bridge/actions/runs/39313293207) lieferte drei Root-Keys `PRESENT`, `V3STAGE nested_git_count=5`, jedoch `STAGING nested_scan=TOO_MANY_CHILDREN`; die dortige begrenzte Unterordnersuche ist nicht vollstaendig. Das ist ein datierter Host-Nachweis, keine aktuell laufende V3-Wirkkette oder Host-Gesundheitsgarantie. Bei erneutem Bedarf dieselbe genehmigte Aufgabe verwenden, statt den Nutzer GitHub manuell durchsuchen zu lassen.
