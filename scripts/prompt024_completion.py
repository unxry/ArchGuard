"""Explicitly authorized segment C; credential-free preparation and verification."""

import argparse
import json
import os
from pathlib import Path

from archguard.infrastructure import development_llm_executor as core
from archguard.infrastructure import final_llm_completion as f
from archguard.infrastructure import final_llm_continuation as c
from archguard.infrastructure import final_llm_executor as e
from archguard.infrastructure import final_llm_preflight as p
from archguard.infrastructure import unified_human_review as io


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "approve", "verify", "freeze", "live"))
    args = parser.parse_args()
    os.umask(0o077)
    try:
        f.git_gate(closed=args.action in {"verify", "freeze"})
        old_sources = io.read_seal(c.ROOT / "source-bindings.json")["files"]
        if old_sources != {n: io.sha(Path(n)) for n in (*c.SOURCES, *p.SOURCES, *p.SHARED)}:
            raise PermissionError("P024_COMPLETION_PRIOR_IMPLEMENTATION_DRIFT")
        if args.action == "prepare":
            print(json.dumps(f.prepare()))
            return
        with p.offline_scope():
            model = p.model_gate()
        with c.scope(f.READS, (f.APPROVAL, f.LEDGER)):
            if args.action == "approve":
                approval = f.approval_bindings()
                f.load(approval)
                sealed = p.seal(f.APPROVAL / "explicit-human-approval.json", approval)
                print(
                    json.dumps(
                        dict(
                            status="COMPLETION_APPROVAL_FROZEN",
                            fingerprint=sealed["fingerprint"],
                            new_provider_invocations=0,
                        )
                    )
                )
                return
            sealed = io.read_seal(f.APPROVAL / "explicit-human-approval.json")
            approval = {k: v for k, v in sealed.items() if k != "fingerprint"}
            manifest, config, pricing, old, protocol = f.initialize(approval)
            new = f.segment_state(manifest, config, pricing)
            if protocol["model_lock_fingerprint"] != io.digest(model):
                raise PermissionError("P024_COMPLETION_MODEL_DRIFT")
            sources = io.read_seal(f.ROOT / "source-bindings.json")["files"]
            if args.action == "live":
                terminal = next(
                    (
                        r["state"]
                        for r in new["results"]
                        if r["state"] not in {"ACCEPTED", "TECHNICAL_FAILED"}
                    ),
                    None,
                )
                uncaptured = any(
                    not all(
                        (f.LEDGER / f"{new['attempts'][rid][-1]['prefix']}.{s}").exists()
                        for s in ("raw", "capture.json")
                    )
                    or (f.LEDGER / f"{new['attempts'][rid][-1]['prefix']}.outcome.json").exists()
                    for rid in new["ambiguous"]
                )
                if terminal or uncaptured:
                    print(json.dumps(f.operational(new, old, terminal or "AMBIGUOUS_TRANSPORT")))
                    return
                remaining = [r for r in manifest["rows"] if r["request_id"] not in new["accepted"]]
                if not remaining:
                    print(json.dumps(f.operational(new, old, "COMPLETE")))
                    return
                if any(
                    len(h) >= 3 and rid not in new["accepted"] for rid, h in new["attempts"].items()
                ):
                    print(json.dumps(f.operational(new, old, "RETRY_EXHAUSTED")))
                    return
                if old["exposure"] + new["exposure"] + f.RESERVE > f.CAP:
                    print(json.dumps(f.operational(new, old, "PAID_CAP_REACHED")))
                    return
                if not new["ambiguous"]:
                    f.guard_request(remaining[0]["request_id"], manifest, old, new)
        if sources != {n: io.sha(Path(n)) for n in (*f.SOURCES, *c.SOURCES, *p.SOURCES, *p.SHARED)}:
            raise PermissionError("P024_COMPLETION_IMPLEMENTATION_DRIFT")
        if args.action == "verify":
            print(json.dumps(f.operational(new, old, "OFFLINE_COMPLETION_VERIFIED")))
            return
        if args.action == "freeze":
            print(json.dumps(f.freeze(approval)))
            return
        from archguard.infrastructure.llm_provider import AIProviderSettings

        credential = Path(".env.ai.local")
        if (
            not credential.exists()
            or credential.is_symlink()
            or credential.stat().st_mode & 0o777 != 0o600
        ):
            raise PermissionError("P024_COMPLETION_SECURE_CREDENTIAL_REQUIRED")
        token = core._CREDENTIAL.set(credential.resolve())
        guarded = core._GUARDED.set(True)
        try:
            settings = AIProviderSettings(_env_file=credential.resolve())
            transport = e.OpenAITransport(config, settings)
        finally:
            core._CREDENTIAL.reset(token)
            core._GUARDED.reset(guarded)
        with c.scope(f.READS, (f.LEDGER,), live=True):
            print(json.dumps(f.execute(approval, transport, transport.decode)))
    except (ValueError, OSError, KeyError):
        print(
            json.dumps(
                dict(
                    status="P024_COMPLETION_BLOCKED_PROTOCOL_OR_APPROVAL",
                    new_provider_invocations=0 if args.action != "live" else None,
                )
            )
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
