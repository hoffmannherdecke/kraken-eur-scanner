# V3 28h-Festfenster: prüfbarer Abschlussbericht ohne neue Laufzeit (13.10.2026)

**Status 12.10.:** Auftrag vorbereitet und offline getestet, NICHT automatisch ausgeführt. Die produktive V2R4-Paper-Serie ist unverändert aktiv; weder der SHA-gepinnte 28h-Watcher noch dessen angeheftete 9 Quelldateien werden durch diesen Bericht geändert.

## Verbindliche Zeit und unabhängige Eingangsdaten

- Ursprüngliches festes Fenster endet am **13.10.2026 12:00:12.2795431 UTC / 14:00:12 MESZ**. Nicht verlängern, nicht zurückdatieren.
- Im bestehenden 10:15-Work- und Milestone-Controller die Echtzeitbelege nach Ende des Fensters abholen, sobald ein geeigneter Lauf/Anlass verfügbar ist. **Achtung:** Der Lauf am 13.10. um 10:15 MESZ ist *vor* dem Ende; ihn nicht als 14:00-Abschluss interpretieren. Kein zusätzlicher Scheduler, keine extra ChatGPT-Erinnerung.
- **Einzeln und unverändert** aus Supabase lesen: `event_id`, `series_id`, `content_sha256`, vollständiger `payload` aus `public.v3_paper_event_receipts` für die Serien `PAPER-V3-CANARY-20261011` und `PAPER-V3-CANARY-WRITER-SMOKE-20261012`. Abgeleitete Aggregatzahlen genügen nicht.
- Separat die aktive Serien-ID `public.paper_series where status='active'` abfragen; nur V2R4 aktiv bedeutet weiterhin KEINE V3-Aktivierung.
- Auf dem Mini-PC **read-only** die Originalmanifest-Deadline, Windows-Aufgabenende bzw. keine weiteren unbeabsichtigten Läufe, alle ursprünglichen neun SHA-256-Hashes sowie lokale Capture-/Journal-/ACK-Zähler prüfen. Ein Uhrzeitablauf oder ein `Ready`-Status allein ist kein physischer Stop-Nachweis. Niemals ungeprüft `git pull` auf den geschützten Dateien oder Task neu installieren.

## Bereits vorbereitete automatische *Berechnung* (kein automatisches Starten)

Modul `paper_evaluator/v3_paper_post_canary_evidence_verdict_v1.py`, reine Funktion `verdict(cloud_rows=..., as_of_utc=..., observer_deadline_utc=..., active_paper_series=..., physical_observer_end_ack=...)`.

Read-only SQL für den bestehenden Supabase-Zugang:

```sql
select series_id, event_id, content_sha256, payload
from public.v3_paper_event_receipts
where series_id in (
    'PAPER-V3-CANARY-20261011',
    'PAPER-V3-CANARY-WRITER-SMOKE-20261012'
)
order by series_id, source_known_at, event_id;

select series_id, status
from public.paper_series
where status = 'active';
```

**Ergebnisfelder:** zwei getrennte Kohorten; tatsächliche Event-ID-/Zeit-/Paarprüfung; für jede Originalkandidaten-ID `6h`, `24h`, `72h` = `not_yet_due`, `due_missing_or_pending`, `censored` oder `mature_complete`. 72h ist eine separate Nachbeobachtung, **keine neue pauschale Pflichtwartezeit** für den 28h-Abschluss. MFE von `NO_BUY` ist keine ausführbare Netto-Rendite; Preisweg mit Lücken ist nicht `0 EUR`. Die separate technisch erfolgreiche RENDER/EUR-5-Beleg-Kohorte ist kein Ersatz für den laufenden Writer.

## Echte Fälligkeiten aus den aktuellen V3-Cloud-Originalen (12.10.2026)

