#!/usr/bin/env python3
import hashlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
run_id, attempt = sys.argv[2], sys.argv[3]
prefix = f"paper-market-tape-{run_id}-{attempt}-"
manifest_artifact = prefix + "manifest"
manifest_files = list(root.rglob("parts-manifest.json"))
if len(manifest_files) != 1:
    raise SystemExit(f"expected one uploaded parts manifest; found {len(manifest_files)}")
parts_manifest = json.loads(manifest_files[0].read_text(encoding="utf-8"))
if parts_manifest.get("schema_version") != 1:
    raise SystemExit("unsupported parts manifest schema")
entries = parts_manifest["parts"]
if not entries:
    raise SystemExit("no parts listed in manifest")

expected_artifacts = {manifest_artifact}
for entry in entries:
    expected_artifacts.add(prefix + f"part-{entry['index']:03d}")
actual_artifacts = {path.name for path in root.iterdir() if path.is_dir()}
if actual_artifacts != expected_artifacts:
    missing = sorted(expected_artifacts - actual_artifacts)
    unexpected = sorted(actual_artifacts - expected_artifacts)
    raise SystemExit(f"artifact mapping mismatch missing={missing} unexpected={unexpected}")

manifest_payloads = list(root.rglob("manifest.json"))
if len(manifest_payloads) != 1:
    raise SystemExit(f"expected one original capture manifest; found {len(manifest_payloads)}")

whole_hash = hashlib.sha256()
total_bytes = 0
with open(root / "reassembled.events.jsonl.gz", "wb") as combined:
    for expected_index, entry in enumerate(entries):
        if entry["index"] != expected_index:
            raise SystemExit(f"out-of-order manifest entry at position {expected_index}: {entry['index']}")
        matches = list(root.rglob(entry["name"]))
        if len(matches) != 1:
            raise SystemExit(f"expected one uploaded part {entry['name']}; found {len(matches)}")
        part_path = matches[0]
        digest = hashlib.sha256()
        size = 0
        with part_path.open("rb") as part:
            while block := part.read(1024 * 1024):
                digest.update(block)
                whole_hash.update(block)
                combined.write(block)
                size += len(block)
        if size != entry["size_bytes"] or digest.hexdigest() != entry["sha256"]:
            raise SystemExit(f"part integrity mismatch for {entry['name']}")
        total_bytes += size

if total_bytes != parts_manifest["source_size_bytes"]:
    raise SystemExit(f"source size mismatch expected={parts_manifest['source_size_bytes']} actual={total_bytes}")
if whole_hash.hexdigest() != parts_manifest["source_sha256"]:
    raise SystemExit("reassembled source SHA-256 mismatch")

print(
    "PAPER_UPLOAD_ROUNDTRIP_VERIFIED "
    + json.dumps(
        {
            "generated_parts": len(entries),
            "uploaded_parts": len(entries),
            "fully_mapped_parts": len(actual_artifacts) - 1,
            "source_bytes": total_bytes,
            "sha256_verified": True,
            "ordered_reassembly_verified": True,
        },
        sort_keys=True,
    )
)
