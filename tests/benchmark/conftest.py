from pathlib import Path
from unittest.mock import patch

import pytest

from archguard.infrastructure.benchmark import load_dataset, validate_dataset

ROOT = Path(__file__).parents[2]


@pytest.fixture(scope="module")
def loaded():
    return load_dataset(ROOT / "benchmarks/v1/dataset.json")


@pytest.fixture(scope="module")
def validated(loaded):
    return validate_dataset(loaded)


@pytest.fixture(autouse=True)
def no_remote():
    with patch(
        "archguard.infrastructure.llm_provider._post",
        side_effect=AssertionError("offline benchmark"),
    ):
        yield