Diese Zeiten stammen aus den *tatsächlichen* unveränderlichen `SCANNER_CAPTURE.event_time_utc`-Quittungen, nicht aus dem Zeitpunkt, zu dem dieser Bericht geschrieben wurde. Vor Fälligkeit sind fehlende Followups **normal**; danach bleibt die kontrollierte 60-Minuten-Datenrekonvaleszenz getrennt von tatsächlicher Censor-Klassifikation.

| Echter Originalkandidat | Ursprungszeit (MESZ) | 6h fällig (MESZ) | 24h fällig (MESZ) |
| --- | --- | --- | --- |
| EIGEN/EUR | 12.10. 07:25:50.737 | **12.10. 13:25:50.737** | **13.10. 07:25:50.737** |
| ZRO/EUR | 12.10. 08:42:19.706 | **12.10. 14:42:19.706** | **13.10. 08:42:19.706** |

Die bestehende `verdict()`-Auswertung gibt dazu jetzt je Fall `followup_due_at_utc`, `recovery_until_utc`, `watcher_next_unmatured_horizon` und `watcher_due_missing_past_60m_recovery` aus. **Achtung:** Dies sind erwartete Termine, keine bestätigten Ergebnisse; ein späterer Dateneingang darf niemals eine rückwirkend beobachtete Stunde vortäuschen. Solange der reale 28h-Watcher unberührt weiterläuft, kann die Source-Capture normal fortgesetzt werden. Unmittelbar nach Ablauf der Endzeit bleiben 72h-Beobachtungen als separate offene oder zensierte Folgearbeit kenntlich; sie verhindern nicht den 28h-Testabschluss.

## Direkt nutzbarer einmaliger Berichtsbefehl (vorbereitet, ohne Task)

Die reine Python-Funktion aus PR222/223 ist zusätzlich durch `tools/v3-post-canary-evidence-readonly-report.py` per JSON-Eingabe aufrufbar, damit die **bestehende** Work-/GitHub-Projektsteuerung einen vollständigen, nachvollziehbaren Bericht erstellen kann, statt technische Quittungen als wirtschaftliche Erfolge zu interpretieren. **Keine neue Automatisierung:** Der Befehl selbst holt keine Daten, nimmt keinen Datenbankzugriff vor, schreibt keine Dateien, nimmt keine Modellaufrufe vor und aktiviert keine Strategie.

Das JSON-Dokument muss einen **unabhängig live aus Supabase gelesenen** Datensatz enthalten, nicht vorher aggregierte oder nachträglich manipulierte Daten:

```json
{
  "kind": "V3_READONLY_SUPABASE_RECEIPTS_FOR_VERDICT_V1",
  "mode": "READ_ONLY_NO_ACTIVATION",
  "cloud_source_verified_by_caller": true,
  "new_model_budget": false,
  "as_of_utc": "2026-10-13T12:05:00Z",
  "active_paper_series": ["PAPER-V2R4-20261009T110135Z"],
  "physical_observer_end_ack": false,
  "cloud_rows": []
}
```

**Wichtig:** Dieses Objekt ist nur ein Schema-Beispiel; die `cloud_rows` müssen aus obiger echten SQL-Abfrage stammen, die aktive Serie neu abgefragt und `as_of_utc` auf den wirklichen Prüfzeitpunkt gesetzt werden. `physical_observer_end_ack` darf nur `true` sein, wenn der tatsächliche Mini-PC-Aufgabenabschluss separat geprüft wurde. Kein unabhängiger Authentizitätsbeweis entsteht durch bloßes `cloud_source_verified_by_caller=true`.

Mit einem vom vorhandenen Owner bereitgestellten JSON auf Standard-Eingabe:

```bash
python tools/v3-post-canary-evidence-readonly-report.py < actual-readonly-supabase-snapshot.json
```

