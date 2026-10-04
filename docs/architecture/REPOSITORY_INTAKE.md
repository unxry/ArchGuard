# Repository Intake & Source Discovery — snapshot schema 1.0

Реализован physical repository subsystem. Он обнаруживает файлы и metadata; source text не
разбирается синтаксически, не выполняется и не отправляется наружу. Java/TypeScript/JavaScript
обнаружение не означает наличие language analyzers. IAM/Finding/Hybrid contracts и API foundation
сохранены; новые analysis endpoints, ORM tables и background jobs не добавлены.

## Architecture и lifecycle

```text
RepositoryInput
  → DiscoverRepository (application)
  → RepositorySource.materialize() (port)
    ├─ LocalDirectorySource
    ├─ ZipRepositorySource
    └─ GitRepositorySource
  → RepositoryWorkspace.discover() (shared scanner)
  → RepositorySnapshot (physical inventory, separate from IAM)
```

Ports/models/policy/errors: `src/archguard/repository/`; implementations:
`src/archguard/infrastructure/repository/`. Application не импортирует subprocess/zipfile/pathlib,
не выбирает команды Git и не открывает файлы напрямую. CLI — composition root с argparse и factory.

`DiscoverRepository.execute(input)` возвращает сериализуемую metadata после закрытия workspace.
`DiscoverRepository.open(input)` — context manager с snapshot и lazy workspace reader. Будущий
parser работает внутри этого context и вызывает `open_source_file(relative_path)`; binary,
generated, oversized, non-target и excluded files ему не выдаются. `open_file` допускает только
indexed regular files для будущих manifest/config consumers. Source content не включён в JSON.

Local source открывает read-only view выбранного root, без копирования потенциальных гигабайтов.
Local files не удаляются. ZIP/Git используют private system TemporaryDirectory `archguard-repo-*`,
с optional infrastructure-only workspace_parent. Handles закрываются перед cleanup. Очистка
работает при успехе, typed error и ошибке downstream consumer. После закрытия reader недоступен;
inventory metadata остаётся пригодной для storage/reporting. Runtime root не сериализуется.

## Contracts и identity

`RepositorySnapshot`: schema 1.0, content-derived SnapshotId, optional caller-owned RepositoryId,
source type, `root="."`, optional Git revision, aware created_at, ordered files, languages,
manifests/lockfiles, source roots, exclusions, statistics, support flag, fingerprint и JSON metadata.
SnapshotId — UUIDv5 fingerprint; он идентифицирует наблюдаемый inventory, не persistent repository.
RepositoryId назначается будущим project/repository owner. Created_at — volatile, вне fingerprint.

`RepositoryFile`: canonical relative path, lowercase extension, size, SourceLanguage, file kind,
generated/binary/large flags, analysis eligibility, optional SHA-256 и explicit hash status.
Нет AST, symbols, ArchitectureNode или source contents. Models frozen с существующими domain
semantics; JSON maps shallow mutable. Snapshot проверяет uniqueness/order/statistics/language lists,
manifest references, support и Git revision ownership. Git revision — полный 40/64-character SHA.

Paths — relative POSIX, без абсолютных путей, backslashes, `.`/`..`, пустых segments и NUL.
Host path не участвует в file identity/fingerprint. Case и Unicode filenames сохраняются;
Unicode normalization между OS не гарантируется. ZIP дополнительно отвергает colon/drive/ADS и
case-colliding components. ZIP wrapper directory сохраняется; automatic flattening отсутствует.

## Discovery rules

Language detection: `.java`, `.ts/.tsx`, `.js/.jsx`; дополнительно `.py`, `.json`, `.yaml/.yml`,
`.xml`, `.toml`, `.sh`, `.md` и exact filename `Dockerfile`. Остальные UNKNOWN. SourceLanguage
отделён от IAM Language, чтобы не расширять старый parser-facing contract configuration languages.
Только Java/TypeScript/JavaScript — target languages. Python inventory не означает поддержку анализа.

Kind precedence: binary → known lockfile → known manifest → generated → source/test → config →
documentation → other. Test heuristic: `test/tests/__tests__` path component, `.test./.spec.` filename,
`*Test.java`. Generated: `dist/build/target/generated` directory или `.min.js/.min.css` и
`.generated.ts/.generated.js/.generated.java`. `.d.ts` не считается автоматически generated.
Binary: known extensions или NUL в prefix до 4096 bytes. Это heuristic; UTF-16 text может стать binary.

Manifests: `pom.xml`, `build.gradle[.kts]`, `settings.gradle[.kts]`, `package.json`, `Dockerfile`,
`docker-compose.yml/.yaml`. Lockfiles: `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`. Зависимости
не разбираются. Source roots — path heuristics для `src/main/java`, `src/test/java`, `src`, tests
или parent directory; build-system semantics не вычисляются.

Statistics: included files/bytes, SOURCE и TEST раздельно, generated/binary/eligible counts,
counts всех detected languages. Generated flag может пересекаться с manifest/lockfile kind.
Exclusions записывают pruned directory или отдельный skipped entry; descendants pruned directory
не перечисляются и не входят в total_files. Support true при любом nonbinary target-language file;
large/generated flags могут дать eligible_files=0 при supported_for_analysis=true.

## Exclusions и .gitignore

