"""Release derivation/SQL integration checks; no production connections."""
import hashlib
import re
import unittest
from pathlib import Path
from tools.build_v3_one_time_release import build, OUTPUT

ROOT=Path(__file__).resolve().parents[1]

class ReleaseContract(unittest.TestCase):
    def test_exact_reproducible_variant(self):
        self.assertEqual(OUTPUT.read_text(), build())

    def test_inactive_original_bytes_unchanged(self):
        for path, expected in {
            'tools/minipc-v3-paper-cutover-operator-INACTIVE.ps1':'3f1649306ef6ae6da13ee521849e36e47a8842de3f40f1f5af849f640ef892e7',
            'supabase/v3-cas-prepared-fence-abort-INACTIVE.sql':'86dfebe688eda78ba14000a63f534e3295af63dcf19c48e07aab26d75e76fbd6',
        }.items():
            self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),expected)

    def test_same_cloud_ddl_with_separate_transaction_admission(self):
        source=(ROOT/'supabase/v3-cas-prepared-fence-abort-INACTIVE.sql').read_text()
        release=(ROOT/'supabase/v3-cas-prepared-fence-abort-release.sql').read_text()
        without_record=re.sub(r'(?s)DO \$release_record\$.*?END \$release_record\$;\n','',release)
        self.assertIn(source[source.index('DO $pre$'):source.index('COMMIT;')],without_record)
        self.assertLess(release.index('V3_RELEASE_INSTALL_AUTHORIZATION_CONTEXT_HOLD'),release.index('GRANT CREATE'))
        self.assertLess(release.index('pg_try_advisory_xact_lock'),release.index('GRANT CREATE'))
        self.assertIn("to_regclass('v3_cas_audit.prepared_fence_abort_v1') IS NOT NULL",release)
        self.assertNotRegex(release,r'(?im)^\s*(CREATE ROLE|ALTER ROLE|DROP|TRUNCATE|UPDATE public\.)')

    def test_native_mutations_reused_not_reimplemented(self):
        source=(ROOT/'tools/minipc-v3-paper-cutover-operator-INACTIVE.ps1').read_text()
        release=OUTPUT.read_text()
        for command in ('Disable-ScheduledTask -TaskName $name','Stop-ScheduledTask -TaskName $name',
                        'Enable-ScheduledTask -TaskName $name','Start-ScheduledTask -TaskName $name'):
            self.assertEqual(source.count(command),1)
            self.assertEqual(release.count(command),1)
        for phase in ('STOP','RESTORE','ARCHIVE'):
            self.assertIn(f"Assert-V3ReleaseMutationBoundary -Phase '{phase}'",release)
        self.assertIn('V3_RELEASE_ISSUER_EXPIRED_AFTER_LEASE',release)
        self.assertIn('TERMINAL_ABORT_BEFORE_STOP_NO_CAS_V1',release)
        self.assertIn('[IO.FileMode]::CreateNew',release)
        self.assertIn('V3_RELEASE_STOP_ALREADY_ATTEMPTED',release)
        self.assertIn('V3_RELEASE_SESSION_ALREADY_OWNED',release)

    def test_readback_is_separate_and_readonly(self):
        sql=(ROOT/'supabase/v3-cas-prepared-fence-abort-release-readback.sql').read_text()
        self.assertIn('BEGIN TRANSACTION READ ONLY;',sql)
        code=re.sub(r'(?m)^--.*','',sql)
        self.assertNotRegex(code,r'(?im)^\s*(GRANT|REVOKE|ALTER|CREATE|INSERT|UPDATE|DELETE|DROP)\b')
        for field in ('function_bodies','policies','function_acl','installation'):
            self.assertIn("'"+field+"'",sql)

if __name__=='__main__':unittest.main()
