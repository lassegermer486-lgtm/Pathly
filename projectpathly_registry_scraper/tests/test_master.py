import copy

from registry.master import identity
from registry.master.candidates import find_candidates
from registry.master.merge import cluster, merge_cluster, unify_record
from registry.master.names import split_name
from registry.master.vocab import (
    map_institution_type, map_ownership, map_recognition,
)


def rec(name, state, url=None, itype="unknown", ownership="unknown",
        recognition="unknown", locations=None):
    return {
        "name": name, "state": state, "official_url": url,
        "institution_type": itype, "ownership": ownership,
        "recognition_status": recognition,
        "locations": locations if locations is not None else [
            {"name": None, "city": None, "state": state, "postal_code": None, "street": None}],
        "source": {"authority": "x", "url": "http://x", "category": "c"},
    }


def build(raws, overrides=None):
    records = [unify_record(r) for r in raws]
    cands = find_candidates(records, overrides)
    return records, cands, [merge_cluster(g) for g in cluster(records, cands)]


def test_vocabulary_is_unified():
    assert map_institution_type("art_music") == map_institution_type("art_music_university")
    assert map_institution_type("university_of_public_administration") == "public_administration"
    assert map_institution_type("theological") == "theological_university"
    assert map_institution_type("nonsense") == "unknown"
    # "private or church" does not say which one -> unknown, never guessed
    assert map_ownership("private_or_church") == map_ownership("private_or_other") == "unknown"
    assert map_ownership("private") == "private"


def test_recognition_is_independent_of_ownership_wording():
    assert map_recognition("state_or_state_recognized", "public") == "public_by_law"
    assert map_recognition("state_or_state_recognized", "private") == "state_recognized"
    assert map_recognition("state_or_state_recognized", "unknown") == "unknown"
    assert map_recognition("state", "unknown") == "unknown"
    assert map_recognition("unknown", "federal") == "public_by_law"
    assert map_recognition("state_recognized", "unknown") == "state_recognized"


def test_split_name():
    assert split_name("Hochschule Fresenius *")["base"] == "Hochschule Fresenius"
    assert split_name("Hochschule Aalen - Technik und Wirtschaft")["base"] == "Hochschule Aalen"
    assert split_name("AKAD – Hochschule Stuttgart")["base"] == "AKAD – Hochschule Stuttgart"
    p = split_name("Hochschule des Bundes - Fachbereich Wetterdienst in Offenbach")
    assert p["is_department"] and p["base"] == "Hochschule des Bundes"


def test_same_host_different_states_merges_and_keeps_locations():
    a = rec("Hochschule Fresenius Heidelberg", "DE-BW", "http://www.hs-fresenius.de",
            locations=[{"name": None, "city": "Heidelberg", "state": "DE-BW",
                        "postal_code": "69115", "street": "A 1"}])
    b = rec("Hochschule Fresenius (Idstein)", "DE-HE", "https://hs-fresenius.de/",
            locations=[{"name": None, "city": "Idstein", "state": "DE-HE",
                        "postal_code": "65510", "street": "B 2"}])
    _, cands, masters = build([a, b])
    assert [c["decision"] for c in cands] == ["auto_merge"]
    assert len(masters) == 1
    m = masters[0]
    assert m["name"] == "Hochschule Fresenius"
    assert {l["city"] for l in m["locations"]} == {"Heidelberg", "Idstein"}
    # A multi-campus institution has no single state; states come from locations.
    assert "home_state" not in m
    assert m["states"] == ["DE-BW", "DE-HE"]
    assert {l["state"] for l in m["locations"]} == {"DE-BW", "DE-HE"}
    assert len(m["merged_from"]) == 2


def test_similar_names_of_different_institutions_are_not_candidates():
    recs = [unify_record(rec("Universität Freiburg", "DE-BW", "http://uni-freiburg.de")),
            unify_record(rec("Universität Augsburg", "DE-BY", "http://uni-augsburg.de")),
            unify_record(rec("Pädagogische Hochschule Freiburg", "DE-BW", "http://ph-freiburg.de"))]
    assert find_candidates(recs) == []


