"""FINAL-only offline acquisition, immutable request bytes and closed scopes."""

import ast
import json
from decimal import Decimal
from pathlib import Path

import pytest

from archguard.benchmark.oss.models import canonical, digest, seal
from archguard.benchmark.semantic_preflight import PricingAssumption
from archguard.benchmark.unified_hybrid import UnifiedAssessment, protocol
from archguard.infrastructure import final_llm_executor as e
from archguard.infrastructure import final_llm_preflight as p
from archguard.infrastructure import unified_human_review as io


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    root = tmp_path / "bundle"
    root.mkdir()
    (root / "payloads").mkdir()
    rows = []
    schema = UnifiedAssessment.model_json_schema()
    for n in range(300):
        rid = digest(("synthetic-request", n))
        eid = digest(("synthetic-execution", n))
        context = dict(
            source_fragments=[dict(text="Domain positive negative mutation control prose.")]
        )
        wire = dict(
            model="gpt-6-luna",
            store=False,
            max_output_tokens=2000,
            input=[
                dict(role="system", content="Synthetic architecture question."),
                dict(
                    role="user",
                    content=canonical(
                        dict(
                            task=dict(request_id=rid, target_rule_id="ARCH001"),
                            untrusted_context=context,
                        )
                    ),
                ),
            ],
            text=dict(
                format=dict(
                    type="json_schema", strict=True, schema=schema, name="architecture_assessment"
                )
            ),
        )
        estimate, upper = e.visible_tokens(wire)
        io.append_seal(
            root / "payloads" / f"{rid}.json",
            dict(
                request_id=rid,
                execution_id=eid,
                context=context,
                context_manifest={},
                wire_payload=wire,
            ),
        )
        rows.append(
            dict(
                request_id=rid,
                execution_id=eid,
                target_rule_id="ARCH001",
                request_fingerprint=digest(wire),
                context_fingerprint=digest(context),
                input_estimate=estimate,
                input_upper=upper,
            )
        )
    rows.sort(key=lambda r: digest(r["execution_id"]))
    contexts = io.append_seal(root / "contexts.json", dict(rows=[]))
    manifest = io.append_seal(
        root / "manifest.json",
        dict(stream="FINAL", rows=rows, context_manifest_fingerprint=contexts["fingerprint"]),
    )
    monkeypatch.setattr(e, "REQUEST_FP", manifest["fingerprint"])
    monkeypatch.setattr(e, "CONTEXT_FP", contexts["fingerprint"])
    io.append_seal(root / "protocol.json", e.protocol(protocol()))
    pricing = seal(PricingAssumption)
    (root / "pricing.json").write_text(canonical(pricing) + "\n")
    io.append_seal(root / "response-schema.json", dict(schema=schema))
    io.append_seal(root / "order.json", dict(request_ids=[r["request_id"] for r in rows]))
    io.append_seal(root / "source-bindings.json", dict(files={}))
    io.append_seal(
        root / "model-lock.json",
        dict(selected_registry_fingerprint=e.REGISTRY_FP, final_model_fingerprint=e.MODEL_FP),
    )
    io.append_seal(root / "cost-preflight.json", e.costs(rows, pricing))
    io.append_seal(
        root / "approval-contract.json",
        dict(
            required_fields=sorted(e.APPROVAL_FIELDS),
            stage="FINAL_300_LLM",
            paid_execution_approved=False,
            approved_cap_usd=None,
        ),
    )
    io.append_seal(
        root / "bundle-freeze.json",
        dict(
            files={
                p.relative_to(root).as_posix(): io.sha(p) for p in root.rglob("*") if p.is_file()
            }
        ),
    )
    approval = e.approval_bindings(root) | dict(paid_execution_approved=True, hard_cap_usd="3.85")
    return root, tmp_path / "ledger", approval


