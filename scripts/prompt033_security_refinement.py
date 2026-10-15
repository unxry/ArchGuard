"""Explicit offline P033 execution or read-only verification; never starts P034."""

import argparse
import json
import os
import sys

from archguard.infrastructure import security_refinement as stage

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("action", choices=("run", "verify"))
parser.add_argument("--reason", default="Generic bounded DEV refinement")
args = parser.parse_args()
os.umask(0o077)
sys.addaudithook(stage.access_guard)
print(json.dumps(stage.verify_selected() if args.action == "verify" else stage.run(args.reason)))
