"Explicit OSS research stages. No annotation or model evaluation runs implicitly."

import argparse
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from archguard.benchmark.oss.annotation import SamplingFrame, SamplingSubject, sample_subjects
from archguard.benchmark.oss.models import (
    AnnotationResult,
    AnnotationSample,
    SampleFreeze,
    canonical,
    digest,
    seal,
)
from archguard.iam.model import ArchitectureModel
from archguard.infrastructure.hybrid_configuration import _read
from archguard.infrastructure.oss_annotation import (
    export_annotations,
    frame_subjects,
    import_annotations,
)
from archguard.infrastructure.oss_benchmark import (
    cache_root,
    characterize_repository,
    fetch_repository,
    load_corpus,
    source_path,
    write_new,
)


def oss_arguments(parser: argparse.ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="oss_command", required=True)
    for name in (
        "validate",
        "fetch",
        "characterize",
        "sample",
        "annotation-export",
        "annotation-import",
    ):
        child = commands.add_parser(name)
        child.add_argument(
            "--corpus", type=Path, default=Path("experiments/oss/oss-corpus-v1.json")
        )
        child.add_argument(
            "--protocol", type=Path, default=Path("experiments/oss/selection-protocol-v1.json")
        )
        child.add_argument(
            "--freeze", type=Path, default=Path("experiments/oss/corpus-freeze.json")
        )
        child.add_argument("--cache", type=Path)
        child.add_argument("--output", type=Path)
        if name == "fetch":
            child.add_argument("--dry-run", action="store_true")
        if name == "sample":
            child.add_argument("--frame", type=Path, required=True)
        if name in {"annotation-export", "annotation-import"}:
            child.add_argument("--sample", type=Path, required=True)
            child.add_argument("--sample-freeze", type=Path)
        if name == "annotation-import":
            child.add_argument("--annotations", type=Path, required=True)
            child.add_argument("--previous", type=Path)


def execute_oss(args: argparse.Namespace) -> int:
    try:
        return _execute(args)
    except (OSError, subprocess.SubprocessError) as error:
        raise ValueError("OSS I/O/acquisition failed; corpus unchanged") from error


