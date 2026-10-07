"""Synthetic third-human contracts and privacy guards; no actual adjudication."""

import ast
import builtins
import hashlib
import json
import socket
from pathlib import Path

import pytest
from pydantic import ValidationError

from archguard.benchmark.oss.models import canonical, digest, seal
from archguard.benchmark.semantic_adjudication import (
    AdjudicatorSubmission,
    validate_adjudication_response,
)
from archguard.benchmark.semantic_holdout import (
    BlindedPacket,
    CaseRecord,
    HoldoutSample,
    SourceEvidence,
)
from archguard.infrastructure.semantic_adjudication import (
    build_adjudicator_material,
    freeze_adjudicator_handoff,
    handoff_receipt,
    verify_adjudicator_handoff,
    verify_conflict_inputs,
)


def sealed(value):
    value = {k: v for k, v in value.items() if k != "fingerprint"}
    return value | {"fingerprint": digest(value)}


@pytest.fixture
def frozen(tmp_path):
    packet_root = tmp_path / "packets"
    packet_root.mkdir()
    records = []
    originals = []
    text = "Synthetic source line one.\nSynthetic source <script>not executable</script>.\n"
    for i in range(100):
        rule = f"ARCH20{i % 5 + 1}"
        language = "JAVA" if i % 2 else "TYPESCRIPT"
        packet = seal(
            BlindedPacket,
            blinded_id=f"synthetic-primary-{i}",
            rule_id=rule,
            language=language,
            project_alias=f"synthetic-private-project-{i}",
            target_path="src/Frozen.txt",
            target_component="Frozen",
            architecture_contract="Synthetic frozen architecture only.",
            evidence=(
                SourceEvidence(
                    evidence_id=f"synthetic-original-evidence-{i}",
                    path="src/Frozen.txt",
                    text=text,
                    sha256=hashlib.sha256(text.encode()).hexdigest(),
                ),
            ),
        )
        records.append(
            CaseRecord(
                case_id=f"synthetic-scientific-{i}",
                blinded_id=packet.blinded_id,
                rule_id=rule,
                language=language,
                project_alias=packet.project_alias,
                technical_status="VALID",
                packet_fingerprint=packet.fingerprint,
                validation_fingerprint="1" * 64,
                context_diagnostics_fingerprint="2" * 64,
            )
        )
        if i < 4:
            (packet_root / (packet.blinded_id + ".json")).write_text(canonical(packet))
            originals.append(packet)
    sample = seal(HoldoutSample, cases=tuple(records))
    sample_path = tmp_path / "sample-v1.json"
    sample_path.write_text(canonical(sample))
    guidance = sealed(
        {
            "schema_version": "synthetic-frozen-guidance-v1",
            "general": "Unchanged synthetic rubric.",
            "arch201_vs_arch205": "Unchanged synthetic distinction.",
            "rules": {f"ARCH20{i}": "Unchanged synthetic rule." for i in range(1, 6)},
        }
    )
    guidance_path = tmp_path / "reviewer-guidance-v1.json"
    guidance_path.write_text(json.dumps(guidance, indent=3) + "\n")
    index = sealed(
        {
            "schema_version": "adjudicator-safe-conflict-index-v1",
            "source_lineage": {"sample_fingerprint": sample.fingerprint},
            "conflict_count": 4,
            "full_handoff_created": False,
            "cases": [
                {
                    "conflict_id": f"synthetic-conflict-{i}",
                    "case_id": records[i].case_id,
                    "rule_id": records[i].rule_id,
                    "language": records[i].language,
                }
                for i in range(4)
            ],
        }
    )
    index_path = tmp_path / "adjudicator-safe-index-v1.json"
    index_path.write_text(canonical(index))
    conflicts = sealed(
        {
            "conflict_count": 4,
            "final_ground_truth_materialized": False,
            "automatic_resolution": False,
            "conflicts": [
                row | {"a_decision": "POSITIVE", "b_decision": "NEGATIVE"} for row in index["cases"]
            ],
        }
    )
    analysis = sealed(
        {
            "primary": {"n": 100, "exact_agreement": 96, "disagreement": 4},
            "final_ground_truth_materialized": False,
            "conflicts_resolved": 0,
        }
    )
    receipt = sealed(
        {
            "paired_cases": 100,
            "conflict_count": 4,
            "ground_truth_status": "FINAL_HUMAN_GROUND_TRUTH_NOT_FROZEN",
            "final_ground_truth_materialized": False,
            "conflict_manifest_fingerprint": conflicts["fingerprint"],
            "adjudicator_safe_index_fingerprint": index["fingerprint"],
            "agreement_analysis_fingerprint": analysis["fingerprint"],
        }
    )
    paths = {
        "conflicts": tmp_path / "conflict-manifest-v1.json",
        "index": index_path,
        "analysis": tmp_path / "agreement-analysis-v1.json",
        "receipt": tmp_path / "agreement-verification-v1.json",
    }
    values = {"conflicts": conflicts, "index": index, "analysis": analysis, "receipt": receipt}
    for name, value in values.items():
        paths[name].write_text(canonical(value))
    return {
        "paths": paths,
        "expected": {name: value["fingerprint"] for name, value in values.items()},
        "sample": sample,
        "sample_path": sample_path,
        "packet_root": packet_root,
        "guidance_path": guidance_path,
        "guidance_fp": guidance["fingerprint"],
        "originals": originals,
        "seed": bytes(range(32)),
    }


