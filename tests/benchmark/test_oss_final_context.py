"""Final common context, revision binding and independent source passes; synthetic data only."""

import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest

from archguard.benchmark.oss.models import (
    AnnotationPacket,
    AnnotationSample,
    canonical,
    digest,
    seal,
)
from archguard.benchmark.oss.review import PinnedEvidence, RevisionCatalog, append_reviews
from archguard.cli import main
from archguard.infrastructure.oss_assistance import AssistancePackage, build_assistance
from archguard.infrastructure.oss_assistance_b import build_b_assistance
from archguard.infrastructure.oss_benchmark import source_path, write_new
from archguard.infrastructure.oss_context_comparison import ContextConsensus, ContextPair
from archguard.infrastructure.oss_final_context import (
    FinalContextAudit,
    FinalContextFreeze,
    _body_visible,
    freeze_context,
    prepare_final_context,
    verify_ready,
)
from archguard.infrastructure.oss_review import (
    import_review_batch,
    initial_catalog,
    prepare_bundles,
    verify_evidence,
)
from archguard.infrastructure.oss_review_wizard import (
    bundle_fingerprint,
    export_draft,
    load_draft,
)
from tests.benchmark.test_oss_benchmark import local_corpus  # noqa: F401
from tests.benchmark.test_oss_review import batch, review


def tree(path):
    return {str(p.relative_to(path)): p.read_bytes() for p in path.rglob("*") if p.is_file()}


@pytest.fixture(scope="module")
def frozen(local_corpus, tmp_path_factory):  # noqa: F811
    bound, _, cache, _, _, _, original, _ = local_corpus
    root = source_path(cache, bound.corpus.repositories[0])
    base, packets = original.packets[0], []
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
    reference = PinnedEvidence(
        repository_id=base.repository_id,
        commit_sha=catalog.packets[0].commit_sha,
        path="README.md",
        sha256=hashlib.sha256((root / "README.md").read_bytes()).hexdigest(),
        start_line=1,
        end_line=1,
        purpose="DOCUMENTATION",
    )
    pairs = []
    for i, packet in enumerate(sample.packets):
        refs = (reference,) if i < 29 else ()
        if i < 2:
            refs += (reference.model_copy(update={"start_line": 2, "end_line": 2}),)
        pairs.append(
            ContextPair(
                case_id=packet.annotation_case_id,
                a_extra_context_recommended=bool(refs),
                b_extra_context_recommended=bool(refs),
                a_requested_ranges=refs,
                b_requested_ranges=refs,
            )
        )
    consensus = seal(
        ContextConsensus,
        sample_fingerprint=sample.fingerprint,
        catalog_fingerprint=catalog.fingerprint,
        a_assistance_fingerprint="a" * 64,
        b_assistance_fingerprint="b" * 64,
        b_freeze_fingerprint="c" * 64,
        both_need_context=tuple(p.case_id for p in pairs[:29]),
        a_only=(),
        b_only=(),
        neither=tuple(p.case_id for p in pairs[29:]),
        cases=tuple(pairs),
    )
    output = tmp_path_factory.mktemp("final-context") / "prepared"
    ready = prepare_final_context(bound, sample, cache, catalog, consensus, output)
    final = RevisionCatalog.model_validate_json((output / "packet-revisions.json").read_text())
    return bound, sample, cache, catalog, consensus, output, final, ready


def test_common_freeze_counts_history_blank_forms_and_reproducibility(frozen, tmp_path):
    bound, sample, cache, old, consensus, output, final, ready = frozen
    before = canonical(old)
    repeated = tmp_path / "repeat"
    assert prepare_final_context(bound, sample, cache, old, consensus, repeated) == ready
    assert tree(repeated) == tree(output)
    assert canonical(old) == before
    assert final.sample_fingerprint == sample.fingerprint
    assert final.packets[:40] == old.packets
    assert len(final.packets) == 69
    receipt = FinalContextFreeze.model_validate_json(
        (output / "final-context-freeze.json").read_text()
    )
    assert (receipt.audited_requests, receipt.supplemented_cases, receipt.unchanged_cases) == (
        31,
        29,
        11,
    )
    assert [m.active_revision for m in receipt.mapping] == [2] * 29 + [1] * 11
    assert len(final.packets[40].additional_evidence) == 2
    a, b = tree(output / "reviewer-a"), tree(output / "reviewer-b")
    a.pop("bundle-manifest.json")
    b.pop("bundle-manifest.json")
    assert a == b
    forms = json.loads(a["review-form.json"])
    assert len(forms["reviews"]) == 40 and forms["adjudications"] == []
    for row in forms["reviews"]:
        assert all(row[k] is None for k in ("label", "reviewer_id", "uncertainty", "attestation"))
        assert row["rationale"] == "" and row["evidence"] == []
    audit = FinalContextAudit.model_validate_json((output / "final-context-audit.json").read_text())
    assert len(audit.cases) == 40
    assert all(c.state == "LIMITED" for c in audit.cases)
    assert all(
        c.ranges and c.reasons and c.lines_shown > 0 and c.context_bytes > 0 for c in audit.cases
    )
    assert ready.status == "READY_FOR_HUMAN_REVIEW" and ready.kappa is None
    assert ready.human_reviews == ready.binary_eligible == ready.completed_attestations == 0
    forbidden = (
        "candidate_present",
        "model_score",
        "HybridDecision",
        "SemanticCandidate",
        "V2 score",
        "recommended_label",
        "expected_label",
    )
    assert all(word not in data.decode() for data in tree(output).values() for word in forbidden)
    with pytest.raises(ValueError, match="immutable"):
        prepare_final_context(bound, sample, cache, old, consensus, output)


