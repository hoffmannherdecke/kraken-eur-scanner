"""Pre-cutover alert flood regression: one writer, matching readiness, truthful label."""
import unittest
from tools.paper_series_transition_guard import (
    PaperSeriesRoutingError, select_current_readiness, paper_completion_message_label)


def active(revision="V2R4-FROZEN", series="PAPER-V2R4-A"):
    return [{"status":"active","series_id":series,"strategy_revision":revision}]


def row(revision="V2R4-FROZEN", series="PAPER-V2R4-A"):
    return {"series_id":series,"strategy_revision":revision,
            "candidate_outcomes":100,"completion_ready":False}


class PaperTransitionAlertTests(unittest.TestCase):
    def test_existing_v2r4_remains_unchanged_and_correctly_named(self):
        self.assertEqual(select_current_readiness(active(),[row()]),row())
        self.assertEqual(paper_completion_message_label(row()),"V2R4-Paper")

    def test_v3_only_after_actual_cloud_active_identity(self):
        a=active("V3-PAPER-RELEASE","PAPER-V3-NEW")
        rows=[row(),row("V3-PAPER-RELEASE","PAPER-V3-NEW")]
        got=select_current_readiness(a,rows)
        self.assertEqual(got["series_id"],"PAPER-V3-NEW")
        self.assertEqual(paper_completion_message_label(got),"V3-Paper")

    def test_legacy_readiness_after_v3_cutover_must_not_trigger(self):
        with self.assertRaisesRegex(PaperSeriesRoutingError,"MISSING_OR_DUPLICATE"):
            select_current_readiness(active("V3-PAPER-RELEASE","PAPER-V3-NEW"),[row()])

    def test_conflicting_two_writers_must_never_be_silenced(self):
        with self.assertRaisesRegex(PaperSeriesRoutingError,"CARDINALITY"):
            select_current_readiness(active()+active("V3-PAPER-RELEASE","PAPER-V3-NEW"),[row()])
        with self.assertRaisesRegex(PaperSeriesRoutingError,"CARDINALITY"):
            select_current_readiness([],[row()])

    def test_stale_revision_or_duplicate_readiness_fail_closed(self):
        with self.assertRaisesRegex(PaperSeriesRoutingError,"WRONG_ACTIVE_REVISION"):
            select_current_readiness(active(),[row("V3-PAPER-RELEASE")])
        with self.assertRaisesRegex(PaperSeriesRoutingError,"MISSING_OR_DUPLICATE"):
            select_current_readiness(active(),[row(),row()])

    def test_unknown_strategy_cannot_assume_v3_or_v2r4(self):
        with self.assertRaisesRegex(PaperSeriesRoutingError,"UNAPPROVED"):
            select_current_readiness(active("V2R3-HISTORIC"),[row("V2R3-HISTORIC")])
        with self.assertRaisesRegex(PaperSeriesRoutingError,"UNAPPROVED"):
            paper_completion_message_label(row("V2R3-HISTORIC"))