def success(wire, capture, decision="NOT_SUPPORTED"):
    task = json.loads(wire["input"][1]["content"])["task"]
    assessment = dict(
        request_id=task["request_id"],
        target_rule_id=task["target_rule_id"],
        decision=decision,
        subject_node_ids=["synthetic-node"],
        short_reason="Synthetic only.",
        evidence_refs=[],
        limitations=[],
    )
    raw = (canonical(dict(synthetic_response=assessment)) + "\n").encode()
    return e.Outcome(
        "OK", raw, canonical(assessment), 100, 50, dict(input_tokens=100, output_tokens=50)
    )


def run(bundle, transport):
    root, ledger, approval = bundle
    with e.final_scope(root, ledger):
        return e.execute(root, ledger, approval, transport)


def test_300_success_resume_exactly_once_and_immutable_attempts(bundle):
    calls = []

    def send(wire, capture):
        calls.append(digest(wire))
        return success(wire, capture)

    result = run(bundle, send)
    assert result["status"] == "COMPLETE" and result["accepted"] == 300 and len(calls) == 300
    before = {f.name: io.sha(f) for f in bundle[1].iterdir() if f.name != "run.lock"}
    result = run(bundle, lambda *a: pytest.fail("accepted must not repeat"))
    assert result["accepted_duplicates"] == 0 and result["provider_invocations"] == 300
    assert before == {f.name: io.sha(f) for f in bundle[1].iterdir() if f.name != "run.lock"}


@pytest.mark.parametrize("failure", ["TIMEOUT", "CONNECTION", "RATE_LIMIT", "TRANSIENT"])
def test_technical_retries_maximum_three_and_exhaustion(bundle, failure):
    calls = []

    def send(wire, capture):
        calls.append(digest(wire))
        return e.Outcome(failure, b"synthetic", input_tokens=100, output_tokens=0)

    result = run(bundle, send)
    assert result["status"] == "RETRY_EXHAUSTED" and len(calls) == 3
    assert len(set(calls)) == 1 and result["accepted"] == 0


@pytest.mark.parametrize("kind", ["schema", "ID"])
def test_original_p020_terminal_invalid_policy_not_development_amendment(bundle, kind):
    calls = []

    def send(wire, capture):
        calls.append(1)
        out = success(wire, capture)
        body = json.loads(out.assessment)
        if kind == "schema":
            body["decision"] = "invented"
        else:
            body["request_id"] = "f" * 64
        return e.Outcome("OK", out.raw, canonical(body), 100, 50)

    result = run(bundle, send)
    assert result["status"] == ("SCHEMA_INVALID" if kind == "schema" else "REQUEST_ID_MISMATCH")
    assert len(calls) == 1 and result["accepted"] == 0


def test_ambiguous_intent_retains_exposure_and_never_resends(bundle):
    def send(*args):
        raise RuntimeError("ambiguous")

    first = run(bundle, send)
    second = run(bundle, lambda *args: pytest.fail("ambiguous must not repeat"))
    assert first["status"] == second["status"] == "AMBIGUOUS_TRANSPORT"
    assert first["estimated_or_reserved_usd"] == second["estimated_or_reserved_usd"] == "0.0042768"
    assert second["provider_invocations"] == 1


@pytest.mark.parametrize("cap", ["0.004", False, "NaN", "Infinity", "-1", None])
def test_cap_refusal_or_invalid_cap_precedes_transport(bundle, cap):
    root, ledger, approval = bundle
    approval["hard_cap_usd"] = cap
    with e.final_scope(root, ledger):
        if cap == "0.004":
            result = e.execute(root, ledger, approval, lambda *args: pytest.fail("cap"))
            assert result["status"] == "PAID_CAP_REACHED" and result["provider_invocations"] == 0
        else:
            with pytest.raises(PermissionError):
                e.execute(root, ledger, approval, lambda *args: pytest.fail("cap"))


