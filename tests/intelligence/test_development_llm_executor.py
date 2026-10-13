"""Synthetic source-only bundles and injected transports. No credentials/provider calls."""

import json
from decimal import Decimal

import pytest

from archguard.benchmark.oss.models import canonical, digest, seal
from archguard.benchmark.semantic_preflight import PricingAssumption
from archguard.benchmark.unified_hybrid import UnifiedAssessment, protocol
from archguard.infrastructure import development_llm_executor as e
from archguard.infrastructure import unified_human_review as io


@pytest.fixture
def bundle(tmp_path):
    root = tmp_path / "bundle"
    root.mkdir()
    (root / "payloads").mkdir()
    rows = []
    schema = UnifiedAssessment.model_json_schema()
    for n in range(180):
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
    io.append_seal(root / "manifest.json", dict(rows=rows))
    io.append_seal(root / "protocol.json", e.protocol(protocol()))
    pricing = seal(PricingAssumption)
    (root / "pricing.json").write_text(canonical(pricing) + "\n")
    io.append_seal(root / "response-schema.json", dict(schema=schema))
    io.append_seal(root / "order.json", dict(request_ids=[r["request_id"] for r in rows]))
    io.append_seal(root / "source-bindings.json", dict(files={}))
    frozen = io.append_seal(
        root / "bundle-freeze.json",
        dict(
            files={
                p.relative_to(root).as_posix(): io.sha(p) for p in root.rglob("*") if p.is_file()
            }
        ),
    )
    approval = dict(
        stage="DEVELOPMENT_STRUCTURAL_LLM",
        logical_requests=180,
        bundle_fingerprint=frozen["fingerprint"],
        provider="openai",
        model="gpt-6-luna",
        paid_execution_approved=True,
        hard_cap_usd="2.31",
        final_calls_authorized=False,
        hybrid_training_authorized=False,
    )
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


def test_complete_and_resume_skip_accepted_without_semantic_retry(bundle):
    root, ledger, approval = bundle
    calls = []

    def transport(wire, capture):
        calls.append(digest(wire))
        return success(wire, capture)

    report = e.execute(root, ledger, approval, transport)
    assert (
        report["accepted"] == 180
        and report["provider_invocations"] == 180
        and report["status"] == "COMPLETE"
    )
    original = {p.name: p.read_bytes() for p in ledger.iterdir()}
    again = e.execute(
        root, ledger, approval, lambda *a: pytest.fail("Accepted logical IDs never repeat")
    )
    assert again == report
    assert {p.name: p.read_bytes() for p in ledger.iterdir()} == original
    frozen = io.read_seal(ledger / "normalized-assessments.json")
    assert len(frozen["assessments"]) == 180 and len(set(calls)) == 180


@pytest.mark.parametrize("kind", ["schema", "id", "technical", "timeout"])
def test_bounded_identical_payload_recovery(bundle, kind):
    root, ledger, approval = bundle
    calls = []

    def transport(wire, capture):
        calls.append(digest(wire))
        if len(calls) == 1:
            if kind == "schema":
                return e.Outcome("OK", b"synthetic invalid", "{}", 100, 50)
            if kind == "id":
                good = success(wire, capture)
                data = json.loads(good.assessment)
                data["request_id"] = "0" * 64
                return e.Outcome("OK", b"synthetic mismatch", canonical(data), 100, 50)
            return e.Outcome(
                "TIMEOUT" if kind == "timeout" else "RATE_LIMIT", b"synthetic technical error"
            )
        return success(wire, capture)

    result = e.execute(root, ledger, approval, transport)
    assert (
        result["accepted"] == 180
        and result["provider_invocations"] == 181
        and result["technical_retries"] == 1
    )
    assert calls[0] == calls[1]


@pytest.mark.parametrize("invalid", [True, False])
def test_retry_exhaustion_and_schema_shared_budget(bundle, invalid):
    root, ledger, approval = bundle
    result = e.execute(
        root,
        ledger,
        approval,
        lambda *a: (
            e.Outcome("OK", b"invalid", "{}", 100, 50)
            if invalid
            else e.Outcome("TRANSIENT", b"technical")
        ),
    )
    assert result["status"] == "RETRY_EXHAUSTED"
    assert result["provider_invocations"] == (2 if invalid else 3) and result["accepted"] == 0


def test_ambiguous_transport_stops_and_reserves_on_resume(bundle):
    root, ledger, approval = bundle
    calls = []

    def transport(*args):
        calls.append(1)
        raise RuntimeError("synthetic uncertain transport")

    result = e.execute(root, ledger, approval, transport)
    assert result["status"] == "AMBIGUOUS_TRANSPORT" and result["provider_invocations"] == 1
    assert Decimal(result["uncertain_reserved_exposure_usd"]) == seal(PricingAssumption).charge(
        32768, 2000
    )
    repeat = e.execute(
        root, ledger, approval, lambda *a: pytest.fail("Do not repeat ambiguous request")
    )
    assert repeat == result and len(calls) == 1


