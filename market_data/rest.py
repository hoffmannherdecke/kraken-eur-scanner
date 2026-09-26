"""Shared public Kraken REST market context; never submits exchange actions."""
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone


def utc():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


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
