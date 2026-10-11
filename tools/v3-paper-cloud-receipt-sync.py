#!/usr/bin/env python3
"""Command-line Mini-PC V3 Paper cloud sync; all code lives in tested module."""
import argparse,json
from pathlib import Path
from paper_evaluator.v3_paper_cloud_receipt_sync_v1 import sync_once

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--journal",type=Path,required=True)
    p.add_argument("--series",required=True)
    p.add_argument("--ack-file",type=Path,required=True)
    p.add_argument("--relay-secret-file",type=Path,required=True)
    p.add_argument("--execute-cloud-sync",action="store_true")
    a=p.parse_args()
    if not a.execute_cloud_sync:
        print(json.dumps({"status":"PREFLIGHT_ONLY_NO_CLOUD_WRITE",
                          "local_receipts":len(list(a.journal.glob("*.json")))}))
        return 0
    token=a.relay_secret_file.read_text("utf-8").strip()
    print(json.dumps(sync_once(journal=a.journal,series_id=a.series,
                               ack_file=a.ack_file,token=token),sort_keys=True))
    return 0

if __name__=="__main__":raise SystemExit(main())
