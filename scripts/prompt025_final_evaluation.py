"""Offline, separately invoked prediction and first-truth-open phases."""

import argparse
import json
import os
from pathlib import Path

from archguard.infrastructure import final_evaluation as final
from archguard.infrastructure import unified_human_review as io


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "predict", "truth", "evaluate", "verify"))
    action = parser.parse_args().action
    os.umask(0o077)
    final.git_gate()
    if action != "prepare":
        metadata = io.read_seal(final.INPUT / "metadata.json")
        if metadata["source_bindings"] != {name: io.sha(Path(name)) for name in final.SOURCES}:
            raise PermissionError("P025_IMPLEMENTATION_DRIFT")
    if action == "prepare":
        result = final.prepare()
    elif action == "predict":
        result = final.predict()
    elif action == "truth":
        result = final.open_truth()
    elif action == "evaluate":
        result = final.evaluate()
    else:
        first = io.read_seal(final.PUBLIC)
        result = final.evaluate()
        if result != first:
            raise ValueError("P025_REPRODUCIBILITY_FAILURE")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
