"""Synthetic returns only: staging/immutable human intake and both agreement branches."""

import hashlib
import json
from pathlib import Path

import pytest

from archguard.benchmark.oss.models import canonical, digest, seal
from archguard.benchmark.semantic_holdout import BlindedPacket, SourceEvidence
from archguard.benchmark.semantic_review import (
    ReviewerABundle,
    ReviewerASubmission,
    ReviewerBBundle,
    ReviewerBSubmission,
)
from archguard.infrastructure import unified_human_intake as intake
from archguard.infrastructure import unified_human_review as review
from scripts.prompt021a_human_handoff import PROTOCOL


@pytest.fixture
def source_authority(tmp_path):
    root = tmp_path / review.REVIEW
    root.mkdir(parents=True)
    text = "Synthetic line one.\nSynthetic line two.\n"
    packets = tuple(
        seal(
            BlindedPacket,
            blinded_id=f"synthetic-{digest(i)}",
            rule_id=f"ARCH20{i % 5 + 1}",
            language="JAVA" if i % 2 else "TYPESCRIPT",
            project_alias="synthetic",
            target_path="src/Synthetic.txt",
            target_component="Synthetic",
            architecture_contract="Synthetic contract.",
            evidence=(
                SourceEvidence(
                    evidence_id=f"synthetic-e-{i}",
                    path="src/Synthetic.txt",
                    text=text,
                    sha256=hashlib.sha256(text.encode()).hexdigest(),
                ),
            ),
        )
        for i in range(100)
    )
    protocol = {"categories": list(PROTOCOL["categories"])}
    protocol["fingerprint"] = digest(protocol)
    guidance = {"questions": {f"ARCH20{i}": "Synthetic question." for i in range(1, 6)}}
    guidance["fingerprint"] = digest(guidance)
    bundles = {}
    files = {}
    for role, model, submission in (
        ("A", ReviewerABundle, ReviewerASubmission),
        ("B", ReviewerBBundle, ReviewerBSubmission),
    ):
        bundle = seal(
            model,
            schema_version="blank-independent-human-bundle-v1",
            reviewer_slot=role,
            status="WAITING_FOR_REAL_INDEPENDENT_HUMAN",
            protocol=protocol,
            guidance=guidance,
            packets=tuple(
                sorted(packets, key=lambda p: digest(("p020-review-order-v2", role, p.blinded_id)))
            ),
        )
        bundles[role] = bundle
        (root / role).mkdir()
        blank = dict(
            schema_version="semantic-holdout-human-submission-v1",
            reviewer_slot=role,
            bundle_fingerprint=bundle.fingerprint,
            reviewer_identity="",
            attestation="",
            responses=[
                dict(blinded_id=p.blinded_id, decision=None, rationale="", evidence=[], note="")
                for p in bundle.packets
            ],
        )
        schema = {"schema": submission.model_json_schema()}
        schema["fingerprint"] = digest(schema)
        for name, value in (
            ("bundle.json", bundle),
            ("submission-schema.json", schema),
            ("submission-template.json", blank),
        ):
            path = root / role / name
            path.write_text(canonical(value) + "\n")
            files[f"{role}/{name}"] = review.sha(path)
    for name, value in (("protocol.json", protocol), ("guidance.json", guidance)):
        path = root / name
        path.write_text(canonical(value) + "\n")
        files[name] = review.sha(path)
    return review.Authority(
        tmp_path, root, bundles, files, digest("synthetic-assignment"), digest(files)
    )


def response(authority, role):
    bundle = authority.bundles[role]
    return dict(
        schema_version="semantic-holdout-human-submission-v1",
        reviewer_slot=role,
        bundle_fingerprint=bundle.fingerprint,
        reviewer_identity="human-" + ("a" if role == "A" else "b") * 32,
        attestation="REAL_HUMAN_INDEPENDENT_REVIEW",
        responses=[
            dict(
                blinded_id=p.blinded_id,
                decision="UNCERTAIN",
                rationale="Synthetic formal validator only.",
                note="",
                evidence=[dict(evidence_id=p.evidence[0].evidence_id, start_line=1, end_line=2)],
            )
            for p in bundle.packets
        ],
    )


