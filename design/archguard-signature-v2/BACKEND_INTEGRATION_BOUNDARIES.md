# V2 — Backend integration boundaries

17 октября 2026. Дизайн-прототип с локальными fixtures, runtime-guarded JSON import и узким additive dev bridge. Production backend/API contracts не изменены. Ни этот документ, ни доступный интерфейс не означают готовность production frontend.

## Три независимые вещи

| Объект | Реальное состояние |
|---|---|
| Dataset `LOCAL_DEMO` | Авторские synthetic nodes/findings/source/coverage. Demo run иллюстрирует этапы, не вызывает Python/provider |
| Dataset `LOCAL_RESULT` | Пользователь выбрал JSON; browser проверил поддержанный envelope и структурные связи. Демо-модель заменяется, не дополняет неизвестные части |
| Connection `LIVE_SYSTEM_ONLY` | Проверены два system endpoints. Не переводит dataset в live mode и не доказывает доступность анализа |

`LOCAL_RESULT` означает local import, **не верифицированную подлинность**. Adapter сохраняет `validation: PROTOTYPE_STRUCTURE_ONLY`, `fingerprints_verified: false`. Отсутствующий Security result остаётся отсутствующим; не заполнять его демонстрационными findings или нулевыми зелёными строками.

## Offline index и dev preview

`index.html` загружает локальные обычные scripts; dependencies и build installation не требуются. Offline mode предназначен для fixtures, локального исследования, выбора результата, локального экспорта и сохранения language/motion preferences. File-origin browser limitations могут ограничивать clipboard или system fetch: это не повод заявлять fake connection.

Для локального HTTP preview:

```sh
node design/archguard-signature-v2/dev-server.cjs --port 8779
```

С явно указанным уже запущенным backend:

```sh
node design/archguard-signature-v2/dev-server.cjs --port 8779 --backend http://127.0.0.1:8780
```

Команды показывают существующий dev-server; они не запускают Python app, не читают `.env`, не анализируют repository. Preview слушает только `127.0.0.1`; localhost hostname намеренно не принимается вместо точного Host. Static root — каталог V2; нет CLI option для произвольного root.

## Точная HTTP-поверхность

Canonical backend: `src/archguard/api/app.py:create_app`, response models в `src/archguard/api/schemas.py`.

| Canonical endpoint | Реальная схема | Чего не доказывает |
|---|---|---|
| `GET /health` | `{status: "ok"}` | Готовность анализаторов, очередь jobs, наличие project |
| `GET /api/v1/system/info` | `name:string`, `version:string`, `status:"foundation"`, `iam_schema_version:"1.0"`, `finding_schema_version:"1.0"` | Findings API, auth, history, reports, live source |

В native dev server существует **только additive** `GET /__bridge/system`, который объединяет реальные ответы:

```json
{"connection":"LIVE_SYSTEM_ONLY","health":{"status":"ok"},"system":{"name":"…","version":"…","status":"foundation","iam_schema_version":"1.0","finding_schema_version":"1.0"}}
```

Это маршрут инструмента preview, не новая canonical версия backend API. Он не принимает source/location/token/provider и не проксирует произвольные paths. GET route точен: query/trailing slash не расширяют контракт; HEAD этого route возвращает 405.

Без `--backend`: HTTP 503, `connection/error: BACKEND_ADAPTER_REQUIRED`. Недоступный/невалидный upstream: 502 `BACKEND_UNAVAILABLE` с безопасным code; timeout: 504. Никакого успешного mock fallback. UI должен сохранять прежний dataset и показать ограничение соединения.

## Ограничения dev bridge

- Backend URL: только `http`, literal loopback IPv4 `127.x.x.x` либо `[::1]`; без credentials, non-root path, query, hash; валидный port. Hostnames, public/private nonloopback IP, HTTPS и необычные числовые формы IP не принимаются.
- Ровно два upstream GET; redirects не следуются. JSON Content-Type, status 200, точный набор полей и literal versions/status проверяются.
- Максимум 64 KiB на upstream response, проверка declared length и streamed bytes; total timeout 3 s на запрос. Ошибка не сериализует body/stack/credentials.
- Static GET/HEAD; прочие методы 405. Request bodies запрещены. Host должен совпадать с `127.0.0.1:PORT`; Origin, если присутствует, должен совпадать с HTTP origin preview. CORS не открыт.
- Traversal, hidden path components, encoded separators, symlinks и неподдержанные file extensions не отдаются. Static serving ограничен artifact root; нет execute/upload/clone/provider endpoints.
- `Cache-Control: no-store`, nosniff, same-origin resource policy, no-referrer, deny framing. Сервер не журналирует project/source/response data.

