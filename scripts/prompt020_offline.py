"""P020 has no provider/connectivity/training/evaluation command."""

import argparse
import json
import os
import sys
from pathlib import Path

from archguard.infrastructure import unified_hybrid as experiment
from archguard.infrastructure.component_holdout import offline


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stage", choices=("plan", "holdout", "development", "workers", "finish", "verify")
    )
    parser.add_argument("--worker", choices=("evidence", "requests", "verify"))
    parser.add_argument("--stream", choices=("DEVELOPMENT", "FINAL"))
    args = parser.parse_args()
    os.umask(0o077)
    sys.addaudithook(offline)
    if args.worker:
        if not args.stream or args.stage:
            parser.error("worker requires stream only")
        workers = {
            "evidence": experiment.evidence_worker,
            "requests": experiment.requests_worker,
            "verify": experiment.verify_worker,
        }
        result = workers[args.worker](args.stream)
    else:
        if not args.stage or args.stream:
            parser.error("stage required")
        actions = {
            "plan": experiment.prepare_plan,
            "holdout": experiment.construct_final,
            "development": experiment.prepare_development,
            "finish": experiment.finish,
            "verify": experiment.verify,
        }
        result = (
            experiment.run_workers(Path(__file__))
            if args.stage == "workers"
            else actions[args.stage]()
        )
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k
                in {
                    "status",
                    "fingerprint",
                    "cases",
                    "requests",
                    "all_freezes_verified",
                    "provider_calls",
                    "connectivity_calls",
                }
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
