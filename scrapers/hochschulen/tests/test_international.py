"""v1.3 Phase C: international online discovery (offline, small fixture files)."""

import csv
import io
import json
import zipfile

import pytest

from registry import http_client, reliability
from registry.international import base, eter, ipeds
from registry.international import run as intl_run
from registry.master import online_de, presence
from registry.master.build import IdRegistry, build
from registry.master.dedup import deduplicate, load_inputs
from registry.master.supabase_import import build_payload, render_sql


# ----------------------------------------------------------------------
# fixtures: pinned files in a temporary cache
# ----------------------------------------------------------------------

ETER_COLUMNS = [
    "ETER ID", "Reference year", "Country Code", "Institution Name", "English Institution Name",
    "Institutional website", "Name of the city", "Postcode", "Legal status",
    "Institution Category standardized", "ROR ID", "WHED ID", "Distance education institution",
]

ETER_ROWS = [
    # id, year, country, national, english, website, city, distance
    ("ES0076", "2019", "ES", "Universitat Oberta de Catalunya", "Open University of Catalonia", "http://www.uoc.edu", "Barcelona", "2"),
    ("ES0076", "2021", "ES", "Universitat Oberta de Catalunya", "Open University of Catalonia", "http://www.uoc.edu", "Barcelona", "2"),
    ("DE0076", "2021", "DE", "FernUniversität in Hagen", "University of Hagen", "http://www.fernuni-hagen.de", "Hagen", "2"),
    ("AL0001", "2016", "AL", "Universiteti i Tiranës", "University of Tirana", "http://www.unitir.edu.al", "Tirana", "2"),
    ("CY0003", "2020", "CY", "Τεχνολογικό Πανεπιστήμιο Κύπρου", "Cyprus University of Technology", "http://www.cut.ac.cy", "Limassol", "2"),
    ("CY0003", "2021", "CY", "Τεχνολογικό Πανεπιστήμιο Κύπρου", "Cyprus University of Technology", "http://www.cut.ac.cy", "Limassol", "m"),
    ("XX0001", "2019", "PT", "Antiga Aberta", "Former Open", "http://old.example.pt", "Lisboa", "2"),
    ("XX0001", "2021", "PT", "Antiga Aberta", "Former Open", "http://old.example.pt", "Lisboa", "0"),
    ("UK0088", "2021", "UK", "The Open University", "The Open University", "http://www.open.ac.uk/", "Milton Keynes", "2"),
    ("IT0007", "2021", "IT", "Università Telematica", "Online University", "http://www.unifortunato.eu", "Benevento", "1"),
]


def write_eter(path):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(ETER_COLUMNS)
        for eid, year, country, national, english, web, city, dist in ETER_ROWS:
            writer.writerow([eid, year, country, national, english, web, city, "", "1", "1", "m", "m", dist])


def zip_csv(path, filename, header, rows):
    text = io.StringIO()
    writer = csv.writer(text)
    writer.writerow(header)
    writer.writerows(rows)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(filename, "﻿" + text.getvalue())


# unitid, name, pset4flg, hloffer, distnced, total, exclusive, abroad
IPEDS = [
    ("100", "Online State University", "1", "9", "1", 200, 190, 5),
    ("101", "Half Online College", "1", "7", "1", 200, 100, 0),
    ("102", "Campus University", "1", "9", "2", 300, 300, 0),
    ("103", "Not Title IV University", "2", "7", "1", 300, 300, 0),
    ("104", "Associate Online College", "1", "3", "1", 300, 300, 0),
    ("105", "Tiny Online University", "1", "7", "1", 50, 50, 0),
    ("106", "Governors Online University", "1", "8", "1", 500, 500, 0),
]


