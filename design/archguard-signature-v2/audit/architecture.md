# P039 — архитектурный контур: capabilities, контракты, import gates

Дата: 17 октября 2026. База аудита: `49087a4`, ветка `design-lab/archguard-signature-v2`. Проверены публичный production-код и адресные публичные тесты. Providers, анализ репозиториев и исследовательские pipelines не запускались; `.env`, private cases, truth/human/adjudication/construction ledgers и research results не читались. Изменён только этот документ. Ссылки `path:symbol` относительны корню репозитория. Test reference означает проверенную существующую спецификацию в тесте, а не выполненный в этом аудите тест.

## 1. Главный вывод и классификация

Архитектурный контур значительно шире графа: явные ARCH001–005 rules, проверка YAML, path classification, graph projections/metrics/queries, structural discovery, dependency matrices, graph-guided context, semantic candidates и ARCH-only Hybrid. Большинство возможностей доступны через CLI и Python. **Analysis API отсутствует**: `src/archguard/api/app.py:create_app` регистрирует только `GET /health` и `GET /api/v1/system/info`.

| Класс | Значение в этом аудите |
| --- | --- |
| `API_EXPOSED` | Есть текущий HTTP route; только health/system info, не архитектурный анализ |
| `CLI_ONLY` | Есть пользовательская CLI-команда и внутренняя реализация; нет HTTP route |
| `REAL_INTERNAL_ONLY` | Есть вызываемая Python-функция/класс; самостоятельной CLI-команды и HTTP route нет |
| `RESEARCH_ONLY` | Исполняемый исследовательский workflow/артефакт; не product capability и не analysis API |
| `PROPOSED` | Требуемый browser adapter/workflow; отсутствует в backend |
| `UNAVAILABLE` | Нельзя обещать в текущем продукте на основании найденного кода |

Browser V2 может показывать проверенный **offline CLI result import** и synthetic demo с явным обозначением происхождения. Кнопки Run/Validate/Discover/Build context требуют отдельного integration gate. Локальная фильтрация уже импортированных данных не равна новому запуску backend. Наличие enum или dataclass не считается реализацией анализатора.

## 2. Callable inventory: rules, specification, conformance

| Возможность и callable | Класс | Реальный вход → выход | Ошибки / предел | Test reference | Journey / gate |
| --- | --- | --- | --- | --- | --- |
| YAML validation: `src/archguard/architecture/specification/loader.py:ArchitectureSpecLoader.load`; CLI `architecture validate SPEC --json` | `CLI_ONLY` | UTF-8 string/bytes → `ArchitectureSpecification`; CLI validation envelope | 131072 bytes, depth 32, 10000 nodes; aliases/anchors/merge/duplicate keys/custom tags forbidden; only v1.0, известные rule types и scopes | `tests/unit/test_architecture_specification.py:test_loader_rejects_malformed_or_unsafe_yaml`, `test_loader_resource_limits`, `test_version_and_unsupported_rule_have_typed_errors`; `tests/integration/test_architecture_cli.py:test_spec_validate_json_and_human` | Rules → import validated spec → scopes/rules. Browser YAML validation требует adapter, не просто JSON.parse |
| Canonical specification identity: `src/archguard/architecture/specification/models.py:ArchitectureSpecification.canonical_json`, `.fingerprint` | `REAL_INTERNAL_ONLY` | Typed spec → normalized JSON / SHA-256 | Rule IDs unique; references must exist; relative POSIX globs; target cycle projection requires declared scopes | `tests/unit/test_architecture_specification.py:test_hash_ignores_mapping_scope_and_rule_order`, `test_selector_rejects_noncanonical_paths` | Rules → exact configuration and fingerprint; UI не изменяет normalized spec молча |
| Classification: `src/archguard/architecture/classification/classifier.py:ArchitectureClassifier.classify`, `path_matches` | `REAL_INTERNAL_ONLY` | IAM + explicit spec → `ArchitectureClassification{nodes,diagnostics}` | Independent layer/module dimensions; overlap invalid; unclassified допустим; actual IAM не мутируется | `tests/integration/test_static_conformance.py:test_classification_inherits_includes_excludes_and_does_not_mutate`, `test_overlapping_classification_is_invalid_without_findings`; `tests/unit/test_static_rules.py:test_posix_glob_semantics` | Rules → scope coverage → exact file membership; не выдавать discovered label за target scope |
| ARCH001/002/004/005 evaluation: `src/archguard/architecture/rules/builtin.py:ForbiddenDependencyRule.violates`, `LayerDependencyRule.violates`, `ReverseDependencyRule.violates`, `ModuleBoundaryRule.violates` | `REAL_INTERNAL_ONLY` | Rule + source/target `NodeClassification` → bool | Только известные классифицированные scopes; ARCH002 отдельно контролирует same-layer; ARCH005 ignores same-module | `tests/unit/test_static_rules.py:test_four_explicit_rules`, `test_allow_deny_and_same_scope` | Rule detail → explain exact constraint and evaluated direction |
| Rule registry: `src/archguard/architecture/rules/registry.py:StaticRuleRegistry`, `create_static_rule_registry` | `REAL_INTERNAL_ONLY` | Rule implementations → lookup by `RuleType` | Duplicate/missing evaluator errors; четыре static builtin; ARCH003 отдельно в graph | `tests/unit/test_static_rules.py:test_registry_duplicate_missing_and_instance_isolation` | Каталог builtins; не обещать runtime custom-rule editor |
| Static conformance: `src/archguard/architecture/conformance/analyzer.py:StaticConformanceAnalyzer.analyze` | `REAL_INTERNAL_ONLY` | IAM + spec → `StaticConformanceResult` | Только proven resolved internal dependencies; aggregate rule + source file + target file; invalid IAM/classification suppresses findings; incomplete IAM не даёт complete conformance | `tests/integration/test_static_conformance.py:test_finding_contract_aggregation_locations_and_trace`, `test_invalid_provenance_never_becomes_findings`, `test_incomplete_iam_cannot_claim_conformance` | Findings → target rule → direct proof → file pair |
| Full check: `src/archguard/application/check_architecture.py:CheckArchitecture.execute`; CLI `architecture check LOCATION --spec SPEC` | `CLI_ONLY` | Repository snapshot/workspace + spec → static result либо `ArchitectureCheckResult` с graph conformance | ARCH003 включается только при enabled circular rule; severity исходного rule; confidence absent | `tests/integration/test_graph_pipeline.py:test_architecture_check_aggregates_static_and_graph_once`; `tests/integration/test_architecture_cli.py:test_check_exports_canonical_json_and_summary` | Rules → check result → confirmed findings; запуск из browser gated |

### Нормативные rules

`src/archguard/architecture/specification/models.py` определяет:

