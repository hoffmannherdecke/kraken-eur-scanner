import copy
import gzip
import hashlib
import json
import tempfile
import unittest
from decimal import Decimal as D
from pathlib import Path
from market import Book, Journal
from replay import replay


def book(bid, ask):
    b = Book()
    b.asks = {D(str(ask)): D(10)}
    b.bids = {D(str(bid)): D(10)}
    b.valid = True
    return b


class CaptureTests(unittest.TestCase):
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
