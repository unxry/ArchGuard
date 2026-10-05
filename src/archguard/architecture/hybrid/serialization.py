import hashlib
import json

from archguard.core.model.base import DomainModel


def canonical(value: object) -> str:
    if isinstance(value, DomainModel):
        value = value.model_dump(mode="json")
    value = json.loads(
        json.dumps(value, allow_nan=False), parse_float=lambda v: round(float(v), 12)
    )
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    )


def fingerprint(value: object) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def serialize_hybrid(value: DomainModel) -> str:
    return canonical(value) + "\n"