| ID / type | Реальная семантика input |
| --- | --- |
| ARCH001 `forbidden_dependency` | `from` и `to`: каждый selector содержит ровно один `layer` или `module` |
| ARCH002 `layer_dependency` | `from` layer; ровно `allow` или `deny`; `allow_same_layer` default true |
| ARCH003 `circular_dependency` | `projection`: component/file/package/layer/module; actual cycle proof и явное enabled правило |
| ARCH004 `reverse_dependency` | `expected:{from,to}` разных layers; нарушение — фактическое ребро `expected.to → expected.from` |
| ARCH005 `module_boundary` | `from` module; ровно `allow` или `deny`; внутренние same-module рёбра не нарушения |

Общие поля: `severity` default MEDIUM; `description:null`; `enabled:true`; `relations:[IMPORTS,INHERITS,IMPLEMENTS,CALLS,CREATES,USES]` с нормализацией порядка/уникальности. Один экземпляр каждого builtin ID; в v1 нет произвольной коллекции разных ARCH001 с тем же ID. Finding ID устойчив к сдвигу строк/новым callsites; два правила на одном ребре остаются двумя findings (`tests/integration/test_static_conformance.py:test_ids_survive_added_callsites_and_lines`, `test_same_edge_two_rules_remains_two_findings`).

## 3. Callable inventory: graph

| Возможность и callable | Класс | Вход → выход | Ошибки / предел | Test reference | Journey / gate |
| --- | --- | --- | --- | --- | --- |
| Actual projections: `src/archguard/architecture/graph/builder.py:GraphBuilder.build` | `REAL_INTERNAL_ONLY` | IAM + GraphAnalysisConfig + optional classification/spec fingerprint → `GraphBuildResult` | component/file/package/layer/module; PACKAGE только Java, ES excluded diagnostic; layer/module требуют valid classification; resource limit → invalid result | `tests/integration/test_graph_pipeline.py:test_all_five_projections_and_provenance`, `test_package_does_not_create_fake_ts_packages`, `test_target_projection_requires_valid_classification`, `test_graph_resource_limits_return_invalid_diagnostic` | Atlas → projection; projection switch по одному импортированному результату не пересчитывает backend |
| Graph orchestration: `src/archguard/architecture/graph/analyzer.py:GraphAnalyzer.analyze`; `src/archguard/application/analyze_graph.py:AnalyzeGraph.execute`; CLI `graph analyze LOCATION` | `CLI_ONLY` | IAM или repository + config + optional spec → `GraphAnalysisResult` | Invalid IAM; unproven/truncated provenance; all diagnostics affect completeness; target rule optional | `tests/integration/test_graph_cli.py:test_graph_export_config_overrides_and_determinism`, `test_target_projection_requires_spec_and_metric_skip_exit` | Atlas import → counts/projection/limitations → node/edge inspector |
| SCC: `src/archguard/architecture/graph/algorithms.py:strongly_connected_components` | `REAL_INTERNAL_ONLY` | `ArchitectureGraph` → sorted SCC records | Stable UUID per members/project/projection; no exhaustive cycle enumeration | `tests/unit/test_graph_engine.py:test_multiple_cycles_and_independent_sccs_have_bounded_proofs` | Atlas → cyclic groups and exact members |
| Cycle observations: `src/archguard/architecture/graph/algorithms.py:cycle_observations` | `REAL_INTERNAL_ONLY` | Graph + SCCs + max trace length → `CycleObservation[]` | One deterministic representative closed cycle per SCC with size >1; truncated → empty proof arrays; retained self-loop не создаёт size>1 cycle finding | `tests/unit/test_graph_engine.py:test_dense_scc_never_enumerates_all_simple_cycles`, `test_trace_limit_and_kept_self_loop_are_explicit` | Cycle → highlighted proof; без explicit rule это observation |
| ARCH003 conformance: `src/archguard/architecture/graph/conformance.py:GraphConformanceAnalyzer.analyze` | `REAL_INTERNAL_ONLY` | IAM + spec + optional graph config → `GraphConformanceResult` | Projection/relations from rule независимы от exploratory config; truncated closed proof не подтверждает violation | `tests/integration/test_graph_pipeline.py:test_arch003_requires_explicit_rule_and_has_grounded_closed_trace`, `test_cycle_trace_limit_cannot_claim_partial_finding`, `test_rule_projection_and_relations_are_independent_of_discovery_config` | Finding → explicit rule → closed source-grounded cycle |
| Metrics: `src/archguard/architecture/graph/metrics.py:calculate_metrics`, `pagerank` | `REAL_INTERNAL_ONLY` | Graph + SCCs + config → metrics, diagnostics, computed/skipped names | Exact unweighted directed betweenness budget; PageRank convergence diagnostic/null; isolated instability=null | `tests/unit/test_graph_engine.py:test_chain_exact_metrics_and_pagerank`, `test_isolated_metrics_are_undefined_instability_and_standard_singleton_centrality`, `test_large_chain_respects_expensive_metric_budget`, `test_pagerank_convergence_is_typed_and_not_fake_zero` | Module inspector → measurements; missing ≠ 0 |
| Directed shortest path: `src/archguard/architecture/graph/algorithms.py:shortest_path` | `REAL_INTERNAL_ONLY` | Graph + source/target UUID → `GraphPath` or null | Unknown node raises `GraphQueryError`; no path → null; deterministic tie ordering; unweighted BFS | `tests/unit/test_graph_engine.py:test_directed_shortest_path_ties_and_provenance` | Atlas → source/target → dependency path. Browser-local computation must be labelled local; internal API отсутствует |
| Neighbourhood: `src/archguard/architecture/graph/algorithms.py:neighbourhood` | `REAL_INTERNAL_ONLY` | Graph + node + hops + IN/OUT/BOTH + max_nodes → `GraphNeighbourhood` | Unknown node/negative hops/max_nodes<1 errors; deterministic truncation | `tests/unit/test_graph_engine.py:test_neighbourhood_directions_and_refs`, `test_neighbourhood_limits_are_deterministic` | Select node → incoming/outgoing/both; show truncation |
| Structural candidates: `src/archguard/architecture/graph/candidates.py:generate_candidates` | `REAL_INTERNAL_ONLY` | Graph + metrics + explicit threshold config → `GraphCandidate[]` | All thresholds default null; no severity/confidence; ARCH103 only component and size+coupling; missing betweenness/instability skips dependent candidate | `tests/unit/test_graph_engine.py:test_all_candidates_have_explicit_thresholds_and_null_confidence`, `test_god_candidate_requires_size_and_coupling`, `test_no_bottleneck_without_betweenness_and_undefined_instability_skipped` | Structural signals → metrics and threshold rationale, separate from violations |

Default graph budgets (`src/archguard/architecture/graph/config.py:GraphAnalysisConfig`): 10000 nodes, 100000 edges, exact betweenness ≤1000 nodes, cycle trace length 256, neighbourhood budget config 1000; PageRank alpha .85, tolerance 1e-10, max 200 iterations. The standalone `neighbourhood` callable accepts `max_nodes` separately; its default is also 1000. Defaults exclude externals and self-edges. Supported relations are IMPORTS/INHERITS/IMPLEMENTS/CALLS/CREATES/USES; CALLS is a filter, not a runtime call trace or a sixth projection.