def material(f):
    return build_adjudicator_material(
        f["paths"]["index"],
        f["sample_path"],
        f["packet_root"],
        f["guidance_path"],
        f["seed"],
        expected_index_fingerprint=f["expected"]["index"],
        expected_sample_fingerprint=f["sample"].fingerprint,
        expected_guidance_fingerprint=f["guidance_fp"],
    )


def verify_c(f):
    paths = f["paths"]
    return verify_conflict_inputs(
        paths["conflicts"], paths["index"], paths["analysis"], paths["receipt"], f["expected"]
    )


@pytest.mark.parametrize("key", ["conflicts", "index", "analysis", "receipt"])
def test_exact_c_fingerprint_guards(frozen, key):
    assert verify_c(frozen).conflict_count == 4
    frozen["expected"][key] = "0" * 64
    with pytest.raises(ValueError, match="unapproved"):
        verify_c(frozen)


@pytest.mark.parametrize(
    "change", ["omitted", "added", "agreement", "replaced", "rule", "truth", "count"]
)
def test_conflict_membership_and_state_guards_even_after_resealing(frozen, change):
    values = {key: json.loads(path.read_bytes()) for key, path in frozen["paths"].items()}
    manifest = values["conflicts"]
    index = values["index"]
    if change == "omitted":
        manifest["conflicts"].pop()
    elif change == "added":
        manifest["conflicts"].append(manifest["conflicts"][0])
    elif change == "agreement":
        manifest["conflicts"][0]["b_decision"] = "POSITIVE"
    elif change == "replaced":
        manifest["conflicts"][0]["case_id"] = "synthetic-scientific-99"
    elif change == "rule":
        manifest["conflicts"][0]["rule_id"] = "ARCH205"
    elif change == "truth":
        values["receipt"]["final_ground_truth_materialized"] = True
    elif change == "count":
        index["conflict_count"] = 3
    values["conflicts"] = sealed(manifest)
    values["index"] = sealed(index)
    values["receipt"].update(
        conflict_manifest_fingerprint=values["conflicts"]["fingerprint"],
        adjudicator_safe_index_fingerprint=values["index"]["fingerprint"],
    )
    for key, value in values.items():
        value = sealed(value)
        frozen["paths"][key].write_text(canonical(value))
        frozen["expected"][key] = value["fingerprint"]
    with pytest.raises(ValueError):
        verify_c(frozen)


