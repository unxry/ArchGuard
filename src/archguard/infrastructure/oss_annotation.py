"""Bounded human context and source-verified import/export; no prediction access."""

import hashlib
from pathlib import Path
from typing import Any

from archguard.benchmark.models import Locator
from archguard.benchmark.oss.annotation import SamplingSubject, review_annotations
from archguard.benchmark.oss.models import (
    Adjudication,
    AnnotationFreeze,
    AnnotationPacket,
    AnnotationResult,
    AnnotationSample,
    EvidenceReference,
    HumanAnnotation,
    digest,
    seal,
)
from archguard.core.identifiers import NodeId
from archguard.core.model.enums import Language
from archguard.iam.model import ArchitectureModel
from archguard.infrastructure.oss_benchmark import (
    FrozenOSSCorpus,
    source_path,
    verify_acquisition,
    write_new,
)

INSTRUCTIONS = (
    "Review source and documented responsibility independently. Never use detector/model/AI "
    "output as truth. Binary labels need rationale and evidence. Use UNCERTAIN for insufficient "
    "context and OUT_OF_SCOPE when the question does not apply. Additional pinned-source "
    "inspection is allowed: record exact hashes/lines in a separately versioned packet before "
    "import. No implied target layers; absence of annotation is not negative."
)


def frame_subjects(
    bound: FrozenOSSCorpus, repository_id: str, iam: ArchitectureModel, cache: Path
) -> tuple[SamplingSubject, ...]:
    repo = next(r for r in bound.corpus.repositories if r.repository_id == repository_id)
    root = source_path(cache, repo)
    protocol = bound.protocol.sampling
    neighbors: dict[NodeId, set[NodeId]] = {}
    for edge in iam.edges:
        neighbors.setdefault(edge.source_id, set()).add(edge.target_id)
        neighbors.setdefault(edge.target_id, set()).add(edge.source_id)
    nodes = {n.id: n for n in iam.nodes}
    hashes: dict[str, str] = {}
    line_counts: dict[str, int] = {}

    def remember(path: str) -> None:
        if path not in hashes:
            data = (root / path).read_bytes()
            hashes[path] = hashlib.sha256(data).hexdigest()
            line_counts[path] = len(data.decode("utf-8").splitlines())

    readme = root / "README.md"
    if readme.is_file() and readme.stat().st_size <= bound.policy.max_source_file_bytes:
        remember("README.md")
    subjects = []
    symbols = {s.id: s for s in iam.symbols}
    seen_subjects = set()
    for node in sorted(iam.nodes, key=lambda n: (n.qualified_name, str(n.id))):
        if node.kind.value not in protocol.subject_kinds or node.source_location is None:
            continue
        location = node.source_location
        path = root / location.file_path
        if not path.is_file() or path.stat().st_size > bound.policy.max_source_file_bytes:
            continue
        remember(location.file_path)
        references = [
            EvidenceReference(
                path=location.file_path,
                sha256=hashes[location.file_path],
                start_line=location.start_line,
                end_line=min(
                    location.end_line or location.start_line + protocol.max_excerpt_lines - 1,
                    location.start_line + protocol.max_excerpt_lines - 1,
                    line_counts[location.file_path],
                ),
                purpose="DECLARATION",
            )
        ]
        if "README.md" in hashes and line_counts["README.md"]:
            references.append(
                EvidenceReference(
                    path="README.md",
                    sha256=hashes["README.md"],
                    start_line=1,
                    end_line=min(100, line_counts["README.md"]),
                    purpose="DOCUMENTATION",
                )
            )
        related = sorted(
            (
                nodes[n]
                for n in neighbors.get(node.id, ())
                if n in nodes and nodes[n].source_location
            ),
            key=lambda n: (
                str(n.source_location.file_path) if n.source_location else "",
                n.source_location.start_line if n.source_location else 0,
            ),
        )
        seen_paths = {location.file_path}
        for other in related:
            assert other.source_location is not None
            context = other.source_location
            file = root / context.file_path
            if (
                context.file_path in seen_paths
                or not file.is_file()
                or file.stat().st_size > bound.policy.max_source_file_bytes
            ):
                continue
            if len(references) >= protocol.max_context_files:
                break
            remember(context.file_path)
            references.append(
                EvidenceReference(
                    path=context.file_path,
                    sha256=hashes[context.file_path],
                    start_line=context.start_line,
                    end_line=min(
                        context.end_line or context.start_line + protocol.max_excerpt_lines - 1,
                        context.start_line + protocol.max_excerpt_lines - 1,
                        line_counts[context.file_path],
                    ),
                    purpose="DEPENDENCY",
                )
            )
            seen_paths.add(context.file_path)
        for document in repo.architecture_provenance.references:
            if len(references) < protocol.max_context_files:
                references.append(document)
        subject = Locator(
            path=location.file_path,
            language=Language(repo.language),
            qualified_name=node.qualified_name,
            kind=node.kind,
            signature=symbols[node.symbol_id].signature if node.symbol_id in symbols else None,
        )
        identity = digest(subject)
        if identity in seen_subjects:
            continue
        seen_subjects.add(identity)
        packet = seal(
            AnnotationPacket,
            annotation_case_id="frame-" + digest((repository_id, subject))[:24],
            repository_id=repository_id,
            corpus_fingerprint=bound.corpus.fingerprint,
            rule_id="ARCH201",
            question="Sampling frame; final question assigned by frozen hash/stratum protocol",
            subject=subject,
            evidence=tuple(references),
            license_spdx=repo.license_spdx,
            instructions=INSTRUCTIONS,
        )
        subjects.append(
            SamplingSubject(
                repository_id=repository_id,
                packet_template=packet,
                raw_degree=len(neighbors.get(node.id, ())),
            )
        )
    return tuple(subjects)


