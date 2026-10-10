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

    def test_wrapped_mini_pc_filenames_and_missing_cases_are_safe(self):
        # Production files are not guaranteed to have exactly <candidate-id>.json.
        # The earlier PowerShell check used *candidate-id*.json and found 12/12.
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "v2r4-paper-stage-test" / "handoff_queue"
            folder.mkdir(parents=True)
            for case in CASES["cases"][:5]:
                c = original(case)
                (folder / ("handoff-" + c["candidate_id"] + "-original.json")).write_text(
                    json.dumps(c))
            result = mod.audit(CASES, Path(root))
            self.assertEqual(result["valid_handoff_count"], 5)
            self.assertEqual(result["original_scanner_context_count"], 5)
            self.assertEqual(result["missing_original_count"], 7)
            self.assertEqual(result["invalid_original_count"], 0)
            self.assertEqual(result["model_calls"], 0)
            self.assertFalse(result["orders"])
            self.assertFalse(result["paper_state_changed"])

    def test_invalid_json_and_duplicate_copies_do_not_crash_audit(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "v2r4-paper-stage-test" / "handoff_queue"
            folder.mkdir(parents=True)
            c0 = CASES["cases"][0]
            (folder / (c0["candidate_id"] + ".json")).write_text("{broken")
            c1 = CASES["cases"][1]
            data = original(c1)
            (folder / (c1["candidate_id"] + ".json")).write_text(json.dumps(data))
            (folder / ("duplicate-" + c1["candidate_id"] + ".json")).write_text(
                json.dumps(data))
            result = mod.audit(CASES, Path(root))
            self.assertEqual(result["invalid_original_count"], 1)
            self.assertEqual(result["ambiguous_original_count"], 1)
            self.assertEqual(result["missing_original_count"], 10)
            self.assertEqual(result["original_scanner_context_count"], 0)


    def test_windows_powershell_utf8_bom_manifest_and_handoff(self):
        # Windows PowerShell 5.1 'Set-Content -Encoding UTF8' writes an
        # optional BOM. A prior local test was blocked before any case printed.
        import contextlib
        import io
        import sys
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as root:
            home = Path(root)
            folder = home / "v2r4-paper-stage-test" / "handoff_queue"
            folder.mkdir(parents=True)
            manifest = home / "casepack.json"
            manifest.write_bytes(b"\xef\xbb\xbf" + json.dumps(CASES).encode("utf-8"))
            for case in CASES["cases"]:
                candidate = original(case)
                # Use real wrapped Mini-PC filenames and optional BOM in
                # read-only historical input files.
                (folder / ("original-" + candidate["candidate_id"] + ".json")).write_bytes(
                    b"\xef\xbb\xbf" + json.dumps(candidate).encode("utf-8"))
            output, errors = io.StringIO(), io.StringIO()
            with patch.object(sys, "argv", [
                        "v3-a-archived-handoff-pit-audit.py",
                        "--casepack", str(manifest),
                        "--runtime-root", str(home)]), \
                 contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                code = mod.main()
            self.assertEqual(code, 0, errors.getvalue())
            self.assertEqual(output.getvalue().count("ORIGINAL_HANDOFF_VALID"), 12)
            self.assertIn('"valid_handoff_count": 12', output.getvalue())
            self.assertIn('"model_calls": 0', output.getvalue())
            self.assertEqual(errors.getvalue(), "")

    def test_bad_casepack_reports_read_class_not_raw_data(self):
        import contextlib
        import io
        import sys
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as root:
            file = Path(root) / "casepack.json"
            file.write_bytes(b"\xef\xbb\xbf" + b'{"candidate_id":"SECRET",broken}')
            errors = io.StringIO()
            with patch.object(sys, "argv", [
                        "v3-a-archived-handoff-pit-audit.py",
                        "--casepack", str(file),
                        "--runtime-root", str(root)]), \
                 contextlib.redirect_stderr(errors):
                code = mod.main()
            self.assertEqual(code, 2)
            self.assertIn("BLOCKED_CASEPACK_READ_JSONDecodeError", errors.getvalue())
            self.assertNotIn("SECRET", errors.getvalue())

    def test_unexpected_manifest_fails_closed(self):
        bad = dict(CASES, cases=CASES["cases"][:11])
        with self.assertRaises(ValueError):
            mod.audit(bad, Path("/dev/null"))

if __name__ == "__main__":
    unittest.main()
