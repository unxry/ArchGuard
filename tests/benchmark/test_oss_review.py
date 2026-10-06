"""Synthetic human-shaped vectors only; real OSS cases remain unannotated."""

import ast
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from archguard.benchmark.oss.models import SampleFreeze, canonical, digest, seal
from archguard.benchmark.oss.review import (
    AdjudicationInput,
    PinnedEvidence,
    ReviewInput,
    active_reviews,
    append_reviews,
    freeze_reviews,
    original_evidence,
    review_report,
    validate_catalog,
)
from archguard.cli import main
from archguard.infrastructure.oss_benchmark import load_corpus, source_path, write_new
from archguard.infrastructure.oss_review import (
    atomic_directory,
    export_adjudication,
    import_review_batch,
    initial_catalog,
    prepare_bundles,
    publish_freeze,
    publish_store,
    supplement_context,
    verify_evidence,
)
from archguard.oss_cli import load_sample
from tests.benchmark.test_oss_benchmark import local_corpus  # noqa: F401

ROOT = Path(__file__).parents[2]


@pytest.fixture
def context(local_corpus):  # noqa: F811
    bound, _, cache, _, _, _, sample, _ = local_corpus
    return bound, sample, cache, initial_catalog(bound, sample)


def review(context, index=0, reviewer="human-fixture-a", label="POSITIVE", **changes):
    _, sample, _, catalog = context
    packet = sample.packets[index]
    revision = next(
        p for p in reversed(catalog.packets) if p.annotation_case_id == packet.annotation_case_id
    )
    return ReviewInput.model_validate(
        {
            "annotation_case_id": packet.annotation_case_id,
            "packet_fingerprint": revision.fingerprint,
            "packet_revision": revision.revision,
            "reviewer_id": reviewer,
            "label": label,
            "rationale": "Synthetic test rationale: inspect unit declaration.",
            "evidence": original_evidence(packet, revision),
            "uncertainty": "CLEAR" if label in {"POSITIVE", "NEGATIVE"} else "AMBIGUOUS",
            "attestation": "HUMAN_REVIEW_COMPLETED",
        }
        | changes
    )


def adjudication(context, store, index=0, **changes):
    decision = review(context, index).model_dump(mode="json")
    decision.pop("reviewer_id")
    decision.pop("supersedes_review_id")
    decision.update(
        adjudicator_id="human-fixture-c",
        review_ids=tuple(
            r.fingerprint for r in active_reviews(store)[decision["annotation_case_id"]]
        ),
    )
    return AdjudicationInput.model_validate(decision | changes)


def batch(sample, reviews=(), adjudications=()):
    return {
        "sample_fingerprint": sample.fingerprint,
        "reviews": [r.model_dump(mode="json") for r in reviews],
        "adjudications": [a.model_dump(mode="json") for a in adjudications],
    }


def test_real_empty_scope_not_negative_or_frozen():
    bound = load_corpus(
        ROOT / "experiments/oss/oss-corpus-v1.json",
        ROOT / "experiments/oss/selection-protocol-v1.json",
        ROOT / "experiments/oss/corpus-freeze.json",
    )
    sample = load_sample(
        ROOT / "experiments/oss/annotation/sample-v1.json",
        ROOT / "experiments/oss/annotation/sample-freeze-v1.json",
    )
    catalog = initial_catalog(bound, sample)
    store = append_reviews(sample, catalog)
    report = review_report(sample, store)
    assert report.counts.total == report.counts.unreviewed == 40
    assert report.counts.negative == report.counts.binary_eligible == report.human_reviewers == 0
    assert report.readiness == "WAITING_FOR_HUMAN_REVIEW"
    assert report.full_hybrid_readiness == "NOT_READY"
    assert report.agreement.agreement_rate is report.agreement.cohen_kappa is None
    assert {g.key: g.counts.total for g in report.by_language} == {"JAVA": 20, "TYPESCRIPT": 20}
    assert all(g.counts.total == 8 for g in report.by_rule)
    assert all(g.counts.total == 5 for g in report.by_repository)
    assert all(c.final_label == "NOT_ANNOTATED" for c in store.cases)
    with pytest.raises(ValueError, match="freeze requires"):
        freeze_reviews(sample, catalog, store)
    with pytest.raises(ValueError, match="unresolved"):
        review_report(sample, store, frozen=True)