def validate_sample(bound: FrozenOSSCorpus, sample: AnnotationSample, cache: Path) -> None:
    if (
        sample.corpus_fingerprint != bound.corpus.fingerprint
        or sample.corpus_freeze_fingerprint != bound.freeze.fingerprint
    ):
        raise ValueError("annotation sample/corpus freeze mismatch")
    if sample.sampling_protocol_fingerprint != digest(bound.protocol.sampling):
        raise ValueError("sampling protocol mismatch")
    repositories = {r.repository_id: r for r in bound.corpus.repositories}
    verified = set()
    for packet in sample.packets:
        repo = repositories.get(packet.repository_id)
        if repo is None:
            raise ValueError("unknown annotation repository")
        expected_id = (
            "oss-"
            + digest(
                (bound.corpus.fingerprint, packet.repository_id, packet.rule_id, packet.subject)
            )[:24]
        )
        if packet.annotation_case_id != expected_id:
            raise ValueError("fake subject/case identity does not match frozen scope")
        if packet.rule_id.startswith("ARCH0") and repo.architecture_provenance.status == "NONE":
            raise ValueError("Static conformance requires documented target architecture")
        if repo.repository_id not in verified:
            verify_acquisition(bound, repo, cache)
            verified.add(repo.repository_id)
        root = source_path(cache, repo)
        if packet.subject.path not in {
            e.path for e in packet.evidence if e.purpose == "DECLARATION"
        }:
            raise ValueError("fake subject lacks declaration evidence")
        for reference in packet.evidence:
            path = root / reference.path
            if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
                raise ValueError("annotation source path escape")
            data = path.read_bytes()
            if (
                len(data) > bound.policy.max_source_file_bytes
                or hashlib.sha256(data).hexdigest() != reference.sha256
            ):
                raise ValueError("annotation source hash/budget mismatch")
            lines = data.decode("utf-8").splitlines()
            if reference.end_line > len(lines):
                raise ValueError("annotation evidence line range outside source")


