"""Explicit P031.A.3 human truth closure; emits aggregates only; never executes P032."""

from archguard.benchmark.oss.models import canonical
from archguard.infrastructure.security_human_truth import run

if __name__ == "__main__":
    print(canonical(run()))