@pytest.mark.parametrize("field", sorted(e.APPROVAL_FIELDS - {"hard_cap_usd"}))
def test_explicit_final_approval_binds_every_scope_and_freeze(bundle, field):
    root, ledger, approval = bundle
    approval[field] = "wrong"
    with e.final_scope(root, ledger), pytest.raises(PermissionError):
        e.execute(root, ledger, approval, lambda *args: pytest.fail("approval"))
    assert not ledger.exists()


@pytest.mark.parametrize(
    "metadata",
    [
        "ground_truth",
        "truth_label",
        "expected_label",
        "mutation",
        "control",
        "pair_role",
        "reviewer",
        "adjudication",
        "correctness",
        "tp",
        "fp",
        "tn",
        "fn",
        "hybrid_prediction",
        "selected_model_correct",
        "validation_metrics",
    ],
)
def test_context_aware_metadata_leakage_and_source_prose(metadata):
    prose = {
        "context": {
            "source_fragments": [
                {"text": "positive negative mutation control ordinary business source"}
            ]
        }
    }
    e.audit_payload(prose)
    for bad in (
        {"context": {metadata: 1}},
        {"context": {"architecture_contract": {metadata: 1}}},
        {"serialized": canonical({metadata: 1})},
    ):
        with pytest.raises(io.ReviewBlocked):
            e.audit_payload(bad)


@pytest.mark.parametrize(
    "name",
    [
        "final/structural-truth.json",
        "human-intake/reviewer-A.json",
        "human-intake/reviewer-B.json",
        "coordinator/construction-intent.json",
        "development/truth.json",
        "p023-hybrid-models-v1/matrices/train-labels.json",
    ],
)
def test_final_executor_and_preparation_deny_truth_before_provider(bundle, name):
    root, ledger, _ = bundle
    with e.final_scope(root, ledger), pytest.raises(PermissionError):
        e.core.audit_hook("open", (str(io.PRIVATE / name), "r", 0))
    with p.offline_scope(), pytest.raises(PermissionError):
        p.prep_hook("open", (str(io.PRIVATE / name), "r", 0))


def test_network_secret_symlink_and_outside_truth_rejected(bundle, tmp_path):
    root, ledger, _ = bundle
    for path in (Path(".env.ai.local"), tmp_path / "truth.py"):
        with e.final_scope(root, ledger), pytest.raises(PermissionError):
            e.core.audit_hook("open", (str(path), "r", 0))
    with e.final_scope(root, ledger), pytest.raises(PermissionError):
        e.core.audit_hook("socket.connect", ())
    outside = tmp_path / "outside"
    outside.mkdir()
    link = root / "payloads/hidden.json"
    link.symlink_to(outside / "truth.json")
    with e.final_scope(root, ledger), pytest.raises((ValueError, io.ReviewBlocked)):
        e.load_bundle(root)


def test_request_byte_drift_and_model_lock_drift_block(bundle):
    root, ledger, approval = bundle
    path = next((root / "payloads").iterdir())
    path.write_bytes(path.read_bytes() + b" ")
    with e.final_scope(root, ledger), pytest.raises(io.ReviewBlocked):
        e.execute(root, ledger, approval, lambda *args: pytest.fail("bytes changed"))


def test_recovery_captured_response_offline_without_second_invocation(bundle):
    root, ledger, approval = bundle

    def crash(wire, capture):
        out = success(wire, capture)
        capture(out.raw, {"input_tokens": 100, "output_tokens": 50})
        raise RuntimeError("after durable capture")

    first = run(bundle, crash)
    assert first["status"] == "AMBIGUOUS_TRANSPORT"

    def decode(raw, metadata):
        body = json.loads(raw)["synthetic_response"]
        return e.Outcome("OK", raw, canonical(body), 100, 50)

    with e.final_scope(root, ledger):
        result = e.execute(root, ledger, approval, success, decode)
    assert result["accepted"] == result["provider_invocations"] == 300


