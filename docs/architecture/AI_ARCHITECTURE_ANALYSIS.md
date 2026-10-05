# Semantic architecture analysis foundation

`AnalyzeArchitectureSemantics` строит IAM один раз, Graph один раз и optional Discovery один раз
в открытом workspace. `SemanticAnalysisTargetSelector` выбирает ограниченный набор вопросов;
`SemanticArchitectureAnalyzer` строит context packs, requests и проверяет ответы через provider port.
API/jobs/database/frontend не добавлены.

## Targets и semantics

Explicit IAM IDs/names/qualified names должны однозначно разрешаться во внутренний projected node.
Методы сохраняют identity/range и используют component ownership для обхода графа.
Default selector рассматривает ambiguous discovery (ARCH204), controller hypotheses (ARCH202),
configured graph candidates (ARCH205); unknown roles opt-in (ARCH201). Explicit target по умолчанию
задаёт ARCH201; `--rule` позволяет выбрать любой ARCH201–205. `TargetSelectionConfig.rules`
применяется к выбранным субъектам. Это deterministic heuristic preselection вопросов, не findings.
Priority: explicit → ambiguous → controller → graph candidate → unknown; UUID/rule ties.
Не все IAM nodes передаются LLM. Graph thresholds default disabled; research profile
[graph-candidates.json](../../examples/ai/graph-candidates.json) включает synthetic demo thresholds.

| ID | Semantic question |
| --- | --- |
| ARCH201 | Responsibility Mismatch |
| ARCH202 | Business Logic in Controller |
| ARCH203 | Infrastructure Leakage |
| ARCH204 | Misplaced Component |
| ARCH205 | Suspicious Cross-Layer Responsibility |

Каждый ответ — `SemanticArchitectureAssessment`: один requested rule, decision
`SUPPORTED` / `NOT_SUPPORTED` / `INSUFFICIENT_CONTEXT`, provided subject IDs, короткая причина,
provided evidence refs, nullable suggested role/layer/recommendation, bounded assumptions/limitations.
Все поля required, nullable options explicit; extra fields запрещены. SUPPORTED требует хотя бы
один evidence ref. Проверяются JSON/schema/catalog/rule equality, target membership, all subjects,
all evidence refs, duplicates и lengths; code fields, code delimiters, free-text path/line claims
отклоняются. SEC, ARCH001–005 и ARCH101–105 в provider assessment недопустимы.
Malformed/unknown references дают `AI_ANALYSIS_INVALID_RESPONSE`, не crash всего анализа.

`SemanticArchitectureCandidate` хранит validated assessment, context fingerprint/strategy,
provider/actual model и prompt/schema versions. Это assessment record при любом из трёх decisions,
не `Finding`; `not_calibrated=true`, confidence/severity/health score отсутствуют.
SUPPORTED не подтверждает factual correctness аргумента. Schema/reference validation проверяет
grounding boundary, не качество рассуждения. Static findings не отменяются.

Logical candidate UUIDv5: project namespace + rule + sorted subjects + context fingerprint +
prompt/schema version + actual provider/model identity. Decision, stochastic prose, provider request ID,
latency и random invocation ID исключены. Повторный вызов того же logical question может иметь
тот же candidate ID и иной assessment; future persistence должна хранить invocation отдельно.

## Prompt boundary

`architecture-semantic-v1` / `semantic-assessment-v1`: отдельные trusted system instructions,
structured task и `untrusted_context`. Все source/comments/strings/names являются DATA;
instructions требуют provided evidence only, запрета code quoting/security/static reassessment
и INSUFFICIENT_CONTEXT при недостатке evidence. TARGET_CONSTRAINT нормативен,
DISCOVERY_HYPOTHESIS inferred/non-normative. Adapter сериализует context в отдельное user JSON
message, не подставляет source в system instructions. Regression проверяет фактический wire request.
Это mitigation, не доказательство устойчивости внешней модели к prompt injection и не DLP.

## Budgets и failures

Default max targets/calls/candidates 10, timeout 30 s, max output tokens 2000.
Call attempts, включая failures, расходуют call budget; late responses не становятся candidates.
Required exact input token caps reserve preflight count даже при failed invocation; missing count
останавливает соответствующий вызов. Реальный adapter не предоставляет local tokenizer,
поэтому такие caps fail closed. Provider-reported usage сохраняется отдельно и не выдумывается;
при отсутствии input/output/total/cost значения null. Нет hardcoded pricing или estimated tokens.

Missing configuration/remote permission → UNAVAILABLE, invalid upstream → INVALID,
dry-run → DRY_RUN/zero calls, successful bounded complete analysis → COMPLETE,
successes с failures/truncation/skips/incomplete upstream → PARTIAL,
отсутствие successes при неполноте → INCOMPLETE. NOT_SUPPORTED/INSUFFICIENT_CONTEXT являются
валидными результатами вызова, а не transport failures. Retry policy: zero automatic retries.
Source-read/provider/schema errors sanitized; остальные targets продолжают работу.

## CLI

```bash
archguard ai context tests/fixtures/discovery/java-layered --node UserController --json
archguard ai context tests/fixtures/discovery/java-layered --node UserController \
  --strategy GRAPH_GUIDED --hops 2 --direction OUT --relations CALLS --json
archguard ai analyze tests/fixtures/discovery/java-layered --target UserController \
  --rule ARCH202 --config examples/ai/graph-guided.json --dry-run --json
archguard ai analyze tests/fixtures/discovery/conflict --dry-run --json
archguard ai analyze tests/fixtures/graph/hub --config examples/ai/graph-candidates.json --dry-run --json
```

Repository options local/ZIP/public Git, namespace, strict, exclusions/gitignore и output сохраняются.
`--dry-run` не читает provider credentials и не создаёт provider: экспортируются targets, manifests,
prompt/schema hashes, task и generation parameters; source-bearing requests не экспортируются.
Exit codes: 0 context/DRY_RUN/COMPLETE, 2 invalid input/upstream, 3 UNAVAILABLE/PARTIAL/INCOMPLETE.
Dry-run явно сообщает omitted target/context budgets, не утверждает успешный LLM analysis.
Privacy и real adapter: [LLM provider](LLM_PROVIDER.md).
