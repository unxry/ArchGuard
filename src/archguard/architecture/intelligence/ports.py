from contextlib import AbstractContextManager
from typing import BinaryIO, Protocol

from archguard.architecture.intelligence.models import (
    ProviderCapabilities,
    StructuredLLMRequest,
    StructuredLLMResponse,
)


class SourceReader(Protocol):
    """Structurally fulfilled by the existing safe RepositoryWorkspace."""

    def open_source_file(self, relative_path: str) -> AbstractContextManager[BinaryIO]: ...


class ContextRedactor(Protocol):
    redactor_id: str

    def redact(self, text: str) -> str: ...


class LLMProvider(Protocol):
    provider_id: str
    model_id: str
    capabilities: ProviderCapabilities

    def count_input_tokens(self, request: StructuredLLMRequest) -> int | None: ...

    def complete_structured(self, request: StructuredLLMRequest) -> StructuredLLMResponse:
        """Honor request timeout, return bounded JSON, never log source or credentials."""
        ...


class LLMProviderError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code
