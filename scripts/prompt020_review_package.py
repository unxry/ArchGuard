"""Prospective human handoff v2: opaque packet order, no construction capability."""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from archguard.benchmark.oss.models import digest, seal
from archguard.benchmark.semantic_holdout import BlindedPacket
from archguard.benchmark.semantic_preflight import QUESTIONS
from archguard.benchmark.semantic_review import (
    ReviewerABundle,
    ReviewerASubmission,
    ReviewerBBundle,
    ReviewerBSubmission,
)
from archguard.infrastructure import unified_hybrid as experiment
from archguard.infrastructure.component_holdout import offline
from archguard.infrastructure.semantic_positive_evaluation_freeze import (
    append_sealed,
    evaluation_io,
)
from archguard.infrastructure.semantic_positive_offline import audit_metadata

DESTINATION = experiment.FINAL / "review-v2"
RECEIPT = experiment.BASE / "p020-blinded-review-handoff-v2.json"


def blinded_order(packets: tuple[BlindedPacket, ...], slot: str) -> tuple[BlindedPacket, ...]:
    if slot not in {"A", "B", "INVENTORY"}:
        raise ValueError("unregistered reviewer stream")
    return tuple(
        sorted(packets, key=lambda p: digest(("p020-review-order-v2", slot, p.blinded_id)))
    )


def freeze() -> dict[str, Any]:
    source = experiment.FINAL / "review/packets"
    with evaluation_io(Path("experiments"), (source,), DESTINATION):
        packets = tuple(
            BlindedPacket.model_validate_json(p.read_bytes()) for p in source.glob("*.json")
        )
        if len(packets) != 100 or len({p.blinded_id for p in packets}) != 100:
            raise ValueError("100 unique original packets required")
        for p in packets:
            audit_metadata(p.model_dump(mode="json"))
        inventory = append_sealed(
            DESTINATION / "packet-inventory.json",
            dict(
                rows=[
                    dict(blinded_id=p.blinded_id, packet_fingerprint=p.fingerprint)
                    for p in blinded_order(packets, "INVENTORY")
                ]
            ),
        )
        protocol = append_sealed(
            DESTINATION / "protocol.json",
            dict(
                version="p020-human-review-v2",
                packet_fingerprint=inventory["fingerprint"],
                ordering="SHA256_VERSION_SLOT_BLINDED_ID; NO_CONSTRUCTION_ORDER",
                independent_slots=["A", "B"],
                categories=["POSITIVE", "NEGATIVE", "UNCERTAIN", "OUT_OF_SCOPE"],
                adjudication="THIRD_REAL_INDEPENDENT_HUMAN; CATEGORICAL_CONFLICTS_ONLY",
                legacy_packages="SUPERSEDED; NEVER_HANDED_OFF",
                human_review_performed=False,
            ),
        )
        guidance = append_sealed(
            DESTINATION / "guidance.json",
            dict(
                questions=QUESTIONS,
                instructions=(
                    "Independent real humans only; no AI assistance or other reviewer answers. "
                    "Use each supplied target question and contract/source behavior. "
                    "Names alone are insufficient. All categories need a human rationale "
                    "and supplied evidence_id plus valid line ranges. Distinguish uncertainty "
                    "from non-applicability; do not infer paired roles or compare packets."
                ),
            ),
        )
        assignments = []
        for slot, model, submission in (
            ("A", ReviewerABundle, ReviewerASubmission),
            ("B", ReviewerBBundle, ReviewerBSubmission),
        ):
            ordered = blinded_order(packets, slot)
            bundle = seal(
                model,
                schema_version="blank-independent-human-bundle-v1",
                reviewer_slot=slot,
                status="WAITING_FOR_REAL_INDEPENDENT_HUMAN",
                packets=ordered,
                protocol=protocol,
                guidance=guidance,
            )
            append_sealed(DESTINATION / slot / "bundle.json", bundle.model_dump(mode="json"))
            append_sealed(
                DESTINATION / slot / "submission-schema.json",
                dict(schema=submission.model_json_schema()),
            )
            template = dict(
                schema_version="semantic-holdout-human-submission-v1",
                reviewer_slot=slot,
                bundle_fingerprint=bundle.fingerprint,
                reviewer_identity="",
                attestation="",
                responses=[
                    dict(blinded_id=p.blinded_id, decision=None, rationale="", evidence=[], note="")
                    for p in ordered
                ],
            )
            # A blank form is deliberately not a valid/attested human submission.
            (DESTINATION / slot / "submission-template.json").write_text(
                experiment.canonical(template) + "\n"
            )
            assignments.append(
                dict(reviewer_slot=slot, bundle_fingerprint=bundle.fingerprint, packet_count=100)
            )
        assignment = append_sealed(DESTINATION / "assignment-manifest.json", dict(rows=assignments))
        files = experiment.source_inventory(DESTINATION)
        material = append_sealed(DESTINATION / "material-freeze.json", dict(files=files))
    return experiment.freeze_public(
        RECEIPT.name,
        dict(
            version="p020-blinded-review-handoff-v2",
            authoritative_handoff=True,
            supersedes_review_packaging_only=True,
            source_packets_unchanged=True,
            reason=(
                "REMOVE_CONSTRUCTION_ADJACENCY_FROM_BUNDLE_ORDER; ADD_EXISTING_RULE_GUIDANCE; "
                "NO_LABEL_SOURCE_COMPONENT_CHANGES"
            ),
            packet_inventory_fingerprint=inventory["fingerprint"],
            protocol_fingerprint=protocol["fingerprint"],
            assignments_fingerprint=assignment["fingerprint"],
            material_fingerprint=material["fingerprint"],
            script_sha256=experiment.sha(Path(__file__)),
            packets=100,
            human_labels_created=False,
            provider_calls=0,
        ),
    )