Candidate catalog: ARCH101 Excessive Coupling = distinct neighbour union threshold; ARCH102 Dependency Hub = incoming distinct dependents; ARCH103 Potential God Component = member/method size plus coupling; ARCH104 Unstable Dependency = target instability minus source instability threshold; ARCH105 Architecture Bottleneck = directed betweenness plus optional neighbour support. Threshold boundary tolerance is 1e-12 (`tests/unit/test_graph_engine.py:test_configuration_identity_and_float_boundary_policy`).

## 4. Callable inventory: discovery

| Возможность и callable | Класс | Вход → выход | Ошибки / предел | Test reference | Journey / gate |
| --- | --- | --- | --- | --- | --- |
| Structural discovery: `src/archguard/architecture/discovery/analyzer.py:ArchitectureDiscoveryAnalyzer.analyze`; `src/archguard/application/discover_architecture.py:DiscoverArchitecture.execute`; CLI `architecture discover LOCATION` | `CLI_ONLY` | Same IAM + actual component graph + config → `ArchitectureDiscoveryResult` | Project/IAM/config mismatch raises ValueError; graph with target conformance/spec rejected; no generated target spec | `tests/integration/test_discovery_pipeline.py:test_single_iam_and_graph_execution`, `test_graph_candidate_refs_not_promoted_and_target_input_rejected`; `tests/integration/test_discovery_cli.py:test_no_target_spec_accepted` | Discovery tab/section → hypotheses + evidence, import standalone result |
| Role classification: `src/archguard/architecture/discovery/classification.py:StructuralRoleClassifier.classify` | `REAL_INTERNAL_ONLY` | Node/projected component + IAM/graph/config/metrics → `RoleHypothesis` | Framework/name/path/structural evidence precedence; generic framework hint insufficient; conflicting equal roles ambiguous | `tests/integration/test_discovery_pipeline.py:test_framework_names_without_arguments_and_generic_hints_are_conservative`, `test_equal_role_precedence_is_ambiguous` | Component → suggested role, strength, reasons, conflicting roles |
| Layer inference: `src/archguard/architecture/discovery/classification.py:LayerInferenceEngine.infer`, `.refine` | `REAL_INTERNAL_ONLY` | Role + IAM/config, optional graph → `LayerHypothesis` | Layer conflicts remain ambiguous; graph refinement adds support, не переопределяет primary role assignment | `tests/integration/test_discovery_pipeline.py:test_layer_conflict_preserves_strong_role_and_excludes_ambiguous_coverage`, `test_signals_can_be_disabled_and_graph_support_never_forces_roles` | Inferred layers → evidence; separate from explicit target layer |
| Module discovery: `src/archguard/architecture/discovery/modules.py:ModuleDiscovery.discover` | `REAL_INTERNAL_ONLY` | Discovered components + IAM/graph/config → module candidates/assignments/diagnostics | Actual Java namespace or ES source-directory seeds; no community detection; weak/ambiguous root may remain unassigned | `tests/integration/test_discovery_pipeline.py:test_module_feature_cohesion_shared_weak_and_matrices`, `test_java_common_prefix_and_configurable_size_and_roots`, `test_uncertain_roots_stay_weak_and_minimum_strengths_are_explicit` | Module hypothesis → members, cohesion, cross-module dependencies |
| Dependency matrices/topology: `src/archguard/architecture/discovery/models.py:DependencyMatrix`, `TopologySummary`; assembled by `ArchitectureDiscoveryAnalyzer.analyze` | `CLI_ONLY` | Discovery graph → layer/module matrices, rank lists, cycles, candidate IDs in discovery result | Matrix counts unique projected edges; coverage counts assignment, not accuracy/probability; null coverage when no components | `tests/integration/test_discovery_pipeline.py:test_exact_mixed_counts_matrices_and_no_cross_language_inference`, `test_exact_seven_of_ten_coverage_and_role_layer_distinction` | Discovery → matrix cell → graph_edge_ids; topology overview |

Config `src/archguard/architecture/discovery/config.py:ArchitectureDiscoveryConfig`: profile `structural-baseline-v1`; internal component graph, no externals/self-edges; min role/layer/module strength MODERATE; roots `["src"]`; min module components 2; max module depth 4; Java min package depth 3; topology rank limit 5. UNKNOWN и AMBIGUOUS — корректные результаты. Roles: CONTROLLER/SERVICE/REPOSITORY/DOMAIN_MODEL/DOMAIN_SERVICE/ADAPTER/GATEWAY/CLIENT/CONFIGURATION/UTILITY/UNKNOWN. Inferred layers: PRESENTATION/APPLICATION/DOMAIN/PERSISTENCE/INFRASTRUCTURE/UNKNOWN/AMBIGUOUS. Strength: STRONG/MODERATE/WEAK/AMBIGUOUS, без confidence.

## 5. Callable inventory: bounded context, semantic AI, provider

