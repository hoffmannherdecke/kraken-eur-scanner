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