@pytest.fixture
def returned(source_authority):
    authority = source_authority
    root = authority.repository
    handoffs = {}
    for role in review.ROLES:
        folder = root / review.HANDOFF / f"reviewer-{role.lower()}"
        receipt = review.prepare_handoff(authority, role, folder)
        handoffs[role] = {"receipt_fingerprint": receipt["fingerprint"]}
        data = response(authority, role)
        # Scientific category labels follow stable ID, never each reviewer's array position.
        data["responses"] = [
            dict(row, decision=PROTOCOL["categories"][i % 4])
            for i, row in enumerate(sorted(data["responses"], key=lambda r: r["blinded_id"]))
        ]
        if role == "B":
            data["responses"].reverse()
        (folder / "completed-response.json").write_text(json.dumps(data, indent=2) + "\n")
        (folder / ".DS_Store").write_bytes(b"synthetic metadata")
    ready = review.append_seal(
        root / review.BASE / "p021-a-handoff-readiness-v1.json", dict(handoffs=handoffs)
    )
    review.append_seal(
        root / review.BASE / "p021-a-verification-v1.json",
        dict(readiness_fingerprint=ready["fingerprint"]),
    )
    review.append_seal(root / review.PROTOCOL_PATH, PROTOCOL)
    mapping = root / intake.COORDINATOR
    for i, p in enumerate(sorted(authority.bundles["A"].packets, key=lambda p: p.blinded_id)):
        review.append_seal(
            mapping / f"{p.blinded_id}.json",
            dict(
                scientific_case_id=f"synthetic-science-{i:03}",
                execution_id=f"synthetic-execution-{i}",
            ),
        )
    return authority


def replace_return(authority, role, change):
    path = (
        authority.repository
        / review.HANDOFF
        / f"reviewer-{role.lower()}"
        / "completed-response.json"
    )
    data = json.loads(path.read_bytes())
    change(data)
    path.write_text(json.dumps(data, indent=3) + "\n")


def test_copy_and_raw_receipts_precede_removal_and_no_json_parse(returned, monkeypatch):
    authority = returned
    root = authority.repository
    originals = {
        r: (
            root / review.HANDOFF / f"reviewer-{r.lower()}" / "completed-response.json"
        ).read_bytes()
        for r in review.ROLES
    }
    for role in review.ROLES:
        (
            root / review.HANDOFF / f"reviewer-{role.lower()}" / "completed-response.json"
        ).write_bytes(b"synthetic NOT JSON")
        originals[role] = b"synthetic NOT JSON"
    real_unlink = Path.unlink
    removed = []

    def checked_unlink(path, *args, **kwargs):
        if path.name == "completed-response.json":
            for role in review.ROLES:
                raw, receipt = intake.verify_incoming(root, role)
                assert raw == originals[role]
                assert receipt["decisions_parsed"] is False
            removed.append(path.parent.name)
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", checked_unlink)
    staged = intake.stage_returns(authority)
    assert staged["parsed_before_staging"] is False
    assert removed == ["reviewer-a", "reviewer-b"]
    assert staged["ds_store_removed"] == {"A": True, "B": True}
    for role in review.ROLES:
        raw, receipt = intake.verify_incoming(root, role)
        assert raw == originals[role] and receipt["raw_sha256"] == hashlib.sha256(raw).hexdigest()
        review.verify_handoff(authority, role, root / review.HANDOFF / f"reviewer-{role.lower()}")
    assert intake.stage_returns(authority)["ds_store_removed"] == staged["ds_store_removed"]


@pytest.mark.parametrize(
    "fault", ["missing", "changed", "arbitrary_hidden", "other_extra", "nested_metadata"]
)
def test_pre_staging_drift_blocks_without_removing_any_return(returned, fault):
    root = returned.repository
    folder = root / review.HANDOFF / "reviewer-b"
    if fault == "missing":
        (folder / "submission-template.json").unlink()
    elif fault == "changed":
        (folder / "guidance.json").write_text("drift")
    else:
        extra = {
            "arbitrary_hidden": ".hidden",
            "other_extra": "unknown.json",
            "nested_metadata": "nested/.DS_Store",
        }[fault]
        path = folder / extra
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"synthetic extra")
    with pytest.raises(review.ReviewBlocked):
        intake.stage_returns(returned)
    assert not (root / intake.INCOMING).exists()
    assert all(
        (root / review.HANDOFF / f"reviewer-{r.lower()}" / "completed-response.json").exists()
        for r in review.ROLES
    )


