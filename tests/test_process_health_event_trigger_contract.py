"""Offline policy checks for the *existing* scanner health watchdog event fast-path.

These assert source wiring and protect against creating a failed-scan retry loop;
they do not claim a real GitHub event delivery or a faster Slack receipt.
"""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
HEALTH=ROOT / ".github/workflows/process-health.yml"
SCAN=ROOT / ".github/workflows/scan.yml"
RECOVERY=ROOT / ".github/workflows/scanner-startup-recovery.yml"

class ProcessHealthEventTriggerContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.health=HEALTH.read_text(encoding="utf-8")
        cls.scan=SCAN.read_text(encoding="utf-8")
        cls.startup_recovery=RECOVERY.read_text(encoding="utf-8")

    def test_existing_five_minute_fallback_unchanged(self):
        self.assertIn("cron: '4,9,14,19,24,29,34,39,44,49,54,59 * * * *'",self.health)
        self.assertIn("workflow_dispatch:",self.health)
        self.assertIn("group: crypto-process-health",self.health)
        self.assertIn("cancel-in-progress: false",self.health)

    def test_completion_event_target_is_exact_existing_scanner(self):
        self.assertRegex(self.health,r"workflow_run:\s+workflows:\s+- Kraken EUR early sensor\s+types:\s+- completed")
        self.assertIn("name: Kraken EUR early sensor",self.scan)
        self.assertIn("workflow_run:",self.startup_recovery)
        self.assertIn("group: scanner-startup-recovery",self.startup_recovery)

    def test_sensitive_audit_job_fail_closed_on_untrusted_or_failure(self):
        predicate=next(line.strip() for line in self.health.splitlines()
                       if line.strip().startswith("if: ${{ github.event_name"))
        required=(
            "github.event_name != 'workflow_run'",
            "github.event.workflow_run.conclusion == 'success'",
            "github.event.workflow_run.event == 'schedule'",
            "github.event.workflow_run.event == 'workflow_dispatch'",
            "github.event.workflow_run.head_branch == 'main'",
            "github.event.workflow_run.head_repository.full_name == github.repository",
        )
        for item in required:
            with self.subTest(item=item):
                self.assertIn(item,predicate)
        self.assertNotIn("cancel-in-progress: true",self.health)
        # In particular: no retry on failed manual scans; the separate
        # startup-recovery owner already handles bounded startup_failure.
        self.assertIn("github.event.workflow_run.conclusion == 'startup_failure'",self.startup_recovery)
        self.assertIn("github.event.workflow_run.event == 'schedule'",self.startup_recovery)

    def test_reuse_one_alert_router_and_one_state_store(self):
        self.assertEqual(self.health.count("python process_audit.py"),1)
        self.assertEqual(self.health.count("python tools/process-health-alert-router.py process_health.json"),1)
        self.assertIn("if: always() && hashFiles('process_health.json') != ''",self.health)
        self.assertIn("group: crypto-process-health",self.health)
        self.assertEqual(self.health.count("SUPABASE_SECRET_KEY:"),1)
        self.assertEqual(self.health.count("SLACK_WEBHOOK_URL:"),1)
        self.assertNotIn("SUPABASE_SECRET_KEY:",self.scan)
        self.assertNotIn("SLACK_WEBHOOK_URL:",self.scan)
        # Both events share the same existing router/dedupe, no new issue
        # table, scheduler, action permission or scanner source change.
        self.assertIn("actions: write",self.health)
        self.assertIn("contents: read",self.health)

if __name__ == "__main__":
    unittest.main()
