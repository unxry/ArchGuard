# Security: audit возможностей и границы интерфейса

Аудит P039 выполнен в изолированном worktree `archguard-signature-v2`. Изучены production-модели, локальные анализаторы, публичная HTTP/CLI-поверхность и отдельные engineering-тесты. Production-файлы не изменены. `.env`, private/human/truth/adjudication-данные, benchmark answer keys и research receipts не читались. Из `security_benchmark/protocol.py` прочитаны только enum и функции преобразования публичного результата в outcome, не наборы данных или метрики. Анализаторы, провайдеры и исследовательские команды не запускались.

Главный вывод: Security — реально реализованная внутренняя Python-подсистема с ограниченными Java/TypeScript-анализаторами и проверяемой структурой доказательств. HTTP endpoint, публичная команда `archguard security`, product-importer JSON, фоновый scan job и подключение репозитория через UI отсутствуют. Дизайн может серьезно работать с результатом анализа, но не должен выдавать существование Python-сервиса за готовую серверную интеграцию.

## Классификация

| Метка | Значение в этом аудите |
|---|---|
| `API_EXPOSED` | Подтвержденный HTTP endpoint в приложении. |
| `CLI_ONLY` | Есть отдельная консольная поверхность; это не HTTP/UI-интеграция. |
| `REAL_INTERNAL_ONLY` | Исполняемый внутренний код или валидируемый контракт без публичной продуктовой поверхности. |
| `RESEARCH_ONLY` | Исследовательское назначение; не доказательство продуктовой эффективности. |
| `PROPOSED` | Предлагаемая граница UI/интеграции, которую еще надо реализовать. |
| `UNAVAILABLE` | Возможность не предоставлена изученной текущей поверхностью. |

`REAL_INTERNAL_ONLY` не означает промышленную полноту, стабильность версии или подтвержденную эффективность. V3 прямо обозначен как candidate в `src/archguard/security/analyzer_v3.py:1`.

## Реестр возможностей

В таблице указан точный `путь:символ`; номера строк позволяют быстро проверить привязку. Test — существующее свидетельство в исходниках тестов, а не утверждение, что весь suite запускался в P039.

