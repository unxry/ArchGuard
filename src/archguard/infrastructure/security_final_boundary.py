"""P034 source capabilities and verified macOS Seatbelt launch boundary."""

import errno
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from archguard.benchmark.oss.models import canonical, digest
from archguard.security.summaries_v2 import V2Limits

VERSION = "security-bounded-v3"
SOURCE_FP = "2a7d0b7573321b1724503e6b5fe7a0d101e11f9929e9ba2a4e64d3694d246afe"
OUTPUTS = ("raw.json", "registry.json", "resources.json", "worker-audit.json")
ZERO = dict.fromkeys(
    (
        "FINAL_truth_reads",
        "HUMAN_truth_300_reads",
        "review_response_reads",
        "adjudication_reads",
        "construction_intent_reads",
        "DEV_truth_reads",
        "candidate_changes",
        "candidate_tuning",
        "provider_calls",
        "OpenAI_calls",
        "LLM_calls",
        "AI_labels",
        "AI_adjudication",
        "credential_reads",
        "network_connections",
        "provider_connectivity",
        "paid_spend",
    ),
    0,
)


def seal(value: dict[str, Any]) -> dict[str, Any]:
    return value | {"fingerprint": digest(value)}


def write_new(path: Path, value: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as stream:
        stream.write(canonical(value) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def validate_roster(cases: list[dict[str, Any]]) -> None:
    if len(cases) != 200 or len({r["case_id"] for r in cases}) != 200:
        raise ValueError("P034_FINAL_ROSTER_INCOMPLETE")
    for row in cases:
        if set(row) != {"case_id", "rule_id", "language", "source_paths"}:
            raise ValueError("P034_FORBIDDEN_ROSTER_FIELDS")
        if (
            not re.fullmatch(r"sc-[a-f0-9]{24}", row["case_id"])
            or not re.fullmatch(r"SEC00[1-9]|SEC010", row["rule_id"])
            or row["language"] not in {"JAVA", "TYPESCRIPT"}
            or not row["source_paths"]
            or len(set(row["source_paths"])) != len(row["source_paths"])
        ):
            raise ValueError("P034_INVALID_ROSTER_IDENTITY")
        extension = ".java" if row["language"] == "JAVA" else ".ts"
        for name in row["source_paths"]:
            if (
                not re.fullmatch(r"src/[A-Za-z0-9_/]+\.(java|ts)", name)
                or Path(name).suffix != extension
            ):
                raise ValueError("P034_UNSAFE_SOURCE_PATH")
    if Counter(r["language"] for r in cases) != {"JAVA": 100, "TYPESCRIPT": 100} or Counter(
        r["rule_id"] for r in cases
    ) != {f"SEC{i:03d}": 20 for i in range(1, 11)}:
        raise ValueError("P034_PROSPECTIVE_STRATA_DRIFT")


class FinalFence:
    def __init__(self, bundle: Path, output: Path, manifest: dict[str, Any]) -> None:
        self.bundle, self.output = bundle.resolve(), output.resolve()
        if set(manifest) != {
            "cases",
            "limits",
            "capabilities",
            "source_hashes",
            "runtime_hashes",
            "candidate_source_fingerprint",
            "fingerprint",
        }:
            raise ValueError("P034_FORBIDDEN_INPUT_FIELDS")
        if (
            digest({k: v for k, v in manifest.items() if k != "fingerprint"})
            != manifest["fingerprint"]
        ):
            raise ValueError("P034_INPUT_SEAL_DRIFT")
        if manifest["candidate_source_fingerprint"] != SOURCE_FP or manifest[
            "limits"
        ] != V2Limits().model_dump(mode="json"):
            raise ValueError("P034_BLOCKED_CANDIDATE_DRIFT")
        validate_roster(manifest["cases"])
        if set(manifest["capabilities"]) != {f"SEC{i:03d}" for i in range(1, 11)}:
            raise ValueError("P034_INVALID_CAPABILITIES")
        for values in manifest["capabilities"].values():
            if set(values) != {"JAVA", "TYPESCRIPT"} or set(values.values()) - {
                "IMPLEMENTED_V3",
                "PARTIAL_V3",
                "CONTRACT_ONLY",
            }:
                raise ValueError("P034_INVALID_CAPABILITIES")
        self.cases = manifest["cases"]
        self.paths = {
            self.bundle / "sources" / row["case_id"] / name
            for row in self.cases
            for name in row["source_paths"]
        }
        if {str(p.relative_to(self.bundle / "sources")) for p in self.paths} != set(
            manifest["source_hashes"]
        ):
            raise ValueError("P034_SOURCE_INVENTORY_DRIFT")
        for path in self.paths:
            if path.resolve() != path or any(p.is_symlink() for p in (path, *path.parents)):
                raise ValueError("P034_SYMLINK_DENIED")

    def source(self, relative: str) -> Path:
        path = self.bundle / "sources" / relative
        if Path(relative).is_absolute() or ".." in Path(relative).parts or path not in self.paths:
            raise ValueError("P034_SOURCE_CAPABILITY_DENIED")
        return path

    def audit(self, event: str, args: tuple[Any, ...]) -> None:
        if event.startswith(("socket.", "subprocess.", "os.system", "os.exec", "os.fork")):
            raise PermissionError("P034_NETWORK_OR_PROCESS_DENIED")
        if event != "open" or isinstance(args[0], int):
            return
        path = Path(os.path.realpath(os.fsdecode(args[0])))
        mode, flags = args[1:3]
        writing = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT)
        )
        if not writing and path in self.paths:
            return
        if writing and path in {self.output / name for name in OUTPUTS}:
            return
        raise PermissionError("P034_FILE_CAPABILITY_DENIED")


