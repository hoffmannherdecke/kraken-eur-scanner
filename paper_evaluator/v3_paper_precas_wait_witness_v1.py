"""Build isolated No-BUY censors from one exact historical WAIT lineage."""

import hashlib
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from paper_evaluator.v3_paper_minipc_closed_1m_capture_v1 import assemble
from paper_evaluator.v3_paper_missed_opportunity_followup_v1 import followup_no_buy
from paper_evaluator.v3_experimental_paper_journal_v1 import KIND, clock
from paper_evaluator.v3_paper_minipc_one_candidate_v1 import REVISION

WAIT_REPLAY = "V3_PRECAS_ORIGINAL_WAIT_CENSOR_V1"
WAIT_PHASES = frozenset({"SCANNER_CAPTURE", "P4_VALIDATION", "WAIT_WATCH",
                         "WAIT_RECHECK", "WAIT_EXPIRY"})
HORIZONS = (6, 24, 72)


def receipt_wire(row):
    return json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"


def _export_row(row):
    identity = "|".join(row[k] for k in ("series_id", "candidate_id", "phase", "event_key"))
    wire = receipt_wire(row)
    return dict(event_id=hashlib.sha256(identity.encode()).hexdigest(),
                content_sha256=hashlib.sha256(wire.encode()).hexdigest(), payload=row)


def validate_wait_originals(originals):
    """Match exactly one candidate, original phase IDs, timestamps and payloads."""
    if not isinstance(originals, list) or len(originals) != len(WAIT_PHASES):
        raise ValueError("exact original scanner/P4/watch/recheck/expiry required")
    by_phase = {}
    for item in originals:
        row = item["payload"]
        if (item != _export_row(row) or row["orders"] is not False or row["real_money_actions"] is not False
                or row["kind"] != KIND or row["revision"] != REVISION):
            raise ValueError("WAIT original receipt checksum or scope differs")
        by_phase[row["phase"]] = row
    if set(by_phase) != WAIT_PHASES:
        raise ValueError("WAIT original phase set differs")
    scanner = by_phase["SCANNER_CAPTURE"]
    for row in by_phase.values():
        if any(row[k] != scanner[k] for k in ("series_id", "candidate_id", "pair", "revision", "event_time_utc")):
            raise ValueError("WAIT original candidate identity differs")
    if (not scanner["series_id"].startswith("PAPER-V3-CANARY-")
            or scanner["result"] != "SEEN" or by_phase["P4_VALIDATION"]["result"] != "WAIT"
            or by_phase["WAIT_WATCH"]["result"] != "WAIT"
            or by_phase["WAIT_RECHECK"]["result"] not in ("WAIT", "PASS")
            or by_phase["WAIT_EXPIRY"]["result"] not in ("UNKNOWN", "CLOSED")):
        raise ValueError("historical WAIT original scope differs")
    chronology = [clock(by_phase[phase]["known_at_utc"]) for phase in
                  ("SCANNER_CAPTURE", "P4_VALIDATION", "WAIT_WATCH", "WAIT_RECHECK", "WAIT_EXPIRY")]
    if chronology != sorted(chronology) or chronology[0] < clock(scanner["event_time_utc"]):
        raise ValueError("historical WAIT clock order differs")
    return scanner


def run_isolated_wait_witness(originals, snapshots=None):
    """Use a disposable journal and a verified archive; never fetch market data."""
    scanner = validate_wait_originals(originals)
    with tempfile.TemporaryDirectory(prefix="v3-precas-wait-") as scratch:
        journal = Path(scratch) / "journal"
        journal.mkdir()
        if snapshots is None:
            # No archive supplied: exercise only the explicit censor path.
            # This does not assert that historical market observations never existed.
            snapshots = Path(scratch) / "no-capture-supplied"
            snapshots.mkdir()
        for item in originals:
            (journal / (item["event_id"] + ".json")).write_text(
                receipt_wire(item["payload"]), encoding="utf-8", newline="\n")
        captured = assemble(snapshots=snapshots, pair=scanner["pair"],
                            entry_at_utc=scanner["event_time_utc"],
                            observed_at_utc=datetime.now(timezone.utc).isoformat())
        for hours in HORIZONS:
            result = followup_no_buy(journal=journal, series_id=scanner["series_id"],
                                     candidate_id=scanner["candidate_id"],
                                     captured_1m=captured, hours=hours)
            if result.get("event_result") != "CENSORED":
                raise ValueError("this witness accepts only censored No-BUY results")
        rows = [_export_row(json.loads(p.read_bytes())) for p in journal.glob("*.json")]
    return sorted((r for r in rows if r["payload"]["phase"].startswith("FOLLOWUP_")),
                  key=lambda r: r["event_id"])


def validate_wait_sandbox_rows(originals, generated, readback):
    """Independently compared sandbox censors extend, but never replace, WAIT originals."""
    scanner = validate_wait_originals(originals)
    if not isinstance(generated, list) or not isinstance(readback, list) or len(generated) != 3 or len(readback) != 3:
        raise ValueError("three exact original-host and sandbox follow-ups required")
    phases = set()
    horizon_by_phase = {f"FOLLOWUP_{h}H": h for h in HORIZONS}
    for item in generated:
        row = item["payload"]
        hours = horizon_by_phase.get(row["phase"])
        if (item != _export_row(row) or row["orders"] is not False
                or row["real_money_actions"] is not False
                or any(row[k] != scanner[k] for k in ("series_id", "candidate_id", "pair", "revision", "event_time_utc"))
                or row["kind"] != KIND or row["result"] != "CENSORED"
                or hours is None or row["event_key"] != f"NOBUY{hours}H"
                or clock(row["known_at_utc"]) < clock(scanner["event_time_utc"]) + timedelta(hours=hours+1)
                or row["data"]["path_contiguous_1m_verified"] is not False
                or row["data"]["censor_reason"] != "CENSORED_NO_CONTIGUOUS_CLOSED_KRAKEN_1M_PATH"
                or any(k in row["data"] for k in ("mfe_pct", "mae_pct", "close_return_pct",
                                                "position_net_pnl_eur", "position_net_return_pct"))):
            raise ValueError("isolated follow-up provenance or censor scope differs")
        phases.add(row["phase"])
    if phases != {f"FOLLOWUP_{h}H" for h in HORIZONS} or sorted(generated, key=lambda r:r["event_id"]) != sorted(readback, key=lambda r:r["event_id"]):
        raise ValueError("sandbox follow-up phases, bytes or identifiers differ")
    return scanner
