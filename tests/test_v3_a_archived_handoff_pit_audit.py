"""Offline guards for the read-only 12-case historical candidate inventory."""
import importlib.util
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "tools" / "v3-a-archived-handoff-pit-audit.py"
SPEC = importlib.util.spec_from_file_location("v3_a_handoff_audit", MODULE)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)
CASES = json.loads((ROOT / "research/v3/v3-a-retro-12-case-matched-no-buy-20261010.json").read_text("utf-8"))


def original(case: dict) -> dict:
    cid = case["candidate_id"]
    pair = case["pair"]
    tag = pair.replace("/", "-")
    timestamp = datetime.strptime(cid[:15], "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc)
    run = int(cid.rsplit("-r", 1)[1])
    return {
        "candidate_id": cid,
        "event_time_utc": timestamp.isoformat(),
        "event_ts": int(timestamp.timestamp()),
        "source_scanner_run_id": run,
        "queue_id": f"{run}:{tag}:{int(timestamp.timestamp())}",
        "pair": pair,
        "altname": tag.replace("-", ""),
        "action": "REVIEW_ONLY_NOT_ORDER",
        "scanner_candidate": {"sensor": "test"},
        "scanner_market_context": {"regime": "test"},
    }


class OriginalHandoffPitAuditTests(unittest.TestCase):
    def test_twelve_exact_handoffs_do_not_imply_historical_features(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "v2r4-paper-stage-test" / "handoff_queue"
            folder.mkdir(parents=True)
            for case in CASES["cases"]:
                c = original(case)
                (folder / (c["candidate_id"] + ".json")).write_text(json.dumps(c))
            result = mod.audit(CASES, Path(root))
            self.assertEqual(result["case_count"], 12)
            self.assertEqual(result["valid_handoff_count"], 12)
            self.assertEqual(result["original_scanner_context_count"], 12)
            self.assertEqual(result["coin_pit_claims_inside_handoff"], 0)
            self.assertEqual(result["historical_coin_pit_authoritatively_proven_count"], 0)
            self.assertEqual(result["model_calls"], 0)
            self.assertFalse(result["orders"])
            self.assertNotIn("outcome_stratum", json.dumps(result))
            self.assertNotIn("mfe24_pct", json.dumps(result))

    def test_name_spoof_and_future_data_are_not_replay_evidence(self):
        case = CASES["cases"][0]
        c = original(case)
        self.assertEqual(mod.verify_handoff(c, case, c["candidate_id"] + ".json")["status"],
                         "ORIGINAL_HANDOFF_VALID")
        fake = dict(c, candidate_id="WRONG")
        self.assertEqual(mod.verify_handoff(fake, case, c["candidate_id"] + ".json")["status"],
                         "IDENTITY_MISMATCH")
        c["candidate_entry_evidence"] = {
            "pair": c["pair"],
            "status": "COMPLETE",
            "observed_at_utc": (mod.clock(c["event_time_utc"]) + timedelta(hours=1)).isoformat(),
            "known_at_utc": (mod.clock(c["event_time_utc"]) + timedelta(hours=1)).isoformat(),
            "frames": {str(k): {"status": "VALID", "last_closed_bar_end_utc": c["event_time_utc"]}
                       for k in (1, 5, 15)}
        }
        c["candidate_entry_evidence"]["frames"]["15"]["atr14_eur"] = 0.01
        found = mod.verify_handoff(c, case, c["candidate_id"] + ".json")
        self.assertFalse(found["historical_coin_pit_claim_in_handoff"])
        self.assertFalse(found["historical_coin_pit_authoritatively_proven"])

    def test_unexpected_manifest_fails_closed(self):
        bad = dict(CASES, cases=CASES["cases"][:11])
        with self.assertRaises(ValueError):
            mod.audit(bad, Path("/dev/null"))

if __name__ == "__main__":
    unittest.main()
