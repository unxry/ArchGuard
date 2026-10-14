"""Closure regressions: no fitting, prediction, evaluation or paid replication."""

import copy
import io
import socket
from pathlib import Path

import pytest

from archguard.benchmark.oss.models import canonical
from archguard.infrastructure import thesis_closure as c


@pytest.fixture(scope="module")
def bundle():
    return c.build()


def test_all_mandatory_items_bind_real_source_tests_and_evidence(bundle):
    c.validate_bundle(bundle)
    assert len(bundle["capability-registry.json"]["rows"]) == len(c.CAPABILITIES)


def test_missing_capability_fails_closure(bundle):
    broken = copy.deepcopy(bundle)
    broken["capability-registry.json"]["rows"].pop()
    with pytest.raises(ValueError, match="MISSING_MANDATORY"):
        c.validate_bundle(broken)


def test_unimplemented_capability_fails_closure(bundle):
    broken = copy.deepcopy(bundle)
    broken["capability-registry.json"]["rows"][0]["status"] = "PLANNED"
    with pytest.raises(ValueError, match="UNIMPLEMENTED"):
        c.validate_bundle(broken)


def test_documentation_only_phantom_symbol_fails():
    with pytest.raises(ValueError, match="MISSING_IMPLEMENTATION_OR_TEST_SYMBOL"):
        c.binding("src/archguard/parsing/tree_sitter_adapters.py", "NonexistentParser")


@pytest.mark.parametrize("change", ["missing", "duplicate", "SEC"])
def test_rule_set_is_exact_and_has_no_security(bundle, change):
    broken = copy.deepcopy(bundle)
    rows = broken["rule-coverage.json"]["rows"]
    if change == "missing":
        rows.pop()
    else:
        rows[0]["rule_id"] = rows[1]["rule_id"] if change == "duplicate" else "SEC001"
    with pytest.raises(ValueError, match="RULE_SET"):
        c.validate_bundle(broken)


def test_each_rule_retains_all_methods_and_imperfect_strata(bundle):
    rows = bundle["rule-coverage.json"]["rows"]
    assert all(r["N"] == 20 and r["positive"] == r["negative"] == 10 for r in rows)
    arch104 = next(r for r in rows if r["rule_id"] == "ARCH104")
    assert arch104["methods"]["A7"]["FN"] == 1
    arch003 = next(r for r in rows if r["rule_id"] == "ARCH003")
    assert arch003["scientific_owner"] == "GRAPH"
    assert arch003["deterministic"] and arch003["evidence_type"] == "DIRECT_CYCLE_PROOF"


def test_java_typescript_final_strata_and_js_tsx_scope(bundle):
    facts = bundle["numeric-facts.json"]
    assert facts["languages"] == {"JAVA": 150, "TYPESCRIPT": 150}
    assert facts["language_metrics"]["JAVA"]["A7"]["FN"] == 1
    assert facts["language_metrics"]["TYPESCRIPT"]["A7"]["FN"] == 0
    assert bundle["scientific-registry.json"]["supported_languages"] == ["JAVA", "TYPESCRIPT"]


@pytest.mark.parametrize("change", ["no_artifact", "no_fingerprint", "no_scope", "no_limit"])
def test_supported_claims_cannot_dangle(bundle, change):
    broken = copy.deepcopy(bundle)
    claim = broken["claim-registry.json"]["rows"][0]
    if change == "no_artifact":
        claim["evidence_artifacts"] = []
    elif change == "no_fingerprint":
        claim["fingerprints"] = []
    else:
        claim["scope" if change == "no_scope" else "limitations"] = ""
    with pytest.raises(ValueError, match="DANGLING_CLAIM"):
        c.validate_bundle(broken)


@pytest.mark.parametrize("rq", ["RQ2", "RQ6"])
def test_partial_rqs_cannot_be_promoted(bundle, rq):
    broken = copy.deepcopy(bundle)
    broken["numeric-facts.json"]["rq_status"][rq] = "ANSWERED"
    with pytest.raises(ValueError, match="RQ_OVERCLAIM"):
        c.validate_bundle(broken)


def test_hypothesis_and_context_claims_remain_qualified(bundle):
    facts = bundle["numeric-facts.json"]
    assert "controlled final benchmark N=300" in facts["hypothesis_conclusion"]
    assert "modestly lower" in facts["context_qualification"]
    assert facts["technical_missing_is_semantic_abstention"] is False
    assert facts["primary"]["A3"]["N"] == 300
    assert facts["primary"]["A3"]["technical_missing"] == 2
    assert facts["resources"]["invoice"] is None