def export_annotations(
    bound: FrozenOSSCorpus, sample: AnnotationSample, cache: Path, destination: Path
) -> None:
    validate_sample(bound, sample, cache)
    destination.mkdir(parents=True, exist_ok=False)
    forms: list[dict[str, Any]] = []
    for packet in sample.packets:
        repo = next(r for r in bound.corpus.repositories if r.repository_id == packet.repository_id)
        root = source_path(cache, repo)
        sections = [
            f"# {packet.annotation_case_id}",
            f"{repo.project} · {packet.rule_id} · {repo.license_spdx}",
            f"Pinned project documentation/source: "
            f"https://github.com/{repo.project}/tree/{repo.commit_sha}",
            packet.question,
            packet.instructions,
            "Allowed labels: POSITIVE / NEGATIVE / UNCERTAIN / OUT_OF_SCOPE.",
        ]
        remaining = bound.protocol.sampling.max_context_bytes
        for evidence in packet.evidence:
            source = (root / evidence.path).read_text(encoding="utf-8").splitlines()
            excerpt = "\n".join(source[evidence.start_line - 1 : evidence.end_line])
            encoded = excerpt.encode("utf-8")
            if len(encoded) > remaining:
                sections.append(
                    f"Context budget exhausted; inspect pinned {evidence.path}:"
                    f"{evidence.start_line}-{evidence.end_line} locally. "
                    "Do not infer a binary label from missing context."
                )
                continue
            remaining -= len(encoded)
            sections.append(
                f"## {evidence.path}:{evidence.start_line}-{evidence.end_line}\n"
                f"SHA256 {evidence.sha256}\n\n```\n{excerpt}\n```"
            )
        (destination / (packet.annotation_case_id + ".md")).write_text(
            "\n\n".join(sections) + "\n", encoding="utf-8"
        )
        forms.append(
            {
                "annotation_case_id": packet.annotation_case_id,
                "packet_fingerprint": packet.fingerprint,
                "reviewer_id": "",
                "label": None,
                "rationale": "",
                "evidence": [packet.evidence[0].model_dump(mode="json")],
                "uncertainty": None,
                "attestation": None,
            }
        )
    write_new(destination / "packets.json", sample.packets)
    write_new(
        destination / "review-form.json",
        {"sample_fingerprint": sample.fingerprint, "reviews": forms, "adjudications": []},
    )
    (destination / "INSTRUCTIONS.md").write_text(
        "Fill review-form.json after actual human inspection. Copy an evidence "
        "reference from packets.json for each binary label. Set your "
        "pseudonymous reviewer ID and HUMAN_REVIEW_COMPLETED attestation only "
        "after completing review. Submit only completed rows; leave incomplete "
        "cases unannotated. Export again to a new directory for a second "
        "independent reviewer. Do not share completed forms before independent "
        "review.\n"
    )


def import_annotations(
    bound: FrozenOSSCorpus,
    sample: AnnotationSample,
    cache: Path,
    raw: dict[str, Any],
    previous: AnnotationResult | None = None,
) -> tuple[AnnotationResult, AnnotationFreeze]:
    validate_sample(bound, sample, cache)
    if (
        set(raw) != {"sample_fingerprint", "reviews", "adjudications"}
        or raw["sample_fingerprint"] != sample.fingerprint
    ):
        raise ValueError("annotation form sample/version mismatch")
    reviews = tuple(HumanAnnotation.model_validate(r) for r in raw["reviews"])
    adjudications = tuple(Adjudication.model_validate(a) for a in raw["adjudications"])
    result = review_annotations(sample, reviews, adjudications, previous)
    reviewed = bool(result.cases) and all(
        c.status in {"DOUBLE_REVIEW", "ADJUDICATED"} for c in result.cases
    )
    receipt = seal(
        AnnotationFreeze,
        corpus_freeze_fingerprint=bound.freeze.fingerprint,
        sample_fingerprint=sample.fingerprint,
        annotation_result_fingerprint=result.fingerprint,
        status="REVIEWED_SCOPE_FROZEN" if reviewed else "AWAITING_HUMAN_REVIEW",
    )
    return result, receipt
