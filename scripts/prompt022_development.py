"""Offline preflight by default. Future live requires an explicit scoped numeric approval."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from archguard.infrastructure import development_llm_executor as executor
from archguard.infrastructure import development_llm_preflight as preflight
from archguard.infrastructure import unified_human_review as io


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "verify", "live"))
    parser.add_argument("--approval", type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    sys.addaudithook(executor.audit_hook)
    executor._GUARDED.set(True)
    try:
        if args.action != "live":
            value = preflight.prepare(verify=args.action == "verify")
            print(
                json.dumps(
                    dict(
                        status=value["status"],
                        requests=180,
                        bundle_fingerprint=value["bundle_fingerprint"],
                        expected_usd=value["cost"]["expected_usd"],
                        recommended_cap_usd=value["cost"]["recommended_cap_usd"],
                        paid_execution_approved=False,
                        provider_invocations=0,
                    )
                )
            )
            return
        if args.approval is None:
            raise PermissionError("P022_EXPLICIT_APPROVAL_REQUIRED")
        approval = io._json(args.approval.read_bytes())
        bundle = io.read_seal(preflight.ROOT / "bundle-freeze.json")
        executor.approval_check(approval, bundle["fingerprint"])
        io.scientific_status(
            subprocess.check_output(
                ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"]
            )
        )
        for sha in preflight.ANCHORS.values():
            if subprocess.run(
                ["git", "merge-base", "--is-ancestor", sha, "HEAD"], capture_output=True
            ).returncode:
                raise io.ReviewBlocked("P022_LIVE_LINEAGE_DRIFT")
        # A numeric cap and the exact scoped bundle are checked before any secret access.
        with executor.executor_scope(preflight.ROOT, preflight.LEDGER):
            _, config, _ = executor.load_bundle(preflight.ROOT)
            sources = io.read_seal(preflight.ROOT / "source-bindings.json")
        if set(sources["files"]) != set((*preflight.SOURCE_FILES, *preflight.ADAPTER_FILES)):
            raise io.ReviewBlocked("P022_EXECUTOR_SOURCE_ALLOWLIST_DRIFT")
        for name, h in sources["files"].items():
            if io.sha(Path(name)) != h:
                raise io.ReviewBlocked("P022_EXECUTOR_IMPLEMENTATION_DRIFT")
        from archguard.infrastructure.llm_provider import AIProviderSettings

        credential = Path(".env.ai.local")
        if credential.is_symlink() or (
            credential.exists() and credential.stat().st_mode & 0o777 != 0o600
        ):
            raise PermissionError("P022_SECURE_CREDENTIAL_CONFIGURATION_REQUIRED")
        credential = credential.resolve()
        token = executor._CREDENTIAL.set(credential)
        try:
            settings = AIProviderSettings(_env_file=credential)
            transport = executor.OpenAITransport(config, settings)
        finally:
            executor._CREDENTIAL.reset(token)
        with executor.executor_scope(preflight.ROOT, preflight.LEDGER, live=True):
            report = executor.execute(
                preflight.ROOT, preflight.LEDGER, approval, transport, transport.decode
            )
        print(json.dumps(report))
    except (ValueError, OSError, PermissionError, KeyError):
        print(
            json.dumps(
                dict(
                    status="P022_BLOCKED_PROTOCOL_OR_AUTHORIZATION",
                    provider_invocations=None if args.action == "live" else 0,
                )
            )
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