| Возможность / класс | Точный источник | Вход → выход | Проверка и ограничения | Возможность UI |
|---|---|---|---|---|
| SEC registry — `REAL_INTERNAL_ONLY` | `src/archguard/security/rules.py:canonical_rules` (163), `SecurityRuleRegistry` (180), `SecurityRuleDefinition.frozen_metadata` (55) | SEC001–010, язык, capability → канонические определения и отдельно зарегистрированные детекторы | `tests/security/test_foundation.py:test_exact_canonical_rule_set_names_order_and_contract_status` (98), `test_rule_meaning_cannot_be_silently_repurposed` (429). Frozen registry сам по себе не реализует детекторы; default severity отсутствует. | Каталог правил с точным названием, scope и разницей contract/implementation. |
| Foundation orchestration — `REAL_INTERNAL_ONLY` | `src/archguard/security/analysis.py:SecurityAnalyzer.analyze` (23) | `SecurityAnalysisContext` → `SecurityAnalysisResult` | По умолчанию набор детекторов пуст; requested rules становятся unsupported. `test_foundation_production_path_emits_no_fake_findings_or_security_guarantee` (256). | Не считать foundation «готовым сканером»; явно показывать detector set. |
| Source intake — `REAL_INTERNAL_ONLY` | `src/archguard/security/analyzer_v1.py:SecuritySourceInput` (39); `src/archguard/security/domain.py:SecurityAnalysisContext` (265) | Уже классифицированный `RepositoryFile`, `bytes`, file UUID; repository/snapshot UUID, JAVA/TYPESCRIPT, requested rules, optional IAM → bound input | `source` скрыт из repr; сервис не получает directory или Git URL. IAM binding, дубли IDs/paths и language mismatch проверяются. `test_source_input_repr_hides_contents` (182), `test_iam_is_reused_read_only_and_false_bindings_rejected` (276). | Intake manifest, язык, snapshot, requested scope; запуск из UI требует отдельного адаптера. |
| Static V1 — `REAL_INTERNAL_ONLY` | `src/archguard/security/analyzer_v1.py:run_security_analysis` (385), `SecurityAnalyzerV1.analyze` (176); `src/archguard/security/engine_v1.py:BoundedFlowEngine` | Context + iterable source bytes + `FlowLimits` → result `security-static-dataflow-v1` | Tree-sitter Java/TS, локальная bounded propagation, без interprocedural полноты. Coverage V1: PARTIAL / UNSUPPORTED / FAILED. `tests/security/test_analysis_v1.py:test_unknown_never_safe` (98), `test_limits_are_partial` (129), `test_failure_is_not_clean_and_exception_is_not_serialized` (159). | Версия анализа и причина ограничения должны оставаться видимыми. |
| Interprocedural V2 — `REAL_INTERNAL_ONLY` | `src/archguard/security/analyzer_v2.py:run_security_analysis` (379), `SecurityAnalyzerV2.analyze` (168); `src/archguard/security/engine_v2.py:InterproceduralEngine.run_all` (334) | Те же source bytes + `V2Limits` → findings, coverage, summaries, proofs, call_resolution, fingerprint | Bounded local/imported specialization, не whole-program compiler. `tests/security/test_analysis_v2.py:test_parameter_return_sink_and_call_trace` (118), `test_source_file_limit_and_reversed_input_order` (274). | Межфункциональное расследование с переходом argument → parameter → return → caller. |
| Refinement V3 — `REAL_INTERNAL_ONLY`, candidate | `src/archguard/security/analyzer_v3.py:SecurityAnalyzerV3.analyze` (172), `run_security_analysis` (389); `src/archguard/security/engine_v3.py:RefinementEngine` (15) | V2 input/limits → `security-bounded-v3`, уточненные API/value facts и rule certificates | Наследует V2, уточняет primitive conversion/API identity, credential pattern и path handling; не универсальное расширение coverage. `tests/security/test_refinement_v3.py:test_primitive_java_randomness_conversion` (241), `test_java_jdbc_script_api_types_and_fully_qualified_shadowing` (254), `test_recursion_bounds_and_ts_deserialization_honesty` (290). | Отдельный version badge; никакой молчаливой замены V2 на V3. |
| Security finding — `REAL_INTERNAL_ONLY` | `src/archguard/security/domain.py:SecurityFinding` (200), `evidence_integrity` (224), `finding_identity` (177) | Rule/source/evidence/status → валидируемый SEC finding с UUID5 identity | Все evidence refs должны разрешаться; совпадают язык и версия; incomplete flow не допускает SUPPORTED. `test_finding_roundtrip_severity_not_evidence_strength_and_stable_identity` (177), `test_dangling_and_duplicate_evidence_references_rejected` (235). | Находка как доказуемое утверждение: статус, severity, evidence strength, scope и source отдельно. |
| Security proof path — `REAL_INTERNAL_ONLY` | `src/archguard/security/domain.py:FlowPath.conservative_flow` (163), `FlowRole` (142); `src/archguard/security/analyzer_v2.py:make_finding` (42) | Ordered role/evidence references + complete + uncertainty → статический proof path | Полный путь начинается SOURCE, заканчивается SINK, не содержит UNKNOWN_FLOW/uncertainty. Не trace реального исполнения. `test_unknown_flow_remains_uncertain_and_is_not_a_taint_implementation` (245); V2 call-trace test (118). | Evidence rail со ссылками на конкретные позиции и разрывами неизвестности; не анимировать как runtime request. |
| Four-state dataflow — `REAL_INTERNAL_ONLY` | `src/archguard/security/flow_v1.py:FlowState` (14), `FlowValue` (39), `merge` (85) | UNTAINTED / TAINTED / SANITIZED / UNKNOWN, path facts → joined value | UNKNOWN доминирует; sanitizer rule-specific; переполнение пути сбрасывает safety. `test_lattice_sanitization_and_recontamination` (103), `test_unknown_library_cannot_preserve_sanitization` (207). | UNKNOWN нельзя рисовать зеленым; sanitizer не является универсальной защитой. |
| Call resolution / summaries — `REAL_INTERNAL_ONLY` | `src/archguard/security/index_v2.py:DeclarationIndex.resolve` (183); `src/archguard/security/summaries_v2.py:FunctionSummary` (110), `SummaryCache` (143) | Parsed local declarations/imports, arguments, heap slots → target states и parameter/return/sink/field effects | EXACT/UNAMBIGUOUS_LOCAL могут специализировать body; PARTIAL/AMBIGUOUS/UNRESOLVED сохраняют неизвестность. Recursive fixed point отсутствует. `test_call_target_bound_reports_ambiguity` (240), `test_constructor_field_and_parameter_write_summaries` (252), `test_cache_is_bounded_invalidates_source_and_preserves_canonical_output` (133). | Показывать альтернативные/неразрешенные цели и budget reason, не выдумывать точный вызов. |
| Framework packs — `REAL_INTERNAL_ONLY` | `src/archguard/security/frameworks_v2.py:FrameworkPack` (9), `packs` (32); `src/archguard/security/api_v1.py:APIEntry` (12), `entries` (33) | Язык + подтвержденная API identity → modeled source/sink/propagation/sanitizer semantics | 17 declared API subsets; не гарантии всех версий framework. `test_registry_real_packs_proofs_and_no_ts_deserialization` (174), `test_api_pack_typed_and_unique` (200). | Evidence показывает pack/API identity и условия, не маркетинговый логотип «полная поддержка». |
| Rule-specific safety proof — `REAL_INTERNAL_ONLY` | `src/archguard/security/frameworks_v2.py:proofs` (194); `src/archguard/security/summaries_v2.py:SafetyProof` (103) | Preconditions + same-value/guard evidence → kind, rule_ids, evidence locations, scope | У каждого proof есть invalidators и limitations; тест registry (174), `test_interprocedural_objects_and_new_taint_after_sanitizer` (273). | Панель «Почему граница признана / почему потеряна», конкретный guard и трансформация. |
| Scoped negative certificate — `REAL_INTERNAL_ONLY`, V3 candidate | `src/archguard/security/completeness_v3.py:CompletenessCertificate` (14), `certify` (57), `map_v3_outcome` (128) | Rule/language + AST units + diagnostics/failure → COMPLETE либо NOT_PROVEN | Реальный COMPLETE сейчас только для узкой SEC008/TS grammar; не для репозитория. `test_completeness_required_for_negative_and_version_separation` (150), `test_certificate_invalidation_schema` (174), `test_closed_grammar_rejects_unmodeled_constructs` (199). | Отдельная карточка «Negative in declared scope» с обязательным раскрытием certificate. |
| Result JSON / report — `REAL_INTERNAL_ONLY` | `src/archguard/security/domain.py:SecurityAnalysisResult` (304), `SecurityReportSection` (343); `src/archguard/core/model/base.py:DomainModel` (6) | Python model ↔ `model_dump_json` / `model_validate_json` | Extra fields запрещены, version/evidence binding проверяется; metadata остается generic JSON. `test_security_domain_schemas_and_result_coverage_are_versioned_and_discriminated` (417); безопасная P039 round-trip проверка ниже. | Реальный контракт для предлагаемого local-file importer; не существующий HTTP API. |
| Generic finding/evidence/trace — `REAL_INTERNAL_ONLY` | `src/archguard/core/findings/model.py:Finding` (19); `src/archguard/core/evidence/__init__.py:Evidence` (38); `src/archguard/core/traces/__init__.py:Trace` (22) | Generic finding + evidence + contiguous trace → namespace-bound model | Generic SEC schema существует как future shape, но SecurityAnalyzer возвращает отдельный `SecurityFinding`. `tests/unit/test_findings.py:test_sec_future_schema_roundtrip` (19), `test_cross_namespace_evidence_rejected` (52), `test_trace_must_be_contiguous` (123). | Общие компоненты отображения допустимы; смешение wire schemas ARCH/SEC — нет. |
| Confidence — `REAL_INTERNAL_ONLY` contract | `src/archguard/core/findings/confidence.py:Confidence` (15), `validate_calibration` (23) | score 0…1 + calibration status/ref → Confidence либо None | Неоткалиброванный score не вероятность; calibrated требует reference. `tests/unit/test_findings.py:test_confidence_semantics` (101). У executable SecurityFinding поля confidence нет. | Security показывает evidence_strength, не придуманную вероятность. Отсутствие значения — «Not supplied». |
| Health / info HTTP — `API_EXPOSED` | `src/archguard/api/app.py:create_app` (14), `health` (35), `system_info` (39) | GET `/health`, GET `/api/v1/system/info` → health/foundation metadata | `tests/integration/test_api.py:test_no_fake_analysis_endpoint` (27) проверяет, что только эти два paths существуют. | Connection status можно подтвердить; readiness анализа из health не следует. |
| Security HTTP / public CLI scan — `UNAVAILABLE` | `src/archguard/api/app.py:create_app`; `src/archguard/cli.py:_parser` (82) | Нет Security request/result endpoint и группы `security` | API paths и полный список CLI groups проверены по коду; `/analyze` и `/api/v1/analyze` ожидаемо 404 в тесте. | Кнопка реального Scan требует новой интеграции. Сейчас — demo/imported artifact mode. |
| Engineering audit CLI — `CLI_ONLY`, research maintenance | `scripts/prompt028_security_analysis.py:main` (10) | action `audit|freeze|verify`, optional quality/commit → JSON summary | Это аудит/заморозка engineering receipts, не пользовательский Security scan. Команда и ее infrastructure implementation не запускались; данные receipts не читались. | Не предлагать как рабочий scan backend или источник UI-метрик. |
| Outcome normalization — `RESEARCH_ONLY` adapter reused by V3 | `src/archguard/security_benchmark/protocol.py:Outcome` (132), `map_outcome` (143), `map_p029_outcome` (169); `completeness_v3.py:map_v3_outcome` | Finding statuses + versioned coverage → outcome | Это код интерпретации результата; не ground truth или доказательство efficacy. V1 metadata не совместима с `map_p029_outcome` напрямую. | Версионная нормализация без выдуманных negative/not-applicable состояний. |
| Browser artifact importer / source attachment — `PROPOSED` | Existing boundary: `SecurityAnalysisResult`; implementation отсутствует | Пользовательский JSON → validated local view model; optional отдельный source attachment | Нужны version-aware metadata validation, provenance, лимиты размера и безопасный text renderer. | Честная ближайшая интеграция с реальными результатами без притворного backend. |
| Security effectiveness / repo safety score — `UNAVAILABLE` в runtime product contract | `SecurityReportSection.effectiveness_metrics_available` (346); `analyzer_v2.py:SecurityAnalyzerV2.analyze` (339), `analyzer_v3.py` (349) | Runtime metadata → `NOT_AVAILABLE`, guarantee=false | Исследовательские данные не открывались и не служат основанием для product precision/recall/F1. | Не показывать Security score, accuracy, CVSS compliance или «репозиторий безопасен». |

