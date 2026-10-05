# LLM provider boundary

Domain `LLMProvider` protocol: provider/model identity, `ProviderCapabilities`, non-network exact
`count_input_tokens(request)` (nullable) и `complete_structured(request)`.
Request содержит system instructions, structured task, explicitly untrusted context, strict response
schema, timeout/output budget и versions. Response содержит bounded structured JSON, actual identity,
optional operational request ID и nullable `LLMUsage`. Vendor HTTP/SDK types остаются вне domain.
Custom adapters обязаны соблюдать timeout, bounded response и source-free diagnostics.

## Реальный adapter

`OpenAIResponsesProvider` использует stdlib HTTPS к фиксированному
`https://api.openai.com/v1/responses`; дополнительных dependencies нет. JSON Schema передаётся через
`text.format` с `strict=true` по [официальной Structured Outputs документации](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).
System/user messages разделены; `store:false`, output token budget и transport timeout передаются
явно. HTTP redirects запрещены; key не может перейти к другому endpoint через redirect.
Ответ ограничен 256 KiB, semantic JSON — 32768 characters. Incomplete/refusal/malformed responses,
401/403/429/5xx/connection/timeout получают typed sanitized diagnostics. Automatic retries отсутствуют.
Модель должна поддерживать этот формат; default model не придуман. Actual model возвращается из
response metadata, requested model остаётся входной конфигурацией. Local tokenizer и cost calculation
не реализованы; usage копируется только из provider response. Отсутствующая usage остаётся null.

## Privacy и configuration

Remote AI по умолчанию отключён: `AIAnalysisConfig.allow_remote_source=false`.
CLI требует `--allow-remote-ai` для каждого real analysis; JSON profile не может заменить этот flag.
Без opt-in возможно только локальное построение context/manifest и zero remote calls.
Programmatic caller должен явно установить config opt-in для remote-capable provider.

Provider не конфигурирован → None/UNAVAILABLE, missing credentials/model →
`AI_PROVIDER_CONFIGURATION_REQUIRED`. Production fake/random provider отсутствует.
Settings читают environment, не требуют keys для application startup или offline tests:

```text
ARCHGUARD_AI_PROVIDER=openai
ARCHGUARD_AI_MODEL=<your structured-output model>
ARCHGUARD_AI_API_KEY=<configured privately in environment>
```

Не помещать key в CLI arguments, repo, profile, artifacts или logs. `.env.example` содержит только
commented placeholders; этот adapter сам не загружает `.env`. Credentials представлены `SecretStr`.
Explicit command при настроенном environment:

```bash
archguard ai analyze <synthetic-repository> --target <qualified-node-name> \
  --provider openai --model <configured-model> --allow-remote-ai --json
```

Этот command передаёт source выбранного bounded pack внешнему provider. `store:false` — request option,
не обещание полного удаления данных у provider. Default redaction/secret scan отсутствуют;
пользователь выбирает допустимый synthetic/private input и optional explicit redactor.
Локальные default exports не содержат source fields; free text модели остаётся недоверенным,
validation не является универсальной защитой от утечки/галлюцинации.

## Offline verification и ограничения

`tests/helpers/scripted_llm.py` существует только в test tree. Scripted provider получает реальные
requests через DI и выдаёт фиксированные assessments/errors. Tests проверяют all rules/decisions,
privacy gates, injected comments, strict validation, call/token budgets и partial failures.
Wire transport реального adapter stubbed до I/O; configured synthetic env key не включает сеть
без opt-in. Это pipeline verification, не LLM-quality benchmark.

Live smoke test не выполнялся: отдельный explicit opt-in на live synthetic invocation не дан.
Это не failure. Runtime response latency и real LLM output не являются deterministic artifacts.
Transport timeout ограничивает сетевые операции; analyzer отклоняет результат после deadline,
но не может принудительно прервать произвольный custom synchronous provider, нарушающий port contract.
Калибровка, provider-specific tokenizer, billed cost, streaming, retries и multi-provider adapters
остаются будущей работой.