def test_interrupt_after_durable_intent_is_not_blindly_repeated(bundle):
    root, ledger, approval = bundle
    with pytest.raises(KeyboardInterrupt):
        e.execute(root, ledger, approval, lambda *a: (_ for _ in ()).throw(KeyboardInterrupt()))
    report = e.execute(
        root, ledger, approval, lambda *a: pytest.fail("Pending could have processed")
    )
    assert report["status"] == "AMBIGUOUS_TRANSPORT"


def test_captured_same_response_recovery_without_second_generation(bundle):
    root, ledger, approval = bundle

    def interrupted(wire, capture):
        good = success(wire, capture)
        capture(good.raw, dict(synthetic_assessment=good.assessment))
        raise RuntimeError("Synthetic interruption after capture")

    e.execute(root, ledger, approval, interrupted)

    def decoder(raw, metadata):
        return e.Outcome("OK", raw, metadata["synthetic_assessment"], 100, 50)

    calls = []

    def remaining(wire, capture):
        calls.append(1)
        return success(wire, capture)

    result = e.execute(root, ledger, approval, remaining, decoder)
    assert result["accepted"] == 180 and result["provider_invocations"] == 180 and len(calls) == 179


@pytest.mark.parametrize("cap", ["0.001", "0.0042768"])
def test_cap_reservation_and_retry_same_cap_resume(bundle, cap):
    root, ledger, approval = bundle
    approval["hard_cap_usd"] = cap
    calls = []

    def transport(*args):
        calls.append(1)
        return e.Outcome("RATE_LIMIT", b"synthetic error")

    result = e.execute(root, ledger, approval, transport)
    assert result["status"] == "PAID_CAP_REACHED" and len(calls) == (0 if cap == "0.001" else 1)
    assert (
        e.execute(root, ledger, approval, lambda *a: pytest.fail("Reserved cap exhausted"))
        == result
    )


def test_approval_required_before_transport_or_ledger(bundle):
    root, ledger, approval = bundle
    approval["paid_execution_approved"] = False
    with pytest.raises(PermissionError):
        e.execute(root, ledger, approval, lambda *a: pytest.fail("No approval"))
    assert not ledger.exists()


@pytest.mark.parametrize(
    "metadata",
    [
        "truth",
        "ground_truth",
        "expected_label",
        "positive",
        "mutation",
        "control",
        "pair_role",
        "reviewer",
        "adjudication",
        "correctness",
        "TP",
        "FP",
        "TN",
        "FN",
        "final_category",
    ],
)
def test_structural_metadata_leakage_rejected_but_source_prose_allowed(metadata):
    e.audit_payload(
        dict(
            context=dict(
                source_fragments=[dict(text="ordinary positive negative mutation control source")]
            )
        )
    )
    with pytest.raises(io.ReviewBlocked):
        e.audit_payload(dict(context={metadata: "synthetic forbidden"}))
    with pytest.raises(io.ReviewBlocked):
        e.audit_payload(dict(serialized=canonical({metadata: True})))


def test_positive_io_scope_denies_all_external_truth_and_final_paths(bundle, tmp_path):
    root, ledger, _ = bundle
    for name in (
        "final-semantic-truth.json",
        "structural-truth.json",
        "reviewer-a.json",
        "p019-truth.json",
        "p015-human-truth.json",
        "construction-intent.json",
        "correctness.json",
        "final-payload.json",
        "truth.py",
    ):
        with e.executor_scope(root, ledger), pytest.raises(PermissionError):
            e.audit_hook("open", (str(tmp_path / name), "r", 0))
    with e.executor_scope(root, ledger), pytest.raises(PermissionError):
        e.audit_hook("open", (".env.ai.local", "r", 0))
    with e.executor_scope(root, ledger), pytest.raises(PermissionError):
        e.audit_hook("socket.connect", ())
    with e.executor_scope(root, ledger):
        e.load_bundle(root)


def test_frozen_payload_drift_and_case_scope_rejected(bundle):
    root, ledger, approval = bundle
    path = next((root / "payloads").iterdir())
    path.write_text("drift")
    with pytest.raises(io.ReviewBlocked):
        e.execute(root, ledger, approval, lambda *a: pytest.fail("Drift blocks"))


