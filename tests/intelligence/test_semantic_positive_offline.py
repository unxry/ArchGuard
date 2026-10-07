"""Synthetic source-only P016 contracts; all ledgers stay in pytest temporary paths."""

import hashlib
import json
import socket
from decimal import Decimal

import pytest

from archguard.architecture.intelligence.models import ContextSelectionConfig
from archguard.benchmark.oss.models import canonical, digest, seal
from archguard.benchmark.semantic_holdout import (
    BlindedPacket,
    CaseRecord,
    HoldoutSample,
    SourceEvidence,
)
from archguard.benchmark.semantic_positive_experiment import (
    STRATEGIES,
    PositiveAssessment,
    PositiveProtocol,
    analysis_plan,
    ordered_product,
    preflight_cost,
    prompt_contract,
    token_estimate,
)
from archguard.benchmark.semantic_preflight import PricingAssumption
from archguard.infrastructure.semantic_positive_offline import (
    audit_metadata,
    capability_path,
    freeze_execution_bundle,
    prepare_material,
    verify_execution_bundle,
)


@pytest.fixture(scope="module")
def source_inputs(tmp_path_factory):
    root = tmp_path_factory.mktemp("p016-synthetic-sources")
    cohort, sources = root / "cohort", root / "sources"
    cohort.mkdir()
    (sources / "packets").mkdir(parents=True)
    cases = []
    for i in range(100):
        java = i < 50
        language = "JAVA" if java else "TYPESCRIPT"
        ext = "java" if java else "ts"
        code = {
            f"Target.{ext}": (
                "public class Target { public int run() { return new Helper().value(); } }"
            )
            if java
            else (
                'import {Helper} from "./Helper"; export class Target { '
                "run(): number { return new Helper().value(); } }"
            ),
            f"Helper.{ext}": "public class Helper { public int value() { return 1; } }"
            if java
            else "export class Helper { value(): number { return 1; } }",
            f"Other.{ext}": "public class Other { public int positive() { return 2; } }"
            if java
            else "export class Other { positive(): number { return 2; } }",
        }
        blinded = f"synthetic-packet-{i}"
        packet = seal(
            BlindedPacket,
            blinded_id=blinded,
            rule_id=f"ARCH20{i % 5 + 1}",
            language=language,
            project_alias=f"synthetic-project-{i}",
            target_path=f"Target.{ext}",
            target_component="Target",
            architecture_contract="Target delegates domain calculations to Helper.",
            evidence=tuple(
                SourceEvidence(
                    evidence_id=f"SRC{n}",
                    path=name,
                    text=text,
                    sha256=hashlib.sha256(text.encode()).hexdigest(),
                )
                for n, (name, text) in enumerate(sorted(code.items()))
            ),
        )
        (sources / "packets" / (blinded + ".json")).write_text(canonical(packet) + "\n")
        workspace = sources / "sources" / blinded
        workspace.mkdir(parents=True)
        for name, text in code.items():
            (workspace / name).write_text(text)
        cases.append(
            CaseRecord(
                case_id=f"synthetic-case-{i}",
                blinded_id=blinded,
                rule_id=packet.rule_id,
                language=language,
                project_alias=packet.project_alias,
                technical_status="VALID",
                packet_fingerprint=packet.fingerprint,
                validation_fingerprint="a" * 64,
                context_diagnostics_fingerprint="b" * 64,
            )
        )
    sample = seal(HoldoutSample, cases=tuple(cases))
    (cohort / "sample-v1.json").write_text(canonical(sample) + "\n")
    protocol = seal(
        PositiveProtocol,
        sample_fingerprint=sample.fingerprint,
        source_freeze_fingerprint="c" * 64,
        truth_fingerprint="d" * 64,
        truth_freeze_fingerprint="e" * 64,
        stage_a_commit="f" * 40,
        strategies=tuple(
            ContextSelectionConfig(
                strategy=s, include_spec=False, include_discovery=False, include_metrics=False
            )
            for s in STRATEGIES
        ),
        prompt_schema_fingerprint=digest(prompt_contract()),
        analysis_plan_fingerprint=digest(analysis_plan()),
    )
    return cohort, sources, protocol


@pytest.fixture(scope="module")
def material(source_inputs):
    cohort, sources, protocol = source_inputs
    files, rows, mapping = prepare_material(protocol, cohort=cohort, sources=sources)
    return protocol, files, rows, mapping


def test_exact_product_context_request_identity_blindness(material):
    protocol, files, rows, mapping = material
    assert len(rows) == len({r.request_id for r in rows}) == 300
    assert len(mapping) == len(set(mapping.values())) == 100
    assert all(sum(r.strategy == s for r in rows) == 100 for s in STRATEGIES)
    assert len([name for name in files if name.startswith("requests/")]) == 300
    assert all(
        r.context_chars <= 20000 and r.conservative_input_upper <= 32768 and r.source_chars > 0
        for r in rows
    )
    for row in rows:
        artifact = files["requests/" + row.request_id + ".json"]
        request = artifact["structured_request"]
        assert request.task["case_id"] == row.execution_case_id
        assert request.task["request_id"] == row.request_id
        assert request.task["candidate_rule_id"] == row.target_rule
        assert request.response_schema == PositiveAssessment.model_json_schema()
        assert digest(request) == row.request_fingerprint
        assert digest(request.untrusted_context) == row.context_fingerprint
        audit_metadata(json.loads(canonical(artifact)))
        assert not any(case in canonical(artifact) for case in mapping)
    assert protocol.paid_execution_approved is False


