"""Formal integrity only. Synthetic answers never reference the scientific cohort."""

import ast
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from archguard.benchmark.oss.models import canonical, digest, seal
from archguard.benchmark.semantic_holdout import BlindedPacket, SourceEvidence
from archguard.benchmark.semantic_review import ReviewerABundle, ReviewerBBundle
from archguard.infrastructure import unified_human_review as review
from scripts.prompt021a_human_handoff import PROTOCOL


def sealed(value):
    return value | {"fingerprint": digest(value)}


@pytest.fixture
def authority(tmp_path):
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
            architecture_contract="Synthetic schema fixture only.",
            evidence=(
                SourceEvidence(
                    evidence_id=f"synthetic-evidence-{i}",
                    path="src/Synthetic.txt",
                    text=text,
                    sha256=hashlib.sha256(text.encode()).hexdigest(),
                ),
            ),
        )
        for i in range(100)
    )
    bundles = {}
    files = {}
    protocol = sealed({"categories": PROTOCOL["categories"], "human_review_performed": False})
    guidance = sealed({"questions": {f"ARCH20{i}": "Synthetic question." for i in range(1, 6)}})
    for role, model in (("A", ReviewerABundle), ("B", ReviewerBBundle)):
        ordered = tuple(
            sorted(packets, key=lambda p: digest(("p020-review-order-v2", role, p.blinded_id)))
        )
        bundle = seal(
            model,
            schema_version="blank-independent-human-bundle-v1",
            reviewer_slot=role,
            status="WAITING_FOR_REAL_INDEPENDENT_HUMAN",
            packets=ordered,
            protocol=protocol,
            guidance=guidance,
        )
        bundles[role] = bundle
        (root / role).mkdir()
        template = dict(
            schema_version="semantic-holdout-human-submission-v1",
            reviewer_slot=role,
            bundle_fingerprint=bundle.fingerprint,
            reviewer_identity="",
            attestation="",
            responses=[
                dict(blinded_id=p.blinded_id, decision=None, rationale="", evidence=[], note="")
                for p in ordered
            ],
        )
        for name, value in (
            ("bundle.json", bundle),
            ("submission-template.json", template),
            ("submission-schema.json", {"synthetic": True}),
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


def response(authority, role="A"):
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
                decision=PROTOCOL["categories"][i % 4],
                rationale="Synthetic formal-validator fixture; no scientific judgment.",
                evidence=[dict(evidence_id=p.evidence[0].evidence_id, start_line=1, end_line=2)],
                note="",
            )
            for i, p in enumerate(bundle.packets)
        ],
    )


def raw(value):
    return (json.dumps(value, indent=2) + "\n").encode()


def test_real_v2_exact_pins_case_sets_blind_order_and_blankness():
    repo = Path(__file__).resolve().parents[2]
    authority = review.load_authority(repo)
    for name in ("packet-inventory.json", "assignment-manifest.json"):
        assert (
            review.read_seal(authority.root / name)["fingerprint"]
            == review.PINS[review.REVIEW / name]
        )
    receipt = review.read_seal(repo / review.BASE / "p020-blinded-review-handoff-v2.json")
    assert (
        receipt["fingerprint"] == review.PINS[review.BASE / "p020-blinded-review-handoff-v2.json"]
    )
    assert len(authority.bundles["A"].packets) == len(authority.bundles["B"].packets) == 100
    assert {p.fingerprint for p in authority.bundles["A"].packets} == {
        p.fingerprint for p in authority.bundles["B"].packets
    }
    assert authority.bundles["A"].packets != authority.bundles["B"].packets


def test_legacy_and_alternative_paths_rejected(authority, tmp_path):
    for root in (tmp_path / review.FINAL / "review", tmp_path / "another-review-v2"):
        root.mkdir(parents=True)
        with pytest.raises(review.ReviewBlocked, match="UNAUTHORIZED"):
            review.load_authority(tmp_path, root)
        with pytest.raises(review.ReviewBlocked, match="UNAUTHORIZED"):
            review.prepare_handoff(replace(authority, root=root), "A", tmp_path / "delivery")


