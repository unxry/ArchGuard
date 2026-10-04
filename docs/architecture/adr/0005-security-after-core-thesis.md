# ADR 0005 — Security only after CORE THESIS COMPLETE

Status: accepted · Stage: Foundation v1

## Context

Security scanning/data-flow/advisories — отдельная большая область. Раннее расширение создаёт
риски сроков и подменяет architectural research задачей создания универсального scanner.

## Decision

Security implementation starts only after CORE THESIS COMPLETE. Сейчас только namespace,
reserved schema variants, каталог и documented package boundary. Gate определяется
`docs/research/CORE_THESIS_COMPLETE.md`, а не наличием UI/security enum members.

## Consequences

Можно безопасно развивать shared foundation. Нет secret scanner, CVE queries, taint, security
LLM или fake findings в production. После подтверждённого архитектурного метода/эксперимента
Security становится обязательным следующим расширением с самостоятельными quality gates.
