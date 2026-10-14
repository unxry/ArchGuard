"""Deterministic prospective cohort and reviewer evidence, with explicit capability roots."""

import ast
import re
from collections import Counter
from pathlib import Path
from typing import Any

from archguard.benchmark.oss.models import canonical, digest
from archguard.security.rules import canonical_rules
from archguard.security_benchmark.protocol import RULES, ReviewEvidence, ReviewPacket
from archguard.security_benchmark.templates import VERSION, generate


class PredictionInputs:
    """A future worker receives a split-specific source root and a sanitized roster only.

    This is an application allowlist, not an OS sandbox. Use a separate restricted
    identity/container in the later stage; no truth/intent root is accepted here.
    """

    def __init__(self, source_root: Path, roster: tuple[dict[str, Any], ...]) -> None:
        if source_root.is_symlink() or not source_root.is_dir():
            raise ValueError("invalid source capability")
        self.root = source_root.resolve()
        self.roster = roster
        if any(set(r) != {"case_id", "rule_id", "language", "source_paths"} for r in roster):
            raise ValueError("prediction roster contains forbidden metadata")
        ids = [r["case_id"] for r in roster]
        if len(set(ids)) != len(ids) or any(not re.fullmatch(r"sc-[a-f0-9]{24}", s) for s in ids):
            raise ValueError("invalid case identity")
        self.paths = frozenset(f"{r['case_id']}/{p}" for r in roster for p in r["source_paths"])
        for p in self.paths:
            self._allowed(p)

    def _allowed(self, relative: str) -> Path:
        if (
            relative not in self.paths
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
        ):
            raise ValueError("path outside source allowlist")
        path = self.root / relative
        if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_relative_to(self.root):
            raise ValueError("unsafe prediction source path")
        if path.suffix not in {".java", ".ts"} or not path.is_file():
            raise ValueError("not a frozen source file")
        return path

    def read(self, relative: str) -> str:
        return self._allowed(relative).read_text()


def truth_join_gate(predictions_frozen: bool, later_stage: str) -> None:
    if not predictions_frozen or later_stage != "SECURITY_FINAL_POST_PREDICTION_TRUTH_JOIN":
        raise ValueError("explicit later stage and prediction freeze required")


