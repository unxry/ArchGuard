"""Offline P029 historical audit and engineering artifact freeze/verify. No credentials/provider."""

import argparse
import json
from pathlib import Path

from archguard.infrastructure.security_analysis_v2 import freeze, historical_audit, verify


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("audit", "freeze", "verify"))
    parser.add_argument("--quality", type=Path)
    parser.add_argument("--implementation-commit")
    args = parser.parse_args()
    if args.action == "freeze":
        if args.quality is None or args.implementation_commit is None:
            parser.error("freeze requires quality and implementation commit")
        result = freeze(args.quality, args.implementation_commit)
    elif args.action == "audit":
        result = historical_audit()
    else:
        result = verify()
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
