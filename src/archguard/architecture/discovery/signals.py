import re
from uuid import uuid5

from archguard.architecture.discovery.config import ArchitectureDiscoveryConfig
from archguard.architecture.discovery.enums import (
    ComponentRole as Role,
)
from archguard.architecture.discovery.enums import (
    DiscoveredLayer as Layer,
)
from archguard.architecture.discovery.enums import (
    DiscoveryEvidenceKind as Kind,
)
from archguard.architecture.discovery.enums import (
    DiscoveryStrength as Strength,
)
from archguard.architecture.discovery.models import DiscoveryEvidence
from archguard.architecture.graph.models import GraphNodeId
from archguard.core.identifiers import ProjectId
from archguard.core.locations import SourceLocation
from archguard.core.model.enums import Language
from archguard.core.model.types import JsonObject

ROLE_LAYERS = {
    Role.CONTROLLER: Layer.PRESENTATION,
    Role.SERVICE: Layer.APPLICATION,
    Role.REPOSITORY: Layer.PERSISTENCE,
    Role.DOMAIN_MODEL: Layer.DOMAIN,
    Role.DOMAIN_SERVICE: Layer.DOMAIN,
    Role.ADAPTER: Layer.INFRASTRUCTURE,
    Role.GATEWAY: Layer.INFRASTRUCTURE,
    Role.CLIENT: Layer.INFRASTRUCTURE,
    Role.CONFIGURATION: Layer.INFRASTRUCTURE,
}
NAME_SIGNALS = {
    ("controller",): Role.CONTROLLER,
    ("resource",): Role.CONTROLLER,
    ("handler",): Role.CONTROLLER,
    ("service",): Role.SERVICE,
    ("use", "case"): Role.SERVICE,
    ("repository",): Role.REPOSITORY,
    ("dao",): Role.REPOSITORY,
    ("entity",): Role.DOMAIN_MODEL,
    ("aggregate",): Role.DOMAIN_MODEL,
    ("aggregate", "root"): Role.DOMAIN_MODEL,
    ("domain", "service"): Role.DOMAIN_SERVICE,
    ("adapter",): Role.ADAPTER,
    ("gateway",): Role.GATEWAY,
    ("client",): Role.CLIENT,
    ("config",): Role.CONFIGURATION,
    ("configuration",): Role.CONFIGURATION,
    ("util",): Role.UTILITY,
    ("utils",): Role.UTILITY,
    ("helper",): Role.UTILITY,
}
PATH_SIGNALS = {
    **{
        name: (Role.CONTROLLER, Layer.PRESENTATION)
        for name in ("controller", "controllers", "handlers")
    },
    **{name: (Role.SERVICE, Layer.APPLICATION) for name in ("service", "services", "usecases")},
    **{
        name: (Role.REPOSITORY, Layer.PERSISTENCE) for name in ("repository", "repositories", "dao")
    },
    **{name: (Role.ADAPTER, Layer.INFRASTRUCTURE) for name in ("adapter", "adapters")},
    "domain": (None, Layer.DOMAIN),
    "application": (None, Layer.APPLICATION),
    "persistence": (None, Layer.PERSISTENCE),
    "infrastructure": (None, Layer.INFRASTRUCTURE),
    "infra": (None, Layer.INFRASTRUCTURE),
    "presentation": (None, Layer.PRESENTATION),
    "clients": (Role.CLIENT, Layer.INFRASTRUCTURE),
    "config": (Role.CONFIGURATION, Layer.INFRASTRUCTURE),
    "utils": (Role.UTILITY, None),
}
FRAMEWORK_SIGNALS = {
    Language.JAVA: {
        "RestController": Role.CONTROLLER,
        "Controller": Role.CONTROLLER,
        "Service": Role.SERVICE,
        "Repository": Role.REPOSITORY,
        "Configuration": Role.CONFIGURATION,
        "Entity": Role.DOMAIN_MODEL,
        "AggregateRoot": Role.DOMAIN_MODEL,
        "Component": None,
    },
    Language.TYPESCRIPT: {"Controller": Role.CONTROLLER, "Injectable": None},
    Language.JAVASCRIPT: {"Controller": Role.CONTROLLER, "Injectable": None},
}
IMPORT_SIGNALS = {
    "org.springframework.web.bind.annotation": Role.CONTROLLER,
    "org.springframework.stereotype": None,
    "@nestjs/common": None,
}


def name_role(name: str) -> Role | None:
    tokens = tuple(
        part.casefold()
        for part in re.split(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|[_-]+", name)
    )
    matched = [
        (len(suffix), role)
        for suffix, role in NAME_SIGNALS.items()
        if tokens[-len(suffix) :] == suffix
    ]
    return max(matched)[1] if matched else None


def evidence(
    config: ArchitectureDiscoveryConfig,
    project: ProjectId,
    subject: GraphNodeId,
    kind: Kind,
    observed: str,
    signal: str,
    strength: Strength,
    role: Role | None = None,
    layer: Layer | None = None,
    location: SourceLocation | None = None,
    metadata: JsonObject | None = None,
) -> DiscoveryEvidence:
    return DiscoveryEvidence(
        id=uuid5(
            project,
            f"discovery-evidence-v1:{config.fingerprint}:{subject}:{kind}:{signal}:{observed}",
        ),
        kind=kind,
        subject_id=subject,
        observed_value=observed,
        signal=signal,
        strength=strength,
        role_hint=role,
        layer_hint=layer,
        location=location,
        metadata=metadata if metadata is not None else {},
    )