@pytest.mark.parametrize("label", ["POSITIVE", "NEGATIVE", "UNCERTAIN", "OUT_OF_SCOPE"])
def test_independent_agreement_eligibility(context, label):
    _, sample, _, catalog = context
    single = append_reviews(sample, catalog, (review(context, label=label),))
    assert single.cases[0].status == "SINGLE_REVIEW"
    assert single.cases[0].provisional_label == label
    assert single.cases[0].final_label == "NOT_ANNOTATED"
    assert review_report(sample, single).counts.binary_eligible == 0
    result = append_reviews(
        sample,
        catalog,
        (review(context, reviewer="human-fixture-b", label=label),),
        previous=single,
    )
    assert result.cases[0].status == "DOUBLE_REVIEW"
    assert result.cases[0].binary_eligible == (label in {"POSITIVE", "NEGATIVE"})
    assert review_report(sample, result).agreement.nonbinary_pairs == (
        label in {"UNCERTAIN", "OUT_OF_SCOPE"}
    )
    with pytest.raises(ValueError, match="freeze requires"):
        freeze_reviews(sample, catalog, single)


def test_conflict_third_human_and_amendments(context):
    _, sample, _, catalog = context
    a, b = review(context), review(context, reviewer="human-fixture-b", label="NEGATIVE")
    conflict = append_reviews(sample, catalog, (a, b))
    assert review_report(sample, conflict).readiness == "ADJUDICATION_REQUIRED"
    assert conflict.cases[0].final_label == "NOT_ANNOTATED"
    with pytest.raises(ValueError, match="distinct third"):
        append_reviews(
            sample,
            catalog,
            adjudications=(adjudication(context, conflict, adjudicator_id=a.reviewer_id),),
            previous=conflict,
        )
    decision = adjudication(context, conflict)
    resolved = append_reviews(sample, catalog, adjudications=(decision,), previous=conflict)
    assert resolved.cases[0].status == "ADJUDICATED"
    assert resolved.cases[0].binary_eligible
    correction = adjudication(
        context,
        resolved,
        label="UNCERTAIN",
        supersedes_adjudication_id=resolved.adjudications[0].fingerprint,
    )
    corrected = append_reviews(sample, catalog, adjudications=(correction,), previous=resolved)
    assert len(corrected.adjudications) == 2
    assert corrected.adjudications[0] == resolved.adjudications[0]
    assert not corrected.cases[0].binary_eligible
    amendment = review(
        context, label="UNCERTAIN", supersedes_review_id=resolved.reviews[0].fingerprint
    )
    changed = append_reviews(sample, catalog, (amendment,), previous=corrected)
    assert changed.reviews[:2] == resolved.reviews
    assert changed.cases[0].status == "ADJUDICATION_REQUIRED"
    assert len(changed.adjudications) == 2
    with pytest.raises(ValueError, match="current independent"):
        append_reviews(
            sample,
            catalog,
            adjudications=(
                AdjudicationInput.model_validate(
                    decision.model_dump(mode="json")
                    | {
                        "supersedes_adjudication_id": corrected.adjudications[-1].fingerprint,
                        "rationale": "Synthetic stale pair test",
                    }
                ),
            ),
            previous=changed,
        )
    agreed = review(context, label="NEGATIVE", supersedes_review_id=changed.reviews[-1].fingerprint)
    final = append_reviews(sample, catalog, (agreed,), previous=changed)
    assert final.cases[0].status == "DOUBLE_REVIEW"
    assert final.cases[0].final_label == "NEGATIVE"


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate",
        "same-human",
        "third-review",
        "stale-amendment",
        "fake-amendment",
        "packet",
        "revision",
        "evidence",
    ],
)
def test_invalid_review_history(context, mutation):
    _, sample, _, catalog = context
    a = review(context)
    initial = append_reviews(sample, catalog, (a,))
    b = review(context, reviewer="human-fixture-b")
    if mutation == "duplicate":
        changed = a
    elif mutation == "same-human":
        changed = review(context, label="NEGATIVE")
    elif mutation == "third-review":
        initial = append_reviews(sample, catalog, (b,), previous=initial)
        changed = review(context, reviewer="human-fixture-d")
    elif mutation == "stale-amendment":
        initial = append_reviews(
            sample,
            catalog,
            (
                review(
                    context, label="NEGATIVE", supersedes_review_id=initial.reviews[0].fingerprint
                ),
            ),
            previous=initial,
        )
        changed = review(context, supersedes_review_id=initial.reviews[0].fingerprint)
    elif mutation == "fake-amendment":
        changed = review(context, reviewer="human-fixture-b", supersedes_review_id="f" * 64)
    elif mutation == "packet":
        changed = review(context, packet_fingerprint="f" * 64, reviewer="human-fixture-b")
    elif mutation == "revision":
        changed = review(context, packet_revision=2, reviewer="human-fixture-b")
    else:
        raw = a.evidence[0].model_dump(mode="json") | {"sha256": "f" * 64}
        changed = review(
            context, evidence=(PinnedEvidence.model_validate(raw),), reviewer="human-fixture-b"
        )
    with pytest.raises(ValueError):
        append_reviews(sample, catalog, (changed,), previous=initial)


