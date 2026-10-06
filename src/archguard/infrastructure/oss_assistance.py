"""Deterministic, local source navigation; never semantic ground truth."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from archguard.benchmark.models import Digest, RuleId
from archguard.benchmark.oss.models import AnnotationSample, Sealed, Slug, seal
from archguard.benchmark.oss.review import (
    PinnedEvidence,
    RevisionCatalog,
    original_evidence,
)
from archguard.core.model.base import DomainModel
from archguard.infrastructure.oss_benchmark import FrozenOSSCorpus, write_new
from archguard.infrastructure.oss_review import atomic_directory, validate_context, verify_evidence

CHECKS = {
    "ARCH201": (
        "Establish the intended role using documentation or structure.",
        "Identify the actual behavior and compare responsibilities.",
        "Can the intended role be established from the available context?",
    ),
    "ARCH202": (
        "Is the subject a controller or presentation component?",
        "Inspect business decisions, calculations, workflow branches and state transitions.",
        "Distinguish those operations from mapping, validation, delegation and error adaptation.",
    ),
    "ARCH203": (
        "Establish the domain/application responsibility and applicable boundary.",
        "Inspect concrete database, framework, vendor or transport implementation details.",
        "Distinguish direct implementation dependencies from abstract interfaces.",
    ),
    "ARCH204": (
        "Find documented or structurally justified placement and responsibility boundaries.",
        "Compare the subject's actual responsibility with that placement evidence.",
        "Is the evidence sufficient to establish an applicable placement boundary?",
    ),
    "ARCH205": (
        "Identify substantial, architecturally different responsibilities.",
        "Inspect presentation, business, persistence and infrastructure operations separately.",
        "Many imports alone do not establish multiple responsibilities.",
    ),
}

CHEATSHEET = """# Human annotation quick sheet

This local assistance is source navigation, not ground truth or a reviewer submission.
Automated evidence summarization reduces annotation burden, but final semantic ground truth
remains human judgment. Both independent reviewers receive the same source context and must
keep their decisions and drafts private from each other.

| Decision | Meaning |
| --- | --- |
| POSITIVE | Applicable question, sufficient context, evidence supports the rule condition. |
| NEGATIVE | Applicable question, sufficient context, evidence supports absence of that condition. |
| UNCERTAIN | Context or responsibility boundary cannot support a decision. |
| OUT_OF_SCOPE | The rule question does not apply to this component. |

Unreviewed is an empty human decision, never a negative. The last two decisions are not binary.

| Rule | What to establish |
| --- | --- |
| ARCH201 | Intended role, actual behavior, and whether they conflict; establish intent first. |
| ARCH202 | Controller/presentation; decisions versus mapping, validation or delegation. |
| ARCH203 | Domain/application boundary; implementation details versus abstractions. |
| ARCH204 | Placement boundary and actual responsibility; missing context: UNCERTAIN/OUT_OF_SCOPE. |
| ARCH205 | Substantial distinct responsibilities; many imports alone are insufficient. |

Open CASE_ID.md alongside the original bundle's CASE_ID.md and packets.json. These excerpts are
a shortlist, not exhaustive context. Candidate ranges have full-file SHA256 hashes. Read the
original packet as needed and manually choose evidence that supports your own rationale.
EXTRA_CONTEXT_RECOMMENDED entries are requests, not added packet evidence: acquire a separately
versioned packet with request-extra-context before using new ranges in a submission. Regenerate
assistance and start a new revision-bound draft after supplementing context. Sample identity stays
unchanged. No assistant evidence is automatically selected for a human decision.

Use the terminal wizard or fill a separate copy of review-form.json manually. The editable human
fields are reviewer_id, label, rationale, uncertainty, attestation and chosen evidence. Preserve
case IDs, sample/packet fingerprints and revisions. The wizard has no default decision and asks
for an explicit human attestation. Skip leaves the case unreviewed. Each confirmed case is saved
to a local draft; rerunning with the same --draft resumes remaining cases. Drafts cannot be
imported as review forms. Explicit draft-export produces a new submission file; canonical
validate/import is a separate subsequent action by the human. No original bundle is edited.

Empty rationale prompts (complete these yourself):

- Observed intended role: ...
- Observed behavior: ...
- Why the condition is / is not present: ...
- Evidence supporting my decision: ...

