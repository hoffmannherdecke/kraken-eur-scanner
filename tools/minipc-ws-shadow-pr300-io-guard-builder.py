#!/usr/bin/env python3
"""Exact-source PR300 Windows-I/O guard builder for original pinned WSShadow.

Offline only: output new source file, never overwrites original.
Maintains byte-identical PR297 exception capture and PR299 last-EUR guard.
"""
import argparse
import hashlib
from pathlib import Path

HUNKS = (
    (
        '''def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\\n", "utf-8")
    tmp.replace(path)


''',
        '''# Windows may briefly refuse a read or atomic replacement while another
# process has a file handle open. Retry ONLY PermissionError, for at most
# 0.5 seconds. Persistent ACL failures still propagate to the crash logger.
WINDOWS_ACCESS_RETRY_DELAYS = (0.04, 0.08, 0.14, 0.24)


def retry_windows_file_access(operation):
    for delay in (*WINDOWS_ACCESS_RETRY_DELAYS, None):
        try:
            return operation()
        except PermissionError:
            if delay is None:
                raise
            time.sleep(delay)


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\\n"
    retry_windows_file_access(lambda: tmp.write_text(serialized, "utf-8"))
    retry_windows_file_access(lambda: tmp.replace(path))


''',
    ),
    (
        '''def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text("utf-8"))
''',
        '''def load_json(path: Path) -> dict[str, Any]:
    # Keep parse errors visible; only brief OS-level access denial is retried.
    return json.loads(retry_windows_file_access(lambda: path.read_text("utf-8")))
''',
    ),
    (
        '''    try:
        state = load_json(path)
    except Exception:
        return load_state(Path("__missing__"))
''',
        '''    try:
        state = load_json(path)
    except OSError:
        # A protected/locked state file must NEVER be treated as a fresh state.
        raise
    except (ValueError, UnicodeError):
        return load_state(Path("__missing__"))
''',
    ),
)
FOOTER = 'if __name__ == "__main__":\n    try:\n        raise SystemExit(main())\n    except BaseException as _ws_error:'
DIAG = 'v2r4-ws-shadow-python-crash.log'
PR299 = 'invalid_price_pairs'


def patch(original: bytes) -> bytes:
    decoded = original.decode("utf-8-sig")
    crlf = "\r\n" in decoded
    text = decoded.replace("\r\n", "\n")
    if text.count(FOOTER) != 1 or text.count(DIAG) != 1:
        raise ValueError("PR297 diagnostic footer mismatch")
    if text.count(PR299) < 2:
        raise ValueError("PR299 invalid-price guard missing")
    footer_before = text[text.index(FOOTER):]
    for before, after in HUNKS:
        if text.count(before) != 1:
            raise ValueError("Expected exact pre-PR300 original source hunk missing or duplicated")
        text = text.replace(before, after)
    if text[text.index(FOOTER):] != footer_before:
        raise ValueError("PR297 diagnostic footer changed")
    return text.replace("\n", "\r\n").encode("utf-8") if crlf else text.encode("utf-8")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--original-sha256", required=True)
    args = p.parse_args()
    old = args.source.read_bytes()
    if hashlib.sha256(old).hexdigest().casefold() != args.original_sha256.casefold():
        raise SystemExit("BLOCKED: live source sha mismatch")
    if args.output.exists() or args.source.resolve() == args.output.resolve():
        raise SystemExit("BLOCKED: output exists or same as original")
    new = patch(old)
    args.output.write_bytes(new)
    print("WS_SHADOW_PR300_IO_GUARD_PREPARED")
    print("NewSHA256=" + hashlib.sha256(new).hexdigest().upper())


if __name__ == "__main__":
    main()
