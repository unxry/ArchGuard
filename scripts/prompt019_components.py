"""P019 CLI: freeze plan, construct, blind components/evidence, then join; offline only."""

import argparse
import sys
from pathlib import Path

from archguard.infrastructure import component_holdout as p019


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    for name in (
        "plan",
        "construct",
        "components",
        "evidence",
        "evaluate",
        "registry",
        "verify",
        "semantic-worker",
    ):
        group.add_argument("--" + name, action="store_true")
    group.add_argument("--worker", choices=p019.COMPONENTS)
    args = parser.parse_args()
    sys.addaudithook(p019.offline)
    if args.worker:
        result = p019.worker(args.worker)
        print(args.worker + " output frozen: " + result["fingerprint"])
    elif args.semantic_worker:
        result = p019.semantic_evidence()
        print("100 semantic evidence records frozen: " + result["fingerprint"])
    else:
        commands = {
            "plan": p019.prepare_plan,
            "construct": p019.construct,
            "components": lambda: p019.run_components(Path(__file__).resolve()),
            "evidence": lambda: p019.run_evidence(Path(__file__).resolve()),
            "evaluate": p019.evaluate,
            "registry": p019.registry,
            "verify": p019.verify_results,
        }
        selected = next(name for name in commands if getattr(args, name))
        result = commands[selected]()
        print(selected + ": " + str(result.get("fingerprint", result)))


if __name__ == "__main__":
    main()