Das ausgegebene JSON ist **ein Urteil über beobachtete Evidenz**, kein freigebender Release-Token. Existierende Work-10:15- oder Milestone-Controller müssen die Daten selbst über ihre vorhandenen berechtigten Quellen holen und dürfen das Skript nur ausdrücklich und einmalig aufrufen. Der 10:15-Lauf VOR 14 Uhr darf keinen finalen Abschluss behaupten.

## Danach: konkrete Entscheidung ohne verdeckte Freigabe

1. **Technik:** Original-Pins, eindeutige V2R4-Owner-Quelle, echter Task-Stop, Cloud ACKs, unveränderliche Einzel-Quittungen und 6/24h-Abdeckung. Lücken exakt benennen.
2. **Strategie:** kaufbare P4-Entscheidungen, bezahlte Modellanfragen nur sofern neu genehmigt, 0,6 % Taker je Seite und 50+50 EUR sowie Stop/Stage2 und wirtschaftliche Gegenprobe Standard/offensiver V3-Variante. Fehlt diese Evidenz, korrekt **nicht bewiesen**, aber keinen künstlichen weiteren 28h-Lauf starten.
3. **Quellen & Betrieb:** Eigenständige H5/H10/H11-Owner-Authentifizierung (Hash ist keine Authentifizierung), tatsächlich fortlaufender EINE V3-Writer, Re-Start-/Crash-Recovery, Cloud-Replay-ACK und atomischer V2R4→V3-Wechsel bleiben jeweils eigene eindeutige Beweis-/Freigabegates.
4. **Freigabe:** Nie aus einem grünen Report die aktive Paper-Serie, Runtime, Strategie, Berechtigungen oder Modellkosten selbst umstellen; die bestehenden fünf Kausal-/Release-Gates und echte Mini-PC-ACKs sind verbindlich.

**Nächste Aktion:** Die bestehende Projektsteuerung nutzt diesen Report beim nächsten *tatsächlich nach dem Ablauf* möglichen Kontrolllauf. Vor dem Stichtag sind Code, Negativtests, Provenienzschema und Reviewer-Entscheidungsfelder bereits fertig; die realen zukünftigen 24h-Beobachtungen dürfen nicht heute erfunden werden.

## V3-28h-Canary – realer Zwischenbefund 12.10.2026 um 16:28:51 UTC

Read-only in Supabase: echte `PAPER-V3-CANARY-20261011`-Kohorte hat **14** Originalquittungen zu EIGEN/EUR und ZRO/EUR. Beide `FOLLOWUP_6H` sind **CENSORED**, mit gespeichertem Grund `CENSORED_NO_CONTIGUOUS_CLOSED_KRAKEN_1M_PATH`, `path_contiguous_1m_verified=false` und ausdrücklich `NO_BUY_OPPORTUNITY_LABEL_NOT_EXECUTABLE_TRADED_PNL`. Quellenzeit EIGEN **12:30:15 UTC**, ZRO **13:45:15 UTC**. Diese Quelle beweist **weder** handelbaren 6h-Gewinn **noch** 0-EUR-Rendite. Die separate `PAPER-V3-CANARY-WRITER-SMOKE-20261012`-Kohorte enthält **5** RENDER/EUR-Originalquittungen und ersetzt den unvollständigen 6h-Kurspfad NICHT.

24h EIGEN fällig 13.10. **05:25:50 UTC**, ZRO **06:42:19 UTC**, beide bei diesem Snapshot noch nicht fällig. Fixes Original-28h-Ende **13.10. 12:00:12.2795431 UTC / 14:00:12 MESZ**, weder verlängern noch vorher als abgeschlossen bewerten. Das anschließende bestehende 10:15-Work-/Milestone-Gate muss echte individuelle 24h-Receipts, 6h-Censorgründe und die physische Windows-Task-Stopquittung samt neun SHA-256-Pins separat prüfen. Fehlen/Censoring ≠ 0-Rendite. Keine Task-, Mini-PC-, Paper-, V2R4-, H10-, Model-HTTP- oder Schedule-Änderung durch diese Dokumentation.

