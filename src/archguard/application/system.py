from dataclasses import dataclass
from typing import Literal

from archguard import __version__
from archguard.core.findings.model import FINDING_SCHEMA_VERSION
from archguard.iam.model import IAM_SCHEMA_VERSION


@dataclass(frozen=True)
class SystemInformation:
    name: str
    version: str
    status: Literal["foundation"]
    iam_schema_version: Literal["1.0"]
    finding_schema_version: Literal["1.0"]


def get_system_information(app_name: str) -> SystemInformation:
    return SystemInformation(
        name=app_name,
        version=__version__,
        status="foundation",
        iam_schema_version=IAM_SCHEMA_VERSION,
        finding_schema_version=FINDING_SCHEMA_VERSION,
    )