@pytest.mark.parametrize("role", ["A", "B"])
def test_handoff_manifest_copies_exact_bytes_and_only_own_role(authority, tmp_path, role):
    destination = tmp_path / ("reviewer-" + role.lower())
    receipt = review.prepare_handoff(authority, role, destination)
    assert review.verify_handoff(authority, role, destination) == receipt
    assert {p.name for p in destination.iterdir()} == {
        "bundle.json",
        "submission-schema.json",
        "submission-template.json",
        "guidance.json",
        "protocol.json",
        "README.txt",
        "handoff-receipt.json",
    }
    assert (destination / "bundle.json").read_bytes() == (
        authority.root / role / "bundle.json"
    ).read_bytes()
    assert receipt["expected_file_count"] == 6
    assert f"Reviewer {role}" in (destination / "README.txt").read_text()
    assert "ChatGPT" in (destination / "README.txt").read_text()
    assert "reviewer_identity" not in canonical(receipt)
    assert destination.stat().st_mode & 0o777 == 0o700
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in destination.iterdir())
    with pytest.raises(ValueError, match="immutable"):
        review.prepare_handoff(authority, role, destination)
    (destination / "bundle.json").write_text("drift")
    with pytest.raises(review.ReviewBlocked):
        review.verify_handoff(authority, role, destination)


def test_blind_order_rejects_construction_input_order_without_decoding(authority):
    bundle = authority.bundles["A"]
    review.verify_blind_bundle(bundle)
    reversed_bundle = seal(
        ReviewerABundle,
        **bundle.model_dump(exclude={"fingerprint", "packets"}),
        packets=tuple(reversed(bundle.packets)),
    )
    with pytest.raises(review.ReviewBlocked, match="ORDER"):
        review.verify_blind_bundle(reversed_bundle)
    assert PROTOCOL["adjudication"]["a_b_categories_or_rationales_exposed"] is False
    assert PROTOCOL["agreement"]["executed"] is False


@pytest.mark.parametrize("role", ["A", "B"])
def test_valid_synthetic_intake_preserves_all_categories_and_prose(authority, role):
    data = response(authority, role)
    data["responses"][0].update(
        decision="UNCERTAIN", rationale="Prose says POSITIVE; do not infer it."
    )
    submission = review.validate_intake(authority.bundles[role], raw(data))
    assert submission.responses[0].decision == "UNCERTAIN"
    assert submission.responses[0].rationale == data["responses"][0]["rationale"]
    assert {r.decision for r in submission.responses} == set(PROTOCOL["categories"])
    assert len(submission.responses) == len({r.blinded_id for r in submission.responses}) == 100


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "extra",
        "duplicate",
        "unknown_id",
        "category",
        "multiple_categories",
        "blank_rationale",
        "no_evidence",
        "negative_line",
        "zero_line",
        "outside_line",
        "reversed_line",
        "float_line",
        "bool_line",
        "unknown_evidence",
        "other_case_evidence",
        "unknown_file_field",
        "wrong_role",
        "wrong_bundle",
        "blank_attestation",
        "name_identity",
        "top_extension",
        "row_extension",
        "pair_id",
        "construction_intent",
        "prediction",
    ],
)
def test_invalid_synthetic_intake_rejected_without_semantic_correction(authority, fault):
    data = response(authority)
    row = data["responses"][0]
    evidence = row["evidence"][0]
    if fault == "missing":
        data["responses"].pop()
    elif fault == "extra":
        data["responses"].append(dict(row, blinded_id="extra"))
    elif fault == "duplicate":
        data["responses"][1] = row
    elif fault == "unknown_id":
        row["blinded_id"] = "synthetic-unknown"
    elif fault == "category":
        row["decision"] = "SUPPORTED"
    elif fault == "multiple_categories":
        row["decision"] = ["POSITIVE", "NEGATIVE"]
    elif fault == "blank_rationale":
        row["rationale"] = "  "
    elif fault == "no_evidence":
        row["evidence"] = []
    elif fault in {"negative_line", "zero_line", "float_line", "bool_line"}:
        evidence["start_line"] = {
            "negative_line": -1,
            "zero_line": 0,
            "float_line": 1.5,
            "bool_line": True,
        }[fault]
    elif fault == "outside_line":
        evidence["end_line"] = 3
    elif fault == "reversed_line":
        evidence.update(start_line=2, end_line=1)
    elif fault == "unknown_evidence":
        evidence["evidence_id"] = "not-present"
    elif fault == "other_case_evidence":
        evidence["evidence_id"] = data["responses"][1]["evidence"][0]["evidence_id"]
    elif fault == "unknown_file_field":
        evidence["file"] = "unknown.txt"
    elif fault == "wrong_role":
        data["reviewer_slot"] = "B"
    elif fault == "wrong_bundle":
        data["bundle_fingerprint"] = authority.bundles["B"].fingerprint
    elif fault == "blank_attestation":
        data["attestation"] = ""
    elif fault == "name_identity":
        data["reviewer_identity"] = "Synthetic personal name"
    elif fault == "top_extension":
        data["email"] = "synthetic@example.invalid"
    else:
        row[fault] = "forbidden extra field"
    with pytest.raises(review.ReviewBlocked):
        review.validate_intake(authority.bundles["A"], raw(data))


