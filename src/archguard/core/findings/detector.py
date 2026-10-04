from archguard.core.findings.enums import DetectorSource
from archguard.core.model.base import DomainModel
from archguard.core.model.types import NonEmptyString


class Detector(DomainModel):
    source: DetectorSource
    name: NonEmptyString
    version: NonEmptyString
