"""Public Kraken telemetry only. No strategy, account access, or order API."""
import argparse
import asyncio
import gzip
import hashlib
import io
import json
import os
import re
import time
import urllib.request
import uuid
import zipfile
import zlib
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

CUTOFF = '2026-09-24T10:50:00Z'
REPO = 'hoffmannherdecke/kraken-eur-scanner'


def utc():
    return datetime.now(timezone.utc).isoformat()


class Book:
    def __init__(self):
        self.asks, self.bids = {}, {}
        self.valid = False

    def checksum(self):
        def digits(x):
            return format(Decimal(x), 'f').replace('.', '').lstrip('0')
        text = ''
        for levels, reverse in ((self.asks, False), (self.bids, True)):
            for price in sorted(levels, reverse=reverse)[:10]:
                text += digits(price) + digits(levels[price])
        return zlib.crc32(text.encode()) & 0xffffffff

    def apply(self, row, snapshot=False):
        if snapshot:
            self.asks, self.bids = {}, {}
        elif not self.valid:
            raise ValueError('book update without valid snapshot')
        for side, reverse in (('asks', False), ('bids', True)):
            levels = getattr(self, side)
            for level in row.get(side, []):
                p, q = Decimal(level['price']), Decimal(level['qty'])
                if q == 0:
                    levels.pop(p, None)
                else:
                    levels[p] = q
            for p in sorted(levels, reverse=reverse)[10:]:
                del levels[p]
        self.valid = (bool(self.asks and self.bids)
                      and max(self.bids) < min(self.asks)
                      and self.checksum() == int(row['checksum']))
        if not self.valid:
            raise ValueError('book checksum or crossed/empty book')

    def execution(self, side, quantity, extra_slippage_bps, limit=None):
        """Depth VWAP + explicitly chosen adverse assumption; never a real fill."""
        if not self.valid:
            raise ValueError('unverified book')
        quantity = Decimal(str(quantity))
        bps = Decimal(str(extra_slippage_bps))
        if quantity <= 0 or bps < 0 or side not in ('buy', 'sell'):
            raise ValueError('invalid execution inputs')
        levels = self.asks if side == 'buy' else self.bids
        ordered = sorted(levels, reverse=side == 'sell')
        remaining, notional = quantity, Decimal(0)
        for price in ordered:
            take = min(remaining, levels[price])
            notional += take * price
            remaining -= take
            if remaining == 0:
                break
        if remaining:
            raise ValueError('insufficient recorded depth: fill_unknown')
        vwap = notional / quantity
        simulated = vwap * (1 + (bps / 10000 if side == 'buy' else -bps / 10000))
        if limit is not None and ((side == 'buy' and simulated > Decimal(str(limit)))
                                  or (side == 'sell' and simulated < Decimal(str(limit)))):
            raise ValueError('not marketable within limit: fill_unknown')
        return {'price': str(simulated), 'depth_vwap': str(vwap),
                'best': str(ordered[0]), 'quantity': str(quantity),
                'notional': str(simulated * quantity),
                'extra_slippage_bps_assumption': str(bps)}


class Journal:
    def __init__(self, path):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.file = gzip.open(self.path / 'events.jsonl.gz', 'wt')
        self.session = str(uuid.uuid4())
        self.seq = 0
        self.previous = '0' * 64
        self.counts = Counter()
        self.started = utc()

    def write(self, kind, **data):
        self.seq += 1
        row = dict(kind=kind, session=self.session, seq=self.seq,
                   received_at=utc(), received_ns=time.time_ns(),
                   monotonic_ns=time.monotonic_ns(), previous_sha256=self.previous, **data)
        raw = json.dumps(row, separators=(',', ':'), sort_keys=True, default=str)
        self.previous = hashlib.sha256(raw.encode()).hexdigest()
        self.file.write(raw + '\n')
        self.file.flush()
        self.counts[kind] += 1

    def close(self):
        self.write('capture_end')
        self.file.close()
        raw = (self.path / 'events.jsonl.gz').read_bytes()
        manifest = dict(session=self.session, started=self.started, ended=utc(),
                        events=self.seq, counts=dict(self.counts),
                        final_event_sha256=self.previous,
                        archive_sha256=hashlib.sha256(raw).hexdigest(),
                        run_id=os.getenv('GITHUB_RUN_ID'),
                        run_attempt=os.getenv('GITHUB_RUN_ATTEMPT'),
                        code_sha=os.getenv('GITHUB_SHA'),
                        source='wss://ws.kraken.com/v2',
                        resolution='event-driven, no resampling',
                        coverage='per symbol/session; not a global completeness claim')
        (self.path / 'manifest.json').write_text(json.dumps(manifest, indent=2))
        print('PAPER_CAPTURE_MANIFEST ' + json.dumps(manifest), flush=True)


def github_get(path, binary=False):
    # Token is used exclusively against the GitHub API, never sent to Kraken.
    request = urllib.request.Request('https://api.github.com/repos/' + REPO + path,
              headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
                       'Accept': 'application/vnd.github+json',
                       'User-Agent': 'public-market-capture'})
    with urllib.request.urlopen(request, timeout=25) as response:
        data = response.read()
    return data if binary else json.loads(data)


