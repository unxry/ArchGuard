"""Source-only third-human handoff; no adjudication acceptance or evaluation."""

import hashlib
import json
import re
from html import escape
from pathlib import Path
from typing import Any

from archguard.benchmark.oss.models import canonical, digest, seal
from archguard.benchmark.semantic_adjudication import (
    AdjudicatorBundle,
    AdjudicatorPacket,
    AdjudicatorSubmission,
    SafeConflictIndex,
)
from archguard.benchmark.semantic_holdout import (
    BlindedPacket,
    HoldoutSample,
    SourceEvidence,
    opaque_id,
)
from archguard.infrastructure.oss_benchmark import write_new
from archguard.infrastructure.oss_review import atomic_directory

INSTRUCTIONS = """Independent third-human adjudication — open this README first

Then open index.html locally. Review all four frozen cases in the supplied order.
Use only this package's source evidence, architecture contracts and unchanged rubric.
Preserve any evidence limitation honestly. No extra context or semantic hints are supplied.

You must be a REAL HUMAN and a THIRD DISTINCT PERSON, not Reviewer A or Reviewer B.
Do not access their decisions, identity, rationales, notes or evidence selections.
Do not communicate case answers with either reviewer before completing and freezing
your own submission. Do not obtain construction metadata or mutation/control relations.
Do not use AI, detectors or model assistance to decide, select evidence or write responses.

Assign your own independent category from POSITIVE, NEGATIVE, UNCERTAIN, OUT_OF_SCOPE.
Any of these four categories is permitted. You are not choosing a primary reviewer.
Make a copy of response-template.json. For each adjudicator blinded ID enter exactly
one category, your own nonempty rationale and at least one explicit evidence reference
with evidence_id/start_line/end_line (inclusive source line numbers). Notes are optional.
No category, rationale, note or evidence selection has been pre-populated.

After all four cases are independently complete, enter your real reviewer_identity
and REAL_HUMAN_INDEPENDENT_ADJUDICATION. This self-declares third-person distinction
and independence; the software does not externally verify identity or authorship.
Save your copy as completed-response.json and return it privately to the coordinator.
Do not edit the frozen bundle, guidance, schema, original blank form or freeze receipt.
Opening the package performs no upload, provider call or automatic judgment.
"""


def verify_conflict_inputs(
    manifest_path: Path,
    index_path: Path,
    analysis_path: Path,
    receipt_path: Path,
    expected: dict[str, str],
) -> SafeConflictIndex:
    values = {}
    for key, path in (
        ("conflicts", manifest_path),
        ("index", index_path),
        ("analysis", analysis_path),
        ("receipt", receipt_path),
    ):
        value = json.loads(path.read_bytes())
        if (
            value["fingerprint"] != expected[key]
            or digest({k: v for k, v in value.items() if k != "fingerprint"}) != expected[key]
        ):
            raise ValueError("unapproved P015.C frozen artifact")
        values[key] = value
    index = SafeConflictIndex.model_validate(values["index"])
    manifest, analysis, receipt = values["conflicts"], values["analysis"], values["receipt"]
    conflicts = manifest["conflicts"]
    primary = analysis["primary"]
    if (
        len(conflicts) != 4
        or manifest["conflict_count"] != 4
        or primary["n"] != 100
        or primary["exact_agreement"] != 96
        or primary["disagreement"] != 4
        or receipt["paired_cases"] != 100
        or receipt["conflict_count"] != 4
        or receipt["ground_truth_status"] != "FINAL_HUMAN_GROUND_TRUTH_NOT_FROZEN"
        or receipt["final_ground_truth_materialized"] is not False
        or manifest["final_ground_truth_materialized"] is not False
        or manifest["automatic_resolution"] is not False
        or analysis["final_ground_truth_materialized"] is not False
        or analysis["conflicts_resolved"] != 0
        or any(row["a_decision"] == row["b_decision"] for row in conflicts)
        or len({row["case_id"] for row in conflicts}) != 4
        or {(r["conflict_id"], r["case_id"], r["rule_id"], r["language"]) for r in conflicts}
        != {(r.conflict_id, r.case_id, r.rule_id, r.language) for r in index.cases}
        or any(
            receipt[field] != expected[key]
            for field, key in (
                ("conflict_manifest_fingerprint", "conflicts"),
                ("adjudicator_safe_index_fingerprint", "index"),
                ("agreement_analysis_fingerprint", "analysis"),
            )
        )
    ):
        raise ValueError("frozen four-conflict membership/state mismatch")
    return index