def test_corrupt_staged_copy_never_authorizes_source_removal(returned, monkeypatch):
    real = Path.write_bytes
    original_build = intake.atomic_directory

    def corrupt(destination, build):
        original_build(destination, build)
        real(destination / "completed-response.json", b"corrupted staged bytes")

    monkeypatch.setattr(intake, "atomic_directory", corrupt)
    with pytest.raises(review.ReviewBlocked):
        intake.stage_returns(returned)
    assert all(
        (
            returned.repository
            / review.HANDOFF
            / f"reviewer-{r.lower()}"
            / "completed-response.json"
        ).exists()
        for r in review.ROLES
    )


@pytest.mark.parametrize("role", ["A", "B"])
@pytest.mark.parametrize(
    "fault",
    [
        "schema",
        "slot",
        "bundle",
        "identity",
        "attestation",
        "missing",
        "extra",
        "duplicate",
        "category",
        "rationale",
        "evidence",
        "unknown_evidence",
        "line",
        "reverse_line",
    ],
)
def test_formal_validation_rejects_without_correcting_return(returned, role, fault):
    def change(data):
        row = data["responses"][0]
        if fault == "schema":
            data["schema_version"] = "historical-other-v2"
        elif fault == "slot":
            data["reviewer_slot"] = "B" if role == "A" else "A"
        elif fault == "bundle":
            data["bundle_fingerprint"] = "0" * 64
        elif fault == "identity":
            data["reviewer_identity"] = "synthetic@example.invalid"
        elif fault == "attestation":
            data["attestation"] = ""
        elif fault == "missing":
            data["responses"].pop()
        elif fault == "extra":
            data["responses"].append(dict(row, blinded_id="synthetic-extra"))
        elif fault == "duplicate":
            data["responses"][1] = row
        elif fault == "category":
            row["decision"] = "SUPPORTED"
        elif fault == "rationale":
            row["rationale"] = " "
        elif fault == "evidence":
            row["evidence"] = []
        elif fault == "unknown_evidence":
            row["evidence"][0]["evidence_id"] = "not-present"
        elif fault == "line":
            row["evidence"][0]["end_line"] = 3
        else:
            row["evidence"][0].update(start_line=2, end_line=1)

    replace_return(returned, role, change)
    intake.stage_returns(returned)
    raw, _ = intake.verify_incoming(returned.repository, role)
    with pytest.raises(review.ReviewBlocked):
        intake.accept(returned, role)
    assert not (returned.repository / intake.ACCEPTED / role / "v0001").exists()
    assert intake.verify_incoming(returned.repository, role)[0] == raw


def test_freeze_byte_exact_idempotent_and_canonical_distinct_and_no_handoff_response_reads(
    returned, monkeypatch
):
    intake.stage_returns(returned)
    original_read = Path.read_bytes

    def guarded(path):
        if path.name == "completed-response.json" and "human-handoff" in path.parts:
            pytest.fail("Scientific intake must never read a handoff return after staging")
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", guarded)
    for role in review.ROLES:
        receipt = intake.accept(returned, role)
        assert intake.accept(returned, role) == receipt
        saved = returned.repository / intake.ACCEPTED / role / "v0001"
        original, _ = intake.verify_incoming(returned.repository, role)
        assert (saved / "completed-response.json").read_bytes() == original
        assert receipt["raw_sha256"] != receipt["canonical_fingerprint"]
        assert (saved / "canonical-response.json").read_bytes() != original
        assert saved.stat().st_mode & 0o777 == 0o700
    (returned.repository / intake.ACCEPTED / "A/v0001/completed-response.json").write_bytes(
        b"drift"
    )
    with pytest.raises(review.ReviewBlocked):
        intake.accept(returned, "A")


def test_agreement_requires_both_accepted_and_distinct_humans(returned):
    replace_return(returned, "B", lambda d: d.update(reviewer_identity="human-" + "a" * 32))
    intake.stage_returns(returned)
    with pytest.raises(review.ReviewBlocked, match="BOTH_ACCEPTED"):
        intake.frozen_pair(returned)
    intake.accept(returned, "A")
    with pytest.raises(review.ReviewBlocked, match="BOTH_ACCEPTED"):
        intake.frozen_pair(returned)
    with pytest.raises(review.ReviewBlocked, match="DISTINCT"):
        intake.accept(returned, "B")
    assert not (returned.repository / intake.ACCEPTED / "B/v0001").exists()


