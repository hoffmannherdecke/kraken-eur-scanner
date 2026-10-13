"""Optional cross-process budget for MINI-PC public Kraken Spot REST requests.

No new scheduler, daemon or credentials. One OS-locked state file shared by all
explicitly enrolled clients on the SAME host. Does NOT cover GitHub runners,
other hosts, Kraken private REST, or WebSocket. OFF unless the absolute
KRAKEN_PUBLIC_BUDGET_DIR is explicitly configured for each enrolled owner.

Requests never fall back to stale market data on budget denial.
"""
from __future__ import annotations

import errno
import hashlib
import json
import os
import time
from pathlib import Path
from urllib.parse import urlsplit, parse_qs


class KrakenPublicBudgetDeferred(RuntimeError):
    """Public REST request was NOT sent because the shared budget had no slot."""


class KrakenPublicBudgetUnsafe(RuntimeError):
    """A corrupt, missing, or inaccessible enrolled budget fails closed."""


MIN_INTERVAL_SECONDS = 1.25
RATE_LIMIT_COOLDOWN_SECONDS = 20.0
_MUTEX_NAME = "budget.lock"
_STATE_NAME = "budget-state.json"


def configured_root() -> Path | None:
    raw = os.environ.get("KRAKEN_PUBLIC_BUDGET_DIR", "")
    if not raw:
        return None
    root = Path(raw)
    if not root.is_absolute():
        raise KrakenPublicBudgetUnsafe("Kraken public budget path must be absolute")
    return root


def _scope(url: str) -> str:
    p = urlsplit(url)
    if p.scheme != "https" or p.hostname != "api.kraken.com" or not p.path.startswith("/0/public/"):
        raise KrakenPublicBudgetUnsafe("Kraken public budget called for a nonpublic URL")
    # Kraken Spot: OHLC and Trades use a per-IP/per-pair limit; all other
    # public REST endpoints share one IP limit. Avoid over-serializing
    # unrelated OHLC pairs or starving time-critical ticker lookups.
    endpoint = p.path.rsplit("/", 1)[-1]
    if endpoint in ("OHLC", "Trades"):
        pair = parse_qs(p.query).get("pair", [""])[0].strip().upper()
        if not pair or len(pair) > 128:
            raise KrakenPublicBudgetUnsafe("pair required for Kraken OHLC/Trades budget")
        digest = hashlib.sha256(pair.encode("utf-8")).hexdigest()[:24]
        return "PAIR:" + digest
    return "IP"


def _try_lock(handle) -> bool:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError as exc:
            if exc.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK, 13, 36):
                return False
            raise
    import fcntl
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except BlockingIOError:
        return False


