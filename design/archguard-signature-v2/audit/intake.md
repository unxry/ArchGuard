# P039 — Intake, configuration, parsing and IAM audit

Дата: 2026-10-17. Статический аудит production-кода и названий/контрактов релевантных тестов. Анализаторы, внешние репозитории, Git clone, providers и Settings runtime не запускались; `.env`, credentials, private truth, adjudication и benchmark answer keys не читались. Тестовые ссылки ниже подтверждают наличие проверок в репозитории, **не являются заявлением об их запуске в этом аудите**.

Пути далее относительно корня repository; запись `path:symbol` обозначает проверенный символ. Классификация: **C** — реализовано в CLI и library; **L** — library-only configurable contract; **H** — действующий HTTP endpoint; **F** — будущая продуктовая интеграция; **B** — ограниченная реализация, требующая явного scope в UI. Возможность в enum сама по себе не равна работающей функции.

## Главный вывод для onboarding

Система уже умеет принимать local directory, local ZIP и credential-free HTTPS Git, строить inventory, последовательно парсить допустимые файлы и выдавать IAM со ссылками на исходный код. Это вызываемые application use cases и CLI-команды. В текущем HTTP-приложении нет API регистрации проектов, загрузки ZIP, анализа, очереди jobs или чтения findings: `src/archguard/api/app.py:create_app` объявляет только `GET /health` и `GET /api/v1/system/info` (**H**).

Поэтому «Add project» в новом дизайне должен различать подключённую будущую операцию и демонстрацию. Наличие `Project` в IAM не означает сохранённый workspace, историю запусков или cloud project. Наличие `database_url` не подтверждает persistence результатов.

## 1. Источники и проверка входа

| Возможность / класс | Реальный путь и символ | Вход → выход / входная поверхность | Ограничения и ошибки | Что показывать пользователю |
|---|---|---|---|---|
| Unified repository request **C** | `src/archguard/repository/models.py:RepositoryInput`; `src/archguard/application/discover_repository.py:DiscoverRepository.open/execute` | `source_type`, `location`, optional `repository_id/ref` → `DiscoveredRepository(snapshot, workspace)` в context manager; `execute` возвращает долговечный `RepositorySnapshot`. CLI `repo inspect LOCATION` | Location nonblank, NUL запрещён. `ref` только для Git и safe regex. После закрытия context lazy access недоступен. Не persistence | Тип источника → значение → явный ref → результат inventory. Не показывать «проект сохранён» по одному snapshot |
| Local directory **C** | `src/archguard/infrastructure/repository/local.py:LocalDirectorySource.materialize` | Локальный directory path → `MaterializedRepository`, path expanduser/resolve(strict=True) | Не файл; отсутствующий root → `RepositoryNotFound`; unreadable → `RepositoryReadError`; wrong source type → `InvalidRepositorySource`. Root symlink разрешается через resolve; вложенные symlinks не обходятся | «Папка доступна локальному исполнителю»; native browser path picker ещё не реализован |
| ZIP intake **C/B** | `src/archguard/infrastructure/repository/zip_source.py:ZipRepositorySource.materialize`, `safe_archive_path`, `validate_archive`, `extract_archive` | Локальный ZIP path → временная распаковка → workspace; CLI `--source zip` | Only regular file, no-follow open; запрещены traversal/absolute/drive/alternate-stream paths, symlinks/special entries, duplicates/case collisions, encrypted ZIP, file-directory collisions. Лимиты проверяются до scan exclusions и во время extraction. Не HTTP upload | Размер архива и лимиты, ошибка конкретного класса, предупреждение о неподдержанной структуре; не имитировать успешный drag-and-drop backend |
| HTTPS Git **C/B** | `src/archguard/infrastructure/repository/git_source.py:validate_public_url`, `GitRepositorySource.materialize`; `git_runner.py:SubprocessGitRunner.run` | HTTPS URL + branch/tag/full 40/64-character SHA → depth-1 clone, optional fetch/checkout, verified HEAD revision; CLI `--source git --ref ...` | URL без credentials/query/fragment, nonempty host/path, без whitespace/control/backslash; only HTTPS protocol, no redirects, hooks/fsmonitor disabled, no credential helper, no recurse submodules, no LFS smudge, prompt disabled. Timeout defaults 60 s, process group killed. Git CLI must exist | Public HTTPS-only form, ref optional, actual resolved revision after success; отдельные ошибки URL/clone/timeout. Authenticated providers не реализованы |
| Safe reading **C** | `src/archguard/infrastructure/repository/filesystem.py:SafeRoot`; `workspace.py:MaterializedRepository.open_file/open_source_file` | Canonical repository-relative path из inventory → binary stream | Только известные inventory files; parser access только eligible. Проверяются изменения после discovery и symlink parent; закрытый workspace не пригоден для чтения | При изменившемся файле предложить повторное discovery; source viewer не должен молча читать другой revision |

