"""Offline handoff rendering and immutable independent human submission storage."""

import hashlib
import json
import re
from collections import Counter
from html import escape
from pathlib import Path
from typing import Any

from archguard.benchmark.oss.models import digest
from archguard.benchmark.semantic_review import (
    ReviewerABundle,
    ReviewerASubmission,
    validate_submission,
)
from archguard.infrastructure.oss_benchmark import write_new
from archguard.infrastructure.oss_review import atomic_directory

INSTRUCTIONS = """Reviewer A: independent human review

Use only this package. Inspect every frozen case and its target rule guidance.
For each case, enter exactly one of POSITIVE, NEGATIVE, UNCERTAIN, OUT_OF_SCOPE
in response-template.json. Write your own concise rationale, reference at least
one evidence_id and its inclusive source line range, and optionally add a note.
Keep every blinded ID and the bundle fingerprint unchanged. Empty fields are
unreviewed; no decision is supplied or selected by this package.

The target rule rubric, general guidance and architecture contract are frozen.
Only the evidence already in your bundle is available; do not obtain additional
case material. State evidence limitations honestly in your own rationale.

You must be a real human. Do not use a model or detector to decide or suggest
answers or to write rationales. Do not receive Reviewer B answers. Do not share
answers with Reviewer B before both independent submissions have been frozen.

Enter your real reviewer identity in reviewer_identity. This is self-declared;
the software does not verify identity or prove human authorship/independence.
Set attestation to REAL_HUMAN_INDEPENDENT_REVIEW only after your own review of
all 100 cases. This declares that you followed these independence instructions.
Save the completed copy as completed-response.json and return it privately to
the coordinator, not to another reviewer. Keep the original bundle unchanged.
Do not edit submission-schema.json or handoff-freeze.json.
No upload, provider call, automatic answer or evaluation is performed here.
"""


def audit_bundle(bundle: ReviewerABundle) -> None:
    forbidden = {
        "pair_id",
        "matched_pair_id",
        "operator_id",
        "expected_semantic_effect",
        "construction_intent",
        "private_blinding_seed",
        "mutation_case_id",
        "control_case_id",
        "provenance",
        "private_provenance",
        "origin_project",
        "judgment",
        "answer",
        "label",
        "final_human_label",
        "rationale",
        "reviewer_identity",
        "reviewer_b_answers",
        "reviewer_b_order",
        "ai_results",
        "detector_results",
        "static_predictions",
        "graph_predictions",
        "structural_v2_predictions",
        "hybrid_predictions",
        "adjudication_data",
        "source_transformations",
    }

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            if forbidden.intersection(value):
                raise ValueError("forbidden review package metadata")
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, str) and re.search(
            r"MUTATION_CANDIDATE|MATCHED_CONTROL|hp-[a-f0-9]{32}|intended-positive|intended-negative",
            value,
        ):
            raise ValueError("construction metadata visible in review package")

    walk(bundle.model_dump(mode="json"))


def load_bundle(path: Path, expected_fingerprint: str) -> ReviewerABundle:
    bundle = ReviewerABundle.model_validate_json(path.read_bytes())
    if bundle.fingerprint != expected_fingerprint:
        raise ValueError("Reviewer A frozen bundle fingerprint mismatch")
    audit_bundle(bundle)
    return bundle


def blank_template(bundle: ReviewerABundle) -> dict[str, Any]:
    return {
        "schema_version": "semantic-holdout-human-submission-v1",
        "reviewer_slot": "A",
        "bundle_fingerprint": bundle.fingerprint,
        "reviewer_identity": "",
        "attestation": None,
        "responses": [
            {
                "blinded_id": p.blinded_id,
                "decision": None,
                "rationale": "",
                "evidence": [],
                "note": "",
            }
            for p in bundle.packets
        ],
    }


