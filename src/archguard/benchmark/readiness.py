from collections import Counter
from typing import Literal

from archguard.benchmark.cohort import CalibrationCohort, CalibrationTrainingRecord
from archguard.benchmark.materialization import AISource, CohortVariant
from archguard.benchmark.models import BenchmarkDataset, GroundTruthCase, Label, RuleFamily, Split
from archguard.benchmark.splits import validate_leakage
from archguard.core.model.base import DomainModel


class ReadinessStatus(DomainModel):
    status: Literal["READY", "NOT_READY"]
    reasons: tuple[str, ...]


class CalibrationReadinessReport(DomainModel):
    schema_version: Literal["calibration-readiness-v1"] = "calibration-readiness-v1"
    dataset_id: str
    dataset_version: str
    dataset_fingerprint: str
    families: int
    repositories: int
    cases: int
    dataset_valid: bool
    structural_hybrid: ReadinessStatus
    full_hybrid: ReadinessStatus
    tasks: dict[str, ReadinessStatus]
    split_composition: dict[str, dict[str, int]]
    task_coverage: dict[str, dict[str, dict[str, int]]]
    rule_coverage: dict[str, dict[str, dict[str, int]]]
    family_coverage: tuple[dict[str, str | int | tuple[str, ...]], ...]
    export_coverage: dict[str, dict[str, int]]
    diagnostics: tuple[str, ...]


def status(reasons: list[str]) -> ReadinessStatus:
    return ReadinessStatus(
        status="NOT_READY" if reasons else "READY",
        reasons=tuple(sorted(set(reasons)))
        or ("COMPOSITION_REQUIREMENTS_MET; NO_STATISTICAL_SUFFICIENCY_CLAIM",),
    )