@pytest.mark.parametrize(
    "changes",
    [
        {"evidence": ()},
        {"rationale": " "},
        {"attestation": None},
        {"reviewer_id": None},
        {"reviewer_id": "person@example.com"},
    ],
)
def test_binary_human_contract_requires_actual_shape(context, changes):
    with pytest.raises(ValidationError):
        review(context, **changes)


def test_agreement_kappa_and_complete_freeze(context):
    _, sample, _, catalog = context
    reviews = tuple(
        review(context, i, reviewer=who, label=label)
        for i, label in enumerate(("POSITIVE", "NEGATIVE", "UNCERTAIN", "OUT_OF_SCOPE", "NEGATIVE"))
        for who in ("human-fixture-a", "human-fixture-b")
    )
    store = append_reviews(sample, catalog, reviews)
    report = review_report(sample, store)
    assert report.readiness == "SECOND_REVIEW_COMPLETE"
    assert report.agreement.binary_pairs == 3
    assert report.agreement.nonbinary_pairs == 2
    assert report.agreement.agreement_rate == report.agreement.cohen_kappa == 1
    assert report.counts.binary_eligible == 3
    frozen = freeze_reviews(sample, catalog, store)
    assert frozen.review_fingerprints == tuple(r.fingerprint for r in store.reviews)
    assert frozen.resolved_cases == store.cases
    assert review_report(sample, store, frozen=True).readiness == "ANNOTATION_FROZEN"
    all_a = append_reviews(
        sample, catalog, tuple(review(context, i) for i in range(len(sample.packets)))
    )
    assert review_report(sample, all_a).readiness == "FIRST_REVIEW_COMPLETE"
    # Mixed rater sets do not produce a pooled Cohen's kappa.
    mixed = append_reviews(
        sample,
        catalog,
        (
            review(context),
            review(context, reviewer="human-fixture-b"),
            review(context, 1, label="NEGATIVE"),
            review(context, 1, reviewer="human-fixture-d", label="NEGATIVE"),
        ),
    )
    assert review_report(sample, mixed).agreement.cohen_kappa is None
    disagreement = append_reviews(
        sample,
        catalog,
        (
            review(context),
            review(context, reviewer="human-fixture-b", label="NEGATIVE"),
            review(context, 1, label="NEGATIVE"),
            review(context, 1, reviewer="human-fixture-b"),
        ),
    )
    assert review_report(sample, disagreement).agreement.cohen_kappa == -1


