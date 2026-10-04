class RepositoryIntakeError(Exception):
    """Public messages are safe; infrastructure exceptions are retained through __cause__."""

    code = "repository_intake_error"


class InvalidRepositorySource(RepositoryIntakeError):
    code = "invalid_repository_source"


class RepositoryNotFound(RepositoryIntakeError):
    code = "repository_not_found"


class RepositoryLimitExceeded(RepositoryIntakeError):
    code = "repository_limit_exceeded"


class UnsafeArchiveError(RepositoryIntakeError):
    code = "unsafe_archive"


class GitCloneError(RepositoryIntakeError):
    code = "git_clone_error"


class GitTimeoutError(GitCloneError):
    code = "git_timeout"


class UnsupportedSourceError(RepositoryIntakeError):
    code = "unsupported_source"


class RepositoryReadError(RepositoryIntakeError):
    code = "repository_read_error"


class RepositoryChangedError(RepositoryReadError):
    code = "repository_changed"
