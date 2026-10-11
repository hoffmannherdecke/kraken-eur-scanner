# Kontext vor Aktion — projektübergreifender Arbeitsvertrag v1

**Stand:** 2026-10-11. **Umfang:** Arbeits- und Entwicklungsprozess, KEINE Trading- oder Runtime-Freigabe.

## Warum

Dokumentieren ist nicht dasselbe wie Wiederfinden, Verstehen oder Anwenden. Frühere Nutzerbeschlüsse und gemessene Erkenntnisse werden häufig korrekt archiviert, aber in späteren Chats/Work-Läufen nicht zuverlässig abgerufen. Der neue Vertrag macht den Quellzugriff und die spätere fachliche Disposition *explizit überprüfbar*. Es entsteht **kein zweites Backlog, keine neue Datenbank und kein zusätzlicher Scheduler**.

## A. Verbindliche Reihenfolge vor einer wesentlichen Änderung

1. **Aufgabentyp festlegen:** `strategy`, `architecture`, `operations` oder `research`. Bei thematischen Überschneidungen alle betroffenen Bereiche gesondert abrufen, nicht frei raten.
2. **On-demand abrufen:** `python tools/context_before_action.py --scope strategy` (entsprechenden Scope einsetzen). Der Bericht zeigt die aktuell auf dem Datenträger vorhandenen *maßgeblichen* Dateien mit Inhaltsfingerprints, deklariertem Projektzustand, bestehender Review-ACK-Spur und — für Strategie/Research — konsolidierten V3-Lern-/H-/Paketstatus. Kein Netz, kein API-Verbrauch, keine Orders und kein persistierter Datenabzug.
3. **Tatsächlich lesen, nicht nur hashen:** Nutzerentscheidungen, früher verworfene Ideen, kausale Evidenz, offene Abhängigkeiten, Risiken, Nutzerrechte und Freigabegrenzen in den referenzierten Originalabschnitten prüfen. Mehrdeutige Signale/alte historische Angaben nur anhand der fachlich höheren Autorität auflösen.
4. **Widerspruch prüfen:** GitHub-`project-current-state.json` beschreibt den **deklarierten, datierten** Zustand, nicht garantiert den Live-MINI-PC-/Supabase-Zustand. `PROJECT_BACKLOG.md` besitzt offene Arbeit, `research/work-analysis-state.json` besitzt Review-ACKs. Ein alter `next_control_decisions`-Eintrag kann trotz gültigem Abschlussbeleg noch sichtbar sein; nicht automatisch zum erneuten Auftrag machen. Work-/ChatGPT-Automationsprompts sind *außerhalb GitHub*; nach materialem Phasenwechsel gesondert prüfen/aktualisieren. Bestehende Chats sind nicht garantiert vollständig abrufbar.
5. **Fachliche Entscheidung dokumentieren:** Für materielle Vorhaben eine kontextgebundene Disposition je Pflichtquelle mit `APPLIED`, `NOT_APPLICABLE_WITH_REASON` oder `CONFLICT_RESOLVED_WITH_PROOF`. Dazu konkrete Änderung, verworfene Alternativen, vorhandenes Freigabegate, bestehender Owner. Keine neue To-do-Kopie.
6. **Richtigen Owner beschreiben und abarbeiten:** Erkenntnis → **ein** bestehender Fach-Owner/Backlog → konkret erlaubter nächster Schritt → Evidenz-/Freigabegate → tatsächliche Tests/CI/Review → Runtime-E2E nur bei vorhandener Freigabe → beweisbarer Abschluss/ACK. `DONE` nur nach realem Beleg. Ein bloßer Chatabschluss ist keine Implementation.
7. **Nachfolgevererbung:** Jedes materielle Vorgänger-Finding muss beim jeweiligen nächsten Versions-/Release-Gate mit `KEEP/TEST/REJECT/DEFER` und Beleg behandelt werden. Ist die Evidenz unzureichend, den kleinsten nächsten Test benennen, niemals erfolgreiche Trade-Ökonomie erfinden.

## B. Technischer Kontrollmechanismus

`research/context-before-action-routing-v1.json` ist ein **Routingindex** auf bereits vorhandene kanonische Quellen, kein neuer fachlicher Owner. `tools/context_before_action.py` stellt einen kleinen, datierten Arbeitskontext **bei Bedarf** aus diesen Quellen zusammen. Pro Datei enthält er SHA-256 sowie Zweck/Autorität; diese Fingerprints verhindern versehentliche Verwendung alter Quellenstände.

Für signifikante, risikoarme Architektur-/Strategieänderungen ist zusätzlich ein ehrlicher `CONTEXT_REVIEW_RECEIPT_V1` sinnvoll. Ein JSON-Receipt enthält:

- `kind`, `scope`, `fingerprint` (aus aktuellem Preflight);
- `change_intent`, `planned_action`, `superseded_or_rejected_alternatives`, `release_gate`, `canonical_followthrough_owner`;
- `source_dispositions`: genau **eine** begründete Disposition pro erforderlicher Quelle, mit `path`, `status`, `reason`.

Validierung: `python tools/context_before_action.py --scope architecture --receipt <PFAD_ZUR_QUITTUNG>`. Fehlende Quelle, fehlende Quellen-Disposition, leere Begründung und veralteter Fingerprint führen zu `CONTEXT_GATE_BLOCKED`. Die Negativtests laufen im **bestehenden** Project-Control-Plane-Guard. Ein valides Receipt beweist nur konsistente Struktur und wahrheitsgemäß abgegebene Review-Behauptung, *nicht* maschinell das semantische Verstehen. Vor autorisierten Releases gelten weiterhin sämtliche bestehenden Evidence-/Safety-/Nutzer-Gates.

**Rollout:** Der Guard prüft zunächst automatisch Verfügbarkeit und Routing aller vier Wissensbereiche; die strengere Receipt-Prüfung ist als dokumentierte, direkt ausführbare Prüfung verfügbar und soll an *echten* künftigen materiellen Änderungen nachgewiesen werden. Keine pauschale CI-Blockade aller laufenden Alt-PRs ohne schrittweisen E2E-Nachweis. Ohne tatsächlichen Review-Receipt keinesfalls behaupten, alte Entscheidungen seien semantisch bewertet.

## C. Praktische Auswirkung bei V2R4 → V3

Vor einem V3-B-/H3-/H6-/V3-Paper-Schritt gehören **mindestens** die ursprüngliche V2R3-Lernspur, V2R4-72h-Wirtschaftsevidenz, V3-A/B-Befunde, konsolidierter P0–P9-Plan, aktuelles H1–H11-Status-/Migrationsledger und die Sicherheits-/One-change-/Kosten-/Sizing-Entscheidungen in die Prüfung. H3-001 bleibt archiviert/unbewertet, H6 bleibt bis zum separaten Gate aus; 50+50-€-Paper, 0,60% Taker/Seite, Anti-Chase, echte Kraken-EUR-Handelbarkeit und kein Echtgeld werden durch dieses Verfahren **nicht** geändert. Eine neu implementierte Eligibility-Prüfung ist noch keine bewiesene Netto-BUY-Verbesserung.

**Wirtschaftlicher Prüfpunkt:** Mehr valide Netto-Trades bei begrenztem Risiko und realen Followups statt nur neue Dateien, größere Kandidatenzahlen oder grünes IT-Health.

## D. Andere gemeinsame Projekte

Das **Verfahren** ist allgemein wiederverwendbar, die **Krypto-Dateien** sind es nicht. Für jedes andere Projekt sind im bereits bestehenden Projektverzeichnis dessen eigene (i) aktuelle Zustandsautorität, (ii) Nutzerbeschlüsse, (iii) Task-Owner, (iv) Evidenz und (v) Abschlussbestätigungen zu benennen. Keine zweite globale „Wissensdatenbank“ als Ersatz; bei fehlenden Quellen klar und frühzeitig sagen, was nicht rekonstruierbar ist. Persönliche ChatGPT-Erinnerung und frühere Chats dürfen helfen, dürfen aber nicht als vollständiges, synchronisiertes Archiv behandelt werden.

In neuen Chats oder Work-Sitzungen muss der tatsächlich arbeitende Assistent das Protokoll **aktiv benutzen** bzw. den projektbezogenen Kontext abrufen. Diese Datei erzwingt allein keinen automatischen Modellaufruf in beliebigen anderen Unterhaltungen. ChatGPT-Tasks/Work-Prompts müssen separat darauf ausgerichtet und nach einem echten Lauf überprüft werden.

## E. Erfolgskriterien

1. Abruf in allen vier Scopes nachweislich erfolgreich; fehlende/stale Quellen oder Receipts scheitern in Tests.
2. Ein echter nachfolgender PR benennt konsistent den Kontext-Fingerprint, die früheren relevanten Nutzerbeschlüsse, eine konkrete Entscheidung und einen Abschlussnachweis.
3. Ein Chatwechsel/Work-Run kann den *aktuellen* Status, ältere abgelehnte Alternativen und das tatsächliche nächste Gate rekonstruieren, **ohne** historische Behauptungen als Live-Fakt auszugeben.
4. Keine neuen Cronjobs, Datenspiegel, OpenAI-Gesprächs-Imports, Secrets, Echtgeldrechte, Strategie-/Paper-/Shadow-Mutationen allein durch diese Verbesserung.

**Bestehende fachliche Autoritäten bleiben:** `docs/project-control-plane-governance.md`, `PROJECT_BACKLOG.md`, `research/v3-migration-ledger.json` und alle vorhandenen Release-Gates.