def test_zero_conflict_consensus_all_four_categories_and_verified_replay(returned, monkeypatch):
    monkeypatch.setattr(intake, "SOURCE_FILES", ())
    result = intake.execute(returned)
    assert result["agreement"]["primary"]["n"] == 100
    assert result["agreement"]["primary"]["exact_agreement"] == 100
    assert result["agreement"]["primary"]["cohens_kappa"] == 1
    assert result["agreement"]["binary"]["n"] == 50
    assert result["truth_categories"] == dict.fromkeys(PROTOCOL["categories"], 25)
    assert result["branch"] == "NO_ADJUDICATION_REQUIRED"
    assert result["final_semantic_truth_frozen"] is True
    assert intake.execute(returned, verify_only=True) == result
    assert intake.execute(returned) == result
    assert review.read_seal(returned.repository / intake.RESULTS / "conflicts.json")["rows"] == []
    truth = review.read_seal(
        returned.repository / intake.RESULTS / "truth/final-semantic-truth.json"
    )
    assert len(truth["cases"]) == 100
    assert sum(c["binary_eligible"] for c in truth["cases"]) == 50
    assert not (returned.repository / intake.RESULTS / "adjudication").exists()


def test_conflict_branch_only_categorical_source_blind_adjudication(returned, monkeypatch):
    monkeypatch.setattr(intake, "SOURCE_FILES", ())

    def change(data):
        for row in data["responses"][:3]:
            row["decision"] = "NEGATIVE" if row["decision"] != "NEGATIVE" else "POSITIVE"
        # Rationale and evidence changes on agreements never create extra conflicts.
        data["responses"][3]["rationale"] = "A different synthetic rationale."
        data["responses"][3]["evidence"][0]["end_line"] = 1

    replace_return(returned, "B", change)
    result = intake.execute(returned)
    assert result["agreement"]["primary"]["disagreement"] == 3
    assert result["adjudication_packets"] == 3 and result["nonconflict_adjudication_packets"] == 0
    assert result["branch"] == "ADJUDICATION_REQUIRED"
    assert result["final_semantic_truth_frozen"] is False
    assert not (returned.repository / intake.RESULTS / "truth").exists()
    assert intake.execute(returned, verify_only=True) == result
    delivery = returned.repository / intake.RESULTS / "adjudication/handoff"
    for path in delivery.iterdir():
        text = path.read_text()
        assert "human-" + "a" * 32 not in text and "human-" + "b" * 32 not in text
        for forbidden in (
            "A_category",
            "B_category",
            "scientific_case_id",
            "pair_id",
            "construction_intent",
            "static_predictions",
            "graph_predictions",
            "ai_results",
            "hybrid_predictions",
        ):
            assert forbidden not in text


@pytest.mark.parametrize("category", PROTOCOL["categories"])
def test_degenerate_kappa_and_binary_nonbinary_exclusion(returned, monkeypatch, category):
    monkeypatch.setattr(intake, "SOURCE_FILES", ())
    for role in review.ROLES:
        replace_return(
            returned, role, lambda d: [r.update(decision=category) for r in d["responses"]]
        )
    result = intake.execute(returned)
    assert result["agreement"]["primary"]["cohens_kappa"] is None
    assert result["agreement"]["binary"]["n"] == (
        100 if category in {"POSITIVE", "NEGATIVE"} else 0
    )
    assert result["agreement"]["binary"]["cohens_kappa"] is None


def test_public_summary_contains_no_private_values_or_case_ids(returned, monkeypatch):
    monkeypatch.setattr(intake, "SOURCE_FILES", ())
    result = intake.execute(returned)
    text = canonical(result)
    for forbidden in (
        "synthetic-science-",
        "synthetic-evidence-",
        "synthetic-",
        "Synthetic formal-validator",
        "human-" + "a" * 32,
        "human-" + "b" * 32,
        '"rationale":',
        '"evidence_id":',
        '"reviewer_identity":',
        "opaque_reviewer_identity_fingerprint",
    ):
        assert forbidden not in text
    assert result["provider_calls"] == result["connectivity_calls"] == result["paid_spend_usd"] == 0
    assert not result["construction_intent_opened"] and not result["model_predictions_joined"]


def test_capabilities_forbid_construction_and_model_inputs(tmp_path):
    for path in (
        review.PRIVATE / "coordinator/construction-intent.json",
        review.FINAL / "evidence/static-output.json",
        review.FINAL / "evidence/graph-output.json",
        review.PRIVATE / "coordinator/structural-truth.json",
    ):
        with intake.intake_capability(tmp_path), pytest.raises(PermissionError):
            review.offline_guard("open", (str(tmp_path / path), "r", 0))
    with intake.intake_capability(tmp_path):
        review.offline_guard(
            "open", (str(tmp_path / intake.COORDINATOR / "synthetic.json"), "r", 0)
        )