def environment(bundle: Path, temporary: Path) -> dict[str, str]:
    return {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "PYTHONPATH": str(bundle / "runtime"),
        "PYTHONHASHSEED": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "TMPDIR": str(temporary),
        "LC_ALL": "C",
    }


def mechanism() -> str:
    executable = shutil.which("sandbox-exec")
    if sys.platform != "darwin" or executable != "/usr/bin/sandbox-exec":
        raise ValueError("P034_BLOCKED_OS_ISOLATION_UNAVAILABLE")
    return executable


def profile(bundle: Path, output: Path, temporary: Path) -> str:
    # No repository/home parent is granted: only code, dependencies and input.
    reads = (
        bundle.resolve(),
        Path(sys.base_prefix).resolve(),
        Path(
            sys.prefix,
            "lib",
            f"python{sys.version_info.major}.{sys.version_info.minor}",
            "site-packages",
        ).resolve(),
        Path("/System/Library"),
        Path("/usr/lib"),
    )

    def literal(path: Path) -> str:
        return json.dumps(str(path))

    return (
        "\n".join(
            (
                "(version 1)",
                "(deny default)",
                "(deny network*)",
                "(allow sysctl-read)",
                "(allow mach-lookup)",
                "(allow file-read-metadata)",
                f"(allow process-exec (literal {literal(Path(sys.executable).resolve())}))",
                "(allow file-read* "
                + " ".join(f"(subpath {literal(p)})" for p in reads)
                + ' (literal "/") (literal "/dev/urandom") (literal "/dev/random"))',
                "(allow file-write* "
                + " ".join(f"(subpath {literal(p.resolve())})" for p in (output, temporary))
                + ")",
            )
        )
        + "\n"
    )


def command(policy: Path, *arguments: str) -> list[str]:
    return [mechanism(), "-f", str(policy), sys.executable, "-S", *arguments]