def test_duplicate_json_keys_rejected_and_diagnostics_do_not_echo_prose(authority):
    data = response(authority)
    source = raw(data).replace(
        b'"decision": "POSITIVE"', b'"decision": "NEGATIVE", "decision": "POSITIVE"', 1
    )
    with pytest.raises(review.ReviewBlocked):
        review.validate_intake(authority.bundles["A"], source)
    data["responses"][0]["decision"] = "SYNTHETIC_PRIVATE_VALUE"
    with pytest.raises(review.ReviewBlocked) as error:
        review.validate_intake(authority.bundles["A"], raw(data))
    assert "SYNTHETIC_PRIVATE_VALUE" not in str(error.value)


def test_coordinator_bound_intake_directory_and_metadata_recovery(authority, tmp_path):
    directory = tmp_path / "synthetic-human-round"
    directory.mkdir()
    bundle = authority.bundles["A"]
    path = directory / "completed-response.json"
    path.write_bytes(raw(response(authority)))
    manifest = review.append_seal(
        directory / "intake-manifest.json",
        dict(
            schema_version="p021-human-intake-snapshot-v1",
            role="A",
            bundle_fingerprint=bundle.fingerprint,
            files={path.name: review.sha(path)},
        ),
    )
    result = review.validate_intake_directory(bundle, directory, manifest["fingerprint"])
    assert len(result.responses) == 100
    metadata = directory / ".DS_Store"
    metadata.write_bytes(b"synthetic OS metadata")
    with pytest.raises(review.ReviewBlocked):
        review.validate_intake_directory(bundle, directory, manifest["fingerprint"])
    assert (
        len(
            review.validate_intake_directory(
                bundle,
                directory,
                manifest["fingerprint"],
                recover_ds_store=True,
            ).responses
        )
        == 100
    )
    assert not metadata.exists()
    with pytest.raises(review.ReviewBlocked):
        review.validate_intake_directory(authority.bundles["B"], directory, manifest["fingerprint"])
    with pytest.raises(review.ReviewBlocked):
        review.validate_intake_directory(bundle, directory, "0" * 64)
    (directory / ".hidden").write_bytes(b"synthetic extra")
    with pytest.raises(review.ReviewBlocked):
        review.validate_intake_directory(
            bundle, directory, manifest["fingerprint"], recover_ds_store=True
        )


def test_symlinks_path_traversal_and_unexpected_intake_versions_rejected(authority, tmp_path):
    folder = tmp_path / "symlinks"
    folder.mkdir()
    (folder / "source").write_bytes(b"synthetic")
    (folder / "link").symlink_to(folder / "source")
    with pytest.raises(review.ReviewBlocked):
        review.verify_files(folder, {"source": review.sha(folder / "source")})
    with pytest.raises(review.ReviewBlocked):
        review.verify_files(folder, {"../outside": "0" * 64})
    with pytest.raises(review.ReviewBlocked):
        review.sha(tmp_path / review.WORKTREE_EXCEPTION)
    store = tmp_path / "store"
    review.freeze_intake(authority.bundles["A"], raw(response(authority)), store)
    (store / "A/v0003").mkdir()
    with pytest.raises(review.ReviewBlocked, match="VERSION_DRIFT"):
        review.freeze_intake(authority.bundles["B"], raw(response(authority, "B")), store)


