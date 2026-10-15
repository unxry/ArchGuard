"""P031.A.2 metadata binding and immutable custody; no case interpretation or writes."""

import copy
import socket
from typing import Any, Literal, Self

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

import archguard.infrastructure.security_review_recovery as r
import archguard.infrastructure.thesis_closure as thesis
import archguard.infrastructure.unified_human_review as io
from archguard.benchmark.oss.models import digest

RESPONSE_PINS = {
    "A": "e935ff30c565e3f6597fc7d4ef38928593666f607079e815dd56b27ee1beb20a",
    "B": "01e5b7e8f15be7dd0a2f0a055fed52e82307ebf69a273f9ba79490340f5e5b47",
}
PACKET_PINS = {
    "A": "fb4955544a76e6b8284bd7499f691bd5086639d078a5297b5187bc33d6b55f18",
    "B": "1c69e33686a71db1d3b15636401cdd8dbb2417231d51c232668f7bc58efcf47d",
}
PRIOR_PINS = {
    "review-completeness.json": "7754de726bf6a19748703253548b21e12fb2194be94388c3928419b101293f2a",
    "security-human-agreement.json": (
        "0bed58cc8a2ccdb2590d3bc27005b1d13fdec23d8ca1ddd1a3a905733578f0fb"
    ),
}
RECEIPT = r.PUBLIC / "security-human-provenance-receipt.json"


