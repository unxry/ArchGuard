"""Independent source inputs and post-freeze comparison; only temporary synthetic human data."""

import hashlib
from functools import partial
from pathlib import Path

import pytest

from archguard.benchmark.oss.models import (
    AnnotationPacket,
    AnnotationSample,
    canonical,
    digest,
    seal,
)
from archguard.cli import main
from archguard.infrastructure.oss_assistance import (
    ContextRequest,
    build_assistance,
    publish_assistance,
)
from archguard.infrastructure.oss_assistance_b import (
    ContextSufficiency,
    ReviewerBAssistance,
    build_b_assistance,
    publish_b_assistance,
    verify_b_freeze,
)
from archguard.infrastructure.oss_benchmark import source_path, write_new
from archguard.infrastructure.oss_context_comparison import (
    compare_context,
    publish_context_comparison,
)
from archguard.infrastructure.oss_review import initial_catalog, original_evidence, prepare_bundles
from archguard.infrastructure.oss_review_wizard import export_draft, wizard
from tests.benchmark.test_oss_assistance import ask_values, human_answers
from tests.benchmark.test_oss_benchmark import local_corpus  # noqa: F401


@pytest.fixture
def context(local_corpus, tmp_path):  # noqa: F811
    bound, _, cache, _, _, _, sample, _ = local_corpus
    catalog = initial_catalog(bound, sample)
    bundles = tmp_path / "bundles"
    prepare_bundles(bound, sample, cache, catalog, bundles)
    return bound, sample, cache, catalog, bundles


def snapshots(path):
    return {p.name: p.read_bytes() for p in path.iterdir() if p.is_file()}


def test_forty_frozen_synthetic_ids_no_answers_and_verified_ranges(context, tmp_path):
    bound, original, cache, _, _ = context
    root = source_path(cache, bound.corpus.repositories[0])
    base = original.packets[0]
    packets = []
    for suffix, names in (("java", "ABCDE"), ("ts", "ABC")):
        for name in names:
            path = f"{suffix}/{name}.{suffix}"
            subject = base.subject.model_copy(update={"path": path, "qualified_name": name})
            ref = base.evidence[0].model_copy(
                update={
                    "path": path,
                    "sha256": hashlib.sha256((root / path).read_bytes()).hexdigest(),
                    "start_line": 1,
                    "end_line": 1,
                }
            )
            for rule in ("ARCH201", "ARCH202", "ARCH203", "ARCH204", "ARCH205"):
                identifier = (
                    "oss-"
                    + digest((bound.corpus.fingerprint, base.repository_id, rule, subject))[:24]
                )
                packets.append(
                    seal(
                        AnnotationPacket,
                        **(
                            base.model_dump(exclude={"fingerprint"})
                            | {
                                "subject": subject,
                                "evidence": (ref,),
                                "rule_id": rule,
                                "annotation_case_id": identifier,
                            }
                        ),
                    )
                )
    sample = seal(
        AnnotationSample,
        **(
            original.model_dump(exclude={"fingerprint"})
            | {
                "packets": tuple(packets),
                "strata": tuple((p.annotation_case_id, "LOW") for p in packets),
            }
        ),
    )
    catalog = initial_catalog(bound, sample)
    b = build_b_assistance(bound, sample, cache, catalog)
    assert len(b.cases) == 40
    assert tuple(c.case_id for c in b.cases) == tuple(p.annotation_case_id for p in sample.packets)
    assert b.sample_fingerprint == sample.fingerprint
    forbidden = (
        '"label"',
        '"prediction"',
        '"decision"',
        '"reviewer_id"',
        '"rationale"',
        '"attestation"',
        "recommended_label",
        "expected_label",
        "most_likely_label",
        "candidate_present",
        "model_score",
        "v2_score",
        "SemanticCandidate",
        "HybridDecision",
        "GraphCandidate",
        "HUMAN_REVIEW_COMPLETED",
        "POSITIVE",
        "NEGATIVE",
    )
    assert not any(term in canonical(b) for term in forbidden)
    output = tmp_path / "b"
    publish_b_assistance(b, output)
    assert len(tuple(output.glob("oss-*.md"))) == 40
    for case, packet, flag in zip(b.cases, sample.packets, b.context_sufficiency, strict=True):
        assert flag.extra_context_recommended == bool(case.extra_context_recommended)
        for ref in case.assistant_evidence_candidates:
            assert any(
                r.path == ref.path
                and r.sha256 == ref.sha256
                and r.start_line <= ref.start_line <= ref.end_line <= r.end_line
                for r in packet.evidence
            )
        assert not any(term in (output / (case.case_id + ".md")).read_text() for term in forbidden)
    assert verify_b_freeze(output)[0] == b