def test_bundles_deterministic_blinded_and_immutable(context, tmp_path):
    bound, sample, cache, catalog = context
    first, second = tmp_path / "first", tmp_path / "second"
    assert prepare_bundles(bound, sample, cache, catalog, first) == prepare_bundles(
        bound, sample, cache, catalog, second
    )
    a, b = first / "reviewer-a", first / "reviewer-b"
    assert len(tuple(a.glob("oss-*.md"))) == len(sample.packets)
    for path in a.iterdir():
        if path.name != "bundle-manifest.json":
            assert path.read_bytes() == (b / path.name).read_bytes()
    form = json.loads((a / "review-form.json").read_text())
    assert all(r["label"] is r["reviewer_id"] is r["attestation"] is None for r in form["reviews"])
    assert all(r["rationale"] == "" and r["evidence"] == [] for r in form["reviews"])
    forbidden = (
        "StaticFinding",
        "GraphCandidate",
        "candidate_present",
        "graph_classification",
        "model_score",
        "v2_score",
        "hybrid_result",
    )
    assert not any(term in (a / "packets.json").read_text() for term in forbidden)
    assert all(
        q["truncated"] is False and q["declaration_visible"]
        for q in json.loads((a / "packet-quality.json").read_text())
    )
    (a / "completed-private.json").write_text("Do not copy responses to B")
    third = tmp_path / "third"
    prepare_bundles(bound, sample, cache, catalog, third)
    assert not (third / "reviewer-b" / "completed-private.json").exists()
    with pytest.raises(ValueError, match="immutable"):
        prepare_bundles(bound, sample, cache, catalog, first)


def test_supplemental_context_and_pinned_evidence(context, tmp_path):
    bound, sample, cache, catalog = context
    packet = sample.packets[0]
    root = source_path(cache, bound.corpus.repositories[0])
    evidence = PinnedEvidence(
        repository_id=packet.repository_id,
        commit_sha=catalog.packets[0].commit_sha,
        path="README.md",
        sha256=hashlib.sha256((root / "README.md").read_bytes()).hexdigest(),
        start_line=2,
        end_line=2,
        purpose="DOCUMENTATION",
    )
    supplemental = supplement_context(
        bound, sample, cache, catalog, packet.annotation_case_id, (evidence,), tmp_path / "extra"
    )
    assert supplemental.packets[:-1] == catalog.packets
    revision = supplemental.packets[-1]
    assert (
        revision.revision == 2
        and revision.previous_packet_fingerprint == catalog.packets[0].fingerprint
    )
    changed_context = bound, sample, cache, supplemental
    imported = import_review_batch(
        bound,
        sample,
        cache,
        supplemental,
        batch(sample, (review(changed_context, evidence=(evidence,)),)),
    )
    assert imported.cases[0].status == "SINGLE_REVIEW"
    for key, value in (
        ("sha256", "f" * 64),
        ("commit_sha", "f" * 40),
        ("repository_id", "unknown"),
        ("end_line", 300),
    ):
        with pytest.raises(ValueError):
            verify_evidence(
                bound,
                cache,
                PinnedEvidence.model_validate(evidence.model_dump(mode="json") | {key: value}),
            )
    with pytest.raises(ValueError):
        supplement_context(
            bound,
            sample,
            cache,
            supplemental,
            packet.annotation_case_id,
            (evidence,),
            tmp_path / "duplicate",
        )
    for path in ("../README.md", "/README.md"):
        with pytest.raises(ValueError):
            PinnedEvidence.model_validate(evidence.model_dump(mode="json") | {"path": path})
    with pytest.raises(ValueError):
        PinnedEvidence.model_validate(evidence.model_dump(mode="json") | {"start_line": 3})