| Возможность и callable | Класс | Вход → выход | Ошибки / предел | Test reference | Journey / gate |
| --- | --- | --- | --- | --- | --- |
| Target resolution: `src/archguard/architecture/intelligence/selection.py:resolve_node`, `graph_owner` | `REAL_INTERNAL_ONLY` | UUID/name/qualified name + IAM; node + graph → unique internal node/owner | Exactly one match/owner required; project/package/external excluded | `tests/intelligence/test_context.py:test_invalid_target_and_token_budget_truthfulness` | Context → choose exact target; ambiguous search не выбирает случайно |
| Context builder: `src/archguard/architecture/intelligence/context.py:GraphGuidedContextBuilder.build`; CLI `ai context LOCATION --node NAME` | `CLI_ONLY` | Target + IAM + graph + SourceReader + config + optional spec/discovery → `ArchitectureContextPack`; default CLI emits only manifest | Upstream IAM/graph mismatch invalid; budgets/truncation and sanitized source errors; explicit internal `allow_invalid_iam_context` opt-in is not default UI mode | `tests/intelligence/test_context.py:test_k_hop_direction_and_unrelated_node`, `test_relation_filter_preserves_only_matching_proofs`, `test_hard_context_budgets`, `test_source_failures_are_sanitized_and_redaction_is_explicit` | Context inspector → selected nodes, fragment references, evidence, dropped counts; source only via explicit separate action |
| Source fragments: `src/archguard/architecture/intelligence/fragments.py:extract_fragments` | `REAL_INTERNAL_ONLY` | Selected nodes + SourceReader + budgets + optional redactor → bounded fragments/counts/diagnostics | Stream/line budgets; overlap dedup; redactor failure or line shifting cannot export wrong source coordinates | `tests/intelligence/test_context.py:test_large_file_method_window_is_streamed_and_bounded`, `test_file_and_overlapping_fragment_dedup`, `test_redactor_failure_or_line_shift_cannot_export_source_or_wrong_coordinates` | Available fragment vs manifest-only state; no invented snippet |
| Target selection: `src/archguard/architecture/intelligence/selection.py:SemanticAnalysisTargetSelector.select` | `REAL_INTERNAL_ONLY` | IAM/graph/discovery + target config → target list + skipped count | Explicit or bounded selected targets, not all nodes; include_ambiguous/controllers default true, unknown false | `tests/intelligence/test_semantics.py:test_target_selector_is_bounded_deterministic_and_not_all_nodes` | Context → explain why target selected, skipped targets |
| Request/response validation: `src/archguard/architecture/intelligence/prompt.py:build_request`, `request_metadata`, `validate_response` | `REAL_INTERNAL_ONLY` | Target + bounded context + budget; structured response → semantic candidate | Response schema/catalog/subject/evidence validation; unstructured location claims rejected; context treated as untrusted data | `tests/intelligence/test_semantics.py:test_invalid_schema_catalog_evidence_and_claims_are_isolated`, `test_prompt_injection_is_only_untrusted_data_in_actual_request` | Semantic candidate → supplied evidence refs and limitations |
| Semantic run/dry-run: `src/archguard/architecture/intelligence/analyzer.py:SemanticArchitectureAnalyzer.analyze`; `src/archguard/application/analyze_architecture_semantics.py:AnalyzeArchitectureSemantics.execute`; CLI `ai analyze` | `CLI_ONLY` | IAM/graph/workspace + AIAnalysisConfig + optional provider/spec/discovery + dry_run → `AIAnalysisResult` | DRY_RUN zero calls; unavailable provider/permission/structured output explicit; failures isolated; candidates are not Findings | `tests/intelligence/test_semantics.py:test_dry_run_and_remote_permissions_make_zero_calls`, `test_middle_provider_failure_keeps_other_results`; `tests/intelligence/test_application_cli.py:test_application_builds_iam_graph_discovery_once_for_multiple_targets` | Prepare context/dry-run offline; live analyze remains gated |
| OpenAI adapter: `src/archguard/infrastructure/llm_provider.py:OpenAIResponsesProvider.complete_structured`, `create_llm_provider` | `CLI_ONLY` | Explicit configured provider/model/secret + StructuredLLMRequest → StructuredLLMResponse | Only implemented live adapter OpenAI Responses; remote=true, `store:false`; no redirects; response cap 262144 bytes; token counting returns None; errors sanitized | `tests/intelligence/test_application_cli.py:test_configured_credentials_never_trigger_implicit_network`, `test_config_cannot_authorize_remote_upload_without_cli_opt_in`, `test_explicit_remote_cli_flag_reaches_real_adapter_with_stubbed_transport` | Provider setup is future backend gate; no browser secret entry/direct provider call in V2 |

Default context: GRAPH_GUIDED, 1 hop, BOTH; LOCAL_ONLY and EXPANDED_BASELINE alternatives. Limits: hops 0–8; max nodes 20/files 10/fragments 20; 4000 chars per fragment; 20000 total chars; 120 lines per fragment; 65536 bytes per line; 33554432 scanned bytes/file. Include spec/discovery/metrics/dependency paths defaults true. Token budget optional: actual provider must count input tokens; built-in OpenAI adapter returns None, so enforced token budget is **unmeasurable**, not estimated silently. AI defaults: max targets/calls/candidates 10; timeout 30s (config max 300s); max output tokens 2000; remote source false (`src/archguard/architecture/intelligence/models.py:ContextSelectionConfig`, `AIAnalysisConfig`, `AIAnalysisBudget`).

Semantic rules: ARCH201 Responsibility Mismatch; ARCH202 Business Logic in Controller; ARCH203 Infrastructure Leakage; ARCH204 Misplaced Component; ARCH205 Suspicious Cross-Layer Responsibility. Assessment states SUPPORTED / NOT_SUPPORTED / INSUFFICIENT_CONTEXT; supported requires nonempty evidence_refs. Fields include suggested role/layer, assumptions, limitations, recommendation; no confidence or severity (`src/archguard/architecture/intelligence/models.py:SemanticArchitectureAssessment`).

## 6. Callable inventory: Hybrid and research boundary

| Возможность и callable | Класс | Вход → выход | Ошибки / предел | Test reference | Journey / gate |
| --- | --- | --- | --- | --- | --- |
| Legacy batch facade: `src/archguard/architecture/hybrid/analyzer.py:HybridAnalyzer.decide` | `REAL_INTERNAL_ONLY` | IAM + ARCH-only `ArchitectureEvidenceBundle` → `ArchitectureDecision{analysis_id,findings}` | Existing deterministic Finding objects preserved; SEC rejected; no rescoring | `tests/unit/test_hybrid_contract.py:test_arch_only_bundle_and_decision_roundtrip`, `test_sec_evidence_never_enters_hybrid` | Compatibility boundary, not new scoring feature |
| Case-level composition: `src/archguard/architecture/hybrid/analyzer.py:HybridAnalyzer.analyze` | `REAL_INTERNAL_ONLY` | IAM + optional static/graph/discovery/AI/spec/graph_conformance + config → `HybridAnalysisResult` | Same IAM/spec/config identities; component graph required; enabled explicit proof/severity preserved; candidate budget max 100000/default 1000 never removes deterministic refs | `tests/hybrid/test_input_guards.py:test_group_projection_cannot_masquerade_as_component_metrics`; `tests/hybrid/test_decisions.py:test_stale_upstream_is_rejected`, `test_candidate_budget_retains_deterministic_refs` | Evidence review → cases/channels/decision, separate from root Findings |
| Evidence assembly/alignment: `src/archguard/architecture/hybrid/assembler.py:HybridEvidenceAssembler.assemble`; `src/archguard/architecture/hybrid/alignment.py` | `REAL_INTERNAL_ONLY` | Identity-bound case + upstream signals → evidence bundle and versioned alignments | Supporting/contradicting/neutral/missing/not-applicable are distinct; unrelated metrics not fabricated support; missing quality stays null | `tests/hybrid/test_decisions.py:test_high_pagerank_does_not_support_controller_logic`, `test_skipped_metric_stays_missing`; `tests/hybrid/test_input_guards.py:test_missing_iam_quality_is_not_invented` | Compare channels → explanation and actual refs |
| Deterministic policy: `src/archguard/architecture/hybrid/policies.py:DeterministicPrecedencePolicy.decide` | `REAL_INTERNAL_ONLY` | Case + evidence + versioned feature vector → HybridDecision | Static proof → CONFIRMED_DETERMINISTIC; graph/meaningful semantic signal → REVIEW_REQUIRED; otherwise INSUFFICIENT_EVIDENCE; AI cannot suppress proof | `tests/hybrid/test_decisions.py:test_ai_never_suppresses_static`, `test_explicit_arch003_survives_negative_ai`, `test_policy_cannot_suppress_deterministic_finding`, `test_numeric_confidence_is_forbidden` | Proof-first inspector; no weighted total score |
| Offline pipeline: `src/archguard/application/analyze_architecture_hybrid.py:AnalyzeArchitectureHybrid.prepare`, `.execute_prepared`, `.execute`; CLI `hybrid analyze` | `CLI_ONLY` | Repository/config/spec + saved AI or internal offline provider → Hybrid result | Remote provider rejected; saved manifests reconstructed and fingerprints compared; CLI never loads provider | `tests/hybrid/test_application_cli.py:test_full_pipeline_each_stage_once`, `test_remote_provider_is_not_run`, `test_cli_does_not_load_provider`, `test_saved_ai_cli_checks_context` | Import offline Hybrid → original proof + case evidence; recomposition is separate adapter gate |
| Source-free saved AI loader: `src/archguard/infrastructure/hybrid_configuration.py:load_hybrid_ai_result` | `CLI_ONLY` | File ≤8388608 bytes → validated AIAnalysisResult | Duplicate keys/raw source/prompt/credentials forbidden; config cap 131072 bytes; sanitized `INVALID_HYBRID_ARTIFACT` | `tests/hybrid/test_application_cli.py:test_saved_ai_loader_rejects_raw_prompt_and_oversize`, `test_config_rejection_is_bounded_and_sanitized` | Saved AI input import must preserve this validation boundary |
| Frozen structural scoring: `src/archguard/architecture/hybrid/calibration.py:CalibratedStructuralHybridPolicy.decide`; CLI `--structural-policy` | `CLI_ONLY` | Frozen approved structural artifact + ARCH101–105 graph case → structural state + model_score/artifact fingerprint | Static bypass; ARCH101–105 only; AI excluded `FULL_HYBRID_NOT_READY`; score is not confidence; artifact provenance is research/engineering seed | `tests/benchmark/test_structural_calibration.py:test_runtime_signals_static_bypass_and_semantic_rejection` (public test symbol only) | If imported, label structural policy and provenance; do not offer general AI-confidence meter |
| Calibration train/select/freeze/evaluate/baseline: `src/archguard/calibration_cli.py:calibration_arguments`, `execute_calibration` | `RESEARCH_ONLY` | Explicit train/validation/test/manifests/artifacts → offline research artifacts | Data/splits/labels not product UI inputs; no research datasets accessed in this audit | `tests/benchmark/test_structural_calibration.py:test_cli_stages_and_guards` (symbol only) | Hidden from product workflow; never import research evidence as production run |
| Generic weighted/logistic artifact contract: `src/archguard/architecture/hybrid/artifacts.py:CalibratedPolicyArtifact` | `REAL_INTERNAL_ONLY` | Metadata/coefficient schema with compatibility checks | A metadata contract alone does not imply a general executable full-Hybrid scoring system | `src/archguard/architecture/hybrid/artifacts.py:require_compatible_schema` is implementation reference; no dedicated test verified here | No UI control based only on existence of this type |

