import pytest

from registry.states import STATES, resolve, short


def test_all_16_states_with_unique_codes():
    assert len(STATES) == 16
    assert len({s.code for s in STATES}) == 16
    assert len({s.short for s in STATES}) == 16


def test_resolve_accepts_official_and_common_codes():
    assert resolve("NRW").code == "DE-NW"
    assert resolve("nw").code == "DE-NW"
    assert resolve("DE-NW").code == "DE-NW"
    assert resolve("bw").code == "DE-BW"
    assert short("DE-NW") == "NRW"
    with pytest.raises(ValueError):
        resolve("XX")
