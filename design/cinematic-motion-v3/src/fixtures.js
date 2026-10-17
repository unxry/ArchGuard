'use strict';
window.AG.demo = {
  "project": {
    "id": "demo-commerce",
    "name": "Northstar Commerce",
    "revision": "demo/checkout",
    "language": "TypeScript",
    "mode": "LOCAL_DEMO"
  },
  "nodes": [
    {
      "id": "storefront",
      "label": "StorefrontController",
      "group": "interface",
      "domain": "experience",
      "path": "src/interface/storefront.ts"
    },
    {
      "id": "checkout",
      "label": "CheckoutController",
      "group": "interface",
      "domain": "orders",
      "path": "src/interface/checkout.ts"
    },
    {
      "id": "admin",
      "label": "AdminController",
      "group": "interface",
      "domain": "platform",
      "path": "src/interface/admin.ts"
    },
    {
      "id": "webhook",
      "label": "WebhookController",
      "group": "interface",
      "domain": "payments",
      "path": "src/interface/webhooks.ts"
    },
    {
      "id": "orders",
      "label": "OrderService",
      "group": "application",
      "domain": "orders",
      "path": "src/application/orders.ts"
    },
    {
      "id": "catalog",
      "label": "CatalogService",
      "group": "application",
      "domain": "catalog",
      "path": "src/application/catalog.ts"
    },
    {
      "id": "payments",
      "label": "PaymentService",
      "group": "application",
      "domain": "payments",
      "path": "src/application/payments.ts"
    },
    {
      "id": "identity",
      "label": "IdentityService",
      "group": "application",
      "domain": "identity",
      "path": "src/application/identity.ts"
    },
    {
      "id": "orderstore",
      "label": "OrderRepository",
      "group": "infrastructure",
      "domain": "orders",
      "path": "src/infrastructure/order-store.ts"
    },
    {
      "id": "productindex",
      "label": "ProductIndex",
      "group": "infrastructure",
      "domain": "catalog",
      "path": "src/infrastructure/product-index.ts"
    },
    {
      "id": "gateway",
      "label": "PaymentGateway",
      "group": "infrastructure",
      "domain": "payments",
      "path": "src/infrastructure/payment-gateway.ts"
    },
    {
      "id": "audit",
      "label": "AuditLog",
      "group": "infrastructure",
      "domain": "platform",
      "path": "src/infrastructure/audit-log.ts"
    }
  ],
  "edges": [
    {
      "id": "e-storefront-catalog",
      "source": "storefront",
      "target": "catalog",
      "relation": "IMPORTS",
      "findingIds": []
    },
    {
      "id": "e-storefront-identity",
      "source": "storefront",
      "target": "identity",
      "relation": "CALLS",
      "findingIds": []
    },
    {
      "id": "e-checkout-orders",
      "source": "checkout",
      "target": "orders",
      "relation": "IMPORTS",
      "findingIds": [
        "arch-101"
      ]
    },
    {
      "id": "e-checkout-identity",
      "source": "checkout",
      "target": "identity",
      "relation": "CALLS",
      "findingIds": []
    },
    {
      "id": "e-checkout-orderstore",
      "source": "checkout",
      "target": "orderstore",
      "relation": "IMPORTS",
      "findingIds": [
        "arch-001"
      ]
    },
    {
      "id": "e-admin-orders",
      "source": "admin",
      "target": "orders",
      "relation": "CALLS",
      "findingIds": [
        "arch-101"
      ]
    },
    {
      "id": "e-admin-catalog",
      "source": "admin",
      "target": "catalog",
      "relation": "IMPORTS",
      "findingIds": []
    },
    {
      "id": "e-admin-identity",
      "source": "admin",
      "target": "identity",
      "relation": "CALLS",
      "findingIds": []
    },
    {
      "id": "e-webhook-payments",
      "source": "webhook",
      "target": "payments",
      "relation": "IMPORTS",
      "findingIds": []
    },
    {
      "id": "e-webhook-orders",
      "source": "webhook",
      "target": "orders",
      "relation": "CALLS",
      "findingIds": [
        "arch-101"
      ]
    },
    {
      "id": "e-orders-orderstore",
      "source": "orders",
      "target": "orderstore",
      "relation": "IMPORTS",
      "findingIds": [
        "arch-101"
      ]
    },
    {
      "id": "e-orders-payments",
      "source": "orders",
      "target": "payments",
      "relation": "IMPORTS",
      "findingIds": [
        "arch-003",
        "arch-101"
      ]
    },
    {
      "id": "e-payments-orders",
      "source": "payments",
      "target": "orders",
      "relation": "IMPORTS",
      "findingIds": [
        "arch-003",
        "arch-101"
      ]
    },
    {
      "id": "e-orders-audit",
      "source": "orders",
      "target": "audit",
      "relation": "CALLS",
      "findingIds": [
        "arch-101"
      ]
    },
    {
      "id": "e-catalog-productindex",
      "source": "catalog",
      "target": "productindex",
      "relation": "IMPORTS",
      "findingIds": []
    },
    {
      "id": "e-payments-gateway",
      "source": "payments",
      "target": "gateway",
      "relation": "IMPORTS",
      "findingIds": []
    },
    {
      "id": "e-payments-audit",
      "source": "payments",
      "target": "audit",
      "relation": "CALLS",
      "findingIds": []
    },
    {
      "id": "e-identity-audit",
      "source": "identity",
      "target": "audit",
      "relation": "IMPORTS",
      "findingIds": []
    }
  ],
  "findings": [
    {
      "id": "arch-001",
      "rule": "ARCH001",
      "namespace": "ARCH",
      "title": {
        "ru": "Checkout импортирует запрещённую зависимость",
        "en": "Checkout imports a forbidden dependency"
      },
      "description": {
        "ru": "Разрешённый статический импорт напрямую связывает CheckoutController с OrderRepository. Явное правило запрещает зависимости входного слоя от инфраструктуры.",
        "en": "A resolved static import connects Checkout to the Order store adapter. An explicit synthetic forbidden-dependency policy prohibits interface → infrastructure imports; this edge violates that policy."
      },
      "severity": "HIGH",
      "status": "CONFIRMED",
      "detector": "STATIC",
      "nodeIds": [
        "checkout",
        "orderstore"
      ],
      "edgeIds": [
        "e-checkout-orderstore"
      ],
      "recommendation": {
        "ru": "Перенесите операцию хранения за границу OrderService; Checkout должен зависеть от прикладного контракта.",
        "en": "Move the persistence operation behind Orders and let Checkout call the application boundary."
      },
      "evidence": [
        {
          "id": "a1-policy",
          "type": "ARCHITECTURE_RULE",
          "title": {
            "ru": "Явное правило запрещённой зависимости",
            "en": "Explicit forbidden-dependency policy"
          },
          "detail": {
            "ru": "Демонстрационная политика явно запрещает эту зависимость. Показанная нотация не является исполняемой схемой ArchGuard.",
            "en": "The demo policy explicitly forbids this dependency. This illustrative policy notation is not an executable ArchGuard configuration schema."
          },
          "path": "demo/policies/forbidden-dependency.example.yaml",
          "line": 3,
          "startLine": 1,
          "code": [
            "# Illustrative policy notation; not an executable schema",
            "rule: ARCH001",
            "forbid:",
            "  from: interface",
            "  to: infrastructure",
            "  relation: IMPORTS"
          ]
        },
        {
          "id": "a1-source",
          "type": "STATIC_RULE",
          "title": {
            "ru": "Разрешённый прямой импорт",
            "en": "Resolved direct import"
          },
          "detail": {
            "ru": "Относительный импорт разрешается в инфраструктурный OrderRepository.",
            "en": "The relative module specifier resolves to the Order store adapter."
          },
          "path": "src/interface/checkout.ts",
          "line": 3,
          "startLine": 1,
          "code": [
            "import type { Request, Response } from 'express';",
            "import { authorizeCheckout } from '../application/identity';",
            "import { orderStore } from '../infrastructure/order-store';",
            "",
            "export async function checkout(req: Request, res: Response) {",
            "  authorizeCheckout(req);",
            "  const order = await orderStore.create(req.body);",
            "  res.json(order);",
            "}"
          ]
        }
      ]
    },
    {
      "id": "arch-003",
      "rule": "ARCH003",
      "namespace": "ARCH",
      "title": {
        "ru": "Заказы и платежи образуют цикл",
        "en": "Orders and Payments form a dependency cycle"
      },
      "description": {
        "ru": "Два разрешённых импорта образуют OrderService → PaymentService → OrderService. Нарушено явное правило отсутствия циклов. Порядок runtime-вызовов не выводится.",
        "en": "Two resolved module imports create Orders → Payments → Orders, violating an explicit synthetic no-cycle policy for application modules. This is a static dependency cycle; runtime call order is not inferred."
      },
      "severity": "MEDIUM",
      "status": "CONFIRMED",
      "detector": "STATIC",
      "nodeIds": [
        "orders",
        "payments"
      ],
      "edgeIds": [
        "e-orders-payments",
        "e-payments-orders"
      ],
      "recommendation": {
        "ru": "Выделите координацию в отдельную границу или инвертируйте одну зависимость через явный порт.",
        "en": "Move shared coordination into a separate application boundary or invert one dependency through an explicit port."
      },
      "evidence": [
        {
          "id": "a3-policy",
          "type": "ARCHITECTURE_RULE",
          "title": {
            "ru": "Явное правило отсутствия циклов",
            "en": "Explicit no-cycle policy"
          },
          "detail": {
            "ru": "Цикл нарушает явно заданное ограничение. Нотация политики демонстрационная, не готовый architecture.yaml.",
            "en": "The demo policy prohibits import cycles within application modules. This illustrative policy notation is not an executable ArchGuard configuration schema."
          },
          "path": "demo/policies/no-cycle.example.yaml",
          "line": 3,
          "startLine": 1,
          "code": [
            "# Illustrative policy notation; not an executable schema",
            "rule: ARCH003",
            "forbid_cycles:",
            "  within: application",
            "  relation: IMPORTS"
          ]
        },
        {
          "id": "a3-orders",
          "type": "STATIC_RULE",
          "title": {
            "ru": "Orders импортирует Payments",
            "en": "Orders imports Payments"
          },
          "detail": {
            "ru": "Первое направленное ребро статического цикла.",
            "en": "First edge of the resolved module cycle."
          },
          "path": "src/application/orders.ts",
          "line": 2,
          "startLine": 1,
          "code": [
            "import { orderStore } from '../infrastructure/order-store';",
            "import { capturePayment } from './payments';",
            "import { appendAudit } from '../infrastructure/audit-log';"
          ]
        },
        {
          "id": "a3-payments",
          "type": "STATIC_RULE",
          "title": {
            "ru": "Payments импортирует Orders",
            "en": "Payments imports Orders"
          },
          "detail": {
            "ru": "Обратное ребро замыкает цикл двух модулей.",
            "en": "Return edge closes the same two-module cycle."
          },
          "path": "src/application/payments.ts",
          "line": 2,
          "startLine": 1,
          "code": [
            "import { paymentGateway } from '../infrastructure/payment-gateway';",
            "import { markOrderPaid } from './orders';",
            "import { appendAudit } from '../infrastructure/audit-log';"
          ]
        }
      ]
    },
    {
      "id": "arch-101",
      "rule": "ARCH101",
      "namespace": "ARCH",
      "title": {
        "ru": "Избыточная связанность OrderService",
        "en": "Excessive coupling candidate in Orders"
      },
      "description": {
        "ru": "Шесть соседей и семь направленных отношений делают OrderService кандидатом для проверки. Связанность сама по себе не доказывает архитектурное нарушение.",
        "en": "Orders is connected to six other modules in this synthetic dependency graph. This excessive-coupling candidate requires contextual review; connectivity alone does not confirm an architectural violation."
      },
      "severity": null,
      "status": "CANDIDATE",
      "detector": "GRAPH",
      "nodeIds": [
        "orders"
      ],
      "edgeIds": [
        "e-checkout-orders",
        "e-admin-orders",
        "e-webhook-orders",
        "e-orders-orderstore",
        "e-orders-payments",
        "e-payments-orders",
        "e-orders-audit"
      ],
      "recommendation": {
        "ru": "Проверьте необходимость и владельца каждой зависимости, прежде чем менять границы.",
        "en": "Review the necessity and ownership of these dependencies before changing the application boundary."
      },
      "evidence": [
        {
          "id": "a101-context",
          "type": "GRAPH_METRIC",
          "title": {
            "ru": "Зависимости для проверки",
            "en": "Dependencies to review"
          },
          "detail": {
            "ru": "Исходный контекст служит основанием для обсуждения, но не для окончательного вывода.",
            "en": "The graph has six distinct direct neighbors and seven directed relationships. This illustrative source excerpt shows the three outgoing dependencies; contextual review is still required."
          },
          "path": "src/application/orders.ts",
          "line": 12,
          "startLine": 12,
          "code": [
            "export async function submitOrder(draft: OrderDraft) {",
            "  const order = await orderStore.create(draft);",
            "  await capturePayment(order.id);",
            "  await appendAudit('order.submitted', order.id);",
            "  return order;",
            "}"
          ]
        }
      ]
    },
    {
      "id": "sec-002",
      "rule": "SEC002",
      "namespace": "SEC",
      "title": {
        "ru": "Вход запроса достигает SQL-запроса",
        "en": "Request input reaches a SQL query"
      },
      "description": {
        "ru": "Значение типизированного Express request используется при построении строки для pg.query. Источник, преобразование и приёмник видны в одном синтетическом примере.",
        "en": "A typed Express request value flows directly into a pg query string in the synthetic local example. The source, string construction and SQL sink are all present."
      },
      "severity": "HIGH",
      "status": "SUPPORTED",
      "detector": "SECURITY_DATAFLOW",
      "nodeIds": [
        "admin",
        "orderstore"
      ],
      "edgeIds": [],
      "recommendation": {
        "ru": "Используйте постоянный SQL-шаблон и передавайте значение отдельно как связанный параметр.",
        "en": "Use a constant query template and pass the request value separately as a bound parameter."
      },
      "evidence": [
        {
          "id": "s2-source",
          "type": "DATA_FLOW",
          "title": {
            "ru": "Типизированный источник запроса",
            "en": "Typed request source"
          },
          "detail": {
            "ru": "Параметр запроса — недоверенный вход. Пример независим от модульного графа.",
            "en": "The request query value is untrusted input. This example is independent of the module dependency diagram."
          },
          "path": "demo/security/sql-route.ts",
          "line": 5,
          "startLine": 1,
          "code": [
            "import type { Request, Response } from 'express';",
            "import { Pool } from 'pg';",
            "const pool = new Pool();",
            "export async function search(req: Request, res: Response) {",
            "  const customer = req.query.customer;",
            "  const rows = await pool.query(",
            "    \"SELECT id FROM orders WHERE customer = '\" + customer + \"'\"",
            "  );",
            "  res.json(rows);",
            "}"
          ]
        },
        {
          "id": "s2-sink",
          "type": "DATA_FLOW",
          "title": {
            "ru": "SQL-приёмник pg.query",
            "en": "pg query receives constructed SQL"
          },
          "detail": {
            "ru": "На локальном пути нет отдельного связывания параметров. Доказательство не подтверждает exploitability.",
            "en": "No separate parameter binding appears on this local source-to-sink path. Evidence does not establish exploitability."
          },
          "path": "demo/security/sql-route.ts",
          "line": 6,
          "startLine": 5,
          "code": [
            "  const customer = req.query.customer;",
            "  const rows = await pool.query(",
            "    \"SELECT id FROM orders WHERE customer = '\" + customer + \"'\"",
            "  );"
          ]
        }
      ],
      "flow": [
        {
          "label": {
            "ru": "Вход запроса",
            "en": "Request input"
          },
          "detail": {
            "ru": "Типизированный Express Request",
            "en": "Typed Express Request"
          },
          "state": "known",
          "path": "demo/security/sql-route.ts",
          "line": 5
        },
        {
          "label": {
            "ru": "Построение SQL",
            "en": "SQL construction"
          },
          "detail": {
            "ru": "Значение включено в строку",
            "en": "Value enters a string"
          },
          "state": "known",
          "path": "demo/security/sql-route.ts",
          "line": 5
        },
        {
          "label": {
            "ru": "SQL-приёмник",
            "en": "SQL sink"
          },
          "detail": {
            "ru": "pg.query без параметров",
            "en": "pg.query without parameters"
          },
          "state": "known",
          "path": "demo/security/sql-route.ts",
          "line": 6
        }
      ]
    },
    {
      "id": "sec-006",
      "rule": "SEC006",
      "namespace": "SEC",
      "title": {
        "ru": "Назначение запроса требует проверки",
        "en": "Outbound destination needs more evidence"
      },
      "description": {
        "ru": "Известный вход запроса проходит через неизвестную URL-обёртку к HTTPS-приёмнику. Неполный путь остаётся потенциальной проблемой.",
        "en": "A known request value reaches an unresolved URL wrapper before a Node HTTPS sink. The wrapper interrupts a complete source-to-sink proof, so the result remains potential."
      },
      "severity": "MEDIUM",
      "status": "POTENTIAL",
      "detector": "SECURITY_DATAFLOW",
      "nodeIds": [
        "webhook",
        "gateway"
      ],
      "edgeIds": [],
      "recommendation": {
        "ru": "Изучите URL-обёртку и разрешённые назначения. DNS и перенаправления требуют отдельной проверки.",
        "en": "Inspect the unresolved wrapper and enforce an explicit destination policy. DNS resolution and redirects require separate review."
      },
      "evidence": [
        {
          "id": "s6-source",
          "type": "DATA_FLOW",
          "title": {
            "ru": "Известные источник и приёмник",
            "en": "Known source and outbound sink"
          },
          "detail": {
            "ru": "Тело импортированной обёртки отсутствует в этой области анализа.",
            "en": "The imported wrapper body is absent from this synthetic analysis scope."
          },
          "path": "demo/security/preview-route.ts",
          "line": 6,
          "startLine": 1,
          "code": [
            "import type { Request } from 'express';",
            "import https from 'node:https';",
            "import { prepareDestination } from './external-wrapper';",
            "",
            "export function preview(req: Request) {",
            "  const destination = prepareDestination(req.query.url);",
            "  return https.get(destination);",
            "}"
          ]
        },
        {
          "id": "s6-gap",
          "type": "DATA_FLOW",
          "title": {
            "ru": "Неизвестная граница преобразования",
            "en": "Unresolved propagation boundary"
          },
          "detail": {
            "ru": "prepareDestination может ограничивать URL. Поведение неизвестно; безопасность и полный небезопасный поток не выводятся.",
            "en": "prepareDestination may transform or restrict the URL. Its behavior is unknown; neither safety nor a complete unsafe flow is inferred."
          },
          "path": "demo/security/preview-route.ts",
          "line": 6,
          "startLine": 6,
          "code": [
            "  const destination = prepareDestination(req.query.url);",
            "  return https.get(destination);"
          ]
        }
      ],
      "flow": [
        {
          "label": {
            "ru": "Вход запроса",
            "en": "Request input"
          },
          "detail": {
            "ru": "Типизированный Express Request",
            "en": "Typed Express Request"
          },
          "state": "known",
          "path": "demo/security/preview-route.ts",
          "line": 6
        },
        {
          "label": {
            "ru": "Граница неизвестна",
            "en": "Unknown boundary"
          },
          "detail": {
            "ru": "Поведение обёртки не установлено",
            "en": "Wrapper behavior is not established"
          },
          "state": "unknown",
          "path": "demo/security/preview-route.ts",
          "line": 6
        },
        {
          "label": {
            "ru": "HTTPS-приёмник",
            "en": "HTTPS sink"
          },
          "detail": {
            "ru": "node:https.get",
            "en": "node:https.get"
          },
          "state": "known",
          "path": "demo/security/preview-route.ts",
          "line": 6
        }
      ]
    },
    {
      "id": "sec-007",
      "rule": "SEC007",
      "namespace": "SEC",
      "title": {
        "ru": "Источник HTML-содержимого не установлен",
        "en": "HTML sink lacks a known input origin"
      },
      "description": {
        "ru": "Типизированный DOM-приёмник известен, но источник содержимого скрыт в неизвестном загрузчике. Доказательств небезопасного потока недостаточно.",
        "en": "A typed DOM HTML sink is visible, but the value comes from an unresolved loader. There is insufficient evidence to establish an untrusted source or a complete flow."
      },
      "severity": "MEDIUM",
      "status": "INSUFFICIENT_EVIDENCE",
      "detector": "SECURITY_DATAFLOW",
      "nodeIds": [
        "storefront"
      ],
      "edgeIds": [],
      "recommendation": {
        "ru": "Изучите загрузчик и контекст HTML-вывода. При недоверенном источнике подтвердите подходящую границу очистки.",
        "en": "Inspect the loader and the exact rendering context, then confirm a context-appropriate sanitization boundary if untrusted content is possible."
      },
      "evidence": [
        {
          "id": "s7-sink",
          "type": "DATA_FLOW",
          "title": {
            "ru": "HTML-присваивание с неизвестным источником",
            "en": "HTML assignment with unknown origin"
          },
          "detail": {
            "ru": "Известный HTML-приёмник не доказывает XSS без установленного источника.",
            "en": "A visible HTML sink alone does not prove XSS. The loader implementation is outside the supplied scope."
          },
          "path": "demo/security/render-card.ts",
          "line": 5,
          "startLine": 1,
          "code": [
            "import { loadCardMarkup } from './external-loader';",
            "",
            "export function renderCard(target: HTMLElement) {",
            "  const content = loadCardMarkup();",
            "  target.innerHTML = content;",
            "}"
          ]
        },
        {
          "id": "s7-gap",
          "type": "DATA_FLOW",
          "title": {
            "ru": "Источник и очистка не установлены",
            "en": "Source and sanitizer context unresolved"
          },
          "detail": {
            "ru": "Источник запроса и проверенный sanitizer не установлены. Неизвестное значение не считается безопасным.",
            "en": "No request source or verified sanitizer is established. Unknown input is not silently treated as safe."
          },
          "path": "demo/security/render-card.ts",
          "line": 4,
          "startLine": 4,
          "code": [
            "  const content = loadCardMarkup();",
            "  target.innerHTML = content;"
          ]
        }
      ],
      "flow": [
        {
          "label": {
            "ru": "Неизвестный источник",
            "en": "Unknown source"
          },
          "detail": {
            "ru": "loadCardMarkup: тело отсутствует",
            "en": "loadCardMarkup: body unavailable"
          },
          "state": "unknown",
          "path": "demo/security/render-card.ts",
          "line": 5
        },
        {
          "label": {
            "ru": "Граница неизвестна",
            "en": "Unknown boundary"
          },
          "detail": {
            "ru": "Поведение обёртки не установлено",
            "en": "Wrapper behavior is not established"
          },
          "state": "unknown",
          "path": "demo/security/render-card.ts",
          "line": 5
        },
        {
          "label": {
            "ru": "HTML-приёмник",
            "en": "HTML sink"
          },
          "detail": {
            "ru": "target.innerHTML",
            "en": "target.innerHTML"
          },
          "state": "known",
          "path": "demo/security/render-card.ts",
          "line": 4
        }
      ]
    }
  ],
  "coverage": [
    {
      "rule": "SEC001",
      "name": {
        "ru": "Секрет в исходном коде",
        "en": "Hardcoded Secret"
      },
      "outcome": "PARTIAL",
      "status": "PARTIAL",
      "scope": {
        "ru": "Ограниченные литеральные паттерны",
        "en": "Synthetic source literal patterns"
      },
      "detail": {
        "ru": "Показанных находок нет. Ограниченная проверка литералов не гарантирует отсутствие секретов. Секретные значения не включены.",
        "en": "No finding is illustrated. Literal pattern coverage is bounded; absence of findings is not a security guarantee. No secret values are included."
      }
    },
    {
      "rule": "SEC002",
      "name": {
        "ru": "Риск SQL-инъекции",
        "en": "SQL Injection Risk"
      },
      "outcome": "DEFINITIVE_POSITIVE",
      "status": "SUPPORTED",
      "scope": {
        "ru": "Один локальный Express → pg пример",
        "en": "One local Express → pg example"
      },
      "detail": {
        "ru": "Доказательство связывает запрос, построение SQL и приёмник. Положительный результат не означает полноту проверки репозитория или доказанную эксплуатацию.",
        "en": "A supported finding binds the request source, SQL construction and query sink. Positive evidence does not imply complete repository coverage or confirmed exploitability."
      }
    },
    {
      "rule": "SEC003",
      "name": {
        "ru": "Риск инъекции команды",
        "en": "Command Injection Risk"
      },
      "outcome": "PARTIAL",
      "status": "PARTIAL",
      "scope": {
        "ru": "Подмножество process/shell API",
        "en": "Modeled process and shell API subset"
      },
      "detail": {
        "ru": "Проверка частичная. Семантика executable, operands и shell требует отдельных оснований.",
        "en": "Execution remains partial. A zero-finding result would not certify command safety; executable, operand and shell semantics require separate evidence."
      }
    },
    {
      "rule": "SEC004",
      "name": {
        "ru": "Риск обхода пути",
        "en": "Path Traversal Risk"
      },
      "outcome": "PARTIAL",
      "status": "PARTIAL",
      "scope": {
        "ru": "Лексическая модель ограничения путей",
        "en": "Bounded lexical path-confinement model"
      },
      "detail": {
        "ru": "Полного сертификата нет. Symlink, race и realpath находятся вне данной модели.",
        "en": "No complete scope certificate is available. Symlinks, races and filesystem realpath behavior are outside this modeled proof subset."
      }
    },
    {
      "rule": "SEC005",
      "name": {
        "ru": "Небезопасная десериализация",
        "en": "Unsafe Deserialization"
      },
      "outcome": "UNSUPPORTED",
      "status": "UNSUPPORTED",
      "scope": {
        "ru": "TypeScript: только контракт",
        "en": "TypeScript: contract only"
      },
      "detail": {
        "ru": "Для TypeScript правило не выполняется. Обычный JSON parsing не считается небезопасной десериализацией объектов.",
        "en": "Not evaluated for TypeScript. The declared rule is not an executable TypeScript capability. Ordinary JSON parsing is not classified as an unsafe object-deserialization sink."
      }
    },
    {
      "rule": "SEC006",
      "name": {
        "ru": "Риск SSRF",
        "en": "Server-Side Request Forgery Risk"
      },
      "outcome": "POTENTIAL",
      "status": "POTENTIAL",
      "scope": {
        "ru": "Один request URL → HTTPS пример",
        "en": "One request URL / HTTPS example"
      },
      "detail": {
        "ru": "Неизвестная URL-обёртка прерывает доказанный поток. DNS и redirects не сертифицированы.",
        "en": "An unresolved URL wrapper interrupts the flow proof. The candidate remains nondefinitive; DNS, redirects and broader destination policy are not certified."
      }
    },
    {
      "rule": "SEC007",
      "name": {
        "ru": "Риск XSS",
        "en": "Cross-Site Scripting Risk"
      },
      "outcome": "INSUFFICIENT_EVIDENCE",
      "status": "INSUFFICIENT_EVIDENCE",
      "scope": {
        "ru": "Один типизированный DOM-приёмник",
        "en": "One typed DOM HTML sink"
      },
      "detail": {
        "ru": "Источник и контекст очистки неизвестны. Одного приёмника недостаточно для unsafe source-to-sink вывода.",
        "en": "The input source and sanitizer context are unresolved. A sink alone is insufficient to establish an unsafe source-to-sink path."
      }
    },
    {
      "rule": "SEC008",
      "name": {
        "ru": "Слабая криптография",
        "en": "Weak Cryptography"
      },
      "outcome": "DEFINITIVE_NEGATIVE",
      "status": "COMPLETE",
      "scope": {
        "ru": "Один изолированный crypto source unit",
        "en": "One isolated synthetic crypto source unit"
      },
      "detail": {
        "ru": "В этой области слабый алгоритм не выбран: один default crypto import и один литеральный sha256 call. Другие файлы и безопасность проекта не проверены.",
        "en": "No weak algorithm in this certified scope: exactly one default crypto import and one direct literal sha256 selection. This says nothing about other files, cryptographic use, or repository safety."
      },
      "certificate": {
        "version": "security-completeness-v3",
        "rule_id": "SEC008",
        "language": "TYPESCRIPT",
        "declared_scope": "Entire supplied source: one default node:crypto import and one literal-only createHash call; no other statements, callbacks, branches or calls.",
        "applicable": true,
        "scope_complete": true,
        "source_coverage_complete": true,
        "sink_coverage_complete": true,
        "call_resolution_complete": true,
        "summary_resolution_complete": true,
        "dataflow_scope_complete": true,
        "framework_model_complete": true,
        "unsupported_constructs_present": false,
        "analysis_failures_present": false,
        "proofs_sufficient": true,
        "reason_codes": [
          "CLOSED_LITERAL_CRYPTO_SCOPE"
        ],
        "certificate_status": "COMPLETE",
        "synthetic": true,
        "path": "demo/security/isolated-hash.ts",
        "startLine": 1,
        "code": [
          "import crypto from 'node:crypto';",
          "crypto.createHash('sha256');"
        ]
      }
    },
    {
      "rule": "SEC009",
      "name": {
        "ru": "Небезопасная случайность",
        "en": "Insecure Randomness"
      },
      "outcome": "PARTIAL",
      "status": "PARTIAL",
      "scope": {
        "ru": "Известные PRNG и чувствительные применения",
        "en": "Modeled PRNG calls and sensitive uses"
      },
      "detail": {
        "ru": "Назначение произвольного downstream use неизвестно. UI-случайность сама по себе не является Security finding.",
        "en": "Arbitrary downstream purpose is unresolved. Ordinary simulation or interface randomness does not establish a security finding."
      }
    },
    {
      "rule": "SEC010",
      "name": {
        "ru": "Динамическое выполнение кода",
        "en": "Unsafe Dynamic Code Execution"
      },
      "outcome": "PARTIAL",
      "status": "PARTIAL",
      "scope": {
        "ru": "Отдельные eval / Function / script API",
        "en": "Selected eval / Function / script APIs"
      },
      "detail": {
        "ru": "Неизвестные интерпретаторы и обёртки остаются частичными. Константные выражения не объявляются небезопасными автоматически.",
        "en": "Unknown interpreters and wrappers remain partial. Constant expressions and callback timers are not automatically unsafe dynamic-execution sinks."
      }
    }
  ],
  "kind": "DEMO",
  "provenance": {
    "synthetic": true,
    "status": "PARTIAL",
    "snapshot": "demo-snapshot-001",
    "providerCalls": 0
  },
  "diagnostics": []
};
