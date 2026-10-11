# V3-B Shadow-5: erster physischer Ergebnisbeleg mit fünf Eligibility-Status (11.10.2026)

**Belegklasse:** Nutzer-Screenshot der originalen lokal gespeicherten MINI-PC-Budgetdatei, read-only PowerShell-Projektion. Kein Rohreport-/Prompt-/Kraken-API-Archiv wurde in GitHub importiert. Die Aussage ist auf sichtbar belegte Felder begrenzt.

## Tatsächlicher EINMALIGER Versuch

- Vorprüfung: 20 zu diesem Zeitpunkt lokal vorhandene V2R4-`EXTENDED`-Ursprungskandidaten, 0 KI-Anfragen, V2R4-Paper unverändert.
- Benutzer startete `tools/run-minipc-v3-b-shadow5.ps1 -Execute -WaitMinutes 90`; tatsächliches Terminal-`V3_B_SHADOW5_SUMMARY`: `cases=5`, `completed_matched_reviews=0`, `model_http_attempts_reserved=0`, `orders=0`, `paper_changed=false`, Ende `WINDOW_ELAPSED_OR_FIVE_ORIGINAL_CASES_REVIEWED`. Das ist **KEIN** positives Modell-/Strategie-/Paper-E2E.
- Der Nutzer las anschließend **nur aus dem unüberschriebenen Originaljournal** `%USERPROFILE%/Trading/Research/v3-b-shadow5-http10-20261011.json` die fünf lokalen Fälle:

| Originalbezug | `second_leg_eligibility_status` | `status` | `failure_type` |
|---|---|---|---|
| INJ/EUR | `SECOND_LEG_CONDITIONS_NOT_CONFIRMED` | `ELIGIBILITY_CHECKED_NO_BUY` | leer |
| BAT/EUR, Fall 1 | `SECOND_LEG_CONDITIONS_NOT_CONFIRMED` | `ELIGIBILITY_CHECKED_NO_BUY` | leer |
| BAT/EUR, Fall 2 | `SECOND_LEG_CONDITIONS_NOT_CONFIRMED` | `ELIGIBILITY_CHECKED_NO_BUY` | leer |
| TIA/EUR | `UNKNOWN_REQUIRED_PIT_OR_STRUCTURE_EVIDENCE` | `ELIGIBILITY_CHECKED_NO_BUY` | leer |
| AERO/EUR | `SECOND_LEG_CONDITIONS_NOT_CONFIRMED` | `ELIGIBILITY_CHECKED_NO_BUY` | leer |

**Interpretation:** 5 einzelne originale Kandidaten, **4 verschiedene EUR-Paare**. BAT zweimal sind getrennte Originalereignisse, **nicht** zwei unabhängige Coin-Kontrollen. Die 4 NOT_CONFIRMED besagen, dass mindestens einer der sieben definierten Second-Leg-Unterchecks nicht bestand; **welche genau, ist nicht rekonstruierbar**, denn die ursprüngliche PR-#172-Runtime speicherte nur `hint.status`, nicht `hint.checks`. TIA wurde als unbekannte **erforderliche PIT-/Strukturevidenz**, nicht als wirtschaftlicher Markt-REJECT, markiert. Welches Datum/Feld/15m-Bar/ATR/Volume fehlt, ist ohne zusätzliche unabhängige at-time-Evidenz nicht belegbar. Kein FAIL- oder Exception-Typ aus der obersten Shadow-Runner-Ebene. Ein solches `UNKNOWN` darf nicht als ein gegen den Markt bewiesenes Negativsetup gewertet werden.

## Tatsächlich nachgewiesene Root-Cause und sicherer Folgeweg

1. **Codefehler des ursprünglichen Pilot-Controllers**, bereits per [PR #173](https://github.com/hoffmannherdecke/kraken-eur-scanner/pull/173) korrigiert: Kandidaten wurden sofort beim ersten Eligibility-Check endgültig als verbrauchte Originale gezählt; nach fünf Untersuchungen war das nominelle 90min-Fenster beendet, auch ohne frische Bestätigung. Neue inaktive Codevariante erlaubt erst ab 75m reife Originale und bis 4h, sowie dieselben Originale erst nach neuer geschlossener 15m-Kerze erneut zu prüfen. Die Korrektur ändert rückwirkend **nicht** die fünf bereits beobachteten Fälle.
2. **Diagnoselücke im ursprünglichen Einmaljournal:** keine booleschen Unterchecks und keine neutralen Snapshot-Statusfelder gespeichert. Eine separate **nur inaktive** Ergänzung soll bei zukünftigen ausdrücklich autorisierten Untersuchungen strukturierte boolesche `checks`, die erforderlichen 1m/5m/15m-`status/reason`-Felder, die Zahl/letzte Zeit abgeschlossener 15m-Kerzen und den jeweiligen Eligibility-Fachstatus speichern; keine Rohdaten/Schlüssel/Modellantworten/Trades. So kann die nächste technische Datenlücke ohne neue Generalanalyse erkannt werden.
3. **Kein automatischer Neustart / kein Budget-Recycling:** Eine zukünftige zweite, neue, eng begrenzte Kohorte braucht eine neue konkrete Nutzerentscheidung; das alte Journal bleibt exklusiv, geschlossen und unverändert. Da es bisher 0 echte Modell-Aufrufe gab, ist eine neue Probe eventuell sinnvoll, aber die null verbrauchten Credits sind **keine** automatische Freigabe für einen neuen Versuch.
4. **Kein Strategie-/Live-Release:** weiterhin keine echte Second-Leg-Full-Modellvergleichskohorte, kein nachweisbar valider BUY/Stage2/Stop/Exit, kein nach Kosten bereinigtes Paper-Outcome; `V3_PAPER_ACTIVE_VERIFIED` weiterhin gesperrt. Laufendes V2R4, H3/H6, bereits existierender GitHub/Work-Takt und MINI-PC-Services nicht ändern.

**Dauerhafter Owner:** vorhandenes `PROJECT_BACKLOG.md` P1/V2R4→V3 und `project-current-state.json#pending_strategy_transition.sequence[1]`. Bei künftigem Work-Read darf der Erstlauf nicht als `MINIPC_PREFLIGHT_PENDING`, `0/5` oder `SUCCESSFUL_5_MODEL_TEST` bezeichnet werden. Die nächste anstehende **Entscheidung** ist, ob die korrigierte, besser dokumentierte V3-B-Routine in einer **neuen begrenzt genehmigten Kohorte** getestet werden soll – nicht dieselbe Runde noch einmal oder den alten Report überschreiben.
