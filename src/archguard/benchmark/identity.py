from hashlib import sha256
from uuid import UUID, uuid5

from archguard.architecture.hybrid.serialization import canonical
from archguard.benchmark.models import Label, Subjects


def digest(value: object) -> str:
    return sha256(canonical(value).encode()).hexdigest()


def case_id(namespace: UUID, repository: str, rule: str, label: Label, subjects: Subjects) -> UUID:
    return uuid5(
        namespace, canonical((repository, rule, label.value, subjects.model_dump(mode="json")))
    )


def subject_key(subjects: Subjects) -> str:
    return canonical(subjects)


def resolved_key(subjects: Subjects, ids: tuple[UUID, ...]) -> str:
    values = tuple(str(i) for i in ids)
    return canonical((subjects.directed, values if subjects.directed else tuple(sorted(values))))