class V3PreCASOriginalPairReviewTests(unittest.TestCase):
    """No original Windows/Cloud calls, keys, migrations or writer actions."""

    def original_pair(self):
        from datetime import datetime, timezone
        now = datetime(2026, 10, 21, 13, 30, 0, tzinfo=timezone.utc)
        shared = {
            "predecessor_series_id": "PAPER-V2R4-20261009T110135Z",
            "successor_series_id": "PAPER-V3-20261021T132950Z",
            "reviewed_v3_repo_sha": "a" * 40,
            "reviewed_v3_bundle_sha256": "b" * 64,
            "reviewed_v3_strategy_sha256": "c" * 64,
            "approved_six_proof_release_packet_sha256": "d" * 64,
            "cutover_intent_id": "e" * 32,
        }
        host = dict(shared, kind="V3_PRECAS_ORIGINALHOST_SNAPSHOT_V1",
                    source="EXTERNAL_MINIPC_PHYSICAL_OWNER", phase="QUIESCED",
                    observed_at_utc="2026-10-21T13:29:50Z",
                    old_intake_tasks_disabled=True,
                    old_intake_workers_absent=True,
                    native_no_rearm_verified=True,
                    supervisor_no_rearm_verified=True,
                    old_lifecycle_and_cloudsync_running=True,
                    v3_writer_started=False, cloud_cas_invoked=False,
                    real_money_actions=False)
        cloud = dict(shared, kind="V3_PRECAS_CLOUD_ORIGINAL_SNAPSHOT_V1",
                     source="INDEPENDENT_PRODUCTION_SQL_QUERY",
                     phase="CAS_NOT_ATTEMPTED",
                     observed_at_utc="2026-10-21T13:29:40Z",
                     read_only=True, cloud_mutations=False,
                     cloud_cas_invoked=False, v3_successor_already_present=False,
                     active_series=[{
                         "series_id": shared["predecessor_series_id"],
                         "status": "active"}],
                     original_candidate_count=5807,
                     original_last_candidate_updated_at="2026-10-21T13:29:35Z",
                     original_trade_count=0, original_last_trade_updated_at=None)
        return host, cloud, now

    def test_correlated_shapes_never_authorize_cas_or_count_six_proofs(self):
        from tools.paper_series_transition_guard import assess_v3_precas_original_pair
        host, cloud, now = self.original_pair()
        result = assess_v3_precas_original_pair(host=host, cloud=cloud, now_utc=now)
        self.assertEqual(result["disposition"],
                         "CORRELATED_SOURCE_SHAPES_ONLY_NOT_CAS_AUTHORITY")
        self.assertFalse(result["original_sources_authenticated"])
        self.assertFalse(result["fresh_database_checkpoint_for_cas"])
        self.assertFalse(result["execution_or_cloud_cas_authorized"])
        self.assertFalse(result["may_rearm_v2r4"])
        self.assertFalse(result["may_start_v3"])
        self.assertFalse(result["may_retry_unknown_cas"])
        self.assertEqual(result["six_e2e_proofs_credited"], 0)

    def test_missing_stale_forged_or_conflicting_origins_all_hold(self):
        from datetime import timedelta
        from tools.paper_series_transition_guard import assess_v3_precas_original_pair
        host, cloud, now = self.original_pair()
        examples = [
            ({"source": "CALLER_JSON"}, {}),
            ({}, {"source": "CALLER_JSON"}),
            ({"cutover_intent_id": "f" * 32}, {}),
            ({}, {"reviewed_v3_bundle_sha256": "0" * 64}),
            ({}, {"approved_six_proof_release_packet_sha256": "0" * 64}),
            ({"phase": "CAS_INVOKED"}, {}),
            ({}, {"phase": "CLOUD_COMMITTED"}),
            ({"cloud_cas_invoked": True}, {}),
            ({}, {"cloud_cas_invoked": True}),
            ({"old_intake_tasks_disabled": 1}, {}),
            ({"native_no_rearm_verified": False}, {}),
            ({"supervisor_no_rearm_verified": False}, {}),
            ({"old_lifecycle_and_cloudsync_running": False}, {}),
            ({"v3_writer_started": True}, {}),
            ({"real_money_actions": True}, {}),
            ({}, {"cloud_mutations": True}),
            ({}, {"v3_successor_already_present": True}),
            ({}, {"original_candidate_count": True}),
            ({}, {"original_trade_count": -1}),
            ({}, {"original_last_trade_updated_at": "2026-10-21T13:29:45Z"}),
            ({}, {"original_last_candidate_updated_at": None}),
            ({}, {"active_series": []}),
            ({}, {"active_series": [{"series_id":host["predecessor_series_id"],
                                      "status": "active"}, {
                                      "series_id":host["successor_series_id"],
                                      "status": "active"}]}),
            ({"observed_at_utc": "2026-10-21T13:20:00Z"}, {}),
            ({}, {"observed_at_utc": "2026-10-21T13:30:01Z"}),
            ({}, {"observed_at_utc": "2026-10-21T13:28:40Z"}),
        ]
        for missing_host, missing_cloud in (({}, {}), (None, cloud),
                                            (host, None)):
            failed = assess_v3_precas_original_pair(
                host=missing_host, cloud=missing_cloud, now_utc=now)
            self.assertEqual(failed["disposition"],
                "BLOCK_UNCORRELATED_OR_UNVERIFIED_PRECAS_ORIGINALS")
            self.assertFalse(failed["execution_or_cloud_cas_authorized"])
        for hed, ced in examples:
            with self.subTest(host=hed, cloud=ced):
                result = assess_v3_precas_original_pair(
                    host=dict(host, **hed), cloud=dict(cloud, **ced),
                    now_utc=now)
                self.assertEqual(result["disposition"],
                    "BLOCK_UNCORRELATED_OR_UNVERIFIED_PRECAS_ORIGINALS")
                self.assertFalse(result["execution_or_cloud_cas_authorized"])
        result = assess_v3_precas_original_pair(
            host=host, cloud=cloud, now_utc=now + timedelta(seconds=120))
        self.assertEqual(result["disposition"],
                         "BLOCK_UNCORRELATED_OR_UNVERIFIED_PRECAS_ORIGINALS")

    def test_nonzero_old_trade_requires_valid_version_not_fresh_event(self):
        from tools.paper_series_transition_guard import assess_v3_precas_original_pair
        host, cloud, now = self.original_pair()
        cloud = dict(cloud, original_trade_count=1,
                     original_last_trade_updated_at="2026-10-18T12:00:00Z")
        result=assess_v3_precas_original_pair(host=host, cloud=cloud, now_utc=now)
        self.assertEqual(result["disposition"],
                         "CORRELATED_SOURCE_SHAPES_ONLY_NOT_CAS_AUTHORITY")
        self.assertFalse(result["execution_or_cloud_cas_authorized"])

        # A genuine, stable old V2R4 Cloud row can retain a version timestamp
        # far before the fresh Cloud read without being a stale *readback*.
        cloud["original_last_candidate_updated_at"] = "2026-10-15T12:00:00Z"
        unchanged=assess_v3_precas_original_pair(host=host, cloud=cloud, now_utc=now)
        self.assertEqual(unchanged["disposition"],
                         "CORRELATED_SOURCE_SHAPES_ONLY_NOT_CAS_AUTHORITY")



