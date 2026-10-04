# ADR 0010 — Tree-sitter parser adapters and separate extraction

Status: accepted · Stage: Language Parsing Foundation

## Context

Нужны реальные syntax trees Java/TypeScript/JavaScript/TSX с error recovery и воспроизводимыми
runtime versions. Language-specific Tree-sitter types не должны стать частью language-neutral
IAM или ARCH/SEC decisions. Existing inventory и lazy bytes reader уже задают source identity.

## Decision

Official tree-sitter + per-language grammar bindings, exact versions в uv.lock и реальные Python
3.13/ABI smoke tests. ParserAdapter Protocol, instance ParserRegistry и separate TSX dialect.
Application ParseRepository использует RepositorySnapshot/RepositoryWorkspace без нового reader.
Parser-facing tree handles находятся только в parsing; metadata JSON не сериализует native trees.

Tolerant default сохраняет ERROR/missing diagnostics; strict отмечает INVALID без прекращения
repository processing. Reader/encoding/adapter failures получают отдельные outcomes. Processing
sequential; metadata aggregate освобождает trees/source bytes, streaming interface выдаёт текущий
tree для будущего extraction. Hash/relative path/snapshot ID переиспользуются из intake.

## Consequences

Tree-sitter обеспечивает syntax parsing и recovery, не архитектурный анализ и не научный метод
ВКР. Symbol/dependency extraction → IAM Builder остаётся отдельным следующим этапом. Нельзя
делать вывод о корректности types/names/dependencies только по отсутствию syntax diagnostics.
Native trees держат source bytes: consumer, сохраняющий streaming trees, отвечает за memory.
Source execution, network calls, IAM mutation и semantic/scanner/LLM logic отсутствуют в parsers.

Подробности и primary package/API references: [PARSING](../PARSING.md).
