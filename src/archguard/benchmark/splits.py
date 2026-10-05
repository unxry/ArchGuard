from hashlib import sha256

from archguard.benchmark.models import BenchmarkDataset, Split


def plan_splits(families: tuple[str, ...], seed: str) -> dict[str, Split]:
    unique = sorted(set(families), key=lambda f: (sha256((seed + ":" + f).encode()).hexdigest(), f))
    if len(unique) < 3:
        raise ValueError("three families required for three partitions")
    # Reserve at least one independent family in each holdout.
    test = max(1, len(unique) // 5)
    validation = max(1, len(unique) // 5)
    return {
        f: Split.TEST if i < test else Split.VALIDATION if i < test + validation else Split.TRAIN
        for i, f in enumerate(unique)
    }


def validate_leakage(dataset: BenchmarkDataset) -> None:
    repositories = {r.repository_id: r for r in dataset.repositories}
    if len(repositories) != len(dataset.repositories):
        raise ValueError("duplicate repository ID")
    families: dict[str, Split] = {}
    hashes: dict[str, Split] = {}
    for repo in dataset.repositories:
        for key, lookup in (
            (repo.repository_family_id, families),
            (repo.source_fingerprint, hashes),
        ):
            if key in lookup and lookup[key] != repo.dataset_split:
                raise ValueError("family/content crosses partitions")
            lookup[key] = repo.dataset_split
        seen = {repo.repository_id}
        current = repo
        while current.base_repository_id is not None:
            if current.base_repository_id not in repositories:
                raise ValueError("missing mutation ancestor")
            current = repositories[current.base_repository_id]
            if current.repository_id in seen:
                raise ValueError("cyclic mutation lineage")
            seen.add(current.repository_id)
            if (
                current.repository_family_id != repo.repository_family_id
                or current.dataset_split != repo.dataset_split
            ):
                raise ValueError("mutation lineage crosses family/partition")
