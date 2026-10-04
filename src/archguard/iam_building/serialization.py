import json

from archguard.iam.model import ArchitectureModel
from archguard.iam_building.validation import validate_built_iam


def serialize_iam(model: ArchitectureModel) -> str:
    validate_built_iam(model)
    return (
        json.dumps(model.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, indent=2)
        + "\n"
    )