`HybridDecision` enforces: only deterministic decisions hold confirmed Finding IDs and severity; nonconfirmed severity=null; uncalibrated confidence=null; structural states require paired model_score/model_artifact_fingerprint and forbid confidence. State enums also contain SUPPORTED_BY_CALIBRATED_POLICY/REJECTED_BY_CALIBRATED_POLICY, but the reviewed executable structural policy emits STRUCTURAL_SIGNAL_SUPPORTED/STRUCTURAL_SIGNAL_NOT_SUPPORTED. Enum membership is not evidence of another ready scoring path. Full live remote Hybrid + semantic calibrated confidence = `UNAVAILABLE`.

## 7. Stable JSON wire shapes for offline import

Это реальные поля сериализуемых моделей, не выдуманный REST envelope. Нотация ниже: `ID` = non-nil UUID string, `Hash` = SHA-256 string где модель требует digest, `JsonObject` = JSON object, `T[]` = JSON array. Поля с `|null` выводятся как null; tuple превращается в array. Serializer не использует exclude_none. Вложенные типы определены указанными source models; не следует подменять их произвольным `{}`. `DomainModel` запрещает extra fields и non-finite floats (`src/archguard/core/model/base.py:DomainModel`).

### 7.1 Specification validation и static check

```ts
type SpecValidation = {
  is_valid: true; fingerprint: Hash;
  specification: ArchitectureSpecification; diagnostics: [];
};
type ArchitectureSpecification = {
  version: "1.0";
  architecture: {layers: ArchitectureScope[]; modules: ArchitectureScope[]};
  rules: RuleSpecification[];
};
type ArchitectureScope = {
  name: string; include: string[]; exclude: string[]; description: string|null;
};
type StaticConformanceResult = {
  result_schema_version: "1.0";
  status: "CONFORMANT"|"NON_CONFORMANT"|"INCOMPLETE"|"INVALID";
  is_valid: boolean; is_complete: boolean;
  classification: {nodes: NodeClassification[]; diagnostics: ConformanceDiagnostic[]};
  statistics: StaticConformanceStatistics; findings: Finding[];
  diagnostics: ConformanceDiagnostic[];
  reproducibility: ConformanceReproducibility; specification_summary: JsonObject;
};
type NodeClassification = {
  node_id: ID; file_id: ID; file_path: string; layer: string|null; module: string|null;
  layer_candidates: string[]; module_candidates: string[];
};
type ArchitectureCheckResult = {
  result_schema_version: "1.0"; analysis_kind: "architecture_check";
  status: StaticConformanceResult["status"]; is_valid: boolean; is_complete: boolean;
  static_result: StaticConformanceResult; graph_result: GraphConformanceResult;
  findings: Finding[]; statistics: StaticConformanceStatistics;
  reproducibility: ConformanceReproducibility;
};
```

`NodeClassification.status` и `ArchitectureClassification.is_valid` — Python properties, **не JSON fields**. Static result не имеет `analysis_kind`, не содержит полного graph и не равен composite check. Enabled ARCH003 приводит к composite shape даже без finding. Sources: `src/archguard/architecture/conformance/models.py:StaticConformanceResult`; `src/archguard/architecture/check_result.py:ArchitectureCheckResult`; `src/archguard/cli.py:_serialize_architecture`.

`StaticConformanceStatistics` exact keys: `iam_nodes_total, iam_edges_total, nodes_considered, nodes_classified, nodes_unclassified, ambiguous_nodes, edges_considered, edges_ignored, rules_enabled, rules_evaluated, findings_total, findings_by_rule, findings_by_severity, nodes_by_layer, nodes_by_module`. Last four are count maps, others nonnegative integers. `ConformanceReproducibility` exact keys: `project_id, snapshot_id, snapshot_fingerprint, iam_schema_version, iam_fingerprint, architecture_spec_version, architecture_spec_fingerprint, analyzer_version, rule_engine_version, classifier_version, configuration`; snapshot fields nullable; configuration is `{require_complete_iam:true}`.

### 7.2 Graph result и proof

