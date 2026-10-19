# THESIS_FACT_AUDIT — проверка фактов ВКР

**Статус: PASS.** Проверены текущие восемь основных файлов рукописи и доступный файл frontmatter и числовые таблицы по замороженным публичным агрегатам. Изменений исходных научных артефактов нет. Проверка является authoring-аудитом: не импортирует проектные evaluators, не запускает анализаторы, не читает индивидуальные предсказания, оригинальную истину, человеческие ответы, замысел конструктора или credentials.

Проверка числовой согласованности использует только доступные агрегаты: сверяет их canonical SHA-256 seals, опубликованные дроби/суммы и значения в основных таблицах. Это не новый научный пересчёт из закрытых строк. Неразрешённые статистические процедуры и confidence intervals не добавлялись. Для читаемости числовые таблицы манускрипта показывают до шести десятичных знаков; точные исходные значения сохранены в этом аудите и замороженных публичных JSON. Дроби, целочисленные counts и научные выводы не менялись.

## 1. Проверенные утверждения

| ID | Утверждение | Точное значение / проверка | Источник | Место в рукописи | Статус |
| --- | --- | --- | --- | --- | --- |
| ARCH-A1-counts | A1 первичные counts | N300; TP/FP/TN/FN=40/0/40/110; negative nondef=110 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4, таблица architecture_counts; приложениеВ | PASS |
| ARCH-A1-Precision | A1 Precision | 1.0 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A1-Recall | A1 Recall | 0.26666666666666666 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A1-F1 | A1 F1 | 0.42105263157894735 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A1-Specificity | A1 Specificity | 1.0 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A1-FPR | A1 FPR | 0.0 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A1-FNR | A1 FNR | 0.7333333333333333 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A1-effective_correctness | A1 effective_correctness | 0.26666666666666666 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A1-definitive_coverage | A1 definitive_coverage | 0.26666666666666666 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A2-counts | A2 первичные counts | N300; TP/FP/TN/FN=60/10/50/90; negative nondef=90 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4, таблица architecture_counts; приложениеВ | PASS |
| ARCH-A2-Precision | A2 Precision | 0.8571428571428571 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A2-Recall | A2 Recall | 0.4 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A2-F1 | A2 F1 | 0.5454545454545454 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A2-Specificity | A2 Specificity | 0.8333333333333334 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A2-FPR | A2 FPR | 0.16666666666666666 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A2-FNR | A2 FNR | 0.6 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A2-effective_correctness | A2 effective_correctness | 0.36666666666666664 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A2-definitive_coverage | A2 definitive_coverage | 0.4 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A3-counts | A3 первичные counts | N300; TP/FP/TN/FN=107/7/124/43; negative nondef=19 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4, таблица architecture_counts; приложениеВ | PASS |
| ARCH-A3-Precision | A3 Precision | 0.9385964912280702 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A3-Recall | A3 Recall | 0.7133333333333334 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A3-F1 | A3 F1 | 0.8106060606060606 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A3-Specificity | A3 Specificity | 0.9465648854961832 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A3-FPR | A3 FPR | 0.05343511450381679 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A3-FNR | A3 FNR | 0.2866666666666667 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A3-effective_correctness | A3 effective_correctness | 0.77 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A3-definitive_coverage | A3 definitive_coverage | 0.7966666666666666 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A4-counts | A4 первичные counts | N300; TP/FP/TN/FN=100/10/90/50; negative nondef=50 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4, таблица architecture_counts; приложениеВ | PASS |
| ARCH-A4-Precision | A4 Precision | 0.9090909090909091 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A4-Recall | A4 Recall | 0.6666666666666666 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A4-F1 | A4 F1 | 0.7692307692307693 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A4-Specificity | A4 Specificity | 0.9 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A4-FPR | A4 FPR | 0.1 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A4-FNR | A4 FNR | 0.3333333333333333 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A4-effective_correctness | A4 effective_correctness | 0.6333333333333333 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A4-definitive_coverage | A4 definitive_coverage | 0.6666666666666666 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A5-counts | A5 первичные counts | N300; TP/FP/TN/FN=107/4/128/43; negative nondef=18 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4, таблица architecture_counts; приложениеВ | PASS |
| ARCH-A5-Precision | A5 Precision | 0.963963963963964 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A5-Recall | A5 Recall | 0.7133333333333334 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A5-F1 | A5 F1 | 0.8199233716475096 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A5-Specificity | A5 Specificity | 0.9696969696969697 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A5-FPR | A5 FPR | 0.030303030303030304 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A5-FNR | A5 FNR | 0.2866666666666667 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A5-effective_correctness | A5 effective_correctness | 0.7833333333333333 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A5-definitive_coverage | A5 definitive_coverage | 0.8 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A6-counts | A6 первичные counts | N300; TP/FP/TN/FN=149/7/141/1; negative nondef=2 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4, таблица architecture_counts; приложениеВ | PASS |
| ARCH-A6-Precision | A6 Precision | 0.9551282051282052 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A6-Recall | A6 Recall | 0.9933333333333333 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A6-F1 | A6 F1 | 0.9738562091503268 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A6-Specificity | A6 Specificity | 0.9527027027027027 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A6-FPR | A6 FPR | 0.0472972972972973 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A6-FNR | A6 FNR | 0.006666666666666667 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A6-effective_correctness | A6 effective_correctness | 0.9666666666666667 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A6-definitive_coverage | A6 definitive_coverage | 0.9933333333333333 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A7-counts | A7 первичные counts | N300; TP/FP/TN/FN=149/0/149/1; negative nondef=1 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4, таблица architecture_counts; приложениеВ | PASS |
| ARCH-A7-Precision | A7 Precision | 1.0 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A7-Recall | A7 Recall | 0.9933333333333333 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A7-F1 | A7 F1 | 0.9966555183946488 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A7-Specificity | A7 Specificity | 1.0 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A7-FPR | A7 FPR | 0.0 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A7-FNR | A7 FNR | 0.006666666666666667 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A7-effective_correctness | A7 effective_correctness | 0.9933333333333333 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| ARCH-A7-definitive_coverage | A7 definitive_coverage | 0.9966666666666667 | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | Глава4; приложениеВ | PASS |
| MANUSCRIPT-ARCH-COUNTS | Таблица всех7 confusion matrices | Сверена каждая числовая ячейка | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | 05_chapter4.md#architecture_counts | PASS |
| MANUSCRIPT-ARCH-METRICS | Таблица35 основных долей | 6-знаковое отображение соответствует frozen exact ratios | experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | 05_chapter4.md#architecture_metrics | PASS |
| ARCH-STRATA | Языки,семейства,правила | Java/TS150/150; NORMATIVE/GRAPH/SEMANTIC100/100/100;15×20 | experiments/unified-hybrid/p025-final-results-v1/final-rule-strata.json; final-family-strata.json; final-language-strata.json | Главы4 и заключение; приложениеГ | PASS |
| ARCH-A7-ERRORS | Сохранённые ошибки A7 | ARCH104/JAVA:1FN; ARCH201/TYPESCRIPT:1negative abstention | experiments/unified-hybrid/p025-final-results-v1/final-rule-strata.json; final-language-strata.json | 4.6–4.7; заключение; приложениеГ | PASS |
| ARCH-NATIVE | Не подменять общий знаменатель | Static native80 F1=1; Graph native120 F1=0.9230769230769231; LLM available-only298 supplemental | experiments/unified-hybrid/p025-final-results-v1/final-native-scope-metrics.json | 4.5–4.7; приложениеГ | PASS |
| ARCH-MODEL | Выбранная конфигурация | A4H0;A5H2@0.5;A6H2@0.5;A7H2@0.75; отсутствие post-selection refit | docs/verification/PROMPT_023.md; experiments/unified-hybrid/p025-final-results-v1/final-ablation.json | 2.7;4.4;заключение | PASS |
| ARCH-RQS | RQ2/RQ6 остаютсячастичными | {'RQ1': 'ANSWERED', 'RQ2': 'PARTIALLY_ANSWERED', 'RQ3': 'ANSWERED', 'RQ4': 'ANSWERED', 'RQ5': 'ANSWERED', 'RQ6': 'PARTIALLY_ANSWERED'} | experiments/unified-hybrid/thesis-core-v1/scientific-registry.json | 4.1/4.10; заключение | PASS |
| ARCH-HYPOTHESIS | Гипотеза только controlledN300 | SUPPORTED on frozen controlled N=300; не universalproof | experiments/unified-hybrid/p025-final-results-v1/final-hypothesis.json; experiments/unified-hybrid/thesis-core-v1/scientific-registry.json | Введение;4.10;заключение | PASS |
| CONTEXT-RESOURCES | Экономияконтекста | input reduction=52.700049596712454%; cost reduction=36.96954105267378%; resource N99 | experiments/unified-hybrid/p025-final-results-v1/prior-context-efficiency.json | 2.6;4.8;6.6;заключение | PASS |
| CONTEXT-QUALITY | Умеренное снижениекачества | quality N96; precision delta-3.3068783068783025pp;F1 delta-1.8142235123367212pp;effectivecorrectness delta-2.083333333333337pp;latency+0.1684111670650908959595959596s | experiments/unified-hybrid/p025-final-results-v1/prior-context-efficiency.json | 4.8;6.6;заключение | PASS |
| ARCH-ACQUISITION | 300/298/2 | 300 logical/physical;298accepted;2technicalmissing;1usageunknown; no droppedmainrows | experiments/unified-hybrid/p025-final-results-v1/final-resource-metrics.json | 4.4/4.9;6.6;заключение | PASS |
| ARCH-COST | Стоимостьнеinvoice | USD0.1424563 known estimated +USD0.0042768 reserved =USD0.1467331 exposure;invoiceNULL | experiments/unified-hybrid/p025-final-results-v1/final-resource-metrics.json | 4.9;6.6;заключение;приложениеВ | PASS |
| ARCH-TOKENS | Reportedusage | 836148input+117683output=953831; cached0;usageunknown1 | experiments/unified-hybrid/p025-final-results-v1/final-resource-metrics.json | 4.9;приложениеВ | PASS |
| ARCH-RUNTIME | Область измерений | combined=4.1773616606369615s;whole-worker RSS=72286208B;transport sum=1713.6846025750565s; per-method RSS/separateStaticGraph NOT_MEASURED | experiments/unified-hybrid/p025-final-results-v1/final-resource-metrics.json | 4.9;приложениеВ | PASS |
| SEC-HUMAN | Согласиеиреференс | 290/300=0.9666666666666667;κ=0.9408913583165859;10humanadjudications | experiments/security/security-human-review-v1/public/security-human-truth-closure.json | 5.5;заключение;приложениеИ | PASS |
| SEC-TRUTH-ALL | Humantruth ALL | N=300;P/N/U/O=122/158/20/0;binary=280 | experiments/security/security-human-review-v1/public/security-human-truth-closure.json | 5.5;заключение | PASS |
| SEC-TRUTH-DEV | Humantruth DEV | N=100;P/N/U/O=37/52/11/0;binary=89 | experiments/security/security-human-review-v1/public/security-human-truth-closure.json | 5.5;заключение | PASS |
| SEC-TRUTH-FINAL | Humantruth FINAL | N=200;P/N/U/O=85/106/9/0;binary=191 | experiments/security/security-human-review-v1/public/security-human-truth-closure.json | 5.5;заключение | PASS |
| SEC-V2DEV-COUNTS | V2DEV counts | N100/binary89; TP/FP/TN/FN=7/0/0/0;positive_nondef=30;negative_nondef=52;defnegative=0 | experiments/security/security-dev-baseline-v1/public/security-dev-baseline-metrics.json | 5.6–5.8;заключение | PASS |
| SEC-V2DEV-precision | V2DEV precision | 1.0 | experiments/security/security-dev-baseline-v1/public/security-dev-baseline-metrics.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V2DEV-recall | V2DEV recall | 1.0 | experiments/security/security-dev-baseline-v1/public/security-dev-baseline-metrics.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V2DEV-F1 | V2DEV F1 | 1.0 | experiments/security/security-dev-baseline-v1/public/security-dev-baseline-metrics.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V2DEV-specificity | V2DEV specificity | None | experiments/security/security-dev-baseline-v1/public/security-dev-baseline-metrics.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V2DEV-FPR | V2DEV FPR | None | experiments/security/security-dev-baseline-v1/public/security-dev-baseline-metrics.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V2DEV-FNR | V2DEV FNR | 0.0 | experiments/security/security-dev-baseline-v1/public/security-dev-baseline-metrics.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V2DEV-effective_positive_recovery | V2DEV effective_positive_recovery | 0.1891891891891892 | experiments/security/security-dev-baseline-v1/public/security-dev-baseline-metrics.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V2DEV-effective_negative_correctness | V2DEV effective_negative_correctness | 0.0 | experiments/security/security-dev-baseline-v1/public/security-dev-baseline-metrics.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V2DEV-definitive_coverage | V2DEV definitive_coverage | 0.07865168539325842 | experiments/security/security-dev-baseline-v1/public/security-dev-baseline-metrics.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V2DEV-effective_correctness | V2DEV effective_correctness | 0.07865168539325842 | experiments/security/security-dev-baseline-v1/public/security-dev-baseline-metrics.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V2DEV-unified_correctness | V2DEV unified_correctness | 0.07 | experiments/security/security-dev-baseline-v1/public/security-dev-baseline-metrics.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V2DEV-unified_definitive_coverage | V2DEV unified_definitive_coverage | 0.08 | experiments/security/security-dev-baseline-v1/public/security-dev-baseline-metrics.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V2DEV-nondefinitive_rate | V2DEV nondefinitive_rate | 0.92 | experiments/security/security-dev-baseline-v1/public/security-dev-baseline-metrics.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V2DEV-analysis_coverage | V2DEV analysis_coverage | 0.95 | experiments/security/security-dev-baseline-v1/public/security-dev-baseline-metrics.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V2DEV-applicability_coverage | V2DEV applicability_coverage | 0.95 | experiments/security/security-dev-baseline-v1/public/security-dev-baseline-metrics.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V3DEV-COUNTS | V3DEV counts | N100/binary89; TP/FP/TN/FN=21/0/0/0;positive_nondef=16;negative_nondef=52;defnegative=0 | experiments/security/security-dev-refinement-v3/public/security-dev-candidate-primary.json | 5.6–5.8;заключение | PASS |
| SEC-V3DEV-precision | V3DEV precision | 1.0 | experiments/security/security-dev-refinement-v3/public/security-dev-candidate-primary.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V3DEV-recall | V3DEV recall | 1.0 | experiments/security/security-dev-refinement-v3/public/security-dev-candidate-primary.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V3DEV-F1 | V3DEV F1 | 1.0 | experiments/security/security-dev-refinement-v3/public/security-dev-candidate-primary.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V3DEV-specificity | V3DEV specificity | None | experiments/security/security-dev-refinement-v3/public/security-dev-candidate-primary.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V3DEV-FPR | V3DEV FPR | None | experiments/security/security-dev-refinement-v3/public/security-dev-candidate-primary.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V3DEV-FNR | V3DEV FNR | 0.0 | experiments/security/security-dev-refinement-v3/public/security-dev-candidate-primary.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V3DEV-effective_positive_recovery | V3DEV effective_positive_recovery | 0.5675675675675675 | experiments/security/security-dev-refinement-v3/public/security-dev-candidate-primary.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V3DEV-effective_negative_correctness | V3DEV effective_negative_correctness | 0.0 | experiments/security/security-dev-refinement-v3/public/security-dev-candidate-primary.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V3DEV-definitive_coverage | V3DEV definitive_coverage | 0.23595505617977527 | experiments/security/security-dev-refinement-v3/public/security-dev-candidate-primary.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V3DEV-effective_correctness | V3DEV effective_correctness | 0.23595505617977527 | experiments/security/security-dev-refinement-v3/public/security-dev-candidate-primary.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V3DEV-unified_correctness | V3DEV unified_correctness | 0.21 | experiments/security/security-dev-refinement-v3/public/security-dev-candidate-primary.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V3DEV-unified_definitive_coverage | V3DEV unified_definitive_coverage | 0.21 | experiments/security/security-dev-refinement-v3/public/security-dev-candidate-primary.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V3DEV-nondefinitive_rate | V3DEV nondefinitive_rate | 0.79 | experiments/security/security-dev-refinement-v3/public/security-dev-candidate-primary.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V3DEV-analysis_coverage | V3DEV analysis_coverage | 0.95 | experiments/security/security-dev-refinement-v3/public/security-dev-candidate-primary.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V3DEV-applicability_coverage | V3DEV applicability_coverage | 0.95 | experiments/security/security-dev-refinement-v3/public/security-dev-candidate-primary.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V3FINAL-COUNTS | V3FINAL counts | N200/binary191; TP/FP/TN/FN=38/3/0/0;positive_nondef=47;negative_nondef=103;defnegative=0 | experiments/security/security-final-evaluation-v1/public/security-final-metrics.json | 5.6–5.8;заключение | PASS |
| SEC-V3FINAL-precision | V3FINAL precision | 0.926829268292683 | experiments/security/security-final-evaluation-v1/public/security-final-metrics.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V3FINAL-recall | V3FINAL recall | 1.0 | experiments/security/security-final-evaluation-v1/public/security-final-metrics.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V3FINAL-F1 | V3FINAL F1 | 0.9620253164556962 | experiments/security/security-final-evaluation-v1/public/security-final-metrics.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V3FINAL-specificity | V3FINAL specificity | 0.0 | experiments/security/security-final-evaluation-v1/public/security-final-metrics.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V3FINAL-FPR | V3FINAL FPR | 1.0 | experiments/security/security-final-evaluation-v1/public/security-final-metrics.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V3FINAL-FNR | V3FINAL FNR | 0.0 | experiments/security/security-final-evaluation-v1/public/security-final-metrics.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V3FINAL-effective_positive_recovery | V3FINAL effective_positive_recovery | 0.4470588235294118 | experiments/security/security-final-evaluation-v1/public/security-final-metrics.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V3FINAL-effective_negative_correctness | V3FINAL effective_negative_correctness | 0.0 | experiments/security/security-final-evaluation-v1/public/security-final-metrics.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V3FINAL-definitive_coverage | V3FINAL definitive_coverage | 0.21465968586387435 | experiments/security/security-final-evaluation-v1/public/security-final-metrics.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V3FINAL-effective_correctness | V3FINAL effective_correctness | 0.19895287958115182 | experiments/security/security-final-evaluation-v1/public/security-final-metrics.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V3FINAL-unified_correctness | V3FINAL unified_correctness | 0.19 | experiments/security/security-final-evaluation-v1/public/security-final-metrics.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V3FINAL-unified_definitive_coverage | V3FINAL unified_definitive_coverage | 0.205 | experiments/security/security-final-evaluation-v1/public/security-final-metrics.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V3FINAL-nondefinitive_rate | V3FINAL nondefinitive_rate | 0.795 | experiments/security/security-final-evaluation-v1/public/security-final-metrics.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V3FINAL-analysis_coverage | V3FINAL analysis_coverage | 0.95 | experiments/security/security-final-evaluation-v1/public/security-final-metrics.json | Глава5;точные значения данного audit;приложения Security | PASS |
| SEC-V3FINAL-applicability_coverage | V3FINAL applicability_coverage | 0.95 | experiments/security/security-final-evaluation-v1/public/security-final-metrics.json | Глава5;точные значения данного audit;приложения Security | PASS |
| MANUSCRIPT-SEC-RULES | ВсеправилаFINAL | Все60 числовых ячеек сверены с frozen groups | experiments/security/security-final-evaluation-v1/public/security-final-rule-metrics.json | 06_chapter5.md#security_rule_final | PASS |
| SEC-FINAL-OUTCOMES | Все8исходовFINAL | {'DEFINITIVE_NEGATIVE': 0, 'DEFINITIVE_POSITIVE': 41, 'FAILED': 0, 'INSUFFICIENT_EVIDENCE': 0, 'NOT_APPLICABLE': 0, 'PARTIAL': 137, 'POTENTIAL': 12, 'UNSUPPORTED': 10} | experiments/security/security-final-evaluation-v1/public/security-final-metrics.json | 5.7 | PASS |
| SEC-FINAL-FP | SEC001неисправленпослеFINAL | 3FP, всеSEC001;ruleprecision3/6=.5 | experiments/security/security-final-evaluation-v1/public/security-final-rule-metrics.json | 5.7;заключение | PASS |
| SEC-DELTA-definitive_coverage | FINAL−DEV definitive_coverage | -2.1295370315900923 pp | experiments/security/security-final-evaluation-v1/public/security-dev-final-generalization.json | 5.8;точная таблицаaudit | PASS |
| SEC-DELTA-effective_correctness | FINAL−DEV effective_correctness | -3.7002176598623455 pp | experiments/security/security-final-evaluation-v1/public/security-dev-final-generalization.json | 5.8;точная таблицаaudit | PASS |
| SEC-DELTA-effective_negative_correctness | FINAL−DEV effective_negative_correctness | 0.0 pp | experiments/security/security-final-evaluation-v1/public/security-dev-final-generalization.json | 5.8;точная таблицаaudit | PASS |
| SEC-DELTA-effective_positive_recovery | FINAL−DEV effective_positive_recovery | -12.050874403815575 pp | experiments/security/security-final-evaluation-v1/public/security-dev-final-generalization.json | 5.8;точная таблицаaudit | PASS |
| SEC-DELTA-nondefinitive_rate | FINAL−DEV nondefinitive_rate | 0.5000000000000004 pp | experiments/security/security-final-evaluation-v1/public/security-dev-final-generalization.json | 5.8;точная таблицаaudit | PASS |
| SEC-DELTA-precision | FINAL−DEV precision | -7.317073170731703 pp | experiments/security/security-final-evaluation-v1/public/security-dev-final-generalization.json | 5.8;точная таблицаaudit | PASS |
| SEC-NO-BASELINE | НетblindV2FINALbaseline | P029_FINAL_EFFECTIVENESS=NOT_EVALUATED;POST_FINAL_TUNING=0 | experiments/security/security-final-evaluation-v1/public/security-dev-final-generalization.json | 5.8;6;заключение | PASS |
| SEC-CAPABILITIES | 20языковыхячеек | SEC001Java/TS IMPLEMENTED_V3;SEC005TS CONTRACT_ONLY;прочиеPARTIAL_V3 | experiments/security/security-extension-v1/public/security-final-capability-matrix.json | 5.2 | PASS |
| SEC-RESOURCES | ЕдинственныйP034run | analyzer0.5379849630116951s;worker0.6030466249794699s;process0.8850627089850605s;RSS62111744B;source81889B | experiments/security/security-final-evaluation-v1/public/security-final-evaluation-resources.json | 5.8 | PASS |
| QUALITY-P035 | ИсторическийqualityP035 | 3278passed/28guardedskips/81%;module-not-measured раскрыт | experiments/security/security-final-evaluation-v1/public/quality-verification.json | 6.2;приложениеИ | PASS |
| QUALITY-P036 | ПоследнийfrozenqualityP036 | 3337passed/29guardedskips/64%;exit0;module-not-measured раскрыт | experiments/security/security-extension-v1/public/quality-verification.json | 6.2;заключение;приложениеИ | PASS |
| SEC-CLOSURE | Completeтолькоboundedresearch | Extension complete;production/soundnessNOT_CLAIMED;naturalprevalenceNOT_ESTABLISHED | experiments/security/security-extension-v1/public/security-extension-closure.json | 5.8;6.7;заключение | PASS |
| MANUSCRIPT-QUALITY-TABLE | Обеисторическиеконтрольныеточки | P0353278/28/81%;P0363337/29/64% | experiments/security/security-extension-v1/public/quality-verification.json | 07_chapter6.md#quality_snapshots | PASS |
| MANUSCRIPT-SEC-CAPABILITY | Сверка20ячеекcapability | Все20статусовсовпадаютсfrozencells | experiments/security/security-extension-v1/public/security-final-capability-matrix.json | 06_chapter5.md#security_capabilities | PASS |
| MANUSCRIPT-NON-SANITIZATION | Неблагоприятныефактыприсутствуют | FN1;FP3;positive_nondef47;negative_nondef103;nondef79.5%;quality decrease;RQpartials;technicalmissing2 | Текущий текст01–08 | Всеосновныеглавы | PASS |
| MANUSCRIPT-COST-NOT-INVOICE | Нетсуммыexposureкакactualinvoice | 0.1467331 обозначена экспозицией;invoiceнеполучен | experiments/unified-hybrid/p025-final-results-v1/final-resource-metrics.json | Всеосновныеглавы | PASS |

