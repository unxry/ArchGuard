# Static Conformance Foundation

Stage: PROMPT 005. `StaticConformanceAnalyzer.analyze(ArchitectureModel, ArchitectureSpecification)`
валидирует inputs, классифицирует actual nodes, выполняет enabled rules через injected registry,
агрегирует и сортирует findings, вычисляет statistics. `CheckArchitecture` связывает существующий
streaming BuildIAM с analyzer. CLI — composition root; filesystem YAML adapter — infrastructure.
IAM/extraction и health API contracts сохранены. Analysis in-memory, без SQL persistence.

## Actual dependency scope

Анализируются только explicit internal IAM edges IMPORTS/INHERITS/IMPLEMENTS/CALLS/CREATES/USES с
file-linked endpoints и валидным provenance. Каждая запись должна содержать RESOLVED, известный
internal resolution method, соответствующий relation reference_kind и SourceLocation source file.
`occurrences == len(provenance) + provenance_truncated`, counts integer, truncation nonnegative.
External, structural/future relations и non-file endpoints excluded; uncertain/missing proof даёт
UNPROVEN_DEPENDENCY diagnostic и incomplete result. Truncated proof сохраняет подтверждённый finding,
но выставляет incomplete и PROVENANCE_TRUNCATED. Unresolved/ambiguous references, не имеющие actual
IAM edges, не становятся dependencies. Analyzer не повторяет resolution и не угадывает receiver types.

Registry имеет отдельные evaluators для ARCH001/002/004/005, protocol и duplicate/missing checks.
Нет глобального mutable registry. Enabled rules pre-indexed по relation; dependency evaluation
O(E × relevant rules), без rule × node × edge scan. Classification вычисляет matches один раз на file,
после чего nodes наследуют их. Sorting и fingerprint дополнительно требуют canonical ordering.

## Finding identity, evidence и trace

Canonical component granularity — physical source file и target file. IMPORTS file→file и
declaration→declaration CALLS/USES/etc для той же file pair дают один logical finding на rule.
Отдельные source/target file pairs и разные rule IDs не дедуплицируются между собой.

FindingId = UUIDv5(ProjectId, versioned canonical identity: rule ID + source/target SourceFileId +
normalized rule scope/constraint). Severity, description, enabled flag и relation filter не входят
в identity; изменение запрещённой границы меняет ID. Lines, callsite count, snapshot fingerprint,
absolute root и timestamps не участвуют. Поэтому добавление callsites или edge kinds сохраняет ID,
но изменяет evidence/locations/artifact. Caller должен задавать стабильный уникальный project namespace.

Используется существующий Finding v1: namespace ARCH, detector STATIC, severity из YAML,
confidence=null (никакого invented score), deterministic description/recommendation templates.
Evidence: один ARCHITECTURE_RULE с normalized expected constraint, spec hash и scope assignments;
затем STATIC_RULE evidence для каждого actual edge с ID, relation, actual endpoint IDs/names,
file IDs, all available provenance locations, occurrence count/truncation и resolution method.
Properties whitelist не копирует arbitrary IAM attributes, raw source или credential-like values.

PrimaryLocation — первая distinct provenance location в canonical POSIX file/line/byte-column order,
остальные distinct sites — relatedLocations. Совпадающие sites разных relation kinds не дублируются
в locations, но сохранены в отдельных evidence. Координаты наследуют IAM: one-based inclusive,
UTF-8 byte columns. Trace — два **actual** node IDs и actual edge ID/kind первого canonical edge,
а не invented transitive path. Trace metadata и finding metadata перечисляют все supporting edges.
Это direct explanation; Graph Engine paths здесь отсутствуют.

Findings sorted by rule ID, source file path, target file path, FindingId; evidence edges ordered by
first location, relation kind, EdgeId. Statistics включают IAM totals, classified/unclassified/ambiguous
counts, considered/ignored edges, enabled/evaluated rules, findings totals/by rule/by severity и scope
counts. Invalid configuration/IAM suppresses all findings; disabled rules не evaluated.