## Call paths и реальные ограничения

V1: `run_security_analysis` → `SecurityAnalyzerV1.analyze` → JavaParser/TypeScriptParser со strict syntax → `BoundedFlowEngine.run` → `StaticFlowDetector.analyze` → `finding` → `SecurityAnalysisResult`.

V2: `run_security_analysis` → `SecurityAnalyzerV2.analyze` → classified bytes → parser → `SourceUnit` → `DeclarationIndex` → `InterproceduralEngine.run_all` → `V2Detector.analyze` → `make_finding` → typed result + summaries/proofs/call_resolution + fingerprint.

V3 использует тот же intake/index/summary model, заменяет engine на `RefinementEngine`, detector на `V3Detector`, добавляет `certify` для каждого requested rule. Coverage status намеренно сохраняет `SUPPORTED_PARTIAL_V2_SCOPE`; настоящий `analyzer_version` — `security-bounded-v3`. Нельзя определять поколение анализатора только по строке coverage status.

Без source units, при parse errors, intake overflow или engine failure анализ не становится успешным пустым результатом. В V2/V3 `failed` блокирует evaluation соответствующих поддерживаемых правил. Исключения превращаются в стабильные diagnostics без публикации exception text/stack. Дубли identities/paths и неверный IAM binding могут непосредственно вызвать ValueError. Источники: `analyzer_v1.py:176–235,314–343`; `analyzer_v2.py:168–246,288–339`; `analyzer_v3.py:172–248,327–350`.

