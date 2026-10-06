"""Source assistance and interactive UX; synthetic human input stays in temporary files."""

import hashlib
import json
import socket
from functools import partial
from pathlib import Path

import pytest

from archguard.benchmark.oss.models import AnnotationPacket, AnnotationSample, digest, seal
from archguard.cli import main
from archguard.infrastructure.oss_assistance import (
    AssistancePackage,
    build_assistance,
    publish_assistance,
)
from archguard.infrastructure.oss_benchmark import source_path
from archguard.infrastructure.oss_review import (
    import_review_batch,
    initial_catalog,
    prepare_bundles,
)
from archguard.infrastructure.oss_review_wizard import export_draft, load_draft, wizard
from tests.benchmark.test_oss_benchmark import local_corpus  # noqa: F401


@pytest.fixture
def context(local_corpus, tmp_path):  # noqa: F811
    bound, _, cache, _, _, _, sample, _ = local_corpus
    catalog = initial_catalog(bound, sample)
    package = build_assistance(bound, sample, cache, catalog)
    root = tmp_path / "bundles"
    prepare_bundles(bound, sample, cache, catalog, root)
    return bound, sample, cache, catalog, package, root / "reviewer-a"


def ask_values(*answers):
    values = iter(answers)

    def ask(_):
        try:
            return next(values)
        except StopIteration:
            raise EOFError from None

    return ask


def human_answers(**changes):
    fields = (
        dict(
            choice="P",
            reviewer="fixture-human",
            rationale="Synthetic source rationale",
            uncertainty="C",
            evidence="1",
            confirm="yes",
        )
        | changes
    )
    return tuple(fields.values())


def snapshots(root):
    return {p.name: p.read_bytes() for p in root.iterdir() if p.is_file()}


def test_source_only_deterministic_immutable(context, tmp_path, monkeypatch):
    bound, sample, cache, catalog, package, bundle = context
    before = snapshots(bundle)
    monkeypatch.setattr(socket, "socket", lambda *a, **k: pytest.fail("offline extraction"))
    first, second = tmp_path / "first", tmp_path / "second"
    publish_assistance(package, first)
    publish_assistance(build_assistance(bound, sample, cache, catalog), second)
    assert snapshots(first) == snapshots(second)
    assert tuple(c.case_id for c in package.cases) == tuple(
        p.annotation_case_id for p in sample.packets
    )
    assert package.sample_fingerprint == sample.fingerprint
    assert package.catalog_fingerprint == catalog.fingerprint
    forbidden = (
        '"label"',
        "candidate_present",
        "model_score",
        "v2_score",
        "GraphCandidate",
        "SemanticCandidate",
        "HybridDecision",
        "expected_label",
        "recommended_label",
        "POSITIVE",
        "NEGATIVE",
        "recommended answer",
        "likely label",
    )
    assert not any(s in (first / "assistance.json").read_text() for s in forbidden)
    for case, packet in zip(package.cases, sample.packets, strict=True):
        card = (first / (case.case_id + ".md")).read_text()
        assert not any(s in card for s in forbidden)
        assert "NO LABEL PROVIDED." in card
        assert 1 <= len(case.assistant_evidence_candidates) <= 8
        for candidate in case.assistant_evidence_candidates:
            assert any(
                r.path == candidate.path
                and r.sha256 == candidate.sha256
                and r.start_line <= candidate.start_line <= candidate.end_line <= r.end_line
                for r in packet.evidence
            )
    assert "POSITIVE" in (first / "ANNOTATION_CHEATSHEET.md").read_text()
    assert snapshots(bundle) == before
    with pytest.raises(ValueError, match="immutable"):
        publish_assistance(package, first)


def test_fill_skip_resume_export_preserves_bundle(context, tmp_path):
    bound, sample, cache, catalog, package, bundle = context
    before = snapshots(bundle)
    path = tmp_path / "draft.json"
    draft = wizard(
        package, bundle, path, ask=ask_values(*human_answers(), "S", "Q"), tell=lambda _: None
    )
    assert len(draft.reviews) == 1
    assert draft.reviews[0].evidence == (
        package.cases[0].assistant_evidence_candidates[0].reference(),
    )
    assert snapshots(bundle) == before
    prompts = []
    resumed = wizard(
        package,
        bundle,
        path,
        ask=ask_values(*human_answers(choice="U", uncertainty="A", evidence=""), "Q"),
        tell=prompts.append,
    )
    assert len(resumed.reviews) == 2
    assert resumed.reviews[1].annotation_case_id == package.cases[1].case_id
    assert "Case 2/" in prompts[0]
    raw = json.loads(path.read_text())
    with pytest.raises(ValueError, match="schema mismatch"):
        import_review_batch(bound, sample, cache, catalog, raw)
    output = tmp_path / "submission.json"
    assert export_draft(package, bundle, path, output) == 2
    submission = json.loads(output.read_text())
    assert submission["sample_fingerprint"] == sample.fingerprint
    assert submission["reviews"] == raw["reviews"]
    assert set(submission) == {"sample_fingerprint", "reviews", "adjudications"}
    with pytest.raises(FileExistsError):
        export_draft(package, bundle, path, output)
    with pytest.raises(ValueError, match="mismatch"):
        load_draft(path, package, "f" * 64)
    with pytest.raises(ValueError, match="mismatch"):
        wizard(
            package, bundle.parent / "reviewer-b", path, ask=ask_values("Q"), tell=lambda _: None
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"rationale": ""},
        {"evidence": ""},
        {"reviewer": ""},
        {"uncertainty": ""},
        {"evidence": "0"},
        {"evidence": "999"},
        {"evidence": "1,1"},
        {"evidence": "x"},
        {"confirm": "no"},
        {"confirm": ""},
    ],
)
def test_invalid_or_unattested_input_not_saved(context, tmp_path, changes):
    *_, package, bundle = context
    path = tmp_path / "draft.json"
    result = wizard(
        package, bundle, path, ask=ask_values(*human_answers(**changes), "Q"), tell=lambda _: None
    )
    assert result.reviews == ()
    assert not path.exists()