def dependency_audit() -> dict[str, Any]:
    checked = []
    for path in sorted(Path("src/archguard/security_benchmark").glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            names = (
                [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else []
            )
            for name in names:
                if name.startswith("archguard.security.") and name not in {
                    "archguard.security.rules",
                    "archguard.security.domain",
                }:
                    raise ValueError("benchmark detector dependency")
                if name.startswith(
                    (
                        "archguard.infrastructure",
                        "archguard.architecture",
                        "openai",
                        "httpx",
                        "requests",
                    )
                ):
                    raise ValueError("benchmark execution dependency")
            if isinstance(node, ast.Call):
                name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
                if name in {
                    "run_security_analysis",
                    "SecurityAnalyzer",
                    "SecurityAnalyzerV2",
                    "eval",
                    "exec",
                    "__import__",
                    "import_module",
                }:
                    raise ValueError("benchmark forbidden execution")
        checked.append(str(path))
    return dict(status="PASS", modules=checked, detector_dependency=False, detector_filtering=False)


def validate_design(rows: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    if len(rows) != 300:
        raise ValueError("cohort must contain 300 cases")
    for field in (
        "case_id",
        "case_fingerprint",
        "source_bundle_fingerprint",
        "project_id",
        "template_id",
        "template_fingerprint",
    ):
        if len({r[field] for r in rows}) != 300:
            raise ValueError(f"nonunique {field}")
    for split, size, per_rule, per_lang in (("DEV", 100, 10, 5), ("FINAL", 200, 20, 10)):
        selected = [r for r in rows if r["split"] == split]
        if len(selected) != size:
            raise ValueError("split count mismatch")
        for rule in RULES:
            group = [r for r in selected if r["rule_id"] == rule]
            if len(group) != per_rule or Counter(r["language"] for r in group) != {
                "JAVA": per_lang,
                "TYPESCRIPT": per_lang,
            }:
                raise ValueError("rule/language balance mismatch")
            if Counter(r["construction_intent"] for r in group) != {
                "MUTATION_INTENT": per_rule // 2,
                "CONTROL_INTENT": per_rule // 2,
            }:
                raise ValueError("intent balance mismatch")
    return dict(
        total=300,
        DEV=100,
        FINAL=200,
        JAVA=150,
        TYPESCRIPT=150,
        MUTATION_INTENT=150,
        CONTROL_INTENT=150,
        rules=10,
        cases_per_rule=30,
        projects=300,
        templates=300,
    )


def separation(rows: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    dev = [r for r in rows if r["split"] == "DEV"]
    final = [r for r in rows if r["split"] == "FINAL"]
    overlaps = {}
    for field in (
        "project_id",
        "case_fingerprint",
        "source_bundle_fingerprint",
        "template_fingerprint",
    ):
        overlaps[field] = len({r[field] for r in dev} & {r[field] for r in final})
    overlaps["source_file_fingerprint"] = len(
        {h for r in dev for h in r["source_file_fingerprints"].values()}
        & {h for r in final for h in r["source_file_fingerprints"].values()}
    )

    # Remove identifiers and literals before overlap diagnostics: do not mask copying with IDs.
    def normalized(row: dict[str, Any]) -> str:
        text = "\n".join(s["content"] for s in row["source_files"])
        text = re.sub(r"[a-f0-9]{16,}", "ID", text)
        text = re.sub(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|`[^`]*`', "LITERAL", text)
        return re.sub(r"\s+", " ", text).strip()

    overlaps["normalized_source"] = len(
        {digest(normalized(r)) for r in dev} & {digest(normalized(r)) for r in final}
    )
    if any(overlaps.values()):
        raise ValueError("split separation failed")

    def grams(text: str) -> set[tuple[str, ...]]:
        tokens = re.findall(r"[A-Za-z_]+|[^\s]", text)
        return {tuple(tokens[i : i + 5]) for i in range(len(tokens) - 4)}

    similarities: list[float] = []
    for d in dev:
        left = grams(normalized(d))
        similarities.extend(
            len(left & right) / len(left | right)
            for f in final
            if (f["rule_id"], f["language"]) == (d["rule_id"], d["language"])
            and (right := grams(normalized(f)))
        )
    return dict(
        status="PASS",
        overlaps=overlaps,
        near_duplicate_audit=dict(
            method="normalized token 5-gram Jaccard, same rule/language cross-split",
            pairs=len(similarities),
            maximum=max(similarities),
            pairs_ge_0_8=sum(x >= 0.8 for x in similarities),
            detector_independent=True,
        ),
        conceptual_overlap=(
            "Shared SEC contracts and framework API concepts are intentional; 15 "
            "different flow families per language-rule, disjoint DEV (5) and FINAL "
            "(10). High lexical similarity from shared APIs/boilerplate is "
            "reported, not hidden; no statistical independence or natural-project "
            "representativeness claim."
        ),
        reviewer_IDs="opaque SHA256 design identities independent of intent or truth",
    )


def packets(rows: tuple[dict[str, Any], ...]) -> dict[str, dict[str, Any]]:
    definitions = {r.rule_id.value: r.description for r in canonical_rules()}
    result = {}
    for row in rows:
        evidence = ReviewEvidence.model_validate(
            {
                k: row[k]
                for k in (
                    "case_id",
                    "rule_id",
                    "language",
                    "framework_context",
                    "review_scope",
                    "source_files",
                )
            }
            | {"rule_definition": definitions[row["rule_id"]]}
        )
        for slot in ("A", "B"):
            packet = ReviewPacket(
                reviewer_slot=slot,
                evidence=evidence,
                evidence_fingerprint=digest(evidence.model_dump(mode="json")),
                response_destination=f"responses/{slot}/{row['case_id']}.json",
            )
            result[f"packets/{slot}/{row['case_id']}.json"] = packet.model_dump(mode="json")
    return result


def blindness_audit(values: dict[str, dict[str, Any]]) -> dict[str, Any]:
    expected = set(ReviewPacket.model_fields)
    evidence_keys = set(ReviewEvidence.model_fields)
    for raw in values.values():
        packet = ReviewPacket.model_validate(raw)
        if set(raw) != expected or set(raw["evidence"]) != evidence_keys:
            raise ValueError("reviewer metadata leakage")
        context = packet.evidence.framework_context.lower()
        if any(
            s in context
            for s in ("detector", "mutation", "control intent", "contract_only", "unsupported_by")
        ):
            raise ValueError("reviewer support/intent leakage")
        for source in packet.evidence.source_files:
            # No generated comments at all: static fixtures need no answer-hinting prose.
            if re.search(r"(?m)^\s*(//|/\*|\*)", source.content):
                raise ValueError("reviewer comment leakage")
            if re.search(
                (
                    "\\b(?:mutation|control|expected|vulnerable|unsafeHtml|safeHtml|positive"
                    "|negative)\\b"
                ),
                source.content,
                re.I,
            ):
                raise ValueError("reviewer identifier leakage")
    return dict(
        status="PASS",
        packets=len(values),
        construction_intent_visible=False,
        detector_output_visible=False,
        split_visible=False,
        support_expectation_visible=False,
        responses_visible=False,
    )


def material() -> tuple[tuple[dict[str, Any], ...], dict[str, dict[str, Any]], dict[str, Any]]:
    rows = generate()
    counts = validate_design(rows)
    review = packets(rows)
    audit = dict(
        counts=counts,
        separation=separation(rows),
        blindness=blindness_audit(review),
        dependency=dependency_audit(),
    )
    return rows, review, audit


def private_material(
    rows: tuple[dict[str, Any], ...], review: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    result: dict[str, Any] = dict(review)
    result["coordinator/case-inventory.json"] = dict(generator=VERSION, cases=list(rows))
    result["coordinator/construction-intent.json"] = dict(
        intent_is_truth=False,
        synthetic_literals_only=True,
        literal_provenance="deterministically fabricated; no environment or external source read",
        cases=[
            {k: r[k] for k in ("case_id", "construction_intent", "RULE_LANGUAGE_SCOPE_EXPECTATION")}
            for r in rows
        ],
    )
    for split in ("DEV", "FINAL"):
        selected = [r for r in rows if r["split"] == split]
        result[f"coordinator/{split}-cohort.json"] = dict(cases=selected)
        result[f"prediction/{split}/roster.json"] = dict(
            cases=[
                {k: r[k] for k in ("case_id", "rule_id", "language")}
                | {"source_paths": [s["path"] for s in r["source_files"]]}
                for r in selected
            ]
        )
        for r in selected:
            for source in r["source_files"]:
                result[f"prediction/{split}/sources/{r['case_id']}/{source['path']}"] = source[
                    "content"
                ]
    return result


def serialized(value: Any) -> str:
    return value if isinstance(value, str) else canonical(value) + "\n"