def test_deterministic_regeneration(source_inputs, material, monkeypatch):
    monkeypatch.setattr(socket, "socket", lambda *a, **k: pytest.fail("network forbidden"))
    cohort, sources, protocol = source_inputs
    actual, rows, mapping = prepare_material(protocol, cohort=cohort, sources=sources)
    assert {name: digest(value) for name, value in actual.items()} == {
        name: digest(value) for name, value in material[1].items()
    }
    assert rows == material[2] and mapping == material[3]


@pytest.mark.parametrize(
    "field",
    [
        "final_category",
        "reviewer_identity",
        "a_decision",
        "b_decision",
        "binary_eligible",
        "pair_id",
        "operator_id",
        "mutation_operator",
        "expected_effect",
        "human_rationale",
        "human_evidence",
        "ai_output",
    ],
)
def test_forbidden_metadata_fails_structurally(field):
    with pytest.raises(ValueError):
        audit_metadata({"nested": [{field: "forbidden"}]})


def test_normal_source_words_are_not_naively_rejected():
    audit_metadata({"text": "return positive; // negative control ordinary program vocabulary"})


@pytest.mark.parametrize(
    "field,value",
    [
        ("model", "another"),
        ("max_output_tokens", 3000),
        ("max_technical_retries", 3),
        ("logical_requests", 301),
        ("paid_execution_approved", True),
    ],
)
def test_nonprovider_protocol_parameters_are_frozen(material, field, value):
    data = material[0].model_dump(exclude={"fingerprint"}) | {field: value}
    with pytest.raises(ValueError):
        seal(PositiveProtocol, **data)


def test_graph_policy_identical_except_strategy(material):
    configs = [c.model_dump(exclude={"strategy"}) for c in material[0].strategies]
    assert configs[0] == configs[1] == configs[2]
    assert configs[0]["hop_count"] == 1 and configs[0]["max_total_chars"] == 20000
    assert not any(
        configs[0][key] for key in ["include_spec", "include_discovery", "include_metrics"]
    )


def test_source_capability_blocks_escape_symlink_and_truth(tmp_path):
    root = tmp_path / "allowed"
    root.mkdir()
    secret = tmp_path / "truth.json"
    secret.write_text("SYNTHETIC_TRUTH_CANARY")
    (root / "link").symlink_to(secret)
    for name in ("../truth.json", "link"):
        with pytest.raises(ValueError):
            capability_path(root, name)


def test_offline_freeze_is_append_only_and_all_bytes_verified(material, tmp_path):
    root = tmp_path / "execution"
    receipt = freeze_execution_bundle(root, material[1])
    assert verify_execution_bundle(root, receipt["fingerprint"]) == receipt
    assert not (root / "assessment-freeze.json").exists()
    with pytest.raises(ValueError, match="immutable"):
        freeze_execution_bundle(root, material[1])
    (root / "unknown.json").write_text("{}")
    with pytest.raises(ValueError, match="inventory"):
        verify_execution_bundle(root, receipt["fingerprint"])


@pytest.mark.parametrize(
    "name",
    ["protocol.json", "context-manifest.json", "request-manifest.json", "prompt-schema.json"],
)
def test_manifest_drift_rejected(material, tmp_path, name):
    root = tmp_path / "execution"
    receipt = freeze_execution_bundle(root, material[1])
    (root / name).write_bytes((root / name).read_bytes() + b" ")
    with pytest.raises(ValueError, match="bytes"):
        verify_execution_bundle(root, receipt["fingerprint"])


def test_cost_estimate_accounts_for_all_requests_outputs_retries(material):
    protocol, _, rows, _ = material
    price = seal(PricingAssumption)
    report = preflight_cost(protocol, rows, price)
    assert report["expected_output_budget"] == 180000
    assert report["maximum_primary_output_budget"] == 600000
    assert report["maximum_output_with_retries"] == 1800000
    assert Decimal(report["maximum_primary_usd"]) == Decimal("1.283040")
    assert Decimal(report["maximum_including_retries_usd"]) == Decimal("3.849120")
    assert report["long_context_requests"] == 0
    assert report["live_api_calls"] == 0 and report["provider_usage"] is None
    assert report["paid_execution_approved"] is False
    assert report["total_input_estimate"] == sum(r.input_estimate for r in rows)
    assert all(
        report["by_strategy"][s.value]["truncated"]
        == sum(r.truncated for r in rows if r.strategy == s)
        for s in STRATEGIES
    )


def test_token_proxy_has_utf8_conservative_bound():
    estimate, upper = token_estimate("π" * 100)
    assert estimate == 195 and upper == 2248


def test_short_long_pricing_applies_per_request():
    price = seal(PricingAssumption)
    assert price.charge(272000, 2000) * 2 != price.charge(272001, 2000)
    with pytest.raises(ValueError):
        price.charge(1050000, 2000)


@pytest.mark.parametrize("count", [99, 101])
def test_incomplete_case_product_refused(count):
    with pytest.raises(ValueError):
        ordered_product(tuple(str(i) for i in range(count)))