Слово «public» в Git URL — заданный режим без credentials, **не доказанная network-publicness**. Проверенный `validate_public_url` не делает DNS/private-address проверки и не доказывает доступность ресурса. Нельзя описывать его как готовую защиту произвольного server-side URL fetching. Git source не устанавливает зависимости и не запускает сборку проекта. ZIP/Git workspaces временные и удаляются при выходе из context, включая ошибки.

**Тестовые опоры:** `tests/integration/test_repository_local.py:test_lazy_reader_rejects_changed_file_and_symlink_parent`, `test_symlinks_and_special_files_are_never_followed`, `test_typed_invalid_source_errors`; `tests/integration/test_repository_zip.py:test_zip_slip_and_drive_paths_are_blocked`, `test_zip_collisions_are_rejected`, `test_zip_limits_apply_before_default_exclusions`, `test_workspace_cleanup_when_consumer_fails`; `tests/integration/test_repository_git.py:test_real_offline_git_clone_revision_ref_and_cleanup`, `test_git_rejects_unsafe_sources_without_running_git`, `test_git_timeout_cleans_materialization`, `test_real_git_process_timeout_terminates_group`. Git integration test обозначен offline: его наличие не доказывает доступ к внешним репозиториям в текущем окружении.

## 2. Inventory, exclusions и resource policy

`src/archguard/repository/policy.py:RepositoryScanPolicy` (**L**, частично **C**) — типизированная immutable policy. CLI выставляет `extra_exclusions` из повторяемого `--exclude` и `respect_gitignore` через `--no-gitignore`; остальные численные лимиты не имеют CLI flags в `src/archguard/cli.py:_repository_arguments`.

| Default policy | Значение |
|---|---:|
| Files / traversed entries | 100,000 / 200,000 |
| Eligible source bytes / hashable file bytes | 2 MiB / 8 MiB |
| Total hash budget / gitignore bytes | 256 MiB / 64 KiB |
| Compressed ZIP / single uncompressed file | 128 MiB / 64 MiB |
| Total uncompressed ZIP | 512 MiB |
| Git operation deadline | 60 s |

