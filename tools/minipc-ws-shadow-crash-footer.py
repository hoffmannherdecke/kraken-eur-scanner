#!/usr/bin/env python3
"""Build a strictly diagnostic footer for the PINNED original V2R4 WS watcher.

Do not alter the paper strategy or the original state and task action.
Only unexpected Python failures are recorded in a bounded LOCAL Logs file.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

OLD_MAIN = 'if __name__ == "__main__":\n    raise SystemExit(main())\n'

NEW_MAIN = '''if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BaseException as _ws_error:
        # Preserve all original exit codes. A normal SystemExit(0) is not a crash.
        if isinstance(_ws_error, SystemExit) and _ws_error.code in (0, None):
            raise
        try:
            import sys as _ws_sys
            import traceback as _ws_traceback
            from datetime import datetime as _ws_datetime, timezone as _ws_timezone

            _ws_argv = _ws_sys.argv
            _ws_hb_arg = _ws_argv.index("--heartbeat")
            _ws_hb_path = Path(_ws_argv[_ws_hb_arg + 1]).resolve()
            # Task's existing --heartbeat is within Trading/State; this is
            # the ORIGINAL local Trading/Logs directory, not a second state owner.
            _ws_log_dir = _ws_hb_path.parent.parent / "Logs"
            _ws_log_dir.mkdir(parents=True, exist_ok=True)
            _ws_log = _ws_log_dir / "v2r4-ws-shadow-python-crash.log"

            _ws_when = _ws_datetime.now(_ws_timezone.utc).isoformat()
            _ws_trace = "".join(
                _ws_traceback.format_exception(
                    type(_ws_error), _ws_error, _ws_error.__traceback__
                )
            )
            _ws_record = (
                ("\\\\n=== WS-SHADOW PYTHON EXIT " + _ws_when + " ===\\\\n")
                + _ws_trace[-16000:] + "\\\\n"
            ).encode("utf-8", errors="replace")

            # Keep the newest 48 KiB only; crash logging must not grow forever.
            _ws_prior = _ws_log.read_bytes()[-(48 * 1024 - len(_ws_record)):] \\
                if _ws_log.exists() else b""
            _ws_tmp = _ws_log.with_suffix(".crash.tmp")
            _ws_tmp.write_bytes((_ws_prior + _ws_record)[-(48 * 1024):])
            _ws_tmp.replace(_ws_log)
        except Exception:
            # A logging error must NEVER replace the original Python traceback.
            pass
        raise
'''


def instrument(source: bytes) -> bytes:
    raw = source.decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in raw else "\n"
    canonical = raw.replace("\r\n", "\n")
    if canonical.count(OLD_MAIN) != 1:
        raise ValueError("pinned watcher footer is absent or already changed")
    modified = canonical.replace(OLD_MAIN, NEW_MAIN)
    return modified.replace("\n", newline).encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--original-sha256", required=True)
    args = parser.parse_args()
    source = args.source.read_bytes()
    digest = hashlib.sha256(source).hexdigest()
    if digest.casefold() != args.original_sha256.casefold():
        raise SystemExit("BLOCKED: pinned source SHA256 changed")
    result = instrument(source)
    if result == source:
        raise SystemExit("BLOCKED: no actual diagnostic change")
    if args.source.resolve() == args.output.resolve():
        raise SystemExit("BLOCKED: original source cannot be overwritten by patch builder")
    if args.output.exists():
        raise SystemExit("BLOCKED: output path already exists")
    args.output.write_bytes(result)
    print("WS_SHADOW_BOUNDED_EXCEPTION_FOOTER_PREPARED")
    print("NewSHA256=" + hashlib.sha256(result).hexdigest().upper())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
