"""Offline fake OSS transports and human vectors; no real reviewer labels are created."""

import hashlib
import inspect
import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest
from pydantic import ValidationError

from archguard.benchmark.oss.annotation import (
    agreement,
    annotation_scope,
    review_annotations,
    sample_subjects,
)
from archguard.benchmark.oss.models import (
    Adjudication,
    AnnotationPacket,
    AnnotationSample,
    CorpusFreeze,
    HumanAnnotation,
    OSSCorpus,
    OSSRepository,
    canonical,
    seal,
)
from archguard.cli import main
from archguard.infrastructure.oss_annotation import (
    export_annotations,
    frame_subjects,
    import_annotations,
    validate_sample,
)
from archguard.infrastructure.oss_benchmark import (
    FrozenOSSCorpus,
    cache_root,
    characterize_repository,
    content_identity,
    fetch_repository,
    load_corpus,
    source_path,
    verify_acquisition,
    write_new,
)

ROOT = Path(__file__).parents[2]


class LocalTransport:
    def __init__(self, remote, wrong_pin=False):
        self.remote = remote
        self.wrong_pin = wrong_pin
        self.commands = []

    def run(self, arguments: Sequence[str], timeout: float, cwd: Path | None = None) -> str:
        args = list(arguments)
        self.commands.append(args)
        if "fetch" in args:
            url = next(i for i, value in enumerate(args) if value.startswith("https://github.com/"))
            args[url] = str(self.remote)
            args = ["-c", "protocol.file.allow=always", *args]
            # Explicit test transport permits its local fixture, never production CLI.
            args = [
                x.replace("protocol.file.allow=never", "protocol.file.allow=always") for x in args
            ]
        if self.wrong_pin and "FETCH_HEAD" in args:
            return "f" * 40
        return subprocess.check_output(["git", *args], cwd=cwd, timeout=timeout, text=True).strip()


@pytest.fixture(scope="module")
def local_corpus(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("oss-local")
    upstream = tmp / "upstream"
    upstream.mkdir()
    (upstream / "LICENSE").write_text("MIT License\nOffline fixture license only.\n")
    (upstream / "README.md").write_text(
        "# Unit library\nFive independent declarations for offline tests.\n"
    )
    (upstream / "package.json").write_text('{"scripts":{"install":"touch MUST_NOT_EXECUTE"}}')
    (upstream / ".gitattributes").write_text("*.java filter=evil\n")
    for language, suffix in (("java", "java"), ("ts", "ts")):
        directory = upstream / language
        directory.mkdir()
        for name in ("A", "B", "C", "D", "E"):
            code = (
                f"package unit; public class {name} {{}}\n"
                if suffix == "java"
                else f"export class {name} {{}}\n"
            )
            (directory / (name + "." + suffix)).write_text(code)
    subprocess.run(["git", "init", "--quiet", str(upstream)], check=True)
    subprocess.run(["git", "add", "."], cwd=upstream, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Unit Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "--quiet",
            "-m",
            "offline fixture",
        ],
        cwd=upstream,
        check=True,
    )
    pin = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=upstream, text=True).strip()
    tree = subprocess.check_output(
        ["git", "rev-parse", "HEAD^{tree}"], cwd=upstream, text=True
    ).strip()
    real = load_corpus(
        ROOT / "experiments/oss/oss-corpus-v1.json",
        ROOT / "experiments/oss/selection-protocol-v1.json",
        ROOT / "experiments/oss/corpus-freeze.json",
    )
    protocol = real.protocol.model_copy(update={"min_source_files": 1})
    repos = tuple(
        OSSRepository(
            repository_id=f"fixture-{i}",
            family_id=f"unit/{i}",
            project=f"unit/fixture-{i}",
            upstream_url=f"https://github.com/unit/fixture-{i}.git",
            language="JAVA" if i < 4 else "TYPESCRIPT",
            commit_sha=pin,
            git_tree_sha=tree,
            commit_date="2026-01-01T00:00:00Z",
            selection_reason="offline unit fixture",
            license_spdx="MIT",
            license_path="LICENSE",
            license_sha256=hashlib.sha256((upstream / "LICENSE").read_bytes()).hexdigest(),
            metadata_size_kib=1,
            estimated_source_files=5,
            estimated_source_bytes=200,
            architecture_provenance={"status": "NONE"},
            acquisition_method="PINNED_GIT_OBJECTS; no checkout filters/submodules/LFS",
        )
        for i in range(8)
    )
    corpus = seal(
        OSSCorpus,
        schema_version="oss-corpus-v1",
        dataset_id="archguard-oss-benchmark-v1",
        version="1.0.0",
        status="OSS_ANNOTATION_SEED",
        selection_protocol_fingerprint=protocol.fingerprint,
        repositories=repos,
    )
    freeze = seal(
        CorpusFreeze,
        schema_version="oss-corpus-freeze-v1",
        corpus_fingerprint=corpus.fingerprint,
        selection_protocol_fingerprint=protocol.fingerprint,
        frozen_at="2026-01-01T01:00:00Z",
        repository_count=8,
        family_count=8,
        commits=tuple((r.repository_id, r.commit_sha) for r in repos),
        phase="BEFORE_FETCH_AND_ANALYSIS",
        source_identities="unit receipt",
    )
    bound = FrozenOSSCorpus(corpus, protocol, freeze)
    cache = tmp / "cache"
    receipt = fetch_repository(bound, repos[0], cache, LocalTransport(upstream))
    report, context = characterize_repository(bound, repos[0], cache)
    from archguard.iam.model import ArchitectureModel

    iam = ArchitectureModel.model_validate(context["iam"])
    subjects = frame_subjects(bound, repos[0].repository_id, iam, cache)
    sample = sample_subjects(corpus, freeze, protocol.sampling, subjects)
    return bound, upstream, cache, receipt, report, iam, sample, subjects


