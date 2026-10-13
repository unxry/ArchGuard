"""Coordinator-authorized untouched FINAL suffix; no implicit paid execution."""

import argparse
import json
import os
from pathlib import Path

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
        if args.action == "prepare":
            print(json.dumps(c.prepare()))
            return
        c.git_gate(closed=args.action in {"verify", "freeze"})
        with p.offline_scope():
            model = p.model_gate()
        with c.scope(
            (c.ROOT, e.ROOT, e.LEDGER, c.PARTIAL, c.PARTIAL_PUBLIC, c.APPROVAL),
            (c.APPROVAL, c.LEDGER),
        ):
            if args.action == "approve":
                approval = c.approval_bindings() | {"paid_execution_approved": True}
                c.load(approval)
                receipt = p.seal(c.APPROVAL / "explicit-human-approval.json", approval)
                print(
                    json.dumps(
                        dict(
                            status="CONTINUATION_APPROVAL_FROZEN",
                            fingerprint=receipt["fingerprint"],
                            provider_invocations=0,
                        )
                    )
                )
                return
            sealed = io.read_seal(c.APPROVAL / "explicit-human-approval.json")
            approval = {k: v for k, v in sealed.items() if k != "fingerprint"}
            manifest, config, pricing, old, protocol = c.initialize(approval)
            new = c.segment_state(manifest, config, pricing)
            if protocol["model_lock_fingerprint"] != io.digest(model):
                raise PermissionError("P024_CONTINUATION_MODEL_DRIFT")
            sources = io.read_seal(c.ROOT / "source-bindings.json")["files"]
            uncaptured_ambiguity = any(
                not all(
                    (c.LEDGER / f"{new['attempts'][rid][-1]['prefix']}.{suffix}").exists()
                    for suffix in ("raw", "capture.json")
                )
                or (c.LEDGER / f"{new['attempts'][rid][-1]['prefix']}.outcome.json").exists()
                for rid in new["ambiguous"]
            )
            if args.action == "live" and (
                uncaptured_ambiguity
                or any(r["state"] not in {"ACCEPTED", "TECHNICAL_FAILED"} for r in new["results"])
            ):
                print(json.dumps(c.operational(new, old, "TERMINAL_OR_AMBIGUOUS_STOP")))
                return
            if args.action == "live" and any(
                len(h) >= 3 and rid not in new["accepted"] for rid, h in new["attempts"].items()
            ):
                print(json.dumps(c.operational(new, old, "RETRY_EXHAUSTED")))
                return
            if args.action == "live" and (
                old["exposure"]
                + new["exposure"]
                + pricing.charge(config["max_input_tokens"], config["max_output_tokens"])
                > c.CAP
            ):
                print(json.dumps(c.operational(new, old, "PAID_CAP_REACHED")))
                return
        if sources != {n: io.sha(Path(n)) for n in (*c.SOURCES, *p.SOURCES, *p.SHARED)}:
            raise PermissionError("P024_CONTINUATION_IMPLEMENTATION_DRIFT")
        if args.action == "verify":
            print(json.dumps(c.operational(new, old, "OFFLINE_CONTINUATION_VERIFIED")))
            return
        if args.action == "freeze":
            print(json.dumps(c.freeze(approval)))
            return
        from archguard.infrastructure.llm_provider import AIProviderSettings

        credential = Path(".env.ai.local")
        if (
            not credential.exists()
            or credential.is_symlink()
            or credential.stat().st_mode & 0o777 != 0o600
        ):
            raise PermissionError("P024_CONTINUATION_SECURE_CREDENTIAL_REQUIRED")
        token = e.core._CREDENTIAL.set(credential.resolve())
        guarded = e.core._GUARDED.set(True)
        try:
            settings = AIProviderSettings(_env_file=credential.resolve())
            transport = e.OpenAITransport(config, settings)
        finally:
            e.core._CREDENTIAL.reset(token)
            e.core._GUARDED.reset(guarded)
        with c.scope(
            (c.ROOT, e.ROOT, e.LEDGER, c.PARTIAL, c.PARTIAL_PUBLIC), (c.LEDGER,), live=True
        ):
            print(json.dumps(c.execute(approval, transport, transport.decode)))
    except (ValueError, OSError, KeyError):
        print(
            json.dumps(
                dict(
                    status="P024_CONTINUATION_BLOCKED_PROTOCOL_OR_APPROVAL",
                    provider_invocations=0 if args.action != "live" else None,
                )
            )
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