Native tests `tests/server.test.cjs` прошли: 23 проверки/подпроверки с synthetic upstream, включая success, Host/Origin/method/path/symlink/redirect/schema/timeout/oversize. Это server validation, **не browser QA и не подтверждение реального Python backend run**. Реальную интеграцию следует проверять отдельно с уже согласованным безопасным server configuration.

## Import contract и ограничения доверия

`src/adapters.js:importArtifact` возвращает normalized view dataset либо `INVALID_ARTIFACT` с bounded reason. До rendering проверяются структура, recognized schema/version, размеры коллекций/строк, depth, dangerous keys, IDs, relative source paths, references и consistency для поддержанных семейств.

Поддержанные branches текущего adapter: IAM bare/CLI wrapper; GraphAnalysisResult; architecture_check/discovery wrappers; conformance result; Security result/report для recognized analyzer versions; Hybrid result; context manifest. Это **ограниченные browser view adapters**, не полные аналоги всех Python validators. Наличие schema branch не означает, что все вложенные функции продукта реализованы на экране.

| Граница | Проверка / честное отображение |
|---|---|
| Selected file budget | UX contract до 5 MiB; чтение только явно выбранного файла, в памяти вкладки. File-size gate должен проверяться до JSON parsing |
| Общий structure budget | Depth ≤25, visited values ≤100,000, string length ≤50,000; prohibited prototype keys |
| Graph view budget | До 500 nodes / 3,000 edges; endpoint IDs и известные relations валидируются |
| Источник | Canonical relative path; positive one-based coordinates; не открывать arbitrary local path из JSON |
| Graph proofs | Связность proof IDs/relation/location/provenance проверяется, но hash происхождения не вычисляется |
| Security evidence | Rule/version/language/source binding и evidence references; incomplete flow не получает SUPPORTED |
| Security negative | Imported zero-findings result остаётся PARTIAL; metadata не используется как доверенное доказательство certificate completeness |
| Hybrid | Cases/decisions/evidence/features связываются; deterministic proof и calibrated confidence не подменяются UI score |
| Unbound manifest | Отсутствующий project/snapshot binding остаётся UNBOUND; нельзя молча объединять с другим run |
| Raw artifact | Сохраняется в памяти для provenance/export; не отправляется на server и не сохраняется в localStorage |

Самостоятельно предоставленные hashes, IDs и source references — данные, не авторизация на чтение файлов и не криптографическое удостоверение. HTML text должен экранироваться. Нельзя запускать строки из recommendation, rule description, commands или source snippets.

## Native JS / JSDoc boundary

UI не требует TypeScript compiler. Рекомендуемые JSDoc contract names: `DataMode = LOCAL_DEMO | LOCAL_RESULT`; `SystemConnection` с самостоятельным state; `WorkspaceDataset` с project/kind/nodes/edges/findings/coverage/provenance/raw; отдельные `FindingView` и `CoverageView`. Эти aliases документируют интерфейс модулей; runtime guards остаются обязательными.

`LIVE_SYSTEM_ONLY` не является видом project analysis dataset. Frontend status conversion сохраняет исходный status/provenance. Неизвестный формат отклоняется или показывается как unsupported; не приводится к более уверенной интерпретации. Browser guards могут быть строже canonical backend, поэтому отказ импорта не равен признанию backend result невалидным.

## Чего пока нет

Нет browser repo clone/upload/intake endpoint, async analysis job contract, cancel endpoint, server history/diff, authentication/authorization, persisted projects, report service, source retrieval API, live policy editing или provider invocation route. Python library/CLI умеют больше, но кнопка не превращает внутренний callable в безопасный public API.

Onboarding Local/ZIP/Git валидирует формат и готовит quoted CLI command. Не проверяет remote availability, не обращается к filesystem path и не запускает clone. Экранные rule/config controls меняют локальное demo state. Session comparison сравнивает совместимые локальные records, не извлекает server history и не измеряет качество анализа.

Следующая интеграция требует отдельного versioned adapter, typed inputs/results/errors, source lifecycle, explicit identity/snapshot binding и безопасного выполнения jobs. Путь разработки и acceptance gates — `IMPLEMENTATION_ROADMAP.md`.
