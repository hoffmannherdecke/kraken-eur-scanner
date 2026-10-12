# V2R4 → V3: Auftrag 11.10.2026 – echtes Tagesurteil, neue Early-Review-Hypothese und Paper-Cutover-Gate

## Aktueller statt angenommener Betrieb (read-only, 11.10. ca. 19:47 UTC)

Supabase `public.paper_series`: **genau eine operative ACTIVE Paper-Serie** `PAPER-V2R4-20261009T110135Z`, Revision `V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION`; Vorgänger `PAPER-V2R4-20261007T184255Z` ist `technical_closed`; **V2R3-CLEAN ist seit dem 7.10. `closed_complete`**. Ein behauptetes heutiges „V2R3“ ist daher ein **Namens-/Versionierungsirrtum**, nicht die echte laufende Strategie. **Keine** Datensatz-/Runtime-Umschreibung.

Direkte Tagesauswertung **Europe/Berlin 11.10. bis Abfrage ca. 21:47 Uhr**, 420 neue V2R4-Erstkandidaten: 238 initial WAIT, 182 initial REJECT, **0 BUY**. 40 tatsächlich ausgelöste lokale Modell-Nachprüfungen, davon **38 nachträglich `EXTENDED`**, nur 1 CONTINUITY und 1 NONE; weitere **189 `V2R4_WAIT_EXPIRY_V1`**. Bei **0/420** ist im `payload.decision.decision_context` `candidate_entry_evidence` strukturiert mit geschlossenem 1/5/15m OHLC/ATR/Stop eingefügt; **0/420** ausgegebene nicht-null `stop_eur` der ersten Modellentscheidung. `reason_codes` häufig `EXTENDED_MOVE`, `REMAINING_MOVE_UNVERIFIED`, `INSUFFICIENT_REMAINING_MOVE_EVIDENCE`, `VOLUME_CONFIRMATION_MISSING`, `LATE_ENTRY_RISK`, `STRUCTURAL_STOP_UNAVAILABLE`, `ATR_STOP_UNAVAILABLE`, `SPREAD_AND_FEES_HIGH`. Reason-Synonyme sind nicht disjunkt, positive Codes wie `SPREAD_ACCEPTABLE` dürfen nicht als Ablehnungsgrund gezählt werden.

**Befund:** Diese nicht gekauften 420 waren nicht automatisch verlorene profitable Trades. Aber strukturell fehlender Coin-PIT zum Modell, bei 38/40 Rechecks erneute `EXTENDED`-Klassifikation und 189 WAIT-Expiries sind echte, erneut reproduzierte **Konversions- und Datenflussprobleme**. Die frühere V2R3-/V2R4-Analyse, 12 historische Fallpaare mit sechs Verlustkontrollen und die 08.–10.10. Rebound-Cohorts bleiben Bestandteil der **bestehenden** Lernbasis, nicht nochmals separat zu scannen.

## V3-Auditmatrix – was wirklich korrigiert ist und was nicht

