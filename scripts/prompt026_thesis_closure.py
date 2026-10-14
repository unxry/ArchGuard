"""Offline closure only; no provider or credential configuration."""

import argparse
import json
from pathlib import Path

from archguard.infrastructure.thesis_closure import accept, generate, verify


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("generate", "verify", "accept"))
    parser.add_argument("--quality", type=Path)
    args = parser.parse_args()
    if args.action == "accept":
        if args.quality is None:
            parser.error("accept requires the offline quality receipt")
        result = accept(json.loads(args.quality.read_text()))
    else:
        result = generate() if args.action == "generate" else verify()
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