def write_ipeds(folder):
    zip_csv(folder / "HD2024.zip", "HD2024.csv",
            ["UNITID", "INSTNM", "ADDR", "CITY", "STABBR", "ZIP", "OPEID", "WEBADDR", "CONTROL",
             "HLOFFER", "DEGGRANT", "CYACTIVE", "PSET4FLG"],
            [(u, n, "1 Main St", "Springfield", "UT", "84101", "0" + u + "00", f"www.u{u}.edu/", "2",
              hl, "1", "1", t4) for u, n, t4, hl, *_ in IPEDS])
    zip_csv(folder / "IC2024.zip", "IC2024.csv", ["UNITID", "DISTNCED"],
            [(u, d) for u, _, _, _, d, *_ in IPEDS])
    zip_csv(folder / "EFFY2024_DIST.zip", "EFFY2024_dist.csv",
            ["UNITID", "EFFYDLEV", "EFYDETOT", "EFYDEEXC"],
            [(u, "1", tot, exc) for u, _, _, _, _, tot, exc, _ in IPEDS]
            + [(u, "2", 1, 1) for u, *_ in IPEDS])           # other levels are ignored
    zip_csv(folder / "EF2023A_DIST.zip", "ef2023a_dist.csv", ["UNITID", "EFDELEV", "EFDEEX4"],
            [(u, "1", ab) for u, *_, ab in IPEDS])


@pytest.fixture
def sources(tmp_path):
    """International config whose pins match the fixture files in tmp_path/cache."""
    eter_dir = tmp_path / "cache" / "INTL-ETER"
    ipeds_dir = tmp_path / "cache" / "INTL-IPEDS"
    eter_dir.mkdir(parents=True)
    ipeds_dir.mkdir(parents=True)
    write_eter(eter_dir / "dump.csv")
    write_ipeds(ipeds_dir)

    def pin(folder, name):
        return {"url": f"https://example.invalid/{name}", "filename": name,
                "sha256": base.sha256_file(folder / name)}

    config = {
        "INTL-ETER": {
            "name": "ETER", "authority": "European Commission – ETER/EHESO", "adapter": "eter",
            "files": {"dump": pin(eter_dir, "dump.csv")},
            "dataset": {"version": "ETER_test", "landing_page": "https://zenodo.org/records/10879501"},
            "filter": {"distance_education_institution": ["2"], "min_reference_year": 2019,
                       "exclude_countries": ["DE"]},
        },
        "INTL-IPEDS": {
            "name": "IPEDS", "authority": "U.S. Department of Education, NCES", "adapter": "ipeds",
            "files": {k: pin(ipeds_dir, f) for k, f in (("hd", "HD2024.zip"), ("ic", "IC2024.zip"),
                      ("effy_dist", "EFFY2024_DIST.zip"), ("ef_dist", "EF2023A_DIST.zip"))},
            "dataset": {"version": "IPEDS_test", "landing_page": "https://nces.ed.gov/ipeds/"},
            "filter": {"cyactive": "1", "pset4flg": "1", "deggrant": "1", "min_hloffer": 5,
                       "distnced": "1", "min_exclusive_distance_share": 0.9, "min_enrollment": 100},
        },
    }
    return config, tmp_path / "cache"


