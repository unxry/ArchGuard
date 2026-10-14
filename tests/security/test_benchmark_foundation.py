"""P030 construction checks and invented-label unit tests; never benchmark predictions/truth."""

import copy
from collections import Counter
from pathlib import Path

import pytest
from pydantic import ValidationError

from archguard.infrastructure.security_benchmark import intake
from archguard.security_benchmark import foundation, protocol, templates

ROWS = templates.generate()
FAKE = "sc-" + "a" * 24
assert FAKE not in {r["case_id"] for r in ROWS}


@pytest.fixture(scope="module")
def built():
    return foundation.material()


def test_counts_uniqueness_separation_determinism(built):
    rows, packets, audit = built
    assert len(rows) == 300 and len(packets) == 600
    assert audit["counts"] == dict(
        total=300,
        DEV=100,
        FINAL=200,
        JAVA=150,
        TYPESCRIPT=150,
        MUTATION_INTENT=150,
        CONTROL_INTENT=150,
        rules=10,
        cases_per_rule=30,
        projects=300,
        templates=300,
    )
    assert not any(audit["separation"]["overlaps"].values())
    assert built == foundation.material()
    assert foundation.private_material(rows, packets) == foundation.private_material(
        *foundation.material()[:2]
    )


@pytest.mark.parametrize("rule", protocol.RULES)
@pytest.mark.parametrize("split,each", [("DEV", 5), ("FINAL", 10)])
def test_rule_language_intent_balance(rule, split, each):
    cases = [r for r in ROWS if (r["rule_id"], r["split"]) == (rule, split)]
    assert Counter(r["language"] for r in cases) == {"JAVA": each, "TYPESCRIPT": each}
    assert Counter(r["construction_intent"] for r in cases) == {
        "MUTATION_INTENT": each,
        "CONTROL_INTENT": each,
    }


@pytest.mark.parametrize("case", ROWS, ids=[r["case_id"] for r in ROWS])
def test_normal_parse_iam_and_source_location(case):
    receipt = intake((case,))
    assert receipt["parse_success"] == receipt["IAM_valid"] == 1
    assert receipt["source_location_mapping"] == "PASS"


def test_ts_deserialization_keeps_unsupported_separate_from_truth(built):
    rows, packets, _ = built
    cases = [r for r in rows if (r["rule_id"], r["language"]) == ("SEC005", "TYPESCRIPT")]
    assert len(cases) == 15
    assert all(
        r["RULE_LANGUAGE_SCOPE_EXPECTATION"] == "UNSUPPORTED_BY_CURRENT_DETECTOR" for r in cases
    )
    for r in cases:
        for slot in ("A", "B"):
            raw = packets[f"packets/{slot}/{r['case_id']}.json"]
            assert "RULE_LANGUAGE_SCOPE_EXPECTATION" not in str(raw)
            assert set(raw["evidence"]["label_choices"]) == set(protocol.TruthLabel)


def test_all_review_packets_bind_same_evidence_independent_destinations(built):
    rows, packets, audit = built
    assert audit["blindness"]["status"] == "PASS"
    for r in rows:
        a, b = [
            protocol.ReviewPacket.model_validate(packets[f"packets/{s}/{r['case_id']}.json"])
            for s in ("A", "B")
        ]
        assert a.evidence == b.evidence
        assert a.evidence_fingerprint == b.evidence_fingerprint
        assert a.response_destination != b.response_destination
        assert a.evidence.source_files and a.evidence.rule_definition


@pytest.mark.parametrize(
    "field",
    [
        "construction_intent",
        "expected",
        "split",
        "detector_output",
        "truth",
        "other_reviewer_response",
    ],
)
def test_reviewer_packet_rejects_leaked_metadata(built, field):
    raw = copy.deepcopy(next(iter(built[1].values())))
    raw["evidence"][field] = "hidden"
    with pytest.raises(ValidationError):
        foundation.blindness_audit({"packet": raw})


@pytest.mark.parametrize(
    "field", ["project_id", "template_fingerprint", "case_fingerprint", "source_bundle_fingerprint"]
)
def test_cross_split_duplicate_rejected(field):
    cases = copy.deepcopy(ROWS)
    dev = next(r for r in cases if r["split"] == "DEV")
    final = next(r for r in cases if r["split"] == "FINAL")
    final[field] = dev[field]
    with pytest.raises(ValueError, match="separation"):
        foundation.separation(cases)