Основные V2/V3 defaults (`src/archguard/security/summaries_v2.py:V2Limits`, 42): depth 4, expansions 256, recursion visits 1, targets/call 4, summary nodes 4096, summary cache 256, path steps 64, aliases/object 32, heap objects 256, fields/object 64, total fields 2048, source files 64, bytes/file 2 MiB, total bytes 8 MiB, actual nodes 50,000, symbolic nodes 50,000, candidates 512. V1 дополнительно ограничивает tracked values, branch states, expression depth и nodes/file (`flow_v1.py:FlowLimits`, 21). Это детерминированные границы, не performance/SLA обещание. UI должен показывать причину остановки и затронутую scope, а не progress=100% как доказательство полноты.

Call resolution признает lexical functions, известные локальные instances, same-class/static methods, явные relative named/namespace imports. Не fetching модулей, не inheritance/virtual-dispatch compiler, не wildcard/re-export/default-module resolution, не общая closure/framework-callback модель. Same-arity Java overload остается ambiguous. Dynamic indices/writes и неподдерживаемые control flow сохраняют UNKNOWN. Источник: `docs/security/SECURITY_ANALYSIS_V2.md:23–62`.

## SEC001–SEC010: обещания по каждому правилу

Канонические названия фиксированы в `src/archguard/security/rules.py:NAMES` (20), определения — `DEFINITIONS` (72). V2 scope таблица: `docs/security/SECURITY_ANALYSIS_V2.md:73–90`. V3 наследует поддержку и добавляет узкие уточнения; это не доказательство общего снятия перечисленных ограничений.