@pytest.mark.parametrize(
    "key,value",
    [
        ("sha256", "f" * 64),
        ("commit_sha", "f" * 40),
        ("end_line", 500),
        ("repository_id", "unknown"),
        ("path", "../README.md"),
    ],
)
def test_bad_requests_fail_closed(frozen, tmp_path, key, value):
    bound, sample, cache, old, consensus, _, _, _ = frozen
    pair = consensus.cases[0]
    with pytest.raises(ValueError):
        bad = PinnedEvidence.model_validate(pair.a_requested_ranges[0].model_dump() | {key: value})
        changed = pair.model_copy(
            update={"a_requested_ranges": (bad,), "b_requested_ranges": (bad,)}
        )
        invalid = seal(
            ContextConsensus,
            **(
                consensus.model_dump(exclude={"fingerprint"})
                | {
                    "cases": (changed,) + consensus.cases[1:],
                }
            ),
        )
        prepare_final_context(bound, sample, cache, old, invalid, tmp_path / "invalid")
    assert not (tmp_path / "invalid").exists()


@pytest.mark.parametrize("kind", ["leaf", "ancestor", "directory", "fifo"])
def test_symlinks_and_nonregular_files_rejected(frozen, tmp_path, kind):
    bound, _, cache, _, consensus, _, _, _ = frozen
    root = source_path(cache, bound.corpus.repositories[0])
    path = root / ("unsafe-013c-" + kind)
    try:
        if kind == "leaf":
            path.symlink_to(root / "README.md")
        elif kind == "ancestor":
            path.symlink_to(root, target_is_directory=True)
        elif kind == "directory":
            path.mkdir()
        else:
            os.mkfifo(path)
        ref = (
            consensus.cases[0]
            .a_requested_ranges[0]
            .model_copy(
                update={
                    "path": path.name + ("/README.md" if kind == "ancestor" else ""),
                }
            )
        )
        with pytest.raises(ValueError, match="source path"):
            verify_evidence(bound, cache, ref)
    finally:
        if kind == "directory":
            path.rmdir()
        else:
            path.unlink()


@pytest.mark.parametrize("mutation", ["sample", "order", "flags", "groups", "covered", "budget"])
def test_consensus_binding_and_budget(frozen, monkeypatch, mutation):
    bound, sample, cache, old, consensus, _, _, _ = frozen
    values = consensus.model_dump(exclude={"fingerprint"})
    if mutation == "sample":
        values["sample_fingerprint"] = "f" * 64
    elif mutation == "order":
        values["cases"] = tuple(reversed(consensus.cases))
    elif mutation == "groups":
        values["a_only"] = consensus.neither
    elif mutation in {"flags", "covered"}:
        pair = consensus.cases[0]
        if mutation == "flags":
            changed = pair.model_copy(update={"a_extra_context_recommended": False})
        else:
            from archguard.benchmark.oss.review import original_evidence

            ref = original_evidence(sample.packets[0], old.packets[0])[0]
            changed = pair.model_copy(
                update={"a_requested_ranges": (ref,), "b_requested_ranges": (ref,)}
            )
        values["cases"] = (changed,) + consensus.cases[1:]
    else:
        monkeypatch.setattr(
            "archguard.infrastructure.oss_final_context.render_packet",
            lambda *a: ("", {"context_bytes": 2**30}),
        )
    with pytest.raises(ValueError):
        freeze_context(bound, sample, cache, old, seal(ContextConsensus, **values))