Defaults: `.git`, `node_modules`, `target`, `dist`, `build`, `coverage`, `.next`, `out`, `.gradle`,
`.idea`, `.vscode`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.venv`, `.archguard`.
Tests не исключаются. Для включения generated directory изменить excluded_directories явно.

`extra_exclusions` — Git-style patterns. Defaults и custom exclusions имеют приоритет над
`.gitignore` negation. `.gitignore` включён по умолчанию для всех sources: root + nested scopes,
last matching pattern wins; ignored parents prune traversal, child negation их не открывает.
GitIgnoreSpec из [Pathspec](https://python-path-specification.readthedocs.io/en/latest/readme.html),
MPL-2.0, заменяет самописный parser. UTF-8 decode использует replacement для malformed bytes.
Global excludes, `.git/info/exclude`, Git index tracked-file override и other git config не читаются:
это content-only discovery policy, а не полная копия `git status` semantics. Одинаковые файлы и
policy дают одинаковый результат независимо от LOCAL/ZIP/GIT source и настроек пользователя.

## Resource limits и fingerprint

| Default | Scope / behavior |
| --- | --- |
| max_files = 100,000 | included inventory; ZIP также проверяет все entries до exclusions |
| max_entries = 200,000 | bounded traversal metadata и ZIP central directory entries |
| max_source_file_bytes = 2 MiB | файл остаётся в inventory, is_large=true, parser eligibility=false |
| max_hash_file_bytes = 8 MiB | larger files имеют SIZE_LIMIT и sha256=null |
| max_total_hash_bytes = 256 MiB | budget в canonical file order; далее BUDGET_LIMIT |
| max_gitignore_bytes = 64 KiB | oversize → RepositoryLimitExceeded |
| max_archive_bytes = 128 MiB | compressed ZIP input bound |
| max_single_file_bytes = 64 MiB | ZIP declared и actual extracted size |
| max_total_uncompressed_bytes = 512 MiB | ZIP declared и actual cumulative bytes |
| git_timeout_seconds = 60 | deadline всех Git commands в materialization |

Local large/generated file не приводит к ZIP-size-limit failure: его metadata регистрируется,
prefix ограничен, hashing policy может пропустить содержимое. Traversal итеративный; metadata
коллекции bounded, file contents не накапливаются. SHA-256 вычисляется streaming chunks 64 KiB.
Concurrent file growth не позволяет hashing читать бесконечный stream.

Fingerprint `inventory-sha256-v1`: SHA-256 header + canonical JSON record на каждый ordered file
(path, size, content hash/hash status, language/kind/flags). Без root, source type, mtime, revision
и created_at. Small text files всех kinds content-hashed; binary/size/budget-skipped files используют
metadata. Поэтому same-size content change **unhashed** file может не изменить fingerprint.
Это selective fingerprint, не полный content-addressed архив. Hash status делает ограничение явным;
future incremental cache не должен считать null SHA доказательством неизменности содержимого.

## Safety и Git policy

Все symlinks (включая internal и dangling) пропускаются; special files не читаются. POSIX openat /
dir_fd + O_NOFOLLOW проверяет каждый component, включая lazy reads после discovery. File stat
identity сверяется до/после чтения, но local view не является атомарным filesystem snapshot.
Caller должен исключать конкурентное изменение проекта для reproducible analysis.

ZIP никогда не вызывает extractall: проверяет все paths/types/collisions/quotas до записи,
затем пишет regular files в private workspace с actual byte checks. Symlink ZIP input, archived
symlinks/special files и encrypted/malformed archives отклоняются. Stdlib zipfile всё же загружает
central directory metadata; max_archive_bytes/max_entries ограничивают практический риск, не
обещают промышленной защиты от любого decompressor attack.

Git: только public HTTPS без embedded credentials/query/fragment; HTTP/SSH/file/ext запрещены.
Argument list, shell=False по умолчанию; shallow clone, branch/tag или full SHA, no submodule init.
`.gitmodules` только помечает future concern, не исполняется и не даёт dependency data. Git hooks,
templates, fsmonitor, global/system config, credential helpers/prompts, inherited GIT_* overrides и
redirects отключены. Timeout убивает POSIX process group и ждёт завершения. Git must be installed.
Private/corporate credentials, SSH, Git LFS materialization, submodules и Windows runtime сейчас
не поддержаны. Только Git source обращается в сеть; других source/AI/telemetry requests нет.
Inventory limits проверяются после clone; shallow clone и deadline не заменяют отдельную
disk quota для Git workspace. Жёсткий лимит общего размера Git checkout пока отсутствует.

Repository code, npm/Maven/Gradle, scripts, Makefile, Dockerfile и CI не выполняются intake.
Typed public errors не содержат raw stderr, source contents или credentials. Internal cause
доступна exception chaining; logs содержат source type, start/finish/counts/duration/revision/error code.

## Developer CLI

```bash
uv sync --locked --extra dev
.venv/bin/archguard repo inspect tests/fixtures/repositories/java_maven
.venv/bin/python -m archguard.cli repository inspect /path/to/repository --json
.venv/bin/archguard repo inspect /path/to/archive.zip --source zip --json
.venv/bin/archguard repo inspect https://github.com/octocat/Hello-World.git --source git --ref master
```

`--exclude PATTERN` repeatable; `--no-gitignore` disables gitignore. JSON goes only to stdout,
lifecycle logs/errors to stderr; typed errors return exit code 2. CLI credentials fields отсутствуют.
Main pytest Git tests use real temporary local Git repositories through a test-only transport
adapter; production URL policy stays HTTPS-only. No network-dependent pytest.

Следующий этап: PROMPT 003 — Language Parsing Foundation / Tree-sitter + parser adapter architecture.
