/* Wholly synthetic demonstration data. No repository source or scan results. */
window.DEMO = {
  metadata: {
    synthetic: true,
    name: 'Northstar Commerce',
    repository: 'northstar / commerce-platform',
    branch: 'demo/checkout-review',
    snapshot: 'Synthetic snapshot',
    language: 'TypeScript',
    analysis: 'Static imports and calls',
    disclaimer: 'Illustrative data only. No repository was scanned.',
    zeroFindingsIsSecurityGuarantee: false
  },
  nodes: [
    { id: 'storefront', label: 'Storefront API', layer: 'interface', role: 'Public product routes', path: 'src/interface/storefront.ts', x: 165, y: 135 },
    { id: 'checkout', label: 'Checkout API', layer: 'interface', role: 'Checkout route handlers', path: 'src/interface/checkout.ts', x: 165, y: 245 },
    { id: 'admin', label: 'Admin API', layer: 'interface', role: 'Operations routes', path: 'src/interface/admin.ts', x: 165, y: 355 },
    { id: 'webhook', label: 'Webhook API', layer: 'interface', role: 'Inbound event handlers', path: 'src/interface/webhooks.ts', x: 165, y: 465 },
    { id: 'orders', label: 'Order service', layer: 'application', role: 'Order orchestration', path: 'src/application/orders.ts', x: 505, y: 135 },
    { id: 'catalog', label: 'Catalog service', layer: 'application', role: 'Product discovery', path: 'src/application/catalog.ts', x: 505, y: 245 },
    { id: 'payments', label: 'Payment service', layer: 'application', role: 'Payment coordination', path: 'src/application/payments.ts', x: 505, y: 355 },
    { id: 'identity', label: 'Identity service', layer: 'application', role: 'Access decisions', path: 'src/application/identity.ts', x: 505, y: 465 },
    { id: 'orderstore', label: 'Order store', layer: 'infrastructure', role: 'PostgreSQL order adapter', path: 'src/infrastructure/order-store.ts', x: 845, y: 135 },
    { id: 'productindex', label: 'Product index', layer: 'infrastructure', role: 'Product search adapter', path: 'src/infrastructure/product-index.ts', x: 845, y: 245 },
    { id: 'gateway', label: 'Payment gateway', layer: 'infrastructure', role: 'Outbound payment adapter', path: 'src/infrastructure/payment-gateway.ts', x: 845, y: 355 },
    { id: 'audit', label: 'Audit log', layer: 'infrastructure', role: 'Append-only event adapter', path: 'src/infrastructure/audit-log.ts', x: 845, y: 465 }
  ],
  edges: [
    { id: 'e-storefront-catalog', source: 'storefront', target: 'catalog', relation: 'IMPORTS', violation: false },
    { id: 'e-storefront-identity', source: 'storefront', target: 'identity', relation: 'CALLS', violation: false },
    { id: 'e-checkout-orders', source: 'checkout', target: 'orders', relation: 'IMPORTS', violation: false },
    { id: 'e-checkout-identity', source: 'checkout', target: 'identity', relation: 'CALLS', violation: false },
    { id: 'e-checkout-orderstore', source: 'checkout', target: 'orderstore', relation: 'IMPORTS', violation: true },
    { id: 'e-admin-orders', source: 'admin', target: 'orders', relation: 'CALLS', violation: false },
    { id: 'e-admin-catalog', source: 'admin', target: 'catalog', relation: 'IMPORTS', violation: false },
    { id: 'e-admin-identity', source: 'admin', target: 'identity', relation: 'CALLS', violation: false },
    { id: 'e-webhook-payments', source: 'webhook', target: 'payments', relation: 'IMPORTS', violation: false },
    { id: 'e-webhook-orders', source: 'webhook', target: 'orders', relation: 'CALLS', violation: false },
    { id: 'e-orders-orderstore', source: 'orders', target: 'orderstore', relation: 'IMPORTS', violation: false },
    { id: 'e-orders-payments', source: 'orders', target: 'payments', relation: 'IMPORTS', violation: true },
    { id: 'e-payments-orders', source: 'payments', target: 'orders', relation: 'IMPORTS', violation: true },
    { id: 'e-orders-audit', source: 'orders', target: 'audit', relation: 'CALLS', violation: false },
    { id: 'e-catalog-productindex', source: 'catalog', target: 'productindex', relation: 'IMPORTS', violation: false },
    { id: 'e-payments-gateway', source: 'payments', target: 'gateway', relation: 'IMPORTS', violation: false },
    { id: 'e-payments-audit', source: 'payments', target: 'audit', relation: 'CALLS', violation: false },
    { id: 'e-identity-audit', source: 'identity', target: 'audit', relation: 'IMPORTS', violation: false }
  ],
  findings: [
    {
      id: 'arch-001', rule: 'ARCH001', namespace: 'ARCH',
      title: 'Checkout imports a forbidden dependency',
      description: 'A resolved static import connects Checkout to the Order store adapter. An explicit synthetic forbidden-dependency policy prohibits interface → infrastructure imports; this edge violates that policy.',
      severity: 'HIGH', status: 'CONFIRMED', detector: 'Deterministic rule',
      nodeIds: ['checkout', 'orderstore'], edgeIds: ['e-checkout-orderstore'],
      recommendation: 'Move the persistence operation behind Orders and let Checkout call the application boundary.',
      evidence: [
        { id: 'a1-policy', type: 'RULE', title: 'Explicit forbidden-dependency policy', detail: 'The demo policy explicitly forbids this dependency. This illustrative policy notation is not an executable ArchGuard configuration schema.', path: 'demo/policies/forbidden-dependency.example.yaml', line: 3, startLine: 1, code: ['# Illustrative policy notation; not an executable schema', 'rule: ARCH001', 'forbid:', '  from: interface', '  to: infrastructure', '  relation: IMPORTS'] },
        { id: 'a1-source', type: 'SOURCE', title: 'Resolved direct import', detail: 'The relative module specifier resolves to the Order store adapter.', path: 'src/interface/checkout.ts', line: 3, startLine: 1, code: ["import type { Request, Response } from 'express';", "import { authorizeCheckout } from '../application/identity';", "import { orderStore } from '../infrastructure/order-store';", '', 'export async function checkout(req: Request, res: Response) {', '  authorizeCheckout(req);', '  const order = await orderStore.create(req.body);', '  res.json(order);', '}'] }
      ]
    },
    {
      id: 'arch-003', rule: 'ARCH003', namespace: 'ARCH',
      title: 'Orders and Payments form a dependency cycle',
      description: 'Two resolved module imports create Orders → Payments → Orders, violating an explicit synthetic no-cycle policy for application modules. This is a static dependency cycle; runtime call order is not inferred.',
      severity: 'MEDIUM', status: 'CONFIRMED', detector: 'Deterministic rule',
      nodeIds: ['orders', 'payments'], edgeIds: ['e-orders-payments', 'e-payments-orders'],
      recommendation: 'Move shared coordination into a separate application boundary or invert one dependency through an explicit port.',
      evidence: [
        { id: 'a3-policy', type: 'RULE', title: 'Explicit no-cycle policy', detail: 'The demo policy prohibits import cycles within application modules. This illustrative policy notation is not an executable ArchGuard configuration schema.', path: 'demo/policies/no-cycle.example.yaml', line: 3, startLine: 1, code: ['# Illustrative policy notation; not an executable schema', 'rule: ARCH003', 'forbid_cycles:', '  within: application', '  relation: IMPORTS'] },
        { id: 'a3-orders', type: 'SOURCE', title: 'Orders imports Payments', detail: 'First edge of the resolved module cycle.', path: 'src/application/orders.ts', line: 2, startLine: 1, code: ["import { orderStore } from '../infrastructure/order-store';", "import { capturePayment } from './payments';", "import { appendAudit } from '../infrastructure/audit-log';"] },
        { id: 'a3-payments', type: 'SOURCE', title: 'Payments imports Orders', detail: 'Return edge closes the same two-module cycle.', path: 'src/application/payments.ts', line: 2, startLine: 1, code: ["import { paymentGateway } from '../infrastructure/payment-gateway';", "import { markOrderPaid } from './orders';", "import { appendAudit } from '../infrastructure/audit-log';"] }
      ]
    },
    {
      id: 'arch-101', rule: 'ARCH101', namespace: 'ARCH',
      title: 'Excessive coupling candidate in Orders',
      description: 'Orders is connected to six other modules in this synthetic dependency graph. This excessive-coupling candidate requires contextual review; connectivity alone does not confirm an architectural violation.',
      severity: null, status: 'CANDIDATE', detector: 'Structural graph candidate',
      nodeIds: ['orders'], edgeIds: ['e-checkout-orders', 'e-admin-orders', 'e-webhook-orders', 'e-orders-orderstore', 'e-orders-payments', 'e-payments-orders', 'e-orders-audit'],
      recommendation: 'Review the necessity and ownership of these dependencies before changing the application boundary.',
      evidence: [
        { id: 'a101-context', type: 'CONTEXT', title: 'Dependencies to review', detail: 'The graph has six distinct direct neighbors and seven directed relationships. This illustrative source excerpt shows the three outgoing dependencies; contextual review is still required.', path: 'src/application/orders.ts', line: 12, startLine: 12, code: ['export async function submitOrder(draft: OrderDraft) {', '  const order = await orderStore.create(draft);', '  await capturePayment(order.id);', "  await appendAudit('order.submitted', order.id);", '  return order;', '}'] }
      ]
    },
    {
      id: 'sec-002', rule: 'SEC002', namespace: 'SEC',
      title: 'Request input reaches a SQL query',
      description: 'A typed Express request value flows directly into a pg query string in the synthetic local example. The source, string construction and SQL sink are all present.',
      severity: 'HIGH', status: 'SUPPORTED', detector: 'Bounded static analysis',
      nodeIds: ['admin', 'orderstore'], edgeIds: [],
      recommendation: 'Use a constant query template and pass the request value separately as a bound parameter.',
      evidence: [
        { id: 's2-source', type: 'SOURCE', title: 'Typed request source', detail: 'The request query value is untrusted input. This example is independent of the module dependency diagram.', path: 'demo/security/sql-route.ts', line: 5, startLine: 1, code: ["import type { Request, Response } from 'express';", "import { Pool } from 'pg';", 'const pool = new Pool();', 'export async function search(req: Request, res: Response) {', '  const customer = req.query.customer;', '  const rows = await pool.query(', '    "SELECT id FROM orders WHERE customer = \'" + customer + "\'"', '  );', '  res.json(rows);', '}'] },
        { id: 's2-sink', type: 'SINK', title: 'pg query receives constructed SQL', detail: 'No separate parameter binding appears on this local source-to-sink path. Evidence does not establish exploitability.', path: 'demo/security/sql-route.ts', line: 6, startLine: 5, code: ['  const customer = req.query.customer;', '  const rows = await pool.query(', '    "SELECT id FROM orders WHERE customer = \'" + customer + "\'"', '  );'] }
      ]
    },
    {
      id: 'sec-006', rule: 'SEC006', namespace: 'SEC',
      title: 'Outbound destination needs more evidence',
      description: 'A known request value reaches an unresolved URL wrapper before a Node HTTPS sink. The wrapper interrupts a complete source-to-sink proof, so the result remains potential.',
      severity: 'MEDIUM', status: 'POTENTIAL', detector: 'Bounded static analysis',
      nodeIds: ['webhook', 'gateway'], edgeIds: [],
      recommendation: 'Inspect the unresolved wrapper and enforce an explicit destination policy. DNS resolution and redirects require separate review.',
      evidence: [
        { id: 's6-source', type: 'SOURCE', title: 'Known source and outbound sink', detail: 'The imported wrapper body is absent from this synthetic analysis scope.', path: 'demo/security/preview-route.ts', line: 6, startLine: 1, code: ["import type { Request } from 'express';", "import https from 'node:https';", "import { prepareDestination } from './external-wrapper';", '', 'export function preview(req: Request) {', '  const destination = prepareDestination(req.query.url);', '  return https.get(destination);', '}'] },
        { id: 's6-gap', type: 'UNKNOWN_FLOW', title: 'Unresolved propagation boundary', detail: 'prepareDestination may transform or restrict the URL. Its behavior is unknown; neither safety nor a complete unsafe flow is inferred.', path: 'demo/security/preview-route.ts', line: 6, startLine: 6, code: ['  const destination = prepareDestination(req.query.url);', '  return https.get(destination);'] }
      ]
    },
    {
      id: 'sec-007', rule: 'SEC007', namespace: 'SEC',
      title: 'HTML sink lacks a known input origin',
      description: 'A typed DOM HTML sink is visible, but the value comes from an unresolved loader. There is insufficient evidence to establish an untrusted source or a complete flow.',
      severity: 'MEDIUM', status: 'INSUFFICIENT_EVIDENCE', detector: 'Bounded static analysis',
      nodeIds: ['storefront'], edgeIds: [],
      recommendation: 'Inspect the loader and the exact rendering context, then confirm a context-appropriate sanitization boundary if untrusted content is possible.',
      evidence: [
        { id: 's7-sink', type: 'SINK', title: 'HTML assignment with unknown origin', detail: 'A visible HTML sink alone does not prove XSS. The loader implementation is outside the supplied scope.', path: 'demo/security/render-card.ts', line: 5, startLine: 1, code: ["import { loadCardMarkup } from './external-loader';", '', 'export function renderCard(target: HTMLElement) {', '  const content = loadCardMarkup();', '  target.innerHTML = content;', '}'] },
        { id: 's7-gap', type: 'UNKNOWN_FLOW', title: 'Source and sanitizer context unresolved', detail: 'No request source or verified sanitizer is established. Unknown input is not silently treated as safe.', path: 'demo/security/render-card.ts', line: 4, startLine: 4, code: ['  const content = loadCardMarkup();', '  target.innerHTML = content;'] }
      ]
    }
  ],
  coverage: [
    { rule: 'SEC001', name: 'Hardcoded Secret', outcome: 'PARTIAL', status: 'PARTIAL', scope: 'Synthetic source literal patterns', detail: 'No finding is illustrated. Literal pattern coverage is bounded; absence of findings is not a security guarantee. No secret values are included.' },
    { rule: 'SEC002', name: 'SQL Injection Risk', outcome: 'DEFINITIVE_POSITIVE', status: 'SUPPORTED', scope: 'One local Express → pg example', detail: 'A supported finding binds the request source, SQL construction and query sink. Positive evidence does not imply complete repository coverage or confirmed exploitability.' },
    { rule: 'SEC003', name: 'Command Injection Risk', outcome: 'PARTIAL', status: 'PARTIAL', scope: 'Modeled process and shell API subset', detail: 'Execution remains partial. A zero-finding result would not certify command safety; executable, operand and shell semantics require separate evidence.' },
    { rule: 'SEC004', name: 'Path Traversal Risk', outcome: 'PARTIAL', status: 'PARTIAL', scope: 'Bounded lexical path-confinement model', detail: 'No complete scope certificate is available. Symlinks, races and filesystem realpath behavior are outside this modeled proof subset.' },
    { rule: 'SEC005', name: 'Unsafe Deserialization', outcome: 'UNSUPPORTED', status: 'UNSUPPORTED', scope: 'TypeScript: contract only', detail: 'Not evaluated for TypeScript. The declared rule is not an executable TypeScript capability. Ordinary JSON parsing is not classified as an unsafe object-deserialization sink.' },
    { rule: 'SEC006', name: 'Server-Side Request Forgery Risk', outcome: 'POTENTIAL', status: 'POTENTIAL', scope: 'One request URL / HTTPS example', detail: 'An unresolved URL wrapper interrupts the flow proof. The candidate remains nondefinitive; DNS, redirects and broader destination policy are not certified.' },
    { rule: 'SEC007', name: 'Cross-Site Scripting Risk', outcome: 'INSUFFICIENT_EVIDENCE', status: 'INSUFFICIENT_EVIDENCE', scope: 'One typed DOM HTML sink', detail: 'The input source and sanitizer context are unresolved. A sink alone is insufficient to establish an unsafe source-to-sink path.' },
    {
      rule: 'SEC008', name: 'Weak Cryptography', outcome: 'DEFINITIVE_NEGATIVE', status: 'COMPLETE',
      scope: 'One isolated synthetic crypto source unit',
      detail: 'No weak algorithm in this certified scope: exactly one default crypto import and one direct literal sha256 selection. This says nothing about other files, cryptographic use, or repository safety.',
      certificate: {
        version: 'security-completeness-v3', rule_id: 'SEC008', language: 'TYPESCRIPT',
        declared_scope: 'Entire supplied source: one default node:crypto import and one literal-only createHash call; no other statements, callbacks, branches or calls.',
        applicable: true, scope_complete: true, source_coverage_complete: true,
        sink_coverage_complete: true, call_resolution_complete: true,
        summary_resolution_complete: true, dataflow_scope_complete: true,
        framework_model_complete: true, unsupported_constructs_present: false,
        analysis_failures_present: false, proofs_sufficient: true,
        reason_codes: ['CLOSED_LITERAL_CRYPTO_SCOPE'], certificate_status: 'COMPLETE',
        synthetic: true, path: 'demo/security/isolated-hash.ts', startLine: 1,
        code: ["import crypto from 'node:crypto';", "crypto.createHash('sha256');"]
      }
    },
    { rule: 'SEC009', name: 'Insecure Randomness', outcome: 'PARTIAL', status: 'PARTIAL', scope: 'Modeled PRNG calls and sensitive uses', detail: 'Arbitrary downstream purpose is unresolved. Ordinary simulation or interface randomness does not establish a security finding.' },
    { rule: 'SEC010', name: 'Unsafe Dynamic Code Execution', outcome: 'PARTIAL', status: 'PARTIAL', scope: 'Selected eval / Function / script APIs', detail: 'Unknown interpreters and wrappers remain partial. Constant expressions and callback timers are not automatically unsafe dynamic-execution sinks.' }
  ]
};
