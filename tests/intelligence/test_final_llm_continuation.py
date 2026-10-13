"""Synthetic state only: untouched suffix, permanent missingness and shared cap."""

import ast
import json
from decimal import Decimal
from pathlib import Path

import pytest

from archguard.benchmark.oss.models import digest
from archguard.infrastructure import final_llm_continuation as c
from archguard.infrastructure import final_llm_executor as e
from archguard.infrastructure import unified_human_review as io
from tests.intelligence import test_final_llm as final_tests

bundle = final_tests.bundle
success = final_tests.success


@pytest.fixture
def continuation(bundle, monkeypatch, tmp_path):
    root, oldledger, approval = bundle
    config = io.read_seal(root / "protocol.json")
    manifest, _, pricing = e.load_bundle(root)
    rows = manifest["rows"]
    e.prepare_ledger(oldledger, io.read_seal(root / "bundle-freeze.json")["fingerprint"])
    original_cost = Decimal(0)
    for row in rows[:75]:
        prefix = f"attempt-{row['request_id']}-01"
        intent = io.append_seal(
            oldledger / f"{prefix}.json",
            dict(
                prefix=prefix,
                request_id=row["request_id"],
                execution_id=row["execution_id"],
                attempt=1,
                request_fingerprint=row["request_fingerprint"],
                reserved_usd="0.0042768",
                provider="openai",
                model="gpt-6-luna",
                processing="STANDARD",
                timestamp="2026-01-01T00:00:00+00:00",
                recovery_of=None,
            ),
        )
        wire = io.read_seal(root / "payloads" / f"{row['request_id']}.json")["wire_payload"]
        result = success(wire, None)
        if row == rows[74]:
            data = json.loads(result.assessment)
            data["request_id"] = digest("wrong-synthetic-id")
            result = e.Outcome(
                "OK",
                b"synthetic invalid audit only",
                json.dumps(data),
                100,
                50,
                dict(input_tokens=100, output_tokens=50),
            )
        e.store_outcome(oldledger, intent, row, result, pricing, config)
        original_cost += pricing.charge(100, 50)
    state = e.ledger_state(oldledger, manifest, config, pricing)
    # Small transport subset for fast protocol tests; separate full suffix proof below.
    suffix = {"rows": rows[75:78]}
    plan = tmp_path / "plan"
    ledger = tmp_path / "continuation"
    monkeypatch.setattr(c, "ROOT", plan)
    monkeypatch.setattr(c, "LEDGER", ledger)
    monkeypatch.setattr(e, "ROOT", root)
    io.append_seal(plan / "plan-freeze.json", dict(files={}))
    proto = dict(partial_freeze_fingerprint=digest("synthetic-partial"))
    monkeypatch.setattr(c, "load", lambda _: (suffix, config, pricing, state, proto))
    return root, oldledger, ledger, suffix, config, pricing, state, proto


def run(continuation, transport, decoder=None):
    root, oldledger, ledger, _, _, _, _, _ = continuation
    with c.scope((root, oldledger, c.ROOT), (ledger,)):
        return c.execute({}, transport, decoder)


def test_success_suffix_order_once_resume_and_original_immutable(continuation):
    root, oldledger, ledger, manifest, config, pricing, old, _ = continuation
    before = {f.name: io.sha(f) for f in oldledger.iterdir()}
    calls = []

    def send(wire, capture):
        calls.append(json.loads(wire["input"][1]["content"])["task"]["request_id"])
        return success(wire, capture)

    result = run(continuation, send)
    assert result["status"] == "COMPLETE" and result["accepted"] == 3
    assert calls == [r["request_id"] for r in manifest["rows"]]
    assert before == {f.name: io.sha(f) for f in oldledger.iterdir()}
    run(continuation, lambda *a: pytest.fail("accepted repeat"))
    state = c.segment_state(manifest, config, pricing)
    for rid in old["attempts"]:
        if old["attempts"][rid]:
            with pytest.raises(PermissionError):
                c.guard_request(rid, manifest, old, state)
    for rid in state["accepted"]:
        with pytest.raises(PermissionError):
            c.guard_request(rid, manifest, old, state)


def test_exact_225_suffix_and_terminal_missing_no_semantic_content(continuation):
    root, _, _, _, config, pricing, old, _ = continuation
    manifest, _, _ = e.load_bundle(root)
    suffix = manifest["rows"][75:]
    assert len(suffix) == len({r["request_id"] for r in suffix}) == 225
    assert all(not old["attempts"][r["request_id"]] for r in suffix)
    assert len(old["accepted"]) == 74 and len(old["results"]) == 75
    bad = [r for r in old["results"] if r["state"] == "REQUEST_ID_MISMATCH"]
    assert len(bad) == 1 and bad[0]["normalized"] is None
    assert not bad[0]["request_id_echo"] and bad[0]["target_rule_binding"]


