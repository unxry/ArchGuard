# Platform / persistence / provider / research boundaries

Audit date: 2026-10-17. Public tracked Python sources inventoried by AST: 285 modules across 17 source groups; 111 tracked non-fixture test modules indexed. This is an inventory, not a claim that every line received manual review. Deep user-facing capability reviews are split between intake, architecture, Security and this platform review. No private runtime artifacts were opened.

| Capability | Classification | Implementation / callable boundary | Input → output | Test / limitation / UI |
|---|---|---|---|---|
| Liveness | API_EXPOSED | api/app.py:create_app / GET /health; api/schemas.py:HealthResponse | none → status=ok | tests/test_api.py; does not establish analysis availability; system-only connection |
| System/schema versions | API_EXPOSED | GET /api/v1/system/info; application/system.py:get_system_information | configured name → name/version/foundation/IAM1.0/Finding1.0 | API tests; no project results; show verified service identity |
| Settings | REAL_INTERNAL_ONLY | infrastructure/settings.py:Settings | explicit configuration/environment → typed immutable settings | tests/test_settings.py; no UI settings API; frontend preferences are separate. Audit did not instantiate Settings or read .env |
| Structured logging | REAL_INTERNAL_ONLY | infrastructure/logging.py:JsonFormatter, configure_logging; cli.py:main | sanitized records → JSON stderr | tests/test_logging.py; no hosted log-stream API; local run transcript only |
| Database foundation | IMPLEMENTED_BUT_NOT_EXPOSED | infrastructure/database/session.py:create_database, Database.transaction | SecretStr DSN → lazy SQLAlchemy engine/session | no application tables/migrations for result persistence; saved projects/history/auth unavailable |
| Report boundary | UNAVAILABLE | reports/__init__.py boundary only | no report service | browser JSON export is a new UI feature, not a backend reporting claim |
| OpenAI Responses adapter | REAL_INTERNAL_ONLY | infrastructure/llm_provider.py:OpenAIResponsesProvider.complete_structured | typed bounded request → response or typed error | tests/ai/test_provider.py; no redirects, bounded262144 response; frontend has no credentials or invocation control |
| Offline / remote consent | CLI_ONLY | ai_cli.py:execute_ai, hybrid_cli.py:execute_hybrid | dry-run / without-ai / explicit remote opt-in | context manifests and offline proof remain useful; no provider calls for design |
| Calibration / benchmark / OSS review tooling | RESEARCH_ONLY | benchmark_cli.py:benchmark_arguments/execute_benchmark; calibration_cli.py:calibration_arguments/execute_calibration; oss_cli.py:oss_arguments/execute_oss | frozen research inputs → evaluation/lineage artifacts | source symbol inventory only; no dataset/truth/answer keys inspected. Expose capability boundary, not an operational project workspace or effectiveness metrics |
| Authentication / collaboration / assignments / suppressions | UNAVAILABLE | no product service contracts | none | do not create fake user accounts, Git tokens or shared projects |
| Run persistence / cancellation / diff service | PROPOSED | no HTTP jobs lifecycle | needs immutable snapshot/run IDs and storage | session-only demo runs and local comparisons are labelled; backend adapter required |

The V2 additive development bridge is limited to fixed GET health/system requests against an explicitly supplied literal loopback address. It cannot clone, execute shell, upload source, run a provider, or execute analysis. Browser result import is separate from a connected live service and replaces demo data completely.
