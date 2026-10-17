"""Copy only bounded, explicitly allowed source files through no-follow descriptors."""

import hashlib
import os
import stat
from pathlib import Path

EXCLUDED = frozenset(
    {"node_modules", "target", "dist", "build", "coverage", "vendor", "experiments", "benchmarks"}
)
MAX_FILES = 200
MAX_BYTES = 4 * 1024 * 1024
MAX_FILE_BYTES = 256 * 1024


class IntakeError(ValueError):
    pass


def projects(root: Path) -> dict[str, str]:
    return {
        hashlib.sha256(entry.name.encode()).hexdigest()[:16]: entry.name
        for entry in sorted(os.scandir(root), key=lambda item: item.name)
        if not entry.name.startswith(".")
        and entry.name not in EXCLUDED
        and entry.is_dir(follow_symlinks=False)
    }


def snapshot(root: Path, name: str, destination: Path) -> dict[str, str | int]:
    if name not in projects(root).values():
        raise IntakeError("PROJECT_UNAVAILABLE")
    entries = total = count = 0
    digest = hashlib.sha256()
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    root_fd = os.open(root, flags)
    try:
        project_fd = os.open(name, flags, dir_fd=root_fd)
    finally:
        os.close(root_fd)
    destination.mkdir(mode=0o700)

    def copy(directory: int, parts: tuple[str, ...] = ()) -> None:
        nonlocal entries, total, count
        if len(parts) > 20:
            raise IntakeError("DEPTH_LIMIT")
        for filename in sorted(os.listdir(directory)):
            entries += 1
            if entries > 5000:
                raise IntakeError("ENTRY_LIMIT")
            if filename.startswith(".") or filename in EXCLUDED:
                continue
            metadata = os.stat(filename, dir_fd=directory, follow_symlinks=False)
            if stat.S_ISLNK(metadata.st_mode):
                raise IntakeError("SYMLINK_REJECTED")
            relative = (*parts, filename)
            target = destination.joinpath(*relative)
            if stat.S_ISDIR(metadata.st_mode):
                fd = os.open(filename, flags, dir_fd=directory)
                try:
                    copy(fd, relative)
                finally:
                    os.close(fd)
                continue
            if not stat.S_ISREG(metadata.st_mode) or (
                Path(filename).suffix not in {".ts", ".tsx", ".java"}
                and relative != ("architecture.yaml",)
            ):
                continue
            count += 1
            if count > MAX_FILES or metadata.st_size > MAX_FILE_BYTES:
                raise IntakeError("SOURCE_LIMIT")
            fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            with os.fdopen(fd, "rb") as source:
                current = os.fstat(source.fileno())
                if not stat.S_ISREG(current.st_mode) or current.st_nlink != 1:
                    raise IntakeError("SPECIAL_FILE_REJECTED")
                data = source.read(MAX_FILE_BYTES + 1)
            total += len(data)
            if len(data) > MAX_FILE_BYTES or total > MAX_BYTES:
                raise IntakeError("BYTE_LIMIT")
            if b"\0" in data:
                raise IntakeError("BINARY_SOURCE_REJECTED")
            try:
                data.decode("utf-8")
            except UnicodeDecodeError as error:
                raise IntakeError("UTF8_REQUIRED") from error
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            target.write_bytes(data)
            digest.update("/".join(relative).encode() + b"\0" + data + b"\0")

    try:
        copy(project_fd)
    finally:
        os.close(project_fd)
    if count == 0:
        raise IntakeError("NO_SUPPORTED_SOURCES")
    return {"files": count, "bytes": total, "sha256": digest.hexdigest()}