def test_real_manifest_is_frozen_and_source_free():
    bound = load_corpus(
        ROOT / "experiments/oss/oss-corpus-v1.json",
        ROOT / "experiments/oss/selection-protocol-v1.json",
        ROOT / "experiments/oss/corpus-freeze.json",
    )
    assert len(bound.corpus.repositories) == 8
    assert len({r.family_id for r in bound.corpus.repositories}) == 8
    assert all(len(r.commit_sha) == 40 and r.license_sha256 for r in bound.corpus.repositories)
    assert bound.corpus.status == "OSS_ANNOTATION_SEED"
    broken = bound.corpus.model_dump(mode="json")
    broken["repositories"][0]["license_spdx"] = "NOASSERTION"
    with pytest.raises(ValidationError):
        OSSCorpus.model_validate(broken)
    broken = bound.corpus.model_dump(mode="json")
    broken["repositories"][0]["commit_sha"] = "main"
    with pytest.raises(ValidationError):
        OSSCorpus.model_validate(broken)
    broken = bound.corpus.model_dump(mode="json")
    broken["repositories"][0]["selection_reason"] = "changed after freeze"
    with pytest.raises(ValidationError, match="fingerprint mismatch"):
        OSSCorpus.model_validate(broken)


def test_fetch_pins_fingerprints_no_execution_and_paths(local_corpus, tmp_path):
    bound, upstream, cache, first, report, _, _, _ = local_corpus
    repo = bound.corpus.repositories[0]
    second_cache = tmp_path / "second"
    runner = LocalTransport(upstream)
    second = fetch_repository(bound, repo, second_cache, runner)
    assert (first.content_fingerprint, first.snapshot_fingerprint) == (
        second.content_fingerprint,
        second.snapshot_fingerprint,
    )
    assert verify_acquisition(bound, repo, cache) == first
    assert not (source_path(cache, repo) / "MUST_NOT_EXECUTE").exists()
    assert all("checkout" not in args and "submodule" not in args for args in runner.commands)
    assert report["iam_nodes"] > 0 and report["parsed"] == 10
    with pytest.raises(ValueError, match="requested commit"):
        fetch_repository(bound, repo, tmp_path / "wrong", LocalTransport(upstream, wrong_pin=True))
    with pytest.raises(ValueError, match="outside Git"):
        cache_root(ROOT / "oss-cache")
    (tmp_path / "escape").symlink_to(cache, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        cache_root(tmp_path / "escape")
    with pytest.raises(ValidationError):
        repo.model_copy(update={"repository_id": "../escape"}).model_validate(
            repo.model_copy(update={"repository_id": "../escape"})
        )
    before = content_identity(source_path(second_cache, repo), bound.policy)[0]
    (source_path(second_cache, repo) / "java/A.java").write_text("tampered\n")
    assert content_identity(source_path(second_cache, repo), bound.policy)[0] != before
    with pytest.raises(ValueError, match="receipt mismatch"):
        verify_acquisition(bound, repo, second_cache)


def test_sampling_blinding_and_output_independence(local_corpus):
    bound, _, cache, _, _, iam, sample, subjects = local_corpus
    again = sample_subjects(
        bound.corpus, bound.freeze, bound.protocol.sampling, tuple(reversed(subjects))
    )
    assert again == sample and len(sample.packets) == 5
    assert {p.rule_id for p in sample.packets} == {f"ARCH20{i}" for i in range(1, 6)}
    altered = iam.model_copy(
        update={
            "metadata": {"model_score": -99, "candidate_present": True, "ai_decision": "SUPPORTED"}
        }
    )
    assert frame_subjects(bound, "fixture-0", altered, cache) == subjects
    packet_view = canonical(sample.packets)
    for forbidden in (
        "model_score",
        "candidate_present",
        "SemanticCandidate",
        "HybridDecision",
        "2ae6c029",
    ):
        assert forbidden not in packet_view
    assert {s for _, s in sample.strata} == {"LOW", "MEDIUM", "HIGH"}
    assert annotation_scope(sample, "fixture-0", "ARCH201", sample.packets[0].subject) == "IN_SCOPE"
    assert (
        annotation_scope(sample, "fixture-0", "ARCH101", sample.packets[0].subject)
        == "OUT_OF_SCOPE"
    )
    with pytest.raises(ValueError, match="duplicate annotation"):
        sample_subjects(
            bound.corpus, bound.freeze, bound.protocol.sampling, (*subjects, subjects[0])
        )
    assert "calibration" not in inspect.getsource(sample_subjects)


def human(packet, reviewer, label):
    return HumanAnnotation(
        annotation_case_id=packet.annotation_case_id,
        packet_fingerprint=packet.fingerprint,
        reviewer_id=reviewer,
        label=label,
        rationale="Unit vector, not an actual OSS human label",
        evidence=packet.evidence[:1],
        uncertainty="CLEAR",
        attestation="HUMAN_REVIEW_COMPLETED",
    )


def test_review_conflict_adjudication_agreement_and_missing_labels(local_corpus):
    _, _, _, _, _, _, sample, _ = local_corpus
    p, q = sample.packets[:2]
    empty = review_annotations(sample, ())
    assert all(c.status == "UNREVIEWED" and c.final_label == "NOT_ANNOTATED" for c in empty.cases)
    single = review_annotations(sample, (human(p, "unit-r1", "POSITIVE"),))
    assert single.cases[0].status == "SINGLE_REVIEW"
    conflict = review_annotations(sample, (human(p, "unit-r2", "NEGATIVE"),), previous=single)
    assert (
        conflict.cases[0].status == "ADJUDICATION_REQUIRED"
        and conflict.cases[0].final_label == "NOT_ANNOTATED"
    )
    adjudication = Adjudication(
        annotation_case_id=p.annotation_case_id,
        adjudicator_id="unit-r3",
        label="UNCERTAIN",
        rationale="Unit adjudication vector",
        evidence=p.evidence[:1],
        attestation="HUMAN_REVIEW_COMPLETED",
    )
    final = review_annotations(sample, (), (adjudication,), previous=conflict)
    assert final.cases[0].status == "ADJUDICATED"
    with pytest.raises(ValueError, match="overwritten"):
        review_annotations(sample, (human(p, "unit-r1", "NEGATIVE"),), previous=single)
    with pytest.raises(ValueError, match="actual conflict"):
        review_annotations(sample, (), (adjudication,))
    reviews = (
        human(p, "unit-r1", "POSITIVE"),
        human(p, "unit-r2", "POSITIVE"),
        human(q, "unit-r1", "NEGATIVE"),
        human(q, "unit-r2", "POSITIVE"),
    )
    result = review_annotations(sample, reviews)
    assert result.cases[0].status == "DOUBLE_REVIEW"
    assert agreement(result, ("unit-r1", "unit-r2")) == {
        "pairs": 2,
        "agreements": 1,
        "agreement_rate": 0.5,
        "kappa": 0.0,
    }
    assert (
        agreement(review_annotations(sample, reviews[:2]), ("unit-r1", "unit-r2"))["kappa"] is None
    )
    with pytest.raises(ValidationError, match="require rationale"):
        human(p, "unit-r1", "POSITIVE").model_copy(update={"evidence": ()}).model_validate(
            human(p, "unit-r1", "POSITIVE").model_copy(update={"evidence": ()})
        )


def test_annotation_export_import_validation_and_cli(local_corpus, tmp_path, capsys, monkeypatch):
    bound, _, cache, _, _, _, sample, _ = local_corpus
    packet_dir = tmp_path / "packets"
    export_annotations(bound, sample, cache, packet_dir)
    assert len(list(packet_dir.glob("oss-*.md"))) == 5
    raw = {"sample_fingerprint": sample.fingerprint, "reviews": [], "adjudications": []}
    result, receipt = import_annotations(bound, sample, cache, raw)
    assert receipt.status == "AWAITING_HUMAN_REVIEW" and not result.reviews
    p = sample.packets[0]
    raw["reviews"] = [human(p, "unit-r1", "NEGATIVE").model_dump(mode="json")]
    result, _ = import_annotations(bound, sample, cache, raw)
    raw["reviews"][0]["annotation_case_id"] = "unknown-case"
    with pytest.raises(ValueError, match="unknown case"):
        import_annotations(bound, sample, cache, raw)
    broken = p.model_dump(mode="python", exclude={"fingerprint"})
    broken["subject"] = p.subject.model_copy(update={"path": "fake.java"})
    fake = seal(AnnotationPacket, **broken)
    altered = seal(
        AnnotationSample,
        **(
            sample.model_dump(mode="python", exclude={"fingerprint"})
            | {"packets": (fake, *sample.packets[1:])}
        ),
    )
    with pytest.raises(ValueError, match="fake subject"):
        validate_sample(bound, altered, cache)
    config = tmp_path / "corpus.json"
    protocol = tmp_path / "protocol.json"
    freeze = tmp_path / "freeze.json"
    for path, value in ((config, bound.corpus), (protocol, bound.protocol), (freeze, bound.freeze)):
        write_new(path, value)
    base = ["benchmark", "oss"]
    common = [
        "--corpus",
        str(config),
        "--protocol",
        str(protocol),
        "--freeze",
        str(freeze),
        "--cache",
        str(tmp_path / "dry-cache"),
    ]
    monkeypatch.setattr(
        "archguard.oss_cli.fetch_repository", lambda *a: pytest.fail("dry-run fetched network")
    )
    assert main([*base, "fetch", *common, "--dry-run"]) == 0
    assert not (tmp_path / "dry-cache").exists()
    capsys.readouterr()
    assert main([*base, "validate", *common]) == 0
    assert "OSS_ANNOTATION_SEED" in capsys.readouterr().out
    from archguard.benchmark.oss.annotation import SamplingFrame

    common[-1] = str(cache)
    frame = SamplingFrame(
        corpus_fingerprint=bound.corpus.fingerprint,
        corpus_freeze_fingerprint=bound.freeze.fingerprint,
        subjects=local_corpus[-1],
    )
    write_new(tmp_path / "frame.json", frame)
    assert (
        main(
            [
                *base,
                "sample",
                *common,
                "--frame",
                str(tmp_path / "frame.json"),
                "--output",
                str(tmp_path / "frozen-sample"),
            ]
        )
        == 0
    )
    sample_path = tmp_path / "frozen-sample/sample.json"
    assert (
        main(
            [
                *base,
                "annotation-export",
                *common,
                "--sample",
                str(sample_path),
                "--output",
                str(tmp_path / "cli-packets"),
            ]
        )
        == 0
    )
    write_new(
        tmp_path / "empty-reviews.json",
        {
            "sample_fingerprint": json.loads(sample_path.read_text())["fingerprint"],
            "reviews": [],
            "adjudications": [],
        },
    )
    assert (
        main(
            [
                *base,
                "annotation-import",
                *common,
                "--sample",
                str(sample_path),
                "--annotations",
                str(tmp_path / "empty-reviews.json"),
                "--output",
                str(tmp_path / "cli-import"),
            ]
        )
        == 0
    )
    imported = json.loads((tmp_path / "cli-import/annotations.json").read_text())
    assert not imported["reviews"] and all(c["status"] == "UNREVIEWED" for c in imported["cases"])
    capsys.readouterr()


def test_oss_domain_has_no_model_or_io_imports():
    import ast

    for path in (ROOT / "src/archguard/benchmark/oss").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom):
                assert not any(
                    s in (node.module or "")
                    for s in ("calibration", "intelligence", "policies", "infrastructure")
                )