| Problem | Vorhandener Zustand / jetzt adressiert | Ergebnis / Grenze |
| --- | --- | --- |
| Coin-spezifische Kraken Spot EUR PIT 1m/5m/15m, ATR, Strukturstop | `successor_coin_entry_evidence_v1.py`, `v3_entry_handoff_probe.py`, geschlossene Frame-/known_at-Checks und P4 Vollvalidator sind inaktiv vorhanden; fünf echte V3-P3-WAIT-Modellfälle mit Daten bereits beobachtet | **FORSCHUNGSWEG VORHANDEN, echter V3-Paper-Consumer/Writer noch NICHT produktiv eingebunden**. Der V2R4-Fehler 0/420 bleibt in seiner eingefrorenen Strategie; V3 muss Input *am wirklichen künftigen Full-Model-Consumer* vor V3-Paper-Aktivierung beweisen |
| Fehlende Ablehnungsphasen/8 P3-Checks/HTTP-Ankunft/WAIT-Trigger | PR #189 `v3_p3_future_diagnostics_offline_v1.py` plus PR #192 strikter WAIT-Vertrag; inkl. Zeit-/Watch-Receipts | **INAKTIV/OFFLINE**, aktuell kein automatisches persistentes V3-Kandidaten-/P4-Journal, kein V3-Folgepfad. Muss in künftigem V3-Writer und Cloud-Ledger dauerhaft gespeichert werden |
| 751 durch technischen V2R4-Serienwechsel unvollständige 24h-Outcomes | historische Lücke aus PR #191 erkannt: 751 ohne 24h, darunter 358 mit 12h, 393 ohne beides | **NICHT BEHOBEN**. Ein eigenständiges Reife-/Followup-Continuity-/Censoring-Gate muss vor der nächsten echten Paper-Serienrotation physisch verifiziert werden; keine stille Veränderung eingefrorener älterer Daten |
| Späte WAIT-Bestätigung führt zu `EXTENDED` | Historisch 153/164 Trigger-Rechecks `EXTENDED`, heute 38/40 | **HEUTE NEU ALS V3-P3-FRÜHERE RESEARCH-REVIEW-POLICY IMPLEMENTIERT:** `v3_p3_early_5m_continuity_research_v1.py`, bei originaler frischer CONTINUITY/WAIT oder REJECT plus *neu geschlossener 5m-Kerze* nach Signal, zulässiger alter geschlossener 15m-Basis, 5m-Volumen unverändert >=1.2, engem Spread, anti-chase, Stopreferenz, PIT-Zeiten. Alte Standard-P3 verlangte erst neue geschlossene 15m-Kerze. **Eine einzige Policy-Änderung: früherer Review-Zeitpunkt, nicht automatisch BUY.** P4 ist für die neue eng definierte Statusfamilie geöffnet, zwingt echtes Modellurteil, Stop unter Ask, Stage2 über Ask und 0,60% pro Seite plus Spread/Slippage. Offline Positiv-/Negativtests, keine Modell-Ausgaben oder Papierstrategie noch aktiviert |
| Historische Daten in wirtschaftlicher Entscheidung verwerten | Zwölf Fälle PR150/PR151/PR192 mit absichtlich auch negativen Kontrollen geschlossen; 08.–10.10. Crash/Rebound PR191 | Verifizierte historische 24h-MFE/MAE/Close helfen Ursachen, **keine** realisierte Netto-P&L. Vor echten V3-Resultaten 6h/24h/ggf.72h Pfade inkl. Stop-vor-Ziel und Stage2-Fills erfassen; reale False-BUYs und verhinderte Verluste ausweisen |
| P5/H1/H3/H6/Work/GitHub | Bereits vorhandener 10:15 Work und 2h-Quellen/Regime Owner sowie serienbezogene GitHub-Notifications, Meilenstein-/Completion-Gates | Versionslogik aus echten `paper_series` statt Verwechslung V2R3/V2R4; keine Wiederbelebung alter V2R3-Workflows, H3/H6 bleiben inaktiv, keine neuen Schedules. Work-Aufgabe wird **nur als dynamisch datengetriebener Followthrough** aktualisiert |

## Sicherheits-/Abnahmeentscheidung für den beantragten V3-PAPER-Start

Die **Nutzerfreigabe für einen kontrollierten V2R4→V3-Paper-Wechsel** liegt vor. Eine bereits laufende V2R4-Serie lediglich per SQL auf `closed` zu setzen, während die Mini-PC-Tasks weiterhin schreiben, würde **Doppel-Writers/inkonsistente Daten erzeugen**. Wir dürfen auch die alte **V2R4 technische Rotations-Edgefunktion** nicht als V3-Strategie-Release missbrauchen.

**Verbindliche vorbereitete Übergabe aus dem schon bestehenden `docs/v3-controlled-paper-cutover-20261011.md` (Schritte A–D):**

1. Echten V3-Kern inklusive lokaler Journal-/Cloud-Persistenz, richtigen Modell-PIT/Stop/Stage2-Entscheidungen, Watch-/6h/24h-Followups, namentlichem Versions-/Code-Fingerprint **physisch auf Mini-PC** nachweisen. Ein nur offline geprüfter früherer P3-Hint und inaktive P4-Verträge reichen **nicht** für einen Paper Writer. Mindestens ein echter kosten-/risk-validierter modellbasierter BUY-Pfad und repräsentative Negativkontrollen erforderlich, bevor sichere Paper-Release-Bedingungen erfüllt sind. Zusätzlich Daten-/Followup-Erhalt über technische Rotation.
2. Code/Strategie/DB-/GitHub-/Work-/Mini-PC-Schnittstellen mit einem einzigen V3 `V3_RELEASE_ELIGIBLE` Beleg signieren/ACK, genau **eine** aktive Strategie-Serie.
3. Einmaliger **physischer Cutover mit Rückweg**: lokale V2R4-Neuaufnahme am Mini-PC stoppen und Supervisor-Selbstheilung sperren, bis tatsächliche Stop-ACK und alle alten Child-Prozesse quittiert sind; offene Alt-WAIT/Positionen/Followups erhalten; danach atomar Cloud-Transition und genau einen V3 Writer einschalten. Erst **danach** GitHub/Work-Benachrichtigungen auf V3 aktiv umstellen, Cloud-Readiness-ID/Version prüfen.
4. **Post-ACK**: Supabase exakt eine aktive V3-Serie, V2R4 keine neue Evaluation, V3 End-to-End 1 echter neuer Kandidat, lokaler Owner/Cloud/Journaling/Watch/6h/24h, Slack/Alerts und Rollback geprüft. Fehlt irgendein Gate = `V3_PREPARED_INACTIVE_RELEASE_BLOCKED`, bisherige V2R4 **nicht** ausschalten.

