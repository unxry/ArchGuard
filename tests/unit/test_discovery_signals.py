import pytest
from pydantic import ValidationError

from archguard.architecture.discovery.config import ArchitectureDiscoveryConfig
from archguard.architecture.discovery.enums import ComponentRole, DiscoveryEvidenceKind
from archguard.architecture.discovery.modules import common_prefix
from archguard.architecture.discovery.signals import name_role


@pytest.mark.parametrize(
    "name,role",
    [
        ("UserController", ComponentRole.CONTROLLER),
        ("Resource", ComponentRole.CONTROLLER),
        ("http_handler", ComponentRole.CONTROLLER),
        ("OrderService", ComponentRole.SERVICE),
        ("SubmitUseCase", ComponentRole.SERVICE),
        ("OrderRepository", ComponentRole.REPOSITORY),
        ("OrderDao", ComponentRole.REPOSITORY),
        ("OrderDAO", ComponentRole.REPOSITORY),
        ("DomainEntity", ComponentRole.DOMAIN_MODEL),
        ("OrderAggregateRoot", ComponentRole.DOMAIN_MODEL),
        ("PaymentDomainService", ComponentRole.DOMAIN_SERVICE),
        ("StripeAdapter", ComponentRole.ADAPTER),
        ("PaymentGateway", ComponentRole.GATEWAY),
        ("ExternalClient", ComponentRole.CLIENT),
        ("AppConfig", ComponentRole.CONFIGURATION),
        ("AppConfiguration", ComponentRole.CONFIGURATION),
        ("SharedUtil", ComponentRole.UTILITY),
        ("Serviceability", None),
        ("ServiceabilityHelper", ComponentRole.UTILITY),
        ("ControllerFactory", None),
        ("ControllerFactoryHelper", ComponentRole.UTILITY),
        ("Foo", None),
    ],
)
def test_bounded_case_and_style_aware_name_signals(name: str, role: ComponentRole | None) -> None:
    assert name_role(name) == role


@pytest.mark.parametrize(
    "raw",
    [
        {"minimum_role_strength": "AMBIGUOUS"},
        {"minimum_layer_strength": "AMBIGUOUS"},
        {"minimum_module_strength": "AMBIGUOUS"},
        {"min_module_components": 0},
        {"module_root_hints": ["../src"]},
        {"module_root_hints": ["/src"]},
        {"module_root_hints": ["C:\\src"]},
        {"java_common_prefix": "com..example"},
        {"graph": {"projection": {"projection": "file"}}},
        {"graph": {"projection": {"include_external": True}}},
        {"graph": {"projection": {"include_self_edges": True}}},
        {"confidence": 0.93},
    ],
)
def test_discovery_configuration_invariants(raw: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ArchitectureDiscoveryConfig.model_validate(raw)


def test_normalized_profile_identity_and_package_prefix() -> None:
    first = ArchitectureDiscoveryConfig(
        enabled_signal_types=(
            DiscoveryEvidenceKind.NAME_PATTERN,
            DiscoveryEvidenceKind.PATH_PATTERN,
        ),
        module_root_hints=("src", "app"),
    )
    second = ArchitectureDiscoveryConfig(
        enabled_signal_types=(
            DiscoveryEvidenceKind.PATH_PATTERN,
            DiscoveryEvidenceKind.NAME_PATTERN,
            DiscoveryEvidenceKind.PATH_PATTERN,
        ),
        module_root_hints=("app", "src", "src"),
    )
    assert first.fingerprint == second.fingerprint
    assert first.fingerprint != ArchitectureDiscoveryConfig().fingerprint
    assert common_prefix([]) == ()
    assert common_prefix([("com", "example", "orders"), ("com", "example", "payments")]) == (
        "com",
        "example",
    )
