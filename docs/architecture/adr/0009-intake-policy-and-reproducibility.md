# ADR 0009 — Conservative Git/archive intake and selective fingerprint

Status: accepted · Stage: Repository Intake & Source Discovery

## Context

Repository sources недоверенны как данные. Git config/hooks и archive paths могут выйти за
границы intake, а mtime/absolute paths портят reproducibility. Полное hashing гигабайтов не нужно
для discovery. Самописный gitignore parser был бы сложным и несовместимым между sources.

## Decision

Public HTTPS Git, sanitized public errors, no credentials, redirects, hooks, submodule init или
inherited user Git config. Subprocess argument list и POSIX process-group timeout/cleanup.
ZIP path/type/collision preflight, bounded streaming extraction в private temporary directory;
all archived entries учитываются до exclusions. Repo code не выполняется.

Pathspec GitIgnoreSpec (MPL-2.0) для content-only root/nested .gitignore semantics одинаково для
Local/ZIP/Git. Явные exclusions сильнее negation, tests включены. Global excludes/Git index ignored.
Canonical ordered inventory и versioned selective SHA-256 fingerprint: hashes small text files,
explicit metadata fallback для binary/size/budget-skipped files. No timestamps/host paths/source type.

## Consequences

Детерминированные snapshots с прозрачными ограничениями и bounded work. Private/SSH/LFS,
recursive submodules и global gitignore не поддержаны. Same-size mutations unhashed files могут
не менять fingerprint; будущий cache обязан учитывать hash_status, не считать null hash доказательством
равенства. Fingerprint сравним между source types при одинаковых included paths/content/policy.
Safety intake не является Security Analysis Engine и не влияет на ARCH/SEC separation.

Primary references: [Git config](https://git-scm.com/docs/git-config),
[Pathspec](https://python-path-specification.readthedocs.io/en/latest/readme.html).