def test_skip_no_default_identity_guard_and_changed_bundle(context, tmp_path):
    *_, package, bundle = context
    path = tmp_path / "draft.json"
    result = wizard(package, bundle, path, ask=ask_values("", "S", "Q"), tell=lambda _: None)
    assert not result.reviews and not path.exists()
    result = wizard(
        package,
        bundle,
        path,
        ask=ask_values(*human_answers(), *human_answers(reviewer="different-human"), "Q"),
        tell=lambda _: None,
    )
    assert len(result.reviews) == 1
    with pytest.raises(ValueError, match="outside"):
        wizard(package, bundle, bundle / "review-form.json", ask=ask_values("Q"))
    with pytest.raises(ValueError, match="outside"):
        export_draft(package, bundle, path, bundle / "review-form.json")
    (bundle / "review-form.json").write_text("changed fixture")
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        wizard(package, bundle, path, ask=ask_values("Q"))


def test_extra_context_is_request_and_injected_answer_rejected(context):
    *_, package, _ = context
    for case in package.cases:
        for request in case.extra_context_recommended:
            assert request.status == "EXTRA_CONTEXT_RECOMMENDED"
            assert request.evidence not in tuple(
                c.reference() for c in case.assistant_evidence_candidates
            )
            assert request.evidence.commit_sha == case.commit_sha
    raw = package.model_dump()
    raw["cases"][0]["label"] = "POSITIVE"
    with pytest.raises(ValueError):
        AssistancePackage.model_validate(raw)


def test_forty_synthetic_cases_preserve_exact_ids(context):
    bound, original, cache, _, _, _ = context
    root = source_path(cache, bound.corpus.repositories[0])
    base = original.packets[0]
    packets = []
    for suffix, names in (("java", "ABCDE"), ("ts", "ABC")):
        for name in names:
            path = f"{suffix}/{name}.{suffix}"
            subject = base.subject.model_copy(update={"path": path, "qualified_name": name})
            reference = base.evidence[0].model_copy(
                update={
                    "path": path,
                    "sha256": hashlib.sha256((root / path).read_bytes()).hexdigest(),
                    "start_line": 1,
                    "end_line": 1,
                }
            )
            for rule in ("ARCH201", "ARCH202", "ARCH203", "ARCH204", "ARCH205"):
                identity = (
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
                                "evidence": (reference,),
                                "rule_id": rule,
                                "annotation_case_id": identity,
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
    assistance = build_assistance(bound, sample, cache, initial_catalog(bound, sample))
    assert len(assistance.cases) == 40
    assert tuple(c.case_id for c in assistance.cases) == tuple(
        p.annotation_case_id for p in packets
    )


def test_real_frozen_scope_stays_unreviewed():
    root = Path(__file__).parents[2] / "experiments/oss/annotation"
    sample = json.loads((root / "sample-v1.json").read_text())
    assert len(sample["packets"]) == 40 and sample["review_status"] == "UNREVIEWED"
    store = json.loads((root / "reviews-unreviewed-v1.json").read_text())
    assert store["reviews"] == store["adjudications"] == []
    assert all(c["status"] == "UNREVIEWED" for c in store["cases"])


def test_cli_assist_wizard_export_and_protection(context, tmp_path, monkeypatch, capsys):
    bound, sample, cache, _, _, bundle = context
    import archguard.infrastructure.oss_review_wizard as wizard_module
    import archguard.oss_review_cli as cli

    monkeypatch.setattr(cli, "load_corpus", lambda *args: bound)
    monkeypatch.setattr(cli, "load_sample", lambda *args: sample)
    assistance, draft, output = (
        tmp_path / "assistance",
        tmp_path / "draft.json",
        tmp_path / "export.json",
    )
    common = ["benchmark", "oss", "review"]
    args = ["--cache", str(cache)]
    assert main([*common, "assist", *args, "--output", str(assistance)]) == 0
    review_args = [
        *args,
        "--bundle",
        str(bundle),
        "--draft",
        str(draft),
        "--assistance",
        str(assistance / "assistance.json"),
    ]
    monkeypatch.setattr(
        wizard_module,
        "wizard",
        partial(wizard, ask=ask_values(*human_answers(), "Q"), tell=lambda _: None),
    )
    assert main([*common, "wizard", *review_args]) == 0
    assert main([*common, "draft-export", *review_args, "--output", str(output)]) == 0
    assert len(json.loads(output.read_text())["reviews"]) == 1
    assert main([*common, "assist", *args]) == 2
    assert main([*common, "draft-export", *review_args]) == 2
    protected = [*review_args]
    protected[protected.index("--draft") + 1] = str(assistance / "draft.json")
    assert main([*common, "wizard", *protected]) == 2
    assert "INVALID_BENCHMARK" in capsys.readouterr().err


def test_interrupt_preserves_confirmed_rows_and_missing_export_rejected(context, tmp_path):
    *_, package, bundle = context
    path = tmp_path / "draft.json"
    first = wizard(package, bundle, path, ask=ask_values(*human_answers()), tell=lambda _: None)
    before = path.read_bytes()

    def interrupt(_):
        raise KeyboardInterrupt

    resumed = wizard(package, bundle, path, ask=interrupt, tell=lambda _: None)
    assert resumed == first and path.read_bytes() == before
    assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(ValueError, match="existing draft"):
        export_draft(package, bundle, tmp_path / "missing.json", tmp_path / "out.json")
