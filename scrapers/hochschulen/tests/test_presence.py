import json

from registry.master import presence
from registry.master.build import IdRegistry, build
from registry.master.supabase_import import build_payload, render_sql


EVIDENCE = "https://www.example-hochschule.de/news/standorte"


def row(registry_id="PTH-DE-0000000A", listed_by=("DE-HH",), url="https://www.example-hochschule.de", flags=()):
    return {
        "registry_id": registry_id,
        "name": "Example Hochschule",
        "official_url": url,
        "listed_by": list(listed_by),
        "flags": [{"code": c, "severity": "medium"} for c in flags],
    }


def loc(city, state, registry_id="PTH-DE-0000000A"):
    return {"registry_id": registry_id, "city": city, "state": state,
            "source_state": state, "source_url": f"https://source.example/{state}"}


def decision(status, city=None, state=None, registry_id="PTH-DE-0000000A", evidence=EVIDENCE):
    d = {"registry_id": registry_id, "status": status, "evidence_url": evidence}
    if city:
        d["city"] = city
    if state:
        d["state"] = state
    return d


def run(rows, locations, decisions=(), doubts=None):
    report = presence.apply(rows, locations, [], doubts or {}, list(decisions), now="2026-10-02T00:00:00+00:00")
    return report


# ----------------------------------------------------------------------
# derivation
# ----------------------------------------------------------------------

def test_listed_location_with_verified_website_is_active():
    r, l = row(), loc("Hamburg", "DE-HH")
    report = run([r], [l])

    assert l["location_status"] == "active"
    assert l["location_status_basis"] == "state_source_and_verified_website"
    assert l["country"] == "DE"
    assert r["german_physical_presence"] is True
    assert r["presence_status"] == "confirmed"
    assert report["counts"]["confirmed"] == 1


def test_one_closed_campus_and_one_active_campus_is_still_present():
    r = row(listed_by=("DE-HH", "DE-BE"))
    hamburg, berlin = loc("Hamburg", "DE-HH"), loc("Berlin", "DE-BE")
    run([r], [hamburg, berlin], [decision("closed", city="Hamburg")])

    assert hamburg["location_status"] == "closed"
    assert hamburg["location_status_basis"] == "manual_review"
    assert hamburg["location_status_evidence_url"] == EVIDENCE
    assert berlin["location_status"] == "active"
    assert r["german_physical_presence"] is True


def test_all_german_locations_closed_means_no_presence_but_record_stays():
    r = row(listed_by=("DE-HH", "DE-BE"))
    hamburg, berlin = loc("Hamburg", "DE-HH"), loc("Berlin", "DE-BE")
    locations = [hamburg, berlin]
    report = run([r], locations, [decision("closed", city="Hamburg"), decision("moved", city="Berlin")])

    assert r["german_physical_presence"] is False
    assert r["presence_status"] == "not_present"
    assert len(locations) == 2                     # history kept
    assert [e["registry_id"] for e in report["not_present"]] == [r["registry_id"]]


def test_uncertain_location_goes_to_review_not_to_false():
    r, l = row(), loc("Hamburg", "DE-HH")
    report = run([r], [l], [decision("uncertain")])

    assert l["location_status"] == "uncertain"
    assert r["german_physical_presence"] is None
    assert r["presence_status"] == "review"
    assert report["counts"]["review"] == 1


def test_doubt_signals_make_the_automatic_status_uncertain():
    r, l = row(url=None), loc("Hamburg", "DE-HH")
    report = run([r], [l], doubts={r["registry_id"]: ["no_verified_website"]})

    assert l["location_status"] == "uncertain"
    assert "no_verified_website" in l["location_status_basis"]
    assert r["presence_status"] == "review"
    assert report["review"][0]["doubts"][0]["code"] == "no_verified_website"


def test_state_listing_without_city_counts_as_observation():
    r = row(listed_by=("DE-BY",))
    report = run([r], [])

    assert r["german_physical_presence"] is True
    # distinguishable from a confirmed address (Scraper 2 can refine it)
    assert r["presence_basis"] == "state_listing_without_city_and_verified_website"
    assert report["counts"]["confirmed"] == 1


def test_city_location_basis_wins_over_state_listing():
    r = row(listed_by=("DE-HH", "DE-BY"))
    run([r], [loc("Hamburg", "DE-HH")])

    assert r["presence_basis"] == "state_source_and_verified_website"


def test_state_listing_can_be_closed_by_a_state_decision():
    r = row(listed_by=("DE-BY",))
    report = run([r], [], [decision("closed", state="DE-BY")])

    assert r["german_physical_presence"] is False
    assert report["not_present"][0]["observations"][0]["kind"] == "state_listing"


def test_institution_wide_decision_applies_to_every_german_location():
    r = row(listed_by=("DE-HH", "DE-BY"))
    hamburg = loc("Hamburg", "DE-HH")
    run([r], [hamburg], [decision("closed")])

    assert hamburg["location_status"] == "closed"
    assert r["presence_status"] == "not_present"


def test_city_decision_beats_institution_decision():
    r = row(listed_by=("DE-HH", "DE-BE"))
    hamburg, berlin = loc("Hamburg", "DE-HH"), loc("Berlin", "DE-BE")
    run([r], [hamburg, berlin], [decision("closed"), decision("active", city="Berlin")])

    assert hamburg["location_status"] == "closed"
    assert berlin["location_status"] == "active"
    assert r["german_physical_presence"] is True


# ----------------------------------------------------------------------
# provenance of decisions
# ----------------------------------------------------------------------

