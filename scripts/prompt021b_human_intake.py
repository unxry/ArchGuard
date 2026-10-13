"""Explicit P021.B.1 stage/accept/freeze commands. No provider or model capability."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from archguard.infrastructure import unified_human_intake as intake
from archguard.infrastructure import unified_human_review as review


def run(repository: Path, action: str) -> dict[str, Any]:
    review.verify_lineage(repository, allowed=intake.PUBLIC_FILES)
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", intake.P021_A, "HEAD"],
        cwd=repository,
        capture_output=True,
    ).returncode:
        raise review.ReviewBlocked("P021_B_BLOCKED_LINEAGE")
    with intake.intake_capability(repository):
        authority = review.load_authority(repository)
        if action == "stage":
            intake.audit(repository, "P021_B_START", review.digest(dict(p021_a=intake.P021_A)))
            staging = intake.stage_returns(authority)
            return dict(
                status="AUTHORITATIVE_HANDOFF_RECONCILED",
                parsed_before_staging=False,
                ds_store_removed=staging["ds_store_removed"],
                provider_calls=0,
                staged={
                    r: dict(
                        raw_sha256=s["raw_sha256"],
                        byte_size=s["byte_size"],
                        receipt_fingerprint=s["fingerprint"],
                    )
                    for r, s in staging["roles"].items()
                },
            )
        result = intake.execute(authority, verify_only=action == "verify")
        path = repository / review.BASE / "p021-b-human-agreement-v1.json"
        if action == "run":
            intake.freeze_exact(path, result)
        elif review.read_seal(path) != result | {"fingerprint": review.digest(result)}:
            raise review.ReviewBlocked("P021_B_PUBLIC_AGGREGATE_DRIFT")
        return dict(
            status=result["status"],
            branch=result["branch"],
            final_status=result["final_status"],
            agreements=result["agreement"]["primary"]["exact_agreement"],
            conflicts=result["agreement"]["primary"]["disagreement"],
            provider_calls=0,
            fingerprint=review.digest(result),
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("stage", "run", "verify"))
    args = parser.parse_args()
    os.umask(0o077)
    sys.addaudithook(review.offline_guard)
    try:
        result = run(Path.cwd(), args.action)
    except review.ReviewBlocked as error:
        print(json.dumps(dict(status=str(error), provider_calls=0)))
        raise SystemExit(1) from None
    except (ValueError, OSError, KeyError):
        print(json.dumps(dict(status="P021_B_BLOCKED_FORM_OR_FREEZE_DRIFT", provider_calls=0)))
        raise SystemExit(1) from None
    print(json.dumps(result))


if __name__ == "__main__":
    main()
