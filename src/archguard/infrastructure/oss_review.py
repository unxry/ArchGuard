"""Offline source verification, independent bundles and atomic immutable review snapshots."""

import hashlib
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from archguard.benchmark.oss.models import (
    AnnotationPacket,
    AnnotationSample,
    canonical,
    digest,
    seal,
)
from archguard.benchmark.oss.review import (
    AdjudicationInput,
    PacketRevision,
    PinnedEvidence,
    ReviewedFreeze,
    ReviewInput,
    ReviewStore,
    RevisionCatalog,
    active_reviews,
    append_reviews,
    freeze_reviews,
    original_evidence,
    review_report,
    validate_catalog,
)
from archguard.infrastructure.oss_annotation import validate_sample
from archguard.infrastructure.oss_benchmark import FrozenOSSCorpus, source_path, write_new

QUESTIONS = {
    "ARCH201": (
        "Does the component's implemented responsibility conflict with its documented "
        "or structurally evident intended role? Identify the role and behavior. Use "
        "UNCERTAIN if the role cannot be established."
    ),
    "ARCH202": (
        "If this is a controller/presentation component, does it perform substantial "
        "business decisions, calculations, workflow coordination or state branching? "
        "Mapping, input validation, delegation and error adaptation alone do not "
        "establish a violation. Use OUT_OF_SCOPE if the controller question does not "
        "apply."
    ),
    "ARCH203": (
        "Does domain/application behavior directly depend on infrastructure "
        "implementation details, such as persistence or transport, across an "
        "established responsibility boundary? An abstract interface alone does not "
        "establish a violation. Explain the boundary and concrete behavior."
    ),
    "ARCH204": (
        "Does the component's placement conflict with a documented or manually "
        "justified responsibility boundary? Cite the boundary and placement evidence. "
        "Use UNCERTAIN or OUT_OF_SCOPE if no applicable boundary can be established."
    ),
    "ARCH205": (
        "Does this component combine substantial, architecturally distinct "
        "responsibilities? Describe those responsibilities and their separation. "
        "Import count alone does not establish a violation."
    ),
}

REVIEW_GUIDE = """# Independent human annotation: quick guide

Inspect pinned source, dependencies and project documentation independently. Never use detector,
AI or model assessments as truth. Case selection does not imply that a violation exists.

- **ARCH201**: Implemented behavior conflicts with a documented or structurally evident intended
  role. Establish the role first.
- **ARCH202**: A controller/presentation component makes substantial business decisions,
  calculations, workflow coordination or state-dependent branches. Mapping, validation,
  delegation and error adaptation alone are insufficient.
- **ARCH203**: Domain/application behavior depends on infrastructure implementation details
  across an established boundary. An abstract interface alone is insufficient.
- **ARCH204**: Placement conflicts with documented or manually justified responsibility
  boundaries. Without such evidence use UNCERTAIN or OUT_OF_SCOPE.
- **ARCH205**: Substantial, architecturally distinct responsibilities are combined. Import count
  alone is insufficient.

**POSITIVE:** applicable question, sufficient context, concrete violation evidence.
**NEGATIVE:** applicable question and sufficient source/context to justify absence of that
violation.
**UNCERTAIN:** insufficient context, ambiguous role/boundary or unresolved interpretation.
**OUT_OF_SCOPE:** the question does not apply (for example, a controller question for a library
utility).
An empty form is unreviewed. UNCERTAIN/OUT_OF_SCOPE are never negatives or true negatives.

For each completed row: (1) inspect source and dependencies; (2) inspect relevant pinned docs;
(3) select a label; (4) write your own rationale; (5) copy exact evidence references from
packets.json;
(6) state CLEAR or AMBIGUOUS uncertainty; (7) set a stable pseudonymous reviewer ID;
(8) attest HUMAN_REVIEW_COMPLETED only after your actual review.
Do not include a name or email. No identity or attestation is assigned by this tool.

Fill review-form.json; submit completed rows only. Leave incomplete rows out of the submitted
copy.
Preserve sample fingerprint, packet fingerprint and packet revision. Evidence ranges may be
narrowed.
For additional pinned source, use request-extra-context before import; it creates a new
immutable
packet revision. Record that revision and its fingerprint in your review. Missing context is a
reason
to request more context or choose UNCERTAIN, never a reason to infer a binary label.

Reviewers A and B must work independently without seeing each other's forms. A first review is
provisional. Two distinct reviewers agreeing resolve a case; disagreement requires a distinct
third
human. To correct an imported review, submit a new row with supersedes_review_id equal to the
active review fingerprint. Earlier decisions remain in the history. No labeled OSS examples are
supplied.
"""