**Resultat dieses PR:** Eine zusätzliche chancenorientierte, trotzdem kontrollierte **inaktive V3-P3-Early-5m-Option** ist implementiert; Tages-Ursachen und unbehobene Telemetrie-/Cutover-Lücken sind offen ausgewiesen. **Kein physischer Cutover ausgelöst, kein neuer Modell-HTTP, keine Supabase-Datenmutation, keine echte Paper-Order, kein Work-Schedule hinzuerfunden.** Der nächste echte Schritt ist die Herstellung und Verifikation des Full-Consumer→Paper-Writer samt Followup-/Cloud-Gates; nicht ein weiterer beliebiger 5er Sonntags-Marktcheck. Paper soll ausdrücklich ausprobiert werden, aber **nicht mit falschem Übergabe-/Ertragsnachweis**.


## Nachtrag 12.10.2026, 16:22:28 UTC – aktuelles, einheitliches V2R4-Abschlussbild

**Dieser Nachtrag ist KEIN zweiter 72h-Review.** Das wirtschaftliche Original-Review und die Lernübergabe vom 10.10. bleiben maßgeblich; hier ist nur die mit einer einzigen read-only Supabase-Abfrage erneut erhobene vollständige V2R4-Strategieepoche (zwei technische Abschnitte, kein Strategie-Reset) abgebildet. Werte entwickeln sich bis zum physischen Intake-Stopp weiter.

| Aktueller V2R4-Nachweis | Wert |
| --- | ---: |
| Kandidaten-Outcomes / EUR-Paare | 2.562 / 102 |
| Initial protokollierte WAIT / REJECT / unbekannt | 1.608 / 952 / 2 |
| WAIT→REJECT / WAIT-Expiry-Kind / lokaler Trigger-Recheck-Kind | 1.590 / 1.393 / 201 |
| Noch WAIT_PENDING im Followup / aktuelle WAIT-Entscheidungen | 18 / 17 |
| Vollständig gereifte 24h-Opportunity-Pfade | 1.221 |
| 24h-MFE mindestens +5% / MAE höchstens −5% / beide Extreme | 589 / 534 / 191 |
| Erstentscheid mit strukturiertem Coin-PIT-Entry-Evidence-Feld / Stop-EUR-Feld | 0 / 0 |
| BUY / Paper-Trade-Ergebnisse | 0 / 0 |

Die WAIT-Expiry-, lokale Recheck- und Pfad-Kategorien **nicht blind als disjunkte BUY-Entscheidungen addieren**. Model Invocation Events melden keinen REVALIDATION-Phase-Eintrag, obwohl 201 Ereignisse ein lokales Trigger-Recheck-Kennzeichen tragen: unterschiedliche Telemetrieebenen, kein Beweis für 201 Modell-HTTP-Aufrufe und kein Beweis für keine lokalen Rechecks. Retrospektive 24h-MFE sind **keine** realisierten Gewinne; 191 Pfade hatten sowohl +5%-Hoch als auch −5%-Tief, bei unbekannter Reihenfolge, Stop-Realisierung und Slippage.

**Verbindliche wirtschaftliche Disposition:** V2R4-Wirtschaftlichkeit nicht nachgewiesen, weitere bloße Null-BUY-Sammlung nicht als Fortschritt zählen. Das im aktiven Supabase-Segment erreichte alternative Abschlussgate (completion_ready und intake_should_stop) legitimiert **keinen** automatischen Stopp, keinen V3-Paper-Cutover und keine Auszahlung. Der bestehende 10:15-Work- und Milestone-Owner sowie der bereits vorbereitete V3-PIT-Full-Model-/Stop-/Stage2-/Kostenvergleich bleiben zuständig. Nur echte geschlossene Kraken-EUR-1m/5m/15m-Frames mit Known-at, gleicher Pair-/Zeitpunkt-Baseline, Gebühren 0,60% je Seite, Spread/Slippage, Stop-vor-Ziel und späterem 6h-/24h-Outcomepfad zählen. H10/H3/H6 keine automatische BUY-Stimme. Der SHA-gepinnte V3-28h-Watcher endet erst am 13.10.2026 um 14:00:12 MESZ; kein vorzeitiger Abschluss. V2R4 aktive Runtime und Followups bleiben unverändert, Work-ACK nicht erfunden.