def test_atomic_bad_batch_and_adjudication_export(context, tmp_path):
    bound, sample, cache, catalog = context
    store = import_review_batch(bound, sample, cache, catalog, batch(sample))
    output = tmp_path / "store"
    publish_store(sample, catalog, store, output)
    before = (output / "reviews.json").read_bytes()
    broken = batch(sample, (review(context), review(context, 1)))
    broken["reviews"][1]["evidence"][0]["sha256"] = "f" * 64
    with pytest.raises(ValueError):
        import_review_batch(bound, sample, cache, catalog, broken, store)
    assert (output / "reviews.json").read_bytes() == before
    assert not (output / "annotation-freeze.json").exists()
    with pytest.raises(ValueError, match="no actual human conflicts"):
        export_adjudication(bound, sample, cache, catalog, store, tmp_path / "empty-adj")
    assert not (tmp_path / "empty-adj").exists()
    conflict = append_reviews(
        sample,
        catalog,
        (review(context), review(context, reviewer="human-fixture-b", label="NEGATIVE")),
    )
    assert export_adjudication(bound, sample, cache, catalog, conflict, tmp_path / "adj") == 1
    content = (tmp_path / "adj" / (sample.packets[0].annotation_case_id + ".md")).read_text()
    assert "POSITIVE" in content and "NEGATIVE" in content and "Synthetic test rationale" in content

    def fail(stage):
        (stage / "partial.json").write_text("partial")
        raise OSError("synthetic disk error")

    with pytest.raises(OSError):
        atomic_directory(tmp_path / "failed", fail)
    assert not (tmp_path / "failed").exists()
    assert not tuple(tmp_path.glob(".archguard-review-*"))
    with pytest.raises(ValueError):
        publish_freeze(sample, catalog, store, tmp_path / "no-freeze")
    assert not (tmp_path / "no-freeze").exists()


def cli_args(context, tmp_path):
    bound, sample, cache, _ = context
    paths = {
        "corpus": bound.corpus,
        "protocol": bound.protocol,
        "freeze": bound.freeze,
        "sample": sample,
        "sample-freeze": seal(
            SampleFreeze,
            corpus_freeze_fingerprint=bound.freeze.fingerprint,
            sample_fingerprint=sample.fingerprint,
            frame_fingerprint=digest(()),
            sampling_protocol_fingerprint=sample.sampling_protocol_fingerprint,
            frozen_at="synthetic",
            cases=len(sample.packets),
        ),
    }
    args = ["benchmark", "oss", "review"]
    options = []
    for name, value in paths.items():
        path = tmp_path / (name + ".json")
        write_new(path, value)
        options += ["--" + name, str(path)]
    return args, options + ["--cache", str(cache)]


def test_cli_atomic_validation_dry_run_and_status(context, tmp_path, capsys):
    _, sample, _, _ = context
    args, options = cli_args(context, tmp_path)
    assert main(args + ["prepare", *options, "--output", str(tmp_path / "prepared")]) == 0
    assert main(args + ["status", *options]) == 0
    assert "WAITING_FOR_HUMAN_REVIEW" in capsys.readouterr().out
    form = tmp_path / "actual-fixture.json"
    write_new(form, batch(sample, (review(context),)))
    base = args + [
        "import",
        *options,
        "--annotations",
        str(form),
        "--output",
        str(tmp_path / "imported"),
    ]
    assert main(base + ["--dry-run"]) == 0
    assert not (tmp_path / "imported").exists()
    assert main(args + ["validate", *options, "--annotations", str(form)]) == 0
    assert main(base) == 0
    assert main(base) == 2
    assert (
        main(args + ["status", *options, "--store", str(tmp_path / "imported/reviews.json")]) == 0
    )
    assert '"single_review":1' in capsys.readouterr().out
    assert (
        main(
            args
            + [
                "freeze",
                *options,
                "--store",
                str(tmp_path / "imported/reviews.json"),
                "--output",
                str(tmp_path / "frozen"),
            ]
        )
        == 2
    )
    invalid = batch(sample, (review(context), review(context, 1)))
    invalid["reviews"][1]["packet_revision"] = 99
    write_new(tmp_path / "bad.json", invalid)
    assert (
        main(
            args
            + [
                "import",
                *options,
                "--annotations",
                str(tmp_path / "bad.json"),
                "--output",
                str(tmp_path / "bad-import"),
            ]
        )
        == 2
    )
    assert not (tmp_path / "bad-import").exists()


