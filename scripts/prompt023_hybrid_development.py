"""Offline development-only fitting; no provider/credential interface."""

import argparse
import json
import os
import sys

from archguard.infrastructure import hybrid_development as stage


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "execute", "verify"))
    args = parser.parse_args()
    os.umask(0o077)
    stage.enable_offline()
    try:
        if args.action == "prepare":
            result = stage.prepare()
        elif args.action == "execute":
            result = stage.execute()
        else:
            result = stage.verify_outputs()
    except Exception as error:
        code = str(error)
        safe = (
            code
            if code.startswith("P023_") and code.replace("_", "").isalnum()
            else ("P023_BLOCKED_FROZEN_INPUT_OR_SOLVER_VERIFICATION_FAILED")
        )
        print(json.dumps(dict(status=safe, error_class=type(error).__name__, provider_calls=0)))
        sys.exit(2)
    print(
        json.dumps(
            dict(
                status=result.get("status", "P023_INPUTS_PREPARED"),
                provider_calls=0,
                paid_execution_approved=False,
                final_full_hybrid_family=result.get("final_full_hybrid_family"),
            )
        )
    )


if __name__ == "__main__":
    main()