```ts
type GraphAnalysisResult = {
  result_schema_version: "1.0"; status: "COMPLETE"|"INCOMPLETE"|"INVALID";
  is_valid: boolean; is_complete: boolean; graph: ArchitectureGraph;
  projection_statistics: ProjectionStatistics; statistics: GraphStatistics;
  metrics: GraphNodeMetrics[]; sccs: StronglyConnectedComponent[];
  cycles: CycleObservation[]; findings: Finding[]; candidates: GraphCandidate[];
  conformance: GraphConformanceResult|null; diagnostics: GraphDiagnostic[];
  reproducibility: GraphReproducibility;
};
type ArchitectureGraph = {
  graph_schema_version: "1.0"; project_id: ID;
  projection: {
    projection: "component"|"file"|"package"|"layer"|"module";
    included_relations: string[]; include_external: boolean; include_self_edges: boolean;
  };
  nodes: GraphNode[]; edges: GraphEdge[];
};
type GraphNode = {
  id: ID; label: string; kind: string|null; iam_node_ids: ID[];
  locations: SourceLocation[]; member_count: number; method_count: number;
};
type GraphEdge = {
  id: ID; source_id: ID; target_id: ID; relation_kinds: string[]; proofs: DependencyProof[];
};
type DependencyProof = {
  iam_edge_id: ID; source_node_id: ID; target_node_id: ID; relation: string;
  locations: SourceLocation[]; provenance: JsonObject[];
  occurrences: number; provenance_truncated: number;
};
type SourceLocation = {
  file_path: string; start_line: number; start_column: number;
  end_line: number|null; end_column: number|null;
};
type StronglyConnectedComponent = {
  id: ID; members: ID[]; internal_edge_count: number; size: number;
};
type CycleObservation = {
  scc_id: ID; members: ID[]; node_ids: ID[]; edge_ids: ID[]; truncated: boolean;
};
type GraphConformanceResult = {
  status: StaticConformanceResult["status"]; is_valid: boolean; is_complete: boolean;
  rule_enabled: boolean; graph: ArchitectureGraph|null;
  sccs: StronglyConnectedComponent[]; cycles: CycleObservation[]; findings: Finding[];
  diagnostics: GraphDiagnostic[]; reproducibility: JsonObject;
};
```

Sources: `src/archguard/architecture/graph/result.py:GraphAnalysisResult`; `src/archguard/architecture/graph/models.py`; `src/archguard/architecture/graph/conformance.py:GraphConformanceResult`; `src/archguard/core/locations/__init__.py:SourceLocation`. Coordinates one-based. Proof arrays nonempty; `occurrences = provenance.length + provenance_truncated`; locations count equals retained provenance count. Graph endpoints exist; IDs unique; graph pairs unique; relation_kinds sorted/unique and equal proof relations. Truncated cycle has empty node_ids/edge_ids. Otherwise cycle closed and edges count = nodes count−1.

`GraphNodeMetrics` exact keys: `node_id, in_degree_edges, out_degree_edges, unique_in_neighbors, unique_out_neighbors, afferent_coupling, efferent_coupling, total_unique_neighbors, instability, in_degree_centrality, out_degree_centrality, betweenness_centrality, pagerank, scc_size, is_cyclic`. Instability/betweenness/pagerank nullable; numeric values не confidence.

`GraphCandidate` exact keys: `candidate_id, rule_id, title, subject_node_id, subject_edge_id, projection, metrics, thresholds, reason, source_locations, not_calibrated, confidence, evidence, metadata`. Rule ARCH101–105; subject IDs nullable; `not_calibrated:true`, `confidence:null`; no severity. `GraphDiagnostic={code,message,subject_id:null|ID}`.

`ProjectionStatistics` keys: `iam_nodes_input, iam_edges_input, graph_nodes, graph_edges, self_edges_removed, external_nodes_excluded, unmapped_nodes, unclassified_nodes_excluded, filtered_edges, unproven_edges`. `GraphStatistics` keys: `scc_count, cyclic_scc_count, cycle_observation_count, cycle_findings, candidate_count_by_rule, metric_node_count, metrics_computed, metrics_skipped`.

`GraphReproducibility` keys: `project_id, snapshot_fingerprint, iam_schema_version, iam_fingerprint, graph_engine_version, networkx_version, configuration, configuration_fingerprint, projection_fingerprint, architecture_spec_fingerprint, canonical_float_decimal_places`. Snapshot/spec fingerprints nullable; decimals literal 12. `configuration` contains complete GraphAnalysisConfig, not only projection.

### 7.3 Discovery result

```ts
type ArchitectureDiscoveryResult = {
  result_schema_version: "1.0"; analysis_kind: "architecture_discovery";
  status: "COMPLETE"|"INCOMPLETE"|"INVALID"; is_valid: boolean; is_complete: boolean;
  discovered: {
    components: DiscoveredComponent[]; layer_groups: LayerGroup[];
    module_candidates: ModuleCandidate[];
    unclassified_components: ID[]; ambiguous_components: ID[];
    module_unassigned_components: ID[];
    layer_dependency_matrix: DependencyMatrix; module_dependency_matrix: DependencyMatrix;
    topology: TopologySummary;
  };
  graph: GraphAnalysisResult; diagnostics: GraphDiagnostic[];
  statistics: DiscoveryStatistics; reproducibility: DiscoveryReproducibility;
};
type DiscoveredComponent = {
  id: ID; iam_node_id: ID; name: string; qualified_name: string; language: string;
  file_path: string; location: SourceLocation|null;
  role: RoleHypothesis; layer: LayerHypothesis; module_id: ID|null;
};
type RoleHypothesis = {
  id: ID; subject_id: ID; role: string; strength: string;
  candidate_roles: string[]; conflicting_roles: string[];
  evidence: DiscoveryEvidence[]; explanation: string;
};
type LayerHypothesis = {
  id: ID; subject_id: ID; label: string; strength: string; candidate_layers: string[];
  role_hypothesis_id: ID; evidence: DiscoveryEvidence[]; explanation: string;
};
type DependencyMatrix = {
  labels: string[]; cells: {
    source: string; target: string; unique_projected_edges: number;
    internal: boolean; graph_edge_ids: ID[];
  }[]; excluded_noncomponent_edges: number;
};
```

Source: `src/archguard/architecture/discovery/models.py`. Important path: **`result.graph.graph.nodes`**, not `result.graph.nodes`. This artifact is the richest single offline input for Atlas + Discovery: actual graph nested together with hypotheses. `reproducibility.not_calibrated=true`; role/layer coverage are nullable assignment ratios. No target spec/Finding generation from inferred roles.

### 7.4 Context manifest и explicit source pack

```ts
type ContextManifest = {
  context_schema_version: "1.0"; target_node_id: ID; configuration: ContextSelectionConfig;
  selected_nodes: {node_id: ID; distance: number|null; reason: string}[];
  fragments: FragmentReference[];
  evidence: {evidence_id: string; kind: "DEPENDENCY"|"TARGET_CONSTRAINT"|
    "DISCOVERY_HYPOTHESIS"|"GRAPH_METRIC"; subject_node_ids: ID[]; data: JsonObject}[];
  context_fingerprint: Hash; context_chars: number; files: number; truncated: boolean;
  dropped_nodes: number; dropped_files: number; dropped_fragments: number; dropped_evidence: number;
  redactor_id: string|null; diagnostics: ContextDiagnostic[];
};
type FragmentReference = {
  evidence_id: string; relative_path: string; start_line: number; end_line: number;
  node_ids: ID[]; language: string; purpose: string; truncated: boolean;
  content_hash: Hash; chars: number;
};
type ArchitectureContextPack = {
  manifest: ContextManifest; fragments: {reference: FragmentReference; text: string}[];
};
type ContextDiagnostic = {code: string; message: string; subject_node_id: ID|null};
```

