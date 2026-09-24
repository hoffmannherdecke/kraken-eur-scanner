"""Technical replay of explicitly supplied barriers; never derives strategy rules.

Inputs must already be in one unambiguous, complete, time-ordered observation
window. Raw websocket channels do not provide a shared exchange sequence.
The caller must prove coverage and reject ties/cross-channel ambiguity first.
Non-price invalidation/revalidation is supplied as a persisted decision event.
"""
from decimal import Decimal as D

FEE = D('0.006')


def replay(plan, tape, coverage_verified=False):
    if not coverage_verified:
        raise ValueError('coverage not independently verified: unauswertbar')
    if plan['decision_at'] > plan['persisted_at'] or plan['valid_from'] < plan['persisted_at']:
        raise ValueError('retroactive activation')
    if plan['expires_at'] <= plan['valid_from']:
        raise ValueError('invalid TTL')
    if len(plan['entries']) not in (1, 2):
        raise ValueError('one or two explicitly planned entries required')
    events, fills, following = [], [], []
    used, position = set(), D(0)
    active, stopped = True, False
    last_time = None
    expiry = plan['expires_at']
    for tick in tape:
        now = tick['at']
        if last_time is not None and now <= last_time:
            raise ValueError('ambiguous or unordered events')
        last_time = now
        if tick['kind'] == 'gap':
            raise ValueError('data gap: unauswertbar')
        if now < plan['valid_from']:
            continue
        if active and now >= expiry:
            events.append(dict(at=expiry, kind='TTL'))
            active = False
        if tick['kind'] == 'revalidate':
            if tick['persisted_at'] > now or tick['expires_at'] <= now or stopped:
                raise ValueError('invalid revalidation')
            expiry, active = tick['expires_at'], True
            events.append(dict(at=now, kind='revalidate', reason=tick['reason']))
            continue
        if tick['kind'] == 'invalidate':
            if tick['persisted_at'] > now:
                raise ValueError('unpersisted invalidation')
            active = False
            events.append(dict(at=now, kind='invalidate', reason=tick['reason']))
            continue
        if tick['kind'] != 'trade':
            continue
        price = D(str(tick['price']))
        following.append(dict(at=now, price=str(price)))
        if position and price <= D(str(plan['stop'])):
            f = tick['book'].execution('sell', position, plan['slippage_bps'])
            f.update(at=now, side='sell', kind='stop', fee=str(D(f['notional'])*FEE))
            fills.append(f)
            events.append(dict(at=now, kind='stop'))
            position, active, stopped = D(0), False, True
        elif active:
            triggered = [(i, e) for i, e in enumerate(plan['entries'])
                         if i not in used and price >= D(str(e['trigger']))]
            # Same-tick multi-stage execution consumes shared depth. Until that
            # matching model exists, reject instead of reusing liquidity twice.
            if len(triggered) > 1:
                raise ValueError('simultaneous stages require shared-depth model')
            for i, entry in triggered:
                try:
                    f = tick['book'].execution('buy', entry['quantity'], plan['slippage_bps'], entry.get('limit'))
                except ValueError:
                    raise ValueError('fill_unknown; no inferred resting-limit fill')
                f.update(at=now, side='buy', kind=f'entry_{i+1}', fee=str(D(f['notional'])*FEE))
                fills.append(f)
                events.append(dict(at=now, kind=f'entry_{i+1}'))
                used.add(i)
                position += D(str(entry['quantity']))
    if not tape or last_time < plan['follow_until']:
        raise ValueError('follow-up incomplete')
    if position:
        net = None
    else:
        net = str(sum((D(f['notional']) if f['side']=='sell' else -D(f['notional']))
                      - D(f['fee']) for f in fills))
    return dict(events=events, fills=fills, follow_path=following,
                net_eur=net, fee_rate=str(FEE), open_quantity=str(position),
                status='controlled_model_replay_not_real_execution')
