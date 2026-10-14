"""Synthetic-only segment C: two locked failures, no-repeat, blind cumulative execution."""

import ast
import json
from decimal import Decimal
from pathlib import Path

import pytest

from archguard.benchmark.oss.models import digest
from archguard.infrastructure import final_llm_completion as f
from archguard.infrastructure import final_llm_continuation as c
from archguard.infrastructure import final_llm_executor as e
from archguard.infrastructure import unified_human_review as io
from tests.intelligence import test_final_llm as base
from tests.intelligence import test_final_llm_continuation as previous

bundle = base.bundle
continuation = previous.continuation
prepared = previous.prepared
success = base.success
REAL_LOAD = f.load


def paths(monkeypatch, tmp_path):
    for name, value in {
        "ROOT": tmp_path / "completion-plan",
        "LEDGER": tmp_path / "completion-ledger",
        "APPROVAL": tmp_path / "completion-approval",
        "FREEZE": tmp_path / "completion-freeze",
        "COMPOSITE": tmp_path / "completion-composite",
        "PUBLIC": tmp_path / "completion-public.json",
        "HANDOFF": tmp_path / "completion-handoff.json",
    }.items():
        monkeypatch.setattr(f, name, value)
    monkeypatch.setattr(
        f,
        "READS",
        (
            f.ROOT,
            f.APPROVAL,
            f.LEDGER,
            e.ROOT,
            e.LEDGER,
            c.PARTIAL,
            c.PARTIAL_PUBLIC,
            c.ROOT,
            c.APPROVAL,
            c.LEDGER,
            c.FREEZE,
            c.COMPOSITE,
            c.PUBLIC,
            io.BASE / "p024-live1-verification-v1.json",
        ),
    )
    monkeypatch.setattr(f, "git_gate", lambda **_: None)


@pytest.fixture
def execution(bundle, monkeypatch, tmp_path):
    root, _, _ = bundle
    monkeypatch.setattr(e, "ROOT", root)
    manifest, config, pricing = e.load_bundle(root)
    paths(monkeypatch, tmp_path)
    io.append_seal(f.ROOT / "plan-freeze.json", dict(files={}))
    old = dict(
        accepted={r["request_id"]: {} for r in manifest["rows"][:74] + manifest["rows"][75:244]},
        attempts={r["request_id"]: [{}] for r in manifest["rows"][:245]},
        exposure=Decimal("0.1226491"),
    )
    suffix = dict(rows=manifest["rows"][245:248])
    proto = dict(allowlist_fingerprint=digest("synthetic-55"))
    approval = dict(plan_fingerprint=digest("synthetic-plan"))
    monkeypatch.setattr(f, "load", lambda _: (suffix, config, pricing, old, proto))
    return manifest, suffix, config, pricing, old, proto, approval


def run(execution, transport, decoder=None):
    *_, approval = execution
    with c.scope(f.READS, (f.LEDGER,)):
        return f.execute(approval, transport, decoder)


def test_original_order_semantics_once_and_resume(execution):
    manifest, suffix, config, pricing, old, proto, approval = execution
    seen = []

    def transport(wire, capture):
        task = json.loads(wire["input"][1]["content"])["task"]
        seen.append(task["request_id"])
        return success(wire, capture, decision="INSUFFICIENT_CONTEXT")

    result = run(execution, transport)
    assert result["status"] == "COMPLETE" and result["accepted"] == 3
    assert seen == [r["request_id"] for r in suffix["rows"]]
    before = {p.name: io.sha(p) for p in f.LEDGER.iterdir()}
    result = run(execution, lambda *_: pytest.fail("accepted resend"))
    assert result["provider_invocations"] == 3
    assert before == {p.name: io.sha(p) for p in f.LEDGER.iterdir()}
    assert result["estimated_or_reserved_usd"] == str(old["exposure"] + 3 * pricing.charge(100, 50))
    assert result["historical_uncertain_reserved_usd"] == "0.0042768"


@pytest.mark.parametrize("position", [0, 73, 74, 75, 243, 244])
def test_prior_accepted_and_both_failures_denied_before_transport(execution, position):
    full, suffix, config, pricing, old, _, approval = execution
    f.initialize(approval)
    state = f.segment_state(suffix, config, pricing)
    with pytest.raises(PermissionError):
        f.guard_request(full["rows"][position]["request_id"], suffix, old, state)