@pytest.fixture
def no_network(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("network access in a test")
    monkeypatch.setattr(http_client, "get", fail)


# ----------------------------------------------------------------------
# pinned files
# ----------------------------------------------------------------------

def test_cached_file_with_matching_checksum_is_used_without_network(sources, no_network):
    config, cache = sources
    path, obtained = base.pinned_file("INTL-ETER", config["INTL-ETER"]["files"]["dump"], cache)
    assert obtained == "cache" and path.exists()


def test_changed_publisher_file_fails_and_is_not_used(sources, monkeypatch):
    config, cache = sources
    spec = dict(config["INTL-ETER"]["files"]["dump"])
    (cache / "INTL-ETER" / spec["filename"]).write_text("changed")

    class Response:
        content = b"a different file"
        def raise_for_status(self):
            pass

    monkeypatch.setattr(http_client, "get", lambda *a, **k: Response())

    with pytest.raises(base.SnapshotError):
        base.pinned_file("INTL-ETER", spec, cache)
    assert not (cache / "INTL-ETER" / (spec["filename"] + ".part")).exists()


# ----------------------------------------------------------------------
# ETER
# ----------------------------------------------------------------------

def test_eter_filter(sources, no_network):
    config, cache = sources
    records, report = eter.discover("INTL-ETER", config["INTL-ETER"], cache_root=cache)

    by_id = {r["source"]["record_id"]: r for r in records}
    # DE excluded, 2016 too old, latest answer 0 / value 1 not selected,
    # "m" in the latest year falls back to the latest answered year (CY 2020).
    assert sorted(by_id) == ["CY0003", "ES0076", "UK0088"]
    assert report["excluded_country"] == 1 and report["too_old"] == 1

    uoc = by_id["ES0076"]
    assert uoc["name"] == "Open University of Catalonia"
    assert uoc["discovery"]["name_national"] == "Universitat Oberta de Catalunya"
    assert uoc["country"] == "ES"
    assert uoc["state"] == "INTL-ETER"                       # source namespace, not a state
    assert uoc["official_url"] == "http://www.uoc.edu"
    assert uoc["discovery"]["signals"]["distance_education_institution"] == 2
    assert uoc["source"]["dataset_version"] == "ETER_test"
    assert uoc["locations"][0]["country"] == "ES"
    assert uoc["locations"][0]["state"] is None
    assert by_id["UK0088"]["country"] == "GB"                # ETER "UK" -> ISO
    assert by_id["CY0003"]["source"]["reference_year"] == "2020"


# ----------------------------------------------------------------------
# IPEDS
# ----------------------------------------------------------------------

def test_ipeds_filter_needs_both_online_signals(sources, no_network):
    config, cache = sources
    records, report = ipeds.discover("INTL-IPEDS", config["INTL-IPEDS"], cache_root=cache)

    names = [r["name"] for r in records]
    # 101 share too low, 102 not all programmes online, 103 not Title IV,
    # 104 below bachelor, 105 too small
    assert sorted(names) == ["Governors Online University", "Online State University"]
    # students abroad only rank, they never exclude (WGU-like 106 has 0)
    assert names[0] == "Online State University"

    osu = records[0]
    assert osu["country"] == "US"
    assert osu["official_url"] == "https://www.u100.edu/"
    assert osu["discovery"]["external_ids"] == {"ipeds_unitid": "100", "opeid": "010000"}
    assert osu["discovery"]["signals"]["exclusive_distance_share_12m"] == 0.95
    assert osu["discovery"]["signals"]["students_outside_us_fall"] == 5
    assert osu["discovery"]["recognition"]["accreditation_source"] == "DAPIP"
    assert osu["discovery"]["recognition"]["accreditation_status"] == "not_checked"
    assert report["selected"] == 2


# ----------------------------------------------------------------------
# run: output, reliability
# ----------------------------------------------------------------------

def test_run_writes_separate_output_and_status(sources, no_network, tmp_path, monkeypatch):
    config, cache = sources
    monkeypatch.chdir(tmp_path)

    status = intl_run.run(config, ["INTL-ETER", "INTL-IPEDS"], cache_root=cache)

    records = json.loads((tmp_path / "data/normalized/universities_intl.json").read_text())
    assert len(records) == 5
    assert not (tmp_path / "data/normalized/universities_de.json").exists()
    assert status["build_status"] == "complete"
    report = json.loads((tmp_path / "data/reports/international_online_discovery.json").read_text())
    assert {c["online_de_status"] for c in report["candidates"]} == {"review"}
    assert reliability.load_state_counts()["INTL-IPEDS"] == 2


def test_failed_source_blocks_publishing(sources, tmp_path, monkeypatch):
    config, cache = sources
    monkeypatch.chdir(tmp_path)
    (cache / "INTL-IPEDS" / "HD2024.zip").write_bytes(b"broken")

    def offline(*a, **k):
        raise http_client.requests.ConnectionError("offline")
    monkeypatch.setattr(http_client, "get", offline)

    status = intl_run.run(config, ["INTL-ETER", "INTL-IPEDS"], cache_root=cache)

    assert status["build_status"] == "degraded"
    assert status["failed_states"] == ["INTL-IPEDS"]
    assert reliability.production_gate("supabase import") is False


# ----------------------------------------------------------------------
# online_de and market_access
# ----------------------------------------------------------------------

def mrow(registry_id="PTH-DE-0000000A", listed_by=("INTL-ETER",), presence_value=None, country="ES"):
    return {"registry_id": registry_id, "name": "Example", "country": country,
            "official_url": "https://www.example.es", "listed_by": list(listed_by),
            "german_physical_presence": presence_value}


EVIDENCE = {"degree_evidence_url": "https://www.example.es/online/ba",
            "eligibility_evidence_url": "https://www.example.es/admissions/international"}


def test_candidate_starts_in_review_without_market_access():
    r = mrow()
    online_de.apply([r])
    assert r["online_de_status"] == "review"
    assert r["online_de_basis"] == "discovery_candidate: INTL-ETER"
    assert r["market_access"] == []


def test_german_institution_is_not_assessed_and_physical():
    r = mrow(listed_by=("DE-NW",), presence_value=True, country="DE")
    online_de.apply([r])
    assert r["online_de_status"] == "not_assessed"
    assert r["market_access"] == ["physical_de"]


def test_confirmed_needs_both_evidence_urls():
    r = mrow()
    report = online_de.apply([r], [{"registry_id": r["registry_id"], "status": "confirmed",
                                    "degree_evidence_url": EVIDENCE["degree_evidence_url"]}])
    assert r["online_de_status"] == "review"
    assert "eligibility_evidence_url" in report["decision_warnings"][0]["problem"]

    online_de.apply([r], [{"registry_id": r["registry_id"], "status": "confirmed", **EVIDENCE}])
    assert r["online_de_status"] == "confirmed"
    assert r["online_de_basis"] == "manual_review"
    assert r["online_de_evidence"] == EVIDENCE
    assert r["market_access"] == ["online_de"]


def test_not_available_needs_the_restricting_page():
    r = mrow()
    online_de.apply([r], [{"registry_id": r["registry_id"], "status": "not_available"}])
    assert r["online_de_status"] == "review"

    online_de.apply([r], [{"registry_id": r["registry_id"], "status": "not_available",
                           "eligibility_evidence_url": "https://www.example.es/us-residents-only"}])
    assert r["online_de_status"] == "not_available"
    assert r["market_access"] == []


def test_both_access_modes():
    r = mrow(listed_by=("DE-HH", "INTL-ETER"), presence_value=True)
    online_de.apply([r], [{"registry_id": r["registry_id"], "status": "confirmed", **EVIDENCE}])
    assert r["market_access"] == ["physical_de", "online_de"]


# ----------------------------------------------------------------------
# presence of international candidates
# ----------------------------------------------------------------------

def test_international_candidate_presence_is_unknown_not_false():
    r = {**mrow(), "flags": []}
    seat = {"registry_id": r["registry_id"], "city": "Barcelona", "state": None, "country": "ES",
            "source_state": "INTL-ETER", "source_url": "https://zenodo.org"}
    report = presence.apply([r], [seat], [], {}, [], now="2026-10-02T00:00:00+00:00")

    assert r["german_physical_presence"] is None
    assert r["presence_status"] == "review"
    assert r["presence_basis"] == "no_german_source_listing"
    assert seat["location_status_basis"] == "outside_germany_not_validated"
    # not mixed into the German review list (nothing there to decide)
    assert report["review"] == [] and report["counts"]["no_german_source_listing"] == 1
    assert report["location_status"]["uncertain"] == 0


def test_international_listing_does_not_count_as_german_observation():
    r = {**mrow(listed_by=("DE-HH", "INTL-ETER")), "flags": []}
    presence.apply([r], [], [], {}, [], now="2026-10-02T00:00:00+00:00")
    assert r["german_physical_presence"] is True
    assert r["presence_basis"] == "state_listing_without_city_and_verified_website"


# ----------------------------------------------------------------------
# dedup and master build
# ----------------------------------------------------------------------

def resolved(record, url):
    return {**record, "official_url": url,
            "website_resolution": {"status": "resolved", "official_url": url, "flags": [],
                                   "identity": {"evidence": ["name_in_title"]}}}


def german_record():
    return resolved({
        "name": "Example Open University", "country": "DE", "state": "DE-HH",
        "institution_type": "university", "ownership": "private", "recognition_status": "state_recognized",
        "locations": [{"city": "Hamburg", "state": "DE-HH", "location_type": "study_location",
                       "location_status": "candidate", "source_url": "https://www.hamburg.de"}],
        "source": {"authority": "Hamburg", "url": "https://www.hamburg.de"},
    }, "https://www.example-open.es")


def intl_record(name="Example Open University", url="https://www.example-open.es", rid="ES9999"):
    record = base.record(source="INTL-ETER", config={"authority": "European Commission – ETER/EHESO",
                         "dataset": {"version": "ETER_test", "landing_page": "https://zenodo.org"}},
                         record_id=rid, name=name, country="ES", official_url=url, city="Madrid",
                         external_ids={"eter": rid}, signals={"distance_education_institution": 2})
    return resolved(record, url)


def test_physical_and_online_observation_become_one_institution():
    records = [german_record(), intl_record()]
    institutions, _ = deduplicate(records, {"merge": [], "keep_separate": []})
    assert len(institutions) == 1

    built = build(institutions, records, IdRegistry(), presence_decisions=[], online_de_decisions=[])
    row = built["universities"][0]
    assert row["listed_by"] == ["DE-HH", "INTL-ETER"]
    assert row["country"] == "ES"                              # home country (§C12)
    assert row["german_physical_presence"] is True             # Hamburg listing
    assert row["online_de_status"] == "review"
    assert row["market_access"] == ["physical_de"]
    assert row["external_ids"] == {"eter": "ES9999"}
    assert {s["record_id"] for s in built["sources"]} == {None, "ES9999"}


def build_international_only():
    records = [intl_record(name="Universidad Abierta Ejemplo", url="https://www.abierta.es")]
    institutions, _ = deduplicate(records, {"merge": [], "keep_separate": []})
    return build(institutions, records, IdRegistry(), presence_decisions=[], online_de_decisions=[])


def test_international_only_candidate_in_master():
    built = build_international_only()
    row = built["universities"][0]

    assert row["registry_id"].startswith("PTH-DE-")              # existing ID strategy
    assert row["country"] == "ES"
    assert row["german_physical_presence"] is None
    assert row["market_access"] == []
    assert row["discovery"][0]["signals"]["distance_education_institution"] == 2
    assert "possibly_foreign_institution" not in {f["code"] for f in row["flags"]}
    assert built["locations"][0]["country"] == "ES"
    assert built["locations"][0]["state"] is None


def test_supabase_payload_and_sql(tmp_path):
    # home country and the new columns travel with the import
    built = build_international_only()
    for name, key in [("universities_de_master.json", "universities"), ("university_metadata.json", "metadata"),
                      ("locations.json", "locations"), ("aliases.json", "aliases"), ("sources.json", "sources")]:
        (tmp_path / name).write_text(json.dumps(built[key]))
    payload = build_payload(tmp_path)

    u = payload["universities"][0]
    assert u["country"] == "ES" and u["market_access"] == [] and u["online_de_status"] == "review"
    assert payload["sources"][0]["dataset_version"] == "ETER_test"
    assert payload["counts"]["international"] == 1
    sql = render_sql(payload, "x", None)
    assert "coalesce(r.country, 'DE')" in sql and "market_access = '{}'" in sql


def test_german_rows_keep_their_values():
    records = [german_record()]
    institutions, _ = deduplicate(records, {"merge": [], "keep_separate": []})
    row = build(institutions, records, IdRegistry(), presence_decisions=[], online_de_decisions=[])["universities"][0]
    assert row["country"] == "DE"
    assert row["external_ids"] == {} and row["discovery"] == []
    assert row["online_de_status"] == "not_assessed"


def test_dedup_reads_several_inputs_and_skips_missing_optional(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data/enriched").mkdir(parents=True)
    (tmp_path / "data/enriched/universities_de_urls.json").write_text(json.dumps([german_record()]))

    assert len(load_inputs(["data/enriched/universities_de_urls.json",
                            "data/enriched/universities_intl_urls.json"])) == 1

    (tmp_path / "data/enriched/universities_intl_urls.json").write_text(json.dumps([intl_record()]))
    assert len(load_inputs(["data/enriched/universities_de_urls.json",
                            "data/enriched/universities_intl_urls.json"])) == 2