def test_decision_without_evidence_is_ignored_and_reported():
    r, l = row(), loc("Hamburg", "DE-HH")
    report = run([r], [l], [decision("closed", city="Hamburg", evidence=None)])

    assert l["location_status"] == "active"
    assert "evidence_url" in report["decision_warnings"][0]["problem"]


def test_decision_for_unknown_id_or_location_is_reported():
    r, l = row(), loc("Hamburg", "DE-HH")
    report = run([r], [l], [
        decision("closed", registry_id="PTH-DE-FFFFFFFF"),
        decision("closed", city="München"),
    ])

    problems = [w["problem"] for w in report["decision_warnings"]]
    assert any("unknown registry_id" in p for p in problems)
    assert any("matches no German location" in p for p in problems)
    assert r["german_physical_presence"] is True


# ----------------------------------------------------------------------
# doubt signals
# ----------------------------------------------------------------------

def agent_member(status, accepted):
    return {"website_resolution": {"agent": {
        "answer": {"lifecycle_status": status},
        "validation": {"accepted": accepted},
    }}}


def test_doubts():
    assert presence.doubts(row(), [agent_member(None, False)]) == []
    assert presence.doubts(row(url=None), []) == ["no_verified_website"]
    assert "agent_reports_closed" in presence.doubts(row(), [agent_member("closed", True)])
    assert "agent_reports_merger_unverified" in presence.doubts(row(), [agent_member("merged", False)])
    # predecessor merged into its successor's cluster: normal, no doubt
    assert presence.doubts(row(), [agent_member("merged", True), agent_member(None, False)]) == []
    assert "merged_into_other_institution" in presence.doubts(row(), [agent_member("merged", True)])
    assert presence.doubts(row(flags=["possibly_foreign_institution"]), []) == ["possibly_foreign_institution"]
    # a rename keeps the location
    assert presence.doubts(row(), [agent_member("renamed", True)]) == []


# ----------------------------------------------------------------------
# master build and Supabase
# ----------------------------------------------------------------------

def record(state, name, city, url="https://www.example-hochschule.de"):
    return {
        "name": name, "state": state, "official_url": url,
        "website_resolution": {"official_url": url, "flags": [], "identity": {"evidence": []}},
        "locations": [{"city": city, "state": state, "location_status": "candidate",
                       "location_type": "study_location", "source_url": "https://source.example"}],
    }


def institution(cluster_id, records):
    return {
        "cluster_id": cluster_id,
        "members": [f"{r['state']}|{r['name']}" for r in records],
        "names": [r["name"] for r in records],
        "official_url": records[0]["official_url"],
        "source_states": sorted({r["state"] for r in records}),
        "locations": [{**l, "source_record": f"{r['state']}|{r['name']}"} for r in records for l in r["locations"]],
        "sources": [{"state": r["state"], "url": "https://source.example", "authority": "Land"} for r in records],
    }


def test_master_build_adds_presence_fields_and_keeps_existing_ones(tmp_path):
    records = [record("DE-HH", "Example Hochschule", "Hamburg"), record("DE-BE", "Example Hochschule", "Berlin")]
    institutions = [institution("c1", records)]
    ids = IdRegistry()
    built = build(institutions, records, ids, presence_decisions=[])

    u = built["universities"][0]
    decided = [{"registry_id": u["registry_id"], "city": "Hamburg", "status": "closed", "evidence_url": EVIDENCE}]
    built = build(institutions, records, ids, presence_decisions=decided)
    u = built["universities"][0]

    assert u["registry_id"].startswith("PTH-DE-")
    assert u["country"] == "DE" and u["lifecycle_status"] == "active"
    assert u["german_physical_presence"] is True
    statuses = {l["city"]: l["location_status"] for l in built["locations"]}
    assert statuses == {"Hamburg": "closed", "Berlin": "active"}
    assert {l["source_location_status"] for l in built["locations"]} == {"candidate"}
    assert built["presence"]["counts"]["confirmed"] == 1

    # Supabase: new columns are filled, the import SQL carries them
    master = tmp_path / "master"
    master.mkdir()
    for name, key in [("universities_de_master.json", "universities"), ("university_metadata.json", "metadata"),
                      ("locations.json", "locations"), ("aliases.json", "aliases"), ("sources.json", "sources")]:
        (master / name).write_text(json.dumps(built[key]))
    payload = build_payload(master)
    assert payload["universities"][0]["presence_status"] == "confirmed"
    assert payload["counts"]["presence_confirmed"] == 1
    sql = render_sql(payload, "x", None)
    assert "location_status" in sql and "german_physical_presence" in sql


def test_payload_of_master_files_from_before_v13(tmp_path):
    (tmp_path / "universities_de_master.json").write_text(json.dumps([{
        "registry_id": "PTH-DE-0000000A", "name": "Alt", "official_url": None, "lifecycle_status": "active",
        "listed_by": ["DE-HH"], "flags": [],
    }]))
    for name in ("university_metadata.json", "locations.json", "aliases.json", "sources.json"):
        (tmp_path / name).write_text("[]")

    payload = build_payload(tmp_path)
    assert payload["universities"][0]["presence_status"] == "review"
    assert payload["universities"][0]["german_physical_presence"] is None


def test_review_markdown_has_ready_made_entries():
    r = row(url=None)
    report = run([r], [loc("Hamburg", "DE-HH")], doubts={r["registry_id"]: ["no_verified_website"]})
    text = presence.review_markdown(report)

    assert "registry_id: PTH-DE-0000000A" in text
    assert "city: Hamburg" in text
    assert "evidence_url:" in text
