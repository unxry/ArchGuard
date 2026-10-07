"""Prepare/verify a correction-only handoff; never accept the corrected submission."""

import argparse
import hashlib
import json
import subprocess

from prompt015e1_recover_handoff import COORDINATOR, HANDOFF, original_material
from prompt015e_acceptance import (
    D_CLOSURE,
    EXPECTED,
    PUBLIC,
    SOURCE,
    SOURCE_SHA,
    verify_prerequisites,
)

from archguard.benchmark.oss.models import canonical
from archguard.infrastructure.oss_benchmark import write_new
from archguard.infrastructure.semantic_adjudication import verify_adjudicator_handoff
from archguard.infrastructure.semantic_adjudication_correction import (
    correction_material,
    load_original_candidate,
    prepare_correction_round,
    verify_correction_round,
)

ROUND = SOURCE.parent / "corrections-v1/round-1"
AUDIT = PUBLIC / "adjudicator-correction-verification-v1.json"


def main():
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--prepare", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    # The approved raw SHA is checked before human JSON decoding or diagnostics.
    raw, data = load_original_candidate(SOURCE, SOURCE_SHA)
    if subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip() != D_CLOSURE:
        raise ValueError("unexpected HEAD for blocked correction handoff")
    if (SOURCE.parent / "frozen-v1").exists() or (
        PUBLIC / "adjudicator-acceptance-verification-v1.json"
    ).exists():
        raise ValueError("adjudicator must remain unaccepted")
    bundle, _ = verify_prerequisites()
    mapping, original, receipt = original_material()
    verify_adjudicator_handoff(HANDOFF, COORDINATOR, mapping, original, receipt)
    material_args = {
        "package_fingerprint": EXPECTED["package"],
        "guidance_bytes": original["rule-guidance-v1.json"],
        "schema_bytes": original["submission-schema.json"],
    }
    contents, _, expected_public = correction_material(raw, data, bundle, **material_args)
    counts = expected_public["counts"]
    if counts != {
        "expected_ids": 4,
        "submitted_ids": 4,
        "unique_submitted_ids": 4,
        "missing": 1,
        "extra": 1,
        "duplicate_ids": 0,
        "invalid_evidence_ids": 1,
        "invalid_line_ranges": 0,
    }:
        raise ValueError("observed structural defect differs from approved blocked state")
    if args.prepare:
        if AUDIT.exists() or AUDIT.is_symlink():
            raise ValueError("correction audit is append-only; cannot overwrite")
        public = prepare_correction_round(
            SOURCE, ROUND, bundle, expected_sha=SOURCE_SHA, **material_args
        )
        if public != expected_public:
            raise ValueError("prepared source-free audit changed")
        write_new(AUDIT, public)
    else:
        verify_correction_round(ROUND, contents)
        if AUDIT.is_symlink() or AUDIT.read_bytes() != (canonical(expected_public) + "\n").encode():
            raise ValueError("public correction audit changed")
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA:
        raise ValueError("original human submission changed")
    verify_prerequisites()
    print(json.dumps(expected_public, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError):
        raise SystemExit(
            "PROMPT_015_E_2_BLOCKED: structural correction freeze/privacy guard failed"
        ) from None
