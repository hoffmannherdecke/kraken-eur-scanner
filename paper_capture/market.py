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
import urllib.parse
import urllib.request
import uuid
import zipfile
import zlib
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from statistics import median

CUTOFF = '2026-09-24T10:50:00Z'
REPO = 'hoffmannherdecke/kraken-eur-scanner'
MICRO_INTERVAL_SECONDS = 5
CONTEXT_INTERVAL_SECONDS = 300


def utc():
    return datetime.now(timezone.utc).isoformat()


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

    def _impact_for_notional(self, side, eur):
        levels = self.asks if side == 'buy' else self.bids
        ordered = sorted(levels, reverse=side == 'sell')
        remaining = Decimal(str(eur))
        qty = Decimal(0)
        spent = Decimal(0)
        for price in ordered:
            level_eur = price * levels[price]
            take_eur = min(remaining, level_eur)
            qty += take_eur / price
            spent += take_eur
            remaining -= take_eur
            if remaining <= 0:
                break
        if remaining > 0 or qty <= 0:
            return None
        vwap = spent / qty
        best = ordered[0]
        bps = ((vwap / best - 1) if side == 'buy' else (1 - vwap / best)) * 10000
        return {'vwap': str(vwap), 'impact_bps': float(bps)}

    def metrics(self):
        if not self.valid:
            raise ValueError('unverified book')
        bids = sorted(self.bids, reverse=True)
        asks = sorted(self.asks)
        bid, ask = bids[0], asks[0]
        mid = (bid + ask) / 2

        def rows(levels, prices):
            return [{'price': str(p), 'qty': str(levels[p]),
                     'notional_eur': float(p * levels[p])} for p in prices]

        bid_rows, ask_rows = rows(self.bids, bids), rows(self.asks, asks)
        bid_notional = sum(x['notional_eur'] for x in bid_rows)
        ask_notional = sum(x['notional_eur'] for x in ask_rows)
        total = bid_notional + ask_notional
        imbalance = ((bid_notional - ask_notional) / total) if total else None

        def depth_within(levels, prices, bps, side):
            total_eur = 0.0
            for p in prices:
                dist = ((mid - p) / mid if side == 'bid' else (p - mid) / mid) * 10000
                if dist <= bps:
                    total_eur += float(p * levels[p])
            return total_eur

        def prominent(level_rows):
            vals = [x['notional_eur'] for x in level_rows]
            med = median(vals) if vals else 0.0
            out = sorted(level_rows, key=lambda x: x['notional_eur'], reverse=True)[:3]
            return [dict(x, relative_to_median=(x['notional_eur'] / med if med else None)) for x in out]

        return {
            'bid': str(bid), 'ask': str(ask), 'mid': str(mid),
            'spread_eur': str(ask - bid),
            'spread_pct': float((ask - bid) / mid * 100) if mid else None,
            'imbalance_top10': imbalance,
            'bid_notional_top10_eur': bid_notional,
            'ask_notional_top10_eur': ask_notional,
            'depth_bid_eur': {str(b): depth_within(self.bids, bids, b, 'bid') for b in (10, 25, 50, 100)},
            'depth_ask_eur': {str(b): depth_within(self.asks, asks, b, 'ask') for b in (10, 25, 50, 100)},
            'prominent_bids': prominent(bid_rows),
            'prominent_asks': prominent(ask_rows),
            'bids': bid_rows, 'asks': ask_rows,
            'impact_curve_eur': {
                str(eur): {'buy': self._impact_for_notional('buy', eur),
                           'sell': self._impact_for_notional('sell', eur)}
                for eur in (50, 75, 100, 150, 250, 500)
            },
        }


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
                        source='Kraken Spot public REST + wss://ws.kraken.com/v2',
                        resolution='raw event-driven book/trades; derived micro snapshots every 5s; REST context every 5m',
                        coverage='per symbol/session; never infer completeness across a data gap')
        (self.path / 'manifest.json').write_text(json.dumps(manifest, indent=2))
        print('PAPER_CAPTURE_MANIFEST ' + json.dumps(manifest), flush=True)


def github_get(path, binary=False):
    request = urllib.request.Request('https://api.github.com/repos/' + REPO + path,
              headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
                       'Accept': 'application/vnd.github+json',
                       'User-Agent': 'public-market-capture'})
    with urllib.request.urlopen(request, timeout=25) as response:
        data = response.read()
    return data if binary else json.loads(data)


def kraken_public(path, params=None):
    query = urllib.parse.urlencode(params or {})
    url = 'https://api.kraken.com' + path + (('?' + query) if query else '')
    req = urllib.request.Request(url, headers={'User-Agent': 'kraken-eur-market-observer/2.0'})
    with urllib.request.urlopen(req, timeout=20) as response:
        payload = json.loads(response.read().decode())
    if payload.get('error'):
        raise RuntimeError(';'.join(payload['error']))
    return payload.get('result', {})