def audit_adjudicator_bundle(bundle: AdjudicatorBundle, old_identifiers: tuple[str, ...]) -> None:
    forbidden = {
        "case_id",
        "conflict_id",
        "a_blinded_id",
        "b_blinded_id",
        "source_blinded_id",
        "source_packet_fingerprint",
        "a_decision",
        "b_decision",
        "a_category",
        "b_category",
        "transition",
        "disagreement_type",
        "rationale",
        "note",
        "reviewer_identity",
        "pair_id",
        "matched_pair_id",
        "operator_id",
        "expected_semantic_effect",
        "construction_intent",
        "private_provenance",
        "private_blinding_seed",
        "source_before",
        "source_after",
        "ai_results",
        "detector_results",
        "static_predictions",
        "graph_predictions",
        "structural_v2_predictions",
        "hybrid_predictions",
        "final_human_label",
    }
    marker = re.compile(
        r"MUTATION_CANDIDATE|MATCHED_CONTROL|\b(?:hb|hc|hp)-[a-f0-9]{32}\b|"
        r"intended[-_](?:positive|negative)|"
        r"(?:one\s+reviewer|reviewer\s*[ab])\s+(?:chose|said|selected|category|was\s+uncertain)|"
        r"reviewers\s+disagreed\s+between",
        re.IGNORECASE,
    )

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            if forbidden.intersection(value) or any(
                k.startswith(("reviewer_a_", "reviewer_b_")) for k in value
            ):
                raise ValueError("private reviewer/construction/model fields in adjudicator bundle")
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
        elif isinstance(value, str) and (
            marker.search(value) or any(identifier in value for identifier in old_identifiers)
        ):
            raise ValueError(
                "private identifier or reviewer/construction hint in adjudicator bundle"
            )

    walk(bundle.model_dump(mode="json"))


def render_adjudicator(bundle: AdjudicatorBundle) -> str:
    sections = []
    navigation = []
    for i, packet in enumerate(bundle.packets, 1):
        identifier = escape(packet.blinded_id, quote=True)
        navigation.append(f'<li><a href="#{identifier}">{identifier}</a></li>')
        evidence = []
        for source in packet.evidence:
            lines = "\n".join(
                f"{line:4}  {escape(text)}" for line, text in enumerate(source.text.splitlines(), 1)
            )
            evidence.append(
                f"<details open><summary>{escape(source.evidence_id)} · "
                f"{escape(source.path)}</summary>"
                f"<p>SHA256: <code>{source.sha256}</code></p><pre>{lines}</pre></details>"
            )
        sections.append(
            f'<section id="{identifier}"><h2>{i}. {identifier}</h2>'
            f"<p>{escape(packet.rule_id)} · {escape(packet.language)}</p>"
            f"<p>Target: {escape(packet.target_component)} · {escape(packet.target_path)}</p>"
            "<h3>Frozen architecture contract</h3>"
            f"<pre>{escape(packet.architecture_contract)}</pre>"
            "<h3>Frozen rule guidance</h3>"
            f"<p>{escape(bundle.guidance['rules'][packet.rule_id])}</p>"
            + "".join(evidence)
            + '<p><a href="#contents">Back to case list</a></p></section>'
        )
    return (
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
        "style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'\">"
        "<title>Independent third-human adjudication</title>"
        "<style>body{font:16px system-ui;max-width:1050px;margin:2rem auto;padding:1rem}"
        "pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:14px}"
        "section{border-top:1px solid #aaa;margin-top:2rem}details{margin:1rem 0}</style><body>"
        f"<h1>Independent third human — four frozen cases</h1><pre>{escape(INSTRUCTIONS)}</pre>"
        f"<h2>Frozen general guidance</h2><p>{escape(bundle.guidance['general'])}</p>"
        f"<p>{escape(bundle.guidance['arch201_vs_arch205'])}</p>"
        '<h2 id="contents">Frozen adjudicator order</h2><ol>'
        + "".join(navigation)
        + "</ol>"
        + "".join(sections)
        + "</body></html>\n"
    )