See docs/annotation-assistance.md for commands. No decision is provided by this package.
"""


class EvidenceCandidate(PinnedEvidence):
    explanation: str
    excerpt: str

    def reference(self) -> PinnedEvidence:
        return PinnedEvidence.model_validate(self.model_dump(exclude={"explanation", "excerpt"}))


class ContextRequest(DomainModel):
    status: Literal["EXTRA_CONTEXT_RECOMMENDED"] = "EXTRA_CONTEXT_RECOMMENDED"
    evidence: PinnedEvidence
    reason: str


class AssistanceCase(DomainModel):
    case_id: Slug
    repository: str
    repository_id: Slug
    commit_sha: str
    rule: RuleId
    subject: str
    subject_path: str
    packet_revision: int
    packet_fingerprint: Digest
    original_packet_fingerprint: Digest
    question: str
    observed_role_evidence: tuple[str, ...]
    observed_behavior: tuple[str, ...]
    important_methods_functions: tuple[str, ...]
    dependency_facts: tuple[str, ...]
    documentation_evidence: tuple[str, ...]
    assistant_evidence_candidates: tuple[EvidenceCandidate, ...]
    ambiguity_notes: tuple[str, ...]
    reviewer_checks: tuple[str, ...]
    extra_context_recommended: tuple[ContextRequest, ...]


class AssistancePackage(Sealed):
    schema_version: Literal["oss-source-assistance-v1"] = "oss-source-assistance-v1"
    scope: Literal["LOCAL_ONLY_SOURCE_NAVIGATION"] = "LOCAL_ONLY_SOURCE_NAVIGATION"
    corpus_fingerprint: Digest
    sample_fingerprint: Digest
    catalog_fingerprint: Digest
    cases: tuple[AssistanceCase, ...]


@dataclass(frozen=True)
class SourceFact:
    type: str
    name: str
    line: int


METHODS = {"declaration_signature"}
CALLS = {"call_lexeme"}
BRANCHES = {"branch_lexeme"}


def _facts(lines: list[str]) -> list[SourceFact]:
    # Mask comments and literals while preserving line numbers. This is lexical navigation.
    masked = re.sub(
        r"/\*.*?\*/|//[^\n]*|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`",
        lambda m: re.sub(r"[^\n]", " ", m.group()),
        "\n".join(lines),
        flags=re.DOTALL,
    ).splitlines()
    result: list[SourceFact] = []
    excluded = {"if", "for", "while", "switch", "catch", "synchronized"}
    for i, line in enumerate(masked, 1):
        declaration = re.search(r"\bfunction\s+([\w$]+)", line) or re.match(
            r"\s*(?:(?:export|default|public|private|protected|static|async|final|abstract)\s+)*"
            r"(?:[\w$<>\[\],.?]+\s+)?(#?[\w$]+)\s*(?:<[^;{}]*>)?\(",
            line,
        )
        method = declaration.group(1) if declaration else None
        if method in excluded or re.match(r"\s*(return|throw|new)\b", line):
            method = None
        if method:
            result.append(SourceFact("declaration_signature", method, i))
        for match in re.finditer(r"(#?[\w$]+(?:\.#?[\w$]+)*)\s*\(", line):
            name = match.group(1)
            if name not in excluded and name != method:
                result.append(SourceFact("call_lexeme", name, i))
        for match in re.finditer(r"\b(if|switch|return|throw)\b", line):
            word = match.group(1)
            kind = "branch_lexeme" if word in {"if", "switch"} else word + "_statement"
            result.append(SourceFact(kind, word, i))
    return result


def _spread(size: int, limit: int) -> list[int]:
    if size <= limit:
        return list(range(size))
    return sorted({i * (size - 1) // (limit - 1) for i in range(limit)})


def _documentation_line(line: str) -> bool:
    return bool(
        re.search(
            r"framework|library|provides|validation|cache|RPC|JSON|features|TypeScript|Java",
            line,
            re.IGNORECASE,
        )
        and not re.search(r"<|badge|shield|sponsor|img|!\[", line, re.IGNORECASE)
    )


def _candidate(
    ref: PinnedEvidence, lines: list[str], start: int, end: int, why: str
) -> EvidenceCandidate:
    start, end = max(ref.start_line, start), min(ref.end_line, end)
    return EvidenceCandidate.model_validate(
        ref.model_dump()
        | {
            "start_line": start,
            "end_line": end,
            "explanation": why,
            "excerpt": "\n".join(f"{i} | {lines[i - 1]}" for i in range(start, end + 1)),
        }
    )


def _ranges(
    ref: PinnedEvidence, lines: list[str], nodes: list[SourceFact]
) -> list[EvidenceCandidate]:
    anchors = [(ref.start_line, "Declaration and structural metadata")]
    methods = [n for n in nodes if n.type in METHODS]
    if methods:
        chosen = sorted({0, len(methods) // 2, len(methods) - 1})
        anchors.extend(
            (methods[i].line, f"Declaration-shaped signature: {methods[i].name}") for i in chosen
        )
    behavior = [n for n in nodes if n.type in BRANCHES]
    if not behavior:
        behavior = [n for n in nodes if n.type in CALLS | {"return_statement", "throw_statement"}]
    if behavior:
        anchors.append((behavior[-1].line, "Final visible branch / operation"))
    if len(anchors) == 1 and ref.end_line - ref.start_line > 8:
        anchors.append(((ref.start_line + ref.end_line) // 2, "Middle of declaration context"))
        anchors.append((max(ref.start_line, ref.end_line - 5), "End of declaration context"))
    result: list[EvidenceCandidate] = []
    for start, why in anchors:
        end = min(start + 5, ref.end_line)
        if not any(e.start_line <= start <= e.end_line for e in result):
            result.append(_candidate(ref, lines, start, end, why))
    return result[:5]


def build_assistance(
    bound: FrozenOSSCorpus, sample: AnnotationSample, cache: Path, catalog: RevisionCatalog
) -> AssistancePackage:
    validate_context(bound, sample, cache, catalog)
    latest = {r.annotation_case_id: r for r in catalog.packets}
    cases: list[AssistanceCase] = []
    for packet in sample.packets:
        revision = latest[packet.annotation_case_id]
        repo = next(r for r in bound.corpus.repositories if r.repository_id == packet.repository_id)
        references = original_evidence(packet, revision) + revision.additional_evidence
        source = next(
            r for r in references if r.purpose == "SOURCE" and r.path == packet.subject.path
        )
        lines = verify_evidence(bound, cache, source)
        all_facts = _facts(lines)
        nodes = [n for n in all_facts if source.start_line <= n.line <= source.end_line]
        methods = tuple(
            dict.fromkeys(f"{n.name} at {source.path}:{n.line}" for n in nodes if n.type in METHODS)
        )
        call_names: dict[str, str] = {}
        for fact in nodes:
            if fact.type in CALLS:
                call_names.setdefault(fact.name, f"{fact.name} at {source.path}:{fact.line}")
        calls = tuple(call_names.values())
        selected_calls = tuple(calls[i] for i in _spread(len(calls), 8))
        role = [
            f"Declaration kind: {packet.subject.kind.value}; "
            f"placement: {source.path}:{source.start_line}-{source.end_line}."
        ]
        for i in range(source.start_line, source.end_line + 1):
            line = lines[i - 1].strip()
            if re.search(r"\b(extends|implements|commandName|description)\b|^@|^\*[^/]", line):
                role.append(f"{source.path}:{i} — {line}")
                if re.search(r"\bdescription\s*=\s*$", line) and i < source.end_line:
                    role.append(f"{source.path}:{i + 1} — {lines[i].strip()}")
        candidates = _ranges(source, lines, nodes)
        docs: list[str] = []
        dependencies: list[str] = []
        for ref in references:
            if ref == source:
                continue
            context = verify_evidence(bound, cache, ref)
            location = f"{ref.path}:{ref.start_line}-{ref.end_line}"
            if ref.purpose == "DOCUMENTATION":
                docs.append(
                    f"Pinned documentation context: {location}; project-level text alone "
                    "does not establish this subject's responsibility."
                )
                start = next(
                    (
                        i
                        for i in range(ref.start_line, ref.end_line + 1)
                        if _documentation_line(context[i - 1])
                    ),
                    ref.start_line,
                )
                if len(candidates) < 8:
                    candidates.append(
                        _candidate(
                            ref,
                            context,
                            start,
                            start + 5,
                            "Pinned documentation prose and adjacent text",
                        )
                    )
                docs.append(f"{ref.path}:{start} — {context[start - 1].strip()}")
                if len(candidates) < 3:
                    following = next(
                        (
                            i
                            for i in range(start + 6, ref.end_line + 1)
                            if _documentation_line(context[i - 1])
                        ),
                        None,
                    )
                    if following is not None:
                        candidates.append(
                            _candidate(
                                ref,
                                context,
                                following,
                                following + 5,
                                "Additional pinned documentation prose",
                            )
                        )
            else:
                dependencies.append(
                    f"Packet {ref.purpose.lower()} context: {location}; "
                    "direction is not inferred from inclusion in the packet."
                )
                if len(candidates) < 8:
                    candidates.append(
                        _candidate(
                            ref,
                            context,
                            ref.start_line,
                            ref.start_line + 5,
                            "Packet dependency/source declaration context",
                        )
                    )
        dependencies[:0] = [
            "Observed call-like lexeme: " + calls[i] for i in _spread(len(calls), 10)
        ]
        ambiguity = [
            "Lexical extraction can omit multiline signatures, templates and dynamic calls; "
            "inspect the numbered source. It does not establish architectural intent "
            "or answer the rule question.",
            "Call syntax does not establish a resolved dependency; packet references do not prove "
            "dependency direction or exhaustive dependents.",
            "Shortlisted excerpts omit other lines; inspect the original packet before "
            "selecting evidence.",
        ]
        extra: list[ContextRequest] = []
        if source.start_line > 1 and (
            source.end_line - source.start_line < 8
            or not docs
            or packet.rule_id in {"ARCH203", "ARCH204"}
        ):
            header_end = min(source.start_line - 1, 24)
            if not any(
                r.path == source.path and r.start_line == 1 and r.end_line >= header_end
                for r in references
            ):
                extra.append(
                    ContextRequest(
                        evidence=source.model_copy(
                            update={"start_line": 1, "end_line": header_end}
                        ),
                        reason="Inspect file imports, package, decorators and documentation "
                        "that are outside this declaration packet.",
                    )
                )
        subject_name = (
            packet.subject.qualified_name.rsplit("::", 1)[-1].split("(", 1)[0].rsplit(".", 1)[-1]
        )
        implementations = [
            n
            for n in all_facts
            if n.type in METHODS and n.name == subject_name and n.line > source.end_line
        ]
        if implementations:
            implementation = implementations[0]
            extra.append(
                ContextRequest(
                    evidence=source.model_copy(
                        update={
                            "start_line": implementation.line,
                            "end_line": min(len(lines), implementation.line + 39),
                        }
                    ),
                    reason="A following signature with the same name lies outside the frozen "
                    "declaration. Inspect implementation/overload context and request more ranges "
                    "if needed.",
                )
            )
        if not docs:
            ambiguity.append(
                "No documentation reference is present in this packet; intent and placement "
                "need human verification."
            )
        if source.end_line - source.start_line < 8:
            ambiguity.append(
                "The declaration spans fewer than nine lines; surrounding owner/caller context "
                "may be needed. Only distinct available ranges are listed."
            )
        cases.append(
            AssistanceCase(
                case_id=packet.annotation_case_id,
                repository=repo.project,
                repository_id=packet.repository_id,
                commit_sha=revision.commit_sha,
                rule=packet.rule_id,
                subject=packet.subject.qualified_name,
                subject_path=packet.subject.path,
                packet_revision=revision.revision,
                packet_fingerprint=revision.fingerprint,
                original_packet_fingerprint=packet.fingerprint,
                question=revision.review_question,
                observed_role_evidence=tuple(role[:10]),
                observed_behavior=(
                    f"Within the declaration range: {len(calls)} distinct call-like "
                    f"names; {sum(n.type in BRANCHES for n in nodes)} branch keyword locations; "
                    f"{sum(n.type == 'return_statement' for n in nodes)} return statements.",
                )
                + tuple("Call-like lexeme: " + c for c in selected_calls),
                important_methods_functions=methods[:10],
                dependency_facts=tuple(dependencies),
                documentation_evidence=tuple(docs),
                assistant_evidence_candidates=tuple(candidates),
                ambiguity_notes=tuple(ambiguity),
                reviewer_checks=CHECKS[packet.rule_id],
                extra_context_recommended=tuple(extra),
            )
        )
    return seal(
        AssistancePackage,
        corpus_fingerprint=sample.corpus_fingerprint,
        sample_fingerprint=sample.fingerprint,
        catalog_fingerprint=catalog.fingerprint,
        cases=tuple(cases),
    )


def render_case(case: AssistanceCase, *, behavior_first: bool = False) -> str:
    sections = [
        f"# {case.case_id}",
        f"Repository: {case.repository}\n\nRule: {case.rule}\n\nSubject: {case.subject}\n\n"
        f"Commit: {case.commit_sha}\n\nPacket revision: {case.packet_revision}\n\n"
        f"Packet fingerprint: {case.packet_fingerprint}\n\n"
        f"Original packet fingerprint: {case.original_packet_fingerprint}",
        "## Question\n\n" + case.question,
    ]
    observations: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("Observed role evidence", case.observed_role_evidence),
        ("Observed implementation structure", case.observed_behavior),
        ("Methods/functions", case.important_methods_functions),
        ("Dependencies / dependents", case.dependency_facts),
        ("Documentation", case.documentation_evidence),
    )
    if behavior_first:
        observations = tuple(observations[i] for i in (1, 3, 2, 0, 4))
    for title, values in observations:
        sections.append(
            "## "
            + title
            + "\n\n"
            + ("\n".join("- " + v for v in values) or "No such facts established in this packet.")
        )
    sections.append(
        "## Assistant evidence candidates\n\nThese are navigation candidates. "
        "The human selects evidence after reading the packet."
    )
    for i, e in enumerate(case.assistant_evidence_candidates, 1):
        url = (
            f"https://github.com/{case.repository}/blob/{case.commit_sha}/{e.path}"
            f"#L{e.start_line}-L{e.end_line}"
        )
        sections.append(
            f"### [{i}] {e.purpose}: [{e.path}:{e.start_line}-{e.end_line}]({url})\n\n"
            f"{e.explanation}\n\nSHA256 (full file): {e.sha256}\n\n```text\n{e.excerpt}\n```"
        )
    for title, values in (
        ("Potential ambiguity", case.ambiguity_notes),
        ("Reviewer checklist", case.reviewer_checks),
    ):
        sections.append("## " + title + "\n\n" + "\n".join("- " + v for v in values))
    if case.extra_context_recommended:
        sections.append(
            "## EXTRA_CONTEXT_RECOMMENDED\n\nThese ranges are outside the current packet; "
            "version context before citing them."
        )
        for request in case.extra_context_recommended:
            ref = request.evidence
            sections.append(
                f"- {ref.repository_id} @ {ref.commit_sha} · "
                f"{ref.path}:{ref.start_line}-{ref.end_line} · {ref.purpose} · "
                f"SHA256 {ref.sha256}\n  {request.reason}"
            )
    sections.append("NO LABEL PROVIDED.")
    return "\n\n".join(sections) + "\n"


def publish_assistance(
    package: AssistancePackage,
    destination: Path,
    *,
    behavior_first: bool = False,
    cheatsheet: str = CHEATSHEET,
) -> None:
    def build(stage: Path) -> None:
        write_new(stage / "assistance.json", package)
        (stage / "ANNOTATION_CHEATSHEET.md").write_text(cheatsheet, encoding="utf-8")
        rows = [
            "# Local annotation assistance",
            "",
            "Source navigation only. Open each card beside its original packet. "
            + (
                "Independent Reviewer B source pass; human responses remain private."
                if behavior_first
                else "Both reviewers use this same package; decisions remain private."
            ),
            "",
            "[Human quick sheet](ANNOTATION_CHEATSHEET.md)",
            "",
            f"Sample fingerprint: {package.sample_fingerprint}",
            "",
            "| Case | Repository | Rule | Subject | Candidates | Extra context |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for case in package.cases:
            (stage / (case.case_id + ".md")).write_text(
                render_case(case, behavior_first=behavior_first), encoding="utf-8"
            )
            context = (
                "EXTRA_CONTEXT_RECOMMENDED"
                if case.extra_context_recommended
                else "No additional range identified"
            )
            rows.append(
                f"| [{case.case_id}]({case.case_id}.md) | {case.repository} | {case.rule} | "
                f"{case.subject.replace('|', '/')} | "
                f"{len(case.assistant_evidence_candidates)} | {context} |"
            )
        (stage / "index.md").write_text("\n".join(rows) + "\n", encoding="utf-8")

    atomic_directory(destination, build)
