"""Reviewer order must depend on opaque IDs, never incoming construction order."""

from types import SimpleNamespace

import pytest

from scripts.prompt020_review_package import blinded_order


@pytest.mark.parametrize("slot", ["A", "B", "INVENTORY"])
def test_blinded_order_is_permutation_invariant(slot):
    packets = tuple(SimpleNamespace(blinded_id="opaque" + str(i)) for i in range(100))
    first = blinded_order(packets, slot)
    assert first == blinded_order(tuple(reversed(packets)), slot)
    assert {p.blinded_id for p in first} == {p.blinded_id for p in packets}
    assert first != packets


def test_reviewers_have_distinct_frozen_orders_and_invalid_slots_rejected():
    packets = tuple(SimpleNamespace(blinded_id="opaque" + str(i)) for i in range(100))
    assert blinded_order(packets, "A") != blinded_order(packets, "B")
    with pytest.raises(ValueError):
        blinded_order(packets, "CONSTRUCTION")
