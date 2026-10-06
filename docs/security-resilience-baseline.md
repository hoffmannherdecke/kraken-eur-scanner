# Security and resilience baseline

Status: **PASS for the current paper/research phase**  
Last reviewed: **2026-10-06**

This baseline is intentionally small. It records the controls that materially reduce
external-attack and component-failure risk without adding a second infrastructure
stack or continuous heavy monitoring.

## 1. Trust boundaries and controls

| Area | Current control | Failure / attack behaviour |
| --- | --- | --- |
| MINI-PC / Windows | Defender + Windows Firewall audit, WireGuard for remote access, no intended public RDP exposure, restricted local secret ACLs | Fail closed for missing runtime/secrets; watchdog reports stale/unhealthy state |
| GitHub Actions | Explicit workflow permissions, PR validation is read-only, no `pull_request_target`, secrets only in non-PR operational workflows | Runner outage creates a data gap but must not corrupt state; bounded recovery retries only |
| Supabase | RLS enabled, no anon/authenticated policies on operational tables, backend/service-role access only | Archive/relay failure may delay sync; strategy/runtime must not auto-change |
| Edge relays | Custom narrow tokens for JWT-disabled functions; hash-only credentials for MINI-PC status and V2R4 evidence; stale/out-of-order/idempotency guards | Invalid/stale requests are rejected; duplicate evidence must not mutate prior evidence |
| Kraken read-only bridge | API-key permission self-check permits query-only scope and rejects any broader permission set | Bridge stops if permissions exceed the approved read-only set |
| OpenAI | API key limited to workflows that require model evaluation; retries are bounded | API outage/quota failure blocks model-dependent evaluation, never authorizes a trade by itself |
| Slack | Notification transport only; no trading authority | Slack outage may suppress a push, not change strategy/order state |
| Altrady | Authenticated transport relay; deduplicated events; current path is transport-only | Bad/missing relay data cannot directly place an order or change strategy state |

## 2. Component-failure policy

| Component unavailable | Required behaviour | Recovery expectation |
| --- | --- | --- |
| GitHub Actions | No partial state assumptions; accept missing real-time scans | Resume automatically; mark outage window as coverage gap |
| Supabase | Scanner/evaluator continue where designed; archive/telemetry may lag | Sync later; dedupe/idempotency prevents double writes |
| Kraken public API / Internet | Do not evaluate stale market data as fresh | Retry with bounded backoff; require fresh heartbeat before normal operation |
| OpenAI API | No model-dependent decision is fabricated | Retry only within the bounded retry budget; otherwise wait |
| Slack | Continue core paper/runtime work without relying on notification delivery | Notify again only on meaningful state transition |
| MINI-PC reboot / power loss | Startup tasks and watchdog recover bounded runtime components | Post-recovery gate verifies health before normal operation |
| External SSD unavailable | Core runtime must not silently assume backup success | Report degraded backup/storage state; do not invent missing evidence |

## 3. External-attack rules

1. No repository secret may be exposed to a normal `pull_request` workflow.
2. `pull_request_target` is forbidden in this repository.
3. PR workflows must remain read-only.
4. Operational JWT-disabled Edge Functions must implement explicit custom
   authentication and reject invalid credentials.
5. Live secrets, private keys and `.env` files must never be committed.
6. Read-only Kraken credentials stay physically/logically separate from any future
   order credential.
7. No external message, webhook or model response may directly authorize an order.

The existing architecture validation workflow enforces the highest-value static
rules above whenever security-sensitive files are changed.

## 4. Deliberately accepted paper-phase risks

These are documented rather than "fixed" with extra machinery:

- **Altrady uses one transport token for ingress and MINI-PC poll/ack today.**
  This is acceptable while the path is transport-only and has no trading authority.
  Split ingress and consumer credentials before a real-money release.
- **Main is not yet protected by a repository ruleset.** Runtime components still
  intentionally persist bounded state to Git in a few paths. Enforcing PR-only main
  today would break that runtime. Protect main after runtime state is fully moved to
  Supabase/local state and direct bot persistence has been removed.
- **Official `actions/*` workflows use maintained major-version tags rather than
  full commit-SHA pinning.** This is accepted for the current small system; pinning
  can be added if the supply-chain threat model is raised.
- The public scanner repository is treated as public information. Security must
  never depend on hiding its source code.

## 5. Mandatory real-money release gates

Before any future automated real-money order path is enabled, all of these must be
implemented and tested:

- explicit kill switch,
- startup reconciliation against the exchange,
- stale-data rejection,
- duplicate-order/idempotency protection,
- bounded circuit breaker,
- explicit order-state machine,
- separate least-privilege trading credential with withdrawals disabled,
- Altrady ingress/consumer credential separation,
- protected release path for production code/configuration.

Until those gates pass, research/paper signals have **no authority to place orders**.

## 6. Audit result 2026-10-06

- Supabase security advisor: no warning/error-class security finding; only
  informational "RLS enabled, no policy" notices, matching the deny-by-default
  backend-only design.
- Operational tables checked: RLS enabled; no public RLS policies.
- Edge-function traffic reviewed for the previous 24 hours: observed calls were
  from the expected MINI-PC path; no unauthorized-response pattern was visible.
- Current MINI-PC health snapshot: HEALTHY, backup fresh, Kraken connectivity
  healthy, runtime supervisor healthy, relay/cloud sync healthy.
- GitHub incident recovery demonstrated that a multi-hour hosted-runner outage
  resumes without persistent state corruption; the unavoidable loss is only the
  real-time observations that were never captured during the outage.

Overall result: **PASS_WITH_DOCUMENTED_PRODUCTION_GATES**.


### Local MINI-PC verification 2026-10-06

Physical/local verification completed successfully:

- Windows network profile changed from Public to Private for the dedicated Ethernet connection.
- Enabled inbound Remote Desktop rules are restricted to the Private profile; audit confirms `Public+AnyRemote=0`.
- Final local security audit result: `PASS_BASELINE`.
- Defender real-time protection and antivirus are active.
- Secret-hygiene audit result: `HEALTHY`, with `Critical: 0`, `Warning: 0`, and no findings.
- No credential rotation, firewall disablement, app installation, or reboot was performed by the audits.

Paper/research-phase security and resilience audit status: **COMPLETE / PASS**.