def scan_candidates(seen_runs):
    """Read existing public scanner output, never choose or count paper trades."""
    output = []
    page = 1
    while True:
        runs = github_get(f'/actions/workflows/363244800/runs?per_page=100&page={page}')['workflow_runs']
        stop = False
        for run in runs:
            if run['updated_at'] < CUTOFF:
                continue
            if run['status'] != 'completed' or run['id'] in seen_runs:
                continue
            archive = github_get(f"/actions/runs/{run['id']}/logs", binary=True)
            unique = set()
            with zipfile.ZipFile(io.BytesIO(archive)) as z:
                for name in z.namelist():
                    for line in z.read(name).decode(errors='replace').splitlines():
                        m = re.match(r'^(\S+)\s+AUDIT_POSTED (SCANNER_CANDIDATE_V1.*)$', line)
                        if not m or m[1] < CUTOFF or m[0] in unique:
                            continue
                        pair = re.search(r'\|\s*pair=([A-Z0-9]+/EUR)(?:\s*\||\s*$)', m[2])
                        if pair and 'action=REVIEW_ONLY_NOT_ORDER' in m[2]:
                            unique.add(m[0])
                            symbol = pair[1].replace('XBT/', 'BTC/').replace('XDG/', 'DOGE/')
                            output.append(dict(scanner_run_id=run['id'], signal_at=m[1],
                                               symbol=symbol, raw_signal=m[2]))
            seen_runs.add(run['id'])
        if stop or len(runs) < 100:
            return output
        page += 1


async def capture(seconds, out, smoke=False):
    from websockets.asyncio.client import connect
    journal = Journal(out)
    journal.write('capture_start', purpose='PUBLIC_MARKET_TELEMETRY_ONLY',
                  historical_backfill=False, smoke=smoke)
    symbols = {'BTC/EUR'}  # Explicit technical probe, never a paper candidate.
    seen_runs = set()
    stop_at = time.monotonic() + seconds
    books, last_ids = {}, {}

    async def discover():
        while time.monotonic() < stop_at:
            try:
                records = await asyncio.to_thread(scan_candidates, seen_runs)
                for r in records:
                    journal.write('scanner_signal_observed', **r)
                    symbols.add(r['symbol'])
                journal.write('discovery_ok', symbols=sorted(symbols))
                print('PAPER_DISCOVERY_OK ' + json.dumps(dict(symbols=sorted(symbols), new_signals=len(records))), flush=True)
            except Exception as exc:
                journal.write('discovery_error', error=type(exc).__name__)
                print('PAPER_DISCOVERY_ERROR ' + type(exc).__name__, flush=True)
            await asyncio.sleep(60)

    discovery_task = asyncio.create_task(discover()) if not smoke else None
    connection = 0
    try:
        while time.monotonic() < stop_at:
            connection += 1
            subscribed = set()
            books.clear()
            last_ids.clear()
            try:
                async with connect('wss://ws.kraken.com/v2', open_timeout=15,
                                   ping_interval=10, ping_timeout=10,
                                   max_size=8*1024*1024) as ws:
                    journal.write('connection_start', connection=connection)
                    while time.monotonic() < stop_at:
                        fresh = sorted(symbols - subscribed)
                        if fresh:
                            for channel in ('book', 'trade'):
                                params = dict(channel=channel, symbol=fresh, snapshot=True)
                                if channel == 'book':
                                    params['depth'] = 10
                                await ws.send(json.dumps(dict(method='subscribe', params=params)))
                            subscribed.update(fresh)
                            journal.write('subscription_requested', connection=connection, symbols=fresh)
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=min(2, max(.01, stop_at-time.monotonic())))
                        except asyncio.TimeoutError:
                            continue
                        journal.write('wire', connection=connection, raw=raw)
                        message = json.loads(raw, parse_float=Decimal)
                        if message.get('success') is False:
                            journal.write('subscription_error', connection=connection, response=message)
                        if message.get('channel') == 'book':
                            for row in message['data']:
                                book = books.setdefault(row['symbol'], Book())
                                book.apply(row, message['type'] == 'snapshot')
                                journal.write('book_verified', connection=connection,
                                              symbol=row['symbol'], exchange_at=row.get('timestamp'),
                                              bid=str(max(book.bids)), ask=str(min(book.asks)),
                                              spread=str(min(book.asks)-max(book.bids)),
                                              checksum=row['checksum'], wire_seq=journal.seq)
                        elif message.get('channel') == 'trade':
                            for row in message['data']:
                                symbol, tid = row['symbol'], row['trade_id']
                                previous = last_ids.get(symbol)
                                if message['type'] == 'update' and previous is not None and tid != previous + 1:
                                    journal.write('trade_sequence_gap', symbol=symbol,
                                                  previous=previous, current=tid, connection=connection)
                                last_ids[symbol] = tid
                                journal.write('trade_observed', connection=connection,
                                              snapshot=message['type']=='snapshot', **row)
                    journal.write('connection_end', connection=connection, reason='scheduled_end')
            except Exception as exc:
                journal.write('data_gap', connection=connection, error=type(exc).__name__,
                              reason=str(exc)[:200])
                await asyncio.sleep(min(5, max(0, stop_at-time.monotonic())))
    finally:
        if discovery_task:
            discovery_task.cancel()
            try:
                await discovery_task
            except asyncio.CancelledError:
                pass
        journal.close()
    if smoke and (journal.counts['book_verified'] < 2 or journal.counts['trade_observed'] == 0
                  or journal.counts['data_gap'] or journal.counts['subscription_error']):
        raise SystemExit('live smoke incomplete/failed; inspect artifact')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--seconds', type=int, required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    asyncio.run(capture(args.seconds, args.out, args.smoke))
