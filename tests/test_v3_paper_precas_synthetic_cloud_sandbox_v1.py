"""Strict PRE-CAS synthetic relay sandbox gates; no live HTTP or credentials."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools.v3_paper_precas_synthetic_cloud_sandbox_v1 import (
    SANDBOX_PROJECT, PRODUCTION_PROJECT, SERIES, STAGE_SHA,
    SANDBOX_RELAY_URL, audit_offline_witness, main
)
from tools.v3_paper_precas_originalhost_offline_witness_v1 import run_offline_cases


class SyntheticCloudSandboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = (Path(self.tmp.name)/"Research"/"V3Paper"/
                     ("PRECAS-OFFLINE-ORIGINALHOST-" + STAGE_SHA[:12]))
        self.root.mkdir(parents=True)
        self.report = run_offline_cases(self.root, SERIES)
        self.report.update(
            stage_source_sha=STAGE_SHA,
            journal_path=str(self.root/"journal"))
        self.witness = self.root/"offline-model-stub-witness.json"
        self.witness.write_text(json.dumps(self.report),encoding="utf-8")

    def test_fixed_independent_project_and_original_sha_verified(self):
        self.assertNotEqual(SANDBOX_PROJECT,PRODUCTION_PROJECT)
        self.assertIn(SANDBOX_PROJECT,SANDBOX_RELAY_URL)
        self.assertNotIn(PRODUCTION_PROJECT,SANDBOX_RELAY_URL)
        result = audit_offline_witness(self.root)
        self.assertEqual(result["count"],16)
        self.assertRegex(result["joined_sha256"],r"^[0-9a-f]{64}$")
        self.assertEqual(len(result["rows"]),16)
        self.assertFalse((self.root/"isolated-test-project-only-ack.json").exists())

    def test_dynamic_readonly_audit_preserves_original_sandbox_transport_pin(self):
        from tools.v3_paper_precas_synthetic_cloud_sandbox_v1 import (
            SERIES, STAGE_SHA, SANDBOX_RELAY_URL, PRODUCTION_PROJECT,
            audit_offline_witness)
        self.assertNotIn(PRODUCTION_PROJECT, SANDBOX_RELAY_URL)
        import inspect
        source = inspect.getsource(audit_offline_witness)
        self.assertIn("stage_sha: str = STAGE_SHA", source)
        self.assertIn("series = ", source)
        self.assertIn("witness.get(\"stage_source_sha\") != stage_sha", source)
        self.assertIn("payload.get(\"series_id\") != series", source)
        with self.assertRaisesRegex(ValueError, "exact synthetic stage SHA"):
            audit_offline_witness(Path("/not-a-witness"), stage_sha="not-a-sha")

    def test_changed_original_file_rejected(self):
        path=next((self.root/"journal").glob("*.json"))
        path.write_bytes(path.read_bytes()+b" ")
        with self.assertRaisesRegex(ValueError,"SHA mismatch|no longer matches witness"):
            audit_offline_witness(self.root)

    def test_reject_untrusted_witness_and_wrong_series(self):
        self.report["source_fixture"]="LIVE_REAL_MARKET"
        self.witness.write_text(json.dumps(self.report),encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"offline-only model stub"):
            audit_offline_witness(self.root)
        self.report["source_fixture"]="SYNTHETIC_20261009_NOT_LIVE_KRAKEN"
        self.report["series_id"]="PAPER-V3-20261019T010000Z"
        self.witness.write_text(json.dumps(self.report),encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"offline-only model stub"):
            audit_offline_witness(self.root)

    def test_default_cli_is_no_network_no_token_and_no_writes(self):
        with mock.patch("sys.argv",["sandbox","--witness-root",str(self.root)]):
            with mock.patch("builtins.print") as show:
                self.assertEqual(main(),0)
                message=json.loads(show.call_args[0][0])
        self.assertEqual(message["status"],"PREVIEW_ONLY_NO_NETWORK_NO_CLOUD_WRITE")
        self.assertFalse(message["production_target_allowed"])
        self.assertEqual(message["release_gates_credited"],0)
        self.assertFalse((self.root/"isolated-test-project-only-ack.json").exists())

    def test_execute_requires_separate_ephemeral_test_token(self):
        with mock.patch("sys.argv",["sandbox","--witness-root",str(self.root),
                                   "--execute-isolated-cloud-sync"]):
            with mock.patch.dict("os.environ",{"V3_PRECAS_ISOLATED_RELAY_TOKEN":""}):
                with self.assertRaisesRegex(ValueError,"sandbox-only session token"):
                    main()
        self.assertFalse((self.root/"isolated-test-project-only-ack.json").exists())

    def test_pure_synthetic_schema_never_allows_real_market_proof(self):
        schema = (Path(__file__).resolve().parents[1]/"research"/"v3"/
                  "v3-precas-synthetic-cloud-test-only-20261019.sql").read_text()
        for marker in (
            "zxyhunwpviafyxyqysne",
            "SYNTHETIC_MODEL_STUB_NOT_ORIGINAL_MARKET",
            "fixture_only boolean NOT NULL DEFAULT true CHECK (fixture_only)",
            "PAPER-V3-CANARY-PRECAS-OFFLINE-C0D55C6C07B2",
            "REVOKE ALL ON public.v3_paper_event_receipts FROM PUBLIC, anon, authenticated",
            "enabled boolean NOT NULL DEFAULT false",
        ):
            self.assertIn(marker,schema)


if __name__=="__main__":
    unittest.main()
