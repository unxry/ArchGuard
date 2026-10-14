"""Offline Security foundation/integrity only; never execute a Security detector or provider."""

import argparse
import json
from pathlib import Path

from archguard.infrastructure.security_foundation import freeze, science_freeze, verify


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("audit", "freeze", "verify"))
    parser.add_argument("--quality", type=Path)
    args = parser.parse_args()
    if args.action == "freeze":
        if args.quality is None:
            parser.error("freeze requires offline quality receipt")
        result = freeze(args.quality)
    elif args.action == "audit":
        freeze_result = science_freeze()
        result = dict(
            status="P027_ARCHITECTURE_SCIENCE_UNCHANGED",
            CORE_THESIS_COMPLETE=freeze_result["CORE_THESIS_COMPLETE"],
            provider_calls=0,
        )
    else:
        result = verify()
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