| Rule | Каноническое имя | Реальный scope / принципиальное ограничение |
|---|---|---|
| SEC001 | Hardcoded Secret | V2 V1-equivalent literal patterns и redaction; V3 уточняет recognition. Нет проверки валидности credential, env/config acquisition или универсальной secret-discovery полноты. Значения не показываются. |
| SEC002 | SQL Injection Risk | JDBC Statement/constant prepared bind, pg string/bind, explicit Prisma unsafe APIs, helpers. Нет универсального query-builder/tagged ORM proof. SQL text без source/sink не finding. |
| SEC003 | Command Injection Risk | Shell text, executable/operands, spawn shell options, Java argv. Separate argv с shell=false доказывает только отсутствие modeled shell interpolation; tainted operand остается POTENTIAL argument injection. |
| SEC004 | Path Traversal Risk | File/helper/field flows и узкий lexical confinement. normalize/resolve сам по себе не proof. Нет symlink/race/realpath guarantee. |
| SEC005 | Unsafe Deserialization | Java Servlet InputStream → ObjectInputStream construct/read; unknown origin/filter partial. TypeScript CONTRACT_ONLY/UNSUPPORTED. JSON.parse не unsafe object sink. |
| SEC006 | Server-Side Request Forgery Risk | Java URL/Node HTTP(S) string/URL flows и exact-host guards. DNS/IP rebinding, redirects, broad scheme/port policy не доказаны. Constant request сам по себе не SSRF. |
| SEC007 | Cross-Site Scripting Risk | JSP/typed DOM HTML sinks, aliases/helpers, default imported DOMPurify return. Text sink исключен; custom options/wrappers/другой render context unknown. |
| SEC008 | Weak Cryptography | MD5/SHA-1 facts с security-vs-checksum purpose, explicit DES/RC4/ECB configuration. Unknown purpose POTENTIAL, non-security checksum не автоматический риск. Единственный текущий COMPLETE certificate узко здесь. |
| SEC009 | Insecure Randomness | PRNG через helpers/fields к token/session/reset purpose. Secure RNG и simulation/game/parser uses исключены; arbitrary downstream purpose неизвестна. |
| SEC010 | Unsafe Dynamic Code Execution | eval/Function/ScriptEngine/vm/string timers через helpers. Constant expressions, callbacks и reflection не выдумываются как sinks; unknown interpreters partial. |

Языки Security: только `JAVA` и `TYPESCRIPT` (`domain.py:SecurityLanguage`, 40). JavaScript/TSX Security contracts не объявлены. Framework source требует import/type/annotation evidence: объект с именем `req`, метод `query` или `sanitize` не доказывает соответствующую API identity.

