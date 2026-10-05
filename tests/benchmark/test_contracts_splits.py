from uuid import uuid5

import pytest
from pydantic import ValidationError

from archguard.benchmark.identity import case_id
from archguard.benchmark.models import (
    AnnotationScope,
    AnnotationStatus,
    BenchmarkPrediction,
    Label,
    Locator,
    Origin,
    PredictionState,
    RuleFamily,
    Split,
    Subjects,
    relative_path,
)
from archguard.benchmark.resolver import LocatorResolver, ResolutionStatus
from archguard.benchmark.splits import plan_splits, validate_leakage
from archguard.core.model.enums import NodeKind


@pytest.mark.parametrize(
    "path", ["", "/abs", "../escape", "src/../file", "a//b", "a\\b", "C:foo", "./x"]
)
def test_bad_paths(path):
    with pytest.raises(ValueError):
        relative_path(path)


def test_family_split_reproducible(loaded):
    families = tuple(r.repository_family_id for r in loaded.dataset.repositories)
    first = plan_splits(families, loaded.dataset.split_seed)
    assert first == plan_splits(tuple(reversed(families)), loaded.dataset.split_seed)
    assert set(first.values()) == set(Split)
    assert all(
        first[r.repository_family_id] == r.dataset_split for r in loaded.dataset.repositories
    )
    with pytest.raises(ValueError):
        plan_splits(("single",), "seed")


@pytest.mark.parametrize(
    "problem", ["duplicate_id", "family", "content", "lineage_family", "ancestor", "cycle"]
)
def test_split_leakage(loaded, problem):
    repos = list(loaded.dataset.repositories)
    if problem == "duplicate_id":
        repos.append(repos[0])
    elif problem == "content":
        other = next(i for i, r in enumerate(repos) if r.dataset_split != repos[0].dataset_split)
        repos[other] = repos[other].model_copy(
            update={"source_fingerprint": repos[0].source_fingerprint}
        )
    else:
        idx = next(i for i, r in enumerate(repos) if r.base_repository_id)
        r = repos[idx]
        updates = {
            "family": {"dataset_split": next(s for s in Split if s != r.dataset_split)},
            "lineage_family": {"repository_family_id": "alien"},
            "ancestor": {"base_repository_id": "missing"},
            "cycle": {"base_repository_id": r.repository_id},
        }[problem]
        repos[idx] = r.model_copy(update=updates)
    with pytest.raises(ValueError):
        validate_leakage(loaded.dataset.model_copy(update={"repositories": tuple(repos)}))


def test_locators_identity_and_resolution(loaded, validated):
    truth = loaded.truths[0]
    resolver = LocatorResolver(validated[1][truth.repository_id])
    for loc in truth.subjects.locators:
        status, ids = resolver.resolve(loc)
        assert status == ResolutionStatus.RESOLVED
        assert resolver.locator(resolver.nodes[ids[0]]) == loc
        assert (
            resolver.resolve(loc.model_copy(update={"signature": "wrong-signature"}))[0]
            == ResolutionStatus.MISSING
        )
    assert (
        case_id(
            loaded.dataset.namespace,
            truth.repository_id,
            truth.rule_id,
            truth.label,
            truth.subjects,
        )
        == truth.case_id
    )
    assert (
        case_id(
            loaded.dataset.namespace,
            truth.repository_id,
            truth.rule_id,
            Label.UNKNOWN,
            truth.subjects,
        )
        != truth.case_id
    )
    node = resolver.nodes[resolver.subjects(truth.subjects)[0]]
    twin = node.model_copy(update={"id": uuid5(node.id, "twin")})
    ambiguous = LocatorResolver(
        resolver.iam.model_copy(update={"nodes": (*resolver.iam.nodes, twin)})
    )
    assert ambiguous.resolve(truth.subjects.locators[0])[0] == ResolutionStatus.AMBIGUOUS
    assert ambiguous.subjects(truth.subjects) is None
    method = next(n for n in resolver.iam.nodes if n.kind == NodeKind.METHOD)
    assert resolver.normalize(method.id, NodeKind.CLASS).kind == NodeKind.CLASS
    assert resolver.normalize(method.id, NodeKind.FILE).kind == NodeKind.FILE
    project = next(n for n in resolver.iam.nodes if n.kind == NodeKind.PROJECT)
    with pytest.raises(ValueError):
        resolver.normalize(project.id, NodeKind.CLASS)


@pytest.mark.parametrize("bad", ["duplicate", "order", "pair"])
def test_subject_validation(loaded, bad):
    locs = next(t for t in loaded.truths if t.rule_id == "ARCH002").subjects.locators
    with pytest.raises(ValidationError):
        if bad == "duplicate":
            Subjects(locators=(locs[0], locs[0]))
        elif bad == "pair":
            Subjects(locators=(locs[0],), directed=True)
        else:
            Subjects(locators=tuple(sorted(locs, key=lambda x: x.model_dump_json(), reverse=True)))


@pytest.mark.parametrize("bad", ["family", "provenance", "scope", "locator", "prediction"])
def test_contract_invariants(loaded, bad):
    truth = loaded.truths[0]
    with pytest.raises(ValidationError):
        if bad == "family":
            type(truth).model_validate(
                truth.model_copy(update={"rule_family": RuleFamily.SEMANTIC})
            )
        elif bad == "provenance":
            type(truth).model_validate(
                truth.model_copy(
                    update={
                        "annotation_status": AnnotationStatus.MUTATION_DERIVED,
                        "origin": Origin.CURATED,
                    }
                )
            )
        elif bad == "scope":
            AnnotationScope(rules=("ARCH001",), fully_annotated_rules=("ARCH002",))
        elif bad == "locator":
            Locator.model_validate(
                truth.subjects.locators[0].model_copy(update={"path": "/private"})
            )
        else:
            from archguard.benchmark.adapters import prediction
            from archguard.benchmark.models import Mode, Task

            p = prediction(
                loaded.dataset.namespace,
                truth.repository_id,
                truth.rule_id,
                truth.subjects,
                PredictionState.POSITIVE,
                Mode.STATIC_ONLY,
                Task.CONFIRMED_VIOLATION_DETECTION,
            )
            BenchmarkPrediction.model_validate(
                p.model_copy(update={"state": PredictionState.CANDIDATE})
            )


def test_line_changes_do_not_change_locator_identity(loaded, validated):
    truth = loaded.truths[0]
    iam = validated[1][truth.repository_id]
    shifted = tuple(
        n.model_copy(
            update={
                "source_location": n.source_location.model_copy(
                    update={
                        "start_line": n.source_location.start_line + 100,
                        "end_line": n.source_location.end_line + 100
                        if n.source_location.end_line
                        else None,
                    }
                )
            }
        )
        if n.source_location
        else n
        for n in iam.nodes
    )
    resolver = LocatorResolver(iam.model_copy(update={"nodes": shifted}))
    assert resolver.subjects(truth.subjects) == LocatorResolver(iam).subjects(truth.subjects)
    assert (
        case_id(
            loaded.dataset.namespace,
            truth.repository_id,
            truth.rule_id,
            truth.label,
            truth.subjects,
        )
        == truth.case_id
    )