def test_exact_four_sources_guidance_and_new_opaque_ids(frozen):
    bundle, mapping, contents = material(frozen)
    assert len(bundle.packets) == len({p.blinded_id for p in bundle.packets}) == 4
    expected = {c.case_id for c in frozen["sample"].cases[:4]}
    assert {r["case_id"] for r in mapping["rows"]} == expected
    original = {p.blinded_id: p for p in frozen["originals"]}
    packets = {p.blinded_id: p for p in bundle.packets}
    for row in mapping["rows"]:
        before = original[row["source_blinded_id"]]
        after = packets[row["adjudicator_blinded_id"]]
        assert (
            after.rule_id,
            after.language,
            after.target_path,
            after.target_component,
            after.architecture_contract,
        ) == (
            before.rule_id,
            before.language,
            before.target_path,
            before.target_component,
            before.architecture_contract,
        )
        assert [(e.path, e.text, e.sha256) for e in after.evidence] == [
            (e.path, e.text, e.sha256) for e in before.evidence
        ]
        assert all(
            new.evidence_id != old.evidence_id
            for new, old in zip(after.evidence, before.evidence, strict=True)
        )
        assert (
            row["source_blinded_id"] not in after.blinded_id
            and row["case_id"] not in after.blinded_id
        )
        for body in contents.values():
            assert not any(
                value.encode() in body
                for value in (
                    row["source_blinded_id"],
                    row["case_id"],
                    row["conflict_id"],
                    before.project_alias,
                )
            )
    assert frozen["seed"].hex().encode() not in b"".join(contents.values())
    assert contents["rule-guidance-v1.json"] == frozen["guidance_path"].read_bytes()
    assert (
        "<script>" not in contents["index.html"].decode()
        and "&lt;script&gt;" in contents["index.html"].decode()
    )
    assert "default-src 'none'" in contents["index.html"].decode()


def test_deterministic_ids_order_and_private_mapping(frozen):
    before = material(frozen)
    assert before == material(frozen)
    sample = seal(HoldoutSample, cases=tuple(reversed(frozen["sample"].cases)))
    frozen["sample"] = sample
    frozen["sample_path"].write_text(canonical(sample))
    after = material(frozen)
    assert before[0] == after[0] and before[2] == after[2]
    frozen["seed"] = b"x" * 32
    other = material(frozen)
    assert {p.blinded_id for p in other[0].packets}.isdisjoint(
        p.blinded_id for p in before[0].packets
    )


def test_builder_only_reads_safe_inputs_not_primary_answers_or_construction(frozen, monkeypatch):
    allowed = {
        frozen["paths"]["index"].resolve(),
        frozen["sample_path"].resolve(),
        frozen["guidance_path"].resolve(),
    }
    allowed.update(path.resolve() for path in frozen["packet_root"].iterdir())
    original = Path.open
    builtin = builtins.open
    seen = []

    def guard(path):
        candidate = Path(path).resolve()
        if candidate not in allowed:
            raise AssertionError("builder attempted private primary/construction input")
        seen.append(candidate)

    def guarded(path, *args, **kwargs):
        guard(path)
        return original(path, *args, **kwargs)

    def guarded_builtin(path, *args, **kwargs):
        guard(path)
        return builtin(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    monkeypatch.setattr(builtins, "open", guarded_builtin)
    bundle, _, _ = material(frozen)
    assert len(bundle.packets) == 4 and set(seen) == allowed


@pytest.mark.parametrize(
    "marker",
    [
        "Reviewer A chose POSITIVE",
        "Reviewer B was uncertain",
        "one reviewer said POSITIVE",
        "reviewers disagreed between POSITIVE and NEGATIVE",
        "Reviewer A category POSITIVE",
        "MUTATION_CANDIDATE",
        "MATCHED_CONTROL",
        "intended-positive",
        "hb-" + "a" * 32,
    ],
)
def test_leakage_audit_stops_without_rewriting_frozen_source(frozen, marker):
    original = frozen["originals"][0]
    evidence = original.evidence[0]
    poisoned = marker + "\n"
    changed = seal(
        BlindedPacket,
        **original.model_dump(exclude={"fingerprint", "evidence"}),
        evidence=(
            SourceEvidence(
                evidence_id=evidence.evidence_id,
                path=evidence.path,
                text=poisoned,
                sha256=hashlib.sha256(poisoned.encode()).hexdigest(),
            ),
        ),
    )
    path = frozen["packet_root"] / (changed.blinded_id + ".json")
    path.write_text(canonical(changed))
    records = tuple(
        CaseRecord.model_validate(c.model_dump() | {"packet_fingerprint": changed.fingerprint})
        if c.blinded_id == changed.blinded_id
        else c
        for c in frozen["sample"].cases
    )
    frozen["sample"] = seal(HoldoutSample, cases=records)
    frozen["sample_path"].write_text(canonical(frozen["sample"]))
    before = path.read_bytes()
    with pytest.raises(ValueError, match="hint"):
        material(frozen)
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "field",
    [
        "a_decision",
        "b_decision",
        "reviewer_a_rationales",
        "reviewer_b_notes",
        "reviewer_a_evidence",
        "pair_id",
        "operator_id",
        "construction_intent",
        "ai_results",
        "static_predictions",
        "graph_predictions",
        "structural_v2_predictions",
        "hybrid_predictions",
    ],
)
def test_private_fields_cannot_enter_case_or_bundle(frozen, field):
    index = json.loads(frozen["paths"]["index"].read_bytes())
    index["cases"][0][field] = "FORBIDDEN"
    frozen["paths"]["index"].write_text(canonical(sealed(index)))
    with pytest.raises(ValueError):
        material(frozen)