def test_numeric_documents_detect_one_digit_drift(bundle, tmp_path, monkeypatch):
    expected = c.metric_table(bundle["numeric-facts.json"]["primary"])
    doc = tmp_path / "facts.md"
    doc.write_text(expected.replace("0.993333333333", "0.993333333334", 1))
    monkeypatch.setattr(c, "documents", lambda _: {doc: expected})
    with pytest.raises(ValueError, match="DOCUMENT_NUMERIC_OR_CLAIM_DRIFT"):
        c.document_gate(bundle)


def test_generation_is_deterministic_and_has_no_new_science(bundle, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Forbidden computation or provider activity")

    from archguard.infrastructure import final_evaluation as f

    for name in ("prepare", "predict", "open_truth", "evaluate"):
        monkeypatch.setattr(f, name, forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    original_open = io.open

    def checked_open(file, *args, **kwargs):
        if isinstance(file, (str, Path)):
            assert not Path(file).name.startswith(".env")
        return original_open(file, *args, **kwargs)

    monkeypatch.setattr(io, "open", checked_open)
    second = c.build()
    assert canonical(second) == canonical(bundle)
    assert not any("timestamp" in canonical(v) for v in second.values())


@pytest.mark.parametrize(
    "material",
    [
        '{"case_id":"private-unit"}',
        '{"execution_id":"private-unit"}',
        '{"raw_response":"private"}',
        "Bearer " + "x" * 20,
    ],
)
def test_public_privacy_blocks_case_identity_raw_data_and_credentials(tmp_path, material):
    p = tmp_path / "public.json"
    p.write_text(material)
    with pytest.raises(ValueError, match="PUBLIC_PRIVACY_FAILURE"):
        c.privacy_audit([p])


def test_credential_and_private_paths_cannot_be_public_bindings():
    for path in (".env.ai.local", "/tmp/credentials.json", "../credentials.json"):
        with pytest.raises(ValueError, match="INVALID_PUBLIC_BINDING"):
            c.safe_path(path)


def test_quality_must_precede_complete_declaration(bundle, monkeypatch):
    monkeypatch.setattr(c, "build", lambda: bundle)
    with pytest.raises(ValueError, match="QUALITY_INCOMPLETE"):
        c.accept({"make_check": "FAIL", "full_tests": 0})


def test_accept_freezes_manifest_and_rejects_policy_drift(bundle, tmp_path, monkeypatch):
    monkeypatch.setattr(c, "ROOT", tmp_path / "registries")
    monkeypatch.setattr(c, "DOC", tmp_path / "docs")
    doc = c.DOC / "facts.md"
    monkeypatch.setattr(c, "DOCUMENTS", (doc,))
    monkeypatch.setattr(c, "documents", lambda _: {doc: "Frozen N=300\n"})
    monkeypatch.setattr(c, "build", lambda: bundle)
    monkeypatch.setattr(c, "worktree_gate", lambda: None)
    monkeypatch.setattr(c, "prior_integrity", lambda: None)
    from archguard.infrastructure import final_evaluation as f

    monkeypatch.setattr(f, "verify_acquisition", lambda: None)
    c.generate()
    (c.DOC / "PROMPT_026.md").write_text("Synthetic acceptance fixture\n")
    quality = {
        name: "PASS"
        for name in (
            "make_check",
            "ruff",
            "format",
            "strict_mypy",
            "regressions",
            "privacy",
            "secret_audit",
            "numeric_consistency",
            "claim_traceability",
            "artifact_fingerprints",
            "overclaim_audit",
            "diff_check",
            "double_run",
            "acquisition_integrity",
        )
    } | {"full_tests": 1, "p026_tests": 1, "provider_calls": 0, "credential_reads": 0}
    accepted = c.accept(quality)
    assert accepted["CORE_THESIS_COMPLETE"] is True
    assert c.accept(quality) == accepted
    manifest = c.io.read_seal(c.ROOT / "closure-manifest.json")
    manifest.pop("fingerprint")
    manifest["provider_calls"] = 1
    (c.ROOT / "closure-manifest.json").write_text(canonical(c.sealed(manifest)) + "\n")
    with pytest.raises(ValueError, match="MANIFEST_DRIFT"):
        c.verify()
