"""P032 source-only child process. Application file fence; no OS sandbox claim."""

import hashlib
import json
import os
import re
import resource
import sys
import time
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from archguard.benchmark.oss.models import canonical, digest
from archguard.core.identifiers import RepositoryId, SnapshotId, SourceFileId
from archguard.parsing.tree_sitter_adapters import JavaParser, TypeScriptParser
from archguard.repository.enums import HashStatus, RepositoryFileKind
from archguard.repository.models import RepositoryFile
from archguard.security.analyzer_v1 import SecuritySourceInput
from archguard.security.analyzer_v2 import SecurityAnalyzerV2
from archguard.security.domain import SecurityAnalysisContext
from archguard.security.summaries_v2 import V2Limits
from archguard.security_benchmark.protocol import Outcome, map_p029_outcome


class SourceFence:
    def __init__(self, root: Path, manifest: dict[str, Any]) -> None:
        self.root = root.resolve()
        if set(manifest) != {"cases", "limits", "capabilities", "source_hashes", "fingerprint"}:
            raise ValueError("P032_FORBIDDEN_INPUT_FIELDS")
        if (
            digest({k: v for k, v in manifest.items() if k != "fingerprint"})
            != manifest["fingerprint"]
        ):
            raise ValueError("P032_INPUT_SEAL_DRIFT")
        self.cases = manifest["cases"]
        for rule, values in manifest["capabilities"].items():
            if (
                not re.fullmatch(r"SEC00[1-9]|SEC010", rule)
                or set(values) - {"JAVA", "TYPESCRIPT"}
                or set(values.values()) - {"IMPLEMENTED_V2", "PARTIAL_V2", "CONTRACT_ONLY"}
            ):
                raise ValueError("P032_FORBIDDEN_CAPABILITY_FIELDS")
        if len(self.cases) != 100 or len({r["case_id"] for r in self.cases}) != 100:
            raise ValueError("P032_DEV_PREDICTION_INCOMPLETE")
        self.paths: set[Path] = set()
        for row in self.cases:
            if set(row) != {"case_id", "rule_id", "language", "source_paths"}:
                raise ValueError("P032_FORBIDDEN_ROSTER_FIELDS")
            if (
                not re.fullmatch(r"sc-[a-f0-9]{24}", row["case_id"])
                or row["language"] not in {"JAVA", "TYPESCRIPT"}
                or not re.fullmatch(r"SEC00[1-9]|SEC010", row["rule_id"])
            ):
                raise ValueError("P032_INVALID_SOURCE_IDENTITY")
            for relative in row["source_paths"]:
                if not re.fullmatch(r"src/[A-Za-z0-9_/]+\.(java|ts)", relative):
                    raise ValueError("P032_UNSAFE_SOURCE_PATH")
                path = self.root / "sources" / row["case_id"] / relative
                if (
                    Path(relative).is_absolute()
                    or ".." in path.parts
                    or path.suffix not in {".java", ".ts"}
                ):
                    raise ValueError("P032_UNSAFE_SOURCE_PATH")
                if not path.is_relative_to(self.root) or any(
                    p.is_symlink() for p in (path, *path.parents)
                ):
                    raise ValueError("P032_UNSAFE_SOURCE_PATH")
                self.paths.add(path)
        if {str(p.relative_to(self.root / "sources")) for p in self.paths} != set(
            manifest["source_hashes"]
        ):
            raise ValueError("P032_SOURCE_HASH_INVENTORY_DRIFT")

    def source(self, relative: str) -> Path:
        path = self.root / "sources" / relative
        if Path(relative).is_absolute() or ".." in Path(relative).parts or path not in self.paths:
            raise ValueError("P032_PATH_OUTSIDE_SOURCE_CAPABILITY")
        return path

    def audit(self, event: str, args: tuple[Any, ...]) -> None:
        if event.startswith(("socket.", "subprocess.", "os.system", "os.exec")):
            raise PermissionError("P032_NETWORK_OR_PROCESS_DENIED")
        if event != "open" or isinstance(args[0], int):
            return
        path = Path(os.fsdecode(args[0])).absolute()
        mode, flags = args[1:3]
        writing = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT)
        )
        if not writing and path in self.paths:
            return
        outputs = {
            self.root / n
            for n in ("raw.json", "registry.json", "resources.json", "worker-audit.json")
        }
        if writing and path in outputs:
            return
        raise PermissionError("P032_FILE_CAPABILITY_DENIED")


def sealed(value: dict[str, Any]) -> dict[str, Any]:
    return value | dict(fingerprint=digest(value))


def write(root: Path, name: str, value: dict[str, Any]) -> None:
    with (root / name).open("x", encoding="utf-8") as stream:
        stream.write(canonical(value) + "\n")


