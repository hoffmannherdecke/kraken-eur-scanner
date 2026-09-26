"""Runtime safety gates for the shared public market data layer.

The market data collector is read-only. This explicit false constant records
that no live evaluation adapter is wired or permitted by this repository.
Changing it is not sufficient to enable trading: no order API exists here.
"""

LIVE_EVALUATION_ENABLED = False
REAL_MONEY_ACTIONS_ENABLED = False


def require_live_evaluation_disabled():
    if LIVE_EVALUATION_ENABLED:
        raise RuntimeError("live evaluation must remain disabled in this release")


def require_real_money_actions_disabled():
    if REAL_MONEY_ACTIONS_ENABLED:
        raise RuntimeError("real-money actions must remain disabled in this release")
