"""Offline frozen B handoff and independent human submission acceptance."""

import hashlib
import json
from pathlib import Path

from archguard.benchmark.oss.models import digest
from archguard.benchmark.semantic_review import ReviewerBBundle, ReviewerBSubmission
from archguard.infrastructure.oss_benchmark import write_new
from archguard.infrastructure.oss_review import atomic_directory
from archguard.infrastructure.semantic_review import (
    audit_bundle,
    blank_template,
    freeze_submission,
    render_handoff,
)

INSTRUCTIONS_B = """Reviewer B: independent real-human review

Open index.html locally and inspect all 100 frozen cases in the supplied order.
Use only this directory and its frozen source evidence, architecture contracts
and rule guidance. Do not obtain construction metadata or additional case hints.
State evidence limitations honestly in your own rationale.

You must be a real human and a DIFFERENT PERSON from Reviewer A.
Do not access Reviewer A answers, rationales, notes, evidence selections, identity,
counts or assessments. Do not communicate case answers with Reviewer A before
both independent submissions are frozen. Do not use AI, detectors or model
suggestions to decide cases, select evidence or write rationales.

Make a copy of response-template.json. For every blinded ID enter exactly one
decision: POSITIVE, NEGATIVE, UNCERTAIN or OUT_OF_SCOPE. Write your own nonempty
concise rationale and optionally a note. Explicitly enter your own evidence array;
each reference requires evidence_id, start_line and end_line (inclusive source
line numbers). Reference at least one item from that case's frozen source.
No decision, rationale or evidence selection is provided by this package.
Preserve the blinded IDs, reviewer_slot B and bundle fingerprint.

Enter your own real reviewer identity in reviewer_identity. Only after completing
your own review of all 100 cases, enter REAL_HUMAN_INDEPENDENT_REVIEW in attestation.
This self-declares that you are a different person from A and followed these
independence requirements. Identity, authorship and independence are not verified
externally by the software. No identity or attestation has been assigned for you.

Save your completed copy as completed-response.json. Return it privately to the
coordinator, never to Reviewer A. Keep the frozen bundle and original blank form
unchanged. Do not edit submission-schema.json or handoff-freeze.json.
No upload, provider call, automatic review, evidence selection or evaluation runs
when this package is opened.
"""


def load_b_bundle(path: Path, expected_fingerprint: str) -> ReviewerBBundle:
    if path.name != "bundle-v1.json" or path.parent.name != "B":
        raise ValueError("B builder accepts only a frozen B bundle path")
    bundle = ReviewerBBundle.model_validate_json(path.read_bytes())
    if bundle.fingerprint != expected_fingerprint:
        raise ValueError("Reviewer B frozen bundle fingerprint mismatch")
    audit_bundle(bundle)
    return bundle


def _contents(bundle: ReviewerBBundle, raw_bundle: bytes) -> dict[str, bytes]:
    return {
        "bundle-v1.json": raw_bundle,
        "index.html": render_handoff(bundle, instructions=INSTRUCTIONS_B).encode(),
        "README.txt": INSTRUCTIONS_B.encode(),
        "response-template.json": (json.dumps(blank_template(bundle), indent=2) + "\n").encode(),
        "submission-schema.json": (
            json.dumps(ReviewerBSubmission.model_json_schema(), indent=2) + "\n"
        ).encode(),
    }


def prepare_b_handoff(bundle_path: Path, expected_fingerprint: str, destination: Path) -> str:
    bundle = load_b_bundle(bundle_path, expected_fingerprint)
    raw_bundle = bundle_path.read_bytes()
    contents = _contents(bundle, raw_bundle)
    receipt = {
        "schema_version": "reviewer-b-handoff-freeze-v1",
        "bundle_fingerprint": bundle.fingerprint,
        "reviewer_slot": "B",
        "case_count": 100,
        "unique_blinded_ids": 100,
        "prepopulated_decisions": 0,
        "prepopulated_rationales": 0,
        "prepopulated_evidence": 0,
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


def verify_b_handoff(bundle_path: Path, expected_fingerprint: str, destination: Path) -> str:
    bundle = load_b_bundle(bundle_path, expected_fingerprint)
    receipt = json.loads((destination / "handoff-freeze.json").read_bytes())
    if receipt["fingerprint"] != digest({k: v for k, v in receipt.items() if k != "fingerprint"}):
        raise ValueError("Reviewer B handoff receipt fingerprint mismatch")
    if receipt["bundle_fingerprint"] != expected_fingerprint or receipt["reviewer_slot"] != "B":
        raise ValueError("Reviewer B handoff binding mismatch")
    counts = (
        receipt["case_count"],
        receipt["unique_blinded_ids"],
        receipt["prepopulated_decisions"],
        receipt["prepopulated_rationales"],
        receipt["prepopulated_evidence"],
    )
    if counts != (100, 100, 0, 0, 0):
        raise ValueError("Reviewer B handoff completeness/blankness mismatch")
    expected = _contents(bundle, bundle_path.read_bytes())
    if set(receipt["files"]) != set(expected) or {p.name for p in destination.iterdir()} != {
        *expected,
        "handoff-freeze.json",
    }:
        raise ValueError("unexpected Reviewer B handoff files")
    for name, data in expected.items():
        path = destination / name
        if path.is_symlink() or path.read_bytes() != data:
            raise ValueError("Reviewer B handoff differs from frozen B material")
        if hashlib.sha256(data).hexdigest() != receipt["files"][name]:
            raise ValueError("Reviewer B handoff file hash mismatch")
    return str(receipt["fingerprint"])


def verify_b_submission_contract(destination: Path, expected_fingerprint: str) -> str:
    receipt = json.loads((destination / "handoff-freeze.json").read_bytes())
    if receipt["fingerprint"] != digest({k: v for k, v in receipt.items() if k != "fingerprint"}):
        raise ValueError("B handoff receipt fingerprint mismatch")
    if receipt["bundle_fingerprint"] != expected_fingerprint or receipt["reviewer_slot"] != "B":
        raise ValueError("B frozen response contract binding mismatch")
    for name in ("bundle-v1.json", "submission-schema.json"):
        path = destination / name
        if (
            path.is_symlink()
            or hashlib.sha256(path.read_bytes()).hexdigest() != receipt["files"][name]
        ):
            raise ValueError("B frozen response contract changed")
    bundle = ReviewerBBundle.model_validate_json((destination / "bundle-v1.json").read_bytes())
    if bundle.fingerprint != expected_fingerprint:
        raise ValueError("B response contract bundle fingerprint mismatch")
    audit_bundle(bundle)
    if json.loads((destination / "submission-schema.json").read_bytes()) != (
        ReviewerBSubmission.model_json_schema()
    ):
        raise ValueError("B response validator differs from frozen schema")
    return str(receipt["fingerprint"])


def freeze_b_submission(
    bundle_path: Path,
    expected_fingerprint: str,
    response_path: Path,
    destination: Path,
    *,
    expected_sha256: str,
    expected_counts: dict[str, int],
    lineage: dict[str, str],
) -> str:
    if (
        response_path.name != "completed-response.json"
        or response_path.parent.name != "reviewer-b-submissions-v1"
        or response_path.is_symlink()
    ):
        raise ValueError("B acceptance requires its own private completed response path")
    return freeze_submission(
        bundle_path,
        expected_fingerprint,
        response_path,
        destination,
        expected_sha256=expected_sha256,
        expected_counts=expected_counts,
        lineage=lineage,
        reviewer_slot="B",
    )