@pytest.mark.parametrize("other", ["assistance-a", "assistance-b", "answers"])
def test_generation_reads_no_opposite_outputs_or_human_answers(
    frozen, tmp_path, monkeypatch, other
):
    bound, sample, cache, _, _, output, final, _ = frozen
    build = build_b_assistance if other == "assistance-a" else build_assistance
    expected = build(bound, sample, cache, final)
    adversary = tmp_path / other
    if other != "answers":
        shutil.copytree(output / other, adversary)
    else:
        adversary.mkdir()
    (adversary / "assistance.json").write_text('{"expected_label":"POSITIVE"}')
    (adversary / "review-form.json").write_text('{"reviewer_id":"mock-human","label":"NEGATIVE"}')
    original = Path.open

    def guarded(path, *a, **kw):
        if "w" not in kw.get("mode", a[0] if a else "r") and (
            path.is_relative_to(adversary) or path.is_relative_to(output)
        ):
            pytest.fail("source regeneration read generated assistance or human forms")
        return original(path, *a, **kw)

    monkeypatch.setattr(Path, "open", guarded)
    assert build(bound, sample, cache, final) == expected
    (adversary / "assistance.json").write_text("mutated")
    assert build(bound, sample, cache, final) == expected


def test_old_draft_and_old_form_rejected_without_history_migration(frozen, tmp_path):
    bound, sample, cache, old, _, output, final, _ = frozen
    old_a = build_assistance(bound, sample, cache, old)
    bundles = tmp_path / "original"
    prepare_bundles(bound, sample, cache, old, bundles)
    draft = load_draft(
        tmp_path / "draft.json", old_a, bundle_fingerprint(bundles / "reviewer-a", old_a)
    )
    write_new(tmp_path / "draft.json", draft)
    final_a = AssistancePackage.model_validate_json(
        (output / "assistance-a/assistance.json").read_text()
    )
    with pytest.raises(ValueError, match="draft.*mismatch"):
        export_draft(final_a, output / "reviewer-a", tmp_path / "draft.json", tmp_path / "out.json")
    assert not (tmp_path / "out.json").exists()
    row = review((bound, sample, cache, old))
    history = append_reviews(sample, old, (row,))
    assert append_reviews(sample, final, previous=history).reviews == history.reviews
    with pytest.raises(ValueError, match="active packet revision"):
        import_review_batch(bound, sample, cache, final, batch(sample, (row,)))


@pytest.mark.parametrize(
    "part", ["assistance-a/index.md", "assistance-b/index.md", "reviewer-a/index.md"]
)
def test_ready_receipt_detects_artifact_changes(frozen, tmp_path, part):
    _, sample, _, _, _, output, final, _ = frozen
    copied = tmp_path / "tampered"
    shutil.copytree(output, copied)
    (copied / part).write_text("changed")
    with pytest.raises(ValueError):
        verify_ready(copied, sample, final)


def test_lexical_body_coverage_preserves_unknowns():
    lines = ["function f() {", '  const s = "}"; // }', "  return 1;", "}"]
    assert _body_visible(lines, 1, 1, {1, 2, 3, 4})
    assert not _body_visible(lines, 1, 1, {1, 2, 3})
    assert not _body_visible(["function f(): number;"], 1, 1, {1})


def test_final_status_cli(frozen, tmp_path, capsys):
    bound, sample, cache, _, _, output, final, _ = frozen
    from archguard.benchmark.oss.models import SampleFreeze

    paths = [tmp_path / n for n in ("corpus", "protocol", "freeze", "sample", "sample-freeze")]
    sample_freeze = seal(
        SampleFreeze,
        corpus_freeze_fingerprint=bound.freeze.fingerprint,
        frame_fingerprint="d" * 64,
        sampling_protocol_fingerprint=sample.sampling_protocol_fingerprint,
        frozen_at="2026-01-01T00:00:00Z",
        sample_fingerprint=sample.fingerprint,
        cases=len(sample.packets),
    )
    for path, value in zip(
        paths, (bound.corpus, bound.protocol, bound.freeze, sample, sample_freeze), strict=True
    ):
        write_new(path, value)
    args = [
        "benchmark",
        "oss",
        "review",
        "status",
        "--cache",
        str(cache),
        "--catalog",
        str(output / "packet-revisions.json"),
        "--ready-directory",
        str(output),
    ]
    for option, path in zip(
        ("--corpus", "--protocol", "--freeze", "--sample", "--sample-freeze"), paths, strict=True
    ):
        args += [option, str(path)]
    assert main(args) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["readiness"] == "READY_FOR_HUMAN_REVIEW" and status["ready_packets"] == 40
    assert final.sample_fingerprint == sample.fingerprint
