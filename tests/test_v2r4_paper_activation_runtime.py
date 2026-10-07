import importlib.util
import json
import tempfile
import unittest
from argparse import Namespace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_tool(filename, module_name):
    spec = importlib.util.spec_from_file_location(module_name, ROOT / "tools" / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class V2R4PaperActivationRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.local_runtime = load_tool("v2r4-paper-local-runtime.py", "v2r4_paper_local_runtime")
        cls.cloud_sync = load_tool("v2r4-paper-cloud-sync.py", "v2r4_paper_cloud_sync")

    def test_chained_wait_expiry_becomes_terminal_reject(self):
        now = datetime(2026, 10, 7, 18, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as td:
            app = Path(td)
            for name in ("paper_decisions", "paper_rechecks", "paper_revalidations"):
                (app / name).mkdir()

            control = {
                "enabled": True,
                "test_id": "PAPER-V2R4-SERIES1-20261007",
                "series_id": "PAPER-V2R4-20261007T170000Z",
                "strategy_revision": "V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION",
                "real_money_actions_enabled": False,
            }
            (app / "paper_runtime_control.json").write_text(json.dumps(control), "utf-8")

            candidate_id = "20261007-170100-BTC-EUR-r1"
            initial = {
                "test_id": control["test_id"],
                "series_id": control["series_id"],
                "strategy_revision": control["strategy_revision"],
                "candidate_id": candidate_id,
                "pair": "BTC/EUR",
                "evaluated_at_utc": "2026-10-07T17:01:00Z",
                "decision": {"decision": "WAIT", "ttl_minutes": 30},
            }
            initial_path = app / "paper_decisions" / f"{candidate_id}.json"
            initial_path.write_text(json.dumps(initial), "utf-8")

            chained = {
                "kind": "V2R4_LOCAL_TRIGGER_RECHECK_V1",
                "test_id": control["test_id"],
                "series_id": control["series_id"],
                "strategy_revision": control["strategy_revision"],
                "candidate_id": candidate_id,
                "pair": "BTC/EUR",
                "recheck_completed_at_utc": "2026-10-07T17:20:00Z",
                "decision": {"decision": "WAIT"},
                "next_wait_trigger_plan": {
                    "candidate_id": candidate_id,
                    "expires_at_utc": "2026-10-07T17:50:00Z",
                    "paper_only": True,
                },
                "paper_only": True,
                "real_money_actions_enabled": False,
                "order_api": False,
            }
            (app / "paper_rechecks" / "first-recheck.json").write_text(json.dumps(chained), "utf-8")

            self.local_runtime.reconcile_rechecks_and_expiry(app, now=now)

            rows = [
                json.loads(p.read_text("utf-8"))
                for p in (app / "paper_rechecks").glob("*.json")
            ]
            terminal = [
                r for r in rows
                if r.get("kind") == "V2R4_WAIT_EXPIRY_V1"
                and (r.get("decision") or {}).get("decision") == "REJECT"
            ]
            self.assertEqual(len(terminal), 1)
            self.assertIn("TTL_EXPIRED_NO_TRIGGER", terminal[0]["decision"]["reason_codes"])
            self.assertIsNone(terminal[0]["paper_entry"])
            self.assertFalse(terminal[0]["real_money_actions_enabled"])
            self.assertFalse(terminal[0]["order_api"])

            mirror = json.loads(
                (app / "paper_revalidations" / initial_path.name).read_text("utf-8")
            )
            self.assertEqual(mirror["decision"]["decision"], "REJECT")
            self.assertEqual(mirror["kind"], "V2R4_WAIT_EXPIRY_V1")

    def test_wait_without_followup_plan_fails_closed(self):
        now = datetime(2026, 10, 7, 18, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as td:
            app = Path(td)
            for name in ("paper_decisions", "paper_rechecks", "paper_revalidations"):
                (app / name).mkdir()
            control = {
                "test_id": "T",
                "series_id": "PAPER-V2R4-20261007T170000Z",
                "strategy_revision": "V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION",
                "real_money_actions_enabled": False,
            }
            (app / "paper_runtime_control.json").write_text(json.dumps(control), "utf-8")
            initial = {
                "series_id": control["series_id"],
                "candidate_id": "C1",
                "pair": "ETH/EUR",
                "evaluated_at_utc": "2026-10-07T17:01:00Z",
                "decision": {"decision": "WAIT", "ttl_minutes": 30},
            }
            (app / "paper_decisions" / "C1.json").write_text(json.dumps(initial), "utf-8")
            bad_wait = {
                "series_id": control["series_id"],
                "candidate_id": "C1",
                "pair": "ETH/EUR",
                "recheck_completed_at_utc": "2026-10-07T17:20:00Z",
                "decision": {"decision": "WAIT"},
                "next_wait_trigger_plan": None,
            }
            (app / "paper_rechecks" / "bad.json").write_text(json.dumps(bad_wait), "utf-8")

            self.local_runtime.reconcile_rechecks_and_expiry(app, now=now)
            mirror = json.loads((app / "paper_revalidations" / "C1.json").read_text("utf-8"))
            self.assertEqual(mirror["decision"]["decision"], "REJECT")
            self.assertIn("WAIT_WITHOUT_TRIGGER_PLAN", mirror["decision"]["reason_codes"])

    def test_cloud_sync_batches_large_series_below_relay_caps(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Secrets").mkdir()
            (root / "State").mkdir()
            (root / "Secrets" / "shadow-evidence-token.txt").write_text("x" * 32, "utf-8")
            candidates = [{"candidate_id": f"C{i}"} for i in range(501)]
            trades = [{"candidate_id": f"T{i}"} for i in range(101)]
            control = {
                "series_id": "PAPER-V2R4-20261007T170000Z",
                "strategy_revision": "V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION",
            }
            calls = []

            def fake_post(endpoint, token, payload):
                calls.append(payload)
                self.assertLessEqual(len(payload["candidates"]), 200)
                self.assertLessEqual(len(payload["trades"]), 50)
                return {
                    "ok": True,
                    "accepted_candidates": len(payload["candidates"]),
                    "accepted_trades": len(payload["trades"]),
                }

            args = Namespace(
                app_root=root / "app",
                trading_root=root,
                endpoint="https://example.invalid",
                interval_seconds=60,
                once=True,
            )
            with patch.object(self.cloud_sync, "collect", return_value=(control, candidates, trades)), \
                 patch.object(self.cloud_sync, "post", side_effect=fake_post):
                result = self.cloud_sync.run_once(args)

            self.assertEqual(result["status"], "HEALTHY")
            self.assertEqual(result["accepted_candidates"], 501)
            self.assertEqual(result["accepted_trades"], 101)
            self.assertEqual(result["batches"], 6)
            self.assertEqual(len(calls), 6)

            # Same unchanged cohort must not be re-uploaded every minute.
            with patch.object(self.cloud_sync, "collect", return_value=(control, candidates, trades)), \
                 patch.object(self.cloud_sync, "post", side_effect=fake_post):
                second = self.cloud_sync.run_once(args)
            self.assertEqual(second["status"], "HEALTHY")
            self.assertEqual(second["pending_candidates"], 0)
            self.assertEqual(second["pending_trades"], 0)
            self.assertEqual(second["batches"], 0)
            self.assertEqual(len(calls), 6)

    def test_activation_installer_and_relay_require_exact_provenance(self):
        installer = (ROOT / "tools" / "install-minipc-v2r4-paper-runtime.ps1").read_text("utf-8")
        relay = (ROOT / "supabase" / "functions" / "v2r4-paper-evidence-relay" / "index.ts").read_text("utf-8")
        for marker in (
            "release_repo_sha",
            "strategy_fingerprint_sha256",
            "runtime_bundle_fingerprint_sha256",
            "candidate_merge_sha",
        ):
            self.assertIn(marker, installer)
            self.assertIn(marker, relay)
        self.assertIn("$healthAge", installer)
        self.assertIn("checked_at_local", installer)
        self.assertIn("MINI-PC health timestamp missing from watchdog report.", installer)
        self.assertIn("git pull --ff-only", installer)
        self.assertIn("real_money_actions_enabled=$false", installer)
        self.assertIn('config.real_money_actions_enabled!==false', relay)
        self.assertIn('unexpected_first_series_sizing', relay)
        alerts = (ROOT / "tools" / "v2r4-paper-alerts.py").read_text("utf-8")
        workflow = (ROOT / ".github" / "workflows" / "v2r4-paper-alerts.yml").read_text("utf-8")
        self.assertIn("v2r4_paper_alert_receipts", alerts)
        self.assertIn("workflow_dispatch", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        constraints = (ROOT / "supabase" / "v2r4-paper-activation-constraints.sql").read_text("utf-8")
        self.assertIn("paper_series_single_active_idx", constraints)
        self.assertIn("where status = 'active'", constraints)
        self.assertIn("predecessor_not_active_without_successor", relay)
        self.assertIn("activation_second_factor_unauthorized", relay)
        self.assertIn("minipc_not_fresh_healthy_ok", relay)
        self.assertIn("X-MiniPC-Status-Token", installer)
        self.assertIn("minipc-status-sync.py", installer)


if __name__ == "__main__":
    unittest.main()