def test_cost_decimal_long_pricing_retry_ceiling_and_rounding():
    pricing = seal(PricingAssumption)
    rows = [
        dict(input_estimate=272000, input_upper=272000),
        dict(input_estimate=272001, input_upper=300000),
    ]
    result = e.costs(rows, pricing)
    assert result["long_context"] == 1
    assert Decimal(result["expected_usd"]) == pricing.charge(272000, 600) + pricing.charge(
        272001, 600
    )
    assert Decimal(result["conservative_usd"]) == pricing.charge(272000, 2000) + pricing.charge(
        300000, 2000
    )
    primary = pricing.charge(32768, 2000) * 2
    assert Decimal(result["configured_primary_ceiling_usd"]) == primary
    assert Decimal(result["configured_one_full_retry_usd"]) == primary * 2
    assert Decimal(result["configured_two_full_retries_usd"]) == primary * 3
    assert Decimal(result["recommended_cap_usd"]) >= primary * 3


def test_live_path_has_no_calibration_prediction_or_evaluator_calls():
    tree = ast.parse(Path(e.__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert not any(
                s in (node.module or "")
                for s in ("calibration", "hybrid_development", "evaluation")
            )
        if isinstance(node, ast.Call):
            name = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else node.func.attr
                if isinstance(node.func, ast.Attribute)
                else ""
            )
            assert name not in {
                "fit_candidate",
                "fit_coefficients",
                "fitted_candidates",
                "predict",
                "select_candidate",
                "validation_selection",
                "transform",
            }


def test_p023_frozen_models_and_protocol_still_locked():
    with p.offline_scope():
        lock = p.model_gate()
    assert lock["selected"]["A4"]["selected_family"] == "H0"
    assert all(lock["selected"][k]["selected_family"] == "H2" for k in ("A5", "A6", "A7"))
    assert lock["selected"]["A7"]["threshold"] == 0.75


def test_actual_p020_final_300_exact_freeze_and_cost():
    with p.offline_scope():
        manifest, _, pricing, facts = p.source_gate()
    result = e.costs(manifest["rows"], pricing)
    assert facts["cases"] == 300 and facts["development_requests"] == 0
    assert result["input_tokens"] == 867517 and result["expected_usd"] == "0.1767517"
    assert result["conservative_usd"] == "0.6101463"
    assert (
        result["configured_two_full_retries_usd"] == "3.8491200"
        and result["recommended_cap_usd"] == "3.85"
    )


@pytest.mark.parametrize(
    "decision", ["SUPPORTED", "NOT_SUPPORTED", "INSUFFICIENT_CONTEXT", "NOT_APPLICABLE"]
)
def test_final_decisions_preserved_and_configuration_errors_terminal(bundle, decision):
    calls = []

    def send(wire, capture):
        calls.append(digest(wire))
        if len(calls) == 1:
            return success(wire, capture, decision)
        return e.Outcome("CONFIGURATION_ERROR", b"synthetic auth/model/billing failure")

    result = run(bundle, send)
    assert result["accepted"] == 1 and result["status"] == "CONFIGURATION_ERROR"
    assert len(calls) == 2 and len(set(calls)) == 2
    outcomes = [io.read_seal(path) for path in bundle[1].glob("*.outcome.json")]
    assert (
        next(v for v in outcomes if v["state"] == "ACCEPTED")["normalized"]["assessment"][
            "decision"
        ]
        == decision
    )


def test_bundle_rejects_extra_validation_metadata_even_when_resealed(bundle):
    root, ledger, _ = bundle
    path = root / "model-lock.json"
    value = io.read_seal(path)
    value.pop("fingerprint")
    value["validation_metrics"] = {"F1": 1.0}
    path.unlink()
    io.append_seal(path, value)
    frozen = io.read_seal(root / "bundle-freeze.json")
    frozen.pop("fingerprint")
    frozen["files"]["model-lock.json"] = io.sha(path)
    (root / "bundle-freeze.json").unlink()
    io.append_seal(root / "bundle-freeze.json", frozen)
    with e.final_scope(root, ledger), pytest.raises(io.ReviewBlocked):
        e.load_bundle(root)