def initial_catalog(bound: FrozenOSSCorpus, sample: AnnotationSample) -> RevisionCatalog:
    pins = {r.repository_id: r.commit_sha for r in bound.corpus.repositories}
    return seal(
        RevisionCatalog,
        sample_fingerprint=sample.fingerprint,
        packets=tuple(
            seal(
                PacketRevision,
                annotation_case_id=p.annotation_case_id,
                original_packet_fingerprint=p.fingerprint,
                repository_id=p.repository_id,
                commit_sha=pins[p.repository_id],
                review_question=QUESTIONS[p.rule_id],
                guide_fingerprint=digest(REVIEW_GUIDE),
                revision=1,
            )
            for p in sample.packets
        ),
    )


def verify_evidence(bound: FrozenOSSCorpus, cache: Path, evidence: PinnedEvidence) -> list[str]:
    repo = next(
        (r for r in bound.corpus.repositories if r.repository_id == evidence.repository_id), None
    )
    if repo is None or repo.commit_sha != evidence.commit_sha:
        raise ValueError("evidence repository/commit mismatch")
    root = source_path(cache, repo)
    path = root / evidence.path
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("evidence source path escape")
    data = path.read_bytes()
    if (
        len(data) > bound.policy.max_source_file_bytes
        or hashlib.sha256(data).hexdigest() != evidence.sha256
    ):
        raise ValueError("evidence source hash/budget mismatch")
    lines = data.decode("utf-8").splitlines()
    if evidence.end_line > len(lines):
        raise ValueError("evidence line range outside pinned source")
    return lines


def validate_context(
    bound: FrozenOSSCorpus, sample: AnnotationSample, cache: Path, catalog: RevisionCatalog
) -> None:
    validate_sample(bound, sample, cache)
    validate_catalog(sample, catalog)
    pins = {r.repository_id: r.commit_sha for r in bound.corpus.repositories}
    for revision in catalog.packets:
        if revision.commit_sha != pins[revision.repository_id]:
            raise ValueError("packet revision commit mismatch")
        for reference in revision.additional_evidence:
            verify_evidence(bound, cache, reference)