@pytest.mark.parametrize("kind", ["schema", "id", "authentication", "billing", "model-access"])
def test_new_terminal_failure_stops_without_skipping_or_retry(execution, kind):
    calls = []

    def transport(wire, capture):
        calls.append(1)
        sample = success(wire, capture)
        if kind == "schema":
            return e.Outcome("OK", b"invalid", "{}", 100, 50, {})
        if kind == "id":
            assessment = json.loads(sample.assessment)
            assessment["request_id"] = digest("synthetic-wrong-id")
            return e.Outcome("OK", sample.raw, json.dumps(assessment), 100, 50, {})
        return e.Outcome(kind.upper(), b"synthetic terminal", None, 100, 50, {})

    result = run(execution, transport)
    assert result["status"] in {
        "SCHEMA_INVALID",
        "REQUEST_ID_MISMATCH",
        "TERMINAL_ERROR",
    }
    assert result["accepted"] == 0 and len(calls) == 1
    again = run(execution, lambda *_: pytest.fail("terminal rerun"))
    assert again["provider_invocations"] == 1


def test_new_ambiguity_stops_no_capture_no_resend(execution):
    calls = []

    def uncertain(*_):
        calls.append(1)
        raise RuntimeError("synthetic uncertain transport")

    result = run(execution, uncertain)
    assert result["status"] == "AMBIGUOUS_TRANSPORT" and len(calls) == 1
    assert result["estimated_or_reserved_usd"] == "0.1269259"
    assert (
        run(execution, lambda *_: pytest.fail("ambiguous resend"))["status"]
        == "AMBIGUOUS_TRANSPORT"
    )


def test_cap_is_total_not_reset_and_reservation_kept(execution):
    old = execution[4]
    old["exposure"] = f.CAP - f.RESERVE / 2
    result = run(execution, lambda *_: pytest.fail("beyond-cap call"))
    assert result["status"] == "PAID_CAP_REACHED" and result["provider_invocations"] == 0


@pytest.mark.parametrize("status", ["TIMEOUT", "CONNECTION", "RATE_LIMIT", "TRANSIENT"])
def test_only_safe_technical_retries_identical_maximum_three(execution, status):
    payloads = []

    def transport(wire, capture):
        payloads.append(digest(wire))
        return e.Outcome(status, b"synthetic safe failure", None, None, None, {})

    result = run(execution, transport)
    assert result["status"] == "RETRY_EXHAUSTED" and len(payloads) == 3 and len(set(payloads)) == 1
    assert result["estimated_or_reserved_usd"] == str(Decimal("0.1226491") + 3 * f.RESERVE)


def test_captured_response_offline_decode_without_resending(execution):
    def interrupted(wire, capture):
        sample = success(wire, None)
        capture(sample.raw, dict(synthetic=True))
        raise RuntimeError("synthetic interruption after capture")

    assert run(execution, interrupted)["status"] == "AMBIGUOUS_TRANSPORT"

    def decode(raw, metadata):
        return e.Outcome(
            "OK",
            raw,
            json.dumps(json.loads(raw)["synthetic_response"]),
            100,
            50,
            dict(input_tokens=100, output_tokens=50, total_tokens=150),
        )

    result = run(execution, success, decode)
    assert result["status"] == "COMPLETE" and result["provider_invocations"] == 3


def test_durable_intent_precedes_transport(execution, monkeypatch):
    synced = []
    monkeypatch.setattr(f.os, "fsync", lambda fd: synced.append(fd))

    def transport(wire, capture):
        assert len(synced) >= 2
        assert len(list(f.LEDGER.glob("attempt-*.json"))) >= 1
        return success(wire, capture)

    run(execution, transport)
    assert len(synced) == 6


def test_readonly_history_truth_and_hybrid_boundaries(execution, tmp_path):
    old = tmp_path / "old-history"
    immutable = io.append_seal(old / "receipt.json", dict(version="synthetic"))
    with c.scope((*f.READS, old), (f.LEDGER,)):
        with pytest.raises(PermissionError):
            (old / "receipt.json").write_bytes(b"mutation")
        for path in [
            io.FINAL / "truth.json",
            io.PRIVATE / "human-intake/accepted/A/canonical-response.json",
            io.PRIVATE / "p023-hybrid-models-v1/train.json",
            Path(".env.ai.local"),
            tmp_path / "intent.json",
        ]:
            with pytest.raises(PermissionError):
                c.audit_hook("open", (str(path), "r", 0))
        with pytest.raises(PermissionError):
            e.core.audit_hook("socket.connect", ())
    assert io.read_seal(old / "receipt.json") == immutable
    for source in f.SOURCES[:2]:
        tree = ast.parse(Path(source).read_text())
        assert not any(
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr in {"fit", "predict", "evaluate", "calibrate", "select_candidate"}
            for n in ast.walk(tree)
        )