def execute(root: Path) -> None:
    root = root.resolve()
    manifest = json.loads((root / "input.json").read_text())
    fence = SourceFence(root, manifest)
    if manifest["limits"] != V2Limits().model_dump(mode="json"):
        raise ValueError("P032_DETECTOR_CONFIGURATION_DRIFT")
    JavaParser()
    TypeScriptParser()
    for denied in (
        "../truth.json",
        "/truth.json",
        "reviews/A.json",
        "adjudication.json",
        "FINAL/truth.json",
    ):
        try:
            fence.source(denied)
        except ValueError:
            pass
        else:
            raise ValueError("P032_INPUT_FENCE_FAILED")
    # All frozen parser/analyzer modules above are imported before installing the
    # deny-by-default data fence; no private experiment store is read by imports.
    sys.addaudithook(fence.audit)
    raw_rows, adapted, latency = [], [], []
    source_bytes = source_chars = 0
    adapter_seconds = 0.0
    worker_start = time.perf_counter()
    for row in sorted(fence.cases, key=lambda r: r["case_id"]):
        repository = RepositoryId(uuid5(UUID(int=320), row["case_id"]))
        snapshot = SnapshotId(uuid5(repository, "P032-frozen-DEV"))
        inputs = []
        for relative in sorted(row["source_paths"]):
            blob = fence.source(f"{row['case_id']}/{relative}").read_bytes()
            if (
                hashlib.sha256(blob).hexdigest()
                != manifest["source_hashes"][f"{row['case_id']}/{relative}"]
            ):
                raise ValueError("P032_SOURCE_BYTE_DRIFT")
            source_bytes += len(blob)
            source_chars += len(blob.decode("utf-8"))
            inputs.append(
                SecuritySourceInput(
                    RepositoryFile(
                        relative_path=relative,
                        extension=Path(relative).suffix,
                        size_bytes=len(blob),
                        language=row["language"],
                        kind=RepositoryFileKind.SOURCE,
                        analysis_eligible=True,
                        hash_status=HashStatus.BUDGET_LIMIT,
                    ),
                    blob,
                    SourceFileId(uuid5(repository, relative)),
                )
            )
        context = SecurityAnalysisContext(
            repository_id=repository,
            snapshot_id=snapshot,
            language=row["language"],
            requested_rules=(row["rule_id"],),
        )
        started = time.perf_counter()
        failure = None
        try:
            result = SecurityAnalyzerV2().analyze(context, tuple(inputs)).model_dump(mode="json")
        except PermissionError:
            raise
        except Exception as error:
            result = None
            failure = type(error).__name__
        latency.append(dict(case_id=row["case_id"], seconds=time.perf_counter() - started))
        started = time.perf_counter()
        raw = dict(
            case_id=row["case_id"],
            language=row["language"],
            rule_id=row["rule_id"],
            capability=manifest["capabilities"][row["rule_id"]][row["language"]],
            result=result,
            analysis_exception=failure,
        )
        outcome = map_p029_outcome(result, row["rule_id"]) if result is not None else Outcome.FAILED
        raw_rows.append(raw)
        adapted.append(
            dict(
                case_id=row["case_id"],
                language=row["language"],
                rule_id=row["rule_id"],
                capability=raw["capability"],
                outcome=outcome.value,
                raw_row_fingerprint=digest(raw),
            )
        )
        adapter_seconds += time.perf_counter() - started
    raw_set = sealed(dict(input_fingerprint=manifest["fingerprint"], rows=raw_rows))
    registry = sealed(dict(raw_prediction_fingerprint=raw_set["fingerprint"], rows=adapted))
    started = time.perf_counter()
    write(root, "raw.json", raw_set)
    write(root, "registry.json", registry)
    adapter_seconds += time.perf_counter() - started
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    write(
        root,
        "resources.json",
        sealed(
            dict(
                latency=latency,
                adapter_materialization_seconds=adapter_seconds,
                worker_wall_seconds=time.perf_counter() - worker_start,
                WHOLE_PROCESS_PEAK_RSS_bytes=rss if sys.platform == "darwin" else rss * 1024,
                source_bytes=source_bytes,
                source_chars=source_chars,
                timeouts="NOT_MEASURED",
            )
        ),
    )
    write(
        root,
        "worker-audit.json",
        sealed(
            dict(
                input_fingerprint=manifest["fingerprint"],
                raw_prediction_fingerprint=raw_set["fingerprint"],
                prediction_fingerprint=registry["fingerprint"],
                DEV_cases_analyzed=100,
                DEV_truth_reads=0,
                FINAL_truth_reads=0,
                review_reads=0,
                adjudication_reads=0,
                construction_intent_reads=0,
                provider_calls=0,
                credential_reads=0,
                APPLICATION_CAPABILITY_BOUNDARY="VERIFIED",
                OS_LEVEL_ISOLATION="NOT_CLAIMED",
            )
        ),
    )


if __name__ == "__main__":
    os.umask(0o077)
    execute(Path(sys.argv[1]))
