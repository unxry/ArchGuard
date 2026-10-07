"""Prospective construction contracts. Intent is private and never semantic truth."""

import hashlib
import hmac
from collections import Counter
from typing import Literal, Self

from pydantic import Field, model_validator

from archguard.benchmark.oss.models import Sealed, digest
from archguard.core.model.base import DomainModel

VERSION = "semantic-positive-holdout-v1"
RULES = tuple(f"ARCH20{i}" for i in range(1, 6))
LANGUAGES = ("JAVA", "TYPESCRIPT")
SCENARIOS = ("pricing", "eligibility", "inventory", "settlement", "allocation")
Language = Literal["JAVA", "TYPESCRIPT"]
TechnicalStatus = Literal["VALID", "PARTIAL", "INVALID"]
Intent = Literal["MUTATION_CANDIDATE", "MATCHED_CONTROL"]


def opaque_id(seed: bytes, purpose: str, identity: object) -> str:
    return hmac.new(seed, (purpose + digest(identity)).encode(), hashlib.sha256).hexdigest()


class Operator(DomainModel):
    operator_id: str
    version: Literal["1.0.0"] = "1.0.0"
    rule_id: str
    preconditions: tuple[str, ...]
    procedure: str
    expected_semantic_effect: str
    structural_invariants: tuple[str, ...]
    rejection_conditions: tuple[str, ...]
    provenance: str = "Original controlled fixture recipes; no OSS source or predictions"


def operators() -> tuple[Operator, ...]:
    definitions = (
        (
            "ARCH201",
            "replace-mapper-delegation",
            "ViewMapper",
            "Replace delegation with a multi-branch domain policy implementation.",
            "A presentation mapper implements domain decisions instead of its mapping role.",
        ),
        (
            "ARCH202",
            "inline-controller-policy",
            "RequestHandler",
            "Inline the domain policy into the HTTP request handler; retain response construction.",
            "Business decisions, not validation or mapping alone, execute in the controller.",
        ),
        (
            "ARCH203",
            "direct-domain-persistence",
            "Policy",
            "Add concrete filesystem persistence directly before the domain decision.",
            "Domain behavior directly uses an infrastructure adapter instead of a boundary port.",
        ),
        (
            "ARCH204",
            "relocate-domain-policy",
            "Policy",
            "Move coherent Policy source to infrastructure; update imports, retain policy body.",
            "Domain decision ownership contradicts its infrastructure location and callers.",
        ),
        (
            "ARCH205",
            "mix-application-concerns",
            "Application",
            "Inline domain decisions and directly persist them in application orchestration.",
            "One component materially owns both business policy and infrastructure side effects.",
        ),
    )
    return tuple(
        Operator(
            operator_id=f"{rule.lower()}-{name}-v1",
            rule_id=rule,
            preconditions=(
                f"Target {target} exists",
                "Complete original layered fixture",
                "HTTP controller and domain policy are source-resolvable",
            ),
            procedure=procedure,
            expected_semantic_effect=effect,
            structural_invariants=(
                "Language/framework/project fixed",
                "HTTP interface unchanged",
                "Business result unchanged",
                "All source parses",
                "Target and internal dependencies present in IAM",
            ),
            rejection_conditions=(
                "Syntax failure",
                "Missing target",
                "Missing source span",
                "Unextractable internal dependency",
                "Runtime failure if run",
            ),
        )
        for rule, name, target, procedure, effect in definitions
    )


def formula(scenario: str, language: str) -> str:
    bodies = {
        "pricing": "if (value >= 1000) { return value - 100; } "
        "if (value >= 500) { return value - 25; } return value;",
        "eligibility": "if (value < 18) { return 0; } if (value >= 65) { return 2; } return 1;",
        "inventory": "if (value >= 100) { return 90; } "
        "if (value >= 10) { return value - 2; } return value;",
        "settlement": "TYPE fee = value / 20; if (value >= 2000) { fee = fee - 20; } "
        "if (fee < 5) { fee = 5; } return value - fee;",
        "allocation": "if (value > 500) { return 300; } "
        "if (value > 100) { return value * 2 / 3; } return value / 2;",
    }
    return bodies[scenario].replace("TYPE", "int" if language == "JAVA" else "let")


