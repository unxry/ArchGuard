from archguard.core.model.base import DomainModel
from archguard.core.model.types import NonEmptyString
from archguard.repository.policy import PositiveInt


class ExtractionConfig(DomainModel):
    repository_namespace: NonEmptyString = "archguard:default-project"
    project_name: NonEmptyString = "ArchGuard project"
    skip_invalid_files: bool = True
    max_declarations_per_file: PositiveInt = 10_000
    max_references_per_file: PositiveInt = 50_000
    max_imports_per_file: PositiveInt = 10_000
    max_provenance_per_edge: PositiveInt = 1_000
