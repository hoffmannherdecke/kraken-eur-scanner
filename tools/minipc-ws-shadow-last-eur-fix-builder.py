#!/usr/bin/env python3
"""Prepare the narrow WS price guard while retaining the installed crash footer."""
import argparse
import hashlib
from pathlib import Path

HUNKS = [
 ("import json\nimport time\n", "import json\nimport math\nimport time\n"),
 ('    if last is None or last <= 0:\n',
  '    if last is None or not math.isfinite(last) or last <= 0:\n'),
 ('    stale_pairs = 0\n    changed_pairs = 0\n    triggered_pairs = 0\n',
  '    stale_pairs = 0\n    changed_pairs = 0\n    invalid_price_pairs = 0\n    triggered_pairs = 0\n'),
 ('        changed_pairs += 1\n\n        market = normalize_market(raw)\n        current_price = float(market["last_eur"])\n',
  '        # Kraken WS ticker may legitimately arrive before a last-trade price.\n'
  "        # Never substitute bid/ask/VWAP as a trade price or consume this pair's\\n"
  '        # timestamp. A later valid update must still be processed normally.\n'
  '        try:\n'
  '            market = normalize_market(raw)\n'
  '        except ValueError as exc:\n'
  '            if str(exc) != "missing positive last_eur":\n'
  '                raise\n'
  '            invalid_price_pairs += 1\n'
  '            continue\n'
  '        changed_pairs += 1\n'
  '        current_price = float(market["last_eur"])\n'),
 ('        "triggered_pairs": triggered_pairs,\n',
  '        "invalid_price_pairs": invalid_price_pairs,\n'
  '        "triggered_pairs": triggered_pairs,\n'),
]
FOOTER = 'if __name__ == "__main__":\n    try:\n        raise SystemExit(main())\n    except BaseException as _ws_error:'
LOG_LINE = 'v2r4-ws-shadow-python-crash.log'

def patch(original: bytes) -> bytes:
    text = original.decode("utf-8-sig")
    crlf = "\r\n" in text
    text = text.replace("\r\n", "\n")
    if text.count(FOOTER) != 1 or text.count(LOG_LINE) != 1:
        raise ValueError("PR297 diagnostic exception footer missing or changed")
    footer = text[text.index(FOOTER):]
    for before, after in HUNKS:
        if text.count(before) != 1:
            raise ValueError("unrecognized pinned source or already patched")
        text = text.replace(before, after)
    if text[text.index(FOOTER):] != footer:
        raise ValueError("original diagnostic footer was changed")
    return text.replace("\n", "\r\n").encode("utf-8") if crlf else text.encode("utf-8")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--original-sha256", required=True)
    a = p.parse_args()
    original = a.source.read_bytes()
    if hashlib.sha256(original).hexdigest().lower() != a.original_sha256.lower():
        raise SystemExit("BLOCKED: installed watcher SHA mismatch")
    if a.output.exists() or a.output.resolve() == a.source.resolve():
        raise SystemExit("BLOCKED: cannot overwrite staged output or production source")
    result = patch(original)
    a.output.write_bytes(result)
    print("WS_SHADOW_LAST_EUR_FIX_PREPARED")
    print("NewSHA256=" + hashlib.sha256(result).hexdigest().upper())

if __name__ == "__main__":
    main()