def _execute(args: argparse.Namespace) -> int:
    bound = load_corpus(args.corpus, args.protocol, args.freeze)
    cache = cache_root(args.cache)
    if args.output and args.output.exists():
        raise ValueError("OSS outputs immutable; choose a new output path")
    summary: dict[str, Any]
    if args.oss_command == "validate":
        summary = {
            "dataset_id": bound.corpus.dataset_id,
            "version": bound.corpus.version,
            "status": bound.corpus.status,
            "corpus_fingerprint": bound.corpus.fingerprint,
            "freeze_fingerprint": bound.freeze.fingerprint,
            "repositories": [
                {
                    "repository_id": r.repository_id,
                    "family_id": r.family_id,
                    "language": r.language,
                    "license": r.license_spdx,
                    "commit": r.commit_sha,
                    "cached": source_path(cache, r).exists(),
                }
                for r in bound.corpus.repositories
            ],
        }
    elif args.oss_command == "fetch":
        if args.dry_run:
            summary = {
                "dry_run": True,
                "limits": bound.protocol.limits,
                "repositories": [
                    {
                        "repository_id": r.repository_id,
                        "url": r.upstream_url,
                        "commit": r.commit_sha,
                        "destination": str(source_path(cache, r)),
                    }
                    for r in bound.corpus.repositories
                ],
            }
        else:
            receipts = tuple(fetch_repository(bound, r, cache) for r in bound.corpus.repositories)
            if sum(r.source_bytes for r in receipts) > bound.protocol.max_corpus_source_bytes:
                raise ValueError("corpus source byte budget exceeded; no analysis permitted")
            summary = {
                "corpus_fingerprint": bound.corpus.fingerprint,
                "acquisitions": [r.model_dump(mode="json") for r in receipts],
            }
    elif args.oss_command == "characterize":
        if args.output is None:
            raise ValueError("characterize requires a new --output directory")
        args.output.mkdir(parents=True)
        private = args.output / "evaluation-private"
        private.mkdir()
        reports: list[dict[str, Any]] = []
        subjects: list[SamplingSubject] = []
        for repository in bound.corpus.repositories:
            try:
                report, context = characterize_repository(bound, repository, cache)
                write_new(private / (repository.repository_id + ".json"), context)
                subjects.extend(
                    frame_subjects(
                        bound,
                        repository.repository_id,
                        ArchitectureModel.model_validate(context["iam"]),
                        cache,
                    )
                )
            except (ValueError, OSError) as error:
                report = {
                    "repository_id": repository.repository_id,
                    "language": repository.language,
                    "status": "ANALYSIS_UNSUPPORTED",
                    "technical_error": type(error).__name__,
                }
            reports.append(report)
        summary = {
            "corpus_fingerprint": bound.corpus.fingerprint,
            "corpus_freeze_fingerprint": bound.freeze.fingerprint,
            "repositories": reports,
            "model_scoring": False,
            "live_ai_calls": 0,
            "cost": None,
        }
        write_new(args.output / "characterization.json", summary)
        frame = SamplingFrame(
            corpus_fingerprint=bound.corpus.fingerprint,
            corpus_freeze_fingerprint=bound.freeze.fingerprint,
            subjects=tuple(subjects),
        )
        write_new(args.output / "sampling-frame.json", frame)
        print(canonical(summary))
        return 0
    elif args.oss_command == "sample":
        if args.output is None:
            raise ValueError("sample requires a new --output directory")
        frame = SamplingFrame.model_validate(_read(args.frame, 33554432))
        if (frame.corpus_fingerprint, frame.corpus_freeze_fingerprint) != (
            bound.corpus.fingerprint,
            bound.freeze.fingerprint,
        ):
            raise ValueError("frame does not belong to frozen corpus")
        sample = sample_subjects(
            bound.corpus, bound.freeze, bound.protocol.sampling, frame.subjects
        )
        args.output.mkdir(parents=True)
        write_new(args.output / "sample.json", sample)
        sample_receipt = seal(
            SampleFreeze,
            corpus_freeze_fingerprint=bound.freeze.fingerprint,
            sample_fingerprint=sample.fingerprint,
            frame_fingerprint=digest(frame),
            sampling_protocol_fingerprint=sample.sampling_protocol_fingerprint,
            frozen_at=datetime.now(UTC).isoformat(),
            cases=len(sample.packets),
        )
        write_new(args.output / "sample-freeze.json", sample_receipt)
        summary = {
            "sample_fingerprint": sample.fingerprint,
            "cases": len(sample.packets),
            "review_status": "UNREVIEWED",
        }
        print(canonical(summary))
        return 0
    elif args.oss_command == "annotation-export":
        if args.output is None:
            raise ValueError("annotation export requires a new --output directory")
        sample = load_sample(args.sample, args.sample_freeze)
        export_annotations(bound, sample, cache, args.output)
        print(canonical({"packets": len(sample.packets), "review_status": "UNREVIEWED"}))
        return 0
    else:
        if args.output is None:
            raise ValueError("annotation import requires a new --output directory")
        sample = load_sample(args.sample, args.sample_freeze)
        previous = (
            AnnotationResult.model_validate(_read(args.previous, 2097152))
            if args.previous
            else None
        )
        raw = _read(args.annotations, 2097152)
        if not isinstance(raw, dict):
            raise ValueError("annotation form must be object")
        result, receipt = import_annotations(bound, sample, cache, raw, previous)
        args.output.mkdir(parents=True)
        write_new(args.output / "annotations.json", result)
        write_new(args.output / "annotation-freeze.json", receipt)
        print(
            canonical(
                {
                    "cases": len(result.cases),
                    "annotation_fingerprint": result.fingerprint,
                    "status": receipt.status,
                }
            )
        )
        return 0
    if args.output:
        write_new(args.output, summary)
    print(canonical(summary))
    return 0


def load_sample(path: Path, freeze_path: Path | None = None) -> AnnotationSample:
    sample = AnnotationSample.model_validate(_read(path, 2097152))
    receipt = SampleFreeze.model_validate(
        _read(freeze_path or path.parent / "sample-freeze.json", 131072)
    )
    if (
        receipt.sample_fingerprint != sample.fingerprint
        or receipt.corpus_freeze_fingerprint != sample.corpus_freeze_fingerprint
        or receipt.sampling_protocol_fingerprint != sample.sampling_protocol_fingerprint
        or receipt.cases != len(sample.packets)
    ):
        raise ValueError("sample changed after freeze; new sample version required")
    return sample