def test_exact_estimator_pricing_long_boundary_and_cost_formulas():
    pricing = seal(PricingAssumption)
    assert pricing.charge(272000, 2000) == Decimal("0.0282")
    assert pricing.charge(272001, 2000) == Decimal("0.0559002")
    rows = [
        dict(input_estimate=1000, input_upper=3000),
        dict(input_estimate=300000, input_upper=400000),
    ]
    cost = e.costs(rows, pricing)
    assert cost["long_context"] == 1
    assert Decimal(cost["expected_usd"]) == pricing.charge(1000, 600) + pricing.charge(300000, 600)
    assert (
        Decimal(cost["two_full_retries_estimated_input_usd"])
        == Decimal(cost["primary_max_estimated_input_usd"]) * 3
    )
    assert cost["invoice"] is None and cost["cached_savings"] is False


def test_real_frozen_p020_requests_are_exact_unique_and_blind():
    from archguard.infrastructure import development_llm_preflight as p

    facts, config, pricing = p.scientific_gate()
    assert (
        facts["structural"] == 180
        and facts["semantic_reuse"] == 100
        and facts["evidence_records"] == 280
    )
    assert facts["final_requests"] == facts["semantic_requests"] == facts["payload_leakage"] == 0
    assert (
        facts["request_manifest_fingerprint"]
        == "31c753f44cff57fe5cfe784b47c89e77eef9a42433c7d86e9358519c54b94a95"
    )
    assert config["concurrency"] == 1 and pricing.short_context_input_cutoff == 272000


@pytest.mark.parametrize(
    "decision", ["SUPPORTED", "NOT_SUPPORTED", "INSUFFICIENT_CONTEXT", "NOT_APPLICABLE"]
)
def test_four_decisions_preserved_without_retry(bundle, decision):
    root, ledger, approval = bundle
    approval["hard_cap_usd"] = "0.00430"
    report = e.execute(root, ledger, approval, lambda w, c: success(w, c, decision))
    assert report["accepted"] == report["provider_invocations"] == 1
    outcome = io.read_seal(next(ledger.glob("*.outcome.json")))
    assert outcome["normalized"]["assessment"]["decision"] == decision


@pytest.mark.parametrize("cap", [None, "NaN", "-1", "not-a-number", True])
def test_numeric_approval_required(bundle, cap):
    root, ledger, approval = bundle
    approval["hard_cap_usd"] = cap
    with pytest.raises(PermissionError):
        e.execute(root, ledger, approval, lambda *a: pytest.fail("Invalid cap"))
    assert not ledger.exists()


def test_configuration_error_never_retried(bundle):
    root, ledger, approval = bundle
    report = e.execute(
        root,
        ledger,
        approval,
        lambda *a: e.Outcome("CONFIGURATION_ERROR", b"synthetic config error"),
    )
    assert report["provider_invocations"] == 1 and report["status"] == "CONFIGURATION_ERROR"


def test_ledger_binding_drift_blocks_resume(bundle):
    root, ledger, approval = bundle
    approval["hard_cap_usd"] = "0.00430"
    e.execute(root, ledger, approval, success)
    path = next(ledger.glob("*.outcome.json"))
    value = io.read_seal(path)
    value.pop("fingerprint")
    value["normalized"]["attempt_fingerprint"] = "0" * 64
    path.write_text(canonical(value | {"fingerprint": digest(value)}))
    with pytest.raises(io.ReviewBlocked, match="ACCEPTED_BINDING"):
        e.execute(root, ledger, approval, lambda *a: pytest.fail("Corrupt ledger"))


def test_future_adapter_reconstructs_identical_frozen_wire_without_call(monkeypatch):
    from types import SimpleNamespace

    from archguard.infrastructure import development_llm_preflight as p
    from archguard.infrastructure import semantic_positive_live as old
    from archguard.infrastructure.semantic_preflight import wire_payload

    row = io.read_seal(p.DEV / "requests/manifest.json")["rows"][0]
    wire = io.read_seal(p.DEV / "requests/payloads" / f"{row['request_id']}.json")["wire_payload"]

    class SyntheticAdapter:
        def __init__(self, settings):
            pass

        def __call__(self, request, protocol, *, capture_response):
            assert wire_payload(request, protocol.model) == wire
            return SimpleNamespace(
                status="TERMINAL_ERROR",
                raw_response=b"synthetic",
                assessment_json=None,
                input_tokens=None,
                output_tokens=None,
                provider_usage=None,
                provider_metadata={},
                error_metadata={},
                latency_seconds=0,
            )

    monkeypatch.setattr(old, "OpenAIPositiveTransport", SyntheticAdapter)
    config = e.protocol(protocol())
    assert e.OpenAITransport(config, object())(wire, lambda *a: None).status == "TERMINAL_ERROR"
