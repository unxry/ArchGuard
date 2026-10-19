# ПРИЛОЖЕНИЕ А Каталог архитектурных правил и примеры DSL

## А.1 Полнота каталога и привязка к реализации

Приложение уточняет технические основания пятнадцати правил, рассматриваемых в главе 2. Сведения перенесены из зафиксированного rule-coverage.json научного ядра. «Научный владелец» означает специализированный канал, отвечающий за соответствующую область в эксперименте. LLM в общей оценке также получает вопросы других семейств, но наличие такого вопроса не делает все каналы равноспособными [@archguard].

Ни графовый threshold-кандидат, ни семантическое SUPPORTED не объявляется детерминированным доказательством только по имени правила. Для ARCH001/002/004/005 требуется исходное подтверждённое отношение и явный контракт. Для ARCH003 необходимы включённое правило и замкнутый графовый proof. Графовые ARCH101–105 используют структурный механизм и отдельно оценённую модель. Семантические ARCH201–205 опираются на заданный контекст и evidence refs.

Данные приведены в [таблица:append_a_rule_binding].

<!-- TABLE:append_a_rule_binding | Привязка правил к исполнителю и регрессионному тесту -->
| Правило | Владелец | Исполняемый символ | Проверяемый символ |
| --- | --- | --- | --- |
| ARCH001 ForbiddenDependency | STATIC | ForbiddenDependencyRule | test_four_explicit_rules |
| ARCH002 LayerViolation | STATIC | LayerDependencyRule | test_four_explicit_rules |
| ARCH003 CircularDependency | GRAPH | cyclic_finding | test_cycle_metrics_and_canonical_closed_proof |
| ARCH004 ReverseDependency | STATIC | ReverseDependencyRule | test_four_explicit_rules |
| ARCH005 ModuleBoundaryViolation | STATIC | ModuleBoundaryRule | test_four_explicit_rules |
| ARCH101 ExcessiveCoupling | GRAPH | evidence_record | test_all_candidates_have_explicit_thresholds_and_null_confidence |
| ARCH102 DependencyHub | GRAPH | evidence_record | test_all_candidates_have_explicit_thresholds_and_null_confidence |
| ARCH103 PotentialGodComponent | GRAPH | evidence_record | test_all_candidates_have_explicit_thresholds_and_null_confidence |
| ARCH104 UnstableDependency | GRAPH | evidence_record | test_all_candidates_have_explicit_thresholds_and_null_confidence |
| ARCH105 ArchitectureBottleneck | GRAPH | evidence_record | test_all_candidates_have_explicit_thresholds_and_null_confidence |
| ARCH201 ResponsibilityMismatch | LLM | SemanticArchitectureAnalyzer | test_all_semantic_rules_and_decisions_are_candidates |
| ARCH202 BusinessLogicInController | LLM | SemanticArchitectureAnalyzer | test_all_semantic_rules_and_decisions_are_candidates |
| ARCH203 InfrastructureLeakage | LLM | SemanticArchitectureAnalyzer | test_all_semantic_rules_and_decisions_are_candidates |
| ARCH204 MisplacedComponent | LLM | SemanticArchitectureAnalyzer | test_all_semantic_rules_and_decisions_are_candidates |
| ARCH205 SuspiciousCrossLayerResponsibility | LLM | SemanticArchitectureAnalyzer | test_all_semantic_rules_and_decisions_are_candidates |

Канонические пути находятся в открытом репозитории. Нормативные evaluators размещены в architecture/rules/builtin.py, графовый conformance — в architecture/graph/conformance.py, графовые кандидаты — в architecture/graph/candidates.py, семантический анализ — в architecture/intelligence/analyzer.py. Полные paths, версии и SHA-256 закреплены в rule-coverage.json; ссылки на агрегаты ведут к final-rule-strata.json. Такое соответствие связывает код, проверку и измерение, а не только текстовое описание возможности.

## А.2 Полный публичный пример ограничения слоёв

Ниже без изменения приведён открытый examples/architecture/layered-clean.yaml. Это проверяемый пример DSL, а не реконструкция закрытого benchmark. Правило относится только к исходному слою presentation, разрешает переход в application и допускает связь внутри presentation. Оно не вводит неявного запрета для других исходных слоёв и не определяет идеальную архитектуру любого приложения.

```yaml
version: "1.0"
architecture:
  layers:
    - name: presentation
      include: ["**/controller/**"]
    - name: application
      include: ["**/service/**"]
    - name: persistence
      include: ["**/repository/**"]
rules:
  - id: ARCH002
    type: layer_dependency
    from: presentation
    allow: [application]
    allow_same_layer: true
    severity: high
```

Если actual endpoint не классифицирован по требуемой размерности, проверка этого ограничения не производится. Если один файл соответствует нескольким слоям, классификация недопустима и findings не выдаются. INCLUDE/EXCLUDE сопоставляются с относительным путём, а не с host directory. Подмена отсутствующего класса «предполагаемым слоем» по имени компонента в этой проверке не допускается.

## А.3 Полный публичный пример проверки цикла

Следующий examples/architecture/circular-component.yaml задаёт ARCH003. Пустое architecture не является ошибкой: component-проекция может строиться без целевых слоёв и модулей. Без включённого правила тот же цикл остаётся наблюдением, а не нормативным нарушением.

```yaml
version: "1.0"
architecture: {}
rules:
  - id: ARCH003
    type: circular_dependency
    projection: component
    severity: high
```

Проекция и фильтр отношений входят в происхождение графового доказательства. Для циклической SCC формируется одна представительная замкнутая трасса. Каждое её ребро связано с исходными IAM refs; ограниченная трасса без замыкания не подходит для finding. Self-loop одного узла в принятой conformance-семантике не превращается в циклическую SCC размера не менее двух.

## А.4 Инварианты доказательства

Нормативное свидетельство содержит нормализованное ограничение, отпечаток спецификации, фактические назначения концов и подтверждённые рёбра. Статический trace описывает прямую пару; графовый — реальный замкнутый путь в конкретной проекции. Несколько мест вызова сохраняются как provenance и occurrences, не дублируя логическую границу.

FindingId устойчив относительно сдвига строк и изменения числа call sites, но зависит от правила, проекта и границы либо SCC. Severity берётся из контракта и не служит confidence. Проверка одинакового имени или численно высокого PageRank не заменяет proof. Generic SEC-свидетельства запрещены в ARCH-композиции. Эти инварианты проверяются до применения научной агрегирующей метрики, поэтому прослеживаемость не может быть восстановлена одним красивым текстовым объяснением после оценки.
