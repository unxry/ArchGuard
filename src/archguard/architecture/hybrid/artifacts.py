from typing import Literal, Self

from pydantic import Field, model_validator

from archguard.architecture.hybrid.features import VERSION, feature_schema
from archguard.architecture.hybrid.models import CalibrationStatus, Digest, HybridPolicyMetadata
from archguard.architecture.hybrid.policies import HybridPolicyError
from archguard.architecture.hybrid.serialization import fingerprint
from archguard.core.model.base import DomainModel


class PolicyCoefficient(DomainModel):
    feature_name: str
    coefficient: float


class CalibratedPolicyArtifact(DomainModel):
    """Future interchange contract only. No fitting, scoring or production artifact exists."""

    artifact_schema_version: Literal["hybrid-policy-artifact-v1"] = "hybrid-policy-artifact-v1"
    method: Literal["WEIGHTED_SCORING", "LOGISTIC_REGRESSION"]
    metadata: HybridPolicyMetadata
    dataset_reference: str = Field(min_length=1)
    calibration_run_reference: str = Field(min_length=1)
    repository_split_fingerprint: Digest
    training_feature_schema_fingerprint: Digest
    intercept: float
    coefficients: tuple[PolicyCoefficient, ...] = Field(min_length=1)
    decision_threshold: float

    @model_validator(mode="after")
    def calibrated_metadata(self) -> Self:
        if self.metadata.calibration_status != CalibrationStatus.CALIBRATED:
            raise ValueError("model artifacts require recorded calibration")
        names = tuple(c.feature_name for c in self.coefficients)
        if len(set(names)) != len(names):
            raise ValueError("artifact coefficient names must be unique")
        return self

    def require_compatible_schema(self) -> None:
        if (
            self.metadata.feature_schema_version != VERSION
            or self.training_feature_schema_fingerprint != fingerprint(feature_schema())
        ):
            raise HybridPolicyError("policy artifact requires a compatible feature schema")
