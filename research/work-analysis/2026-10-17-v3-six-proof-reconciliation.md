# V3 six-proof reconciliation — 2026-10-17

## Scope and decision

This is a bounded read-only release-evidence reconciliation for `V3_EXPERIMENTAL_PAPER_SIX_PROOFS`. It does not activate V3 Paper, spend model budget, change V2R4, create a scheduler, or authorize real money.

**Decision:** `BLOCKED_RELEASE_EVIDENCE_NOT_V3_RUNNING`. The TIA/EUR canary is authentic component evidence, but no proof-specific set of all six accepted `V3_PAPER_TECHNICAL_E2E_READBACK_V1` envelopes is present. Therefore the release counter remains **0/6**, while the underlying progress is recorded precisely rather than discarded.

## New authentic evidence reviewed

- Issue #99 owner checkpoint [6222965426](https://github.com/hoffmannherdecke/kraken-eur-scanner/issues/99#issuecomment-6222965426): real one-shot TIA/EUR candidate `20261016-190002-TIA-EUR-r17497221611485`, one real model HTTP response, `WAIT`, P4 `FULL_WAIT_VALIDATED_OFFLINE`, eight initial immutable Cloud receipts, no order and no V3 active series.
- Issue #99 owner checkpoint [6223498351](https://github.com/hoffmannherdecke/kraken-eur-scanner/issues/99#issuecomment-6223498351): post-TTL `WAIT_EXPIRY=UNKNOWN` closed honestly; 10/10 distinct Cloud event IDs and hashes, one observed 5m snapshot only, no negative market inference, no model retry, no order, V2R4 still the sole active Paper series.
- Current `project-current-state.json` still declares V2R4 as active and the V3 transition as `BLOCKED_RELEASE_EVIDENCE_NOT_V3_RUNNING`.
- `docs/v3-controlled-paper-cutover-20261011.md` explicitly says the earlier recovery drill needed manual recovery and did not prove uninterrupted automatic rollback.
- `tools/v3_experimental_paper_technical_gate.py` requires six named, origin-bound readback envelopes. GitHub code search did not return a committed proof envelope, but reported an incomplete search; this report therefore relies on the gate's own zero-credit declared state and the reviewed canonical evidence, not on search absence alone.

## Per-proof disposition

| Proof | Authentic evidence now present | Release disposition |
|---|---|---|
| `V3_REAL_MODEL_COIN_PIT_P4_INPUT_E2E` | Real TIA scanner candidate, real model response and validated P4 WAIT with immutable Cloud receipts | **PARTIAL_EVIDENCE_NOT_ACCEPTED_PROOF** — canary evidence exists, but the required proof-specific Mini-PC readback envelope and non-canary release binding are not recorded |
| `V3_FAIL_CLOSED_STOP_STAGE2_FEE_WAIT_CONTRACT` | WAIT branch exercised; no order | **OPEN** — no physical BUY/stop/stage2/fee-path proof and no accepted proof envelope |
| `V3_JOURNAL_REASONS_ERRORS_6H24H_FOLLOWUP_CENSURE` | Ten distinct journal/Cloud receipts; incomplete TTL correctly persisted as UNKNOWN | **PARTIAL_EVIDENCE_NOT_ACCEPTED_PROOF** — 6h/24h non-canary lifecycle and required Mini-PC+Supabase envelope remain open |
| `V3_SINGLE_WRITER_FENCE_CLOUD_CAS_DRYRUN` | Source/CI preparation exists; V2R4 remained sole active series | **OPEN** — no physical V3 CAS rotation or exact Mini-PC+Supabase proof envelope |
| `V3_MINIPC_SUPERVISOR_STOP_START_ROLLBACK` | Earlier recovery drill and later canary isolation provide component evidence | **PARTIAL_EVIDENCE_NOT_ACCEPTED_PROOF** — uninterrupted automatic rollback, exact source/task pins and proof envelope remain open |
| `V3_GITHUB_WORK_ALERT_DYNAMIC_SERIES_ROUTING` | GitHub/Work routing code and Issue #99 ownership exist | **OPEN** — no active V3 series and no paired GitHub+Work accepted readback envelope |

## Gate consequences

- Accepted authentic release proofs: **0/6**.
- Component evidence is materially stronger than on 15 October: the real TIA model→P4→journal→Cloud WAIT path and honest UNKNOWN expiry are now proven and must not be repeated.
- V3 Paper activation remains prohibited; V2R4 remains the only active Paper strategy. Echtgeld remains prohibited.
- The unchanged Work selector fingerprint is acknowledged as blocked at a specific external evidence/release boundary so the same synthesis is not repeated daily.

## Smallest next objective gate

The next release work must produce the first exact, proof-specific original readback envelope from an already required physical gate, without another model call or a second writer. Candidate order:

1. complete the physical single-writer fence / Cloud CAS dry-run evidence; or
2. complete the supervisor stop/start/rollback proof with uninterrupted automatic recovery.

Both remain physical release work and require their existing explicit gate; this report grants no execution authority. Independent safe work may continue meanwhile.