def verify() -> dict[str, Any]:
    receipt = experiment.read(RECEIPT)
    material = experiment.read(DESTINATION / "material-freeze.json")
    if material["fingerprint"] != receipt["material_fingerprint"]:
        raise ValueError("handoff material seal drift")
    files = experiment.source_inventory(DESTINATION)
    del files["material-freeze.json"]
    source_path = experiment.BASE / "p020-review-source-freeze-v1.json"
    source = experiment.read(source_path) if source_path.exists() else receipt
    if source.get("handoff_fingerprint", receipt["fingerprint"]) != receipt["fingerprint"]:
        raise ValueError("review source binding drift")
    if files != material["files"] or experiment.sha(Path(__file__)) != source["script_sha256"]:
        raise ValueError("handoff file/code drift")
    original = {
        p.stem: BlindedPacket.model_validate_json(p.read_bytes()).fingerprint
        for p in (experiment.FINAL / "review/packets").glob("*.json")
    }
    for slot, model in (("A", ReviewerABundle), ("B", ReviewerBBundle)):
        bundle = model.model_validate_json((DESTINATION / slot / "bundle.json").read_bytes())
        if bundle.packets != blinded_order(bundle.packets, slot):
            raise ValueError("reviewer ordering drift")
        if {p.blinded_id: p.fingerprint for p in bundle.packets} != original:
            raise ValueError("original packets changed")
        for p in bundle.packets:
            audit_metadata(p.model_dump(mode="json"))
        template = json.loads((DESTINATION / slot / "submission-template.json").read_bytes())
        if (
            template["attestation"]
            or template["reviewer_identity"]
            or any(
                r["decision"] is not None or r["rationale"] or r["evidence"]
                for r in template["responses"]
            )
        ):
            raise ValueError("human content fabricated")
    return dict(
        status="P020_BLINDED_REVIEW_V2_VERIFIED", packets=100, source_packets_unchanged=True
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "verify"))
    args = parser.parse_args()
    os.umask(0o077)
    sys.addaudithook(offline)
    result = freeze() if args.action == "freeze" else verify()
    print(
        json.dumps({k: v for k, v in result.items() if k in {"status", "fingerprint", "packets"}})
    )


if __name__ == "__main__":
    main()
