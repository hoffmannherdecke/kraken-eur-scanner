"""Read the existing Mini-PC scanner originals for the signed V3 Paper task."""

from datetime import datetime, timezone
import hashlib
import math
from pathlib import Path
import re
from urllib.parse import urlencode

from market_data.universe import online_eur_universe
from paper_evaluator.evaluate import http_json, kraken_ticker
from paper_evaluator.successor_coin_entry_evidence_v1 import fetch_public_entry_evidence
from paper_evaluator.v3_p3_ab_five_bounded_research import verified_spot_metadata
from paper_evaluator.v3_paper_positive_source_entry_v1 import STREAMS, utc
from paper_evaluator.v3_paper_single_writer_preflight_v1 import plan_writer_preflight


def original_candidate(event: dict, *, observed: datetime, series_started: datetime) -> dict | None:
    """Preserve the original scanner clock and the existing canonical handoff ID."""
    # Legacy liquidity/recheck labels belong to the source evidence.
    # The released V3 preflight alone determines review eligibility.
    pair = event.get("pair")
    if (event.get("kind") != "V2R4_WS_SHADOW_DISCOVERY"
            or type(event.get("schema_version")) is not int or event["schema_version"] != 1
            or event.get("shadow_only") is not True
            or event.get("paper_only") is not True
            or event.get("real_money_actions_enabled") is not False
            or event.get("fresh_recheck_invoked") is not False
            or event.get("next_action") != "SHADOW_OBSERVE_ONLY"
            or not isinstance(pair, str) or re.fullmatch(r"[A-Z0-9]{2,20}/EUR", pair) is None):
        return None
    try:
        event_at = utc(event["observed_at_utc"])
        received = utc(event["source_pair_received_at_utc"])
        snapshot = utc(event["source_snapshot_written_at_utc"])
        price = event["last_eur"]
        if (not received <= snapshot <= event_at or event_at < series_started
                or not 0 <= (observed - event_at).total_seconds() <= 600
                or type(price) not in (int, float) or not math.isfinite(price) or price <= 0
                or not isinstance(event.get("returns"), dict)
                or not isinstance(event.get("reasons"), list)):
            return None
    except (KeyError, ValueError, TypeError, OverflowError, AttributeError):
        return None

    material = "|".join(str(event[key]) for key in (
        "pair", "observed_at_utc", "source_pair_received_at_utc", "last_eur"))
    event_id = hashlib.sha256(material.encode()).hexdigest()[:24]
    run_id = int(hashlib.sha256(event_id.encode()).hexdigest()[:12], 16)
    tag = pair.replace("/", "-")
    stamp = int(event_at.timestamp())
    return {
        "kind": "CANONICAL_CANDIDATE_HANDOFF_V1", "schema_version": 1,
        "entry_origin": "SCANNER", "action": "REVIEW_ONLY_NOT_ORDER", "pair": pair,
        "candidate_id": f"{event_at:%Y%m%d-%H%M%S}-{tag}-r{run_id}",
        "queue_id": f"{run_id}:{tag}:{stamp}", "source_scanner_run_id": run_id,
        "event_time_utc": event_at.isoformat().replace("+00:00", "Z"), "event_ts": stamp,
        "scanner_candidate": {"pair": pair, "price": price, "reasons": event["reasons"],
                              **{k: event["returns"].get(k) for k in (
                                  "ret10m", "ret30m", "ret1h", "ret3h", "ret6h", "ret12h",
                                  "ret_day_open")}},
        "scanner_market_context": {
            "source": "MINIPC_V2R4_WS_SHADOW_DISCOVERY", "source_event_id": event_id,
            "sensor_price_eur": price, "spread_pct": event.get("spread_pct"),
            "turnover24h_eur": event.get("turnover24h_eur"), "source_event": event,
        },
    }


def prepare_next_scanner_input(*, source: Path, series_id: str, series_started: datetime,
                               seen: set[str], attempted: set[str], clock, read_json):
    """At most one new canonical original and one public-only PIT acquisition per cycle."""
    if (not source.is_dir() or any(p.is_symlink() or getattr(p, "is_junction", lambda: False)()
                                  for p in (source, *source.parents))):
        raise ValueError("original Scanner event directory missing or linked")
    observed = clock()
    fresh = []
    for path in source.glob("*.json"):
        # Original filename orders the events and bounds JSON reads on every cycle.
        if not re.fullmatch(r"\d{8}T\d{6}\.\d{6}Z-[A-Z0-9]+-EUR\.json", path.name):
            continue
        try:
            written = datetime.strptime(path.name.split("-", 1)[0], "%Y%m%dT%H%M%S.%fZ")
        except ValueError:
            continue
        if 0 <= (observed - written.replace(tzinfo=timezone.utc)).total_seconds() <= 600:
            fresh.append(path)
    for path in sorted(fresh)[:100]:
        try:
            event = read_json(path)
        except (OSError, ValueError):
            continue
        candidate = original_candidate(event, observed=observed, series_started=series_started)
        if candidate is None or candidate["candidate_id"] in (seen | attempted):
            continue
        attempted.add(candidate["candidate_id"])
        pair = candidate["pair"]
        clock()
        asset_pairs = http_json("https://api.kraken.com/0/public/AssetPairs", timeout=9)
        if asset_pairs.get("error") or not isinstance(asset_pairs.get("result"), dict):
            return None
        matches = [row for row in online_eur_universe(asset_pairs["result"]) if row["symbol"] == pair]
        if len(matches) != 1:
            return None
        alt = matches[0]["altname"]
        if not re.fullmatch(r"[A-Za-z0-9]{2,24}", alt):
            raise ValueError("invalid original Kraken alias")
        candidate["altname"] = alt
        candidate["scanner_candidate"]["altname"] = alt
        def load_ohlc(symbol, interval):
            return http_json("https://api.kraken.com/0/public/OHLC?" + urlencode({
                "pair": symbol, "interval": interval}), timeout=9)

        evidence = fetch_public_entry_evidence(alt, pair, clock=clock, loader=load_ohlc)
        clock()
        ticker = dict(kraken_ticker(alt), pair=pair, observed_at_utc=clock().isoformat())
        metadata = dict(verified_spot_metadata(alt, pair, ticker), altname=alt)
        snapshot = {"entry_evidence": evidence, "ticker": ticker, "pair_metadata": metadata}
        preflight = plan_writer_preflight(
            scanner_events=[candidate], owner_event_packets=[], h10_context=None,
            h11_market_capture=None, h5_macro_calendar=None,
            authenticated_owner_ids={name: [] for name in STREAMS}, journal_receipts=[],
            known_pairs={pair: metadata}, market_observations={pair: snapshot},
            series_id=series_id, decision_at_utc=clock().isoformat(), max_reviews=1)
        reviews = preflight["review_preflights"]
        if (len(reviews) == 1 and reviews[0]["eligible_for_full_model_review"]
                and preflight["selected_candidates"] == [candidate]):
            return candidate, preflight
        return None
    return None
