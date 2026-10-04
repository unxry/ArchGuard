from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class DomainModel(BaseModel):
    """Validated snapshots; tuple collections are immutable, JSON maps are shallow-frozen."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_default=True,
        revalidate_instances="always",
        allow_inf_nan=False,
    )

    @field_validator("*")
    @classmethod
    def reject_nil_uuid(cls, value: object) -> object:
        if isinstance(value, UUID) and value.int == 0:
            raise ValueError("identifiers must not be nil UUIDs")
        return value
