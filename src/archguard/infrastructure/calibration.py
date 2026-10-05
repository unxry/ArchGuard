"""Bounded file adapters; split files are opened only by their respective stage."""

import json
from pathlib import Path

from pydantic import TypeAdapter

from archguard.architecture.hybrid.calibration import (
    FrozenStructuralHybridPolicyArtifact,
    StructuralCalibrationError,
)
from archguard.architecture.hybrid.serialization import canonical
from archguard.benchmark.cohort import CalibrationTrainingRecord
from archguard.benchmark.models import Split
from archguard.calibration.models import Experiment, PrimaryCohort
from archguard.calibration.workflow import assert_split_allowed, primary_cohort
from archguard.core.model.base import DomainModel
from archguard.infrastructure.hybrid_configuration import _read, _source_free, _unique


def load_experiment(path: Path) -> Experiment:
    return TypeAdapter(Experiment).validate_python(_read(path, 131072))


def load_primary(path: Path, split: Split, experiment: Experiment) -> PrimaryCohort:
    assert_split_allowed(split, experiment)
    if path.name != split.value.lower() + ".jsonl" or path.is_symlink():
        raise StructuralCalibrationError(
            "stage requires its canonical split file, without symlinks"
        )
    records: list[CalibrationTrainingRecord] = []
    total = 0
    with path.open("rb") as stream:
        for line in iter(lambda: stream.readline(65537), b""):
            total += len(line)
            if len(line) > 65536 or total > 8388608 or len(records) >= 20000:
                raise StructuralCalibrationError("cohort exceeds calibration read budget")
            raw = json.loads(line, object_pairs_hook=_unique)
            _source_free(raw)
            records.append(CalibrationTrainingRecord.model_validate(raw))
    return primary_cohort(tuple(records), split, experiment)


def load_policy(path: Path) -> FrozenStructuralHybridPolicyArtifact:
    return FrozenStructuralHybridPolicyArtifact.model_validate(_read(path, 1048576))


def save_new(path: Path, value: DomainModel) -> None:
    with path.open("x", encoding="utf-8") as stream:
        stream.write(canonical(value) + "\n")
