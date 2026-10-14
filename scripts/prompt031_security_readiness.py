"""P031 Outcome A; prints only aggregate readiness, never human labels or case IDs."""

from archguard.benchmark.oss.models import canonical
from archguard.infrastructure.security_review_readiness import prepare

if __name__ == "__main__":
    print(canonical(prepare()))
