"""
Runs the bridge against the scraper that is checked out next to the UI.
No network: only the offline parts (state list, dedup pipeline) are exercised.
This is the test that tells you early when a new scraper version changed
something the UI relies on.
"""
import os
from pathlib import Path

import pytest

SCRAPER_DIR = Path(os.environ.get(
    "PATHLY_SCRAPER_DIR",
    Path(__file__).resolve().parents[2] / "projectpathly_registry_scraper"))

pytestmark = pytest.mark.skipif(
    not (SCRAPER_DIR / "registry" / "run.py").is_file(), reason="scraper not checked out")


@pytest.fixture(scope="module")
def bridge():
    from scraper_ui.bridge import ScraperBridge
    cwd = os.getcwd()
    try:
        yield ScraperBridge(SCRAPER_DIR)
    finally:
        os.chdir(cwd)


def raw(name, state, url):
    return {"name": name, "state": state, "official_url": url, "institution_type": "unknown",
            "ownership": "unknown", "recognition_status": "unknown",
            "locations": [{"name": None, "city": None, "state": state,
                           "postal_code": None, "street": None}],
            "source": {"authority": "Test", "url": "https://example.org", "category": "c"}}


def test_sixteen_states_and_sources(bridge):
    states = bridge.states()
    assert len(states) == 16 and {"code", "short", "name"} <= set(states[0])
    config = bridge.load_config()
    assert all(s["code"] in config for s in states)


def test_build_produces_what_the_ui_reads(bridge):
    result = bridge.build(
        [raw("Test Hochschule Nord", "DE-HH", "https://test-hochschule.example"),
         raw("Test Hochschule Nord", "DE-SH", "https://test-hochschule.example"),
         raw("Andere Universität", "DE-BY", "https://andere.example")],
        log=lambda line: None)

    for key in ("dedup", "records", "candidates", "masters"):
        assert key in result
    assert all("source_key" in r for r in result["records"])
    for m in result["masters"]:
        assert m["name"] and m["university_id"]
        assert isinstance(m.get("validation_flags"), list)

    if not bridge.capabilities()["dedup"]:
        pytest.skip("this scraper version has no dedup pipeline")
    assert len(result["masters"]) == 2                       # same host, same name -> merged
    merged = next(m for m in result["masters"] if len(m["merged_from"]) == 2)
    assert set(merged["listed_by"]) == {"DE-HH", "DE-SH"}
    summary = bridge.summary(result)
    assert summary["input_records"] == 3 and summary["master_records"] == 2
