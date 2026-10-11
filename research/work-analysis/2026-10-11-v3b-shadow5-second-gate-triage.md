# V3-B Second-Shadow-5: sieben Einzelsignale und die UNKNOWN-Prüflücke (11.10.2026)

## Tatsächliche Evidence, keine erfundene Vollmodellentscheidung

**Quelle:** unmittelbar nach dem zweiten abgeschlossenen Mini-PC-Einmalversuch vom Nutzer übermitteltes Foto der rein lesenden PowerShell-Projektion aus `%USERPROFILE%/Trading/Research/v3-b-shadow5-http10-20261011-run2.json`. Die Protokolldatei selbst liegt lokal und wurde **nicht** als Roh-Datei eingelesen. Der Lauf ist geschlossen: `cases=5`, `completed_matched_reviews=0`, `model_http_attempts_reserved=0`, `paper_changed=false`, `orders=0`.

| Pair | finaler Second-Leg-Hinweis | `eligibility_checks` | Geschlossene 15m-Bars | Belegte Einzelchecks |
|---|---|---:|---:|---|
| EIGEN/EUR | `UNKNOWN_REQUIRED_PIT_OR_STRUCTURE_EVIDENCE` | 4 | 21 | Alle sieben Werte `null` (Berechnung nicht erreicht oder abgebrochen) |
| BAT/EUR | `UNKNOWN_REQUIRED_PIT_OR_STRUCTURE_EVIDENCE` | 4 | 21 | Alle sieben Werte `null` |
| TIA/EUR | `SECOND_LEG_CONDITIONS_NOT_CONFIRMED` | 5 | 21 | **false**: `closed_reclaim_above_prior_base_high`, `existing_v2r4_volume_confirmed`, `fresh_five_minute_continuation`; übrige Einzelchecks im letzten Snapshot true |
| ARB/EUR | `SECOND_LEG_CONDITIONS_NOT_CONFIRMED` | 5 | 21 | dieselben drei nachweislich falschen Bedingungen; übrige true |
| AERO/EUR | `UNKNOWN_REQUIRED_PIT_OR_STRUCTURE_EVIDENCE` | 6 | 21 | Alle sieben `null` |

**Bei allen fünf Fällen** meldete das Journal `required_coin_frames["1"|"5"|"15"].status=VALID`, `reason` leer. Hieraus folgt: kein belegter Totalausfall der 1/5/15m Kraken-Kerzendaten. Die oben genannten `UNKNOWN`-Fälle können an **nachgelagerten Pflichtfeld-, Verhältnis-, Zeit-/Struktur- oder Tickerchecks** scheitern; die ursprüngliche Laufzeit hat die konkrete Exception/Phase nicht differenziert und deshalb alle sieben booleschen Unterchecks `null` gespeichert. Nicht behaupten, die konkrete unbekannte Ursache nachträglich zu kennen.

Der korrigierte PR-#173-Recheck wurde in diesem zweiten Lauf real genutzt (vier bis sechs Eligibility-Prüfungen pro Ursprung); der ursprüngliche frühe Einmalverbrauchsfehler erklärt das Ergebnis dieses zweiten Laufs daher nicht allein. Diese Stichprobe belegt nicht, dass ein Second-Leg-Ansatz über den gesamten Markt nie funktioniert; sie belegt jedoch, dass **hier** null E2E-Modellvergleiche, null Paper-BUY und null ökonomische Verbesserung nachgewiesen wurden.

## Präzise sicher reproduzierbare technische Fehlklassifikation