Source: `src/archguard/architecture/intelligence/models.py:ContextManifest`, `ArchitectureContextPack`; `src/archguard/ai_cli.py:execute_ai`. `ai context --json --output` emits **manifest**, `--show-source` changes shape to **pack** and exposes source text. Safe default browser importer should reject pack/raw source rather than silently ingest it. Manifest has **no project_id, snapshot_fingerprint or iam_fingerprint**. Standalone manifest can show context evidence, but matching node UUID alone cannot prove a cross-artifact snapshot association. A future trusted import bundle needs explicit identity validation; no invented fields should be inserted into engine artifacts.

### 7.5 AI analysis и Hybrid

```ts
type AIAnalysisResult = {
  result_schema_version: "1.0";
  status: "DRY_RUN"|"COMPLETE"|"PARTIAL"|"UNAVAILABLE"|"INCOMPLETE"|"INVALID";
  targets: {node_id: ID; candidate_rule_id: string; reason: string}[];
  manifests: ContextManifest[]; request_metadata: JsonObject[];
  candidates: SemanticArchitectureCandidate[]; invocations: AIInvocation[];
  diagnostics: ContextDiagnostic[]; calls: number; skipped_targets: number;
};
type SemanticArchitectureCandidate = {
  candidate_id: ID; assessment: {
    candidate_rule_id: string; decision: "SUPPORTED"|"NOT_SUPPORTED"|"INSUFFICIENT_CONTEXT";
    subject_node_ids: ID[]; short_reason: string; evidence_refs: string[];
    suggested_role: string|null; suggested_layer: string|null;
    assumptions: string[]; limitations: string[]; recommendation: string|null;
  };
  context_fingerprint: Hash; strategy: "LOCAL_ONLY"|"GRAPH_GUIDED"|"EXPANDED_BASELINE";
  provider_id: string; model_id: string; prompt_version: string; schema_version: string;
  not_calibrated: true;
};
type AIInvocation = {
  invocation_id: ID; target: AIAnalysisResult["targets"][number];
  provider_id: string; model_id: string; provider_request_id: string|null;
  usage: {input_tokens: number|null; output_tokens: number|null;
    total_tokens: number|null; provider_reported_cost: number|null};
  latency_seconds: number; generation_parameters: JsonObject;
  diagnostic: ContextDiagnostic|null;
};
type HybridAnalysisResult = {
  result_schema_version: "hybrid-analysis-v1";
  cases: HybridCase[]; evidence_bundles: HybridEvidenceBundle[];
  feature_schema: HybridFeatureSchema; features: HybridFeatureVector[];
  decisions: HybridDecision[]; confirmed_finding_ids: ID[]; review_case_ids: ID[];
  diagnostics: string[]; statistics: HybridStatistics; reproducibility: HybridReproducibility;
};
type HybridCase = {
  case_id: ID; case_type: "DETERMINISTIC_CONFORMANCE"|"GRAPH_STRUCTURAL"|"SEMANTIC"|"COMPOSITE";
  primary_subject_ids: ID[]; related_subject_ids: ID[];
  subject_pairs: {source_id: ID; target_id: ID}[];
  origin: "STATIC"|"GRAPH_CONFORMANCE"|"GRAPH"|"AI"|"CALLER";
  rule_id: string; anchor_ids: ID[]; scope: string; bundle_id: ID;
};
type HybridDecision = {
  decision_id: ID; case_id: ID; state: string; policy: HybridPolicyMetadata;
  calibration_status: "UNCALIBRATED"|"CALIBRATED"|"DETERMINISTIC";
  feature_fingerprint: Hash; evidence_fingerprint: Hash; reason_codes: string[];
  supporting_refs: string[]; contradicting_refs: string[]; missing_refs: string[];
  confirmed_finding_ids: ID[]; severity: string|null; confidence: Confidence|null;
  model_score: number|null; model_artifact_fingerprint: Hash|null;
};
```

Sources: `src/archguard/architecture/intelligence/models.py:AIAnalysisResult`; `src/archguard/architecture/hybrid/models.py:HybridAnalysisResult`, `HybridDecision`. Hybrid contains **references to confirmed Finding IDs, not a root findings array** and not a full graph. Evidence bundle exact channel keys: `bundle_id, static, graph, graph_measurements, ai, discovery, context, completeness, alignments`. Each case has exactly one ordered decision and feature vector and its corresponding bundle. Feature/evidence hashes and original proof invariants are validated by `HybridAnalysisResult.preserve_proofs`.

AI `invocations` contain operational request IDs/latency; live runs are not byte-identical simply because serialize_ai is canonical JSON. Hybrid canonical result intentionally omits invocation IDs, latency, provider request IDs, raw source/prompt/response and semantic prose (`tests/hybrid/test_decisions.py:test_canonical_result_is_deterministic_and_source_free`). Same fixed input → same Hybrid artifact; new live LLM result is outside that guarantee.

### 7.6 IAM serialization caveat

`iam build --output FILE` writes `ArchitectureModel` via `src/archguard/iam_building/serialization.py:serialize_iam`:

```ts
type ArchitectureModel = {
  iam_schema_version: "1.0"; project: Project; modules: Module[]; packages: Package[];
  source_files: SourceFile[]; symbols: Symbol[]; nodes: ArchitectureNode[];
  edges: ArchitectureEdge[]; metadata: JsonObject;
};
```

But `iam build --json` stdout is `IAMBuildResult` with exact root keys `iam, config, parsing, facts, resolutions, statistics, diagnostics, is_valid, is_complete, builder_version, resolver_version`. It is **not identical to --output**. Prefer canonical `--output` artifact for a dedicated IAM importer; do not treat arbitrary fact/resolution payload as the smaller graph-result shape (`src/archguard/cli.py:main`; `src/archguard/iam_building/models.py:IAMBuildResult`).

### 7.7 Serializer behaviour, commands and errors

| Artifact | Serializer | JSON properties | CLI exit contract |
| --- | --- | --- | --- |
| Static conformance | `conformance/analyzer.py:serialize_conformance` | Sorted keys, UTF-8, indent=2, newline | 0 conformant / 1 nonconformant / 2 invalid / 3 incomplete |
| Combined architecture check | `cli.py:_serialize_architecture` | Same formatting, validated composite model | Same as above |
| Graph | `graph/analyzer.py:serialize_graph_result` | Computed metric/candidate metric floats rounded to 12 decimals; config precision preserved; sorted/indent/newline | 2 invalid, else 1 if findings, else 0 complete / 3 incomplete |
| Discovery | `discovery/analyzer.py:serialize_discovery` | Nested graph serializer; coverage/cohesion/betweenness summary rounded 12; config preserved | 2 invalid / 0 complete / 3 incomplete |
| Context/AI | `intelligence/models.py:serialize_ai` | Sorted compact JSON, no NaN, newline; source pack only explicit | ai analyze: 0 DRY_RUN/COMPLETE; 2 INVALID; other result statuses 3 |
| Hybrid | `hybrid/serialization.py:serialize_hybrid` | Sorted compact JSON, floats normalized to 12, no NaN, newline | CLI 2 if diagnostics contain exact INVALID/AI_INVALID, else 0; do not infer complete from exit 0 |

