# Supabase Data API - Rollenrechte für neue Tabellen ab 30. Oktober 2026

**Projektweite Infrastruktur-/Betriebsregel (21.10.2026), nicht V3-spezifisch.** Owner im vorhandenen Projektmanager: `PROJECT_BACKLOG.md` → `security_permissions_and_rls`; Kontextmanager `AGENTS.md` liest diese bestehende Aufgabenquelle mit. Keine eigene Automation, kein neuer Manager, keine V2R4-/V3-/Kraken-Aktion.

## Warum

Supabase stellt am 30.10.2026 bei bestehenden Projekten die automatische Vergabe von Data-API-Rechten für **neue** Tabellen im exponierten Schema `public` um. Bereits existierende Tabellen behalten ihre bisherigen Grants. Auch Schema-Rekonstruktionen in neuen Projekten, Testbranches oder mit `supabase db reset` müssen bei der späteren Wiederherstellung konsistente explizite Rechte besitzen. Data-API-Requests (PostgREST, supabase-js, GraphQL) benötigen `GRANT` für die tatsächliche Rolle **und** eine passende RLS-/Policy-Entscheidung; fehlende Rechte können als `42501 permission denied` erscheinen. Direkter SQL-Zugriff ist kein positiver API-Client-Test.

**Live-Datenpunkt 21.10., ausschließlich lesend:** 26 Tabellen mit RLS, 36 Views in `public`; SELECT für `anon` 0/62, für `authenticated` 0/62, für `service_role` 62/62. `pg_default_acl` zeigt unterschiedliche Defaults nach der Erstellerrolle: `postgres` mit `service_role`, `supabase_admin` ebenfalls mit `anon`/`authenticated`. Rollen- und Server-Defaults können sich ändern; die künftige Migration darf sich auf keine dieser Annahmen verlassen. Source: https://supabase.com/docs/guides/api/securing-your-api und die Supabase-Mitteilung vom 20.10.2026.

## Bestehender Migrations-/Sicherheitsablauf

1. **Vor dem konkreten Schema-Change:** Tatsächlich genutztes Zielprojekt, Schema, Erstellerrolle, existierenden Datenbankowner, API-Consumer (`service_role`/andere) sowie abhängige Views, Funktionen und Sequenzen ermitteln; zwischen API und direktem SQL unterscheiden. Bestehende komponentenbezogene Releases und Rechtefreigaben bleiben in Kraft.
2. **Innerhalb derselben genehmigten Migration:** `CREATE TABLE`, RLS/Policies sowie ausdrücklich erforderliche `REVOKE/GRANT` für die Tabelle und ggf. Sequenzen/Funktionen atomar ausführen. `anon`/`authenticated` nicht pauschal berechtigen; Default-Rechte auch bei `supabase_admin`-Erstellerrolle aktiv überprüfen. Für Daten ohne API-Bedarf keine API-Grants erfinden. **Keine pauschalen `ALTER DEFAULT PRIVILEGES`-Änderungen am aktiven Projekt ohne eigene Folgenprüfung.**
3. **Beispiel nur für einen separat autorisierten internen Service-Writer** (Rechte konkret anpassen, kein Auftrag zum Ausführen):

```sql
create table public.example_internal (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now()
);
alter table public.example_internal enable row level security;
revoke all privileges on table public.example_internal from anon, authenticated;
revoke all privileges on table public.example_internal from service_role;
grant select, insert on table public.example_internal to service_role;
-- Vor Migration prüfen: eventuell erforderliche Sequence- und Funktionsrechte,
-- Spalten-INSERT-ACLs, RLS-Policies und unveränderliche Event-Tabellen-Regeln.
```

**Wichtig:** Dieses Muster ist nicht auf Event-Tabellen mit INSERT-Column-Privileges, immutable Trigger oder andere Spezialfälle übertragbar. Die `service_role` kann RLS umgehen, benötigt aber weiterhin die richtigen PostgreSQL-Zugriffsrechte. Views und `SECURITY DEFINER`-Funktionen benötigen gesonderte Prüfung. Öffentliches `GRANT ALL` aus der Beispiel-E-Mail nicht übernehmen.

4. **Vor Migration/Freigabe und danach in geeignetem bereits bestehendem Testpfad:** `pg_default_acl` für die Erstellerrolle, `pg_class.relrowsecurity`, `has_table_privilege` und ggf. Sequenzprivilegien prüfen; mit der tatsächlichen Consumer-Rolle positive SELECT-/INSERT-/UPDATE-Aufrufe über die Daten-API und negative `anon`-/`authenticated`-Tests durchführen. Ein Admin-SQL-Query ist kein ausreichend realer Clientnachweis. Keine neue bezahlte Testumgebung automatisch erzeugen.
5. **Nachlauf und Fehler:** Bei Fehler `42501` das konkrete erforderliche GRANT innerhalb der zugehörigen Migration ergänzen, keine globalen Grants; RLS und API-Erfolg original belegen. Nach dem 30.10. erster echter Tabellenfall mit Schema-Version, Zeitpunkt, Rollen-ACL und API-ACK im bisherigen Owner dokumentieren. Solange kein erster Echtfall vorliegt, bleibt dessen ACK offen.

## Read-only PostgreSQL-Check für konkrete Tabellen

```sql
select c.relname, c.relkind, c.relrowsecurity,
       has_table_privilege('anon', c.oid, 'SELECT') as anon_select,
       has_table_privilege('authenticated', c.oid, 'SELECT') as authenticated_select,
       has_table_privilege('service_role', c.oid, 'SELECT') as service_select,
       has_table_privilege('service_role', c.oid, 'INSERT') as service_insert
from pg_class c join pg_namespace n on n.oid=c.relnamespace
where n.nspname='public' and c.relkind in ('r','p','v','m')
order by c.relname;
```

Default-ACL gesondert je Rolle über `pg_default_acl`, `pg_get_userbyid(defaclrole)` und `pg_namespace` kontrollieren. Die Abfrage ist kein Ersatz für tatsächlichen Data-API-Zugriff und kein ausreichender Freigabe-ACK. Kein produktives DDL, keine Strategie- oder Runtime-Änderung durch diesen Leitfaden.