@pytest.mark.parametrize("a_state", ["absent", "present", "mutated", "deleted", "human_changed"])
def test_generation_does_not_open_a_and_is_byte_identical(context, tmp_path, monkeypatch, a_state):
    bound, sample, cache, catalog, bundles = context
    aid = tmp_path / "prompt013-aid-v1"
    human_a = bundles / "reviewer-a"
    original_open = Path.open

    def read_barrier(path, mode="r", *args, **kwargs):
        if "r" in mode and any(path.resolve().is_relative_to(p.resolve()) for p in (aid, human_a)):
            pytest.fail("B generation accessed forbidden A data")
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", read_barrier)
    first = build_b_assistance(bound, sample, cache, catalog)
    publish_b_assistance(first, tmp_path / "b-first")
    if a_state != "absent":
        aid.mkdir()
        (aid / "assistance.json").write_text('{"label":"POSITIVE","rationale":"Never consume"}')
    if a_state == "mutated":
        (aid / "assistance.json").write_text('{"label":"NEGATIVE","summary":"Changed A output"}')
    if a_state == "deleted":
        (aid / "assistance.json").unlink()
        aid.rmdir()
    if a_state == "human_changed":
        (human_a / "review-form.json").write_text(
            '{"label":"NEGATIVE","rationale":"Synthetic A answer"}'
        )
        (human_a / "draft.json").write_text('{"reviewer_id":"mock-human","label":"POSITIVE"}')
    second = build_b_assistance(bound, sample, cache, catalog)
    publish_b_assistance(second, tmp_path / "b-second")
    assert first.fingerprint == second.fingerprint
    assert snapshots(tmp_path / "b-first") == snapshots(tmp_path / "b-second")


def test_context_flags_cannot_be_divorced_from_requests(context):
    bound, sample, cache, catalog, _ = context
    b = build_b_assistance(bound, sample, cache, catalog)
    payload = b.model_dump(exclude={"fingerprint"})
    payload["context_sufficiency"][0]["extra_context_recommended"] = True
    with pytest.raises(ValueError, match="context flags"):
        seal(ReviewerBAssistance, **payload)


def test_wizard_b_binds_assistance_and_preserves_a(context, tmp_path):
    bound, sample, cache, catalog, bundles = context
    a = build_assistance(bound, sample, cache, catalog)
    b = build_b_assistance(bound, sample, cache, catalog)
    a_bundle, b_bundle = bundles / "reviewer-a", bundles / "reviewer-b"
    before = snapshots(a_bundle), snapshots(b_bundle)
    draft = tmp_path / "b-draft.json"
    completed = wizard(
        b, b_bundle, draft, ask=ask_values(*human_answers(), "Q"), tell=lambda _: None
    )
    assert completed.assistance_fingerprint == b.fingerprint
    assert completed.catalog_fingerprint == catalog.fingerprint
    assert len(completed.reviews) == 1
    resumed = wizard(b, b_bundle, draft, ask=ask_values("S", "Q"), tell=lambda _: None)
    assert resumed == completed
    assert export_draft(b, b_bundle, draft, tmp_path / "b-submission.json") == 1
    with pytest.raises(ValueError, match="slot mismatch"):
        wizard(a, b_bundle, tmp_path / "mixed.json", ask=ask_values("Q"))
    with pytest.raises(ValueError, match="slot mismatch"):
        wizard(b, a_bundle, tmp_path / "mixed.json", ask=ask_values("Q"))
    result = wizard(
        a, a_bundle, tmp_path / "a-draft.json", ask=ask_values("S", "Q"), tell=lambda _: None
    )
    assert result.reviews == ()
    assert (snapshots(a_bundle), snapshots(b_bundle)) == before


def test_comparison_refuses_unfrozen_b_before_access_to_a(context, tmp_path, monkeypatch):
    bound, sample, cache, catalog, _ = context
    b = build_b_assistance(bound, sample, cache, catalog)
    destination = tmp_path / "unfrozen"
    publish_assistance(b, destination)
    forbidden = tmp_path / "a.json"
    original_open = Path.open

    def guard(path, mode="r", *args, **kwargs):
        if path == forbidden:
            pytest.fail("comparison opened A before B freeze")
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guard)
    with pytest.raises((OSError, ValueError)):
        compare_context(forbidden, destination)


