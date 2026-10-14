"""P030 offline prospective foundation. Never executes Security detectors or a provider."""

import argparse
from pathlib import Path

from archguard.benchmark.oss.models import canonical
from archguard.infrastructure import security_benchmark


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("validate", "freeze", "verify"))
    parser.add_argument("--quality", type=Path)
    parser.add_argument("--implementation")
    args = parser.parse_args()
    if args.command == "freeze":
        if args.quality is None or args.implementation is None:
            parser.error("freeze requires --quality and --implementation")
        result = security_benchmark.freeze(args.quality, args.implementation)
    elif args.command == "verify":
        result = security_benchmark.verify()
    else:
        result = security_benchmark.validate()
    print(canonical(result))


if __name__ == "__main__":
    main()