def build_adjudicator_material(
    index_path: Path,
    sample_path: Path,
    packet_root: Path,
    guidance_path: Path,
    seed: bytes,
    *,
    expected_index_fingerprint: str,
    expected_sample_fingerprint: str,
    expected_guidance_fingerprint: str,
) -> tuple[AdjudicatorBundle, dict[str, Any], dict[str, bytes]]:
    if len(seed) != 32:
        raise ValueError("separate 256-bit private blinding key required")
    index = SafeConflictIndex.model_validate_json(index_path.read_bytes())
    sample = HoldoutSample.model_validate_json(sample_path.read_bytes())
    raw_guidance = guidance_path.read_bytes()
    guidance = json.loads(raw_guidance)
    if (
        index.fingerprint != expected_index_fingerprint
        or sample.fingerprint != expected_sample_fingerprint
        or guidance["fingerprint"] != expected_guidance_fingerprint
        or digest({k: v for k, v in guidance.items() if k != "fingerprint"})
        != expected_guidance_fingerprint
    ):
        raise ValueError("unapproved frozen source-only inputs")
    by_case = {c.case_id: c for c in sample.cases}
    packets: list[AdjudicatorPacket] = []
    mapping_rows: list[dict[str, Any]] = []
    old_identifiers: list[str] = []
    for conflict in index.cases:
        case = by_case.get(conflict.case_id)
        if case is None or (case.rule_id, case.language) != (conflict.rule_id, conflict.language):
            raise ValueError("frozen conflict absent from scientific source mapping")
        path = packet_root / (case.blinded_id + ".json")
        if path.is_symlink() or path.resolve().parent != packet_root.resolve():
            raise ValueError("source packet path escaped frozen packet directory")
        original = BlindedPacket.model_validate_json(path.read_bytes())
        if (
            original.fingerprint != case.packet_fingerprint
            or original.blinded_id != case.blinded_id
            or (original.rule_id, original.language) != (conflict.rule_id, conflict.language)
        ):
            raise ValueError("frozen source packet binding mismatch")
        identifier = "adj-" + opaque_id(seed, "adjudicator-id-v1", case.case_id)[:32]
        evidence = tuple(
            SourceEvidence(
                evidence_id="aev-"
                + opaque_id(seed, "adjudicator-evidence-v1", (identifier, e.path))[:24],
                path=e.path,
                text=e.text,
                sha256=e.sha256,
            )
            for e in original.evidence
        )
        packet = seal(
            AdjudicatorPacket,
            blinded_id=identifier,
            rule_id=original.rule_id,
            language=original.language,
            target_path=original.target_path,
            target_component=original.target_component,
            architecture_contract=original.architecture_contract,
            evidence=evidence,
        )
        packets.append(packet)
        mapping_rows.append(
            {
                "adjudicator_blinded_id": identifier,
                "case_id": case.case_id,
                "source_blinded_id": case.blinded_id,
                "conflict_id": conflict.conflict_id,
                "source_packet_fingerprint": original.fingerprint,
                "adjudicator_packet_fingerprint": packet.fingerprint,
                "evidence_mapping": {
                    new.evidence_id: old.evidence_id
                    for new, old in zip(evidence, original.evidence, strict=True)
                },
            }
        )
        old_identifiers.extend(
            (case.case_id, case.blinded_id, conflict.conflict_id, original.project_alias)
        )
        old_identifiers.extend(e.evidence_id for e in original.evidence)
    ordered = tuple(
        sorted(
            packets,
            key=lambda p: (opaque_id(seed, "adjudicator-order-v1", p.blinded_id), p.blinded_id),
        )
    )
    bundle = seal(
        AdjudicatorBundle,
        schema_version="blank-independent-adjudicator-bundle-v1",
        reviewer_slot="ADJUDICATOR",
        status="WAITING_FOR_ADJUDICATOR",
        packets=ordered,
        guidance=guidance,
    )
    audit_adjudicator_bundle(bundle, tuple(old_identifiers))
    mapping = {
        "schema_version": "adjudicator-private-mapping-v1",
        "algorithm": "HMAC-SHA256/domain-separated-v1",
        "private_blinding_key_hex": seed.hex(),
        "safe_index_fingerprint": index.fingerprint,
        "sample_fingerprint": sample.fingerprint,
        "guidance_fingerprint": guidance["fingerprint"],
        "bundle_fingerprint": bundle.fingerprint,
        "rows": sorted(mapping_rows, key=lambda r: r["adjudicator_blinded_id"]),
    }
    mapping["fingerprint"] = digest(mapping)
    template: dict[str, Any] = {
        "schema_version": "semantic-holdout-adjudication-submission-v1",
        "reviewer_slot": "ADJUDICATOR",
        "bundle_fingerprint": bundle.fingerprint,
        "reviewer_identity": "",
        "attestation": None,
        "responses": [
            {
                "blinded_id": p.blinded_id,
                "decision": None,
                "rationale": "",
                "evidence": [],
                "note": "",
            }
            for p in ordered
        ],
    }
    contents = {
        "bundle-v1.json": (canonical(bundle) + "\n").encode(),
        "rule-guidance-v1.json": raw_guidance,
        "index.html": render_adjudicator(bundle).encode(),
        "README.txt": INSTRUCTIONS.encode(),
        "response-template.json": (json.dumps(template, indent=2) + "\n").encode(),
        "submission-schema.json": (
            json.dumps(AdjudicatorSubmission.model_json_schema(), indent=2) + "\n"
        ).encode(),
    }
    for body in contents.values():
        if any(identifier.encode() in body for identifier in old_identifiers):
            raise ValueError("primary/scientific identifiers exposed in handoff")
    return bundle, mapping, contents