@pytest.mark.parametrize("kind", ["schema", "ID", "CONFIGURATION_ERROR"])
def test_new_invalid_is_terminal_and_never_retried(continuation, kind):
    calls = []

    def send(wire, capture):
        calls.append(digest(wire))
        result = success(wire, capture)
        if kind == "schema":
            return e.Outcome("OK", b"invalid", "{}", 100, 50)
        if kind == "ID":
            data = json.loads(result.assessment)
            data["request_id"] = digest("wrong")
            return e.Outcome("OK", b"invalid", json.dumps(data), 100, 50)
        return e.Outcome(kind, b"configuration error", input_tokens=100, output_tokens=0)

    result = run(continuation, send)
    assert result["accepted"] == 0 and len(calls) == 1
    assert result["status"] == {"schema": "SCHEMA_INVALID", "ID": "REQUEST_ID_MISMATCH"}.get(
        kind, kind
    )
    run(continuation, lambda *a: pytest.fail("terminal repeat"))


def test_cumulative_budget_cannot_reset_prior_exposure(continuation, monkeypatch):
    root, _, _, _, config, pricing, old, _ = continuation
    reserve = pricing.charge(32768, 2000)
    monkeypatch.setattr(c, "CAP", old["exposure"] + reserve - Decimal(".0000001"))
    result = run(continuation, lambda *a: pytest.fail("shared cap must refuse"))
    assert result["status"] == "PAID_CAP_REACHED" and result["provider_invocations"] == 0
    assert Decimal(result["estimated_or_reserved_usd"]) == old["exposure"]


@pytest.mark.parametrize("status", ["TIMEOUT", "CONNECTION", "RATE_LIMIT", "TRANSIENT"])
def test_technical_only_retries_identical_bounded_three(continuation, status):
    calls = []

    def send(wire, capture):
        calls.append(digest(wire))
        return e.Outcome(status, b"synthetic technical", input_tokens=100, output_tokens=0)

    result = run(continuation, send)
    assert result["status"] == "RETRY_EXHAUSTED" and len(calls) == 3 and len(set(calls)) == 1
    assert result["technical_retries"] == 2


def test_ambiguous_never_blindly_resends(continuation):
    def crash(*a):
        raise RuntimeError("synthetic transport interruption")

    first = run(continuation, crash)
    second = run(continuation, lambda *a: pytest.fail("blind replacement"))
    assert first["status"] == second["status"] == "AMBIGUOUS_TRANSPORT"
    assert first["provider_invocations"] == second["provider_invocations"] == 1
    assert Decimal(second["estimated_or_reserved_usd"]) > continuation[6]["exposure"]


def test_readonly_history_truth_secret_network_and_fit_boundaries(continuation, tmp_path):
    root, oldledger, ledger, *_ = continuation
    oldfile = next(oldledger.glob("*.json"))
    before = io.sha(oldfile)
    with c.scope((root, oldledger), (ledger,)):
        with pytest.raises(PermissionError):
            oldfile.write_bytes(b"overwritten")
        for path in [
            io.FINAL / "truth.json",
            io.PRIVATE / "human-intake/accepted/A/canonical-response.json",
            io.PRIVATE / "p023-hybrid-models-v1/train.json",
            Path(".env.ai.local"),
            tmp_path / "unmounted.json",
        ]:
            with pytest.raises(PermissionError):
                c.audit_hook("open", (str(path), "r", 0))
        with pytest.raises(PermissionError):
            c.core.audit_hook("socket.connect", ())
    assert io.sha(oldfile) == before
    trees = [ast.parse(Path(n).read_text()) for n in c.SOURCES[:2]]
    forbidden = {
        "fit",
        "predict",
        "evaluate",
        "calibrate",
        "select_candidate",
        "evaluate_effectiveness",
    }
    for tree in trees:
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in forbidden
            for node in ast.walk(tree)
        )


REAL_LOAD = c.load


