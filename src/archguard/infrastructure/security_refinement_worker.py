"""P032 source-only child process. Application file fence; no OS sandbox claim."""

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
from archguard.infrastructure.security_dev_worker import SourceFence, sealed, write
from archguard.parsing.tree_sitter_adapters import JavaParser, TypeScriptParser
from archguard.repository.enums import HashStatus, RepositoryFileKind
from archguard.repository.models import RepositoryFile
from archguard.security.analyzer_v1 import SecuritySourceInput
from archguard.security.analyzer_v3 import SecurityAnalyzerV3
from archguard.security.completeness_v3 import map_v3_outcome
from archguard.security.domain import SecurityAnalysisContext
from archguard.security.summaries_v2 import V2Limits
from archguard.security_benchmark.protocol import Outcome


def execute(root: Path) -> None:
    root = root.resolve()
    manifest = json.loads((root / "input.json").read_text())
    if (
        digest({k: v for k, v in manifest.items() if k != "fingerprint"})
        != "2ce11fa476274e8c99e9d55d70a4b57518dbbcbe55abe8799b7d726d55f66879"
    ):
        raise ValueError("P033_ONLY_FROZEN_DEV_ALLOWED")
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
            capability=manifest["capabilities"][row["rule_id"]][row["language"]].replace(
                "_V2", "_V3"
            ),
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
