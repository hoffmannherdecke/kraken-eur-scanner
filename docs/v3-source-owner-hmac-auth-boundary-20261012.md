# V3 – echte positive H5/H10/H11-Quelle: Owner-Authentifizierung vor dem gemeinsamen Writer

**Stand 12.10.2026: Code vorbereitet und CI-gesichert, keine Live-Owner-Schlüssel ausgegeben, keine echten positiven Quellenereignisse authentifiziert.** V2R4 bleibt einzige aktive Paper-Strategie, die bestehende 28-Stunden-Beobachtung mit ihren neun gepinnten Dateien bleibt unverändert.

## Die bisherige gefährliche Verkürzung

Bislang konnte ein vom Aufrufer selbst gesetztes `authentication_checked_by_trusted_caller=true` mit einem korrekt berechneten `canonical_payload_sha256` schon bis zum reinen Quellen-Intake vordringen. **SHA-256 bestätigt nur unveränderte Daten, nicht wer sie erzeugte.** Eine geschlossene Paper-Strategie braucht eine echte Quelle-zu-Writer-Vertrauenskette.

## Neue Sicherheitsgrenze (inaktiv, source-only)

Die bestehende Brücke `v3_paper_existing_owner_source_bridge_v1.join_owner_sources` prüft jedes mögliche positive H5/H10/H11-Ereignis zusätzlich mit `v3_paper_source_owner_hmac_v1.verify_owner_packet`:

- Drei getrennte Quellenfamilien, pro tatsächlichem `source_owner` ein **außerhalb des Repositories** provisionierter hochentropischer geheimer Schlüssel (mindestens 32 Bytes, kein Klartext-Testschlüssel).
- Eine HMAC-SHA256-Signatur bindet **originales `source_name`, `pair`, `altname`, vollständigen ursprünglichen `snapshot`, `market_move`, `source_owner` und `signed_at_utc`**. Der sichtbare Digest alleine reicht nicht.
- Verifikation ausschließlich mit einem von der separaten **trusted Mini-PC Owner-Runtime** bereitgestellten `trusted_owner_hmac_keys`-Mapping. Ohne diese Schlüssel ist die Quelle `NO_TRUSTED_RUNTIME_SOURCE_OWNER_KEY`, nicht `VERIFIED`. Ungültige Signatur, Zeitumkehr, Signature-Alter über 15 Minuten, geändertes Paar/Market-Move und falscher Owner führen zu Ablehnung.
- Trotzdem zusätzlich die bestehende unabhängige fachliche Qualifikation: H5 echte amtliche Primärquelle plus direkte Coin-Begünstigung, H10 unabhängig belegte Onchain-Fills und Nettozuflüsse, H11 direkt coin-relevanter positiver Prognosewechsel **und** echter Marktimpuls. Fehlende Quellen dürfen einen qualifizierten Scanner niemals negativ vetoen.

**Begrenzung:** HMAC beweist die Kontrolle des jeweiligen Runtime-Schlüssels, nicht die Markt-Wahrheit. Quellenschlüssel können kompromittiert sein; pro Event sind Herkunft, Originalzeit und korrekte nachträgliche Journal-/Cloud-ACK-Einmaligkeit noch gesondert zu prüfen. Ein kryptografisch autorisierter positiver Herkunftsevent ist **nur Eignung zur vollständigen Kraken-/V3-Modell-/P4-Nachprüfung** – niemals unmittelbares BUY, nie bezahlte Modellfreigabe.

## Original-Eingänge bei Ablehnung VOR dem Router vollständig erfassen (Folgeschritt)

Ein nicht signiertes, ungültiges, veraltetes oder gefälschtes H5/H10/H11-Original darf nicht einfach als Summenzähler verloren gehen. Die vorhandene `join_owner_sources`-Brücke liefert dazu nun je tatsächlichem Eingang einen anonymisierten `V3_ROUTER_REJECTED_ORIGINAL_AUDIT_V1`-Beleg mit `SOURCE_OWNER`-Eingangsindex, eigenem deterministischen `V3-INPUT-REJECT-...`-Schlüssel, Ablehnungsgrund und nur erlaubten sicheren Identitäts-/Zeitmetadaten. Das gemeinsame V3-Preflight rechnet diese Vor-Router-Abweisungen **vollständig** in die Kandidatenstatistik ein und die vorhandene `stage_receipts_explicitly` schreibt sie im selben bewährten O_EXCL-Journal als `SOURCE_INPUT / UNKNOWN / ROUTERREJECT / UNMAPPED/EUR`. **Vollständige fremde Raw-Payloads und Geheimnisse werden niemals archiviert.**

