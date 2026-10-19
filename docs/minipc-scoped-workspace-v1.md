# Mini-PC: Einmalig autorisierter isolierter Schreib-Arbeitsbereich (19.10.2026)

**Nutzerfreigabe:** Ein neuer, abgegrenzter Arbeitsordner `C:\CryptoSupport\Workspace` mit Modify-Recht für das lokale `CryptoSupportSvc`-Konto wurde ausdrücklich freigegeben. Das ist **keine** Freigabe für Administratorrechte, Systemordner, Runner-Skripte, bestehende Trading-/V2R4-/V3-Dateien, Registry, Dienste, Windows-Updates, Neustarts, Zugangsdaten, Modellbudgets oder echte/papierne Orders.

**Originale Infrastruktur bleibt:** Private `MINIPC_TASK_V1 | protected-main-SHA | taskname`-Schnittstelle, SHA-Pin, `CryptoSupportSvc` ohne Adminrolle, normaler Windows-Runner-Zeitplan und dessen SafePause. Bereits abgenommene Basisprüfungen werden nicht wiederholt.

## Einmaliges separates Setup (nur nach geprüftem Source-Merge)

Die neue Datei `tools/minipc_runner_guard/install_scoped_workspace.ps1` ist **kein GitHub-Runner-Task**, sondern eine manuell durch den autorisierten Windows-Administrator auszuführende Installationsanweisung. Sie prüft das bestehende `C:\CryptoSupport`-Verzeichnis, lehnt Reparsepoints ab, bricht bei existierendem Workspace ab, legt **nur wenn neu** das Verzeichnis an und setzt eine geschützte, nicht geerbte DACL: SYSTEM und BUILTIN-Administratoren mit FullControl; `CryptoSupportSvc` mit Modify ausschließlich im Workspace und seinen künftigen Inhalten. Eine Abweichung führt zur Sperre und – falls sicher und leer – zum Zurücknehmen des neu angelegten Ordners. Keine anderen ACLs, keine Prozesse, Aufgaben, Windows-Konfiguration oder Dienstzustände werden verändert.

**Wichtig:** Die freigegebene Installation wurde **noch nicht am Windows-Host ausgeführt**, bis tatsächlich überprüfter Quellstand und eine bestätigte lokale Administratorausführung vorliegen. Unbekannter Ordner-/ACL-Bestand darf nicht überschrieben werden.

## Erstes reviewed Arbeitsbeispiel

`tools/minipc_runner_tasks/workspace_report.ps1` verwendet ausschließlich `C:\CryptoSupport\Workspace`, prüft die Originalidentität und tatsächliche lokale Verzeichnisse/Reparsepoint-Grenze, verweigert mehr als 19 vorhandene Einträge, erstellt eine zufällig benannte Testdatei, liest exakt ihren Inhalt zurück und löscht sie wieder. Danach schreibt es mit `CreateNew` einen kleinen, maximal 4096-Byte großen, nicht ausführbaren JSON-Bericht in denselben Ordner, liest ihn zurück und gibt nur einen bereinigten `MINIPC_WORKSPACE_SAFE_SUMMARY_V1`-Status sowie den üblichen `MINIPC_REVIEWED_TASK_ACK_V1` zurück. Es akzeptiert **keinen** Dateipfad, URL, Shelltext oder sonstige frei wählbare Parameter und führt **keine** Datei aus dem schreibbaren Verzeichnis aus. Berichte werden nicht an Dritte übertragen und sind nicht automatisch eine Cloud-/Trading-Eingabequelle. Nach Erreichen des Eintragslimits müssen Berichte gezielt außerhalb dieses Auftrags archiviert werden – keine unkontrollierte Bereinigung.

**Abnahme einmalig und differenziell:** (1) geschützte PR-Quelle und CI; (2) manuelle neue Windows-ACL mit echtem Originalhost-Readback; (3) **genau ein** source-gepinnter Original-Mini-PC-Runner-Auftrag `workspace_report`, bei dem Schreib-Lese-Löschprobe und persistenter Bericht `PASS` sind. Danach keine erneute Gesamtprüfung der alten Runner-/Strom-/Scheduler-Funktionen. Wenn Setup oder Test nicht besteht, nur diese **neue** Grenze korrigieren; keinesfalls pauschale Admin- oder zusätzliche NTFS-Freigaben.

**Offen/ausgeschlossen:** Der Ordner ist bislang nicht nachgewiesen, seine NTFS-ACL noch nicht gesetzt und ein echter Schreib-ACK noch nicht vorhanden. Der dokumentierte `SOURCE_CI_PASS` darf niemals als `WINDOWS_WORKSPACE_WRITE_HOST_PASS` ausgegeben werden. Weiterer Funktionsausbau nutzt dieselben vorhandenen Quellen statt neue Runner/Scheduler/Work-Aufgaben einzurichten.
