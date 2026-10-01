from registry.master.dedup import deduplicate


def rec(state, name, url=None, city=None, status="resolved", agent_name=None):
    resolution = {"status": status, "flags": []}

    if agent_name:
        resolution["agent"] = {
            "answer": {"canonical_name": agent_name, "lifecycle_status": "merged"},
            "validation": {"accepted": True},
        }

    return {
        "name": name,
        "state": state,
        "official_url": url,
        "locations": [{"city": city, "name": None, "postal_code": None, "street": None}],
        "source": {"authority": f"Land {state}", "url": f"https://{state}.example"},
        "website_resolution": resolution,
    }


NO_OVERRIDES = {"merge": [], "keep_separate": []}


def run(records, overrides=NO_OVERRIDES):
    institutions, report = deduplicate(records, overrides)
    groups = sorted(sorted(i["members"]) for i in institutions)
    return institutions, report, groups


def test_spec_example_doepfer_is_merged_without_losing_anything():
    institutions, report, groups = run([
        rec("DE-BB", "HSD Hochschule Döpfer GmbH", "https://www.hs-doepfer.de", "Potsdam"),
        rec("DE-NW", "HSD Hochschule Döpfer", "https://www.hs-doepfer.de/", "Köln"),
    ])

    assert len(institutions) == 1
    merged = institutions[0]
    assert {loc["city"] for loc in merged["locations"]} == {"Potsdam", "Köln"}
    assert len(merged["sources"]) == 2
    assert merged["names"] == ["HSD Hochschule Döpfer GmbH", "HSD Hochschule Döpfer"]
    assert merged["source_states"] == ["DE-BB", "DE-NW"]


def test_spec_example_evangelische_hochschulen_stay_apart():
    _, report, groups = run([
        rec("DE-BE", "Evangelische Hochschule Berlin", "https://www.eh-berlin.de", "Berlin"),
        rec("DE-SN", "Evangelische Hochschule Dresden (FH)", "https://www.ehs-dresden.de", "Dresden"),
    ])

    assert len(groups) == 2
    assert report["review"] == []


def test_location_suffix_on_same_site_is_merged():
    _, _, groups = run([
        rec("DE-BW", "SRH University of Applied Sciences Heidelberg", "https://www.srh-university.de", "Heidelberg"),
        rec("DE-TH", "SRH University of Applied Sciences Heidelberg in Gera", "https://www.srh-university.de/de", "Gera"),
    ])
    assert len(groups) == 1


def test_location_suffix_on_other_site_needs_review():
    _, report, groups = run([
        rec("DE-BW", "Beispiel Hochschule Musterstadt", "https://www.beispiel.de", "Heidelberg"),
        rec("DE-TH", "Beispiel Hochschule Musterstadt in Gera", "https://www.beispiel-gera.de", "Gera"),
    ])
    assert len(groups) == 2
    assert report["review"][0]["rule"] == "rule_5_location_suffix"


def test_same_name_different_site_needs_review():
    _, report, _ = run([
        rec("DE-MV", "Fachhochschule des Mittelstands", "https://www.fhm-campus.de", "Schwerin"),
        rec("DE-NW", "Fachhochschule des Mittelstands", "https://www.fh-mittelstand.de", "Bielefeld"),
    ])
    assert report["review"][0]["rule"] == "rule_3_same_name_different_site"


def test_trailing_city_is_not_a_location_suffix():
    # Different institutions with the same pattern of name.
    _, report, groups = run([
        rec("DE-HH", "Hochschule für Musik und Theater Hamburg", "https://www.hfmt-hamburg.de", "Hamburg"),
        rec("DE-BY", "Hochschule für Musik und Theater München", "https://www.hmtm.de", "München"),
    ])
    assert len(groups) == 2
    assert report["review"] == []


def test_same_site_with_unrelated_names_needs_review():
    _, report, groups = run([
        rec("DE-SL", "Fachhochschule für Verwaltung", "https://www.saarland.de/fhsv", "Saarbrücken"),
        rec("DE-SL", "Landesinstitut für Pädagogik", "https://www.saarland.de/lpm", "Saarbrücken"),
    ])
    assert len(groups) == 2
    assert report["review"][0]["rule"] == "same_site_unrelated_names"


def test_verified_agent_name_counts_as_alias():
    _, _, groups = run([
        rec("DE-BB", "University of Europe for Applied Sciences", "https://www.ue-germany.com"),
        rec(
            "DE-HH",
            "BTK Hochschule für Gestaltung, Campus Hamburg",
            "https://www.ue-germany.com/de",
            "Hamburg",
            agent_name="University of Europe for Applied Sciences",
        ),
    ])
    assert len(groups) == 1


def test_shared_acronym_alone_is_not_enough():
    _, report, _ = run([
        rec("DE-BE", "Hochschule für Technik und Wirtschaft Berlin (HTW)", "https://www.htw-berlin.de", "Berlin"),
        rec("DE-SN", "HTW Dresden", "https://www.htw-dresden.de", "Dresden"),
    ])
    assert report["review"] == []


def test_overrides_win():
    a = rec("DE-MV", "Fachhochschule des Mittelstands", "https://www.fhm-campus.de", "Schwerin")
    b = rec("DE-NW", "Fachhochschule des Mittelstands", "https://www.fh-mittelstand.de", "Bielefeld")
    key_a, key_b = "DE-MV|Fachhochschule des Mittelstands", "DE-NW|Fachhochschule des Mittelstands"

    _, report, groups = run([a, b], {"merge": [[key_a, key_b]], "keep_separate": []})
    assert len(groups) == 1
    assert report["review"] == []

    # keep_separate blocks even an automatic merge on the same site.
    c = rec("DE-HH", "HFH Hamburger Fern-Hochschule", "https://www.hfh-fernstudium.de", "Hamburg")
    d = rec("DE-MV", "HFH Hamburger Fern-Hochschule", "https://www.hfh-fernstudium.de", "Schwerin")
    _, report, groups = run(
        [c, d],
        {"merge": [], "keep_separate": [["DE-HH|HFH Hamburger Fern-Hochschule", "DE-MV|HFH Hamburger Fern-Hochschule"]]},
    )
    assert len(groups) == 2

    _, report, _ = run([a], {"merge": [["DE-XX|Unbekannt", key_a]], "keep_separate": []})
    assert report["unknown_override_keys"] == ["DE-XX|Unbekannt"]
