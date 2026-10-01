#!/usr/bin/env python3
"""Local immutable search-accounting ledger for historical strategy research.

The ledger is intentionally local/research-only. It does not mutate active
Paper/Shadow strategy state, does not call exchanges and does not place orders.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def payload_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def schema_required(schema: dict[str, Any]) -> set[str]:
    required = schema.get("required_fields")
    if not isinstance(required, list) or not all(isinstance(x, str) for x in required):
        raise ValueError("trial ledger schema required_fields invalid")
    return set(required)


def validate_record(record: dict[str, Any], schema: dict[str, Any]) -> None:
    missing = sorted(schema_required(schema) - set(record))
    if missing:
        raise ValueError(f"trial record missing required fields: {', '.join(missing)}")

    trial_id = record.get("trial_id")
    if not isinstance(trial_id, str) or len(trial_id) < 8:
        raise ValueError("trial_id must be a stable text id with length >=8")

    created = record.get("created_at_utc")
    if not isinstance(created, str) or not created.endswith("Z"):
        raise ValueError("created_at_utc must be UTC ISO-8601 ending in Z")
    datetime.fromisoformat(created.replace("Z", "+00:00"))

    checksum = record.get("dataset_sha256")
    if not isinstance(checksum, str) or len(checksum) != 64:
        raise ValueError("dataset_sha256 must be 64 hex chars")
    int(checksum, 16)

    for name in ("purge_seconds", "embargo_seconds"):
        value = record.get(name)
        if not isinstance(value, int) or value < 0:
            raise ValueError(f"{name} must be a nonnegative integer")

    for name in ("parameters", "metrics"):
        if not isinstance(record.get(name), dict):
            raise ValueError(f"{name} must be an object")

    if record.get("influenced_later_design") not in (True, False):
        raise ValueError("influenced_later_design must be boolean")

    fee = record.get("fee_model")
    if not isinstance(fee, dict):
        raise ValueError("fee_model must be an object")
    if float(fee.get("taker_pct_per_side", -1)) < 0:
        raise ValueError("fee_model.taker_pct_per_side missing/invalid")


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init_db(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        create table if not exists trials (
            trial_id text primary key,
            created_at_utc text not null,
            parent_hypothesis text not null,
            strategy_revision text not null,
            dataset_snapshot text not null,
            dataset_sha256 text not null,
            payload_sha256 text not null,
            influenced_later_design integer not null check (influenced_later_design in (0,1)),
            payload_json text not null,
            inserted_at_utc text not null
        );

        create table if not exists ledger_meta (
            key text primary key,
            value text not null
        );
        """
    )
    con.execute(
        "insert or ignore into ledger_meta(key,value) values('schema_version','1')"
    )
    con.commit()


def append_record(
    con: sqlite3.Connection,
    record: dict[str, Any],
    schema: dict[str, Any],
) -> str:
    validate_record(record, schema)
    digest = payload_sha256(record)
    payload = canonical_json(record)
    inserted = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        con.execute(
            """
            insert into trials(
                trial_id,created_at_utc,parent_hypothesis,strategy_revision,
                dataset_snapshot,dataset_sha256,payload_sha256,
                influenced_later_design,payload_json,inserted_at_utc
            ) values(?,?,?,?,?,?,?,?,?,?)
            """,
            (
                record["trial_id"],
                record["created_at_utc"],
                str(record["parent_hypothesis"]),
                str(record["strategy_revision"]),
                str(record["dataset_snapshot"]),
                record["dataset_sha256"],
                digest,
                1 if record["influenced_later_design"] else 0,
                payload,
                inserted,
            ),
        )
    except sqlite3.IntegrityError as exc:
        raise RuntimeError(
            f"trial_id already exists; immutable ledger refuses overwrite: {record['trial_id']}"
        ) from exc
    con.commit()
    return digest


def verify(con: sqlite3.Connection) -> dict[str, Any]:
    rows = con.execute(
        "select trial_id,payload_sha256,payload_json from trials order by trial_id"
    ).fetchall()
    corrupt: list[str] = []
    for trial_id, expected, payload_json in rows:
        obj = json.loads(payload_json)
        actual = payload_sha256(obj)
        if actual != expected:
            corrupt.append(trial_id)
    return {
        "status": "PASS" if not corrupt else "FAIL",
        "trial_count": len(rows),
        "corrupt_trial_ids": corrupt,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--db",
        type=Path,
        default=Path.home() / "Trading" / "Historical" / "trials" / "trial-ledger.sqlite3",
    )
    ap.add_argument(
        "--schema",
        type=Path,
        default=Path("research/historical/trial-ledger-schema.json"),
    )
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("init")
    add = sub.add_parser("append")
    add.add_argument("--record", type=Path, required=True)
    sub.add_parser("verify")
    sub.add_parser("list")

    args = ap.parse_args()
    schema = load_json(args.schema)
    con = connect(args.db)
    try:
        init_db(con)
        if args.command == "init":
            result = {"status": "PASS", "action": "init", "db": str(args.db)}
        elif args.command == "append":
            record = load_json(args.record)
            digest = append_record(con, record, schema)
            result = {
                "status": "PASS",
                "action": "append",
                "trial_id": record["trial_id"],
                "payload_sha256": digest,
            }
        elif args.command == "verify":
            result = {"action": "verify", **verify(con)}
        elif args.command == "list":
            rows = con.execute(
                """
                select trial_id,created_at_utc,parent_hypothesis,strategy_revision,
                       dataset_snapshot,influenced_later_design
                from trials order by created_at_utc,trial_id
                """
            ).fetchall()
            result = {
                "status": "PASS",
                "action": "list",
                "trials": [
                    {
                        "trial_id": r[0],
                        "created_at_utc": r[1],
                        "parent_hypothesis": r[2],
                        "strategy_revision": r[3],
                        "dataset_snapshot": r[4],
                        "influenced_later_design": bool(r[5]),
                    }
                    for r in rows
                ],
            }
        else:
            raise AssertionError("unreachable")
    finally:
        con.close()

    print("HISTORICAL_TRIAL_LEDGER " + json.dumps(result, sort_keys=True))
    return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