def test_case_comment_leakage_rejected(built):
    raw = copy.deepcopy(next(iter(built[1].values())))
    raw["evidence"]["source_files"][0]["content"] = (
        "// expected positive\n" + raw["evidence"]["source_files"][0]["content"]
    )
    from archguard.benchmark.oss.models import digest

    raw["evidence_fingerprint"] = digest(raw["evidence"])
    with pytest.raises(ValueError, match="comment leakage"):
        foundation.blindness_audit({"packet": raw})


def response(slot="A", label="POSITIVE", case=FAKE):
    return protocol.ReviewResponse(reviewer_slot=slot, case_id=case, label=label, completed=True)


@pytest.mark.parametrize("label", list(protocol.TruthLabel))
def test_human_response_labels_and_agreement_preserve_enum(label):
    a, b = response(label=label), response("B", label)
    protocol.validate_submission((a,), "A", {FAKE})
    assert protocol.reconcile(a, b)["final_label"] == label
    assert not protocol.reconcile(a, b)["requires_human_adjudication"]


@pytest.mark.parametrize(
    "change",
    [
        {"label": "MUTATION"},
        {"reviewer_slot": "X"},
        {"completed": True},
        {"label": "NEGATIVE", "completed": False},
        {"reviewer_name": "Person"},
    ],
)
def test_invalid_response_schema(change):
    raw = dict(reviewer_slot="A", case_id=FAKE)
    with pytest.raises(ValidationError):
        protocol.ReviewResponse.model_validate(raw | change)


def test_missing_duplicate_wrong_slot_or_incomplete_submission():
    for rows, ids in (
        ((), {FAKE}),
        ((response(), response()), {FAKE}),
        ((response("B"),), {FAKE}),
        ((protocol.ReviewResponse(reviewer_slot="A", case_id=FAKE),), {FAKE}),
    ):
        with pytest.raises(ValueError):
            protocol.validate_submission(rows, "A", ids)


def test_conflict_requires_independent_human_adjudication_not_intent_or_ai():
    a, b = response(), response("B", "NEGATIVE")
    unresolved = protocol.reconcile(a, b)
    assert unresolved["final_label"] is None and unresolved["requires_human_adjudication"]
    solved = protocol.reconcile(a, b, protocol.TruthLabel.UNCERTAIN)
    assert solved["A"] == "POSITIVE" and solved["B"] == "NEGATIVE"
    assert solved["conflict"] and solved["final_label"] == "UNCERTAIN"
    with pytest.raises(TypeError):
        protocol.reconcile(a, b, construction_intent="MUTATION_INTENT")
    with pytest.raises(TypeError):
        protocol.reconcile(a, b, detector_prediction="SUPPORTED")
    with pytest.raises(TypeError):
        protocol.reconcile(a, b, AI_label="POSITIVE")


def test_agreement_kappa_and_zero_denominators():
    L = protocol.TruthLabel
    r = protocol.agreement((L.POSITIVE, L.NEGATIVE), (L.POSITIVE, L.UNCERTAIN))
    assert r["raw_agreement"] == 0.5 and r["conflict_count"] == 1
    assert r["cohens_kappa"] == pytest.approx(1 / 3)
    assert protocol.agreement((), ())["cohens_kappa"] is None
    assert protocol.agreement((L.POSITIVE,), (L.POSITIVE,))["cohens_kappa"] is None


@pytest.mark.parametrize(
    "statuses,execution,applicable,expected",
    [
        (("SUPPORTED",), "COMPLETE", True, "DEFINITIVE_POSITIVE"),
        (("CONFIRMED_PATTERN",), "PARTIAL", True, "DEFINITIVE_POSITIVE"),
        (("POTENTIAL",), "COMPLETE", True, "POTENTIAL"),
        (("INSUFFICIENT_EVIDENCE",), "COMPLETE", True, "INSUFFICIENT_EVIDENCE"),
        (("NOT_APPLICABLE",), "COMPLETE", False, "NOT_APPLICABLE"),
        ((), "COMPLETE", True, "DEFINITIVE_NEGATIVE"),
        ((), "COMPLETE", False, "NOT_APPLICABLE"),
        ((), "PARTIAL", True, "PARTIAL"),
        ((), "FAILED", True, "FAILED"),
        ((), "UNSUPPORTED", False, "UNSUPPORTED"),
        (("POTENTIAL", "SUPPORTED"), "PARTIAL", True, "DEFINITIVE_POSITIVE"),
    ],
)
def test_frozen_output_mapping(statuses, execution, applicable, expected):
    assert protocol.map_outcome(statuses, execution, applicable) == expected


