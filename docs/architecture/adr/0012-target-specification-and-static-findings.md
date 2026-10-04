# ADR 0012: Explicit target DSL, deterministic classification and file-pair findings

Status: accepted. Stage: PROMPT 005.

## Context

Actual IAM имеет IMPORTS file→file и other relations declaration→declaration. Static violations
требуют valid target constraints; ambiguous ownership не доказывает code violation. YAML untrusted,
а вывод должен быть воспроизводимым и совместимым с едиными Finding/Evidence/Trace contracts.

## Decision

Версионируем YAML DSL 1.0 и independent target layer/module scopes. Matching — relative POSIX globs
с explicit include/exclude, без приоритетов. Overlap в dimension — invalid classification diagnostic;
unclassified accepted. Target classification не изменяет actual IAM. Bounded event/node loader
запрещает object construction, anchors/aliases/merge keys/duplicate keys и sanitises input errors.

Rules — injected protocol registry, четыре explicit builtins. Только actual internal resolved edges
дают findings; future graph/semantic/security decisions не подменяются static heuristics.
Aggregation — rule + source file + target file, все supporting edges/provenance retained.
Versioned UUIDv5 identity включает project, file IDs и normalized rule scope, но не line/count/severity.
Trace хранит direct actual edge; Confidence absent. Canonical result отдельно от timestamped logs.

## Consequences

Imports/calls/type uses не размножают один logical finding; две rules создают два findings.
IDs переживают сдвиг lines/добавление callsites; normalized spec hash переживает YAML formatting.
File-pair granularity и path-based ownership ограничивают точность component modeling. v1 допускает
один экземпляр каждого builtin ID; richer constraints потребуют явного развития DSL. Completeness
отражается отдельно, и отсутствие findings при incomplete IAM не считается complete conformance.
ARCH003 требует Graph Engine и остаётся следующему этапу. БД, analysis API и frontend отложены.