class AttestationReceipt(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    protocol_stage: Literal["P031.A.2"]
    reviewer_slot: Literal["A", "B"]
    benchmark_version: Literal["security-controlled-generator-v1"]
    packet_set_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    authoritative_response_set_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    response_count: Literal[300]
    human_origin: Literal["COORDINATOR_ATTESTED"]
    independence: Literal["COORDINATOR_ATTESTED"]
    AI_GENERATED_BY_P031: Literal["NO"]
    AI_REWRITTEN_BY_P031: Literal["NO"]
    semantic_edits_by_recovery: Literal[0]
    provenance_role: Literal["AUTHORITATIVE_PER_CASE_RESPONSE_SET"]
    aggregate_master_role: Literal["NON_AUTHORITATIVE_HISTORICAL_PROVENANCE"]
    authoritative_source: Literal["FROZEN_PER_CASE_RESPONSE_SET"]
    attestation_source: Literal["COORDINATOR_STATEMENT_P031_A_2"]
    cryptographic_authorship_proof: Literal[False]
    cryptographic_noncommunication_proof: Literal[False]
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def binding(self) -> Self:
        if self.fingerprint != digest(self.model_dump(exclude={"fingerprint"})):
            raise ValueError("P031_A2_INVALID_RECEIPT_SEAL")
        if (
            self.authoritative_response_set_fingerprint != RESPONSE_PINS[self.reviewer_slot]
            or self.packet_set_fingerprint != PACKET_PINS[self.reviewer_slot]
        ):
            raise ValueError("P031_A2_WRONG_FROZEN_SET_BINDING")
        return self


@pytest.fixture
def public() -> dict[str, Any]:
    return io.read_seal(RECEIPT)


def private_receipt(slot: str, public: dict[str, Any]) -> dict[str, Any]:
    path = r.PRIVATE / "provenance" / slot / "authoritative-response-attestation.json"
    if not path.exists():
        pytest.skip("Private human-provenance custody is not mounted")
    return io.read_seal(path, public["response_sets"][slot]["attestation_receipt_fingerprint"])


@pytest.mark.parametrize("slot", ["A", "B"])
def test_exact_response_packet_and_private_attestation_binding(
    public: dict[str, Any], slot: str
) -> None:
    private = private_receipt(slot, public)
    validated = AttestationReceipt.model_validate(private)
    binding = public["response_sets"][slot]
    assert validated.reviewer_slot == slot
    assert validated.authoritative_response_set_fingerprint == binding["response_set_fingerprint"]
    assert validated.packet_set_fingerprint == binding["packet_set_fingerprint"]
    assert validated.response_count == binding["response_count"] == 300
    assert validated.human_origin == binding["human_origin"] == "COORDINATOR_ATTESTED"
    assert validated.independence == binding["independence"] == "COORDINATOR_ATTESTED"
    assert binding["authoritative_source"] == "PER_CASE_FROZEN_SET"
    assert binding["aggregate_master_authoritative"] is False
    assert binding["aggregate_master_role"] == "HISTORICAL_TRANSPORT_ONLY"


@pytest.mark.parametrize(
    "field,value",
    [
        ("authoritative_response_set_fingerprint", "0" * 64),
        ("packet_set_fingerprint", "0" * 64),
        ("reviewer_slot", "B"),
        ("response_count", 299),
        ("human_origin", "CRYPTOGRAPHICALLY_PROVEN"),
        ("independence", "NOT_ATTESTED"),
        ("semantic_edits_by_recovery", 1),
        ("aggregate_master_role", "AUTHORITATIVE"),
        ("AI_REWRITTEN_BY_P031", "YES"),
        ("cryptographic_authorship_proof", True),
        ("unapproved_identity", "not allowed"),
    ],
)
def test_receipt_schema_rejects_wrong_binding_even_with_valid_seal(
    public: dict[str, Any], field: str, value: Any
) -> None:
    broken = copy.deepcopy(private_receipt("A", public))
    broken.pop("fingerprint")
    broken[field] = value
    broken = thesis.sealed(broken)
    with pytest.raises(ValidationError):
        AttestationReceipt.model_validate(broken)


def test_public_receipt_contains_only_aggregate_non_authoritative_provenance(
    public: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("Network or adjudication execution is forbidden in provenance binding")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(r, "adjudication_packet", forbidden)
    r.privacy((RECEIPT,))
    assert public["protocol_stage"] == "P031.A.2"
    assert public["aggregate_A_caveat"] == dict(
        rationales_different=288,
        evidence_notes_different=300,
        authoritative_source="FROZEN_PER_CASE_RESPONSE_SET",
        aggregate_master_authoritative=False,
    )
    assert all(
        public[k] == 0
        for k in (
            "AI_generated_labels",
            "AI_rewrites",
            "response_semantic_edits",
            "provider_calls",
            "connectivity_calls",
            "credential_reads",
            "paid_spend",
            "DEV_detector_predictions",
            "FINAL_detector_predictions",
            "AI_adjudications",
        )
    )
    assert public["truth_300"] == public["DEV_truth"] == public["FINAL_truth"] == "NOT_FROZEN"
    assert public["P032"] == "NOT_STARTED"
    assert not any("truth" in k.lower() and "fingerprint" in k.lower() for k in public)
    assert all(all(n == 0 for n in v.values()) for v in public["field_changes"].values())


def test_original_public_freezes_and_agreement_remain_identical(public: dict[str, Any]) -> None:
    parent = io.read_seal(
        r.PUBLIC / "resume-freeze-index.json",
        "8fc2f1ab0f55d1a2c785913b73eafdf725d98fb3422ca75837417cd38f83f2cd",
    )
    for name, fingerprint in PRIOR_PINS.items():
        io.read_seal(r.PUBLIC / name, fingerprint)
    for name, byte_hash in parent["files"].items():
        assert io.sha(r.PUBLIC / name) == byte_hash
    stats = io.read_seal(r.PUBLIC / "security-human-agreement.json")["statistics"]["ALL"]
    assert stats["N"] == 300 and stats["exact_agreements"] == public["exact_agreements"] == 290
    assert stats["disagreements"] == public["disagreements"] == 10
    assert stats["cohens_kappa"] == public["cohens_kappa"] == 7959 / 8459


def test_private_byte_inventory_responses_masters_and_packets_are_unchanged(
    public: dict[str, Any],
) -> None:
    if not (r.PRIVATE / "freeze-index.json").exists():
        pytest.skip("Private frozen custody is not mounted")
    index = io.read_seal(r.PRIVATE / "freeze-index.json")
    for name, byte_hash in index["files"].items():
        if io.sha(r.PRIVATE / name) != byte_hash:
            pytest.fail("Frozen private custody byte drift")
    for slot in ("A", "B"):
        frozen = io.read_seal(r.PRIVATE / "frozen" / f"reviewer-{slot}.json", RESPONSE_PINS[slot])
        root = r.PRIVATE / "responses" / slot
        paths = sorted(root.iterdir())
        assert len(paths) == 300 and all(p.is_file() and p.suffix == ".json" for p in paths)
        rows = {p.stem: r.read_object(p, 128_000) for p in paths}
        assert digest(dict(reviewer_slot=slot, responses=rows)) == RESPONSE_PINS[slot]
        assert frozen["responses"] == rows
    packets = io.read_seal(
        r.PRIVATE / "adjudication/packet-set.json", public["adjudication_packet_set_fingerprint"]
    )
    assert len(packets["packets"]) == 10
    index = r.read_object(r.PRIVATE / "adjudication/index.json")
    assert len(index["entries"]) == 10
    assert all(e["completed"] is False for e in index["entries"])
    assert all("packet_path" in e and "response_destination" in e for e in index["entries"])
    closure = r.PUBLIC / "security-human-truth-closure.json"
    if closure.exists():
        # The A2 receipt is an immutable historical snapshot, before real human adjudication.
        accepted = io.read_seal(closure)
        assert accepted["adjudications_accepted"] == 10
        assert accepted["adjudications_remaining"] == 0
        assert len(list((r.PRIVATE / "adjudication/responses").glob("*.json"))) == 10
    else:
        assert not any((r.PRIVATE / "adjudication/responses").iterdir())
    assert public["human_adjudications_completed"] == 0


def test_provenance_seals_are_deterministic_and_no_operational_timestamp_is_added(
    public: dict[str, Any],
) -> None:
    for slot in ("A", "B"):
        value = private_receipt(slot, public)
        payload = {k: v for k, v in value.items() if k != "fingerprint"}
        assert thesis.sealed(payload) == value
        assert not any("timestamp" in k or k.endswith("_at") for k in payload)
    payload = {k: v for k, v in public.items() if k != "fingerprint"}
    assert thesis.sealed(payload) == public
