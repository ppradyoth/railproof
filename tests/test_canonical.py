import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from railproof.canonical import canonical_json, digest_json
from railproof.exceptions import CanonicalizationError

json_scalars = st.none() | st.booleans() | st.integers() | st.text()
json_values = st.recursive(
    json_scalars,
    lambda children: (
        st.lists(children, max_size=5) | st.dictionaries(st.text(), children, max_size=5)
    ),
    max_leaves=20,
)


@given(json_values)
def test_canonicalization_is_deterministic(value) -> None:
    assert canonical_json(value) == canonical_json(value)
    assert digest_json(value) == digest_json(value)


@given(st.dictionaries(st.text(), json_scalars, max_size=10))
def test_mapping_order_does_not_change_digest(value) -> None:
    reversed_items = dict(reversed(list(value.items())))
    assert digest_json(value) == digest_json(reversed_items)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, {1: "not-string-key"}])
def test_non_canonical_values_are_rejected(value) -> None:
    with pytest.raises(CanonicalizationError):
        canonical_json(value)


def test_cycles_are_rejected() -> None:
    value = []
    value.append(value)

    with pytest.raises(CanonicalizationError, match="cycle"):
        canonical_json(value)


def test_excessive_depth_is_rejected() -> None:
    value: list = []
    current = value
    for _ in range(66):
        child: list = []
        current.append(child)
        current = child

    with pytest.raises(CanonicalizationError, match="maximum depth"):
        canonical_json(value)
