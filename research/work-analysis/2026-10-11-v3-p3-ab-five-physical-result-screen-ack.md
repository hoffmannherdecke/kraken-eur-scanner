# V3 P3 Standard/Experimental – erster autorisierter physischer Modelltest (11.10.2026)

## Quelle und Belegstatus

- Quelle: vom Nutzer am 11.10.2026 gegen **19:49 MESZ** im Chat bereitgestelltes Foto der **abgeschlossenen Mini-PC-PowerShell**, nicht der JSON-Report selbst. **SCREENSHOT_ACK_ONLY**: das lokale JSON wurde noch nicht technisch eingelesen; Zahlen und alle `WAIT`-Fälle sind anhand der sichtbaren Console-JSON-Zeilen abgelesen.
- Eingesetzter einmaliger Test: **PR #186**, `V3_P3_AB_FIVE_HTTP10_6H_RESEARCH_V1`. Original-Hardcap **5 qualifizierte Setups**, **10 HTTP inklusive Retries**, **360 Minuten maximal**, keine Echtgeldorder, keine V3-Paper-Aktivierung.
- Physischer lokaler Report laut Bild: `C:\Users\ADMIN\Trading\Research\v3-p3-ab-five-http10-6h-20261011.json` (nur lokaler Pfad, keine erfolgte Übernahme in GitHub).
- Abschlusssignal: `V3_P3_AB_FINITE_RESEARCH_RESULT_RECORDED_NO_PAPER_CHANGE`; `status=FINISHED_FIVE_QUALIFIED_OR_SIX_HOUR_WINDOW`; PowerShell-Prompt ist zurückgekehrt. Der Lauf **ist abgeschlossen**, nicht länger aktiv und **darf nicht wiederholt** werden; durch fünf qualifizierte Setups beendet, kein Beweis für eine voll gelaufene sechsstündige Beobachtungsdauer.

## Tatsächlich sichtbares Ergebnis (kein wirtschaftlicher Edge-Nachweis)

| Merkmal | Screenshot |
|---|---:|
| Qualifizierte P3-CONTINUITY-Eintritte für Modellreview | **5** |
| Echtes Modell-HTTP-Budget verbraucht | **5 / 10** |
| Voll-Modell-WAIT nach normalisiertem P4-Validator | **5** |
| Voll-Modell-BUY_SCOUT | **0** |
| Experimental-Inkrementalberechtigung unter Volumen 1.0–<1.2 | **0 / 5** |
| Standardarm unter Volumen ≥1.2 | **5 / 5** |
| Ursprungskandidaten in Diagnose | **38** |
| Ohne Reviewberechtigung | **30** |
| Fehlende/ungültige PIT-Eingaben | **3** |
| Spot-EUR-Paarmetadatenfehler | **0** |
| Virtuelle oder echte Orders | **0** |
| 6h-/24h-Netto-Follow-ups verifiziert | **NEIN** |

Alle fünf angezeigten Cases weisen `eligible_arm=STANDARD` auf. `experimental_status=BASELINE_ALREADY_ELIGIBLE_NOT_INCREMENTAL`, also **keine einzige isolierte Experimental-Extra-Berechtigung**. `full_model_decision=WAIT` und `validated_decision=WAIT` mit `FULL_WAIT_VALIDATED_OFFLINE` für fünf Modell-Reviews; diese belegen einen realen Modell-WAIT-Pfad, **keine echte positive BUY→Stop/Stage2→Netto-Chain**.

Im Bild ersichtliche Model-Reason-Codes wiederholen u.a. **COST_EDGE_UNCONFIRMED**, **5M_VOLUME_WEAK**, **FEES_REQUIRE_ROOM_TO_RUN** und **PERSISTENT_6H_CONTEXT**. Keine kausale Zuschreibung, bevor das Original-JSON und die tatsächliche Herkunft dieser Attribute ohne Lookahead ausgewertet werden.

## Kanonische Disposition und unmittelbare erlaubte Folgearbeit

1. `CLOSED_SCREENSHOT_ACK`, **Freigabe verbraucht und kein Auto-Retry**, nicht erneut den alten V3B- oder diesen P3-Runner nutzen. Auch die ungenutzten fünf möglichen HTTP-Versuche sind **kein übertragbares neues Budget**.
2. **Einzige nächste aussagekräftige Aktion:** den *existierenden* lokalen Report `v3-p3-ab-five-http10-6h-20261011.json` **read-only** einsehen oder vom Nutzer hochladen lassen, um alle fünf P4-/Model-Reasons, 30 strukturelle Non-Reviews, 3 Datenfehler sowie exakte Zeit-/Candidate-Provenienz zu prüfen, ohne neue Modellaufrufe. Dabei mögliche Spannungen zwischen strukturell bestandenem 5m-Volumengate und Begründungen `5M_VOLUME_WEAK` explizit untersuchen; noch keine voreilige Regeländerung ableiten.
3. Der erste echte wirtschaftliche **gepaarte Standard-vs-incremental-Experimental-Vergleich** ist weiterhin **NICHT belegt**; es gab **0** Experimental-Inkrementalfälle und 0 BUY. Ein einzelner zusätzlicher Shadow/Modelversuch oder neue Volumengrenze braucht neues Evidenz-/Freigabegate, nicht automatisch aus diesem Report.
4. **V2R4 ist einzige aktive Paper-Strategie**, physischer Single-Writer und bisherige Followups bleiben unverändert; P1/P2/H3/H6 inaktiv; keine Echtgeldausführung.
5. Dieser Befund wird unter **dem bestehenden** V3 P0/P3/P4/P8 Owner, `PROJECT_BACKLOG.md` und dem regulären 10:15-Followthrough berücksichtigt. **Kein** neuer Scheduler, keine eigenständige Erinnerung und kein zweites Backlog.

**Evidenzgrenze:** Das Foto dokumentiert den tatsächlichen physischen Abschluss und aggregierte Case-Angaben. Bevor maschinelle oder wirtschaftliche Detailanalysen als `VERIFIED_JSON` markiert werden, muss die echte lokale Reportdatei gelesen werden. Mock-/CI-Fälle aus #186 dürfen nicht als echtes P&L zählen.