def render_handoff(bundle: ReviewerABundle) -> str:
    sections = []
    navigation = []
    guidance = bundle.guidance
    for number, packet in enumerate(bundle.packets, 1):
        identifier = escape(packet.blinded_id, quote=True)
        navigation.append(f'<li><a href="#{identifier}">{identifier}</a></li>')
        source_sections = []
        for source in packet.evidence:
            lines = "\n".join(
                f"{i:4}  {escape(line)}" for i, line in enumerate(source.text.splitlines(), 1)
            )
            source_sections.append(
                f"<details open><summary>{escape(source.evidence_id)} · {escape(source.path)}"
                f"</summary><p>SHA256: <code>{source.sha256}</code></p><pre>{lines}</pre></details>"
            )
        sections.append(
            f'<section id="{identifier}"><h2>{number}. {identifier}</h2>'
            f"<p>{escape(packet.rule_id)} · {escape(packet.language)}</p>"
            f"<p>Target: {escape(packet.target_component)} · {escape(packet.target_path)}</p>"
            "<h3>Frozen architecture contract</h3>"
            f"<pre>{escape(packet.architecture_contract)}</pre>"
            "<h3>Frozen target rule guidance</h3>"
            f"<p>{escape(guidance['rules'][packet.rule_id])}</p>"
            + "".join(source_sections)
            + '<p><a href="#contents">Back to case list</a></p></section>'
        )
    return (
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
        "style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'\">"
        "<title>Independent human review — Reviewer A</title>"
        "<style>body{font:16px system-ui;max-width:1050px;margin:2rem auto;padding:1rem}"
        "pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:14px}"
        "section{border-top:1px solid #aaa;margin-top:2rem}li{margin:.25rem 0}"
        "summary{cursor:pointer}details{margin:1rem 0}</style><body>"
        "<h1>Reviewer A — 100 frozen cases</h1>"
        f"<p>Bundle fingerprint: <code>{bundle.fingerprint}</code></p>"
        f"<pre>{escape(INSTRUCTIONS)}</pre><h2>Frozen general guidance</h2>"
        f"<p>{escape(guidance['general'])}</p><p>{escape(guidance['arch201_vs_arch205'])}</p>"
        '<h2 id="contents">Cases in frozen Reviewer A order</h2><ol>'
        + "".join(navigation)
        + "</ol>"
        + "".join(sections)
        + "</body></html>\n"
    )


def prepare_handoff(bundle_path: Path, expected_fingerprint: str, destination: Path) -> str:
    bundle = load_bundle(bundle_path, expected_fingerprint)
    raw_bundle = bundle_path.read_bytes()
    contents = {
        "bundle-v1.json": raw_bundle,
        "index.html": render_handoff(bundle).encode(),
        "README.txt": INSTRUCTIONS.encode(),
        "response-template.json": (json.dumps(blank_template(bundle), indent=2) + "\n").encode(),
        "submission-schema.json": (
            json.dumps(ReviewerASubmission.model_json_schema(), indent=2) + "\n"
        ).encode(),
    }
    receipt = {
        "schema_version": "reviewer-a-handoff-freeze-v1",
        "bundle_fingerprint": bundle.fingerprint,
        "case_count": 100,
        "prepopulated_answers": 0,
        "files": {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()},
    }
    receipt["fingerprint"] = digest(receipt)

    def build(stage: Path) -> None:
        stage.chmod(0o700)
        for name, data in contents.items():
            with (stage / name).open("xb") as output:
                output.write(data)
        write_new(stage / "handoff-freeze.json", receipt)

    atomic_directory(destination, build)
    return str(receipt["fingerprint"])


def verify_handoff(destination: Path, expected_fingerprint: str) -> str:
    receipt = json.loads((destination / "handoff-freeze.json").read_bytes())
    if receipt["fingerprint"] != digest({k: v for k, v in receipt.items() if k != "fingerprint"}):
        raise ValueError("handoff freeze fingerprint mismatch")
    bundle = load_bundle(destination / "bundle-v1.json", expected_fingerprint)
    expected_contents = {
        "index.html": render_handoff(bundle).encode(),
        "README.txt": INSTRUCTIONS.encode(),
        "response-template.json": (json.dumps(blank_template(bundle), indent=2) + "\n").encode(),
        "submission-schema.json": (
            json.dumps(ReviewerASubmission.model_json_schema(), indent=2) + "\n"
        ).encode(),
    }
    if receipt["bundle_fingerprint"] != bundle.fingerprint or (
        receipt["case_count"],
        receipt["prepopulated_answers"],
    ) != (100, 0):
        raise ValueError("handoff cohort/blank answer mismatch")
    required = {*expected_contents, "bundle-v1.json", "handoff-freeze.json"}
    if {p.name for p in destination.iterdir()} != required or set(receipt["files"]) != (
        required - {"handoff-freeze.json"}
    ):
        raise ValueError("unexpected handoff files")
    for name, expected in receipt["files"].items():
        path = destination / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("handoff artifact changed")
        if name in expected_contents and path.read_bytes() != expected_contents[name]:
            raise ValueError("handoff differs from frozen source-only rendering")
    return str(receipt["fingerprint"])