@pytest.fixture
def ready(prepared, monkeypatch, tmp_path):
    approval, manifest, _, _ = prepared
    suffix, config, pricing, a, protocol = c.initialize(approval)
    exposure = a["exposure"]
    for pos, row in enumerate(suffix["rows"][:170]):
        prefix = f"attempt-{row['request_id']}-01"
        intent = io.append_seal(
            c.LEDGER / f"{prefix}.json",
            dict(
                prefix=prefix,
                request_id=row["request_id"],
                execution_id=row["execution_id"],
                attempt=1,
                request_fingerprint=row["request_fingerprint"],
                reserved_usd=str(f.RESERVE),
                provider="openai",
                model="gpt-6-luna",
                processing="STANDARD",
                timestamp=f"2026-01-02T00:00:{pos:03}+00:00",
                recovery_of=None,
                segment="p024-final-live-continuation-v1",
                global_logical_state="NEVER_EXECUTED",
                total_stage_reserved_at_intent_usd=str(exposure + f.RESERVE),
                partial_freeze_fingerprint=protocol["partial_freeze_fingerprint"],
            ),
        )
        if pos == 169:
            break
        inp = 484237 // 169 + (pos < 484237 % 169)
        out = 67116 // 169 + (pos < 67116 % 169)
        sample = success(
            io.read_seal(e.ROOT / "payloads" / f"{row['request_id']}.json")["wire_payload"], None
        )
        result = e.Outcome(
            "OK",
            sample.raw,
            sample.assessment,
            inp,
            out,
            dict(
                input_tokens=inp,
                output_tokens=out,
                total_tokens=inp + out,
                input_tokens_details=dict(cached_tokens=0),
            ),
        )
        e.store_outcome(c.LEDGER, intent, row, result, pricing, config)
        exposure += pricing.charge(inp, out)
    public = c.freeze(approval)
    monkeypatch.setattr(io, "BASE", tmp_path / "public")
    quality = io.append_seal(
        io.BASE / "p024-live1-verification-v1.json",
        dict(acquisition_fingerprint=public["fingerprint"]),
    )
    monkeypatch.setattr(f, "B_PUBLIC_FP", public["fingerprint"])
    monkeypatch.setattr(f, "B_QUALITY_FP", quality["fingerprint"])
    paths(monkeypatch, tmp_path)
    f.prepare()
    approval = f.approval_bindings()
    return approval, manifest


def test_exact_55_proof_both_immutable_histories_and_approval_gates(ready):
    approval, manifest = ready
    before = {
        str(p): io.sha(p)
        for root in (e.LEDGER, c.PARTIAL, c.LEDGER, c.FREEZE, c.COMPOSITE)
        for p in root.rglob("*")
        if p.is_file()
    }
    suffix, config, pricing, old, proto = f.load(approval)
    assert suffix["rows"] == manifest["rows"][245:] and len(suffix["rows"]) == 55
    assert not {r["request_id"] for r in suffix["rows"]} & set(old["attempts"])
    assert (
        old["exposure"] == Decimal("0.1226491")
        and proto["maximum_total_exposure_usd"] == "0.8283211"
    )
    for field in (
        "paid_execution_approved",
        "ambiguous_retry_authorized",
        "request_id_mismatch_retry_authorized",
        "hard_cap_usd_total_stage",
        "final_evaluation_authorized",
        "new_logical_requests_authorized",
        "model",
        "hybrid_retraining_authorized",
        "security_authorized",
    ):
        with pytest.raises(PermissionError):
            f.load(approval | {field: "unauthorized"})
    assert before == {name: io.sha(Path(name)) for name in before}
    with c.scope(f.READS, (f.LEDGER,)):
        for root in (e.LEDGER, c.LEDGER, c.PARTIAL, c.FREEZE, c.COMPOSITE):
            with pytest.raises(PermissionError):
                next(root.glob("*.json")).write_bytes(b"mutation")
    assert config["schema_id_recovery_max"] == 0 and config["invalid_response_amendment"] is None
    for name in ("mismatch-binding.json", "ambiguity-binding.json"):
        binding = io.read_seal(f.ROOT / name)
        assert binding["semantic_decision"] is None and binding["accepted_assessment"] is None
        assert not binding["retry_allowed"] and not binding["provider_replacement_allowed"]