def fixture_sources(rule: str, language: Language, scenario: str, mutation: bool) -> dict[str, str]:
    """Versioned material code transformations; no labels, filesystem or model input."""
    if rule not in RULES or scenario not in SCENARIOS:
        raise ValueError("unsupported predefined fixture")
    policy_layer = "infrastructure" if mutation and rule == "ARCH204" else "domain"
    layers = {
        "Policy": policy_layer,
        "Application": "application",
        "ViewMapper": "presentation",
        "RequestHandler": "presentation",
        "HttpRequest": "presentation",
        "HttpResponse": "presentation",
        "FileLedger": "infrastructure",
    }
    policy = formula(scenario, language)
    policy_body = "FileLedger.store(value); " + policy if mutation and rule == "ARCH203" else policy
    app_body = (
        "VALUE decision = decide(value); FileLedger.store(decision); return decision;"
        if mutation and rule == "ARCH205"
        else "return Policy.evaluate(value);"
    )
    mapper_body = policy if mutation and rule == "ARCH201" else "return Application.execute(value);"
    handler_body = (
        "VALUE value = request.amount; VALUE result = decide(value); "
        "return new HttpResponse(200, result);"
        if mutation and rule == "ARCH202"
        else "return new HttpResponse(200, ViewMapper.transform(request.amount));"
    )
    methods = {
        "Policy": ("evaluate", policy_body),
        "Application": ("execute", app_body),
        "ViewMapper": ("transform", mapper_body),
        "RequestHandler": ("handle", handler_body),
    }
    files = {}
    for name, layer in layers.items():
        dependencies = {
            "Policy": ["FileLedger"] if mutation and rule == "ARCH203" else [],
            "Application": ["FileLedger"] if mutation and rule == "ARCH205" else ["Policy"],
            "ViewMapper": [] if mutation and rule == "ARCH201" else ["Application"],
            "RequestHandler": ["HttpRequest", "HttpResponse"]
            + ([] if mutation and rule == "ARCH202" else ["ViewMapper"]),
        }.get(name, [])
        if language == "JAVA":
            imports = "".join(f"import fixture.{layers[d]}.{d};\n" for d in dependencies)
            if name == "HttpRequest":
                body = "public final int amount; public HttpRequest(int value) { amount = value; }"
            elif name == "HttpResponse":
                body = (
                    "public final int status; public final int body; "
                    "public HttpResponse(int code, int value) { status = code; body = value; }"
                )
            elif name == "FileLedger":
                imports = (
                    "import java.nio.file.Files;\nimport java.nio.file.Path;\n"
                    "import java.io.IOException;\n"
                )
                body = (
                    "public static void store(int value) { try { "
                    'Files.writeString(Path.of("ledger.txt"), "" + value); '
                    "} catch (IOException failure) { throw new IllegalStateException(failure); } }"
                )
            else:
                method, statements = methods[name]
                signature = (
                    "HttpResponse handle(HttpRequest request)"
                    if name == "RequestHandler"
                    else f"int {method}(int value)"
                )
                body = (
                    "public static " + signature + " { " + statements.replace("VALUE", "int") + " }"
                )
                if "decide(" in statements:
                    body += " private static int decide(int value) { " + policy + " }"
            files[f"src/{layer}/{name}.java"] = (
                f"package fixture.{layer};\n{imports}public class {name} {{\n{body}\n}}\n"
            )
        else:
            imports = "".join(
                f"import {{ {d} }} from '../{layers[d]}/{d}.ts';\n" for d in dependencies
            )
            if name == "HttpRequest":
                body = "amount: number; constructor(value: number) { this.amount = value; }"
            elif name == "HttpResponse":
                body = (
                    "status: number; body: number; constructor(code: number, value: number) "
                    "{ this.status = code; this.body = value; }"
                )
            elif name == "FileLedger":
                imports = "import { writeFileSync } from 'node:fs';\n"
                body = (
                    "static store(value: number): void { "
                    "writeFileSync('ledger.txt', String(value)); }"
                )
            else:
                method, statements = methods[name]
                signature = (
                    "handle(request: HttpRequest): HttpResponse"
                    if name == "RequestHandler"
                    else f"{method}(value: number): number"
                )
                body = (
                    "static "
                    + signature
                    + " { "
                    + statements.replace("VALUE", "let").replace("decide(", "this.decide(")
                    + " }"
                )
                if "decide(" in statements:
                    body += " private static decide(value: number): number { " + policy + " }"
            files[f"src/{layer}/{name}.ts"] = imports + f"export class {name} {{\n{body}\n}}\n"
    return files