def _unlock(handle) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _lock_file(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    handle = open(root / _MUTEX_NAME, "a+b")
    # msvcrt byte-range locking needs a real byte; race-safe since every writer
    # uses the same constant byte and seeks to offset zero.
    if handle.seek(0, os.SEEK_END) == 0:
        handle.write(b"0")
        handle.flush()
    handle.seek(0)
    return handle


def _state(root: Path) -> dict:
    path = root / _STATE_NAME
    if not path.exists():
        return {"schema_version": 1, "last_claim_at": {}, "cooldown_until": {}}
    try:
        data = json.loads(path.read_text("utf-8"))
        if (not isinstance(data, dict) or data.get("schema_version") != 1 or
            any(not isinstance(data.get(k), dict) for k in ("last_claim_at", "cooldown_until")) or
            any(not isinstance(v, (int, float)) or v < 0 or v > time.time() + 3600
                for k in ("last_claim_at", "cooldown_until")
                for v in data[k].values())):
            raise ValueError("invalid counters")
        return data
    except (OSError, ValueError, TypeError) as exc:
        raise KrakenPublicBudgetUnsafe("Kraken public budget state invalid") from exc


def _save(root: Path, data: dict) -> None:
    # Keep bounded state and avoid per-request log growth. Old pair-scoped
    # entries can be removed after they can no longer influence rate safety.
    now = time.time()
    for key in ("last_claim_at", "cooldown_until"):
        data[key] = {k: v for k, v in data[key].items()
                     if v >= now - 3600 or k == "IP"}
        if len(data[key]) > 4096:
            raise KrakenPublicBudgetUnsafe("Kraken public budget too many active pair scopes")
    # A process-unique temp name prevents a failed writer from clobbering
    # another process's file. Exclusive byte lock remains held during replace.
    path = root / _STATE_NAME
    tmp = root / f".{_STATE_NAME}.{os.getpid()}.tmp"
    try:
        tmp.write_text(json.dumps(data, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def reserve_public_request(url: str, *, max_wait_seconds: float = 0.0) -> bool:
    """Reserve one public Kraken REST request; False means feature is OFF.

    Must be called immediately BEFORE the HTTP request. A reservation is
    conservatively consumed even if the subsequent network request fails.
    On contention/budget exhaustion, raise a bounded fail-closed exception.
    """
    root = configured_root()
    if root is None:
        return False
    bucket = _scope(url)
    if not 0 <= max_wait_seconds <= 3:
        raise ValueError("max_wait_seconds must be between 0 and 3")
    end = time.monotonic() + max_wait_seconds
    try:
        with _lock_file(root) as handle:
            while True:
                if not _try_lock(handle):
                    if time.monotonic() >= end:
                        raise KrakenPublicBudgetDeferred("Kraken public rate limit budget lock busy")
                    time.sleep(min(0.05, max(0, end - time.monotonic())))
                    continue
                try:
                    state = _state(root)
                    now = time.time()
                    # No claim if wall clock moves backwards; never use a
                    # fabricated counter reset to bypass the rate gate.
                    next_time = max(
                        state["last_claim_at"].get(bucket, 0.0) + MIN_INTERVAL_SECONDS,
                        state["cooldown_until"].get(bucket, 0.0),
                    )
                    if now >= next_time:
                        state["last_claim_at"][bucket] = now
                        _save(root, state)
                        return True
                    delay = next_time - now
                finally:
                    _unlock(handle)
                if delay > max(0.0, end - time.monotonic()):
                    raise KrakenPublicBudgetDeferred("Kraken public rate limit budget deferred")
                time.sleep(min(delay, 0.05))
    except (OSError, PermissionError) as exc:
        raise KrakenPublicBudgetUnsafe("Kraken public budget filesystem inaccessible") from exc


def report_public_rate_limit(url: str, payload: dict | None = None, *, http_status: int | None = None) -> bool:
    """Register real Kraken HTTP 429 or EGeneral/Rate limit errors.

    Does not perform a request. No effect on valid responses or when OFF.
    """
    root = configured_root()
    if root is None:
        return False
    bucket = _scope(url)
    errors = payload.get("error", []) if isinstance(payload, dict) else []
    error_text = " ".join(map(str, errors)).lower()
    limited = http_status == 429 or any(
        token in error_text for token in ("too many requests", "rate limit", "throttl")
    )
    if not limited:
        return False
    try:
        with _lock_file(root) as handle:
            # Bounded lock time; failure means the limiter is not reliably
            # updated, and source callers must still fail closed.
            end = time.monotonic() + 0.5
            while not _try_lock(handle):
                if time.monotonic() >= end:
                    raise KrakenPublicBudgetUnsafe("Kraken public rate limit update lock busy")
                time.sleep(0.025)
            try:
                state = _state(root)
                state["cooldown_until"][bucket] = max(
                    state["cooldown_until"].get(bucket, 0.0),
                    time.time() + RATE_LIMIT_COOLDOWN_SECONDS
                )
                _save(root, state)
            finally:
                _unlock(handle)
    except OSError as exc:
        raise KrakenPublicBudgetUnsafe("Kraken public rate limit cooldown not persisted") from exc
    return True