def test_synthetic_metrics_confusion_abstention_unsupported_oos():
    T, Outcome = protocol.TruthLabel, protocol.Outcome
    r = protocol.metrics(
        (
            (T.POSITIVE, Outcome.DEFINITIVE_POSITIVE),
            (T.POSITIVE, Outcome.DEFINITIVE_NEGATIVE),
            (T.NEGATIVE, Outcome.DEFINITIVE_POSITIVE),
            (T.NEGATIVE, Outcome.DEFINITIVE_NEGATIVE),
            (T.POSITIVE, Outcome.POTENTIAL),
            (T.NEGATIVE, Outcome.UNSUPPORTED),
            (T.OUT_OF_SCOPE, Outcome.DEFINITIVE_POSITIVE),
        )
    )
    assert [r[x] for x in ("TP", "FP", "TN", "FN")] == [1, 1, 1, 1]
    assert (
        r["precision"] == r["recall"] == r["F1"] == r["specificity"] == r["FPR"] == r["FNR"] == 0.5
    )
    assert r["effective_correctness"] == 2 / 6 and r["unified_correctness"] == 2 / 7
    assert r["effective_positive_recovery"] == 1 / 3
    assert r["nondefinitive_binary"] == 2 and r["excluded_truth"] == 1
    assert r["outcomes"]["POTENTIAL"] == r["outcomes"]["UNSUPPORTED"] == 1


def test_empty_and_all_nondefinitive_metrics_are_not_invented_negatives():
    T, Outcome = protocol.TruthLabel, protocol.Outcome
    r = protocol.metrics(())
    assert all(
        r[k] is None
        for k in ("precision", "recall", "F1", "FPR", "FNR", "specificity", "effective_correctness")
    )
    r = protocol.metrics(((T.POSITIVE, Outcome.POTENTIAL), (T.NEGATIVE, Outcome.PARTIAL)))
    assert r["FN"] == r["TN"] == 0
    assert r["definitive_coverage"] == r["effective_correctness"] == 0
    assert r["recall"] is None


def test_prediction_source_capability_excludes_truth_intent_and_other_split(tmp_path, monkeypatch):
    root = tmp_path / "FINAL" / "sources"
    source = root / FAKE / "src/Unit.ts"
    source.parent.mkdir(parents=True)
    source.write_text("export const x = 1;")
    private = tmp_path / "coordinator"
    private.mkdir()
    (private / "truth.json").write_text("private")
    roster = (
        {
            "case_id": FAKE,
            "rule_id": "SEC002",
            "language": "TYPESCRIPT",
            "source_paths": ["src/Unit.ts"],
        },
    )
    capability = foundation.PredictionInputs(root, roster)
    original = Path.read_text

    def limited(path, *args, **kwargs):
        assert path == source, "non-source file opened"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", limited)
    assert capability.read(f"{FAKE}/src/Unit.ts").startswith("export")
    for p in (
        "../../coordinator/truth.json",
        str(private / "truth.json"),
        "responses/A.json",
        "DEV/src/Unit.ts",
    ):
        with pytest.raises(ValueError):
            capability.read(p)
    with pytest.raises(ValueError):
        foundation.PredictionInputs(root, (roster[0] | {"construction_intent": "hidden"},))


def test_prediction_worker_rejects_symlink_escape(tmp_path):
    root = tmp_path / "sources"
    (root / FAKE / "src").mkdir(parents=True)
    outside = tmp_path / "truth.ts"
    outside.write_text("private")
    (root / FAKE / "src/Unit.ts").symlink_to(outside)
    with pytest.raises(ValueError, match="unsafe"):
        foundation.PredictionInputs(
            root,
            (
                {
                    "case_id": FAKE,
                    "rule_id": "SEC002",
                    "language": "TYPESCRIPT",
                    "source_paths": ["src/Unit.ts"],
                },
            ),
        )


def test_final_join_requires_frozen_predictions_and_explicit_later_stage():
    with pytest.raises(ValueError):
        foundation.truth_join_gate(False, "SECURITY_FINAL_POST_PREDICTION_TRUTH_JOIN")
    with pytest.raises(ValueError):
        foundation.truth_join_gate(True, "P030")
    foundation.truth_join_gate(True, "SECURITY_FINAL_POST_PREDICTION_TRUTH_JOIN")