17 packs: JAVA_SERVLET_V2, JAVA_SPRING_WEB_V2, JAVA_JDBC_V2, JAVA_HTTP_V2, JAVA_FILESYSTEM_V2, JAVA_CRYPTO_V2, JAVA_PROCESS_V2, JAVA_SERIALIZATION_V2, JAVA_RENDER_SCRIPT_V2; TS_EXPRESS_V2, TS_PG_V2, TS_NODE_HTTP_V2, TS_NODE_FS_V2, TS_DOM_V2, TS_NODE_CRYPTO_V2, TS_PROCESS_SCRIPT_V2, TS_PRISMA_RAW_UNSAFE_V2 (`frameworks_v2.py:packs`; `SECURITY_ANALYSIS_V2.md:64–71`). Это API models, не подключения к сервисам или аккаунтам.

## Статусы, которые интерфейс обязан разделять

1. **Finding status**: CONFIRMED_PATTERN, SUPPORTED, POTENTIAL, INSUFFICIENT_EVIDENCE, NOT_APPLICABLE (`domain.py:SecurityFindingStatus`, 59). CONFIRMED_PATTERN подтверждает распознанный static pattern, не эксплуатируемую vulnerability.
2. **Severity**: INFO/LOW/MEDIUM/HIGH/CRITICAL; оценка важности отдельно от доказательности.
3. **Evidence strength**: LOW/MEDIUM/HIGH; качественная сила evidence, не численная вероятность. У SecurityFinding нет generic Confidence.
4. **Execution coverage**: V1 PARTIAL/UNSUPPORTED/FAILED; V2/V3 SUPPORTED_PARTIAL_V2_SCOPE/CONTRACT_ONLY/FAILED плюс requested/supported/evaluated booleans.
5. **Flow state/completeness**: UNTAINTED/TAINTED/SANITIZED/UNKNOWN — внутренние value facts; complete/uncertainty — конкретный evidence path. Complete path не делает весь run complete.
6. **Outcome / scope certificate**: интерпретация rule-scoped результата; certificate COMPLETE/NOT_PROVEN — отдельное основание для очень узкого negative.

Outcome precedence (`protocol.py:map_outcome`, 143): FAILED/UNSUPPORTED перекрывают остальные; затем CONFIRMED_PATTERN или SUPPORTED → DEFINITIVE_POSITIVE; затем POTENTIAL; затем INSUFFICIENT_EVIDENCE; затем явное NOT_APPLICABLE; затем PARTIAL; и только complete+applicable без finding → DEFINITIVE_NEGATIVE.

`applicable_rules` у V2/V3 выводится из существующих findings (`analyzer_v2.py:346`, `analyzer_v3.py:356`). Отсутствие правила в этом массиве **не доказывает NOT_APPLICABLE**. `unsupported_rules = requested - evaluated` включает failed rules; поэтому сначала требуется per-rule coverage status FAILED. Нельзя строить интерфейс только по двум counts findings/unsupported. Ноль findings в evaluated V2 всегда nondefinitive PARTIAL, не «clean».

### Что именно может означать scoped negative

`completeness_v3.py:certify` допускает COMPLETE только для SEC008 / TYPESCRIPT / одной source unit / ровно двух верхнеуровневых statements: default import из `crypto` или `node:crypto` и прямой literal-only вызов этого же alias. Разрешены createHash с sha256/sha384/sha512/sha3-256/sha3-512 либо createCipheriv с aes-128-gcm/aes-192-gcm/aes-256-gcm и тремя строковыми аргументами. Нет callbacks, branches или других calls; нет failures и diagnostics, кроме PARTIAL_ANALYSIS.

COMPLETE требует true для applicable, scope_complete, source_coverage_complete, sink_coverage_complete, call_resolution_complete, summary_resolution_complete, dataflow_scope_complete, framework_model_complete, proofs_sufficient; unsupported_constructs_present и analysis_failures_present должны быть false. Rule/language binding дополнительно проверяется при outcome mapping.

Это проверка **выбора алгоритма в закрытой grammar**, не правильности ключей, IV, протокола, криптографического использования или репозитория. В UI: «No weak algorithm in this certified scope», рядом конкретная declared_scope и reason code. Для импортированного файла: «Reported scope certificate» до проверки происхождения; структурная Pydantic-валидация не доказывает, что пользовательский JSON был произведен анализатором.

## Точная граница JSON import

Текущий внутренний wire shape — `archguard.security.domain.SecurityAnalysisResult`, а не generic `Finding`, не SARIF, не массив findings и не произвольный `{results: ...}`. Обертка `SecurityReportSection` отдельно допускает `{domain: "SECURITY", result: <SecurityAnalysisResult>, effectiveness_metrics_available: false}`. Product importer обеих форм пока `PROPOSED`.

