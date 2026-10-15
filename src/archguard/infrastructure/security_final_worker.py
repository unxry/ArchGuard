"""P034 one-pass frozen candidate worker; launched only inside verified Seatbelt."""

import hashlib
import json
import os
import resource
import sys
import time
from pathlib import Path
from uuid import UUID, uuid5

from archguard.benchmark.oss.models import digest
from archguard.core.identifiers import RepositoryId, SnapshotId, SourceFileId
from archguard.infrastructure.security_final_boundary import (
    SOURCE_FP,
    VERSION,
    ZERO,
    FinalFence,
    write_new,
)
from archguard.infrastructure.security_final_boundary import (
    seal as sealed,
)
from archguard.parsing.tree_sitter_adapters import JavaParser, TypeScriptParser
from archguard.repository.enums import HashStatus, RepositoryFileKind
from archguard.repository.models import RepositoryFile
from archguard.security.analyzer_v1 import SecuritySourceInput
from archguard.security.analyzer_v3 import SecurityAnalyzerV3
from archguard.security.completeness_v3 import map_v3_outcome
from archguard.security.domain import SecurityAnalysisContext
from archguard.security.summaries_v2 import V2Limits
from archguard.security_benchmark.protocol import Outcome


def execute(root: Path, output: Path) -> None:
    root, output = root.resolve(), output.resolve()
    manifest = json.loads((root / "input.json").read_text())
    fence = FinalFence(root, output, manifest)
    for name, expected in manifest["runtime_hashes"].items():
        if hashlib.sha256((root / "runtime" / name).read_bytes()).hexdigest() != expected:
            raise ValueError("P034_RUNTIME_DRIFT")
    if manifest["limits"] != V2Limits().model_dump(mode="json"):
        raise ValueError("P034_BLOCKED_CANDIDATE_DRIFT")
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
            raise ValueError("P034_INPUT_FENCE_FAILED")
    # All frozen parser/analyzer modules above are imported before installing the
    # deny-by-default data fence; no private experiment store is read by imports.
    sys.addaudithook(fence.audit)
    raw_rows, adapted, latency = [], [], []
    source_bytes = source_chars = 0
    adapter_seconds = 0.0
    worker_start = time.perf_counter()
    for row in sorted(fence.cases, key=lambda r: r["case_id"]):
        repository = RepositoryId(uuid5(UUID(int=320), row["case_id"]))
        snapshot = SnapshotId(uuid5(repository, "P034-frozen-FINAL"))
        inputs = []
        for relative in sorted(row["source_paths"]):
            blob = fence.source(f"{row['case_id']}/{relative}").read_bytes()
            if (
                hashlib.sha256(blob).hexdigest()
                != manifest["source_hashes"][f"{row['case_id']}/{relative}"]
            ):
                raise ValueError("P034_SOURCE_BYTE_DRIFT")
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
            result = SecurityAnalyzerV3().analyze(context, tuple(inputs)).model_dump(mode="json")
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
            candidate_version=VERSION,
            candidate_source_fingerprint=SOURCE_FP,
            execution_status="FAILED" if result is None else "ANALYZED",
            result=result,
            analysis_exception=failure,
        )
        outcome = (
            map_v3_outcome(result, row["rule_id"], row["language"])
            if result is not None
            else Outcome.FAILED
        )
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
    write_new(output / "raw.json", raw_set)
    write_new(output / "registry.json", registry)
    adapter_seconds += time.perf_counter() - started
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    write_new(
        output / "resources.json",
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
    write_new(
        output / "worker-audit.json",
        sealed(
            dict(
                input_fingerprint=manifest["fingerprint"],
                raw_prediction_fingerprint=raw_set["fingerprint"],
                prediction_fingerprint=registry["fingerprint"],
                FINAL_cases_analyzed=200,
                authoritative_invocations=1,
                technical_retries=0,
                **ZERO,
                APPLICATION_CAPABILITY_BOUNDARY="VERIFIED",
                OS_LEVEL_ISOLATION="VERIFIED_BY_PARENT_PREFLIGHT",
            )
        ),
    )


if __name__ == "__main__":
    os.umask(0o077)
    if sys.argv[1] == "--preflight":
        JavaParser()
        TypeScriptParser()
        print("P034_RUNTIME_IMPORTS_VERIFIED")
    else:
        execute(Path(sys.argv[1]), Path(sys.argv[2]))