def test_sample_catalog_history_tampering_and_model_independence(context, tmp_path):
    _, sample, _, catalog = context
    bad_sample = seal(
        type(sample),
        **(
            sample.model_dump(mode="json", exclude={"fingerprint"})
            | {"packets": tuple(reversed(sample.packets)), "strata": tuple(reversed(sample.strata))}
        ),
    )
    with pytest.raises(ValueError, match="sample mismatch"):
        validate_catalog(bad_sample, catalog)
    store = append_reviews(sample, catalog, (review(context),))
    altered = seal(
        type(store),
        **(
            store.model_dump(mode="json", exclude={"fingerprint"})
            | {"cases": append_reviews(sample, catalog).cases}
        ),
    )
    with pytest.raises(ValueError, match="history/state"):
        append_reviews(sample, catalog, previous=altered)
    source = ROOT / "src/archguard/benchmark/oss/review.py"
    imports = [
        node.module
        for node in ast.walk(ast.parse(source.read_text()))
        if isinstance(node, ast.ImportFrom)
    ]
    assert not any(
        name
        and any(
            word in name for word in ("infrastructure", "intelligence", "calibration", "hybrid")
        )
        for name in imports
    )
    before = canonical(append_reviews(sample, catalog))
    (tmp_path / "model-output.json").write_text('{"prediction":"POSITIVE","score":9999}')
    assert canonical(append_reviews(sample, catalog)) == before


@pytest.mark.parametrize(
    "mutation",
    ["unknown-case", "original-revision", "broken-chain", "duplicate-context", "cross-repository"],
)
def test_catalog_guards(context, mutation):
    _, sample, _, catalog = context
    from archguard.benchmark.oss.review import PacketRevision, RevisionCatalog

    first = catalog.packets[0]
    values = first.model_dump(mode="json", exclude={"fingerprint"})
    if mutation == "unknown-case":
        values["annotation_case_id"] = "unknown"
        packets = (seal(PacketRevision, **values),) + catalog.packets[1:]
    elif mutation == "original-revision":
        values["revision"] = 2
        packets = (seal(PacketRevision, **values),) + catalog.packets[1:]
    else:
        reference = original_evidence(sample.packets[0], first)[0]
        values.update(
            revision=2,
            previous_packet_fingerprint=first.fingerprint,
            additional_evidence=(reference,),
        )
        if mutation == "broken-chain":
            values["previous_packet_fingerprint"] = "f" * 64
        elif mutation == "duplicate-context":
            values["additional_evidence"] = (reference, reference)
        else:
            values["additional_evidence"] = (
                PinnedEvidence.model_validate(
                    reference.model_dump(mode="json") | {"repository_id": "other"}
                ),
            )
        packets = catalog.packets + (seal(PacketRevision, **values),)
    with pytest.raises(ValueError):
        validate_catalog(
            sample, seal(RevisionCatalog, sample_fingerprint=sample.fingerprint, packets=packets)
        )