| Поле SecurityAnalysisResult | Обязательность / точный тип |
|---|---|
| `namespace` | Literal `SEC`, default SEC. |
| `findings` | JSON array `SecurityFinding`, default empty. |
| `requested_rules` | Обязательный array SEC001–SEC010, без дублей. |
| `analyzed_rules` | Array правил, default empty. |
| `applicable_rules` | Array правил, default empty; subset analyzed. |
| `unsupported_rules` | Обязательный array правил; вместе с analyzed образует точное непересекающееся разбиение requested. |
| `diagnostics` | Array `{code, rule_ids, message}`, default empty. |
| `analyzer_version` | Обязательная непустая строка; модель не ограничивает ее известным enum. |
| `analysis_metadata` | JSON object, default empty. Вложенная семантика версии не валидируется этим полем автоматически. |
| `zero_findings_is_security_guarantee` | Literal false, default false. |

Существенные границы для разработчика importer:

- В envelope нет repository_id/snapshot_id/language; они находятся в findings. При пустом findings их нельзя восстановить. В UI это «Not supplied», либо отдельные **user-supplied** labels вне исходного model payload. Не вставлять придуманные snapshot/language внутрь валидируемого результата.
- Finding содержит `schema_version="security-finding-v1"`, `namespace="SEC"`, ID, repository/snapshot IDs, rule, title/description, severity, evidence_strength, status, language, primary_source, evidence/evidence_refs, optional source_ref/sink_ref/flow/remediation, metadata и analyzer_version. Identity вычисляется из source/snapshot/rule/flow; произвольные IDs не проходят текущую validation.
- SecurityEvidence содержит ID, kind, source reference, summary, analysis_version, related_evidence и metadata. **Исходного текста/сниппета в контракте нет.** Source reference — file UUID, canonical repository-relative path, координаты, language, optional symbol/module IDs и input category. UI из одного JSON может показать позиции и summaries, но не выдумывать source code. Для текста нужна отдельно разрешенная source attachment/integration.
- `SourceLocation` использует one-based inclusive координаты; без end это точка. end_line/end_column присутствуют вместе, end не раньше start (`src/archguard/core/locations/__init__.py:SourceLocation`, 11). В анализаторных engineering tests проверяются byte columns (`test_analysis_v1.py:test_multiline_locations_are_concrete_byte_columns`, 345); editor conversion должна учитывать UTF-8, а не считать столбец автоматически JS code-unit offset.
- `RepositoryPath` запрещает absolute paths, backslash, NUL, пустые/`.`/`..` сегменты (`core/model/types.py:_repository_path`, 13). Проверенный path остается ссылкой внутри artifact, не разрешением читать файл с диска.
- DomainModel frozen/extra=forbid и запрет NaN/Inf — реальные проверки. `analysis_metadata` остается `dict[str, JsonValue]`; его `coverage`, `proofs`, `summaries`, `call_resolution`, `completeness_certificates` нуждаются в **отдельной version-aware проверке**. Не принимать arbitrary certificate-status string за подтвержденную полноту.
- V2 metadata: coverage[rule] `{requested,supported,evaluated,status}`; limits; summaries; proofs; call_resolution; source_pack_version; interprocedural; provider_calls/credential_reads/connectivity_calls; security_effectiveness; partial; result_fingerprint. V3 добавляет completeness_certificates. V1 coverage status strings отличаются; V2 adapter к ним напрямую неприменим.
- `result_fingerprint` обеспечивает воспроизводимое представление, не цифровую подпись, provenance или доказательство запуска. Произвольный JSON может содержать синтаксически корректные, но недостоверные assertions.
- Render arbitrary titles/summaries/metadata как text; source paths не открывать автоматически и не превращать в unrestricted file reads. Import не должен запускать analyzer/provider, fetch модулей или делать network requests. Это требования **предлагаемого** importer, а не уже реализованная защита в browser UI.
- Unknown analyzer version: структурно разобрать если model позволяет, но не вычислять definitive outcome с неподходящим adapter. Показать «Unsupported result version» для interpretation; сохранить исходный статус как supplied.

Безопасно проверенный синтетический минимальный result (не результат анализа):