def test_identical_name_with_conflicting_websites_needs_review():
    a = rec("Fachhochschule des Mittelstands", "DE-NW", "https://www.fhm.eu")
    b = rec("Fachhochschule des Mittelstands", "DE-MV", "https://www.other.de")
    _, cands, masters = build([a, b])
    assert cands[0]["decision"] == "review"
    assert len(masters) == 2


def test_overrides():
    a = rec("Alpha Hochschule", "DE-NW", "https://a.de")
    b = rec("Beta Akademie", "DE-BY", "https://b.de")
    key = lambda r: f"{r['state']}|{r['name']}"
    _, _, masters = build([a, b], {"merge": [[key(a), key(b)]]})
    assert len(masters) == 1

    c = rec("Gamma Hochschule", "DE-NW", "https://g.de")
    d = rec("Gamma Hochschule", "DE-BY", "https://g.de")
    _, _, masters = build([c, d], {"keep_separate": [[key(c), key(d)]]})
    assert len(masters) == 2


def test_department_entries_become_locations():
    base = rec("Hochschule des Bundes", "DE-NW", "https://hsbund.de")
    dep = rec("Hochschule des Bundes - Fachbereich Wetterdienst in Offenbach", "DE-HE",
              "https://hsbund.de")
    _, _, masters = build([base, dep])
    assert len(masters) == 1
    assert any(l["name"] == "Fachbereich Wetterdienst in Offenbach" and l["location_type"] == "department"
               for l in masters[0]["locations"])


def test_generic_subject_words_are_no_identity_evidence():
    recs = [unify_record(rec("Evangelische Hochschule Berlin", "DE-BE", "https://eh-berlin.de")),
            unify_record(rec("Evangelische Hochschule Dresden", "DE-SN", "https://ehs-dresden.de",
                             locations=[{"name": None, "city": "Dresden", "state": "DE-SN"}])),
            unify_record(rec("Hochschule für Technik und Wirtschaft Berlin", "DE-BE", "https://htw-berlin.de",
                             locations=[{"name": None, "city": "Berlin", "state": "DE-BE"}])),
            unify_record(rec("Private Hochschule für Wirtschaft und Technik", "DE-NI", "https://phwt.de"))]
    assert find_candidates(recs) == []


def test_brand_name_with_place_suffix_is_only_a_review_candidate():
    a = rec("HSD Hochschule Döpfer", "DE-NW", "https://hs-doepfer.de")
    b = rec("HSD Hochschule Döpfer Potsdam", "DE-BB", None,
            locations=[{"name": None, "city": "Potsdam", "state": "DE-BB"}])
    _, cands, masters = build([a, b])
    assert [c["decision"] for c in cands] == ["review"]
    assert len(masters) == 2


def test_ids_are_stable_across_reruns_and_renames():
    registry = {"version": 1, "entries": {}}
    _, _, first = build([rec("Alpha Hochschule", "DE-NW", "https://alpha.de")])
    identity.assign_ids(first, registry)
    uid = first[0]["university_id"]

    # Same record, re-scraped -> same id.
    _, _, again = build([rec("Alpha Hochschule", "DE-NW", "https://alpha.de")])
    identity.assign_ids(again, copy.deepcopy(registry))
    assert again[0]["university_id"] == uid

    # Renamed by the source but same website -> still the same id.
    _, _, renamed = build([rec("Neue Alpha Universität", "DE-NW", "https://alpha.de")])
    identity.assign_ids(renamed, registry)
    assert renamed[0]["university_id"] == uid

    # A different institution never receives that id.
    _, _, other = build([rec("Beta Hochschule", "DE-BY", "https://beta.de")])
    identity.assign_ids(other, registry)
    assert other[0]["university_id"] != uid


def test_state_portals_are_not_a_shared_website():
    a = rec("Akademie der Polizei Hamburg", "DE-HH", "https://akademie-der-polizei.hamburg.de")
    b = rec("AMD Akademie für Mode & Design", "DE-HH", "https://www.hamburg.de/amd")
    _, cands, masters = build([a, b])
    assert cands == [] and len(masters) == 2