def verify_submission_contract(destination: Path, expected_fingerprint: str) -> str:
    """Validate frozen input contracts even after the human renames their blank form."""
    receipt = json.loads((destination / "handoff-freeze.json").read_bytes())
    if receipt["fingerprint"] != digest({k: v for k, v in receipt.items() if k != "fingerprint"}):
        raise ValueError("handoff freeze fingerprint mismatch")
    if receipt["bundle_fingerprint"] != expected_fingerprint:
        raise ValueError("frozen submission contract bundle mismatch")
    for name in ("bundle-v1.json", "submission-schema.json"):
        path = destination / name
        if (
            path.is_symlink()
            or hashlib.sha256(path.read_bytes()).hexdigest() != receipt["files"][name]
        ):
            raise ValueError("frozen submission contract changed")
    load_bundle(destination / "bundle-v1.json", expected_fingerprint)
    if json.loads((destination / "submission-schema.json").read_bytes()) != (
        ReviewerASubmission.model_json_schema()
    ):
        raise ValueError("submission validator differs from the frozen schema")
    return str(receipt["fingerprint"])


def audit_submission(submission: ReviewerASubmission) -> None:
    """Check private metadata markers only; never evaluate a human judgment."""
    marker = re.compile(
        r"MUTATION_CANDIDATE|MATCHED_CONTROL|hp-[a-f0-9]{32}|"
        r"\b(?:pair_id|matched_pair_id|operator_id|construction_intent|"
        r"private_provenance|private_blinding_seed|mutation_case_id|control_case_id)\b|"
        r"intended-positive|intended-negative",
        re.IGNORECASE,
    )
    if marker.search(json.dumps(submission.model_dump(mode="json"))):
        raise ValueError("construction metadata marker in human submission")


def freeze_submission(
    bundle_path: Path,
    expected_fingerprint: str,
    response_path: Path,
    destination: Path,
    *,
    expected_sha256: str | None = None,
    expected_counts: dict[str, int] | None = None,
    lineage: dict[str, str] | None = None,
) -> str:
    raw_source = response_path.read_bytes()
    source_sha256 = hashlib.sha256(raw_source).hexdigest()
    if expected_sha256 is not None and source_sha256 != expected_sha256:
        raise ValueError("submitted-file SHA-256 mismatch: " + source_sha256)

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate submission field; multiple answers forbidden")
            result[key] = value
        return result

    submission = ReviewerASubmission.model_validate(
        json.loads(raw_source, object_pairs_hook=unique_object)
    )
    counts = dict(Counter(r.decision for r in submission.responses))
    if expected_counts is not None and counts != expected_counts:
        raise ValueError("human decision counts mismatch: " + json.dumps(counts, sort_keys=True))
    bundle = load_bundle(bundle_path, expected_fingerprint)
    validate_submission(bundle, submission)
    audit_submission(submission)
    fingerprint = digest(submission)
    receipt = {
        "schema_version": "independent-reviewer-a-submission-freeze-v1",
        "submission_fingerprint": fingerprint,
        "submission_sha256": source_sha256,
        "bundle_fingerprint": bundle.fingerprint,
        "reviewer_slot": "A",
        "responses": 100,
        "decision_counts": counts,
        "schema_validation": "PASS",
        "evidence_validation": "PASS",
        "leakage_audit": "PASS",
        "invalid_evidence_refs": 0,
        "invalid_line_ranges": 0,
        "missing_cases": 0,
        "extra_cases": 0,
        "duplicate_ids": 0,
        "human_answers_modified": False,
        "review_stream": "INDEPENDENT_REVIEWER_A_ONLY",
        "final_ground_truth": False,
        "adjudicated_truth": False,
        "lineage": lineage or {},
        "identity_verification": "SELF_DECLARED_ONLY",
    }
    receipt["fingerprint"] = digest(receipt)

    def build(stage: Path) -> None:
        stage.chmod(0o700)
        with (stage / "submission-v1.json").open("xb") as output:
            output.write(raw_source)
        write_new(stage / "submission-freeze-v1.json", receipt)

    if response_path.read_bytes() != raw_source:
        raise ValueError("human source submission changed during validation")
    atomic_directory(destination, build)
    return fingerprint