```json
{
  "namespace": "SEC",
  "findings": [],
  "requested_rules": ["SEC005"],
  "analyzed_rules": [],
  "applicable_rules": [],
  "unsupported_rules": ["SEC005"],
  "diagnostics": [],
  "analyzer_version": "security-interprocedural-v2",
  "analysis_metadata": {
    "coverage": {
      "SEC005": {
        "requested": true,
        "supported": false,
        "evaluated": false,
        "status": "CONTRACT_ONLY"
      }
    },
    "partial": true
  },
  "zero_findings_is_security_guarantee": false
}
```

Рекомендуемая реализация границы: распознать ровно result либо report wrapper; валидировать `SecurityAnalysisResult.model_validate_json` или `SecurityReportSection.model_validate_json`; отдельно проверить известную версию и metadata; только после этого построить UI view model. Самодостаточный browser importer должен честно назвать свой validator «prototype validation», если он не воспроизводит Pydantic invariants, UUID5 identity и versioned outcome mapping.

## Предлагаемое расследование Security

Первичный экран — не heatmap угроз и не общая оценка безопасности. Это рабочее пространство с finding queue, статическим evidence path и постоянно доступной карточкой coverage. Пользователь выбирает утверждение, видит его source/sink/proof/unknown boundary, затем решает, достаточно ли evidence для дальнейшего действия.

| Слой интерфейса | Что показывать | Семантическая граница |
|---|---|---|
| Run header | artifact provenance, analyzer version, supplied language/snapshot, requested/evaluated rules, failure/partial indicator | Health endpoint и импорт файла не означают, что сейчас прошел scan. |
| Finding queue | Rule/name, severity, finding status, evidence_strength, primary path, unknown count | Potential и insufficient остаются отдельными состояниями; не сортировать их как confirmed с меньшим процентом. |
| Evidence rail | SOURCE → PROPAGATION → CALL_ARGUMENT/CALLEE_PARAMETER → return → SANITIZER/guard → SINK; unknown cut явно | Статическая proof path; линия не изображает выполненный запрос. Не додумывать отсутствующие шаги. |
| Location viewer | original source coordinates, supplied summary, optional отдельно приложенный source text | При отсутствии текста — «Source not supplied», а не реконструкция. SEC001 остается редактированным. |
| Proof inspector | kind, rule, scope, preconditions, concrete locations, invalidators | SQL parameterization не защищает от XSS; DOM sanitizer не является generic sanitizer; guard validity относится к конкретному value identity. |
| Resolution drawer | EXACT / UNAMBIGUOUS_LOCAL / PARTIAL / AMBIGUOUS / UNRESOLVED; targets и budget diagnostics | Не соединять ambiguous target сплошной «доказанной» линией. |
| Coverage matrix | Все requested SEC rules; evaluation, outcome, framework scope, diagnostics | Нет findings ≠ negative; unsupported ≠ failed; applicability не выводится из finding count. |
| Negative dossier | certificate rule/language, declared scope, boolean conditions, reason codes, provenance | Только scoped negative; никакого «Secure repository», comprehensive crypto safety или общего зеленого score. |

ARCH structural graph и SEC proof path могут разделять location viewer, но их типы ребер и conclusions различаются. IMPORTS/CALLS architecture edges не заменяют taint propagation и не доказывают exploit chain. Сопоставление находки с module aggregate допустимо только при явной source/module binding; приблизительное demo-placement нужно помечать illustrative.

## Проверка P039

Проверена отдельная model-only команда в имеющемся Python 3.13 окружении, с `PYTHONPATH=src` текущего worktree и `PYTHONDONTWRITEBYTECODE=1`: синтетический `SecurityAnalysisResult` проходит JSON round-trip; `SecurityReportSection` также; namespace ARCH, guarantee=true и неизвестное top-level поле отклоняются. Анализаторы, Settings, repository intake и HTTP приложение не создавались. Начальная попытка через системный Python 3.9 оказалась несовместимой со StrEnum; успешная проверка использовала проектный Python 3.13.14, без установки зависимостей.

Полный test suite и исследовательские скрипты не запускались. Указанные test symbols проверены как engineering evidence в исходниках. Никакие результаты benchmark, accuracy или исторические научные выводы из этого аудита не следуют.
