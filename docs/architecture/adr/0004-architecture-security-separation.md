# ADR 0004 — Architecture and Security separation

Status: accepted · Stage: Foundation v1

## Context

ВКР исследует architectural conformance. Общая program model полезна Security, но inclusion
SEC findings в архитектурный benchmark изменило бы предмет исследования.

## Decision

Раздельные ARCH/SEC pipelines, detector sources, decisions и evaluation. Hybrid input/output
валидируют ARCH-only принадлежность, включая generic SEC LLM_RESULT. Security-specific evidence
types запрещены ARCH. Единая очередь UI может показывать оба namespace только с явной маркировкой.

Deterministic explicit rule violations сохраняются; LLM не вправе их отменять. Structural findings
содержат graph facts и heuristic interpretation. Semantic findings используют LLM лишь для
семантического контекста. Security findings принимаются отдельным Security pipeline.

## Consequences

Security использует IDs/IAM/trace без изменения научного ядра. Architecture F1 фильтруется ARCH
на уровне protocol, dataset и future evaluation. Future Hybrid implementation обязана сохранять
confirmed deterministic findings; scoring/fusion в этом этапе не реализуется.