def test_append_only_independent_acceptance_explicit_human_correction_and_original_preserved(
    authority, tmp_path
):
    store = tmp_path / "synthetic-intake"
    bundle = authority.bundles["A"]
    first_raw = raw(response(authority))
    first = review.freeze_intake(bundle, first_raw, store)
    path = store / "A/v0001"
    original = {p.name: p.read_bytes() for p in path.iterdir()}
    assert (path / "submission.json").read_bytes() == first_raw
    with pytest.raises(review.ReviewBlocked, match="IMMUTABLE"):
        review.freeze_intake(bundle, first_raw, store)
    for correction in (
        review.HumanCorrection("0" * 64, "Synthetic reason", "REAL_HUMAN_EXPLICIT_CORRECTION"),
        review.HumanCorrection(first["fingerprint"], "  ", "REAL_HUMAN_EXPLICIT_CORRECTION"),
        review.HumanCorrection(first["fingerprint"], "Synthetic reason", "wrong-attestation"),
    ):
        with pytest.raises(review.ReviewBlocked, match="CORRECTION_REQUIRED"):
            review.freeze_intake(bundle, first_raw, store, correction=correction)
    corrected = response(authority)
    corrected["responses"][0]["decision"] = "OUT_OF_SCOPE"
    second = review.freeze_intake(
        bundle,
        raw(corrected),
        store,
        correction=review.HumanCorrection(
            first["fingerprint"],
            "Synthetic human correction reason.",
            "REAL_HUMAN_EXPLICIT_CORRECTION",
        ),
    )
    assert second["version"] == 2 and second["previous_receipt_fingerprint"] == first["fingerprint"]
    assert {p.name: p.read_bytes() for p in path.iterdir()} == original
    assert review.verify_accepted(store / "A/v0002") == second
    b = review.freeze_intake(authority.bundles["B"], raw(response(authority, "B")), store)
    assert b["version"] == 1 and b["previous_receipt_fingerprint"] is None
    assert "reviewer_identity" not in canonical(first)
    assert all(not r["final_truth_created"] for r in (first, second, b))
    (path / "submission.json").write_bytes(b"altered")
    with pytest.raises(review.ReviewBlocked, match="DRIFT"):
        review.freeze_intake(bundle, raw(corrected), store)


def test_intake_distinct_pseudonyms_and_correction_without_original_rejected(authority, tmp_path):
    store = tmp_path / "store"
    a = response(authority)
    with pytest.raises(review.ReviewBlocked, match="CORRECTION_REQUIRED"):
        review.freeze_intake(
            authority.bundles["A"],
            raw(a),
            store,
            correction=review.HumanCorrection(
                "0" * 64,
                "Synthetic reason",
                "REAL_HUMAN_EXPLICIT_CORRECTION",
            ),
        )
    review.freeze_intake(authority.bundles["A"], raw(a), store)
    b = response(authority, "B")
    b["reviewer_identity"] = a["reviewer_identity"]
    with pytest.raises(review.ReviewBlocked, match="DISTINCT_REVIEWERS"):
        review.freeze_intake(authority.bundles["B"], raw(b), store)


@pytest.mark.parametrize(
    "extra", [".hidden", "unknown.json", "nested/.DS_Store", "another-directory"]
)
def test_arbitrary_unexpected_entry_blocks_even_if_metadata_recovery_enabled(tmp_path, extra):
    (tmp_path / "expected.json").write_bytes(b"synthetic expected")
    expected = {"expected.json": review.sha(tmp_path / "expected.json")}
    path = tmp_path / extra
    path.parent.mkdir(parents=True, exist_ok=True)
    if extra == "another-directory":
        path.mkdir()
    else:
        path.write_bytes(b"unexpected")
    with pytest.raises(review.ReviewBlocked, match="UNEXPECTED"):
        review.verify_files(tmp_path, expected, recover_ds_store=True)


