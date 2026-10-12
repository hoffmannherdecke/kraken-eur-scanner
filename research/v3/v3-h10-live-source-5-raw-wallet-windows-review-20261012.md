# V3 H10 Quellen-Owner: fünf historische *Rohfilter*-Fenster gezielt untersuchen

**Stand:** 12.10.2026 ca. 11:32 UTC, nur READ-ONLY Supabase-Abfragen; keine neue Capture-Task, Strategie-/Paper-/Cloud-Mutation. Diese fünf Zeitfenster sind **weder authentifizierte Source-Catalysts noch Trades, PnL oder reale Modellentscheidungen**.

## Beobachtete Daten und Zählung

H10 läuft bereits erfolgreich über `GITHUB_BOOTSTRAP_30M` (401 Capture-Batches, 1.430 Fill-Rohereignisse; 48 Batches in den letzten 24 Stunden). `v3_h10_asset_consensus_30m_history` enthält 810 nach Coin gruppierte 30-Minuten-Zeitfenster ab 02.10.2026. Insgesamt 11 Fenster mit mindestens drei unabhängigen Wallets, **5** mit zusätzlich mindestens drei bullish Wallets, null bearish Wallets und Netto-Positionszuwachs der Quelle ≥ 10.000 Quote-Einheiten; **0** solche 3-Wallet-Fenster in den letzten 24 Stunden.

| Coin | 30-Minuten-Fenster (UTC, 08.10.2026) | Wallets (bullish/bearish) | Netto-Quote, gerundet | letzte bekannte Fill-Zeit (UTC) |
| --- | --- | --- | ---: | --- |
| BTC | 03:00 | 3 (3/0) | 206.501,59 | 03:23:13.381 |
| BTC | 04:00 | 3 (3/0) | 723.284,30 | 04:25:47.806 |
| BTC | 13:30 | 3 (3/0) | 4.783.958,35 | 13:59:12.794 |
| ZEC | 15:00 | 3 (3/0) | 123.617,95 | 15:24:00.506 |
| BTC | 15:30 | 3 (3/0) | 51.387,00 | 15:38:05.533 |

**Wichtige fachliche Einschränkungen:** Quote-Wert ist nicht automatisch ein EUR-Kaufgewinn. Die View liefert `last_activity_time` der beobachteten Fills, **nicht den belegten ursprünglichen `known_at`-Erkennungszeitpunkt**. Ebenso hat die View keine unabhängige Self-Dealing-/Related-Party-Attestation, keine coin-spezifisch überprüfte Kraken-Online-Spot-EUR-Metadatenhistorie, keine damaligen frischen 1/5/15-Minuten-Kerzen, keine echten Modell-/P4-Prüfungen, keine Orderbuch-Ausführbarkeit und keine 6-/24h-Nettoergebnisse. Die fünf Überschreitungen sind **nur Rohfilter-/Nachforschungsziele**. Vier BTC-Fenster dürfen nicht automatisch als vier voneinander unabhängige Chancen gezählt werden.

## Welche Arbeit ohne neue Systeme sinnvoll ist

1. Die bestehende H10-Collector-Ausführung `GITHUB_BOOTSTRAP_30M` und `public.v3_h10_capture_batches` mit den ursprünglichen `first_seen_at`-/`created_at`-Nachweisen verbinden. Die frühestmögliche legitim bekannte Originalzeit (PIT) ist maßgeblich; niemals das spätere Roh-Signal auf die frühere Fill-Zeit rückdatieren.
2. Nur diese **fünf** bereits auffälligen historischen 30-Minuten-Fenster gegen `v3_h10_fill_events` und die getrennte Wallet-Kohorte prüfen: tatsächliche eigenständige Wallets, BUY-/SELL-Zuordnung, Gegenparteien-/Self-Dealing-Nachweise, anwendbare Quote-Einheiten, transparente Datenlücken und Abdeckung der Originalquelle. Bis dahin `H10_PIT_CONTEXT_ONLY` und `SOURCE_CATALYST_NOT_PROVEN`.
3. Falls nach PIT-/Self-Dealing-Prüfung ein Fenster standhält: anschließend getrennt, rein *prospektiv* den im PR #228 implementierten H10-Source-Owner-Signierer auf dem tatsächlichen GitHub-Owner prüfen; kryptografischer Owner-Status ist dann noch kein Modellbudget, BUY oder Paper-Freigabe. Historische 08.10.-Fenster niemals am 12.10. nachsignieren und als zeitgenössische V3-Trades ausgeben.
4. Kein neuer Wallet-Poller, GitHub-Cron, Windows-Task, Cloud-Edge-Dienst oder Work-Lauf nur für diese Auswertung. Vor dem geplanten 28h-Watcher-Ende 13.10.2026 14:00:12 MESZ bleiben die neun SHA-gepinnten Dateien und V2R4 vollständig unverändert.

## Einmalige reproduzierbare Auslese (read-only)

