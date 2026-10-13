"""Optional cross-process budget for MINI-PC public Kraken Spot REST requests.

No new scheduler, daemon or credentials. One OS-locked state file shared by all
explicitly enrolled clients on the SAME host. Does NOT cover GitHub runners,
other hosts, Kraken private REST, or WebSocket. OFF unless the absolute
KRAKEN_PUBLIC_BUDGET_DIR is explicitly configured for each enrolled owner.

Requests never fall back to stale market data on budget denial.
"""
from __future__ import annotations

import errno
import json
import os
import time
from pathlib import Path
from urllib.parse import urlsplit


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


def _validate_public_url(url: str) -> None:
    p = urlsplit(url)
    if p.scheme != "https" or p.hostname != "api.kraken.com" or not p.path.startswith("/0/public/"):
        raise KrakenPublicBudgetUnsafe("Kraken public budget called for a nonpublic URL")


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


def _state(root: Path) -> dict[str, float]:
    path = root / _STATE_NAME
    if not path.exists():
        return {"last_claim_at": 0.0, "cooldown_until": 0.0}
    try:
        data = json.loads(path.read_text("utf-8"))
        if (not isinstance(data, dict) or
            not isinstance(data.get("last_claim_at"), (int, float)) or
            not isinstance(data.get("cooldown_until"), (int, float)) or
            data["last_claim_at"] < 0 or data["cooldown_until"] < 0):
            raise ValueError("invalid counters")
        return data
    except (OSError, ValueError, TypeError) as exc:
        raise KrakenPublicBudgetUnsafe("Kraken public budget state invalid") from exc


def _save(root: Path, data: dict[str, float]) -> None:
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
    _validate_public_url(url)
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
                        state["last_claim_at"] + MIN_INTERVAL_SECONDS,
                        state["cooldown_until"],
                    )
                    if now >= next_time:
                        state["last_claim_at"] = now
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


def report_public_rate_limit(payload: dict | None = None, *, http_status: int | None = None) -> bool:
    """Register real Kraken HTTP 429 or EGeneral/Rate limit errors.

    Does not perform a request. No effect on valid responses or when OFF.
    """
    root = configured_root()
    if root is None:
        return False
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
                state["cooldown_until"] = max(
                    state["cooldown_until"], time.time() + RATE_LIMIT_COOLDOWN_SECONDS
                )
                _save(root, state)
            finally:
                _unlock(handle)
    except OSError as exc:
        raise KrakenPublicBudgetUnsafe("Kraken public rate limit cooldown not persisted") from exc
    return True
