import json
from uuid import NAMESPACE_URL, UUID, uuid5

from archguard.core.identifiers import ProjectId
from archguard.core.model.enums import Language, NodeKind


def canonical_identity(*parts: str) -> str:
    return json.dumps(parts, ensure_ascii=False, separators=(",", ":"))


def declaration_key(
    path: str, language: Language, kind: NodeKind, qualified_name: str, signature: str | None
) -> str:
    return canonical_identity(
        "declaration-v1", path, language.value, kind.value, qualified_name, signature or ""
    )


def project_id(namespace: str) -> ProjectId:
    return ProjectId(uuid5(NAMESPACE_URL, canonical_identity("archguard-project-v1", namespace)))


def entity_id(project: ProjectId, category: str, identity: str) -> UUID:
    return uuid5(project, canonical_identity(category, identity))