def test_blankness_schema_and_no_identity_assignment(frozen):
    bundle, _, contents = material(frozen)
    template = json.loads(contents["response-template.json"])
    assert template["reviewer_identity"] == "" and template["attestation"] is None
    assert [r["blinded_id"] for r in template["responses"]] == [
        p.blinded_id for p in bundle.packets
    ]
    assert all(
        r["decision"] is None and not r["rationale"] and not r["evidence"] and not r["note"]
        for r in template["responses"]
    )
    with pytest.raises(ValidationError):
        AdjudicatorSubmission.model_validate(template)
    assert (
        json.loads(contents["submission-schema.json"]) == AdjudicatorSubmission.model_json_schema()
    )
    receipt = handoff_receipt(bundle, contents)
    assert all(
        receipt[k] == 0
        for k in (
            "prepopulated_decisions",
            "prepopulated_rationales",
            "prepopulated_evidence",
            "prepopulated_notes",
            "A_B_category_leakage_findings",
            "A_B_rationale_note_evidence_leakage_findings",
            "construction_leakage_findings",
            "model_detector_leakage_findings",
        )
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("decision", "POSITIVE"),
        ("rationale", "suggestion"),
        ("evidence", [{"evidence_id": "guess", "start_line": 1, "end_line": 1}]),
        ("note", "hint"),
    ],
)
def test_nonblank_forms_rejected_before_handoff(frozen, field, value):
    bundle, _, contents = material(frozen)
    template = json.loads(contents["response-template.json"])
    template["responses"][0][field] = value
    contents["response-template.json"] = json.dumps(template).encode()
    with pytest.raises(ValueError, match="blank"):
        handoff_receipt(bundle, contents)


def synthetic_response(bundle, category):
    return {
        "schema_version": "semantic-holdout-adjudication-submission-v1",
        "reviewer_slot": "ADJUDICATOR",
        "bundle_fingerprint": bundle.fingerprint,
        "reviewer_identity": "Synthetic third-human test identity only",
        "attestation": "REAL_HUMAN_INDEPENDENT_ADJUDICATION",
        "responses": [
            {
                "blinded_id": p.blinded_id,
                "decision": category,
                "rationale": "Synthetic independent DTO fixture.",
                "evidence": [
                    {"evidence_id": p.evidence[0].evidence_id, "start_line": 1, "end_line": 2}
                ],
            }
            for p in bundle.packets
        ],
    }


@pytest.mark.parametrize("category", ["POSITIVE", "NEGATIVE", "UNCERTAIN", "OUT_OF_SCOPE"])
def test_all_four_independent_categories_allowed_including_neither_primary(frozen, category):
    bundle, _, _ = material(frozen)
    submission = AdjudicatorSubmission.model_validate(synthetic_response(bundle, category))
    validate_adjudication_response(bundle, submission)
    assert all(r.decision == category for r in submission.responses)
    # Synthetic primaries selected POSITIVE/NEGATIVE; UNCERTAIN/OOS remain unrestricted.


@pytest.mark.parametrize(
    "change",
    [
        "identity",
        "attestation",
        "duplicate",
        "missing",
        "rationale",
        "empty_evidence",
        "foreign_evidence",
        "range",
        "float_line",
        "bundle",
        "extra_case",
    ],
)
def test_future_response_schema_and_evidence_validation_support(frozen, change):
    bundle, _, _ = material(frozen)
    data = synthetic_response(bundle, "UNCERTAIN")
    row = data["responses"][0]
    if change == "identity":
        data["reviewer_identity"] = " "
    elif change == "attestation":
        data["attestation"] = "REAL_HUMAN_INDEPENDENT_REVIEW"
    elif change == "duplicate":
        data["responses"][1] = row
    elif change == "missing":
        data["responses"].pop()
    elif change == "rationale":
        row["rationale"] = " "
    elif change == "empty_evidence":
        row["evidence"] = []
    elif change == "foreign_evidence":
        row["evidence"][0]["evidence_id"] = bundle.packets[1].evidence[0].evidence_id
    elif change == "range":
        row["evidence"][0]["end_line"] = 3
    elif change == "float_line":
        row["evidence"][0]["start_line"] = 1.0
    elif change == "bundle":
        data["bundle_fingerprint"] = "0" * 64
    elif change == "extra_case":
        row["blinded_id"] = "not-in-bundle"
    with pytest.raises(ValueError):
        validate_adjudication_response(bundle, AdjudicatorSubmission.model_validate(data))