```sql
select coin,cohort_role,window_start,independent_wallets,
       bullish_wallets,bearish_wallets,net_exposure_change_quote,
       gross_fill_notional_quote,first_activity_time,last_activity_time
from public.v3_h10_asset_consensus_30m_history
where independent_wallets>=3
  and bullish_wallets>=3
  and bearish_wallets=0
  and net_exposure_change_quote>=10000
order by last_activity_time;
```

**Evidenz-Gate:** Unter den vorhandenen bestehenden Work-/Milestone-Controllern nur echte `first_seen`-Originalbelege und Self-Dealing-Lücken nachverfolgen. H10-Rohfilter → Original-PIT-Audit → echter überprüfter Source-Event → externe Owner-Key-/HMAC-Kontrolle → ein einziger künftiger V3-Writer mit Cloud-ACK → getrennte Paper-/Modellfreigabe. Nicht alle Schritte als „bereits erledigt“ markieren.

## 12. Oktober 2026: Original-PIT-Audit nach PR237

**Methode:** Unveränderte vorhandene Supabase-Tabellen/Views nur mit `SELECT` befragt; bestehende H10-Owner-Topologie und inzwischen gemergtes Anti-Flickenteppich-PR237 berücksichtigt. Keine neue H10-Runtime/Quelleninstanz installiert. Rohereignisse wurden zu den fünf exakten Coin-/PRIMARY-/UTC-Fenstern aus diesem Bericht zugeordnet, danach über `v3_h10_wallet_asset_5m` als unabhängiges Aggregat gegengeprüft.

| Fenster (UTC 08.10.) | verschiedene aggregierte Wallet-Adressen | 5m-Aggregat-Fill-Zählungen | originale Fill-Zeilen in `v3_h10_fill_events` | Ergebnis |
| --- | ---: | ---: | ---: | --- |
| BTC 03:00 | 3 | 12 | 0 | Original-PIT nicht nachweisbar |
| BTC 04:00 | 3 | 16 | 0 | Original-PIT nicht nachweisbar |
| BTC 13:30 | 3 | 29 | 0 | Original-PIT nicht nachweisbar |
| ZEC 15:00 | 3 | 16 | 0 | Original-PIT nicht nachweisbar |
| BTC 15:30 | 3 | 27 | 0 | Original-PIT nicht nachweisbar |

**Herkunft:** Die View `v3_h10_asset_consensus_30m_history` aggregiert die View `v3_h10_wallet_asset_30m_history`, deren Quelle die verbleibenden 5-Minuten-Wallet-Aggregate sind. Die beobachteten 3 Adressen sind Adress-Disjunktheit, **kein** belegter unabhängiger wirtschaftlicher Inhaber und keine Gegenseiten-/Self-Dealing-Attestation. Auch die 12/16/29/16/27 sind Aggregat-Zählungen, keine Original-Event-IDs. In der aktuellen Rohereignistabelle standen 1.523 jüngere Fills, frühester `fill_time` 10.10.2026 14:04:14.883 UTC und `first_seen_at` 10.10.2026 14:26:03.822 UTC; folglich kein Original-`event_id` oder `first_seen_batch_id` zu den fünf 08.10.-Fenstern verfügbar. Die 48 erhaltenen 08.10.-Capture-Batches erfassten im Tagesfeld zusammen 1.970 `fill_events_seen`, **nicht notwendigerweise eindeutige** Fills; daraus lässt sich eine Original-Event-zu-Batch-Zuordnung nicht wiederherstellen. H10 weiter laufend: 403 Batches insgesamt bei der Prüfung, 48 in den vorangegangenen 24 Stunden.

**Disposition/weiterer Gate:** `H10_PIT5_ORIGINAL_PROOF_MISSING`. Kein prospektives damaliges `known_at` aus Fill-Zeit oder aggregiertem Bucket ableiten, kein historisches Signieren, keine FIVE_BUY-, PnL- oder Renditebehauptung. Nicht behaupten, dass eine bestimmte TTL/Retention-Funktion bewiesen ist: Andere Originalarchive oder Workflow-Artefakte wurden hier noch nicht als vollständige Rohdatenquelle überprüft. Der vorhandene H10-Owner soll beim nächsten bereits bestehenden Evidenz-Owner-Gate zuerst **nur lesend** prüfen, ob zeitgenössische, immutable Originalbelege für die fünf Fälle anderswo existieren; wenn nicht, die fünf als ausschließlich retrospektiven Kontext abschließen und **zukünftige** Quellenevents im bisherigen Owner-Prozess erst mit echtem `first_seen`/Batch-/Sender-/Unabhängigkeitsbeleg autorisieren. BTC/ZEC-EUR-Pair-P0, echter Self-Dealing-Ausschluss, Original-Owner-HMAC, aktuelles Coin-Signal, Modellbudget, Cloud-ACK und Paper-/6h24h-Outcome sind eigenständige nachgelagerte Gates. Keine aktive V3-Ausführung, kein neuer Poller, keine Änderung am V2R4 oder an neun SHA-gepinnten 28h-Watcher-Dateien bis 13.10.2026 14:00:12 MESZ.