In `paper_evaluator/successor_coin_entry_evidence_v1.py` gilt ein 5m-Kraken-Kerzenframe bei abgeschlossenem, zusammenhängendem OHLC als `VALID`, wenn Vorvolumen > 0 ist. Der korrekt berechnete Wert `volume_ratio_prior_5=0.0` bei 0 Volumen in der letzten geschlossenen Kerze ist dabei **zulässig und gültig** (Baseline-Vorvolumen > 0). Die ursprüngliche Second-Leg-Funktion verwendete für das Volumenverhältnis dagegen `_finite_positive()`, die **0.0 ablehnt** und mit einem verschluckten `ValueError` in `UNKNOWN_REQUIRED_PIT_OR_STRUCTURE_EVIDENCE` umschaltet. Deshalb ist ein zweifellos unbestätigtes Volumensignal fälschlich als Datenlücke darstellbar. Ob dieser spezifische 0.0-Fehler in EIGEN, BAT oder AERO eingetreten ist, bleibt ohne ursprüngliche preisfreie Diagnose **unbewiesen**.

**Zulässige inaktive Korrektur:** 5m Ratio braucht **endlich und >=0**, fehlend, NaN oder negativ bleibt UNKNOWN, echte 0.0 führt zu `SECOND_LEG_CONDITIONS_NOT_CONFIRMED` und dem gescheiterten vorhandenen `existing_v2r4_volume_confirmed`-Gate. BUY- und STOP-/Stage2-Schwellen, Volumenminimum 1.2, EUR-Spread, ATR/Anti-Chase und Gesamt-V3-Strategie werden **nicht** gelockert. Der generische `UNKNOWN` trägt künftig einen kleinen erlaubten `validation_stage`-Code (z.B. `CORE_PIT_SOURCE`, `CLOSED_BASE_HISTORY`, `CLOSED_COIN_PRICE_ATR_AND_VOLUME`, `FRESH_EUR_TICKER`, `STRUCTURAL_STOP_REFERENCE`), den die vorhandene kompakte Research-Diagnose übernimmt; keine Roh-Exceptions/Preise/Keys/prompts oder Datenrückdatierung.

## Strategische Folgerung und Gate

1. **Keine dritte neue Testkohorte**, keine Wiederholung der verbrauchten First-/Second-Trials, keine Modellkosten, keine Änderung laufender V2R4-Tasks / Supabase PAPER. Nur inaktiver Testcode/Regression und konsistente Projektakte. Negative TIA-/ARB-Reclaim-/5m-/Volumenfilter bleiben als Schutz gegen FOMO gültig, bis eine separat geprüfte, **kausale** Alternative vorliegt.
2. V3 darf **nicht** auf Second-Leg-B reduziert werden. Die bestehenden P2-Fresh-WAIT/TTL-Wiedereintrittshypothesen sowie P3-IGNITION/CONTINUITY/BREAKOUT/REVERSAL und P4-Kosten-/Risiko-/Stop-/Stage2-Validierung bleiben als einheitliche V3-Strategiearbeit vorgesehen. Erst mit einer echten Same-Clock-Baseline + aktivierter eigenständiger V3-Full-Review-Entscheidung sind höhere BUY-Raten oder Nettoqualität nachweisbar.
3. V3-Paper-Aktivierung bleibt ausdrücklich **gesperrt**, bis die bereits bestehenden fünf `VERIFIED_PIT_E2E_PASS`-Releasebelege und ein validierter kosten-/risikofähiger Prospektiv-BUY plus echte Mini-PC-/Supabase-Single-Writer-Umstellung vorliegen. Bis dahin V2R4 einzig aktive Paper-Strategie.
4. Bestehender `PROJECT_BACKLOG.md` P1 / `project-current-state.json#pending_strategy_transition.sequence[1]` / bestehender 10:15-Work-Lauf lesen **diesen** Bericht bei künftigem Anlass. Nicht erneut um das gleiche Foto, ursprüngliche Freigaben oder die gleichen Einmaltests bitten.

**Evidenzstufen:** Benutzerfoto = historische bestätigte Statuscodes, echter Marktbeweis nur für TIA/ARB letzten Snapshot; inaktive Regression = programmatische Fehlerkorrektur, KEIN Beweis für die historischen drei UNKNOWN-Cases und KEIN zukünftiger Strategievorteil.