def handoff_receipt(bundle: AdjudicatorBundle, contents: dict[str, bytes]) -> dict[str, Any]:
    template = json.loads(contents["response-template.json"])
    rows = template["responses"]
    if (
        len(rows) != 4
        or [r["blinded_id"] for r in rows] != [p.blinded_id for p in bundle.packets]
        or template["reviewer_identity"] != ""
        or template["attestation"] is not None
        or template["bundle_fingerprint"] != bundle.fingerprint
        or any(
            r["decision"] is not None
            or r["rationale"] != ""
            or r["evidence"] != []
            or r["note"] != ""
            for r in rows
        )
        or json.loads(contents["submission-schema.json"])
        != AdjudicatorSubmission.model_json_schema()
    ):
        raise ValueError("handoff must contain exactly four blank responses and unchanged schema")
    receipt = {
        "schema_version": "adjudicator-handoff-freeze-v1",
        "bundle_fingerprint": bundle.fingerprint,
        "case_count": 4,
        "unique_adjudicator_ids": 4,
        "prepopulated_decisions": 0,
        "prepopulated_rationales": 0,
        "prepopulated_evidence": 0,
        "prepopulated_notes": 0,
        "A_B_category_leakage_findings": 0,
        "A_B_rationale_note_evidence_leakage_findings": 0,
        "construction_leakage_findings": 0,
        "model_detector_leakage_findings": 0,
        "files": {name: hashlib.sha256(body).hexdigest() for name, body in contents.items()},
    }
    return receipt | {"fingerprint": digest(receipt)}


def freeze_adjudicator_handoff(
    destination: Path,
    coordinator: Path,
    bundle: AdjudicatorBundle,
    mapping: dict[str, Any],
    contents: dict[str, bytes],
) -> dict[str, Any]:
    if any(p.exists() or p.is_symlink() for p in (destination, coordinator)):
        raise ValueError("adjudicator package and mapping immutable; cannot overwrite")
    receipt = handoff_receipt(bundle, contents)

    def build_mapping(stage: Path) -> None:
        stage.chmod(0o700)
        write_new(stage / "adjudicator-mapping-v1.json", mapping)
        (stage / "adjudicator-mapping-v1.json").chmod(0o600)

    def build_handoff(stage: Path) -> None:
        stage.chmod(0o700)
        for name, body in contents.items():
            with (stage / name).open("xb") as output:
                output.write(body)
        write_new(stage / "handoff-freeze.json", receipt)

    atomic_directory(coordinator, build_mapping)
    atomic_directory(destination, build_handoff)
    return receipt


def verify_adjudicator_handoff(
    destination: Path,
    coordinator: Path,
    mapping: dict[str, Any],
    contents: dict[str, bytes],
    receipt: dict[str, Any],
) -> None:
    if destination.is_symlink() or coordinator.is_symlink():
        raise ValueError("symlinked adjudicator freeze forbidden")
    if {p.name for p in destination.iterdir()} != {*contents, "handoff-freeze.json"} or {
        p.name for p in coordinator.iterdir()
    } != {"adjudicator-mapping-v1.json"}:
        raise ValueError("adjudicator freeze inventory changed")
    expected = {name: body for name, body in contents.items()}
    expected["handoff-freeze.json"] = (canonical(receipt) + "\n").encode()
    for name, body in expected.items():
        path = destination / name
        if path.is_symlink() or path.read_bytes() != body:
            raise ValueError("adjudicator frozen material changed")
    path = coordinator / "adjudicator-mapping-v1.json"
    if path.is_symlink() or path.read_bytes() != (canonical(mapping) + "\n").encode():
        raise ValueError("private adjudicator mapping changed")
