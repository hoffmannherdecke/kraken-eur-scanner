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
from collections import Counter, defaultdict, deque
from decimal import Decimal
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from market_data.microstructure import (Book, flow_metrics, wall_transitions, derive_microstructure_bias)
from market_data.parity import evaluation_basis, canonical_sha256
from market_data.rest import utc, rest_market_context

CUTOFF = '2026-09-24T10:50:00Z'
REPO = 'hoffmannherdecke/kraken-eur-scanner'
MICRO_INTERVAL_SECONDS = 5
CONTEXT_INTERVAL_SECONDS = 300



def normalize_symbol(symbol):
    return symbol.replace('XBT/', 'BTC/').replace('XDG/', 'DOGE/')


def load_watchlist():
    path = Path(__file__).with_name('watchlist.json')
    if not path.exists():
        return {}
    payload = json.loads(path.read_text('utf-8'))
    out = {}
    for row in payload.get('pairs', []):
        symbol = normalize_symbol(str(row['symbol']).upper())
        if not symbol.endswith('/EUR'):
            continue
        out[symbol] = str(row.get('altname') or symbol.replace('/', ''))
    return out


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
        return row

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
                        source='Kraken Spot public REST + wss://ws.kraken.com/v2',
                        resolution='raw event-driven book/trades; derived micro snapshots every 5s; REST context every 5m',
                        coverage='per symbol/session; never infer completeness across a data gap')
        (self.path / 'manifest.json').write_text(json.dumps(manifest, indent=2))
        print('MARKET_DATA_MANIFEST ' + json.dumps(manifest), flush=True)


def github_get(path, binary=False):
    request = urllib.request.Request('https://api.github.com/repos/' + REPO + path,
              headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
                       'Accept': 'application/vnd.github+json',
                       'User-Agent': 'public-market-capture'})
    with urllib.request.urlopen(request, timeout=25) as response:
        data = response.read()
    return data if binary else json.loads(data)


def scan_candidates(seen_runs):
    """Read scanner telemetry. This observes; it never changes selection or paper counts."""
    output_by_symbol = {}
    page = 1
    while True:
        runs = github_get(f'/actions/workflows/363244800/runs?per_page=100&page={page}')['workflow_runs']
        for run in runs:
            if run['updated_at'] < CUTOFF or run['status'] != 'completed' or run['id'] in seen_runs:
                continue
            archive = github_get(f"/actions/runs/{run['id']}/logs", binary=True)
            by_symbol = {}
            with zipfile.ZipFile(io.BytesIO(archive)) as z:
                for name in z.namelist():
                    for line in z.read(name).decode(errors='replace').splitlines():
                        mrow = re.match(r'^(\S+)\s+AUDIT_ROW (\{.*\})$', line)
                        if mrow and mrow[1] >= CUTOFF:
                            try:
                                p = json.loads(mrow[2])
                            except Exception:
                                p = {}
                            pair = p.get('pair')
                            if isinstance(pair, str) and pair.endswith('/EUR'):
                                symbol = normalize_symbol(pair)
                                by_symbol[symbol] = {
                                    'scanner_run_id': run['id'], 'signal_at': mrow[1],
                                    'observer_id': hashlib.sha256((str(run['id']) + ':' + symbol).encode()).hexdigest(),
                                    'symbol': symbol, 'altname': p.get('altname') or symbol.replace('/', ''),
                                    'source': 'scanner_audit_row', 'scanner_features': p,
                                }
                            continue
                        m = re.match(r'^(\S+)\s+AUDIT_POSTED (SCANNER_CANDIDATE_V1.*)$', line)
                        if not m or m[1] < CUTOFF:
                            continue
                        pair = re.search(r'\|\s*pair=([A-Z0-9]+/EUR)(?:\s*\||\s*$)', m[2])
                        if pair and 'action=REVIEW_ONLY_NOT_ORDER' in m[2]:
                            symbol = normalize_symbol(pair[1])
                            by_symbol.setdefault(symbol, {
                                'scanner_run_id': run['id'], 'signal_at': m[1],
                                'observer_id': hashlib.sha256((str(run['id']) + ':' + symbol).encode()).hexdigest(),
                                'symbol': symbol, 'altname': symbol.replace('/', ''),
                                'source': 'scanner_posted', 'raw_signal': m[2],
                            })
            for symbol, record in by_symbol.items():
                old = output_by_symbol.get(symbol)
                if old is None or record['signal_at'] > old['signal_at']:
                    output_by_symbol[symbol] = record
            seen_runs.add(run['id'])
        if len(runs) < 100:
            return sorted(output_by_symbol.values(), key=lambda r: (r['signal_at'], r['observer_id']))
        page += 1