@pytest.fixture
def prepared(continuation, monkeypatch, tmp_path):
    root, oldledger, _, _, config, pricing, old, _ = continuation
    # Rebind fixture usage to the real frozen aggregate, without real provider calls.
    # A separate immutable synthetic history exercises the complete plan loader.
    synthetic = tmp_path / "historical"
    manifest = io.read_seal(root / "manifest.json")
    e.prepare_ledger(synthetic, io.read_seal(root / "bundle-freeze.json")["fingerprint"])
    for pos, row in enumerate(manifest["rows"][:75]):
        prefix = f"attempt-{row['request_id']}-01"
        inp, out = (2755, 419) if pos < 74 else (2806, 440)
        intent = io.append_seal(
            synthetic / f"{prefix}.json",
            dict(
                prefix=prefix,
                request_id=row["request_id"],
                execution_id=row["execution_id"],
                attempt=1,
                request_fingerprint=row["request_fingerprint"],
                reserved_usd="0.0042768",
                provider="openai",
                model="gpt-6-luna",
                processing="STANDARD",
                timestamp=f"2026-01-01T00:00:{pos:02}+00:00",
                recovery_of=None,
            ),
        )
        wire = io.read_seal(root / "payloads" / f"{row['request_id']}.json")["wire_payload"]
        sample = success(wire, None)
        data = json.loads(sample.assessment)
        if pos == 74:
            data.update(request_id=digest("synthetic-invalid"), decision="SUPPORTED")
        outcome = e.Outcome(
            "OK",
            sample.raw,
            json.dumps(data),
            inp,
            out,
            dict(
                input_tokens=inp,
                output_tokens=out,
                total_tokens=inp + out,
                input_tokens_details=dict(cached_tokens=0),
            ),
        )
        e.store_outcome(synthetic, intent, row, outcome, pricing, config)
    runtime = e.approval_bindings(root) | dict(paid_execution_approved=True, hard_cap_usd="3.85")
    runtime_seal = io.append_seal(synthetic / "approval.json", runtime)
    state = e.ledger_state(synthetic, manifest, config, pricing)
    partial = tmp_path / "partial"
    parts = {
        "normalized-assessments.json": dict(
            assessments=[state["accepted"][r["request_id"]] for r in manifest["rows"][:74]]
        ),
        "raw-ledger.json": dict(provider_invocations=75),
        "usage-ledger.json": dict(cost=str(state["exposure"])),
        "execution-lineage.json": dict(version="synthetic-lineage"),
        "approval-receipt.json": dict(approval_fingerprint=digest(runtime)),
        "completion-receipt.json": dict(accepted=74),
    }
    fps = {name: io.append_seal(partial / name, v)["fingerprint"] for name, v in parts.items()}
    receipt = io.append_seal(
        partial / "freeze-receipt.json",
        dict(
            files={name: io.sha(partial / name) for name in parts},
            fingerprints=fps,
            original_ledger_files={f.name: io.sha(f) for f in synthetic.iterdir()},
        ),
    )
    public_path = tmp_path / "historical-public.json"
    public = io.append_seal(
        public_path,
        dict(
            fingerprints=fps
            | {
                "freeze-receipt.json": receipt["fingerprint"],
                "runtime-approval": runtime_seal["fingerprint"],
                "human-approval": digest(runtime),
            },
            reported_input_tokens=206676,
            reported_output_tokens=31446,
            reported_total_tokens=238122,
            reported_cached_input_tokens=0,
        ),
    )
    for name, value in {
        "ROOT": tmp_path / "full-plan",
        "LEDGER": tmp_path / "segment",
        "PARTIAL": partial,
        "PARTIAL_PUBLIC": public_path,
        "PARTIAL_PUBLIC_FP": public["fingerprint"],
        "APPROVAL": tmp_path / "approval",
        "FREEZE": tmp_path / "segment-freeze",
        "COMPOSITE": tmp_path / "composite",
        "PUBLIC": tmp_path / "public.json",
        "load": REAL_LOAD,
    }.items():
        monkeypatch.setattr(c, name, value)
    monkeypatch.setattr(e, "LEDGER", synthetic)
    monkeypatch.setattr(c, "git_gate", lambda **_: None)
    lock = io.read_seal(root / "model-lock.json")
    monkeypatch.setattr(
        c.p, "model_gate", lambda: {k: v for k, v in lock.items() if k != "fingerprint"}
    )
    c.prepare()
    approval = c.approval_bindings() | dict(paid_execution_approved=True)
    return approval, manifest, synthetic, partial


def test_full_prepared_225_exact_suffix_and_history_immutability(prepared):
    approval, manifest, legacy, partial = prepared
    before = {f.name: io.sha(f) for f in legacy.iterdir()}
    suffix, config, pricing, old, protocol = c.load(approval)
    assert suffix["rows"] == manifest["rows"][75:] and len(suffix["rows"]) == 225
    assert old["exposure"] == Decimal("0.0363906") and config["schema_id_recovery_max"] == 0
    binding = io.read_seal(c.ROOT / "terminal-invalid-binding.json")
    assert binding["request_id"] == manifest["rows"][74]["request_id"]
    assert binding["retry_allowed"] is False and binding["semantic_decision"] is None
    with c.scope((legacy, partial, c.ROOT)), pytest.raises(PermissionError):
        (partial / "completion-receipt.json").write_bytes(b"changed")
    assert before == {f.name: io.sha(f) for f in legacy.iterdir()}


