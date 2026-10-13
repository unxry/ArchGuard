"""Offline final preflight; paid mode requires a new manifest-bound human approval."""

import argparse
import json
import os
from pathlib import Path

from archguard.infrastructure import development_llm_executor as core
from archguard.infrastructure import final_llm_executor as e
from archguard.infrastructure import final_llm_preflight as p
from archguard.infrastructure import unified_human_review as io


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "verify", "live"))
    parser.add_argument("--approval", type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        if args.action != "live":
            r = p.prepare(verify=args.action == "verify")
            print(
                json.dumps(
                    dict(
                        status=r["status"],
                        requests=300,
                        cost=r["cost"],
                        paid_execution_approved=False,
                        provider_invocations=0,
                    )
                )
            )
            return
        if args.approval is None:
            raise PermissionError("P024_EXPLICIT_FINAL_APPROVAL_REQUIRED")
        io._safe_path(args.approval)
        if not args.approval.resolve().is_relative_to(e.APPROVAL_ROOT.resolve()):
            raise PermissionError("P024_FINAL_APPROVAL_ROOT_REQUIRED")
        with p.offline_scope():
            approval = json.loads(args.approval.read_bytes(), parse_float=str)
            with e.final_scope(e.ROOT, e.LEDGER):
                e.approval_check(approval, e.ROOT)
                _, config, _ = e.load_bundle(e.ROOT)
                sources = io.read_seal(e.ROOT / "source-bindings.json")["files"]
            p.git_gate(live=True)
            p.model_gate()
            if sources != {n: io.sha(Path(n)) for n in (*p.SOURCES, *p.SHARED)}:
                raise PermissionError("P024_IMPLEMENTATION_DRIFT")
        from archguard.infrastructure.llm_provider import AIProviderSettings

        credential = Path(".env.ai.local")
        if credential.is_symlink() or (
            credential.exists() and credential.stat().st_mode & 0o777 != 0o600
        ):
            raise PermissionError("P024_SECURE_CREDENTIAL_CONFIGURATION_REQUIRED")
        token = core._CREDENTIAL.set(credential.resolve())
        guarded = core._GUARDED.set(True)
        try:
            settings = AIProviderSettings(_env_file=credential.resolve())
            transport = e.OpenAITransport(config, settings)
        finally:
            core._CREDENTIAL.reset(token)
            core._GUARDED.reset(guarded)
        with e.final_scope(e.ROOT, e.LEDGER, live=True):
            report = e.execute(e.ROOT, e.LEDGER, approval, transport, transport.decode)
        print(json.dumps(report))
    except (ValueError, OSError, KeyError):
        print(
            json.dumps(
                dict(
                    status="P024_BLOCKED_PROTOCOL_OR_AUTHORIZATION",
                    provider_invocations=0 if args.action != "live" else None,
                )
            )
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