@pytest.mark.parametrize("complete", [False, True])
def test_composite_298_plus_two_nonsemantic_missing_and_handoff_twice(ready, complete):
    approval, manifest = ready
    suffix, config, pricing, old, protocol = f.initialize(approval)
    exposure = old["exposure"]
    for row in suffix["rows"] if complete else suffix["rows"][:1]:
        prefix = f"attempt-{row['request_id']}-01"
        intent = io.append_seal(
            f.LEDGER / f"{prefix}.json",
            dict(
                prefix=prefix,
                request_id=row["request_id"],
                execution_id=row["execution_id"],
                attempt=1,
                request_fingerprint=row["request_fingerprint"],
                reserved_usd=str(f.RESERVE),
                provider="openai",
                model="gpt-6-luna",
                processing="STANDARD",
                timestamp="2026-01-03T00:00:00+00:00",
                recovery_of=None,
                segment="p024-final-live-completion-v1",
                global_logical_state="NEVER_EXECUTED",
                total_stage_reserved_at_intent_usd=str(exposure + f.RESERVE),
                segment_c_plan_fingerprint=approval["plan_fingerprint"],
                segment_c_approval_fingerprint=digest(approval),
                allowlist_fingerprint=protocol["allowlist_fingerprint"],
                original_request_manifest_fingerprint=e.REQUEST_FP,
            ),
        )
        wire = io.read_seal(e.ROOT / "payloads" / f"{row['request_id']}.json")["wire_payload"]
        sample = success(wire, None)
        outcome = (
            e.Outcome(
                "OK",
                sample.raw,
                sample.assessment,
                100,
                50,
                dict(
                    input_tokens=100,
                    output_tokens=50,
                    total_tokens=150,
                    input_tokens_details=dict(cached_tokens=0),
                ),
            )
            if complete
            else e.Outcome("OK", b"bad schema", "{}", 100, 50, {})
        )
        e.store_outcome(f.LEDGER, intent, row, outcome, pricing, config)
        exposure += pricing.charge(100, 50)
    before = {
        str(p): io.sha(p)
        for root in (e.LEDGER, c.LEDGER, c.PARTIAL, c.FREEZE, c.COMPOSITE)
        for p in root.rglob("*")
        if p.is_file()
    }
    first = f.freeze(approval)
    assert first == f.freeze(approval)
    assert first["p025_acquisition_readiness"] is complete
    handoff = io.read_seal(f.HANDOFF)
    assert handoff["ready"] is complete and handoff["primary_benchmark_must_remain_300"]
    statuses = io.read_seal(f.COMPOSITE / "technical-status.json")["rows"]
    assert len(statuses) == 300
    missing = [r for r in statuses if r["llm_technical_missing"]]
    assert all("semantic_decision" not in r for r in missing)
    assert first["total_accepted"] == (298 if complete else 243)
    if complete:
        assert len(missing) == 2 and first["unexecuted"] == 0 and first["technical_missing"] == 2
        assert (
            first["active_unresolved_execution_stops"] == 0
            and first["historical_ambiguous_events"] == 1
        )
        assert sum(first["decisions"].values()) == 298
    assert before == {name: io.sha(Path(name)) for name in before}
    assert (
        first["total_exposure_usd"] == str(exposure)
        and first["historical_uncertain_reserved_usd"] == "0.0042768"
    )
    for root in (f.ROOT, f.FREEZE, f.COMPOSITE):
        for path in root.glob("*.json"):
            assert '"timestamp"' not in path.read_text() and '"frozen_at"' not in path.read_text()


@pytest.mark.parametrize("segment", ["a", "b"])
def test_prior_ledger_drift_blocks_completion(ready, segment):
    approval, _ = ready
    root = e.LEDGER if segment == "a" else c.LEDGER
    (root / "unregistered.json").write_text("{}")
    with pytest.raises(io.ReviewBlocked):
        f.load(approval)


def test_handoff_cannot_be_ready_for_inexact_accounting():
    statuses = [dict(llm_evidence_status="ACCEPTED") for _ in range(298)] + [
        dict(llm_evidence_status="TERMINAL_INVALID_REQUEST_ID_MISMATCH"),
        dict(llm_evidence_status="AMBIGUOUS_TRANSPORT_NO_CAPTURE"),
    ]
    new = dict(
        accepted={str(i): {} for i in range(55)},
        attempts={str(i): [{}] for i in range(55)},
        ambiguous=[],
        results=[dict(state="ACCEPTED") for _ in range(55)],
    )
    assert f.readiness(new, statuses)
    assert not f.readiness(new, statuses[:-1])
    assert not f.readiness(new | dict(accepted={}), statuses)
    assert not f.readiness(new | dict(ambiguous=["synthetic-pending"]), statuses)
    assert not f.readiness(new | dict(results=[dict(state="SCHEMA_INVALID")]), statuses)