## 2. Зафиксированные смысловые границы

- Architecture primary FN включает каждый положительный non-SUPPORTED. Отрицательные неопределённые не становятся TN. Coverage использует фактически определённые ответы D/N, а не автоматически сумму primary confusion counts.
- Security FN условный и означает definitive negative на положительном эталоне; PARTIAL/POTENTIAL/UNSUPPORTED не становятся negative. Поэтому FN=0/Recall=1 сосуществуют с 47 положительными неокончательными. Architecture/Security метрики не объединяются.
- Все семь вариантов на общей Architecture N=300 опубликованы. Нативные80/120 и LLM available-only298 являются дополнительными представлениями.
- Graph-guided экономит input/cost при умеренном снижении качества; ресурсный N=99 и качественный N=96 принадлежат отдельному опыту.
- USD0.1467331 является суммой известной **оценки** USD0.1424563 и неопределённого **резерва** USD0.0042768. Это exposure, не actual spend и не invoice. Формулировка позднего prompt, называющая всю сумму измеренной фактической стоимостью, отвергнута в пользу frozen authority.
- DEV V3 использован для refinement; FINAL его не подменяет слепым сравнением с V2. P029 blind FINAL baseline отсутствует.
- Zero definitive negatives и zero effective negative correctness сохранены; узкий TS SEC008 certificate не сертифицировал benchmark-negative.
- RQ2/RQ6 частичны; нет causal feature ranking, natural-prevalence validation или универсальной scalability.
- Криптографический отпечаток фиксирует байты, но не human authorship, независимость людей или semantic truth.
- PostgreSQL/SQLAlchemy/Alembic — инфраструктурная основа без прикладных таблиц; API health/system не выдается за завершённый analysis lifecycle; frontend не выдуман.

