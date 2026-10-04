import pytest
from pydantic import ValidationError

from archguard.experiments.contracts import ReproducibilityManifest


def test_manifest_serialization_without_fake_results() -> None:
    manifest = ReproducibilityManifest(
        software_version="test-software",
        dataset_version="synthetic-contract-test",
        random_seed=17,
        analysis_config={"synthetic": True, "methods": ["Static"]},
    )
    assert manifest.model is None
    assert manifest.parsers == ()
    assert ReproducibilityManifest.model_validate_json(manifest.model_dump_json()) == manifest


@pytest.mark.parametrize("changes", [{"random_seed": -1}, {"git_commit": "branch-name"}])
def test_manifest_rejects_invalid_config(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ReproducibilityManifest.model_validate(
            {"software_version": "test", "dataset_version": "test"} | changes
        )