def test_generator_dependency_and_protocol_mapping():
    assert foundation.dependency_audit()["status"] == "PASS"
    assert not protocol.metric_protocol()["post_truth_remapping_allowed"]
    assert not protocol.human_protocol()["AI_labels_permitted"]
    assert not templates.generate()[0].get("truth")


def test_rule_construction_api_diversity_without_predictions():
    def text(rule):
        return "\n".join(
            s["content"] for r in ROWS if r["rule_id"] == rule for s in r["source_files"]
        )

    required = {
        "SEC001": ["apiKey", "PRIVATE KEY", "YOUR_API_KEY", "checksum"],
        "SEC002": [
            "createStatement",
            "prepareStatement",
            "client.query",
            "$queryRawUnsafe",
            "setString",
        ],
        "SEC003": ["ProcessBuilder", "sh", "execFile", "shell:false"],
        "SEC004": ["normalize", "startsWith", "path.sep", "readFileSync"],
        "SEC005": ["ObjectInputStream", "readObject", "readTree", "JSON.parse", "decode"],
        "SEC006": ["HttpClient", "hostname", "endsWith", "includes", "req.query.other"],
        "SEC007": ["innerHTML", "textContent", "DOMPurify.sanitize", "forHtml"],
        "SEC008": ["DES", "RC4", "ECB", "MD5", "sha1", "AES/GCM", "checksum", "selectAlgorithm"],
        "SEC009": [
            "resetToken",
            "sessionToken",
            "nonce",
            "simulation",
            "sample",
            "SecureRandom",
            "randomBytes",
            "generateValue",
        ],
        "SEC010": [
            "ScriptEngineManager",
            "eval",
            "new Function",
            "runInNewContext",
            "Class.forName",
            "Reflect.get",
        ],
    }
    for rule, apis in required.items():
        assert all(api in text(rule) for api in apis), rule


def test_outcome_invalid_values_and_conflicting_response_rejected():
    with pytest.raises(ValueError):
        protocol.map_outcome(("INVENTED",), "COMPLETE", True)
    with pytest.raises(ValueError):
        protocol.map_outcome((), "IMPLEMENTED_V2", True)
    with pytest.raises(ValueError):
        protocol.metrics((("INVENTED", protocol.Outcome.POTENTIAL),))
    with pytest.raises(ValueError):
        protocol.reconcile(response(), response("B", "NEGATIVE"), "AI_LABEL")
    with pytest.raises(ValidationError):
        protocol.ReviewResponse(reviewer_slot="A", case_id=FAKE, completed="true", label="POSITIVE")


def test_supported_scope_is_supplement_and_no_results_exist():
    frozen = protocol.metric_protocol()
    assert frozen["primary_view"] == "ALL_CASES_UNIFIED_WITH_COMPLETENESS_PENALTY"
    assert "supported language-rule scope" in frozen["supplemental_views"]
    assert frozen["results"] == "NOT_EVALUATED"
    assert frozen["zero_denominator"] is None


@pytest.mark.parametrize(
    "coverage,statuses,expected",
    [
        ("SUPPORTED_PARTIAL_V2_SCOPE", (), "PARTIAL"),
        ("SUPPORTED_PARTIAL_V2_SCOPE", ("SUPPORTED",), "DEFINITIVE_POSITIVE"),
        ("SUPPORTED_PARTIAL_V2_SCOPE", ("POTENTIAL",), "POTENTIAL"),
        ("CONTRACT_ONLY", (), "UNSUPPORTED"),
        ("FAILED", (), "FAILED"),
    ],
)
def test_actual_p029_receipt_mapping_never_infers_absence_from_applicable_rules(
    coverage, statuses, expected
):
    receipt = dict(
        requested_rules=["SEC005"],
        applicable_rules=[],
        unsupported_rules=[],
        findings=[dict(rule_id="SEC005", status=s) for s in statuses],
        analysis_metadata=dict(
            coverage={
                "SEC005": dict(status=coverage, evaluated=coverage == "SUPPORTED_PARTIAL_V2_SCOPE")
            }
        ),
    )
    assert protocol.map_p029_outcome(receipt, "SEC005") == expected


def test_p029_receipt_rejects_unknown_coverage_or_unrequested_rule():
    with pytest.raises(ValueError):
        protocol.map_p029_outcome({}, "SEC001")
    with pytest.raises(ValueError):
        protocol.map_p029_outcome(
            {"requested_rules": ["SEC001"], "analysis_metadata": {}}, "SEC001"
        )
