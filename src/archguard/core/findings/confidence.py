from enum import StrEnum
from typing import Annotated, Self

from pydantic import Field, model_validator

from archguard.core.model.base import DomainModel
from archguard.core.model.types import NonEmptyString


class CalibrationStatus(StrEnum):
    NOT_CALIBRATED = "not_calibrated"
    CALIBRATED = "calibrated"


class Confidence(DomainModel):
    """An uncalibrated score is not a probability; absent confidence is Finding.confidence=None."""

    score: Annotated[float, Field(strict=True, ge=0, le=1)]
    status: CalibrationStatus = CalibrationStatus.NOT_CALIBRATED
    calibration_reference: NonEmptyString | None = None

    @model_validator(mode="after")
    def validate_calibration(self) -> Self:
        if (self.status == CalibrationStatus.CALIBRATED) != (
            self.calibration_reference is not None
        ):
            raise ValueError("calibration_reference is required exactly for calibrated confidence")
        return self
