# Graph experience V2

SVG + native JavaScript: хватает детерминированной сцены, доступных interactive node targets и точной геометрии pulses; WebGL для 216 synthetic nodes не нужен. Видимый DOM ограничен агрегатами либо одним кластером, а не всеми деталями сразу.

12: прямое исследование модулей. 40/216: overview доменных кластеров с member counts, раскрытие одного кластера, доступ к связанным boundary modules. Search-to-node раскрывает нужный контекст. Type filter относится к IMPORTS/CALLS, не к runtime execution. Incoming = dependents; outgoing = dependencies. Это не доказанная полная change-impact модель.

Выбор edge показывает relation и связанные findings/proofs. Node inspector предоставляет текстовый эквивалент связи. Fit, selection focus, pan/zoom, back-to-clusters, minimap, fullscreen и replay полезны каждый сам по себе. Повторные входы не умножают обработчики.

Imported graph не получает синтетических findings, role assignments или inferred domains. Данные без классификации объединяются только в явно UI-generated buckets, не в target architecture. Provenance и truncation сохраняются. Отсутствие edge не означает отсутствие зависимости.

## Final implementation notes

216-node demo is clustered into six domains. Domains larger than 24 nodes use 18-node pages, with explicit page controls and cross-page search. Visible paths are restricted to that page; the inspector retains all incident relationships. Imported unclassified nodes are grouped by visual batches, never labelled as discovered architectural layers. The import hard cap is 500 nodes / 3000 edges; UX stress verification covers 12, 40 and 216, not 1000. Imported metrics, proof provenance and cycle observations are inspectable without treating an unruled cycle as a violation.
