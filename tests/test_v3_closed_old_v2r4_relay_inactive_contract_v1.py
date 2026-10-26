"""Release-only static contract for existing V2R4 Edge relay closed-original lane.

No actual Edge deployment, Cloud modification or live old trade event here.
The physical single-writer owner must independently prove genuine host/Cloud
closed-series followup+trade ACK before the V3 Paper CAS release.
"""
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EDGE=ROOT/"supabase/functions/v2r4-paper-evidence-relay/index.ts"


class ClosedOriginalV2R4RelayInactiveContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script=EDGE.read_text(encoding="utf-8")
        cls.old_begin=cls.script.index('if(action==="sync_closed_original_followups")')
        cls.old_end=cls.script.index('if(action==="sync")',cls.old_begin)
        cls.closed=cls.script[cls.old_begin:cls.old_end]
        cls.active=cls.script[cls.old_end:]

    def test_original_active_v2r4_sync_still_active_only(self):
        self.assertIn('if(action==="sync"){',self.active)
        self.assertIn('series.status!=="active"',self.active)
        self.assertIn('admin.from("paper_candidate_outcomes").upsert',self.active)
        self.assertIn('admin.from("paper_trade_results").upsert',self.active)
        self.assertNotIn('sync_closed_original_followups',self.active)

    def test_closed_series_requires_two_existing_credentials_and_live_v3(self):
        for need in (
            'X-MiniPC-Status-Token',
            'credentialAuthorized(admin,statusToken,"minipc-status-relay")',
            'oldSeries?.status!=="strategy_cutover_closed"',
            'oldSeries?.config?.release_repo_sha!==expectedSha',
            'activeRows.length!==1',
            'activeRows[0]?.series_id!==expectedV3Sid',
            'startsWith("V3-")',
            'candidates.length>20',
            'trades.length>20',
        ):
            with self.subTest(need=need):self.assertIn(need,self.closed)
        # First authentication (X-Shadow-Evidence-Token) already occurs
        # before the entire action dispatch, reused from original relay.
        self.assertLess(self.script.index('if(!(await authorized(admin,req)))'),
                        self.old_begin)

    def test_closed_path_pins_exact_v3_successor_and_old_predecessor(self):
        # A generic active V3 series is insufficient: old-series aftercare
        # must be routed only to the exact CAS successor submitted by host.
        for need in (
            'const expectedV3Sid=String(body?.expected_active_v3_series_id??"")',
            '!/^PAPER-V3-\\d{8}T\\d{6}Z$/.test(expectedV3Sid)',
            '.select("series_id,status,strategy_revision,config")',
            'activeRows[0]?.series_id!==expectedV3Sid',
            'activeRows[0]?.config?.predecessor_series_id!==sid',
            'oldSeries?.status!=="strategy_cutover_closed"',
        ):
            with self.subTest(need=need):self.assertIn(need,self.closed)
        self.assertNotIn(
            '!String(activeRows[0]?.series_id??"").startsWith("PAPER-V3-")',
            self.closed)

    def test_closed_path_cannot_insert_new_original_candidates_or_trades(self):
        self.assertNotRegex(self.closed,r'(?i)\.upsert\(')
        self.assertNotRegex(self.closed,r'(?i)\.insert\(')
        self.assertNotIn('.delete(',self.closed)
        self.assertNotIn('action:"activate"',self.closed)
        for name in (
            'closed_original_candidate_not_preexisting',
            'closed_original_trade_not_preexisting',
            'new_old_series_entry_disallowed',
            'paper_candidate_outcomes',
            'paper_trade_results',
            '.eq("candidate_id",cid).eq("series_id",sid)',
            '.eq("updated_at",prior.updated_at)',
            'closed_followup_optimistic_cas_conflict',
            'closed_trade_optimistic_cas_conflict',
        ):
            with self.subTest(name=name):self.assertIn(name,self.closed)

    def test_cloud_itself_rejects_post_cutover_old_wait_rechecks(self):
        # The old Windows sender already checks this chronology, but the
        # independently accessible Edge action must reject bypass packets.
        self.assertIn('activeRows[0]?.config?.series_started_at_utc',self.closed)
        self.assertIn('v3_successor_cutover_clock_unverified',self.closed)
        self.assertIn('old_wait_recheck_after_v3_cutover',self.closed)
        self.assertIn('old_wait_recheck_invalid',self.closed)
        self.assertIn('"recheck_started_at_utc"',self.closed)
        self.assertIn('"recheck_completed_at_utc"',self.closed)
        self.assertIn('"completed_at_utc"',self.closed)
        self.assertIn('"revalidated_at_utc"',self.closed)
        self.assertIn('at>=cutoverMs',self.closed)
        self.assertIn('terminalRecheckFields.some(field=>{',self.closed)
        self.assertIn('Number.isFinite(at)&&at<cutoverMs',self.closed)
        self.assertLess(self.closed.index('old_wait_recheck_after_v3_cutover'),
                        self.closed.index('acceptedCandidates++'))
        self.assertLess(self.closed.index('v3_successor_cutover_clock_unverified'),
                        self.closed.index('for(const row of candidates)'))

    def test_closed_path_retains_original_identity_and_completed_horizons(self):
        for text in (
            'canonicalJson(prior.payload?.decision)',
            'canonicalJson(row.payload?.decision)',
            'safeUtcMs(prior.evaluated_at)',
            'safeUtcMs(row.evaluated_at)',
            'old_completed_horizon_immutable',
            'old_followup_identity_changed',
            'old_followup_time_regression',
            'old_followup_same_timestamp_conflict',
            'new_v2r4_intake_allowed:false',
        ):
            with self.subTest(text=text):self.assertIn(text,self.closed)

    def test_historical_followup_timestamp_not_compared_to_later_cloud_ack_clock(self):
        # In real V2R4 originals the Cloud row was often rewritten after
        # the original followup time. Compare original event clocks only.
        for marker in (
            "safeUtcMs(follow.updated_at_utc)",
            "safeUtcMs(prior.followup.updated_at_utc)",
            "stamp<oldFollowStamp",
            "stamp===oldFollowStamp",
            "canonicalJson(prior.followup)===canonicalJson(follow)",
            "Math.max(Date.now(),cloudStamp+1,stamp)",
            '.eq("updated_at",prior.updated_at)',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker,self.closed)
        self.assertNotIn("stamp<oldStamp",self.closed)
        self.assertNotIn("updated_at:new Date(stamp).toISOString()",self.closed)

    def test_historical_trade_exit_checks_economic_events_not_ack_timestamp(self):
        for marker in (
            "safeUtcMs(prior.updated_at)",
            "prior.payload?.events",
            "eventStamp>closed",
            "Math.max(Date.now(),oldUpdated+1,closed)",
            '.eq("updated_at",prior.updated_at)',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker,self.closed)
        self.assertNotIn("closed<oldUpdated",self.closed)
        self.assertNotIn("updated_at:new Date(closed).toISOString()",self.closed)

    def test_terminal_open_trade_only_cannot_create_new_entry(self):
        for text in (
            'row?.status!=="CLOSED"',
            'safeUtcMs(prior.opened_at)!==safeUtcMs(row.opened_at)',
            'canonicalJson(prior.payload?.entry??null)',
            'canonicalJson(row.payload?.entry??null)',
            'row?.payload?.real_money_actions_enabled!==false',
            'prior.status==="CLOSED"',
            'immutable_old_closed_trade_conflict',
            'row.payload.exit',
            'net_pnl_eur',
            'net_return_pct',
        ):
            with self.subTest(text=text):self.assertIn(text,self.closed)
        self.assertNotRegex(self.closed,r'(?i)register.*scheduledtask')


if __name__=="__main__":unittest.main()
