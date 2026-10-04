import hashlib
import json
from typing import TYPE_CHECKING
from uuid import NAMESPACE_URL, uuid5

from archguard.core.identifiers import SnapshotId

if TYPE_CHECKING:
    from archguard.repository.models import RepositoryFile


def inventory_fingerprint(files: tuple["RepositoryFile", ...]) -> str:
    """Hash selected content and unhashed-file metadata, without timestamps or host paths."""
    digest = hashlib.sha256(b"archguard-inventory-sha256-v1\n")
    for file in files:
        record = [
            file.relative_path,
            file.size_bytes,
            file.sha256,
            file.hash_status.value,
            file.language.value,
            file.kind.value,
            file.is_generated,
            file.is_binary,
            file.is_large,
        ]
        digest.update(json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def snapshot_id(fingerprint: str) -> SnapshotId:
    return SnapshotId(uuid5(NAMESPACE_URL, f"archguard:repository-snapshot:1.0:{fingerprint}"))