@pytest.mark.parametrize(
    "field",
    [
        "stage",
        "new_logical_requests_authorized",
        "terminal_invalid_retry_authorized",
        "hard_cap_usd_total_stage",
        "hard_cap_increase",
        "plan_fingerprint",
        "continuation_allowlist_fingerprint",
        "partial_freeze_fingerprint",
    ],
)
def test_approval_gates_precede_provider_construction(prepared, field):
    approval, *_ = prepared
    invalid = approval | {field: "unauthorized"}
    with pytest.raises(PermissionError):
        c.load(invalid)


def test_successful_299_plus_missing_composite_twice_no_imputation(prepared):
    approval, manifest, legacy, partial = prepared
    suffix, config, pricing, old, protocol = c.initialize(approval)
    exposure = old["exposure"]
    for row in suffix["rows"]:
        prefix = f"attempt-{row['request_id']}-01"
        reserve = pricing.charge(32768, 2000)
        intent = io.append_seal(
            c.LEDGER / f"{prefix}.json",
            dict(
                prefix=prefix,
                request_id=row["request_id"],
                execution_id=row["execution_id"],
                attempt=1,
                request_fingerprint=row["request_fingerprint"],
                reserved_usd=str(reserve),
                provider="openai",
                model="gpt-6-luna",
                processing="STANDARD",
                timestamp="2026-01-02T00:00:00+00:00",
                recovery_of=None,
                segment="p024-final-live-continuation-v1",
                global_logical_state="NEVER_EXECUTED",
                total_stage_reserved_at_intent_usd=str(exposure + reserve),
                partial_freeze_fingerprint=protocol["partial_freeze_fingerprint"],
            ),
        )
        wire = io.read_seal(e.ROOT / "payloads" / f"{row['request_id']}.json")["wire_payload"]
        result = success(wire, None)
        result = e.Outcome(
            result.status,
            result.raw,
            result.assessment,
            100,
            50,
            dict(
                input_tokens=100,
                output_tokens=50,
                total_tokens=150,
                input_tokens_details=dict(cached_tokens=0),
            ),
        )
        e.store_outcome(c.LEDGER, intent, row, result, pricing, config)
        exposure += pricing.charge(100, 50)
    first = c.freeze(approval)
    second = c.freeze(approval)
    assert first == second and first["status"] == "P024_LIVE_1_CONTINUATION_COMPLETE"
    assert (
        first["total_accepted"] == 299
        and first["technical_missing"] == 1
        and first["unexecuted"] == 0
    )
    assert first["total_provider_invocations"] == 300 and first["decisions"]["SUPPORTED"] == 0
    statuses = io.read_seal(c.COMPOSITE / "technical-status.json")["rows"]
    missing = [r for r in statuses if r["llm_technical_missing"]]
    assert (
        len(missing) == 1
        and missing[0]["llm_evidence_status"] == "TERMINAL_INVALID_REQUEST_ID_MISMATCH"
    )
    assert "semantic_decision" not in missing[0]
    accepted = io.read_seal(c.COMPOSITE / "accepted-assessments.json")["assessments"]
    assert len(accepted) == 299 and missing[0]["request_id"] not in {
        r["assessment"]["request_id"] for r in accepted
    }
    assert (
        first["total_exposure_usd"] == str(exposure)
        and first["original_known_cost_usd"] == "0.0363906"
    )
    for path in [
        c.FREEZE / "usage-ledger.json",
        c.COMPOSITE / "lineage.json",
        c.COMPOSITE / "freeze-receipt.json",
    ]:
        assert "timestamp" not in path.read_text() and "frozen_at" not in path.read_text()


def test_offline_captured_response_recovered_without_regeneration(continuation):
    def interrupted(wire, capture):
        good = success(wire, capture)
        capture(good.raw, {"synthetic": True})
        raise RuntimeError("after complete capture")

    run(continuation, interrupted)

    def decode(raw, metadata):
        data = json.loads(raw)["synthetic_response"]
        return e.Outcome(
            "OK", raw, json.dumps(data), 100, 50, dict(input_tokens=100, output_tokens=50)
        )

    calls = []

    def send(wire, capture):
        calls.append(digest(wire))
        return success(wire, capture)

    result = run(continuation, send, decode)
    assert (
        result["status"] == "COMPLETE" and len(calls) == 2 and result["provider_invocations"] == 3
    )