def test_immutable_private_handoff_no_network_and_no_truth(frozen, tmp_path, monkeypatch):
    bundle, mapping, contents = material(frozen)

    def denied(*args, **kwargs):
        raise AssertionError("live network forbidden")

    monkeypatch.setattr(socket, "socket", denied)
    handoff, coordinator = tmp_path / "handoff", tmp_path / "coordinator"
    receipt = freeze_adjudicator_handoff(handoff, coordinator, bundle, mapping, contents)
    verify_adjudicator_handoff(handoff, coordinator, mapping, contents, receipt)
    assert {p.name for p in handoff.iterdir()} == {*contents, "handoff-freeze.json"}
    assert {p.name for p in coordinator.iterdir()} == {"adjudicator-mapping-v1.json"}
    before = {str(p): p.read_bytes() for root in (handoff, coordinator) for p in root.iterdir()}
    with pytest.raises(ValueError, match="immutable"):
        freeze_adjudicator_handoff(handoff, coordinator, bundle, mapping, contents)
    assert before == {
        str(p): p.read_bytes() for root in (handoff, coordinator) for p in root.iterdir()
    }
    assert all(
        "truth" not in p.name and "completed-response" not in p.name for p in handoff.iterdir()
    )
    (handoff / "bundle-v1.json").write_text("tamper")
    with pytest.raises(ValueError, match="changed"):
        verify_adjudicator_handoff(handoff, coordinator, mapping, contents, receipt)


def test_preparation_keeps_all_old_inputs_byte_identical(frozen, tmp_path):
    paths = {*frozen["paths"].values(), frozen["sample_path"], frozen["guidance_path"]}
    paths.update(frozen["packet_root"].iterdir())
    before = {p: p.read_bytes() for p in paths}
    bundle, mapping, contents = material(frozen)
    freeze_adjudicator_handoff(
        tmp_path / "handoff", tmp_path / "coordinator", bundle, mapping, contents
    )
    assert before == {p: p.read_bytes() for p in paths}


def test_execution_has_no_acceptance_truth_or_ai_path():
    root = Path(__file__).resolve().parents[2]
    for name in (
        "src/archguard/benchmark/semantic_adjudication.py",
        "src/archguard/infrastructure/semantic_adjudication.py",
        "scripts/prompt015d_adjudicator.py",
    ):
        tree = ast.parse((root / name).read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [n.name for n in node.names] + (
                    [node.module or ""] if isinstance(node, ast.ImportFrom) else []
                )
                assert not any(
                    token in value
                    for value in names
                    for token in (
                        "llm_provider",
                        "semantic_evaluation",
                        "httpx",
                        "requests",
                        "urllib",
                        "socket",
                        "PrivatePair",
                        "Operator",
                    )
                )
            if isinstance(node, ast.Call):
                call = getattr(node.func, "id", getattr(node.func, "attr", ""))
                assert call not in {
                    "freeze_submission",
                    "freeze_b_submission",
                    "validate_adjudication_response",
                    "construct_holdout",
                    "finalize_truth",
                    "adjudicate",
                    "majority_vote",
                }
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert ".env" not in node.value and "provenance-v1.json" not in node.value
    builder = ast.parse(
        (root / "src/archguard/infrastructure/semantic_adjudication.py").read_text()
    )
    function = next(
        n
        for n in ast.walk(builder)
        if isinstance(n, ast.FunctionDef) and n.name == "build_adjudicator_material"
    )
    assert not any(
        isinstance(n, ast.Name)
        and n.id in {"a_decision", "b_decision", "conflicts", "manifest_path"}
        for n in ast.walk(function)
    )