def target_name(rule: str) -> str:
    return dict(
        zip(RULES, ("ViewMapper", "RequestHandler", "Policy", "Policy", "Application"), strict=True)
    )[rule]


class SourceEvidence(DomainModel):
    evidence_id: str
    path: str
    text: str = Field(repr=False)
    sha256: str

    @model_validator(mode="after")
    def integrity(self) -> Self:
        if self.sha256 != hashlib.sha256(self.text.encode()).hexdigest():
            raise ValueError("source evidence hash mismatch")
        if self.path.startswith("/") or ".." in self.path.split("/"):
            raise ValueError("evidence must be case-relative")
        return self


class BlindedPacket(Sealed):
    schema_version: Literal["blinded-semantic-holdout-v1"] = "blinded-semantic-holdout-v1"
    blinded_id: str
    rule_id: str
    language: Language
    project_alias: str
    target_path: str
    target_component: str
    architecture_contract: str
    evidence: tuple[SourceEvidence, ...]

    @model_validator(mode="after")
    def target_present(self) -> Self:
        if self.rule_id not in RULES or self.target_path not in {e.path for e in self.evidence}:
            raise ValueError("unsupported rule or missing target evidence")
        return self


class CaseRecord(DomainModel):
    case_id: str
    blinded_id: str
    rule_id: str
    language: Language
    project_alias: str
    technical_status: TechnicalStatus
    packet_fingerprint: str
    validation_fingerprint: str
    context_diagnostics_fingerprint: str


class HoldoutSample(Sealed):
    schema_version: Literal["semantic-holdout-sample-v1"] = "semantic-holdout-sample-v1"
    dataset_id: Literal["semantic-positive-holdout-v1"] = "semantic-positive-holdout-v1"
    cases: tuple[CaseRecord, ...]

    @model_validator(mode="after")
    def distribution(self) -> Self:
        if len(self.cases) != 100 or len({c.case_id for c in self.cases}) != 100:
            raise ValueError("exactly 100 unique cases required")
        if len({c.blinded_id for c in self.cases}) != 100:
            raise ValueError("blinded IDs must be unique")
        counts = Counter((c.rule_id, c.language) for c in self.cases)
        if counts != {(r, lang): 10 for r in RULES for lang in LANGUAGES}:
            raise ValueError("exact rule/language distribution required")
        if sum(c.technical_status == "VALID" for c in self.cases) < 90:
            raise ValueError("at least 90 technically VALID cases required")
        return self


class PrivatePair(DomainModel):
    pair_id: str
    rule_id: str
    language: Language
    origin_project: str
    operator_id: str
    mutation_case_id: str
    control_case_id: str
    before_hashes: dict[str, str]
    after_hashes: dict[str, str]
    mutation_validation_fingerprint: str
    control_validation_fingerprint: str


def validate_pairs(
    sample: HoldoutSample, pairs: tuple[PrivatePair, ...], p013_ids: set[str]
) -> None:
    cases = {c.case_id: c for c in sample.cases}
    if set(cases) & p013_ids or {c.blinded_id for c in sample.cases} & p013_ids:
        raise ValueError("P013 case reuse forbidden")
    counts = Counter((p.rule_id, p.language) for p in pairs)
    if len(pairs) != 50 or len({p.pair_id for p in pairs}) != 50:
        raise ValueError("exactly 50 unique matched pairs required")
    if counts != {(r, lang): 5 for r in RULES for lang in LANGUAGES}:
        raise ValueError("exact pair balance required")
    covered: list[str] = []
    for pair in pairs:
        members = (pair.mutation_case_id, pair.control_case_id)
        for case_id in members:
            case = cases[case_id]
            if (case.rule_id, case.language) != (pair.rule_id, pair.language):
                raise ValueError("pair rule/language mismatch")
        if pair.before_hashes == pair.after_hashes or len(set(members)) != 2:
            raise ValueError("mutation must materially change source")
        covered.extend(members)
    if len(set(covered)) != 100 or set(covered) != set(cases):
        raise ValueError("each frozen case must belong to exactly one matched pair")