def _aggregate_ohlc(rows, minutes):
    buckets = {}
    span = minutes * 60
    for r in rows:
        t = int(float(r[0]))
        key = t - (t % span)
        b = buckets.setdefault(key, {'time': key, 'open': float(r[1]), 'high': float(r[2]),
                                     'low': float(r[3]), 'close': float(r[4]), 'volume': 0.0})
        b['high'] = max(b['high'], float(r[2]))
        b['low'] = min(b['low'], float(r[3]))
        b['close'] = float(r[4])
        b['volume'] += float(r[6])
    return [buckets[k] for k in sorted(buckets)]


def rest_market_context(symbol, altname):
    ohlc_result = kraken_public('/0/public/OHLC', {'pair': altname, 'interval': 1})
    ohlc_key = next(k for k in ohlc_result if k != 'last')
    raw = ohlc_result[ohlc_key]
    closed = raw[:-1] if len(raw) > 1 else raw
    closed = closed[-180:]
    one = _aggregate_ohlc(closed, 1)
    five = _aggregate_ohlc(closed, 5)
    fifteen = _aggregate_ohlc(closed, 15)
    sixty = _aggregate_ohlc(closed, 60)

    ticker_result = kraken_public('/0/public/Ticker', {'pair': altname})
    ticker = next(iter(ticker_result.values()))
    last = float(ticker['c'][0])
    high24 = float(ticker['h'][1] if len(ticker['h']) > 1 else ticker['h'][0])
    low24 = float(ticker['l'][1] if len(ticker['l']) > 1 else ticker['l'][0])
    volume24 = float(ticker['v'][1] if len(ticker['v']) > 1 else ticker['v'][0])
    vwap24 = float(ticker['p'][1] if len(ticker['p']) > 1 else ticker['p'][0])

    recent15 = one[-15:] if len(one) >= 15 else one
    recent60 = one[-60:] if len(one) >= 60 else one
    prior15 = one[-16:-1] if len(one) >= 16 else one[:-1]
    current = one[-1] if one else None
    prior20 = one[-25:-5] if len(one) >= 25 else []
    recent5 = one[-5:] if len(one) >= 5 else one
    base_vol = (sum(x['volume'] for x in prior20) / len(prior20)) if prior20 else None
    vol_accel = ((sum(x['volume'] for x in recent5) / max(1, len(recent5))) / base_vol
                 if base_vol and base_vol > 0 else None)

    prior_res = max((x['high'] for x in prior15), default=None)
    prior_sup = min((x['low'] for x in prior15), default=None)
    five_closed = five[-3:]
    higher_low = len(five_closed) >= 2 and five_closed[-1]['low'] > five_closed[-2]['low']
    lower_high = len(five_closed) >= 2 and five_closed[-1]['high'] < five_closed[-2]['high']

    return {
        'symbol': symbol, 'altname': altname, 'source': 'kraken_public_rest',
        'retrieved_at': utc(),
        'ticker': {
            'last': last, 'bid': float(ticker['b'][0]), 'ask': float(ticker['a'][0]),
            'high24': high24, 'low24': low24, 'volume24_base': volume24,
            'vwap24': vwap24, 'turnover24_est_eur': volume24 * vwap24,
            'pct_below_24h_high': ((high24 - last) / last * 100) if last else None,
            'pct_above_24h_low': ((last - low24) / last * 100) if last else None,
        },
        'levels': {
            'support_15m': min((x['low'] for x in recent15), default=None),
            'resistance_15m': max((x['high'] for x in recent15), default=None),
            'support_60m': min((x['low'] for x in recent60), default=None),
            'resistance_60m': max((x['high'] for x in recent60), default=None),
            'prior_15m_support': prior_sup, 'prior_15m_resistance': prior_res,
            'crossed_above_prior_15m_resistance': bool(current and prior_res is not None and current['close'] > prior_res),
            'crossed_below_prior_15m_support': bool(current and prior_sup is not None and current['close'] < prior_sup),
            'higher_low_5m': higher_low, 'lower_high_5m': lower_high,
        },
        'volume_acceleration_5m_vs_prior20m': vol_accel,
        'candles': {'1m': one[-20:], '5m': five[-12:], '15m': fifteen[-8:], '60m': sixty[-4:]},
    }


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


def flow_metrics(trades, now_ns, seconds):
    cutoff = now_ns - int(seconds * 1e9)
    buy = sell = 0.0
    count = 0
    for t in trades:
        if t['monotonic_ns'] < cutoff:
            continue
        n = float(t['price']) * float(t['qty'])
        if t.get('side') == 'buy':
            buy += n
        elif t.get('side') == 'sell':
            sell += n
        count += 1
    total = buy + sell
    return {'buy_eur': buy, 'sell_eur': sell, 'count': count,
            'pressure': ((buy - sell) / total) if total else None}