def test_comparison_four_groups_uses_only_context_projection(context, tmp_path):
    bound, sample, cache, catalog, _ = context
    a = build_assistance(bound, sample, cache, catalog)
    b = build_b_assistance(bound, sample, cache, catalog)
    peer = original_evidence(sample.packets[0], catalog.packets[0])[0]
    request = ContextRequest(evidence=peer, reason="Synthetic context request")
    a_cases = tuple(
        c.model_copy(update={"extra_context_recommended": (request,) if i in {0, 3} else ()})
        for i, c in enumerate(a.cases)
    )
    b_cases = tuple(
        c.model_copy(update={"extra_context_recommended": (request,) if i in {0, 2} else ()})
        for i, c in enumerate(b.cases)
    )
    a = seal(type(a), **(a.model_dump(exclude={"fingerprint"}) | {"cases": a_cases}))
    b = seal(
        ReviewerBAssistance,
        **(
            b.model_dump(exclude={"fingerprint", "context_sufficiency"})
            | {
                "cases": b_cases,
                "context_sufficiency": tuple(
                    ContextSufficiency(
                        case_id=c.case_id,
                        extra_context_recommended=bool(c.extra_context_recommended),
                    )
                    for c in b_cases
                ),
            }
        ),
    )
    write_new(tmp_path / "a.json", a)
    receipt = publish_b_assistance(b, tmp_path / "b")
    comparison = compare_context(tmp_path / "a.json", tmp_path / "b")
    assert comparison.b_freeze_fingerprint == receipt.fingerprint
    assert tuple(
        map(
            len,
            (
                comparison.both_need_context,
                comparison.a_only,
                comparison.b_only,
                comparison.neither,
            ),
        )
    ) == (1, 1, 1, 2)
    assert "Synthetic context request" not in canonical(comparison)
    assert '"observed_behavior"' not in canonical(comparison)
    before = snapshots(tmp_path / "b")
    publish_context_comparison(comparison, tmp_path / "comparison")
    assert snapshots(tmp_path / "b") == before
    assert '"label"' not in (tmp_path / "comparison/context-consensus.json").read_text()
    (tmp_path / "b/index.md").write_text("Tampered frozen card navigation")
    with pytest.raises(ValueError, match="changed after freeze"):
        compare_context(tmp_path / "a.json", tmp_path / "b")


def test_cli_b_generation_wizard_export_compare_and_mixing_guard(context, tmp_path, monkeypatch):
    bound, sample, cache, catalog, bundles = context
    import archguard.infrastructure.oss_review_wizard as wizard_module
    import archguard.oss_review_cli as cli

    monkeypatch.setattr(cli, "load_corpus", lambda *args: bound)
    monkeypatch.setattr(cli, "load_sample", lambda *args: sample)
    commands = ["benchmark", "oss", "review"]
    output = tmp_path / "b"
    assert main([*commands, "assist-b", "--cache", str(cache), "--output", str(output)]) == 0
    monkeypatch.setattr(
        wizard_module,
        "wizard",
        partial(wizard, ask=ask_values(*human_answers(), "Q"), tell=lambda _: None),
    )
    args = [
        "--cache",
        str(cache),
        "--assistance",
        str(output / "assistance.json"),
        "--bundle",
        str(bundles / "reviewer-b"),
        "--draft",
        str(tmp_path / "draft.json"),
    ]
    assert main([*commands, "wizard", *args]) == 0
    assert (
        main([*commands, "draft-export", *args, "--output", str(tmp_path / "submission.json")]) == 0
    )
    a = build_assistance(bound, sample, cache, catalog)
    write_new(tmp_path / "a.json", a)
    assert (
        main(
            [
                *commands,
                "context-compare",
                "--a-assistance",
                str(tmp_path / "a.json"),
                "--b-assistance",
                str(output),
                "--output",
                str(tmp_path / "comparison"),
            ]
        )
        == 0
    )
    args[args.index("--assistance") + 1] = str(tmp_path / "a.json")
    assert main([*commands, "wizard", *args]) == 2
    with pytest.raises(SystemExit):
        main([*commands, "assist-b", "--assistance", str(tmp_path / "a.json")])