Paths in serializer column are within `src/archguard/architecture/` except `cli.py` in `src/archguard/`. Canonical-byte test refs: `tests/unit/test_graph_serialization.py:test_canonical_precision_preserves_algorithm_configuration`; `tests/integration/test_discovery_cli.py:test_export_bytes_match_stdout_and_repeat_without_leaking_source`; `tests/intelligence/test_application_cli.py:test_cli_context_source_is_explicit_and_output_canonical`; `tests/hybrid/test_application_cli.py:test_offline_pipeline_bytes_across_fresh_ai_runs`.

Safe offline command patterns for **user-approved local repositories** (documented, not executed by this audit):

```sh
archguard architecture validate architecture.yaml --json
archguard architecture check REPOSITORY --spec architecture.yaml --json --output check.json
archguard graph analyze REPOSITORY --json --output graph.json
archguard architecture discover REPOSITORY --json --output discovery.json
archguard ai context REPOSITORY --node QUALIFIED_NAME --json --output context.json
archguard ai analyze REPOSITORY --target QUALIFIED_NAME --dry-run --json --output ai-dry-run.json
archguard hybrid analyze REPOSITORY --without-ai --json --output hybrid.json
```

Optional graph/config/spec flags change recorded result/projection. `--relations CALLS` filters actual resolved call dependencies. `hybrid --ai-result SAVED_AI_JSON` validates source-free artifact and reconstructs current context; this is not a generic merge of unrelated JSON files. `--without-ai` is explicit offline intent, although no saved AI is already an offline default. Never add `--allow-remote-ai` or `--show-source` to an offline import help action implicitly.

`--json` input failures are emitted to **stderr** as `{error:{code,message}}`; architecture spec errors additionally contain `line` and `column` (nullable). Exit 2; these are error envelopes, not analysis results. `architecture validate` success has no result_schema_version. Canonical result and human summary/log text must not be concatenated into one import file. Sources: `src/archguard/cli.py:main`; `tests/integration/test_architecture_cli.py:test_cli_input_errors_are_typed_and_do_not_leak`; `test_invalid_validate_exit_two`.

## 8. Browser import acceptance and integration gates

The following is `PROPOSED`, not existing backend behaviour:

1. Accept a local JSON file as inert data; no network/provider invocation, no repository execution, no filesystem paths followed. Show artifact type, imported filename and explicit offline provenance. Set independent browser byte/depth/node budgets and report them; do not call them backend limits.
2. Dispatch **before** generic graph detection: `analysis_kind=architecture_discovery`; `analysis_kind=architecture_check`; `result_schema_version=hybrid-analysis-v1`; `context_schema_version=1.0`; typed graph root (`graph.graph_schema_version`, metrics/sccs); static root (classification/specification_summary); AI root (targets/manifests/request_metadata); spec validation root. Shared `result_schema_version:"1.0"` alone is ambiguous. Unknown versions, conflicting roots and `{error:...}` get a readable rejection.
3. Use per-kind schema validation, exact enum sets, UUID/reference/count/proof checks, and reject duplicate keys/non-finite numbers. `JSON.parse` alone does not detect duplicate keys. Render strings as text; do not accept imported HTML or infer source links to arbitrary URLs.
4. Default accept source-free result envelopes. Reject raw pack `{manifest,fragments:[{text:...}]}`. For saved AI compatibility, mirror the existing forbidden keys recursively: `source_fragments,text,untrusted_context,system_instructions,raw_prompt,raw_response,messages,api_key,authorization` (case-insensitive), plus byte cap. General result importer may use stricter documented policy; it must not claim the backend applies this guard to every artifact family.
5. Single discovery artifact supports both graph and hypotheses without invented joins. Static check, Hybrid and context artifacts can be shown standalone. Cross-artifact joins require matching project/IAM/spec/config fingerprints where available; context manifest alone lacks project/IAM identity. Unmatched references remain unmatched. Imported fingerprints indicate recorded provenance, not cryptographic authenticity or proof the source is unchanged.
6. Preserve raw numeric meaning: null ≠ zero, candidate ≠ violation, severity ≠ confidence, discovery coverage ≠ accuracy, source dependency path ≠ execution trace. INVALID may be displayed as diagnostics but cannot claim reliable findings. INCOMPLETE can still contain valid findings; zero findings is not complete conformance.
7. Read-only imported-result views may filter/search/select/highlight already present evidence. Reprojection, validation against a new YAML, discovery recomputation, source fetch, context rebuilding and Hybrid recomposition require a real adapter and available IAM/source. Gate each unavailable action with its exact prerequisite.

| Browser capability | Honest V2 path | Gate / unavailable backend |
| --- | --- | --- |
| Atlas + metrics + cycles | Synthetic demo or imported Graph/Discovery result | Live analysis/projection recomputation requires analysis/result adapter |
| Rules + explicit scopes | Validated specification/check import; catalog backed by real builtins | Running YAML loader/check requires service/desktop adapter |
| Discovery + matrix + uncertainty | Imported ArchitectureDiscoveryResult | Re-infer from user project requires IAM/graph/source pipeline |
| Context + evidence budget | Imported manifest/AI dry-run result, no raw source | Build context/source preview requires SourceReader adapter and repository identity |
| Hybrid review | Imported HybridAnalysisResult; refs retain missing state | Full graph/source join and recomposition need compatible artifacts/adapter |
| System connection | `/health`, `/api/v1/system/info` only | Does not unlock analyses, jobs/history or source access |
| Run history, job progress, persistence, source endpoints, collaborative review | `PROPOSED` | No current production API found |
| Full live remote Hybrid, calibrated semantic confidence, auto-generated enforced target architecture | `UNAVAILABLE` | Must not appear as working capabilities |

## 9. Audit validation and remaining uncertainty

Source and test symbols above establish available entry points and expected behaviour. No provider, full test suite or research job was executed; no accuracy/performance benchmark claim is made. JSON field inventories were checked against typed models and actual CLI dispatch/serializers. Exact engine model validation remains the authority for nested constraints; the compact TypeScript notation is a frontend mapping aid, not a replacement schema.

Outstanding engineering decisions: import-kind schemas and browser resource limits; whether imported canonical JSON stays local or is persisted; a trustworthy cross-artifact bundle identity; source access authorization/revision binding; service API for use cases and query budgets; dedicated product coverage model. These do not block a truthful offline V2, but they block advertising live analysis integration.