## 3. Проверенные публичные источники

| Путь | Canonical fingerprint | SHA-256 байтов | Статус |
| --- | --- | --- | --- |
| experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json | f98709ce55c6ed64200052a69612480cb3593e1ea6f82592b2f6ca69278f959e | 26431ec29dd438dc13acbc66a2e5027ce3145d28bf3d0394c533e5575ffa3dbb | PASS |
| experiments/unified-hybrid/p025-final-results-v1/final-coverage-metrics.json | ceea3dea28a10596aa84530d033bbabfe1b576dd397a16a17b07a13c24b0b1e1 | 14eff5848963f57bbbd59ac01ee7a952f94893000f7bee315b3296c3c3212efb | PASS |
| experiments/unified-hybrid/p025-final-results-v1/final-native-scope-metrics.json | fc48e613ce28811ce9ff6e85dd78bc7949ebf308c75419801fffeaeab882d604 | 250d9baab190a565a25a75dabec04ddbde13fa0a805695c75f509ade0ce5aa7d | PASS |
| experiments/unified-hybrid/p025-final-results-v1/final-rq-summary.json | 402d603c6848d5c6866375ae2b919173cc127d2a2c3c15164372630181bcfb2d | 3f231881623369cae45736e444e33d39789ced99b070eae7deccdb4cf4d0d303 | PASS |
| experiments/unified-hybrid/p025-final-results-v1/final-hypothesis.json | 43911be7b9ab087cad58158abef19b30e3d4e3a1965b4150bd839a1e23c6a053 | f07f9c7d72cb74e636e28d859740e9369797f4dd8f026cec3aba4c528a7026bb | PASS |
| experiments/unified-hybrid/p025-final-results-v1/final-resource-metrics.json | 870efc24437b19790073e0986c899c4ae09329085dbe5b84f4af4736c170c6d9 | 86062117e9a5820d87d1575a4d7f58d26cced315058c239468cba32dfb2d1892 | PASS |
| experiments/unified-hybrid/p025-final-results-v1/prior-context-efficiency.json | 84dbfa2f8dae7ff903f6fe820e08e687343f4df4950e0efb03dc11ef547d1ba6 | 987d73ac0b03a1449f284c1261e186745d366794dc193cc7faabd473eb7d8e6a | PASS |
| experiments/unified-hybrid/p025-final-results-v1/final-ablation.json | c68adf9b16375a85812308bc8efc403d238c8d105544d5e20cabd8252ab9c2a2 | 21d1db1b5ecef1dd3f4b65c062bbdb50359760bbe4cf5cd40e327893b337fe6a | PASS |
| experiments/unified-hybrid/p025-final-results-v1/final-family-strata.json | 520fce8aa2af38602406158bb16f170d7711102a1b221e06d67a9b03bb94a2e2 | c694ccd4564ff2993e5941febe66df02313c6f0f4ed521968076ea8365650e35 | PASS |
| experiments/unified-hybrid/p025-final-results-v1/final-language-strata.json | 1836a63b276db458a365570eea473a3a95ba1974ae3fff065ea3f6caf8236795 | 9c8f83a8edf6770e4db3e8fdc5ededae0a98f922175e9192f1c74764007918cf | PASS |
| experiments/unified-hybrid/p025-final-results-v1/final-rule-strata.json | 46cd755a9943e48c84794c9e2beaede45ffb201c14f6abd5d0d895350342d073 | 88431a42c52d754d724a64eae0e2d70137aa294391302acb1ef4cf956407ecb0 | PASS |
| experiments/unified-hybrid/p025-final-results-v1/final-paired-comparisons.json | 9c896e89f268eab905caa9c3ce1b64284d2f0e5901fcc7c9610efcb164cbeb7c | 6c3fb30921c2f06c0715191eeb8b759d02e8450de2ba3fe5ba8033943d4541a9 | PASS |
| experiments/unified-hybrid/thesis-core-v1/numeric-facts.json | 4ae2451806b1d1c8142aab36a05c1961ad47fce17be0b76a1094c9b20000237e | 54fbd6e84228e9c472886f39cef00b567fb2a5974558c779218aef38cf6e516f | PASS |
| experiments/unified-hybrid/thesis-core-v1/scientific-registry.json | 53420d0aa167ebb99814adb498f3b84597b096f73fe1f77c5c467dc7882a8db1 | a349f40b1aa0fa22c88290d0519852694489c6cac2c98c9f0f9a34b0102a2df3 | PASS |
| experiments/unified-hybrid/thesis-core-v1/quality-verification.json | 14ea8d662087b3abadd51d2113b9f09c5b24ce7b3079df88662cca251713f3c5 | 44b505c2a81baf6fe50112ed50457d79b427ae15d71230f4cc8b6fa14492012a | PASS |
| experiments/security/security-human-review-v1/public/security-human-truth-closure.json | c7481bcafa5adb540777d7b507e13f6fcae50d6368bddaaa307b8a8a5c3d7528 | c7433db631da582a96dec03732512eb08073b4a08d6bb116360097b24b628a85 | PASS |
| experiments/security/security-human-review-v1/public/security-human-agreement.json | 0bed58cc8a2ccdb2590d3bc27005b1d13fdec23d8ca1ddd1a3a905733578f0fb | b5f9956c93c47040af1656eefcf4be9a54a9d8d019b222cb41db69fb41434105 | PASS |
| experiments/security/security-dev-baseline-v1/public/security-dev-baseline-metrics.json | 870cadb51268e77196276457251599664034c7b697e30805de594fb6c7e20905 | 71ab9a1a0fa8faf799d7b243154dd6d2699ed809ddb94d1c3f3fa288dd31b41a | PASS |
| experiments/security/security-dev-refinement-v3/public/security-dev-candidate-primary.json | 0e6f07c86c8b4932d896dbe72dcea89af868357083e91ac21662f1dd13122873 | 1bf86026618cd4ab3409900217b9c7eee6403015f246460949201a94dbdb4fa6 | PASS |
| experiments/security/security-final-evaluation-v1/public/security-final-metrics.json | cb2e461eb89b3578ad6d59e1ec013e71dd732b627ae7785e8a2d5e101044b81e | 57bd8f7877a1ee40794af217638f7161a30673f0e60e4f0eaf1c621a86ec7936 | PASS |
| experiments/security/security-final-evaluation-v1/public/security-final-rule-metrics.json | 76ef9f59c88f9cedd6599dfe5e463c4116d5762df44d016cd78295e87f4c62eb | 6c38a7f26a582fc5f71756ac1b1c24f9be6884f9f095dcb6aed35c8a8896fcd3 | PASS |
| experiments/security/security-final-evaluation-v1/public/security-final-language-metrics.json | 5e571dec83df88508834746bdd1df65eb0525e1cce1fd65195cd87e2321a8901 | 7e105520938c375735c1983e2889c54cb6ee7037410d9d3ad85a1c5c4f385a1a | PASS |
| experiments/security/security-final-evaluation-v1/public/security-dev-final-generalization.json | a383468d36f64be372b633ae95053580f8088e00bfe0592cd69a0931981d4fcf | f739ac39e038836c1c03a50d98d8f20bb691a5f003189cb62548d94f80229fb8 | PASS |
| experiments/security/security-final-evaluation-v1/public/security-final-evaluation-resources.json | b69f1ae9c665c19b1148cf590a2994ba6e912ec12c015c42cf15fc9fc2c5246b | 8a65d48fe01f811e614992d2e272e25ef1aa907a5e3b3ed4a7256e53907cb1d0 | PASS |
| experiments/security/security-final-evaluation-v1/public/quality-verification.json | 4504da900cae9b738c87865d5ba51586dca73beefafe58013d28968699c2b174 | 6af703b75db2739e38593e15d53146b4d95e61611e19e18ae89bbc47bd87b110 | PASS |
| experiments/security/security-extension-v1/public/quality-verification.json | d241d0f2240f4a30db4b4c985235bad3a8021bd55d8fa23ce67e234cb2b5b41f | 118f5e758e464a627470465ebe2343d2fcc990b07c7ec24543235a04916b33c2 | PASS |
| experiments/security/security-extension-v1/public/security-extension-closure.json | 8e3f2a34e44b2aa58ce2d50cdf7e228a1452ca61cec4baa7cb1126c5cb6fd831 | d0fec941ec76498279aa501c0d5c8801f41cb5eeabad310056545e8939295c93 | PASS |
| experiments/security/security-extension-v1/public/security-final-capability-matrix.json | 194a5621282d5cde4ca34a7dd74b2e3c4c274663ff92f0ea4db1a14402c8f137 | 45c0cd73df6e68818ee4964e688059ea5ed0a408100d601683e5d0f433341d6b | PASS |
| experiments/security/security-extension-v1/public/security-rule-catalog.json | 33bfd548683cb766731af6bd061b92ea44631369a8d79d1fdbdf1989ba0ae6e9 | 4d9aa0ecd590aea31f177ca6bc4d0082f21a9fe25725141fc8f70580fe3ebd85 | PASS |

