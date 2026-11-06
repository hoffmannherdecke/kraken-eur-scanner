"""Offline executable-entry plumbing; no physical Windows/Cloud claims."""
import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from paper_evaluator import v3_paper_minipc_native_launcher_v1 as native


class ProductiveNativeBootstrapTests(unittest.TestCase):
    def test_bounded_parser_rejects_duplicate_and_nonfinite_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'spec.json'
            for raw in ('{"phase":1,"phase":2}', '{"v":NaN}', '[]'):
                p.write_text(raw)
                with self.subTest(raw=raw), self.assertRaises(ValueError):
                    native._bounded_release_json(p)
            p.write_text('{"valid":true}')
            self.assertEqual(native._bounded_release_json(p), {'valid': True})
            with self.assertRaises(ValueError):
                native._bounded_release_json(Path('relative.json'))

    def test_provider_uses_fixed_original_operator_and_no_secret_arguments(self):
        args = argparse.Namespace(runtime_spec='spec', approval_json='approval',
            approval_cms='cms', admission_json='admission', admission_sha256='a'*64,
            expected_source_sha='b'*40, host_receipt='host', host_cms='host-cms')
        result = argparse.Namespace(returncode=0, stdout='{"kind":"observed"}')
        with patch.object(native.subprocess, 'run', return_value=result) as run:
            self.assertEqual(native.authenticated_originalhost_release_provider(args=args), {'kind':'observed'})
        cmd = run.call_args.args[0]
        self.assertIn('PaperHostReadback', cmd)
        self.assertIn('-ExpectedReleaseCommit', cmd)
        self.assertNotIn('-PostgresPassword', cmd)
        self.assertEqual(cmd[cmd.index('-File')+1], str(Path(native.__file__).absolute().parents[1]/'tools/v3-one-time-release.ps1'))

    def test_provider_failure_never_returns_report(self):
        args = argparse.Namespace(**{k:'x' for k in ('runtime_spec','approval_json',
            'approval_cms','admission_json','admission_sha256','expected_source_sha','host_receipt','host_cms')})
        for code, out in ((1,'{}'), (0,''), (0,'[]'), (0,'x'*65537)):
            with self.subTest(code=code, length=len(out)), patch.object(native.subprocess,
                'run', return_value=argparse.Namespace(returncode=code,stdout=out)), self.assertRaises(ValueError):
                native.authenticated_originalhost_release_provider(args=args)

    def test_runtime_spec_forbids_paid_model_and_transport_injection(self):
        spec = dict.fromkeys(('kind','series_id','repo_sha','bundle_sha256','strategy_sha256',
            'phase','journal','capture_dir','model_reservations','ack_file','release_root',
            'release_packet','candidate','preflight','paper_plan'), '')
        spec.update(kind='V3_NATIVE_RELEASE_RUNTIME_SPEC_V1',repo_sha='a'*40,phase=native.PHASES[0])
        args=argparse.Namespace(expected_source_sha='a'*40)
        for extra in ('model_key','model_client','read_active_series','clock_now','approval'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                native.run_authenticated_windows_spec(args=args,spec={**spec,extra:'untrusted'})

    def test_productive_bootstrap_rejects_non_windows_before_import_or_io(self):
        argv=['native','--released-one-shot']
        for flag in ('runtime-spec','approval-json','approval-cms','admission-json',
                     'admission-sha256','expected-source-sha','host-receipt','host-cms'):
            argv += ['--'+flag,'missing']
        with patch.object(native.sys,'platform','linux'), patch.object(native.sys,'argv',argv), \
             patch.object(native,'load_native_runtime_snapshot') as load, self.assertRaises(ValueError):
            native._released_windows_bootstrap()
        load.assert_not_called()


if __name__ == '__main__':
    unittest.main()