def atomic_directory(destination: Path, build: Callable[[Path], None]) -> None:
    if destination.exists() or destination.is_symlink():
        raise ValueError("review outputs immutable; choose a new directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".archguard-review-", dir=destination.parent) as temporary:
        stage = Path(temporary) / "payload"
        stage.mkdir()
        build(stage)
        if destination.exists() or destination.is_symlink():
            raise ValueError("review outputs immutable; choose a new directory")
        stage.rename(destination)


def blank_decision(packet: AnnotationPacket, revision: PacketRevision) -> dict[str, Any]:
    return {
        "annotation_case_id": packet.annotation_case_id,
        "packet_fingerprint": revision.fingerprint,
        "packet_revision": revision.revision,
        "label": None,
        "rationale": "",
        "evidence": [],
        "uncertainty": None,
        "attestation": None,
    }


def render_packet(
    bound: FrozenOSSCorpus, sample: AnnotationSample, cache: Path, revision: PacketRevision
) -> tuple[str, dict[str, Any]]:
    packet = next(p for p in sample.packets if p.annotation_case_id == revision.annotation_case_id)
    repo = next(r for r in bound.corpus.repositories if r.repository_id == packet.repository_id)
    if revision.guide_fingerprint != digest(REVIEW_GUIDE):
        raise ValueError("packet requires its original review guide for rendering")
    references = original_evidence(packet, revision) + revision.additional_evidence
    sections = [
        f"# {packet.annotation_case_id}",
        f"Repository: {repo.project} · {packet.rule_id} · {repo.license_spdx}",
        f"Subject: {packet.subject.qualified_name} ({packet.subject.kind.value})",
        f"Commit: {repo.commit_sha}\n\nPacket revision: {revision.revision}\n\n"
        f"Packet fingerprint: {revision.fingerprint}\n\n"
        f"Original packet fingerprint: {packet.fingerprint}",
        f"Pinned documentation/source: https://github.com/{repo.project}/tree/{repo.commit_sha}",
        "## Review question\n\n" + revision.review_question,
        "Apply the quick guide. Request more pinned context when needed. "
        "No binary label is implied.",
    ]
    context_bytes = 0
    declaration_visible = False
    for reference in references:
        lines = verify_evidence(bound, cache, reference)
        selected = range(reference.start_line - 1, reference.end_line)
        excerpt = "\n".join(f"{i + 1} | {lines[i]}" for i in selected)
        if not any(lines[i].strip() for i in selected):
            raise ValueError("empty source context")
        context_bytes += len(excerpt.encode("utf-8"))
        # Supplements may enlarge context, but no silent truncation is permitted.
        if context_bytes > 1048576:
            raise ValueError("packet context exceeds 1 MiB; request smaller context ranges")
        declaration_name = packet.subject.qualified_name.rsplit("::", 1)[-1]
        declaration_name = declaration_name.split("(", 1)[0].rsplit(".", 1)[-1]
        declaration_visible |= (
            reference.purpose == "SOURCE"
            and reference.path == packet.subject.path
            and declaration_name in excerpt
        )
        sections.append(
            f"## {reference.purpose}: {reference.path}:"
            f"{reference.start_line}-{reference.end_line}\n\nSHA256: {reference.sha256}\n\n"
            f"```text\n{excerpt}\n```\n\nPinned source: "
            f"https://github.com/{repo.project}/blob/{repo.commit_sha}/{reference.path}"
            f"#L{reference.start_line}-L{reference.end_line}"
        )
    if not declaration_visible:
        raise ValueError("packet lacks visible declaration context")
    audit = {
        "annotation_case_id": packet.annotation_case_id,
        "packet_revision": revision.revision,
        "references": len(references),
        "context_bytes": context_bytes,
        "source_exists": True,
        "hashes_valid": True,
        "line_ranges_valid": True,
        "declaration_visible": declaration_visible,
        "question_visible": True,
        "truncated": False,
    }
    return "\n\n".join(sections) + "\n", audit


def prepare_bundles(
    bound: FrozenOSSCorpus,
    sample: AnnotationSample,
    cache: Path,
    catalog: RevisionCatalog,
    destination: Path,
) -> dict[str, Any]:
    validate_context(bound, sample, cache, catalog)
    latest = {p.annotation_case_id: p for p in catalog.packets}
    rendered = {
        p.annotation_case_id: render_packet(bound, sample, cache, latest[p.annotation_case_id])
        for p in sample.packets
    }
    manifests: dict[str, Any] = {}

    def build(stage: Path) -> None:
        write_new(stage / "packet-revisions.json", catalog)
        for slot in ("a", "b"):
            bundle = stage / ("reviewer-" + slot)
            bundle.mkdir()
            index = [
                "# Review cases",
                "",
                "| # | Repository | Question | Subject | Packet |",
                "| --- | --- | --- | --- | --- |",
            ]
            forms, packets, audit = [], [], []
            for i, packet in enumerate(sample.packets, 1):
                revision = latest[packet.annotation_case_id]
                text, quality = rendered[packet.annotation_case_id]
                (bundle / (packet.annotation_case_id + ".md")).write_text(text, encoding="utf-8")
                index.append(
                    f"| {i} | {packet.repository_id} | {packet.rule_id} | "
                    f"{packet.subject.qualified_name.replace('|', '/')} | "
                    f"[Open]({packet.annotation_case_id}.md) |"
                )
                forms.append(
                    blank_decision(packet, revision)
                    | {"reviewer_id": None, "supersedes_review_id": None}
                )
                packets.append(
                    {
                        "revision": revision,
                        "evidence": original_evidence(packet, revision)
                        + revision.additional_evidence,
                    }
                )
                audit.append(quality)
            (bundle / "index.md").write_text("\n".join(index) + "\n", encoding="utf-8")
            (bundle / "README.md").write_text(REVIEW_GUIDE, encoding="utf-8")
            write_new(
                bundle / "review-form.json",
                {"sample_fingerprint": sample.fingerprint, "reviews": forms, "adjudications": []},
            )
            write_new(bundle / "packets.json", packets)
            write_new(bundle / "packet-quality.json", audit)
            files = tuple(
                (p.name, hashlib.sha256(p.read_bytes()).hexdigest())
                for p in sorted(bundle.iterdir())
            )
            content_fingerprint = digest(files)
            payload = {
                "schema_version": "oss-independent-review-bundle-v1",
                "slot": slot,
                "sample_fingerprint": sample.fingerprint,
                "catalog_fingerprint": catalog.fingerprint,
                "content_fingerprint": content_fingerprint,
                "files": files,
                "prefilled_labels": 0,
                "assigned_reviewer_ids": 0,
            }
            manifest = payload | {"fingerprint": digest(payload)}
            write_new(bundle / "bundle-manifest.json", manifest)
            manifests[slot] = manifest
        if manifests["a"]["content_fingerprint"] != manifests["b"]["content_fingerprint"]:
            raise ValueError("independent bundle context mismatch")

    atomic_directory(destination, build)
    return manifests


def supplement_context(
    bound: FrozenOSSCorpus,
    sample: AnnotationSample,
    cache: Path,
    catalog: RevisionCatalog,
    case_id: str,
    references: tuple[PinnedEvidence, ...],
    destination: Path,
) -> RevisionCatalog:
    validate_context(bound, sample, cache, catalog)
    previous = next((p for p in reversed(catalog.packets) if p.annotation_case_id == case_id), None)
    if previous is None or not references:
        raise ValueError("extra context requires a known case and additional references")
    revision = seal(
        PacketRevision,
        annotation_case_id=case_id,
        original_packet_fingerprint=previous.original_packet_fingerprint,
        repository_id=previous.repository_id,
        commit_sha=previous.commit_sha,
        review_question=previous.review_question,
        guide_fingerprint=previous.guide_fingerprint,
        revision=previous.revision + 1,
        previous_packet_fingerprint=previous.fingerprint,
        additional_evidence=previous.additional_evidence + references,
    )
    result = seal(
        RevisionCatalog,
        sample_fingerprint=sample.fingerprint,
        packets=catalog.packets + (revision,),
    )
    validate_context(bound, sample, cache, result)
    rendered, quality = render_packet(bound, sample, cache, revision)

    def build(stage: Path) -> None:
        write_new(stage / "packet-revisions.json", result)
        write_new(stage / "packet-quality.json", quality)
        (stage / (case_id + ".md")).write_text(rendered, encoding="utf-8")
        write_new(
            stage / "packets.json",
            {
                "revision": revision,
                "evidence": original_evidence(
                    next(p for p in sample.packets if p.annotation_case_id == case_id), revision
                )
                + revision.additional_evidence,
            },
        )

    atomic_directory(destination, build)
    return result


def import_review_batch(
    bound: FrozenOSSCorpus,
    sample: AnnotationSample,
    cache: Path,
    catalog: RevisionCatalog,
    raw: dict[str, Any],
    previous: ReviewStore | None = None,
) -> ReviewStore:
    validate_context(bound, sample, cache, catalog)
    if (
        set(raw) != {"sample_fingerprint", "reviews", "adjudications"}
        or raw["sample_fingerprint"] != sample.fingerprint
    ):
        raise ValueError("review form sample/schema mismatch")
    if not isinstance(raw["reviews"], list) or not isinstance(raw["adjudications"], list):
        raise ValueError("review form requires arrays")
    reviews = tuple(ReviewInput.model_validate(r) for r in raw["reviews"])
    adjudications = tuple(AdjudicationInput.model_validate(a) for a in raw["adjudications"])
    for decision in (*reviews, *adjudications):
        for evidence in decision.evidence:
            verify_evidence(bound, cache, evidence)
    return append_reviews(sample, catalog, reviews, adjudications, previous)


def publish_store(
    sample: AnnotationSample, catalog: RevisionCatalog, store: ReviewStore, destination: Path
) -> None:
    report = review_report(sample, store)

    def build(stage: Path) -> None:
        write_new(stage / "reviews.json", store)
        write_new(stage / "packet-revisions.json", catalog)
        write_new(stage / "review-report.json", report)
        write_new(
            stage / "pending-freeze.json",
            {
                "status": report.readiness,
                "completed_annotation_freeze": False,
                "sample_fingerprint": sample.fingerprint,
                "store_fingerprint": store.fingerprint,
                "unresolved_cases": report.counts.unreviewed
                + report.counts.single_review
                + report.counts.conflicts,
            },
        )

    atomic_directory(destination, build)


def export_adjudication(
    bound: FrozenOSSCorpus,
    sample: AnnotationSample,
    cache: Path,
    catalog: RevisionCatalog,
    store: ReviewStore,
    destination: Path,
) -> int:
    validate_context(bound, sample, cache, catalog)
    append_reviews(sample, catalog, previous=store)
    conflicts = tuple(c for c in store.cases if c.status == "ADJUDICATION_REQUIRED")
    if not conflicts:
        raise ValueError("no actual human conflicts to export")
    active = active_reviews(store)
    latest = {p.annotation_case_id: p for p in catalog.packets}

    def build(stage: Path) -> None:
        forms = []
        for case in conflicts:
            revision = latest[case.annotation_case_id]
            packet = next(
                p for p in sample.packets if p.annotation_case_id == case.annotation_case_id
            )
            rendered, _ = render_packet(bound, sample, cache, revision)
            pair = active[case.annotation_case_id]
            # Only adjudicators see the actual conflicting labels and rationales.
            rendered += (
                "\n## Independent human reviews\n\n"
                + "\n\n".join(canonical(r) for r in pair)
                + "\n"
            )
            (stage / (case.annotation_case_id + ".md")).write_text(rendered, encoding="utf-8")
            forms.append(
                blank_decision(packet, revision)
                | {
                    "adjudicator_id": None,
                    "review_ids": tuple(r.fingerprint for r in pair),
                    "supersedes_adjudication_id": None,
                }
            )
        (stage / "README.md").write_text(
            "A distinct third human must inspect the source and both human rationales, "
            "then complete review-form.json. No automated adjudication is supplied.\n"
            + REVIEW_GUIDE,
            encoding="utf-8",
        )
        write_new(
            stage / "review-form.json",
            {"sample_fingerprint": sample.fingerprint, "reviews": [], "adjudications": forms},
        )
        write_new(stage / "packet-revisions.json", catalog)

    atomic_directory(destination, build)
    return len(conflicts)


def publish_freeze(
    sample: AnnotationSample, catalog: RevisionCatalog, store: ReviewStore, destination: Path
) -> ReviewedFreeze:
    receipt = freeze_reviews(sample, catalog, store)

    def build(stage: Path) -> None:
        write_new(stage / "annotation-freeze.json", receipt)
        write_new(stage / "review-report.json", review_report(sample, store, frozen=True))

    atomic_directory(destination, build)
    return receipt
