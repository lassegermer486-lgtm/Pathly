"""
Runs the bridge against the scraper that is checked out next to the UI.
No network: only the offline parts (state list, dedup, master build, import
script) are exercised, and nothing is written into the scraper folder.
This is the test that tells you early when a new scraper version changed
something the UI relies on.
"""
import json
import os
from pathlib import Path

import pytest

SCRAPER_DIR = Path(os.environ.get(
    "PATHLY_SCRAPER_DIR",
    Path(__file__).resolve().parents[3] / "scrapers" / "hochschulen"))

pytestmark = pytest.mark.skipif(
    not (SCRAPER_DIR / "registry" / "run.py").is_file(), reason="scraper not checked out")

NORD = "https://test-hochschule.example"


@pytest.fixture(scope="module")
def bridge():
    from scraper_ui.bridge import ScraperBridge
    cwd = os.getcwd()
    try:
        yield ScraperBridge(SCRAPER_DIR)
    finally:
        os.chdir(cwd)


@pytest.fixture(autouse=True)
def without_saved_international_candidates(bridge, tmp_path, monkeypatch):
    """The tests use their own records only; the scraper folder may hold
    real international candidates from a production run (v1.3)."""
    monkeypatch.setattr(bridge, "intl_enriched_path", tmp_path / "none.json")


def raw(name, state, url):
    return {"name": name, "state": state, "official_url": url, "institution_type": "university",
            "ownership": "public", "recognition_status": "public",
            "locations": [{"name": None, "city": "Teststadt", "state": state,
                           "postal_code": "12345", "street": None, "location_type": "main"}],
            "source": {"authority": "Test", "url": "https://example.org", "category": "c"}}


def resolved(url):
    """A website check that confirmed the site (as website_resolver writes it)."""
    return {"status": "resolved", "method": "source_verified", "confidence": 0.95,
            "official_url": url, "source_url": url, "http_status": 200,
            "identity": {"evidence": ["name_in_imprint"]}, "flags": [], "candidates": [],
            "checked_at": "2026-10-01T00:00:00+00:00"}


RECORDS = [raw("Test Hochschule Nord", "DE-HH", NORD),
           raw("Test Hochschule Nord", "DE-SH", NORD),
           raw("Andere Testuniversität", "DE-BY", "https://andere.example")]


def test_sixteen_states_and_sources(bridge):
    states = bridge.states()
    assert len(states) == 16 and {"code", "short", "name"} <= set(states[0])
    config = bridge.load_config()
    assert all(s["code"] in config for s in states)
    assert bridge.capabilities()["dedup"], "v1.2 pipeline (registry.master.*) not found"


def test_verified_same_site_is_merged_automatically(bridge):
    websites = {"DE-HH|Test Hochschule Nord": resolved(NORD),
                "DE-SH|Test Hochschule Nord": resolved(NORD)}
    result = bridge.build(RECORDS, log=lambda line: None, websites=websites)

    for key in ("dedup", "records", "candidates", "masters", "websites", "pipeline"):
        assert key in result
    assert all("source_key" in r for r in result["records"])
    for m in result["masters"]:
        assert m["name"] and m["university_id"].startswith("PTH-DE-")
        assert isinstance(m["validation_flags"], list)

    assert len(result["masters"]) == 2
    merged = next(m for m in result["masters"] if len(m["merged_from"]) == 2)
    assert set(merged["listed_by"]) == {"DE-HH", "DE-SH"}
    assert merged["institution_type"] == "university"
    assert merged["locations"] and merged["sources"]

    summary = bridge.summary(result)
    assert summary["input_records"] == 3 and summary["master_records"] == 2
    assert summary["auto_merge_pairs"] == 1 and summary["review_pairs"] == 0


def test_same_name_without_website_check_needs_a_decision(bridge):
    result = bridge.build(RECORDS, log=lambda line: None)
    review = [c for c in result["candidates"] if c["decision"] == "review"]
    assert [(c["a"], c["b"]) for c in review] == [("DE-HH|Test Hochschule Nord", "DE-SH|Test Hochschule Nord")]
    assert review[0]["reasons"] and len(result["masters"]) == 3


def test_build_writes_nothing(bridge):
    before = {p: p.stat().st_mtime for p in (SCRAPER_DIR / "data").rglob("*") if p.is_file()}
    bridge.build(RECORDS, log=lambda line: None)
    after = {p: p.stat().st_mtime for p in (SCRAPER_DIR / "data").rglob("*") if p.is_file()}
    assert before == after


def test_import_script_from_the_saved_master_files(bridge):
    if not bridge.registry_path.is_file():
        pytest.skip("no saved master registry in the scraper folder")
    payload, sql = bridge.import_script()
    assert payload["universities"] and payload["counts"]["universities"] == len(payload["universities"])
    assert sql.lstrip().startswith("--") and "begin;" in sql and sql.rstrip().endswith("commit;")


def test_dedup_cache_returns_the_original_values(bridge):
    dedup, website = bridge._pipeline.dedup, bridge._pipeline.website
    for name in ("HSD Hochschule Döpfer GmbH", "SRH University of Applied Sciences Heidelberg in Gera",
                 "Berliner Hochschule für Technik (BHT)"):
        assert dedup.fold(name) == dedup.fold.__wrapped__(name)
        assert dedup.name_key(name) == dedup.name_key.__wrapped__(name)
        assert list(dedup.explicit_acronyms(name)) == website.explicit_acronyms(name)


def test_international_candidates_are_kept_but_not_written_as_german(bridge, tmp_path, monkeypatch):
    """v1.3: candidates from registry.international stay in the register when
    the UI rebuilds it; the German enriched file stays German."""
    candidate = {**raw("Universidad Abierta Ejemplo", "INTL-ETER", "https://www.abierta.example"),
                 "country": "ES", "website_resolution": resolved("https://www.abierta.example")}
    candidate["locations"][0].update(state=None, country="ES", city="Madrid", postal_code=None)
    intl_file = tmp_path / "universities_intl_urls.json"
    intl_file.write_text(json.dumps([candidate]), encoding="utf-8")
    monkeypatch.setattr(bridge, "intl_enriched_path", intl_file)

    result = bridge.build(RECORDS, log=lambda line: None)
    master = next(m for m in result["masters"] if m["name"] == "Universidad Abierta Ejemplo")
    assert master["country"] == "ES" and master["listed_by"] == ["INTL-ETER"]

    written = {}
    monkeypatch.setattr(bridge, "_write", lambda path, data: written.__setitem__(path, data))
    bridge.save(result, RECORDS, complete=True, scraped_codes=[])

    german = written[bridge.enriched_path]
    assert len(german) == len(RECORDS)
    assert all(r["state"].startswith("DE-") for r in german)
    assert any(r["registry_id"] == master["university_id"] for r in written[bridge.registry_path])
