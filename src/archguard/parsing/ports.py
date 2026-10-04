from typing import Protocol

from archguard.core.identifiers import SnapshotId
from archguard.parsing.config import ParserConfig
from archguard.parsing.enums import ParserLanguage
from archguard.parsing.models import ParsedSourceFile, ParserRuntimeInfo
from archguard.repository.models import RepositoryFile


class ParserAdapter(Protocol):
    @property
    def language(self) -> ParserLanguage: ...

    @property
    def supported_extensions(self) -> tuple[str, ...]: ...

    @property
    def runtime_info(self) -> ParserRuntimeInfo: ...

    def parse(
        self,
        snapshot_id: SnapshotId,
        source_file: RepositoryFile,
        source: bytes,
        config: ParserConfig,
    ) -> ParsedSourceFile: ...