def test_adjudication_and_scope_guards(context):
    _, sample, _, catalog = context
    conflict = append_reviews(
        sample,
        catalog,
        (review(context), review(context, reviewer="human-fixture-b", label="NEGATIVE")),
    )
    with pytest.raises(ValueError, match="unknown reviews"):
        append_reviews(
            sample,
            catalog,
            adjudications=(adjudication(context, conflict, review_ids=("f" * 64, "a" * 64)),),
            previous=conflict,
        )
    resolved = append_reviews(
        sample, catalog, adjudications=(adjudication(context, conflict),), previous=conflict
    )
    with pytest.raises(ValueError, match="explicit amendment"):
        append_reviews(
            sample,
            catalog,
            adjudications=(
                adjudication(context, conflict, rationale="Synthetic corrected rationale"),
            ),
            previous=resolved,
        )
    with pytest.raises(ValueError, match="invalid adjudication amendment"):
        append_reviews(
            sample,
            catalog,
            adjudications=(adjudication(context, conflict, supersedes_adjudication_id="f" * 64),),
            previous=resolved,
        )
    wrong = seal(
        type(resolved),
        **(
            resolved.model_dump(mode="json", exclude={"fingerprint"})
            | {"sample_fingerprint": "f" * 64}
        ),
    )
    with pytest.raises(ValueError, match="sample/corpus"):
        append_reviews(sample, catalog, previous=wrong)


def test_cli_complete_synthetic_scope_and_supplement(context, tmp_path, capsys):
    bound, sample, cache, catalog = context
    args, options = cli_args(context, tmp_path)
    reviews = tuple(
        review(context, i, reviewer=who, label="UNCERTAIN" if i == 4 else "NEGATIVE")
        for i in range(len(sample.packets))
        for who in ("human-fixture-a", "human-fixture-b")
    )
    write_new(tmp_path / "humans.json", batch(sample, reviews))
    assert (
        main(
            args
            + [
                "import",
                *options,
                "--annotations",
                str(tmp_path / "humans.json"),
                "--output",
                str(tmp_path / "store"),
            ]
        )
        == 0
    )
    store_args = ["--store", str(tmp_path / "store/reviews.json")]
    assert (
        main(args + ["freeze", *options, *store_args, "--output", str(tmp_path / "freeze-out")])
        == 0
    )
    assert (
        main(
            args
            + [
                "status",
                *options,
                *store_args,
                "--freeze-receipt",
                str(tmp_path / "freeze-out/annotation-freeze.json"),
            ]
        )
        == 0
    )
    assert "ANNOTATION_FROZEN" in capsys.readouterr().out
    assert (
        main(
            args
            + [
                "status",
                *options,
                "--freeze-receipt",
                str(tmp_path / "freeze-out/annotation-freeze.json"),
            ]
        )
        == 2
    )
    assert main(args + ["adjudication-export", *options, "--output", str(tmp_path / "no-adj")]) == 2
    reference = original_evidence(sample.packets[0], catalog.packets[0])[0].model_dump(mode="json")
    reference["start_line"] = reference["end_line"]
    write_new(tmp_path / "context.json", [reference])
    assert (
        main(
            args
            + [
                "request-extra-context",
                *options,
                "--case",
                sample.packets[0].annotation_case_id,
                "--context",
                str(tmp_path / "context.json"),
                "--output",
                str(tmp_path / "supplement"),
            ]
        )
        == 0
    )
    assert (
        main(
            args
            + ["status", *options, "--catalog", str(tmp_path / "supplement/packet-revisions.json")]
        )
        == 0
    )
    assert main(args + ["prepare", *options]) == 2
    assert main(args + ["import", *options, "--annotations", str(tmp_path / "humans.json")]) == 2
    write_new(tmp_path / "invalid-form.json", ["invalid"])
    assert (
        main(args + ["validate", *options, "--annotations", str(tmp_path / "invalid-form.json")])
        == 2
    )
    write_new(tmp_path / "invalid-context.json", {"invalid": True})
    assert (
        main(
            args
            + [
                "request-extra-context",
                *options,
                "--case",
                sample.packets[0].annotation_case_id,
                "--context",
                str(tmp_path / "invalid-context.json"),
                "--output",
                str(tmp_path / "invalid-supplement"),
            ]
        )
        == 2
    )
    with pytest.raises(ValueError):
        import_review_batch(
            bound,
            sample,
            cache,
            catalog,
            {"sample_fingerprint": sample.fingerprint, "reviews": None, "adjudications": []},
        )
    with pytest.raises(ValueError):
        import_review_batch(
            bound,
            sample,
            cache,
            catalog,
            {"sample_fingerprint": "f" * 64, "reviews": [], "adjudications": []},
        )