## 4. Снимок текста, к которому относится аудит

| Файл | SHA-256 | Статус |
| --- | --- | --- |
| docs/thesis/source/00_frontmatter.md | ba3cdd66a2fd9c6f6c310fb5db6a278431eb7ac59eaa4d33c70fdb2d81c4a17a | PASS |
| docs/thesis/source/01_introduction.md | 0446db4ab9341ffdc5031fa521abb59e3e888bb154f6a7896d11f348a1e23ca6 | PASS |
| docs/thesis/source/02_chapter1.md | 88c9ef2c4b4e4ef3a5983f96d27de19c7588600224a3e66c2e3cb3afaaada504 | PASS |
| docs/thesis/source/03_chapter2.md | 44f4b4a1db8a30831d519ab494555bfee5e0989bd4e638680912481d2b1234b5 | PASS |
| docs/thesis/source/04_chapter3.md | de1c730a04cac8e668203e7a198b305da377f98aee911faa6985220d6e40f659 | PASS |
| docs/thesis/source/05_chapter4.md | 8e704b9fb4b82bfd08023f8ee86c64f3d80162a2748cedf627bd695147d7734c | PASS |
| docs/thesis/source/06_chapter5.md | 90e6282e308695fb9c2cedcb5b0ac42633387de780412a80aa73b14034a6db3d | PASS |
| docs/thesis/source/07_chapter6.md | 2b4b08fe2723ca8b0a38bf81512f290137fdcd5de6463b7d04f7a355a99123c1 | PASS |
| docs/thesis/source/08_conclusion.md | 4ff2357ac299e9e4cfd6d0d626cfc682b879747fea5b123a8d02c1929254be78 | PASS |

## 5. Ограничения authoring-проверки

Аудит не подтверждает отсутствующие закрытые данные новым чтением. Числа тестов и coverage относятся к историческим quality receipts, а не к запуску suite при написании ВКР. Не измерены отдельные финальные Static/Graph runtimes и память каждого метода; whole-worker RSS не приписан A7. Фактические page/word/character/figure/table/equation/reference counts и OOXML/layout проверяются после сборки DOCX отдельно. При последующей редактуре содержательных числовых утверждений требуется повторная сверка соответствующей строки и обновление снимка текста.

## Финальный контроль 19.10.2026

DOCX SHA-256: `71e83609e42e0592a5cd19a5b148799d5ba407fe6cdc2bd4771cb1c0b4202169`. Все обязательные отрицательные результаты сохранены. Повторно проверены 41 публичная SHA-256-привязка; несовпадений 0. Оригинальные truth/prediction строки не читались; новых научных запусков 0.