async def capture(seconds, out, smoke=False):
    from websockets.asyncio.client import connect
    journal = Journal(out)
    static_watch = load_watchlist()
    focus = set(static_watch) | {'BTC/EUR'}
    symbols = {**static_watch, 'BTC/EUR': 'XBTEUR'}
    journal.write('capture_start', purpose='PUBLIC_MARKET_TELEMETRY_ONLY',
                  historical_backfill=False, smoke=smoke, static_watchlist=sorted(focus))
    seen_runs = set()
    stop_at = time.monotonic() + seconds
    books, last_ids = {}, {}
    trades = defaultdict(lambda: deque(maxlen=20000))
    last_trade = {}
    price_history = defaultdict(lambda: deque(maxlen=500))
    contexts = {}
    last_micro = defaultdict(float)
    last_context = defaultdict(float)
    previous_metrics = {}
    removed_memory = defaultdict(dict)
    last_gap_ns = 0

    async def discover():
        while time.monotonic() < stop_at:
            try:
                records = await asyncio.to_thread(scan_candidates, seen_runs)
                for r in records:
                    journal.write('scanner_market_observed', **r)
                    symbols[r['symbol']] = r.get('altname') or r['symbol'].replace('/', '')
                journal.write('discovery_ok', symbols=sorted(symbols))
                print('PAPER_DISCOVERY_OK ' + json.dumps(
                    dict(symbols=sorted(symbols), new_observed=len(records))), flush=True)
            except Exception as exc:
                journal.write('discovery_error', error=type(exc).__name__, reason=str(exc)[:200])
                print('PAPER_DISCOVERY_ERROR ' + type(exc).__name__, flush=True)
            await asyncio.sleep(60)

    async def context_loop():
        while time.monotonic() < stop_at:
            for symbol, altname in list(symbols.items()):
                if time.monotonic() >= stop_at:
                    break
                if last_context[symbol] and time.monotonic() - last_context[symbol] < CONTEXT_INTERVAL_SECONDS:
                    continue
                last_context[symbol] = time.monotonic()
                try:
                    ctx = await asyncio.to_thread(rest_market_context, symbol, altname)
                    contexts[symbol] = ctx
                    journal.write('market_context', **ctx)
                    if symbol in focus:
                        print('MARKET_CONTEXT_V1 ' + json.dumps(ctx, separators=(',', ':'), sort_keys=True), flush=True)
                except Exception as exc:
                    journal.write('market_data_incomplete', symbol=symbol, component='rest_context',
                                  error=type(exc).__name__, reason=str(exc)[:160])
                    if symbol in focus:
                        print('MARKET_DATA_INCOMPLETE ' + json.dumps(
                            {'symbol': symbol, 'component': 'rest_context', 'error': type(exc).__name__}), flush=True)
                await asyncio.sleep(.35)
            await asyncio.sleep(5)

    discovery_task = asyncio.create_task(discover()) if not smoke else None
    context_task = asyncio.create_task(context_loop())
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
                        fresh = sorted(set(symbols) - subscribed)
                        if fresh:
                            for channel in ('book', 'trade'):
                                params = dict(channel=channel, symbol=fresh, snapshot=True)
                                if channel == 'book':
                                    params['depth'] = BOOK_DEPTH
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
                                symbol = row['symbol']
                                book = books.setdefault(symbol, Book())
                                book.apply(row, message['type'] == 'snapshot')
                                book_event = journal.write('book_verified', connection=connection,
                                                           symbol=symbol, exchange_at=row.get('timestamp'),
                                                           bid=str(max(book.bids)), ask=str(min(book.asks)),
                                                           spread=str(min(book.asks)-max(book.bids)),
                                                           checksum=row['checksum'], wire_seq=journal.seq)
                                now = time.monotonic()
                                if now - last_micro[symbol] >= MICRO_INTERVAL_SECONDS:
                                    last_micro[symbol] = now
                                    now_ns = time.monotonic_ns()
                                    metrics = book.metrics()
                                    mid = float(metrics['mid'])
                                    price_history[symbol].append((now_ns, mid))
                                    while price_history[symbol] and now_ns - price_history[symbol][0][0] > int(300e9):
                                        price_history[symbol].popleft()
                                    while trades[symbol] and now_ns - trades[symbol][0]['monotonic_ns'] > int(300e9):
                                        trades[symbol].popleft()
                                    old60 = next((p for ts, p in price_history[symbol]
                                                  if now_ns - ts <= int(60e9)), mid)
                                    ret60 = ((mid / old60 - 1) * 100) if old60 else None
                                    flow15 = flow_metrics(trades[symbol], now_ns, 15)
                                    flow60 = flow_metrics(trades[symbol], now_ns, 60)
                                    flow300 = flow_metrics(trades[symbol], now_ns, 300)
                                    changes = wall_transitions(previous_metrics.get(symbol), metrics, mid,
                                                               removed_memory[symbol], now_ns)
                                    previous_metrics[symbol] = metrics
                                    bias, absorption = derive_microstructure_bias(
                                        flow60, metrics['imbalance_top10'], ret60)
                                    quality = 'complete'
                                    if last_gap_ns and now_ns - last_gap_ns < int(60e9):
                                        quality = 'Marktdaten unvollständig'
                                    snapshot = {
                                        'symbol': symbol, 'exchange_at': row.get('timestamp'),
                                        'quality': quality, 'book': metrics,
                                        'source_wire_seq': book_event.get('wire_seq'),
                                        'source_trade_ids': [t['trade_id'] for t in trades[symbol]],
                                        'last_trade': last_trade.get(symbol),
                                        'flow': {'15s': flow15, '60s': flow60, '300s': flow300},
                                        'mid_return_60s_pct': ret60,
                                        'wall_events': changes,
                                        'absorption_candidate': absorption,
                                        'microstructure_bias': bias,
                                        'context_age_seconds': (
                                            max(0.0, time.time() - datetime.fromisoformat(contexts[symbol]['retrieved_at']).timestamp())
                                            if symbol in contexts else None),
                                        'context_levels': contexts.get(symbol, {}).get('levels'),
                                        'ticker24': contexts.get(symbol, {}).get('ticker'),
                                        'candles': contexts.get(symbol, {}).get('candles'),
                                    }
                                    micro_event = journal.write('micro_snapshot', **snapshot)
                                    basis = evaluation_basis(micro_event)
                                    journal.write('assessment_basis', source_seq=micro_event['seq'],
                                                  basis_sha256=canonical_sha256(basis), basis=basis)
                                    for event in changes:
                                        journal.write('wall_transition', symbol=symbol, exchange_at=row.get('timestamp'), **event)
                                    if symbol in focus:
                                        print('MICRO_SNAPSHOT_V1 ' + json.dumps(snapshot, separators=(',', ':'), sort_keys=True), flush=True)
                        elif message.get('channel') == 'trade':
                            for row in message['data']:
                                symbol, tid = row['symbol'], row['trade_id']
                                previous = last_ids.get(symbol)
                                if message['type'] == 'update' and previous is not None and tid != previous + 1:
                                    journal.write('trade_sequence_gap', symbol=symbol,
                                                  previous=previous, current=tid, connection=connection)
                                    journal.write('market_data_incomplete', symbol=symbol,
                                                  component='trade_sequence', previous=previous, current=tid)
                                last_ids[symbol] = tid
                                journal.write('trade_observed', connection=connection,
                                              snapshot=message['type']=='snapshot', **row)
                                if symbol in focus:
                                    print('TRADE_EVENT_V1 ' + json.dumps({
                                        'symbol': symbol, 'snapshot': message['type']=='snapshot',
                                        'exchange_at': row.get('timestamp'), 'trade_id': tid,
                                        'side': row.get('side'), 'price': str(row.get('price')),
                                        'qty': str(row.get('qty')),
                                    }, separators=(',', ':'), sort_keys=True), flush=True)
                                if message['type'] == 'update':
                                    trade_tick = {
                                        'monotonic_ns': time.monotonic_ns(),
                                        'exchange_at': row.get('timestamp'), 'trade_id': tid,
                                        'side': row.get('side'), 'price': str(row.get('price')),
                                        'qty': str(row.get('qty')),
                                    }
                                    trades[symbol].append(trade_tick)
                                    last_trade[symbol] = {k: v for k, v in trade_tick.items() if k != 'monotonic_ns'}
                                    if symbol in focus:
                                        print('TRADE_TICK_V1 ' + json.dumps(
                                            {'symbol': symbol, **last_trade[symbol]},
                                            separators=(',', ':'), sort_keys=True), flush=True)
                    journal.write('connection_end', connection=connection, reason='scheduled_end')
            except Exception as exc:
                last_gap_ns = time.monotonic_ns()
                journal.write('data_gap', connection=connection, error=type(exc).__name__,
                              reason=str(exc)[:200])
                journal.write('market_data_incomplete', component='websocket',
                              error=type(exc).__name__, reason=str(exc)[:160])
                await asyncio.sleep(min(5, max(0, stop_at-time.monotonic())))
    finally:
        for task in (discovery_task, context_task):
            if task:
                task.cancel()
                try:
                    await task
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