def wall_map(metrics):
    out = {}
    for side, key in (('bid', 'prominent_bids'), ('ask', 'prominent_asks')):
        for row in metrics[key]:
            out[(side, row['price'])] = row
    return out


def wall_transitions(previous, current, mid, removed_memory, now_ns):
    events = []
    prev = wall_map(previous) if previous else {}
    cur = wall_map(current)
    for key, old in prev.items():
        if key in cur:
            new = cur[key]
            old_q, new_q = float(old['qty']), float(new['qty'])
            if old_q and new_q / old_q >= 1.25:
                events.append({'event': 'build', 'side': key[0], 'price': key[1], 'qty_ratio': new_q / old_q})
            elif new_q and old_q / new_q >= 1.25:
                events.append({'event': 'decay', 'side': key[0], 'price': key[1], 'qty_ratio': new_q / old_q})
            continue
        side, price = key
        p = float(price)
        candidates = [(k, v) for k, v in cur.items() if k[0] == side and k not in prev]
        nearest = min(candidates, key=lambda kv: abs(float(kv[0][1]) - p), default=None)
        if nearest and abs(float(nearest[0][1]) - p) / float(mid) <= 0.005:
            events.append({'event': 'move', 'side': side, 'from_price': price, 'to_price': nearest[0][1]})
        else:
            events.append({'event': 'remove', 'side': side, 'price': price})
            removed_memory[key] = now_ns
            if (side == 'ask' and float(mid) > p) or (side == 'bid' and float(mid) < p):
                events.append({'event': 'liquidity_removed_breakout', 'side': side, 'price': price})
    for key, new in cur.items():
        if key in prev:
            continue
        if key in removed_memory and now_ns - removed_memory[key] <= int(120e9):
            events.append({'event': 'refill', 'side': key[0], 'price': key[1],
                           'seconds_since_remove': (now_ns - removed_memory[key]) / 1e9})
    return events


async def capture(seconds, out, smoke=False):
    from websockets.asyncio.client import connect
    journal = Journal(out)
    static_watch = load_watchlist()
    focus = set(static_watch)
    symbols = {**static_watch, 'BTC/EUR': 'XBTEUR'}
    journal.write('capture_start', purpose='PUBLIC_MARKET_TELEMETRY_ONLY',
                  historical_backfill=False, smoke=smoke, static_watchlist=sorted(focus))
    seen_runs = set()
    stop_at = time.monotonic() + seconds
    books, last_ids = {}, {}
    trades = defaultdict(lambda: deque(maxlen=20000))
    price_history = defaultdict(lambda: deque(maxlen=500))
    contexts = {}
    last_micro = defaultdict(float)
    last_context = defaultdict(float)
    previous_metrics = {}
    removed_memory = {}
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
                                symbol = row['symbol']
                                book = books.setdefault(symbol, Book())
                                book.apply(row, message['type'] == 'snapshot')
                                journal.write('book_verified', connection=connection,
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
                                                               removed_memory, now_ns)
                                    previous_metrics[symbol] = metrics
                                    pressure = flow60['pressure']
                                    imbalance = metrics['imbalance_top10']
                                    bias = 'mixed'
                                    if pressure is not None and imbalance is not None and ret60 is not None:
                                        if pressure > 0 and imbalance > 0 and ret60 >= 0:
                                            bias = 'supportive'
                                        elif pressure < 0 and imbalance < 0 and ret60 <= 0:
                                            bias = 'opposed'
                                    quality = 'complete'
                                    if last_gap_ns and now_ns - last_gap_ns < int(60e9):
                                        quality = 'Marktdaten unvollständig'
                                    snapshot = {
                                        'symbol': symbol, 'exchange_at': row.get('timestamp'),
                                        'quality': quality, 'book': metrics,
                                        'flow': {'15s': flow15, '60s': flow60, '300s': flow300},
                                        'mid_return_60s_pct': ret60,
                                        'wall_events': changes,
                                        'absorption_candidate': (
                                            'buy_absorption' if pressure is not None and pressure > 0 and ret60 is not None and ret60 <= 0
                                            else 'sell_absorption' if pressure is not None and pressure < 0 and ret60 is not None and ret60 >= 0
                                            else None),
                                        'microstructure_bias': bias,
                                        'context_age_seconds': (
                                            max(0.0, time.time() - datetime.fromisoformat(contexts[symbol]['retrieved_at']).timestamp())
                                            if symbol in contexts else None),
                                        'context_levels': contexts.get(symbol, {}).get('levels'),
                                        'ticker24': contexts.get(symbol, {}).get('ticker'),
                                    }
                                    journal.write('micro_snapshot', **snapshot)
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
                                    trades[symbol].append({
                                        'monotonic_ns': time.monotonic_ns(),
                                        'exchange_at': row.get('timestamp'), 'trade_id': tid,
                                        'side': row.get('side'), 'price': str(row.get('price')),
                                        'qty': str(row.get('qty')),
                                    })
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