def test_narrow_root_ds_store_recovery_requires_all_expected_hashes_and_sole_extra(tmp_path):
    source = tmp_path / "expected.json"
    source.write_bytes(b"synthetic expected")
    expected = {source.name: review.sha(source)}
    metadata = tmp_path / ".DS_Store"
    metadata.write_bytes(b"synthetic metadata")
    with pytest.raises(review.ReviewBlocked):
        review.verify_files(tmp_path, expected)
    source.write_bytes(b"drift")
    with pytest.raises(review.ReviewBlocked):
        review.verify_files(tmp_path, expected, recover_ds_store=True)
    assert metadata.exists()
    source.write_bytes(b"synthetic expected")
    (tmp_path / ".other").write_bytes(b"extra")
    with pytest.raises(review.ReviewBlocked):
        review.verify_files(tmp_path, expected, recover_ds_store=True)
    assert metadata.exists()
    (tmp_path / ".other").unlink()
    assert review.verify_files(tmp_path, expected, recover_ds_store=True)
    assert not metadata.exists()
    metadata.write_bytes(b"frozen metadata")
    expected[metadata.name] = review.sha(metadata)
    assert not review.verify_files(tmp_path, expected, recover_ds_store=True)
    assert metadata.exists()


@pytest.mark.parametrize(
    "marker",
    [
        "pair_id",
        "construction_intent",
        "mutation_case_id",
        "control_case_id",
        "static_predictions",
        "graph_predictions",
        "ai_results",
        "hybrid_predictions",
    ],
)
def test_hidden_metadata_unavailable_in_review_packages(authority, marker):
    bundle = authority.bundles["A"]
    protocol = sealed({marker: "synthetic prohibited metadata"})
    contaminated = seal(
        ReviewerABundle, **bundle.model_dump(exclude={"fingerprint", "protocol"}), protocol=protocol
    )
    with pytest.raises(ValueError, match="forbidden"):
        review.verify_blind_bundle(contaminated)


def test_ai_credential_boundary_and_source_only_capability(tmp_path):
    for event in ("socket.connect", "socket.getaddrinfo", "urllib.Request", "http.client.connect"):
        with pytest.raises(PermissionError):
            review.offline_guard(event, ())
    with pytest.raises(PermissionError):
        review.offline_guard("open", (".env.ai.local", "r", 0))
    for relative, mode, flags in (
        (review.PRIVATE / "coordinator/private-plan.json", "r", 0),
        (review.PRIVATE / "coordinator/construction-intent.json", "r", 0),
        (review.REVIEW / "A/bundle.json", "w", 1),
    ):
        with review.handoff_capability(tmp_path), pytest.raises(PermissionError):
            review.offline_guard("open", (str(tmp_path / relative), mode, flags))
    with review.handoff_capability(tmp_path):
        review.offline_guard("open", (str(tmp_path / review.REVIEW / "A/bundle.json"), "r", 0))
    tree = ast.parse(Path(review.__file__).read_text())
    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert not names.intersection(
        {"predict", "infer", "classify", "normalize_category", "evaluate", "fit"}
    )
    imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not any(
        n and ("provider" in n or "intelligence" in n or "construction" in n) for n in imports
    )


def test_only_exact_unstaged_exception_excluded():
    preserved = f" D {review.WORKTREE_EXCEPTION}\0".encode()
    review.scientific_status(preserved)
    for unexpected in (
        b"",
        f"D  {review.WORKTREE_EXCEPTION}\0".encode(),
        preserved + b" M unrelated.txt\0",
        preserved + b"?? other-index.html\0",
    ):
        with pytest.raises(review.ReviewBlocked):
            review.scientific_status(unexpected)
    review.scientific_status(preserved + b"?? intended.py\0", ("intended.py",))


def test_instruction_prohibitions_privacy_and_protocol_boundaries():
    for role in ("A", "B"):
        text = review.instructions(role).decode()
        for forbidden in (
            "pair_id",
            "construction_intent",
            "mutation",
            "control case",
            "prediction",
        ):
            assert forbidden not in text
    assert PROTOCOL["semantic_normalization"] is False
    assert (
        PROTOCOL["provider_calls"]
        == PROTOCOL["connectivity_calls"]
        == PROTOCOL["paid_spend_usd"]
        == 0
    )
    assert PROTOCOL["agreement"]["executed"] is PROTOCOL["adjudication"]["executed"] is False
    assert PROTOCOL["final_semantic_human_truth"] == "NOT_CREATED"