## Result semantics и CLI

| Status | Meaning | CLI exit |
| --- | --- | --- |
| CONFORMANT | Valid, complete supplied IAM; no implemented explicit static violations | 0 |
| NON_CONFORMANT | Valid target classification; at least one proven violation | 1 |
| INVALID | Invalid IAM, ambiguous classification or missing enabled evaluator; no code findings | 2 |
| INCOMPLETE | Valid, no proven violations, incomplete IAM/provenance | 3 |

Invalid YAML/input возвращает typed CLI error (exit 2), не ARCH finding. `is_complete` независим от
NON_CONFORMANT: найденные доказанные нарушения сохраняются при incomplete input. Strict completeness
policy в foundation единственная; `require_complete_iam=true`. IAM completeness flag описывает
processing coverage, а не semantic recall: unresolved references всё ещё отсутствуют в actual edges.
Unclassified nodes accepted; rules skip отсутствующую нужную dimension. CONFORMANT оценивает только
доступный explicit IAM scope и реализованные constraints, не идеальность архитектуры/security safety.

```bash
.venv/bin/archguard architecture validate examples/architecture/layered-strict.yaml --json
.venv/bin/archguard architecture check tests/fixtures/conformance/clean/java \
  --spec examples/architecture/layered-clean.yaml --json
.venv/bin/archguard architecture check tests/fixtures/conformance/violating/typescript \
  --spec examples/architecture/layered-clean.yaml --output /tmp/result.json
```

Check поддерживает Local/ZIP/public HTTPS Git, --source/--ref/--exclude/--no-gitignore, --strict,
--namespace, --json, --output. Validate не открывает repository. JSON stdout/output — одинаковый
canonical StaticConformanceResult; repository/parser operational logs идут отдельно в stderr и
могут содержать timestamps. Artifact не содержит source, absolute paths, native trees или clocks.
Reproducibility: project/snapshot IDs, snapshot fingerprint, IAM schema/hash, spec version/hash,
analyzer/classifier/engine versions и configuration. IAM fingerprint canonicalizes collection order.

## Validation и limits

Fixtures в `tests/fixtures/conformance`: clean и violating Java/TypeScript, mixed, forbidden domain →
infrastructure, reverse domain → application, orders → payments. Все проходят реальный
intake/parsing/extraction/resolution/IAM pipeline. Tests проверяют multiple callsites/relations,
two rules same edge, inherited/excluded/overlapping/unclassified nodes, unresolved/ambiguous/external
scope, contracts, metadata privacy, schema errors, root/order/line stability, JSON and CLI exit codes.
ArchitectureEvidenceBundle contract принимает deterministic findings/evidence без реализации fusion.

Ограничения: path-based classification вместо annotations/semantic ownership; один экземпляр
каждого builtin ID; нет cross-module exposed API allowlists; conservative extraction без compiler
type inference/transitive dependencies/re-export chains; отдельные constructions/unsupported languages
не входят в IAM; unclassified endpoints не контролируются соответствующей rule dimension.
Source file granularity не различает независимые components внутри одного файла. Classification
overlap инвалидирует весь result даже вне rule source scope. Существующие intake/provenance budgets
также ограничивают coverage. IAM и spec модели frozen, но nested JSON metadata словари shallow-mutable;
analyzer revalidates inputs и не изменяет их.

PROMPT 006 добавляет отдельный [Graph Engine](GRAPH_ENGINE.md) с ARCH003, cycles/SCC и metrics.
Application `CheckArchitecture` строит IAM один раз и объединяет static/graph findings, если enabled
ARCH003 присутствует. Без него сохраняется прежний StaticConformanceResult. Static registry не
импортирует NetworkX и не исполняет graph rules. Invalid aggregate подавляет итоговые findings;
дочерние results сохраняют собственный контекст validity/completeness.
LLM/embeddings, scoring/Hybrid fusion, SEC pipeline, analysis API, persistence и frontend отложены.