Zählgleichheit, einzelne Original-IDs, begrenzte Metadaten, unveränderlicher Replay, kein PnL und weder Modell-/BUY- noch Paper-Autorität sind CI-geprüft. Unverändert bleibt die Grenze: Diese Stufe läuft **noch nicht dauerhaft auf dem Mini-PC**, hat keinen autonomen H5/H10/H11-Sender, keinen aktiven V3-Writer und noch keinen echten Cloud-ACK aus solchen Ablehnungen. Ein Code-Merge darf diesen Nachweis nicht ersetzen.

## Gesonderter HMAC-Nachweis im bestehenden unveränderlichen Journal (vorbereiteter nächster Schritt)

`paper_evaluator/v3_paper_signed_source_journal_stage_v1.py` prüft das **wirkliche signierte Originalpaket** erneut mit dem extern bereitgestellten, familien-/ownerbezogenen HMAC-Key, und vergleicht es gegen die **identische** bereits durch das Original-Preflight ausgewählte, zurückgestellte oder koaleszierte Quelle. Fehlt die Signatur, stimmt das Original-/Paar-/Zeit-/Owner-Binding nicht oder fehlt der ursprüngliche nicht handelbare `SOURCE_INPUT:FIRST:UNKNOWN`-Beleg, wird **vor jeder neuen Journal-Schreibaktion** abgebrochen.

Bei bestandener unabhängiger Signaturkontrolle wird ein zusätzlicher, idempotenter `SOURCE_INPUT:OWNERAUTH:PASS`-Beleg im **selben** O_EXCL-Journal erzeugt. Er enthält nur kanonische Source-ID, Owner-ID, Paar, Originalzeit und Inhaltsfingerabdruck. Weder HMAC-Key noch Original-Rohpaket werden gespeichert; die ältere `UNKNOWN`-Quittung wird niemals ersetzt. Kein automatischer Modellaufruf, keine P4-Kaufentscheidung, keine Paper-Füllung, keine Live-Strategie-/Cloud-Änderung.

Diese getrennte Quittung besagt **nur**, dass die Signatur am Ort dieses Aufrufs kontrolliert wurde. Der Code ist weiterhin **inaktiv**, echte H5/H10/H11-Schlüssel sind nicht physisch provisioniert, und kein realer Cloud-ACK einer solchen positiven Quelle ist nachgewiesen. Die Authentizität der ursprünglichen Quelle und ihre tatsächliche Marktwahrheit bleiben eigenständige Evidenzgates. Scanner-Kandidaten und laufende 28h-Aufgabe werden nicht berührt.

## Noch erforderliche physische Umsetzung – erst nach eigener Freigabe/Prüfung

Die bestehenden H10-Context-Cloud-Endpunkte, fünf H11-Polymarket-Bücher und der H5-Makrokalender besitzen derzeit **keine** belegten kryptografisch signierten positiven Einzelereignisse. Damit im nächsten Schritt real signierte Events eintreffen, muss der bisherige Source-Owner mit einer passenden Signatur versehen und sein Key **isoliert von GitHub und den bestehenden Cloud-Relay-Token** sicher provisioniert werden. Der einzige künftige Mini-PC-Paper-Writer verifiziert diesen Beleg VOR Modellbudget, persistiert jede akzeptierte/abgewiesene Originalentscheidung unveränderlich und bestätigt exakt seine Cloud-ACK. Keine neue allgemeine Polling-Runtime und kein zweiter Writer.

Die vorhandene `v3_paper_intake_receipt_stage_v1`-Stufe behandelt Source-Originale weiterhin `UNKNOWN / SOURCE_OWNER_RUNTIME_AUTH_NOT_PROVEN`. Diese zweite Sicherheitsgrenze ist absichtlich **nicht** durch einen Code-Merge aufgeweicht. Sie darf erst nach physischem Nachweis (echte Sender-/Key-/Cloud-ACK-Ereignisse) sicher geändert werden. Keine Änderung an RENDER-P0/Cloud-Beweiskette und V2R4.

## Abnahmekriterien für späteren realen Owner

1. Quelle sendet nachweislich ein echtes, zeitgestempeltes und einzeln direkt coin-relevantes Event, keine bloßen Kontextdaten.
2. HMAC-Prüfung bindet Owner, Coin, Stream, Originalmeldung, Wahrscheinlichkeit-/Netto-Geld-/Nachrichteninhalt und Zeit; ohne getrennt provisionierten Key niemals akzeptieren.
3. Replays und vollständige Quittungen müssen vor bezahltem Modell und nach Restart in ein EINZIGES autoritatives Journal; jede Cloud-ACK identisch/idempotent.
4. Vergleich Standard/offensiv bleibt prospektiv, Marktbewegung allein ist kein Ausführungsgewinn, 50+50 EUR und 0,6 % Taker/Seite bleiben. Separate Papier- und Kosten-Freigaben weiterhin nötig.

**Followthrough:** Genau die vorhandene Work-10:15-/Meilensteinsteuerung, keine zusätzliche Task-Erinnerung oder neuer Zeitplan; physische Gate-/Owner-Aufgabe ist ausdrücklich weiterhin OFFEN.
