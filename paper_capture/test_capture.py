import copy
import gzip
import hashlib
import json
import tempfile
import unittest
import io
import zipfile
from unittest.mock import patch
from decimal import Decimal as D
from pathlib import Path
from market import Book, Journal, scan_candidates
from replay import replay
from market_data.parity import evaluation_basis, canonical_sha256


def book(bid, ask):
    b = Book()
    b.asks = {D(str(ask)): D(10)}
    b.bids = {D(str(bid)): D(10)}
    b.valid = True
    return b


class CaptureTests(unittest.TestCase):
    def test_duplicate_github_logs_with_different_timestamps(self):
        data = io.BytesIO()
        signal = 'AUDIT_POSTED SCANNER_CANDIDATE_V1 | pair=MINA/EUR | action=REVIEW_ONLY_NOT_ORDER'
        with zipfile.ZipFile(data, 'w') as z:
            z.writestr('combined.txt', '2026-09-24T11:22:36.9898743Z '+signal)
            z.writestr('step.txt', '2026-09-24T11:22:36.9898697Z '+signal)
        run = dict(id=1, created_at='2026-09-24T10:49:00Z', updated_at='2026-09-24T11:23:00Z', status='completed')
        with patch('market.github_get', side_effect=[{'workflow_runs':[run]}, data.getvalue()]):
            rows = scan_candidates(set())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['symbol'], 'MINA/EUR')
        self.assertEqual(len(rows[0]['observer_id']), 64)

    def test_checksum_corruption_and_resnapshot(self):
        b = book('99.9', '100.1')
        row = dict(asks=[dict(price=D('100.1'), qty=D(10))],
                   bids=[dict(price=D('99.9'), qty=D(10))], checksum=b.checksum())
        other = Book()
        other.apply(row, True)
        with self.assertRaises(ValueError):
            other.apply(dict(asks=[dict(price=D('100.1'), qty=D(9))], checksum=row['checksum']))
        self.assertFalse(other.valid)
        other.apply(row, True)
        self.assertTrue(other.valid)

    def test_depth_impact_limits_and_insufficient_liquidity(self):
        b = book(99, 100)
        b.asks = {D(100): D(1), D(101): D(1)}
        f = b.execution('buy', 2, 10)
        self.assertEqual(D(f['price']), D('100.6005'))
        with self.assertRaises(ValueError): b.execution('buy', 3, 0)
        with self.assertRaises(ValueError): b.execution('buy', 2, 10, 100)

    def test_persisted_two_stage_stop_and_follow(self):
        p, tape = fixture()
        r = replay(p, tape, True)
        self.assertEqual([e['kind'] for e in r['events']], ['entry_1', 'entry_2', 'stop'])
        # 100.1 + 102.1 buys, 2*96.9 sell; fee on every fill (0.006).
        self.assertEqual(D(r['net_eur']), D('-10.7760'))
        self.assertEqual(r['follow_path'][-1]['price'], '106')
        self.assertEqual(len(r['fills']), 3)

    def test_ttl_revalidation_invalidation_no_entry(self):
        p, _ = fixture()
        p['expires_at'] = 3
        p['entries'][0]['trigger'] = 200
        p['entries'] = p['entries'][:1]
        tape = [dict(at=2, kind='trade', price=100, book=book(99, 101)),
                dict(at=4, kind='revalidate', persisted_at=4, expires_at=10, reason='controlled'),
                dict(at=5, kind='invalidate', persisted_at=5, reason='controlled structure event'),
                dict(at=6, kind='trade', price=210, book=book(209, 211))]
        r = replay(p, tape, True)
        self.assertEqual([e['kind'] for e in r['events']], ['TTL', 'revalidate', 'invalidate'])
        self.assertEqual(r['fills'], [])

    def test_reject_gap_ties_backdate_and_unproven_coverage(self):
        p, tape = fixture()
        with self.assertRaises(ValueError): replay(p, tape)
        bad = copy.deepcopy(p); bad['valid_from'] = 0
        with self.assertRaises(ValueError): replay(bad, tape, True)
        with self.assertRaises(ValueError): replay(p, tape + [tape[-1]], True)
        with self.assertRaises(ValueError): replay(p, [dict(at=2, kind='gap')] + tape[1:], True)

    def test_durable_hash_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = Journal(tmp)
            journal.write('signal', at=1)
            journal.write('decision', at=2)
            journal.close()
            previous = '0'*64
            with gzip.open(Path(tmp)/'events.jsonl.gz', 'rt') as f:
                for line in f:
                    self.assertEqual(json.loads(line)['previous_sha256'], previous)
                    previous = hashlib.sha256(line.rstrip('\n').encode()).hexdigest()
            self.assertEqual(previous, json.loads((Path(tmp)/'manifest.json').read_text())['final_event_sha256'])

    def test_paper_capture_persists_shared_assessment_basis(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = Journal(tmp)
            micro_event = journal.write(
                'micro_snapshot', symbol='RAY/EUR',
                exchange_at='2026-09-26T06:00:00.200Z', quality='complete',
                book=book(99.9, 100.1).metrics(),
                flow={'60s': {'buy_eur': 200.0, 'sell_eur': 0.0, 'count': 1,
                              'pressure': 1.0}},
                mid_return_60s_pct=0.0, wall_events=[],
                source_wire_seq=8, source_trade_ids=[123])
            basis = evaluation_basis(micro_event)
            journal.write('assessment_basis', source_seq=micro_event['seq'],
                          basis_sha256=canonical_sha256(basis), basis=basis)
            journal.close()
            with gzip.open(Path(tmp)/'events.jsonl.gz', 'rt') as f:
                rows = [json.loads(line) for line in f]
            saved = next(row for row in rows if row['kind'] == 'assessment_basis')
            self.assertEqual(saved['source_seq'], micro_event['seq'])
            self.assertEqual(saved['basis']['received_at'], micro_event['received_at'])
            self.assertEqual(saved['basis']['source_wire_seq'], 8)
            self.assertEqual(saved['basis_sha256'], canonical_sha256(saved['basis']))


def fixture():
    p = dict(decision_at=0, persisted_at=1, valid_from=1, expires_at=10,
             entries=[dict(trigger=100, quantity=1), dict(trigger=102, quantity=1)],
             stop=97, slippage_bps=0, follow_until=6)
    tape = [dict(at=t, kind='trade', price=p, book=book(b, a))
            for t, p, b, a in [(2,100,99.9,100.1),(3,102,101.9,102.1),
                               (4,97,96.9,97.1),(6,106,105.9,106.1)]]
    return p, tape


if __name__ == '__main__':
    unittest.main()