Default excluded directory names: `.git`, `node_modules`, `target`, `dist`, `build`, `coverage`, `.next`, `out`, `.gradle`, `.idea`, `.vscode`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.venv`, `.archguard`. Это кодовая policy, не прочитанное состояние окружения.

`src/archguard/infrastructure/repository/discovery.py:collect_entries` применяет default/custom exclusions и nested gitignore scopes; учитывает visited entries, исключает symlinks/special files; результаты сортируются. `describe_file` читает prefix до 4096 bytes для classification, хеширует в пределах бюджета и проверяет изменение размеров. `source_roots` эвристически группирует `src`, `src/main/java`, `src/test/java`, test directories; это **B**, не полноценное понимание Maven/Gradle/TS workspace graph.

`classification.py:classify` распознаёт extensions Java/TS/TSX/JS/JSX и ряд несопровождаемых языков/данных, manifest/lockfile names, generated/minified/test/binary признаки. `RepositoryFile` сохраняет `language`, `kind`, generated/binary/large flags, `analysis_eligible`, hash status и optional sha256. Inventory может перечислять Python, JSON или YAML; parser support из этого не следует. Список manifest names не означает dependency installation или полное вычисление build configuration.

`src/archguard/repository/models.py:RepositorySnapshot` → schema 1.0, snapshot/repository IDs, source type, `root="."`, Git revision only for Git, timestamp, files, detected languages, manifests/lockfiles/source_roots/exclusions/statistics, fingerprint и `supported_for_analysis`. Materialization path не сериализуется. Snapshot ID связан с inventory fingerprint; это не commit ID для local/ZIP. Files без sha256 из-за бюджета требуют видимой информации о hash coverage: не называть fingerprint доказательством полного content hashing.

**Критическая UX-разница:** `supported_for_analysis` проверяет наличие target-language nonbinary file; `analysis_eligible` дополнительно требует source/test kind, not generated, not binary, not large. Поэтому `supported_for_analysis=true` совместим с `eligible_files=0`. Onboarding должен показывать обе величины и причины exclusions, не давать безусловный «Ready for complete analysis».

**Тесты:** `tests/unit/test_repository_contracts.py:test_snapshot_roundtrip_without_materialization_paths`, `test_snapshot_invariants`, `test_policy_rejects_invalid_limits`; `tests/unit/test_repository_classification.py:test_language_detection`, `test_file_classification`; `tests/integration/test_repository_local.py:test_nested_gitignore_and_negation`, `test_binary_large_generated_and_hash_budget`, `test_fingerprint_determinism_and_content_change`, `test_empty_project_is_valid`.

## 3. Configuration: текущие области не смешивать

| Область / класс | Код и I/O | CLI/API | Граница / UX |
|---|---|---|---|
| Scan **L/C** | `repository/policy.py:RepositoryScanPolicy` → validated policy | Source flags, `--exclude`, `--no-gitignore`; no HTTP | Exclusion preview и limits — настройка intake, не architecture rule |
| Parsing **L/C** | `parsing/config.py:ParserConfig`: languages, 2 MiB source limit, error-node collection, strict flag, diagnostics cap 100/file | `--strict`; остальные параметры library-only | Tolerant/strict — политика синтаксических ошибок, не строгость ARCH rules |
| Extraction **L/C** | `extraction/config.py:ExtractionConfig`: namespace, project_name, skip_invalid_files; caps 10,000 declarations, 50,000 references, 10,000 imports/file, 1,000 provenance/edge | `--namespace` default `archguard:default-project`; остальные library-only | Stable identity namespace нужен для повторных результатов; нет persisted project identity management |
| Target architecture **C** | `infrastructure/architecture_specification.py:load_architecture_file` → `architecture/specification/loader.py:ArchitectureSpecLoader.load` → `ArchitectureSpecification` | `architecture validate SPEC [--json]`; `architecture check LOCATION --spec SPEC` | Явная target YAML, отдельная от discovered structure. Valid YAML не означает conformant code |
| Graph / discovery profile **C** | `infrastructure/graph_configuration.py:load_graph_configuration`; `discovery_configuration.py:load_discovery_configuration` → typed JSON models | `graph analyze --config ...`; `architecture discover --config ...`; graph `--projection`, `--relations` | Bounded 128 KiB UTF-8 JSON. Неправильная schema → typed configuration error. Структурное discovery не требует target spec |
| Runtime settings **L** | `infrastructure/settings.py:Settings` объявляет app_name, environment, debug, database_url SecretStr, log_level; prefix `ARCHGUARD_` | Python settings injection; no settings-edit HTTP | Класс настроен на `.env`, но файл и instance в этом аудите не читались/не создавались. Production debug запрещён; database URL валидируется как PostgreSQL+psycopg. Это deployment settings, не готовая product settings page |

Target architecture schema в `architecture/specification/models.py` version 1.0: layers/modules с include/exclude relative POSIX globs, unique names; rule selectors выбирают ровно layer либо module. RuleBase содержит severity (MEDIUM default), description, enabled, relations. Поддержаны forbidden_dependency, layer_dependency, reverse_dependency, module_boundary, circular_dependency. References и rule IDs валидируются, scopes/rules нормализуются; `ArchitectureSpecification.canonical_json/fingerprint` дают стабильное представление и digest.

YAML loader принимает UTF-8, максимум 128 KiB, depth 32, 10,000 nodes. Ограничивает scalar/tag types, rejects duplicate keys/aliases/unsupported versions/rule kinds; bounded reader скрывает local paths в ошибке. `ArchitectureSpecificationError` может передать line/column через CLI JSON error. Будущий редактор policy (**F**) должен показывать validation diagnostics и canonical fingerprint, не обещать live autosave/backend persistence.

**Тесты:** `tests/unit/test_architecture_specification.py:test_examples_roundtrip_and_normalize`, `test_hash_ignores_mapping_scope_and_rule_order`, `test_yaml_constructor_never_executes`, `test_loader_resource_limits`, `test_syntax_error_has_safe_coordinates`; `tests/integration/test_architecture_cli.py:test_spec_validate_json_and_human`, `test_invalid_validate_exit_two`, `test_cli_overlap_is_diagnostic_and_exit_two`; `tests/integration/test_graph_cli.py:test_graph_export_config_overrides_and_determinism`; `tests/integration/test_discovery_cli.py:test_existing_target_file_does_not_define_discovery`, `test_typed_configuration_input_and_output_errors`; `tests/unit/test_settings.py:test_production_debug_rejected`.

## 4. Parsing → extraction → conservative resolution

| Этап / класс | Реальный символ и вход → выход | Полнота, ошибки, UX |
|---|---|---|
| Parser registry **C/B** | `parsing/factory.py:create_parser_registry`; `parsing/enums.py:ParserLanguage` → JAVA, TYPESCRIPT, JAVASCRIPT, TSX; Tree-sitter adapters | JSX использует JS grammar. Python присутствует в general language enum, но не в parser languages. Показывать конкретный dialect, parser/runtime version |
| Repository parse **C** | `application/parse_repository.py:ParseRepository.iter_parse(snapshot, workspace)` → sequential `ParsedSourceFile` либо `FileParseMetadata`; `execute` → `ParseRepositoryResult` без retained trees | Per-file statuses PARSED/INVALID/SKIPPED/UNSUPPORTED/FAILED. Invalid UTF-8/read/runtime failures изолируются; unsafe source-bearing exception text не логируется. Unsupported/disabled/ineligible/size-limit видны отдельно |
| Tolerant vs strict **C/B** | `parsing/config.py:ParserConfig.strict_syntax_errors`; adapters return tree + metadata/diagnostics | Tolerant syntax error может сохранить parsed tree; strict помечает INVALID и сохраняет tree; extraction по умолчанию skip invalid. «Parsed» не равно «ошибок нет» |
| Extractors **C/B** | `extraction/java/extractor.py:JavaExtractor.extract`; `extraction/ecmascript/extractor.py:ECMAScriptExtractor.extract`, TypeScriptExtractor/JavaScriptExtractor/TSXExtractor → `ExtractedFileFacts` | Компактные declarations/imports/exports/references, source locations, extractor/runtime provenance. Статические синтаксические факты, не выполнение Java/JS/TS и не compiler/typechecker |
| Symbol resolution **C/B** | `extraction/resolution/resolver.py:SymbolResolver.resolve/resolve_reference`; `index.py:SymbolIndex` → `ResolutionResult` | RESOLVED, AMBIGUOUS, UNRESOLVED, EXTERNAL. Dynamic reference, unknown receiver, local binding conflict остаются unresolved. Unique compatible target required; arity helps, но это не полная semantic type inference |
| External references **B** | `extraction/resolution/models.py:ExternalDependency`; resolver `_import` | Namespace root в java_namespace/npm/node, а не вымышленные external classes/functions. Нельзя показывать unresolved edge как доказанную runtime call chain |

`ExtractedFileFacts` содержит provenance и structural facts, но не полный source text или native parser object. Java extraction охватывает declarations/modifiers/heritage; ECMAScript extraction — exports, imports/aliases, functions/classes, CommonJS-паттерны с ограничениями shadowing/mutation. Наличие decorators или type constructs в AST не подтверждает framework-specific flow analysis. Re-export/wildcard chains консервативны; ambiguity не должна превращаться в guessed edge.

**Тесты:** `tests/unit/test_parsing_adapters.py:test_valid_fixtures_build_real_trees`, `test_strict_mode_marks_invalid_and_keeps_tree`, `test_diagnostic_limit_preserves_complete_counts`, `test_invalid_utf8_is_typed_and_byte_position_is_exact`, `test_jsx_uses_javascript_grammar`; `tests/integration/test_parsing_repository.py:test_unexpected_adapter_failure_is_visible_isolated_and_private`, `test_dozens_of_files_are_sequential_and_do_not_retain_all_trees`; `tests/integration/test_iam_pipeline.py:test_typescript_constructs_and_jsx_exclusion`, `test_explicit_relative_import_alias_call_and_new`, `test_ambiguity_never_produces_guessed_edges`, `test_dynamic_import_require_and_unknown_receiver`, `test_reexport_chains_and_wildcards_are_conservative`, `test_extraction_is_offline_and_does_not_execute_sources`.

## 5. IAM и output contracts

**Use case — C/B:** `src/archguard/application/build_iam.py:BuildIAM.execute(snapshot, workspace) -> IAMBuildResult`. Последовательно потребляет parse iterator, извлекает compact facts, строит SymbolIndex, выполняет resolution, вызывает `iam_building/builder.py:IAMBuilder.build`, собирает statistics/diagnostics. Extraction failures видимы как MISSING_EXTRACTOR/EXTRACTION_FAILED, strict-invalid получает INVALID_FILE_SKIPPED. Результат включает `iam`, config, parsing, facts, resolutions, statistics, diagnostics, `is_valid`, `is_complete`, builder/resolver versions.

`is_valid` зависит от parser validity и ERROR diagnostics. `is_complete` снижается при проблемах обработки, unsupported/failed inputs, skipped eligible files и extraction diagnostics. При этом unresolved/external resolution diagnostics добавляются **после** вычисления накопительного completeness; `is_complete=true` не означает «все символы разрешены». В UX resolution coverage (`resolved / ambiguous / unresolved / external`) — отдельный показатель, без превращения в security confidence. CLI `iam build` в конце проверяет `is_valid`, а не `is_complete`, поэтому exit 0 сам по себе также не доказывает полную модель.

| Контракт | Символ / поля | Продуктовая интерпретация |
|---|---|---|
| Domain validation **L** | `core/model/base.py:DomainModel`: frozen, extra=forbid, validate_default, revalidate_instances, no inf/nan | Typed boundary, но nested JSON metadata не становится immutable storage |
| Identity/location **L** | `core/model/entities.py:Project/Module/Package/SourceFile/Symbol`; `core/model/types.py:RepositoryPath`; `core/locations/__init__.py:SourceLocation` | Project-scoped stable IDs, canonical relative POSIX path; start/end line/column, start column default 1. Source refs доступны; IDE deep-link route пока F |
| IAM snapshot **L/C** | `iam/model.py:ArchitectureModel`, schema 1.0; project/modules/packages/source_files/symbols/nodes/edges/metadata | Referential/collection consistency validated. Graph проекция продукта должна сохранять source identity, не выдавать layout grouping за реальный module |
| Graph primitives **L** | `iam/nodes.py:ArchitectureNode`: kind/name/qualified_name/language/module/package/file/symbol/layer/location/attributes; `iam/edges.py:ArchitectureEdge`: source/target/kind/location/weight/attributes | Node kind и edge kind — различимые данные. `weight` не является severity/confidence. Enum DATA_FLOW/SECURITY не доказывает полную реализацию этих видов анализа |
| Full build JSON **C** | `cli.py:main` при `iam build --json`: `IAMBuildResult.model_dump_json(indent=2)` | Полный envelope: факты, parsing, diagnostics и completeness. Frontend adapter должен знать именно этот формат |
| Canonical IAM export **C** | `iam_building/serialization.py:serialize_iam`, `validate_built_iam`; `iam build --output FILE` | Только ArchitectureModel; JSON sorted keys, UTF-8, indent=2, trailing newline. Не тот же payload, что stdout `--json` |

**Тесты:** `tests/unit/test_iam.py:test_iam_roundtrip_and_entity_links`, `test_version_and_unknown_fields_rejected`, `test_stable_ids_are_project_and_category_scoped`; `tests/integration/test_iam_pipeline.py:test_compact_facts_and_iam_exclude_source_and_native_objects`, `test_utf8_crlf_inclusive_source_coordinates`, `test_streaming_releases_previous_parsed_file`, `test_builder_rejects_fake_resolution_and_snapshot_mismatch`, `test_three_call_sites_preserve_all_locations_in_order`; `tests/integration/test_iam_cli.py:test_iam_cli_json_full_export_summary_and_determinism`, `test_iam_cli_zip_exclusions_and_strict`.

## 6. Реальные application workflows и выходы CLI

Источник можно передавать во все нижеследующие analysis-команды через общие `location --source local|zip|git [--ref ...] [--exclude ...] [--no-gitignore]`. `--json` отправляет результат stdout; логи stderr. Fatal input/config/output errors имеют typed code, возвращают 2. CLI не является async job server.

| User action | Command / application symbol | Output / exit semantics |
|---|---|---|
| Проверить источник | `repo inspect` (alias `repository inspect`) / `DiscoverRepository.execute` | RepositorySnapshot; 0 при успешном inventory, включая пустой/unsupported проект |
| Проверить parser coverage | `parse inspect [--strict]` / `ParseRepository.execute` | ParseRepositoryResult; invalid result → 3; fatal intake → 2 |
| Построить модель | `iam build [--strict] [--namespace ...] [--output ...]` / `BuildIAM.execute` | IAMBuildResult stdout / separate IAM export; invalid → 3, valid → 0 даже если incomplete |
| Валидировать target policy | `architecture validate SPEC` / `load_architecture_file` | valid flag, fingerprint, normalized specification, diagnostics []; invalid → 2; репозиторий не нужен |
| Проверить соответствие | `architecture check LOCATION --spec SPEC` / `application/check_architecture.py:CheckArchitecture.execute` | CONFORMANT 0 / NON_CONFORMANT 1 / INVALID 2 / INCOMPLETE 3 |
| Исследовать зависимости | `graph analyze [--spec ...] [--config ...] [--projection ...] [--relations ...]` / `application/analyze_graph.py:AnalyzeGraph.execute` | Invalid 2; findings 1; valid complete without findings 0; otherwise 3 |
| Вывести structural hypotheses | `architecture discover [--config ...]` / `application/discover_architecture.py:DiscoverArchitecture.execute` | Invalid 2 / complete 0 / incomplete 3. Нет обязательного target YAML; hypotheses не заменяют explicit rules |

AI/hybrid CLI entry points существуют в `cli.py:_parser/main`, но их семантика и provider contracts относятся к отдельной части аудита. Intake workflow не должен автоматически запускать provider или смешивать parser success с LLM quality. Benchmark/calibration команды намеренно не исследовались здесь, чтобы не смешивать production onboarding с research workstreams.

## 7. Подтверждённый UX-маршрут и будущие адаптеры

1. **Выбрать источник.** Local folder / local ZIP / public HTTPS Git; рядом явный режим запуска. Browser upload/connector — F. Ref показывать только Git. Не запрашивать credentials, поскольку текущий adapter их не поддерживает.
2. **Проверить intake.** Сначала source-type validation и materialization, затем inventory. Показывать revision (только Git), total/eligible files, detected vs parser-supported languages, ignored/generated/large/binary counts, exclusions и hash coverage. Не объединять их в «health score».
3. **Уточнить scope.** Повторяемые exclusions и respect-gitignore соответствуют CLI. Resource budgets — L; будущая форма может подготовить policy, но не притворяться существующим remote settings API. Объяснить отсутствие eligible files до запуска parsing.
4. **Выбрать задачу.** Build IAM / structural discovery / graph analysis / explicit conformance. Для conformance предварительно validate YAML, показать fingerprint и diagnostics; graph target projections могут требовать spec. Structural discovery не объявлять inferred policy принятой пользователем.
5. **Показать завершение этапов.** Inventory → parsing → extraction → resolution → selected analysis; текущий backend даёт синхронные use cases и логирование. Streaming progress/job cancellation/history — F. Не рисовать точный процент прогресса без измеримого denominator.
6. **Открыть результат с coverage.** Отдельно valid/complete/parser outcomes/resolution counts; source refs связаны с данным snapshot. IAM export и full build envelope различать по типу загрузки. Ошибка stage не должна выглядеть как zero findings или complete success.

**Минимальный будущий adapter — F:** request schema для source/policy/parser/extraction/task; validation без запуска анализа; invocation lifecycle с safe cleanup; typed result version/discriminator; serialization boundary; retained source/snapshot strategy для source viewer; explicit error mapping; отдельное решение persistence. Наличие этих требований не означает, что они реализованы в HTTP.

## 8. Ограничения доказательства аудита

Проверены существующие production symbols и текущий CLI dispatch, не выполнялась end-to-end загрузка нового проекта. Проверки UI, runtime availability git/tree-sitter, производительность, внешняя сеть и фактический запуск всех тестов относятся к дальнейшей валидации. Изученные test cases дают локальную трассируемость ожидаемого поведения; они не подтверждают непроверенные backend workflows, масштабирование или полноту language semantics.
