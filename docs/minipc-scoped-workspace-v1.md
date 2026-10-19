# Mini-PC: Ein einziger isolierter Schreib-Arbeitsbereich (19.10.2026)

**Vom Nutzer ausdrücklich genehmigt:** ausschließlich der neu anzulegende Ordner `C:\CryptoSupport\Workspace` mit `Ändern/Modify` für das lokale nichtadministrative Konto `CryptoSupportSvc`. Keine Erweiterung der Administratorrolle, der Trading-/V2R4-/V3-Dateien, anderer Benutzerprofile, Registry, Dienste, Aufgaben, Windows-Updates, Neustarts, API-Schlüssel, Modell- oder Orderrechte. Einzelner bestehender Owner: [Issue #353](https://github.com/hoffmannherdecke/kraken-eur-scanner/issues/353).

**Unveränderter Transport:** bestehender privater `MINIPC_TASK_V1 | <protected-main-SHA> | workspace_report`, lokale Prejob-Pin-Prüfung und begrenztes Runnerfenster. Keine neue permanente Komponente, keine freie PowerShell oder frei übergebene Pfade. Bereits abgeschlossene Runner-/Strom-/Scheduler-/SafePause-Abnahmen bleiben gültig.

## Einmalige manuelle Windows-Einrichtung

Nur **nach** geschütztem Source-Merge und unter anwesendem Windows-Administrator auf dem Original-Mini-PC. Ein früherer unvalidierter Administrator-Installer-Entwurf wurde im Entwicklungszweig ausdrücklich **entfernt** und ist nicht auszuführen.

1. Im Explorer prüfen, dass `C:\CryptoSupport` ein echtes vorhandenes Verzeichnis ist (keine Verknüpfung/Junction). **Wenn `Workspace` bereits vorhanden ist: STOP**, keinen vorhandenen Ordner/ACL überschreiben; Ist-Bestand erst prüfen.
2. Ein neues Verzeichnis namens `Workspace` innerhalb von `C:\CryptoSupport` anlegen.
3. Rechtsklick `Workspace` → **Eigenschaften → Sicherheit → Erweitert**. Vererbung **deaktivieren** und für **genau dieses neue Verzeichnis** geerbte Zugriffsregeln entfernen. Vor Abschluss kontrollieren, dass der Bearbeitende weiterhin administrative Kontrolle herstellen kann. Keine Rechte des übergeordneten `CryptoSupport`-Verzeichnisses ändern.
4. Genau folgende drei explizite **Zulassen**-Einträge für **Diesen Ordner, Unterordner und Dateien** einrichten: `SYSTEM` → Vollzugriff; lokale Gruppe `Administratoren` → Vollzugriff; **lokales Konto** `<PC-Name>\CryptoSupportSvc` → **Ändern**. Weder `Jeder/Everyone`, `Benutzer/Users`, `Authenticated Users`, noch allgemeine Gruppen mit Schreibrechten ergänzen.
5. Erneut im erweiterten Sicherheitsdialog ablesen: Pfad und Besitzer, Vererbung aus, genau die beabsichtigten Berechtigungen, und kein anderes Verzeichnis verändert. **Erst dann** `WORKSPACE_NTFS_ORIGINAL_ADMIN_ACK=PASS` mit Datum/Uhrzeit dokumentieren. Bei unklarer oder abweichender Ansicht nicht fortfahren; kein weiteres ACL-Experiment.

**Diese GUI-Einrichtung ist noch nicht geschehen und wird nicht aus der GitHub-Quelle abgeleitet.** Wenn Einstellungen an vorhandenen Arbeitsdaten nötig wären, stoppen: dafür liegt keine Freigabe vor.

## Eng begrenzter ausführbarer Auftrag

Das im geschützten Projekt `main` zu prüfende Script `tools/minipc_runner_tasks/workspace_report.ps1` läuft ausschließlich unter dem bestehenden `CryptoSupportSvc` ohne Administratorrechte. Es nimmt **keine Parameter** an. Das Script verwendet nur diesen festen Workspace, verweigert Reparse-Ordner und bereits vorhandene Reparse-Einträge, stoppt bei 20 oder mehr Einträgen und hat ein Dateilimit von 4096 Byte pro Ergebnis. Pro Auftrag legt es eine zufällige kleine Prüfedatei an, liest sie zurück und löscht **nur diese selbst erzeugte** Prüfedatei. Danach legt es **nur eine neue** nicht ausführbare JSON-Berichtsdatei mittels `CreateNew` an, liest sie selbst zurück und liefert ein bereinigtes `MINIPC_WORKSPACE_SAFE_SUMMARY_V1` und den existierenden `MINIPC_REVIEWED_TASK_ACK_V1`. Vorhandene Dateien werden nicht überschrieben, umbenannt oder automatisch gelöscht; es erfolgt kein Scan anderer Dateibäume und keine Cloud-Übertragung von Dateiinhalten.

**Einmalige gezielte Originalhost-Abnahme** nach echter Windows-ACL: im vorhandenen privaten GitHub-Audit-Issue #13 exakt ein `MINIPC_TASK_V1`-Auftrag mit neu gemergter Hauptrepo-SHA und `workspace_report`. Nur `LOCAL_PREJOB_V1_APPROVED`, Original-Runnerjob `success`, `MINIPC_WORKSPACE_SAFE_SUMMARY_V1` mit erfolgreicher Schreib-Lese-Löschprobe und persistenter Bericht sowie richtiger SHA erlauben `WORKSPACE_WRITE_HOST_ACK=PASS`. Nicht noch einmal Runner-Grundeinrichtung oder Stromausfall testen. Bei Berechtigungsfehlern **nur** die eng definierte neue Workspace-ACL prüfen; niemals allgemeine Admin-/Trading-Rechte vergeben.

### Beweisstatus

- `USER_APPROVAL=PASS` (nur Workspace/Modify)
- `REVIEWED_SOURCE_MERGED=PENDING`
- `NTFS_ORIGINAL_WINDOWS_GUI_ACK=PENDING`
- `RESTRICTED_WORKSPACE_WRITE_HOST_ACK=PENDING`
- `TRADING_WINDOWS_ADMIN_RIGHTS=NOT_GRANTED`
