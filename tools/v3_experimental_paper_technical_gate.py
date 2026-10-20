"""Optional STRICT technical-only release gate for V3 EXPERIMENTAL PAPER.

Paper is where economics are tested; profitability is NOT a prerequisite to
an exploratory Paper trial. But technical/recording/stop and single-writer
correctness ARE prerequisites. No effects, network, orders or strategy changes.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
# Repository unit tests import through tools.*, while the canonical project
# state validator runs tools/strategy_successor_gate.py as a direct script.
# Both invocation contexts must consume the SAME original transition guard.
try:
    from tools.paper_series_transition_guard import assess_v3_cutover_recovery
except ModuleNotFoundError as exc:
    if exc.name != "tools":
        raise
    from paper_series_transition_guard import assess_v3_cutover_recovery


# Source inventory for the existing V3 experimental PAPER release gate.
# This is NOT a release packet, runnable successor, signed build or proof.
# It only computes repeatable digests of source bytes already in this repo,
# so a later independently reviewed paper release can identify exact input.
# Never treat these candidate digests as approved runtime fingerprints.
BUNDLE_SOURCE="research/v3/v3-experimental-paper-all-lessons-bundle-20261011.json"
REQUIRED_SOURCE_ANCHORS=frozenset({
    "paper_evaluator/v3_paper_minipc_one_candidate_v1.py",
    "paper_evaluator/v3_experimental_paper_model_prompt_v1.py",
    "paper_evaluator/v3_experimental_paper_initial_review_v1.py",
    "paper_evaluator/v3_experimental_paper_journal_v1.py",
    "paper_evaluator/v3_experimental_paper_family_router_v1.py",
    "tools/v3_experimental_paper_technical_gate.py",
})
SOURCE_PATTERN=re.compile(
    r"(?:paper_evaluator|tools)/(?:[a-z0-9][a-z0-9_-]*/)*[a-z0-9][a-z0-9_-]*\.py\Z"
)


def assess_v3_experimental_source_inventory(root:Path)->dict[str,Any]:
    """Pure local read-only V3 source identity: never a live release ACK.

    Dynamic module references come from the existing source of truth bundle.
    Includes exact source bytes and errors on missing, unsafe or drifting files.
    No file writes, network, API, model, task, process, DB or activation.
    """
    errors:list[str]=[]
    paths:list[str]=[]
    file_hashes:list[list[str]]=[]
    strategy_hash=None
    inventory_hash=None
    revision=None
    outstanding_live_gates=[]
    try:
        root=root.resolve(strict=True)
        bundle=root/BUNDLE_SOURCE
        if (bundle.is_symlink() or not bundle.is_file()
                or not bundle.resolve(strict=True).is_relative_to(root)):
            raise ValueError("bundle outside source root")
        raw=bundle.read_bytes()
        if len(raw)>128*1024:
            raise ValueError("oversize bundle")
        v=json.loads(raw)
        if not isinstance(v,dict):
            raise ValueError("bundle is not an object")
        revision=v.get("strategy_revision")
        strategy_hash=hashlib.sha256(raw).hexdigest()
        state=v.get("current_verified_state")
        if isinstance(state,dict):
            # Read original, explicit FALSE fields as outstanding, never infer
            # that a missing or TRUE field is a completed host receipt.
            outstanding_live_gates=sorted(
                key for key,val in state.items()
                if isinstance(key,str) and val is False
            )
        if (v.get("kind")!="V3_EXPERIMENTAL_PAPER_ALL_LESSONS_POLICY_BUNDLE_V1"
                or not isinstance(revision,str)
                or not re.fullmatch(r"V3-[A-Za-z0-9_.-]{8,95}",revision)):
            errors.append("V3_SOURCE_BUNDLE_KIND_OR_REVISION_INVALID")
        if (v.get("status")!="CODE_READY_INACTIVE_RUNTIME_NOT_ACTIVATED"
                or v.get("scope")!="ONLY_EXPERIMENTAL_PAPER_NOT_REAL_MONEY"):
            errors.append("V3_BUNDLE_NOT_INACTIVE_PAPER_ONLY")
        rows=v.get("entry_priority")
        modules=v.get("canonical_modules")
        if (not isinstance(rows,list) or len(rows)<6
                or not isinstance(modules,dict) or len(modules)<7):
            errors.append("V3_SOURCE_REFERENCES_INCOMPLETE")
        else:
            source_refs=set(REQUIRED_SOURCE_ANCHORS)
            for item in modules.values():
                if isinstance(item,str) and item.endswith(".py"):
                    source_refs.add(item)
            for item in rows:
                if not isinstance(item,dict):
                    errors.append("V3_INVALID_ENTRY_POLICY_ROW")
                    continue
                if (not isinstance(item.get("module"),str)
                        or not item["module"].endswith(".py")):
                    errors.append("V3_INVALID_ENTRY_MODULE_REFERENCE")
                if item.get("runtime_enabled") is not False:
                    errors.append("V3_SOURCE_MISTAKENLY_RUNTIME_ENABLED")
                for key in ("module","consumer","candidate_generator","model_prompt"):
                    item_path=item.get(key)
                    if isinstance(item_path,str) and item_path.endswith(".py"):
                        source_refs.add(item_path)
            paths=sorted(source_refs)
            if len(paths)<len(REQUIRED_SOURCE_ANCHORS) or len(paths)>64:
                errors.append("V3_UNEXPECTED_SOURCE_SET_SIZE")
            for rel in paths:
                if len(rel)>180 or not SOURCE_PATTERN.fullmatch(rel):
                    errors.append("V3_UNSAFE_SOURCE_PATH")
                    continue
                path=root/rel
                try:
                    if (path.is_symlink() or not path.is_file()
                            or not path.resolve(strict=True).is_relative_to(root)):
                        raise ValueError("source path unsafe")
                    content=path.read_bytes()
                    if not content or len(content)>512*1024:
                        raise ValueError("empty/oversize source")
                    file_hashes.append([rel,hashlib.sha256(content).hexdigest()])
                except (OSError,ValueError):
                    errors.append("V3_MISSING_OR_UNSAFE_REFERENCED_SOURCE")
            if len(file_hashes)!=len(paths):
                errors.append("V3_SOURCE_HASH_SET_INCOMPLETE")
            if not errors:
                payload=json.dumps({
                    "kind":"V3_EXPERIMENTAL_PAPER_SOURCE_INVENTORY_CANDIDATE_V1",
                    "revision":revision,"strategy_bundle_sha256":strategy_hash,
                    "files":file_hashes,
                },sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("utf-8")
                inventory_hash=hashlib.sha256(payload).hexdigest()
    except (OSError,ValueError,TypeError,UnicodeError,json.JSONDecodeError):
        errors.append("V3_SOURCE_BUNDLE_UNAVAILABLE_OR_INVALID")
    # Physical release requirements are ALWAYS separate from these digests.
    return {
        "kind":"V3_EXPERIMENTAL_PAPER_SOURCE_INVENTORY_READONLY_V1",
        "strategy_revision":revision,
        "source_inventory_complete":not errors and inventory_hash is not None,
        "source_inventory_errors":sorted(set(errors)),
        "source_files_count":len(file_hashes),
        "candidate_source_files":paths,
        "original_bundle_unproven_live_gate_names":outstanding_live_gates,
        "candidate_strategy_bundle_source_sha256":strategy_hash,
        "candidate_source_inventory_sha256":inventory_hash,
        "candidate_digests_not_release_fingerprints":True,
        "full_transitive_dependency_closure_proven":False,
        "physical_runtime_loaded_or_started_here":False,
        "real_model_e2e_authenticated_here":False,
        "model_api_budget_approved_here":False,
        "cloud_successor_cas_or_writer_started_here":False,
        "original_writer_stop_rollback_proven_here":False,
        "paper_release_authorized":False,
        "authentic_technical_e2e_proofs_credited":0,
    }


# The existing experimental V3 source-inventory owner also serves the
# original native Windows One-Shot staging acceptance. This is a STATIC
# local-import graph: it does not import/execute candidate code or verify
# the physically loaded module bytes. Never use it as a seventh release gate.
V3_NATIVE_SOURCE_IMPORT_ROOTS=(
    "paper_evaluator/v3_paper_minipc_native_launcher_v1.py",
    "paper_evaluator/v3_paper_minipc_selective_tick_v1.py",
    "paper_evaluator/v3_paper_cloud_receipt_sync_v1.py",
    "tools/v3_experimental_paper_technical_gate.py",
)


def assess_v3_native_source_import_closure(root:Path)->dict[str,Any]:
    """Bounded source-only transitive LOCAL imports for maintenance staging.

    Keeps the existing source manifest authoritative; follows static Python
    imports into this very checkout. Third-party imports and dynamic module
    loading are reported separately, not falsely declared validated.
    """
    errors:list[str]=[]
    dynamic:list[str]=[]
    external:set[str]=set()
    manifest:list[list[str]]=[]
    closure_hash=None
    try:
        if root.is_symlink():
            raise ValueError("source checkout is symlink")
        root=root.resolve(strict=True)
        if not root.is_dir():
            raise ValueError("source checkout missing")
        direct=assess_v3_experimental_source_inventory(root)
        if not direct["source_inventory_complete"]:
            raise ValueError("existing bundle source inventory incomplete")
        seeds=set(direct["candidate_source_files"])|set(V3_NATIVE_SOURCE_IMPORT_ROOTS)
        pending=sorted(seeds)
        seen:set[str]=set()
        while pending:
            rel=pending.pop(0)
            if rel in seen:
                continue
            # Different existing code paths can import a top-level source
            # module or a known package; never accept absolute/dotdot paths.
            if (len(seen)>=512 or len(rel)>180
                    or rel.startswith("/") or "\\" in rel
                    or ".." in Path(rel).parts
                    or not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_./-]*\.py",rel)):
                raise ValueError("invalid/bounded transitive source path")
            target=root/rel
            if (target.is_symlink() or target.parent.is_symlink()
                    or not target.is_file()
                    or not target.resolve(strict=True).is_relative_to(root)):
                raise ValueError("missing or unsafe transitive source: "+rel)
            content=target.read_bytes()
            if not content or len(content)>512*1024:
                raise ValueError("oversize or empty transitive source: "+rel)
            parsed=ast.parse(content,filename=rel)
            seen.add(rel)
            manifest.append([rel,hashlib.sha256(content).hexdigest()])
            pkg=rel[:-3].split("/")[:-1]
            for node in ast.walk(parsed):
                modnames:list[str]=[]
                if isinstance(node,ast.Import):
                    modnames=[alias.name for alias in node.names]
                elif isinstance(node,ast.ImportFrom):
                    if node.level:
                        if node.level>len(pkg):
                            raise ValueError("transitive relative import outside package")
                        base=pkg[:len(pkg)-node.level+1]
                        mod=".".join(base+([node.module] if node.module else []))
                    else:
                        mod=node.module or ""
                    if mod:
                        modnames.append(mod)
                    for alias in node.names:
                        if alias.name!="*":
                            modnames.append(mod+"."+alias.name if mod else alias.name)
                elif isinstance(node,ast.Call):
                    call=node.func
                    if (isinstance(call,ast.Name) and call.id=="__import__"
                            or isinstance(call,ast.Attribute) and
                            call.attr=="import_module" and
                            isinstance(call.value,ast.Name) and
                            call.value.id=="importlib"):
                        dynamic.append(rel)
                for dotted in modnames:
                    prefix=dotted.split(".")[0]
                    relname=dotted.replace(".","/")
                    match=None
                    for candidate in (relname+".py",relname+"/__init__.py"):
                        if (root/candidate).is_file() or (root/candidate).is_symlink():
                            match=candidate
                            break
                    if match:
                        if match not in seen and match not in pending:
                            pending.append(match)
                    elif (root/prefix).is_dir() or (root/(prefix+".py")).is_file():
                        # 'from module import symbol' does not imply a
                        # separate module. Only a missing explicit Import
                        # indicates an actual unresolved local module.
                        if isinstance(node,ast.Import):
                            errors.append("UNRESOLVED_LOCAL_MODULE:"+dotted)
                    else:
                        external.add(prefix)
            pending.sort()
        payload=json.dumps(
            {"kind":"V3_NATIVE_SOURCE_STATIC_IMPORT_CLOSURE_CANDIDATE_V1",
             "files":sorted(manifest)},sort_keys=True,separators=(",",":"),
            ensure_ascii=True).encode("utf-8")
        closure_hash=hashlib.sha256(payload).hexdigest()
    except (OSError,ValueError,SyntaxError,TypeError,UnicodeError) as exc:
        errors.append("V3_NATIVE_SOURCE_IMPORT_CLOSURE_INCOMPLETE:"+type(exc).__name__)
    return {
        "kind":"V3_NATIVE_SOURCE_IMPORT_CLOSURE_READONLY_V1",
        "static_local_import_closure_complete":not errors and closure_hash is not None,
        "errors":sorted(set(errors)),
        "candidate_transitive_files":sorted(manifest),
        "candidate_transitive_file_count":len(manifest),
        "candidate_transitive_source_sha256":closure_hash,
        "third_party_or_stdlib_import_prefixes":sorted(external),
        # Static names only; no pip execution or version/installation claim.
        "stdlib_import_prefixes":sorted(external.intersection(
            sys.stdlib_module_names)),
        "external_import_prefixes_requiring_host_review":sorted(
            external.difference(sys.stdlib_module_names)),
        "dynamic_import_source_paths_review_required":sorted(set(dynamic)),
        "dynamic_imports_and_external_package_versions_proven":False,
        "actual_loaded_python_bytecode_independently_verified":False,
        "source_digests_not_final_release_pins":True,
        "physical_mini_pc_or_cloud_release_proven":False,
        "paper_release_authorized":False,
        "real_money_actions":False,
    }


PROOFS=frozenset({
    "V3_REAL_MODEL_COIN_PIT_P4_INPUT_E2E",
    "V3_FAIL_CLOSED_STOP_STAGE2_FEE_WAIT_CONTRACT",
    "V3_JOURNAL_REASONS_ERRORS_6H24H_FOLLOWUP_CENSURE",
    "V3_SINGLE_WRITER_FENCE_CLOUD_CAS_DRYRUN",
    "V3_MINIPC_SUPERVISOR_STOP_START_ROLLBACK",
    "V3_GITHUB_WORK_ALERT_DYNAMIC_SERIES_ROUTING",
})
SHA=re.compile(r"[0-9a-f]{64}\Z")

# Actual external evidence cannot be authenticated by a local hash alone.
# This offline schema guard rejects dummy files and forces each approval
# proof to contain original source readbacks that the separate release owner
# must independently compare to Mini-PC/Cloud/GitHub/Work.
PROOF_ORIGINS={
    "V3_REAL_MODEL_COIN_PIT_P4_INPUT_E2E":
        frozenset({"MINIPC_PHYSICAL","SUPABASE_CLOUD","SUPABASE_SANDBOX"}),
    "V3_FAIL_CLOSED_STOP_STAGE2_FEE_WAIT_CONTRACT":frozenset({"MINIPC_PHYSICAL"}),
    "V3_JOURNAL_REASONS_ERRORS_6H24H_FOLLOWUP_CENSURE":
        frozenset({"MINIPC_PHYSICAL","SUPABASE_CLOUD"}),
    "V3_SINGLE_WRITER_FENCE_CLOUD_CAS_DRYRUN":
        frozenset({"MINIPC_PHYSICAL","SUPABASE_CLOUD"}),
    "V3_MINIPC_SUPERVISOR_STOP_START_ROLLBACK":
        frozenset({"MINIPC_PHYSICAL"}),
    "V3_GITHUB_WORK_ALERT_DYNAMIC_SERIES_ROUTING":
        frozenset({"GITHUB","WORK"}),
}
# The already independently verified real-model receipts live in production.
# The OFFLINE synthetic writer cases live only in the revoked/paused test DB.
# Never combine these origins into a fictional single-project Cloud record.
PRODUCTION_ORIGINAL_PROJECT="nlgzjmqgwueojlyqmoru"
ISOLATED_SYNTHETIC_PROJECT="zxyhunwpviafyxyqysne"
ISOLATED_ORIGINAL_16_SHA="a5f9660f96fd714447566607539d1a05ce700fdab0a779cc457b746dc7dd25d1"
PROOF_KIND="V3_PAPER_TECHNICAL_E2E_READBACK_V1"
ORIGINAL_ID=re.compile(r"[A-Za-z0-9_.:/-]{8,160}\Z")


def _evidence_content_error(
        name:str,data:bytes,*,expected_code_sha:object,
        expected_strategy_sha:object)->str|None:
    """Schema/integrity only. Independent live provenance remains mandatory."""
    if len(data)>65536:
        return name+" oversized original E2E proof"
    try:
        proof=json.loads(data)
    except (ValueError,UnicodeError):
        return name+" E2E proof is not JSON"
    if (not isinstance(proof,dict) or proof.get("kind")!=PROOF_KIND
            or proof.get("proof_id")!=name or proof.get("fixture_only") is True
            or proof.get("real_e2e_fixture_only") is True):
        return name+" not a proof-specific real readback envelope"
    sources=proof.get("source_originals")
    required=PROOF_ORIGINS[name]
    if not isinstance(sources,list) or not 1<=len(sources)<=12:
        return name+" original external readbacks absent"
    present=set()
    by_origin={}
    for item in sources:
        if not isinstance(item,dict):
            return name+" original readback record invalid"
        origin,identity,payload,digest=(item.get(x) for x in
            ("origin","original_id","original_record","original_sha256"))
        if origin not in {"MINIPC_PHYSICAL","SUPABASE_CLOUD","SUPABASE_SANDBOX","GITHUB","WORK","SLACK"}:
            return name+" unrecognized independent proof source"
        if origin=="SUPABASE_SANDBOX" and name!="V3_REAL_MODEL_COIN_PIT_P4_INPUT_E2E":
            return name+" sandbox receipt not a required source for this proof"
        if not isinstance(identity,str) or not ORIGINAL_ID.fullmatch(identity):
            return name+" missing original external receipt ID"
        if not isinstance(digest,str) or not SHA.fullmatch(digest):
            return name+" invalid original readback checksum"
        if not isinstance(payload,dict) or len(payload)<3:
            return name+" empty or implausible external original record"
        if (payload.get("fixture_only") is True
                or payload.get("real_e2e_fixture_only") is True
                or payload.get("source_id")!=identity):
            return name+" test fixture or mismatched original readback"
        stamp=payload.get("observed_at_utc")
        try:
            seen=datetime.fromisoformat(stamp.replace("Z","+00:00"))
            if seen.tzinfo is None or seen.utcoffset() is None:
                raise ValueError("timestamp missing timezone")
            original=json.dumps(payload,sort_keys=True,separators=(",",":"),
                                allow_nan=False).encode("utf-8")
        except (AttributeError,ValueError,TypeError,UnicodeError,OverflowError):
            return name+" original readback timestamp/content invalid"
        if hashlib.sha256(original).hexdigest()!=digest:
            return name+" original readback content SHA mismatch"
        present.add(origin)
        if origin in by_origin:
            return name+" duplicated external readback source role"
        by_origin[origin]=payload
    if not required.issubset(present):
        return name+" missing required independent Mini-PC/Cloud/Work source role"
    # Technical proof #1 must NOT be a generic "the model and writer work"
    # claim. A real one-shot response MAY be WAIT/REJECT; the TWO physically
    # executed positive/negative Paper writer dry-runs may use *offline* model
    # stubs, but their actual host receipts must be independently inspected.
    # Never demand a profitable natural BUY before experimental Paper start.
    if name=="V3_REAL_MODEL_COIN_PIT_P4_INPUT_E2E":
        host=by_origin["MINIPC_PHYSICAL"]
        original=host.get("original_model_p4_readback")
        cases=host.get("native_paper_writer_dryrun_cases")
        if (not isinstance(original,dict) or
                not isinstance(cases,list) or len(cases)!=2):
            return name+" original paid-model and both Paper writer paths missing"
        if (original.get("model_http_attempts_reserved")!=1
                or original.get("model_http_retries")!=0
                or original.get("p4_decision") not in
                    ("BUY_SCOUT","WAIT","REJECT","UNKNOWN")
                or original.get("source_pit_complete") is not True
                or original.get("no_real_orders") is not True
                or not isinstance(original.get("model_response_id"),str)
                or not 8<=len(original["model_response_id"])<=150
                or not isinstance(original.get("original_pit_sha256"),str)
                or not SHA.fullmatch(original["original_pit_sha256"])
                or not isinstance(original.get("original_p4_receipt_sha256"),str)
                or not SHA.fullmatch(original["original_p4_receipt_sha256"])):
            return name+" actual one-shot model/PIT/P4 original not complete"
        by_case={x.get("case") if isinstance(x,dict) else None:x for x in cases}
        if (len(by_case)!=2 or set(by_case)!=
                {"POSITIVE_BUY_SCOUT","NEGATIVE_REJECT"}):
            return name+" two distinct positive/negative writer cases required"
        positive=by_case["POSITIVE_BUY_SCOUT"]
        negative=by_case["NEGATIVE_REJECT"]
        if (positive.get("p4_decision")!="BUY_SCOUT"
                or positive.get("paper_fill_result")!="PAPER_FILLED"
                or positive.get("paper_fill_count")!=1
                or positive.get("paper_scout_eur")!=50
                or positive.get("paper_entry_taker_fee_eur")!=0.30
                or negative.get("p4_decision")!="REJECT"
                or negative.get("paper_fill_result")!="NO_PAPER_FILL"
                or negative.get("paper_fill_count")!=0):
            return name+" positive/negative P4 to immutable Paper fill contradiction"
        ids=[]
        for case in cases:
            cid=case.get("candidate_id")
            series=case.get("series_id")
            if (not isinstance(cid,str) or not ORIGINAL_ID.fullmatch(cid)
                    or not isinstance(series,str)
                    or not re.fullmatch(r"PAPER-V3-[A-Za-z0-9-]{8,96}",series)
                    or case.get("execution_kind")!="PHYSICAL_MINIPC_OFFLINE_MODEL_STUB"
                    or case.get("original_native_owner_lock_verified") is not True
                    or case.get("disk_ledger_readback_verified") is not True
                    or case.get("no_real_orders") is not True
                    or case.get("no_provider_model_http_in_dryrun") is not True
                    or case.get("v2r4_runtime_unchanged") is not True
                    or not isinstance(case.get("p4_record_sha256"),str)
                    or not SHA.fullmatch(case["p4_record_sha256"])
                    or not isinstance(case.get("native_journal_record_sha256"),str)
                    or not SHA.fullmatch(case["native_journal_record_sha256"])):
                return name+" original host model/P4/ledger dry-run identity missing"
            ids.append((series,cid))
        if len(set(ids))!=2 or ids[0][0]!=ids[1][0]:
            return name+" positive and negative host cases must be separate same-series candidates"
        try:
            p4_time=datetime.fromisoformat(
                positive["p4_known_at_utc"].replace("Z","+00:00"))
            fill_time=datetime.fromisoformat(
                positive["paper_fill_known_at_utc"].replace("Z","+00:00"))
            if (p4_time.tzinfo is None or fill_time.tzinfo is None
                    or fill_time<p4_time):
                raise ValueError("positive original fill timestamp precedes P4")
        except (KeyError,ValueError,AttributeError,TypeError,OverflowError):
            return name+" positive Paper fill/P4 time ordering not witnessed"
        # A healthy Mini-PC and an internal 'Cloud ACK' flag cannot prove
        # the exact Paper fill reached append-only Supabase. Require an
        # independently fetched Cloud original for the SAME two case IDs,
        # with the identical immutable canonical event digests. Negative
        # P4 must have an independently observed ZERO Paper fills.
        cloud=by_origin["SUPABASE_CLOUD"]
        sandbox=by_origin["SUPABASE_SANDBOX"]
        cloud_cases=sandbox.get("paper_writer_dryrun_case_readbacks")
        if (cloud.get("cloud_project_id")!=PRODUCTION_ORIGINAL_PROJECT
                or sandbox.get("cloud_project_id")!=ISOLATED_SYNTHETIC_PROJECT
                or cloud.get("read_only") is not True
                or cloud.get("cloud_cas_performed") is not False
                or cloud.get("active_paper_series_changed") is not False
                or cloud.get("v2r4_live_strategy_modified") is not False
                or cloud.get("independent_original_receipt_query") is not True
                or cloud.get("same_event_id_reread_no_duplicate_verified") is not True
                or cloud.get("paper_writer_dryrun_case_readbacks") is not None
                or sandbox.get("original_model_response_id") is not None
                or sandbox.get("read_only") is not True
                or sandbox.get("cloud_cas_performed") is not False
                or sandbox.get("active_paper_series_changed") is not False
                or sandbox.get("v2r4_live_strategy_modified") is not False
                or sandbox.get("historical_independent_original_query_previously_completed") is not True
                or sandbox.get("fresh_sandbox_network_access") is not False
                or sandbox.get("synthetic_offline_fixtures_only") is not True
                or sandbox.get("original_synthetic_event_count")!=16
                or sandbox.get("original_historical_join_sha256")!=ISOLATED_ORIGINAL_16_SHA
                or sandbox.get("same_event_id_reread_no_duplicate_verified") is not True
                or cloud.get("original_model_response_id")!=
                    original["model_response_id"]
                or cloud.get("original_model_p4_receipt_sha256")!=
                    original["original_p4_receipt_sha256"]
                or not isinstance(cloud_cases,list)
                or len(cloud_cases)!=2):
            return name+" missing independent Cloud original model/P4/Paper readback"
        cloud_by_case={
            item.get("case") if isinstance(item,dict) else None:item
            for item in cloud_cases
        }
        if len(cloud_by_case)!=2 or set(cloud_by_case)!=set(by_case):
            return name+" Cloud case identities incomplete or duplicated"
        for case_name,host_case in by_case.items():
            remote=cloud_by_case[case_name]
            for key in (
                "series_id","candidate_id","p4_decision",
                "p4_record_sha256","native_journal_record_sha256",
                "paper_fill_count","paper_fill_result",
            ):
                if remote.get(key)!=host_case.get(key):
                    return name+" host/Cloud positive or negative original mismatch"
            if (remote.get("cloud_query_readback_verified") is not True
                    or remote.get("orders") is not False
                    or remote.get("real_money_actions") is not False):
                return name+" unverified independent Cloud append-only Paper row"
        try:
            remote_at=datetime.fromisoformat(
                sandbox["observed_at_utc"].replace("Z","+00:00"))
            if remote_at.tzinfo is None or remote_at<fill_time:
                raise ValueError("Cloud readback before physical Paper fill")
        except (ValueError,AttributeError,TypeError,OverflowError):
            return name+" sandbox original observation precedes positive Paper fill"
    if name=="V3_FAIL_CLOSED_STOP_STAGE2_FEE_WAIT_CONTRACT":
        host=by_origin["MINIPC_PHYSICAL"]
        checks=(
            "stop_below_current_ask_tested",
            "stage2_above_current_ask_and_ttl_tested",
            "taker_fee_roundtrip_spread_slippage_counted_tested",
            "invalid_stop_or_stage2_never_creates_fill_tested",
            "negative_net_edge_never_creates_fill_tested",
            "wait_trigger_no_buy_without_new_full_model_p4_tested",
            "missing_response_id_quarantined_tested",
            "p4_buy_without_durable_fill_quarantined_tested",
            "interrupted_http_reservation_never_retried_tested",
            "duplicate_child_episode_never_bought_twice_tested",
            "no_real_orders_tested",
        )
        if (any(host.get(key) is not True for key in checks)
                or host.get("paper_scout_eur")!=50
                or host.get("paper_stage2_eur")!=50
                or host.get("taker_fee_pct_each_side")!=0.6
                or host.get("paper_entry_fee_eur")!=0.30):
            return name+" physical Stop/Stage2/fee/WAIT/one-shot safety incomplete"
    # Strengthen the EXISTING journal/WAIT/followup proof, not a seventh gate.
    # A single TIA WAIT_RECHECK followed by UNKNOWN expiry proves fail-closed
    # missingness, NOT a continuously witnessed TTL or 6/24/72h followups.
    # Both source roles must identify the same physical V3 candidate/readback;
    # each asserted fact still needs independent original-host/cloud review.
    if name=="V3_JOURNAL_REASONS_ERRORS_6H24H_FOLLOWUP_CENSURE":
        host=by_origin["MINIPC_PHYSICAL"]
        cloud=by_origin["SUPABASE_CLOUD"]
        host_checks=(
            "original_v3_single_writer_wait_tick_tested",
            "valid_closed_5m_wait_observation_within_ttl_tested",
            "missing_or_late_wait_ticks_become_unknown_tested",
            "trigger_requires_fresh_full_model_and_p4_tested",
            "no_buy_wait_reject_skip_unknown_followup_routing_tested",
            "prospective_closed_1m_no_historical_backfill_tested",
            "followup_6h24h72h_and_gap_censor_logic_tested",
            "old_v2r4_aftercare_separate_series_preserved_tested",
        )
        cloud_checks=(
            "v3_wait_recheck_expiry_original_readback_verified",
            "v3_no_buy_followup_original_journal_readback_verified",
            "missingness_never_claimed_as_zero_pnl_verified",
            "old_v2r4_aftercare_remains_original_series_verified",
        )
        if (any(host.get(key) is not True for key in host_checks)
                or any(cloud.get(key) is not True for key in cloud_checks)):
            return name+" physical WAIT/No-BUY/6h24h72h original evidence incomplete"
        series=host.get("witnessed_v3_series_id")
        candidate=host.get("witnessed_v3_candidate_id")
        if (not isinstance(series,str)
                or not re.fullmatch(r"PAPER-V3-[A-Za-z0-9-]{8,96}",series)
                or not isinstance(candidate,str)
                or not ORIGINAL_ID.fullmatch(candidate)
                or cloud.get("witnessed_v3_series_id")!=series
                or cloud.get("witnessed_v3_candidate_id")!=candidate):
            return name+" independent V3 WAIT/No-BUY candidate lineage mismatch"
        # Before first experimental Paper, require physical schedule/source
        # wiring + bounded negative tests, NOT natural 72h results from the
        # future. After start, genuine maturing/censored receipts are separate.
    # Extend the EXISTING sixth technical proof, not a new release stage.
    # A healthy task status alone is not a bounded recovery receipt.
    # Independent validation of the physical source remains mandatory.
    if name=="V3_MINIPC_SUPERVISOR_STOP_START_ROLLBACK":
        host=by_origin["MINIPC_PHYSICAL"]
        required_recovery_checks=(
            "original_task_identity_and_source_pins_verified",
            "stop_only_candidates_wait_lifecycle_continues",
            "unknown_python_worker_blocks_unclassified",
            "admin_shell_path_reference_not_worker",
            "interrupted_marker_transition_preserves_armed_backup",
            "atomic_marker_repair_has_verified_backup",
            "partial_restore_keeps_fence_until_actual_worker_ack",
            "both_original_worker_heartbeats_advance_after_restart",
            "supervisor_healthy_after_marker_removed",
            "cloudsync_returns_active_original_no_network_hold_cleared",
            "no_v3_cas_or_real_money_actions",
        )
        if (any(host.get(key) is not True for key in required_recovery_checks)
                or host.get("final_fence_state")!="ABSENT"
                or host.get("restore_boundary")!="PRECOMMIT_ORIGINAL_ONLY"
                or host.get("recovery_ack_kind")!="REAL_MINIPC_POST_RESTORE_READBACK"):
            return name+" physical restart/recovery evidence incomplete"
    # A genuine single-writer dry run is NOT two arbitrary healthy readbacks.
    # It must bind one actual active V2R4 predecessor to the same proposed V3
    # successor on both independently checked physical and Cloud originals.
    # This is a content gate; provenance and CAS atomicity remain separate
    # physically verified obligations for the authorized release owner.
    if name=="V3_SINGLE_WRITER_FENCE_CLOUD_CAS_DRYRUN":
        host=by_origin["MINIPC_PHYSICAL"]
        cloud=by_origin["SUPABASE_CLOUD"]
        predecessor=host.get("expected_predecessor_series_id")
        successor=host.get("proposed_successor_series_id")
        if (not isinstance(predecessor,str)
                or not re.fullmatch(r"PAPER-V2R4-[0-9]{8}T[0-9]{6}Z",predecessor)
                or not isinstance(successor,str)
                or not re.fullmatch(r"PAPER-V3-[A-Za-z0-9-]{8,96}",successor)
                or cloud.get("expected_predecessor_series_id")!=predecessor
                or cloud.get("proposed_successor_series_id")!=successor):
            return name+" physical and cloud expected predecessor/successor mismatch"
        # Both original sources must refer not just to the same Paper IDs
        # but also to the same immutable old/new release and bundled strategy.
        # The V3 bundle and strategy must match the OUTER independently
        # reviewed technical release packet; a coincidentally correct
        # self-hash of a different bundle is insufficient.
        fingerprints=(
            ("expected_old_repo_sha",40,None),
            ("proposed_v3_repo_sha",40,None),
            ("proposed_v3_bundle_sha256",64,expected_code_sha),
            ("proposed_v3_strategy_sha256",64,expected_strategy_sha),
        )
        for key,length,expected in fingerprints:
            original=host.get(key)
            if (not isinstance(original,str)
                    or not re.fullmatch(r"[0-9a-f]{"+str(length)+r"}",original)
                    or cloud.get(key)!=original
                    or expected is not None and original!=expected):
                return name+" host/cloud or outer-packet release fingerprint mismatch"
        if (host.get("physical_writer_fence_dry_run_passed") is not True
                or host.get("new_v3_writer_started") is not False
                or host.get("v2r4_live_strategy_modified") is not False
                or cloud.get("single_active_unique_index_present") is not True
                or cloud.get("expected_predecessor_cas_dry_run_passed") is not True
                or cloud.get("v2r4_only_rotation_not_invoked") is not True
                or cloud.get("active_paper_series_changed") is not False
                or any(payload.get("dry_run_only") is not True
                       for payload in (host,cloud))):
            return name+" false physical fence or cloud CAS dry-run assertion"
        # Test both sides of the rollback boundary. The concrete source
        # receipts still require independent validation outside this parser.
        if (host.get("precommit_original_backup_verified") is not True
                or host.get("precommit_restore_only_before_cloud_commit_tested") is not True
                or host.get("old_followups_retained_on_original_series_tested") is not True
                or host.get("old_followup_owner_running_after_cutover_tested") is not True
                or host.get("old_supervisor_intake_rearm_fence_tested") is not True
                or cloud.get("stale_predecessor_cas_rejected_tested") is not True
                or cloud.get("ambiguous_cloud_outcome_quarantines_both_tested") is not True
                or cloud.get("postcommit_no_predecessor_restart_tested") is not True
                or cloud.get("closed_old_series_followup_update_accepted_tested") is not True
                or cloud.get("closed_old_series_trade_exit_update_accepted_tested") is not True
                or cloud.get("closed_old_series_new_intake_rejected_tested") is not True
                or cloud.get("phase")!="CLOUD_COMMIT_NOT_ATTEMPTED"):
            return name+" V3 pre/post-CAS rollback safety not witnessed"
        active=cloud.get("active_paper_series")
        recovery=assess_v3_cutover_recovery(
            phase=cloud["phase"],active_series=active,
            expected_old=predecessor,proposed_new=successor)
        if recovery["disposition"]!="PRECOMMIT_DRYRUN_ONLY_NO_CLOUD_MUTATION":
            return name+" invalid real pre-CAS active-series readback"
    # These checks cannot prove who supplied the JSON. The external owner
    # still must perform fresh independent comparisons before release.
    return None


def validate_experimental_paper_packet(root: Path, revision: str,
                                       packet: dict[str, Any]) -> list[str]:
    """Return blockers. No approval from a CI fixture or old V3 model budget."""
    errors: list[str]=[]
    def block(why: str)->None:
        errors.append("EXPERIMENTAL_PAPER_BLOCKED: "+why)

    if not revision.startswith("V3-") or packet.get("strategy_revision")!=revision:
        block("exact V3 revision not pinned")
    if (packet.get("kind")!="SUCCESSOR_STRATEGY_CAUSAL_RELEASE_EVIDENCE_V1"
            or packet.get("paper_phase")!="EXPERIMENTAL_PAPER_ONLY"
            or packet.get("status")!="READY_WITH_EXPLICIT_EXPERIMENTAL_PAPER_APPROVAL"):
        block("wrong experimental Paper release packet")
    if (packet.get("explicit_human_release_decision")!="APPROVED_EXPERIMENTAL_PAPER"
            or packet.get("real_money_actions") is not False
            or packet.get("paper_only") is not True
            or packet.get("automatic_activation") is not False):
        block("human-authorized Paper-only and no-auto-start required")
    for k in ("code_fingerprint_sha256","strategy_fingerprint_sha256"):
        v=packet.get(k)
        if not isinstance(v,str) or not SHA.fullmatch(v):
            block("invalid pinned "+k)
    scope=packet.get("bounded_research_scope")
    if not isinstance(scope,dict):
        scope={}
    for k,maximum in (("max_candidates",500),("max_model_http_attempts_including_retries",1000),
                      ("max_observation_days",21)):
        v=scope.get(k)
        if type(v) is not int or not 1<=v<=maximum:
            block("missing/invalid finite "+k)
    for k in ("deduplicate_pair_clock","mandatory_real_6h_24h_and_censored_followups",
              "stop_when_budget_exhausted"):
        if scope.get(k) is not True:
            block("missing "+k)
    risk=packet.get("frozen_execution_risk")
    if not isinstance(risk,dict):
        risk={}
    for k,want in (("taker_pct_each_side",0.6),("scout_eur",50),("stage2_eur",50)):
        if risk.get(k)!=want: block("altered "+k)
    for k in ("kraken_online_spot_eur","true_pit_1m5m15m_atr_stop",
              "full_model_decision_before_any_paper_buy",
              "stop_stage2_spread_slippage_required","no_real_orders",
              "no_h3_h6_auto_activation"):
        if risk.get(k) is not True: block("missing risk "+k)
    if packet.get("economic_alpha_claimed") is not False:
        block("Paper experiment cannot claim economic alpha")
    if packet.get("post_experiment_promotion_requires_economic_gate") is not True:
        block("later economic promotion gate missing")
    if packet.get("fixed_api_cost_limit_user_authorized") is not True:
        block("new fixed-cost budget authorization missing")
    # Pre-cutover requirement is a physically verified dry run, not a
    # POST-cutover ACK (requiring post ACK to authorize cutover is circular).
    # Post-cutover ACK is checked later by the existing cloud+Mini-PC monitors.
    if packet.get("physical_single_writer_cutover_dry_run_passed") is not True:
        block("physical single-writer transition dry run missing")
    if packet.get("physical_single_writer_cutover_ack_obtained") is True:
        block("release packet falsely claims post-cutover ACK before activation")
    rows=packet.get("experimental_paper_technical_proofs")
    if not isinstance(rows,list) or len(rows)!=len(PROOFS) or any(not isinstance(x,dict) for x in rows):
        block("six actual technical evidence rows required")
        return errors
    by_id={x.get("id"):x for x in rows}
    if len(by_id)!=len(rows) or set(by_id)!=PROOFS:
        block("technical proof IDs mismatch or duplicated")
    for name in PROOFS:
        x=by_id.get(name)
        if not isinstance(x,dict):
            continue
        if x.get("status")!="VERIFIED_PHYSICAL_OR_CLOUD_E2E":
            block(name+" not physically verified")
        path=x.get("evidence_path")
        digest=x.get("sha256")
        if (not isinstance(path,str) or not path.startswith("research/")
                or Path(path).is_absolute() or ".." in Path(path).parts):
            block(name+" invalid path")
            continue
        try:
            target=(root/path)
            research=(root/"research").resolve(strict=True)
            resolved=target.resolve(strict=True)
            if (target.is_symlink() or not resolved.is_relative_to(research)
                    or not target.is_file()):
                raise ValueError("evidence path escapes guarded research")
            data=target.read_bytes()
        except (OSError,ValueError):
            block(name+" evidence file absent or unsafe path")
            continue
        if not isinstance(digest,str) or not SHA.fullmatch(digest) or hashlib.sha256(data).hexdigest()!=digest:
            block(name+" evidence SHA mismatch")
            continue
        content_error=_evidence_content_error(
            name,data,expected_code_sha=packet.get("code_fingerprint_sha256"),
            expected_strategy_sha=packet.get("strategy_fingerprint_sha256"))
        if content_error:
            block(content_error)
    return errors


def native_source_closure_readonly_main(argv:list[str]|None=None)->int:
    """Emit source-stage observations without touching Windows/Cloud/runtime."""
    parser=argparse.ArgumentParser(
        description="V3 experimental Paper stage: static source/dependency readback ONLY")
    parser.add_argument("--source-closure-readonly",action="store_true",required=True)
    parser.add_argument("--source-root",type=Path,
                        default=Path(__file__).absolute().parent.parent)
    args=parser.parse_args(argv)
    report=assess_v3_native_source_import_closure(args.source_root)
    # No output file, pip install, runtime imports, git pull or activation.
    report["inspection_authority"]="SOURCE_ONLY_NO_ORIGINALHOST_OR_CLOUD_ACK"
    report["runtime_dependency_versions_verified"]=False
    report["candidate_checkout_path"]=str(args.source_root.absolute())
    print(json.dumps(report,sort_keys=True,ensure_ascii=True,indent=2))
    return 0 if report["static_local_import_closure_complete"] else 2


if __name__=="__main__":
    raise SystemExit(native_source_closure_readonly_main())