def preflight(bundle: Path, output: Path, temporary: Path, policy: Path) -> dict[str, Any]:
    sentinels = policy.parent / "protected-sentinels"
    sentinels.mkdir(mode=0o700)
    categories = (
        "FINAL_truth",
        "HUMAN_truth_300",
        "review_response",
        "adjudication_response",
        "construction_intent",
        "DEV_truth",
        "credentials",
        "unrelated_home",
    )
    for name in categories:
        (sentinels / name).write_text("harmless P034 denial sentinel\n")
    (bundle / "preflight.txt").write_text("P034 harmless read sentinel\n")
    probe = bundle / "preflight.py"
    probe.write_text(
        "import errno,json,os,socket,subprocess,sys\n"
        "from pathlib import Path\n"
        "bundle,denied,out=map(Path,sys.argv[1:])\n"
        "for p in [bundle/'preflight.txt',bundle/'input.json',"
        "bundle/'runtime/archguard/security/analyzer_v3.py']:\n"
        "    assert p.read_bytes()\n"
        "checks={}\n"
        f"for name in {categories!r}:\n"
        "    try:\n"
        "        fd=os.open(denied/name,os.O_RDONLY)\n"
        "    except OSError as e:\n"
        "        assert e.errno in (errno.EACCES,errno.EPERM), e\n"
        "        checks[name]=True\n"
        "    else:\n"
        "        os.close(fd);raise AssertionError('protected read allowed')\n"
        "try:\n"
        "    (denied/'write-attempt').write_text('x')\n"
        "except OSError as e:\n"
        "    assert e.errno in (errno.EACCES,errno.EPERM)\n"
        "    checks['write_outside']=True\n"
        "else: raise AssertionError('write allowed')\n"
        "try:\n"
        "    s=socket.socket();s.connect(('127.0.0.1',9))\n"
        "except OSError as e:\n"
        "    assert e.errno in (errno.EACCES,errno.EPERM), e\n"
        "    checks['network']=True\n"
        "else: raise AssertionError('network allowed')\n"
        "try:\n"
        "    subprocess.run(['/usr/bin/true'],check=True)\n"
        "except OSError as e:\n"
        "    assert e.errno in (errno.EACCES,errno.EPERM), e\n"
        "    checks['unauthorized_process']=True\n"
        "else: raise AssertionError('process allowed')\n"
        "(out/'preflight-ok').write_text('P034')\n"
        "print(json.dumps(checks,sort_keys=True))\n"
    )
    bootstrap = bundle / "runtime/launch.py"
    result = subprocess.run(
        command(policy, str(probe), str(bundle), str(sentinels), str(output)),
        env=environment(bundle, temporary),
        cwd=bundle,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        (policy.parent / "preflight-failure.log").write_text(result.stderr)
        raise ValueError("P034_BLOCKED_OS_ISOLATION_UNAVAILABLE")
    checks = json.loads(result.stdout)
    if len(checks) != len(categories) + 3 or not all(v is True for v in checks.values()):
        raise ValueError("P034_BLOCKED_OS_ISOLATION_UNAVAILABLE")
    imported = subprocess.run(
        command(policy, str(bootstrap), "--preflight"),
        env=environment(bundle, temporary),
        cwd=bundle,
        capture_output=True,
        text=True,
    )
    if imported.returncode or imported.stdout.strip() != "P034_RUNTIME_IMPORTS_VERIFIED":
        (policy.parent / "preflight-import-failure.log").write_text(imported.stderr)
        raise ValueError("P034_BLOCKED_OS_ISOLATION_UNAVAILABLE")
    return seal(
        dict(
            mechanism="macOS Seatbelt sandbox-exec",
            OS_LEVEL_ISOLATION="VERIFIED",
            checks=checks,
            allowed_reads=3,
            protected_reads_succeeded=0,
            protected_reads_denied=len(categories),
            direct_protected_content_probes=0,
            probe_type="dedicated harmless sentinels outside the read allowlist",
            denial_errno=[errno.EACCES, errno.EPERM],
            policy_sha256=digest(policy.read_text()),
            runtime_imports_verified=True,
        )
    )
