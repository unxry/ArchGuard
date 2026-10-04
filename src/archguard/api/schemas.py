from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    status: Literal["ok"] = "ok"


class SystemInfoResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str
    version: str
    status: Literal["foundation"]
    iam_schema_version: Literal["1.0"]
    finding_schema_version: Literal["1.0"]
