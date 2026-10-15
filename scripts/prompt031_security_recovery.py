"""Explicitly authorized P031 mechanical recovery; aggregate output only."""

from archguard.benchmark.oss.models import canonical
from archguard.infrastructure.security_review_recovery import run

if __name__ == "__main__":
    print(canonical(run()))
