"""Explicit offline P032 DEV-only execution; stops before P033."""

from archguard.benchmark.oss.models import canonical
from archguard.infrastructure.security_dev_evaluation import run

if __name__ == "__main__":
    print(canonical(run()))
