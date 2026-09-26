"""Mode-independent Kraken Spot book and microstructure calculations.

This module is deliberately read-only: it has no strategy, account, order,
Slack, or runtime-mode dependencies. Paper and any later live assessment must
import these same functions.
"""
from decimal import Decimal
from statistics import median
import zlib

BOOK_DEPTH = 25


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
            for p in sorted(levels, reverse=reverse)[BOOK_DEPTH:]:
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
        bid_top10, ask_top10 = bid_rows[:10], ask_rows[:10]
        bid_notional = sum(x['notional_eur'] for x in bid_top10)
        ask_notional = sum(x['notional_eur'] for x in ask_top10)
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



def derive_microstructure_bias(flow_60s, imbalance_top10, mid_return_60s_pct):
    """Existing observational label; no trade recommendation or threshold change."""
    bias = 'mixed'
    pressure = flow_60s['pressure']
    if pressure is not None and imbalance_top10 is not None and mid_return_60s_pct is not None:
        if pressure > 0 and imbalance_top10 > 0 and mid_return_60s_pct >= 0:
            bias = 'supportive'
        elif pressure < 0 and imbalance_top10 < 0 and mid_return_60s_pct <= 0:
            bias = 'opposed'
    absorption = (
        'buy_absorption' if pressure is not None and pressure > 0 and mid_return_60s_pct is not None and mid_return_60s_pct <= 0
        else 'sell_absorption' if pressure is not None and pressure < 0 and mid_return_60s_pct is not None and mid_return_60s_pct >= 0
        else None
    )
    return bias, absorption
