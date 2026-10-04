# PROMPT 005 verification

Date: 2026-10-04. Status: complete. Эти counts относятся к небольшим fixtures,
не являются benchmark Precision/Recall/F1 или результатами Hybrid/Security analysis.

## Git baseline

Initial project был целиком untracked, без history. Проверены exclusions для .env (кроме example),
venv/caches/coverage, runtime/DB data, temporary IAM/results/workspaces/logs и IDE files.
Baseline `make check`: 424 passed. Создан только разрешённый local root commit
`53956fc` — `chore: baseline ArchGuard through IAM foundation`. Remote/push/global identity changes
не выполнялись. PROMPT 005 changes оставлены reviewable uncommitted diff, новые файлы с intent-to-add.

## Quality gate

`uv sync --locked --extra dev`: passed.
`make check`: Ruff passed, 184 Python files formatted, strict mypy passed (115 source files),
pytest **559 passed, 0 failed, 0 skipped**, branch-aware total coverage **93%**.
Существующие 424 tests сохранены; добавлены 135 tests.
`git diff --check`: passed, включая new files.

Critical module coverage: specification models 98%, loader 95%, classifier 97%, dependency proof
98%, analyzer 100%, rule evaluators/registry 100%, finding generation 100%. Confidence остаётся null;
Hybrid evidence contract compatibility проверена без реализации fusion.

## Manual CLI scenarios

Команда для каждого fixture:

```bash
.venv/bin/archguard architecture check tests/fixtures/conformance/clean/java \
  --spec examples/architecture/layered-clean.yaml --namespace prompt005-verification --json
```

| Fixture | Specification | Status / exit | Findings | IAM nodes / edges |
| --- | --- | --- | --- | --- |
| clean/java | layered-clean | CONFORMANT / 0 | 0 | 16 / 6 |
| clean/typescript | layered-clean | CONFORMANT / 0 | 0 | 14 / 6 |
| clean (mixed) | layered-clean | CONFORMANT / 0 | 0 | 29 / 12 |
| violating/java | layered-clean | NON_CONFORMANT / 1 | ARCH002: 1 | 16 / 6 |
| violating/typescript | layered-clean | NON_CONFORMANT / 1 | ARCH002: 1 | 14 / 6 |
| violating (mixed) | layered-clean | NON_CONFORMANT / 1 | ARCH002: 2 | 29 / 12 |
| forbidden | layered-strict | NON_CONFORMANT / 1 | ARCH001: 1 | 11 / 2 |
| reverse | layered-strict | NON_CONFORMANT / 1 | ARCH004: 1 | 11 / 2 |
| module | modular | NON_CONFORMANT / 1 | ARCH005: 1 | 9 / 2 |

Все scenarios valid/complete. Clean — Controller → Service → Repository; violating —
Controller → Repository с IMPORTS/CREATES/USES и тремя CALLS sites, агрегированными в один finding.
Finding primary location — import line 2; related locations включают call lines 7/8/9.
Подтверждены actual endpoints/edge trace, expected target-rule evidence и HIGH severity ARCH002.
Full source/comment marker и absolute repository path отсутствуют в canonical outputs.

## Determinism и Linux

Два независимых violating/java CLI runs, второй с `--output result-b.json`, дали побайтно одинаковые
result-a/result-b artifacts. SHA-256:
`c028bb2e1c45f9afe4ddd5360feaf2895c948d97fec20143d8627a7c42b8accf`.

`docker build -t archguard:prompt005 -f docker/Dockerfile .`: passed from locked runtime.
Linux checks выполнялись от image USER archguard, с `--rm --network none --read-only`, tmpfs /tmp
и read-only fixture/spec mounts. Clean/java и violating/java outputs побайтно совпали с macOS.
Clean artifact SHA-256: `2d1c17e047709482daf6184036acd2c1105f1048f379dfb75172e6997b8de1d9`.
Operational logs отдельно от canonical artifact. Temporary result-a/result-b/result-linux,
manual summary и task-specific check/build logs удалены после проверки; containers auto-removed.

## Scope review

Без valid explicit target spec ARCH findings не создаются. Unknown/ambiguous references не становятся
actual dependencies. Overlap/invalid schema — configuration errors; invalid classification подавляет
findings. Shared Finding/Evidence/Trace и IAM contracts сохранены; application/domain boundary test
расширен только разрешённой application → architecture зависимостью.

Changed areas: specification/classification/rule registry/conformance, CheckArchitecture use case,
filesystem loader и CLI; PyYAML/types stubs + lockfile; 3 YAML examples, 18 source fixture files,
4 test modules и boundary contract; README, catalog, DSL/conformance docs и ADR 0012.
Known limits и semantics перечислены в [Static Conformance](STATIC_CONFORMANCE.md).
ARCH003 требует cycles/path proof, поэтому отложен вместе с Graph Engine/metrics. LLM/Hybrid scoring,
SEC, analysis API/persistence и frontend не добавлены. Следующий этап:
**PROMPT 006 — Graph Engine & Structural Architecture Analysis**.