class PaperCompletionUsageProjectionContract(unittest.TestCase):
    """Keep the expensive REST view from evaluating unused aggregates."""

    def test_watch_requests_only_alert_and_snapshot_fields(self):
        from pathlib import Path
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/paper-series-completion-watch.yml").read_text()
        anchor = 'f"/rest/v1/paper_model_usage_guard?series_id=eq.{encoded}&select="'
        self.assertEqual(workflow.count(anchor), 1)
        self.assertNotIn(
            'paper_model_usage_guard?series_id=eq.{encoded}&select=*', workflow)
        query = workflow[workflow.index(anchor):workflow.index(anchor) + 250]
        for field in (
            "series_id", "usage_state", "logical_model_calls",
            "estimated_http_attempts", "retry_overhead_requests",
            "duplicate_response_ids", "max_attempt", "cost_precision"
        ):
            with self.subTest(field=field):
                self.assertIn(field, query)
        # Scheduling, cloud writes and notification behavior remain untouched.
        self.assertIn("req(", workflow)
        self.assertIn('"/rest/v1/paper_series_completion_watch?on_conflict=series_id"', workflow)
        self.assertIn("if should_notify_usage:", workflow)



class PaperCompletionTimeoutIsolation(unittest.TestCase):
    """Execute the production error branch, not just a status-string fixture."""

    @staticmethod
    def usage_try():
        import ast
        from pathlib import Path
        source=(Path(__file__).resolve().parents[1] /
                ".github/workflows/paper-series-completion-watch.yml").read_text()
        script=source.split("          python - <<'PY'\n", 1)[1].split("\n          PY", 1)[0]
        python="\n".join(line[10:] if line.startswith("          ") else line
                         for line in script.splitlines())
        module=ast.parse(python)
        candidates=[node for node in module.body if isinstance(node, ast.Try)
                    and any(isinstance(h.type, ast.Attribute)
                            and h.type.attr=="HTTPError"
                            for h in node.handlers)]
        assert len(candidates)==1
        return compile(ast.Module(body=[candidates[0]], type_ignores=[]),
                       "<production-monitor-usage-try>", "exec")

    @staticmethod
    def fake_error(code, sqlstate):
        import io
        from urllib.error import HTTPError
        import json
        return HTTPError("https://example.invalid/rest/v1", code, "failure", {},
                         io.BytesIO(json.dumps({"code":sqlstate}).encode()))

    def test_known_database_timeout_isolated_without_fake_healthy(self):
        import json
        import urllib
        code=self.usage_try()
        def req(*args):
            raise self.fake_error(500, "57014")
        scope={"req":req,"json":json,"urllib":urllib,"encoded":"TEST",
               "usage_rows":None, "usage_timed_out":False}
        exec(code,scope)
        self.assertTrue(scope["usage_timed_out"])
        self.assertEqual(scope["usage_rows"],[])

    def test_other_errors_still_fail_closed(self):
        import json
        import urllib
        code=self.usage_try()
        for status,sqlstate in ((403,"42501"),(500,"XX000"),(503,"57014")):
            with self.subTest(status=status,sqlstate=sqlstate):
                def req(*args):
                    raise self.fake_error(status,sqlstate)
                scope={"req":req,"json":json,"urllib":urllib,"encoded":"TEST",
                       "usage_rows":None, "usage_timed_out":False}
                with self.assertRaises(urllib.error.HTTPError):
                    exec(code,scope)

    def test_success_retains_original_usage(self):
        import json
        import urllib
        code=self.usage_try()
        sample={"usage_state":"ANOMALY","logical_model_calls":12}
        scope={"req":lambda *args:(200,[sample]),"json":json,
               "urllib":urllib,"encoded":"TEST","usage_timed_out":False}
        exec(code,scope)
        self.assertFalse(scope["usage_timed_out"])
        self.assertEqual(scope["usage_rows"],[sample])

    def test_timeout_explicitly_warns_and_never_reports_healthy(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parents[1] /
                ".github/workflows/paper-series-completion-watch.yml").read_text()
        self.assertIn('usage_state=("UNAVAILABLE_TIMEOUT" if usage_timed_out',source)
        self.assertIn('should_notify_usage_timeout=(usage_timed_out and',source)
        self.assertIn('previous_usage_state!="UNAVAILABLE_TIMEOUT"',source)
        self.assertIn('if should_notify_usage_timeout:',source)
        self.assertIn('Modellnutzung ist UNBEKANNT, nicht gesund',source)
        self.assertIn('if should_notify_usage:',source)
        self.assertIn('"last_checked_at":now',source)


if __name__=="__main__":
    unittest.main()