def test_context_safety_empty_missing_and_budget(context, tmp_path):
    from archguard.benchmark.oss.review import PacketRevision
    from archguard.infrastructure.oss_review import render_packet, validate_context

    bound, sample, cache, catalog = context
    root = source_path(cache, bound.corpus.repositories[0])
    link = root / "untrusted-link.md"
    link.symlink_to(tmp_path)
    reference = original_evidence(sample.packets[0], catalog.packets[0])[0]
    try:
        with pytest.raises(ValueError, match="escape"):
            verify_evidence(
                bound,
                cache,
                PinnedEvidence.model_validate(
                    reference.model_dump(mode="json") | {"path": link.name}
                ),
            )
    finally:
        link.unlink()
    pin_changed = seal(
        PacketRevision,
        **(
            catalog.packets[0].model_dump(mode="json", exclude={"fingerprint"})
            | {"commit_sha": "f" * 40}
        ),
    )
    wrong_catalog = seal(
        type(catalog),
        sample_fingerprint=sample.fingerprint,
        packets=(pin_changed,) + catalog.packets[1:],
    )
    with pytest.raises(ValueError, match="commit mismatch"):
        validate_context(bound, sample, cache, wrong_catalog)
    extra_path = root / "supplement-fixture.txt"
    try:
        for content, error in ((" \n", "empty source"), ("x" * 1048576, "exceeds 1 MiB")):
            extra_path.write_text(content)
            extra = PinnedEvidence.model_validate(
                reference.model_dump(mode="json")
                | {
                    "path": extra_path.name,
                    "sha256": hashlib.sha256(extra_path.read_bytes()).hexdigest(),
                    "start_line": 1,
                    "end_line": 1,
                }
            )
            revision = seal(
                PacketRevision,
                **(
                    catalog.packets[0].model_dump(mode="json", exclude={"fingerprint"})
                    | {
                        "revision": 2,
                        "previous_packet_fingerprint": catalog.packets[0].fingerprint,
                        "additional_evidence": (extra,),
                    }
                ),
            )
            with pytest.raises(ValueError, match=error):
                render_packet(bound, sample, cache, revision)
    finally:
        extra_path.unlink()
    packet = sample.packets[0]
    fake_subject = packet.subject.model_copy(update={"qualified_name": "NotPresentInSource"})
    fake_packet = seal(
        type(packet),
        **(packet.model_dump(mode="json", exclude={"fingerprint"}) | {"subject": fake_subject}),
    )
    fake_sample = seal(
        type(sample),
        **(
            sample.model_dump(mode="json", exclude={"fingerprint"})
            | {"packets": (fake_packet,) + sample.packets[1:]}
        ),
    )
    with pytest.raises(ValueError, match="visible declaration"):
        render_packet(bound, fake_sample, cache, catalog.packets[0])
    with pytest.raises(ValueError, match="known case"):
        supplement_context(
            bound, sample, cache, catalog, "unknown", (reference,), tmp_path / "no-context"
        )
    with pytest.raises(ValueError, match="cover frozen"):
        validate_catalog(
            sample,
            seal(
                type(catalog), sample_fingerprint=sample.fingerprint, packets=catalog.packets[:-1]
            ),
        )
    destination = tmp_path / "occupied"

    def occupy(stage):
        destination.mkdir()
        (destination / "owned.txt").write_text("existing output")

    with pytest.raises(ValueError, match="immutable"):
        atomic_directory(destination, occupy)
    assert (destination / "owned.txt").read_text() == "existing output"