class CalibrationReadinessValidator:
    def validate(
        self,
        dataset: BenchmarkDataset,
        truths: tuple[GroundTruthCase, ...],
        cohort: CalibrationCohort,
        *,
        dataset_valid: bool = True,
    ) -> CalibrationReadinessReport:
        validate_leakage(dataset)
        repos = {r.repository_id: r for r in dataset.repositories}
        by_truth = {t.case_id: t for t in truths}
        seen = set()
        for record in cohort.records:
            CalibrationTrainingRecord.model_validate(record)
            repo = repos.get(record.repository_id)
            truth = by_truth.get(record.case_id)
            if (
                repo is None
                or truth is None
                or repo.dataset_split != record.split
                or repo.repository_family_id != record.repository_family_id
                or record.dataset_id != dataset.dataset_id
                or record.dataset_version != dataset.dataset_version
                or record.dataset_fingerprint != cohort.dataset_fingerprint
                or truth.repository_id != record.repository_id
                or truth.rule_id != record.rule_id
                or truth.subjects != record.subjects
                or truth.label != record.ground_truth_label
                or truth.annotation_status != record.annotation_status
            ):
                raise ValueError("cohort provenance/truth binding mismatch")
            key = (record.case_id, record.variant)
            if key in seen:
                raise ValueError("duplicate cohort sample")
            seen.add(key)
        splits = {}
        exports = {}
        task_coverage: dict[str, dict[str, dict[str, int]]] = {}
        rules: dict[str, dict[str, dict[str, int]]] = {
            f"ARCH{prefix}0{i}": {} for prefix in ("0", "1", "2") for i in range(1, 6)
        }
        task_reasons: dict[RuleFamily, list[str]] = {family: [] for family in RuleFamily}
        common = list(cohort.diagnostics)
        if not dataset_valid:
            common.append("DATASET_INVALID_OR_PARTIAL")
        if (cohort.dataset_id, cohort.dataset_version) != (
            dataset.dataset_id,
            dataset.dataset_version,
        ):
            raise ValueError("cohort dataset/version mismatch")
        for split in Split:
            split_repos = {
                r.repository_id for r in dataset.repositories if r.dataset_split == split
            }
            annotations = [t for t in truths if t.repository_id in split_repos]
            records = [r for r in cohort.records if r.split == split]
            labels = Counter(t.label.value for t in annotations)
            splits[split.value] = {
                "families": len({repos[r].repository_family_id for r in split_repos}),
                "repositories": len(split_repos),
                "cases": len(annotations),
                "positive": labels[Label.POSITIVE.value],
                "negative": labels[Label.NEGATIVE.value],
                "unknown": labels[Label.UNKNOWN.value],
            }
            exports[split.value] = {
                "records": len(records),
                "positive": sum(r.ground_truth_label == Label.POSITIVE for r in records),
                "negative": sum(r.ground_truth_label == Label.NEGATIVE for r in records),
                "eligible": sum(r.calibration_eligible for r in records),
                "ineligible": sum(not r.calibration_eligible for r in records),
                "ai_real": sum(r.ai_source == AISource.REAL_PROVIDER for r in records),
                "ai_scripted": sum(r.ai_source == AISource.SCRIPTED_TEST for r in records),
                "ai_absent": sum(r.ai_source == AISource.AI_UNAVAILABLE for r in records),
            }
            if not {Label.POSITIVE, Label.NEGATIVE} <= {r.ground_truth_label for r in records}:
                common.append(f"{split}:SINGLE_CLASS_EXPORT")
            task_coverage[split.value] = {}
            for family in RuleFamily:
                selected = [t for t in annotations if t.rule_family == family]
                task_families = {repos[t.repository_id].repository_family_id for t in selected}
                task_coverage[split.value][family.value] = {
                    "families": len(task_families),
                    "positive": sum(t.label == Label.POSITIVE for t in selected),
                    "negative": sum(t.label == Label.NEGATIVE for t in selected),
                }
                minimum = 2 if split == Split.TRAIN else 1
                if len(task_families) < minimum:
                    task_reasons[family].append(f"{split}:INSUFFICIENT_INDEPENDENT_FAMILIES")
                # Eligibility is assessed on the real, complete extraction variant only.
                eligible = [
                    r
                    for r in records
                    if r.rule_family == family
                    and r.calibration_eligible
                    and r.variant == CohortVariant.STRUCTURAL
                ]
                eligible_families = {r.repository_family_id for r in eligible}
                task_coverage[split.value][family.value].update(
                    eligible_families=len(eligible_families),
                    eligible_positive=sum(r.ground_truth_label == Label.POSITIVE for r in eligible),
                    eligible_negative=sum(r.ground_truth_label == Label.NEGATIVE for r in eligible),
                )
                if len(eligible_families) < minimum:
                    task_reasons[family].append(f"{split}:INSUFFICIENT_ELIGIBLE_FAMILIES")
                if not {Label.POSITIVE, Label.NEGATIVE} <= {r.ground_truth_label for r in eligible}:
                    task_reasons[family].append(f"{split}:MISSING_ELIGIBLE_CLASSES")
            for rule in rules:
                selected = [t for t in annotations if t.rule_id == rule]
                rules[rule][split.value] = {
                    "positive": sum(t.label == Label.POSITIVE for t in selected),
                    "negative": sum(t.label == Label.NEGATIVE for t in selected),
                }
        structural_reasons = (
            common
            + task_reasons[RuleFamily.DETERMINISTIC_CONFORMANCE]
            + task_reasons[RuleFamily.STRUCTURAL_GRAPH]
        )
        full_reasons = (
            structural_reasons
            + task_reasons[RuleFamily.SEMANTIC]
            + ["REAL_AI_ASSESSMENT_COHORT_AND_SEMANTIC_REVIEW_REQUIRED"]
        )
        family_rows: list[dict[str, str | int | tuple[str, ...]]] = []
        for family_id in sorted({r.repository_family_id for r in dataset.repositories}):
            members = [r for r in dataset.repositories if r.repository_family_id == family_id]
            cases = [t for t in truths if t.repository_id in {r.repository_id for r in members}]
            family_rows.append(
                {
                    "family": family_id,
                    "origins": tuple(sorted({r.origin.value for r in members})),
                    "tasks": tuple(sorted({t.rule_family.value for t in cases})),
                    "languages": tuple(
                        sorted({language.value for r in members for language in r.languages})
                    ),
                    "split": members[0].dataset_split.value,
                    "repositories": len(members),
                    "cases": len(cases),
                }
            )
        return CalibrationReadinessReport(
            dataset_id=dataset.dataset_id,
            dataset_version=dataset.dataset_version,
            dataset_fingerprint=cohort.dataset_fingerprint,
            families=len(family_rows),
            repositories=len(dataset.repositories),
            cases=len(truths),
            dataset_valid=dataset_valid,
            structural_hybrid=status(structural_reasons),
            full_hybrid=status(full_reasons),
            tasks={f.value: status(common + task_reasons[f]) for f in RuleFamily},
            split_composition=splits,
            task_coverage=task_coverage,
            rule_coverage=rules,
            family_coverage=tuple(family_rows),
            export_coverage=exports,
            diagnostics=tuple(sorted(common)),
        )


def human_readiness(report: CalibrationReadinessReport) -> str:
    lines = [
        f"Dataset {report.dataset_id} {report.dataset_version}: "
        f"{report.repositories} repositories, {report.families} families, {report.cases} cases",
        f"Validity: {'VALID' if report.dataset_valid else 'PARTIAL'}",
    ]
    for split, counts in report.split_composition.items():
        export = report.export_coverage[split]
        lines.append(
            f"{split}: {counts['families']} families; {counts['cases']} cases; "
            f"P/N={counts['positive']}/{counts['negative']}; "
            f"records={export['records']}; eligible={export['eligible']}"
        )
        lines.append(
            "  Tasks: "
            + ", ".join(
                f"{task}: families={values['families']}, "
                f"P/N={values['positive']}/{values['negative']}"
                for task, values in report.task_coverage[split].items()
            )
        )
    for name, ready in [
        ("Structural Hybrid", report.structural_hybrid),
        ("Full Hybrid", report.full_hybrid),
    ]:
        lines.append(f"{name}: {ready.status}; " + ", ".join(ready.reasons))
    return "\n".join(lines)
