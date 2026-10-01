import pytest

from registry.master.build import (
    REGISTRY_ID_RE,
    IdRegistry,
    choose_name,
    clean_name,
    validate,
)
from registry.master.supabase_import import DOLLAR_TAG, render_sql


CITIES = frozenset({"hamburg", "idstein", "hagen", "gera"})


# ----------------------------------------------------------------------
# Step 9: canonical names
# ----------------------------------------------------------------------

@pytest.mark.parametrize("source, expected", [
    ("Medizinische Hochschule Brandenburg - Außenansicht", "Medizinische Hochschule Brandenburg"),
    ("HSD Hochschule Döpfer GmbH", "HSD Hochschule Döpfer"),
    ("Berliner Hochschule für Technik (BHT)", "Berliner Hochschule für Technik"),
    ("BTK Hochschule für Gestaltung, Campus Hamburg", "BTK Hochschule für Gestaltung"),
    ("Hochschule Fresenius (Idstein)", "Hochschule Fresenius"),
    ("Hochschule Fresenius *", "Hochschule Fresenius"),
    ("NORDAKADEMIE Hochschule der Wirtschaft | Graduate School", "NORDAKADEMIE Hochschule der Wirtschaft"),
    ("Hochschule des Bundes für öffentliche Verwaltung - Fachbereich Wetterdienst in Offenbach",
     "Hochschule des Bundes für öffentliche Verwaltung"),
    # Part of the official name, must stay:
    ("FernUniversität in Hagen", "FernUniversität in Hagen"),
    ("VICTORIA | Internationale Hochschule", "VICTORIA | Internationale Hochschule"),
    ("Evangelische Hochschule Dresden (FH)", "Evangelische Hochschule Dresden (FH)"),
])
def test_clean_name(source, expected):
    assert clean_name(source, CITIES) == expected


def member(name, agent_name=None, evidence=()):
    resolution = {"identity": {"evidence": list(evidence)}, "flags": []}
    if agent_name:
        resolution["agent"] = {
            "answer": {"canonical_name": agent_name},
            "validation": {"accepted": True},
        }
    return {"name": name, "state": "DE-XX", "website_resolution": resolution}


def test_verified_agent_name_wins():
    name = choose_name([member("Fachhochschule Bielefeld", agent_name="Hochschule Bielefeld")], CITIES, None)
    assert name == {"name": "Hochschule Bielefeld", "origin": "agent_verified", "confirmed": True}


def test_imprint_decides_between_member_names():
    def site_texts(url):
        return (
            ["FOM Die Hochschule für Berufstätige"],
            "Impressum: FOM Hochschule für Oekonomie & Management gemeinnützige GmbH",
        )

    name = choose_name(
        [member("FOM Die Hochschule für Berufstätige"), member("FOM Hochschule für Oekonomie & Management")],
        CITIES,
        "https://www.fom.de",
        site_texts,
    )
    assert name["name"] == "FOM Hochschule für Oekonomie & Management"
    assert name["origin"] == "website"


def test_majority_when_website_says_nothing():
    name = choose_name(
        [member("Hochschule Fresenius Heidelberg"), member("Hochschule Fresenius (Idstein)"), member("Hochschule Fresenius *")],
        CITIES,
        "https://www.hs-fresenius.de",
        lambda url: ([], ""),
    )
    assert name["name"] == "Hochschule Fresenius"
    assert not name["confirmed"]


# ----------------------------------------------------------------------
# Step 10: validation
# ----------------------------------------------------------------------

def test_missing_website_means_review():
    lifecycle, flags = validate(
        {"name": "Thüringer Fachhochschule für öffentliche Verwaltung", "official_url": None},
        [member("Thüringer Fachhochschule für öffentliche Verwaltung Gotha")],
        None,
        {"confirmed": False},
    )
    assert lifecycle == "review"
    assert {"code": "missing_website", "severity": "high", "detail": None} in flags


def test_agent_verified_site_drops_old_resolver_doubts():
    chosen = member("Fachhochschule Bielefeld")
    chosen["website_resolution"].update(
        method="agent_verified",
        flags=["identity_unconfirmed", "possible_rename_or_merger", "renamed_per_agent"],
    )
    lifecycle, flags = validate(
        {"name": "Hochschule Bielefeld", "official_url": "https://www.hsbi.de"},
        [chosen],
        chosen,
        {"confirmed": True},
    )
    assert lifecycle == "active"
    assert flags == []


def test_validation_questions_become_flags():
    _, flags = validate(
        {"name": "ISBA Internationale Studien- und Berufsakademie", "official_url": "https://www.isba.py"},
        [member("ISBA")],
        None,
        {"confirmed": True},
    )
    codes = {f["code"] for f in flags}
    assert codes == {"possibly_not_hochschule", "possibly_foreign_institution"}


# ----------------------------------------------------------------------
# Step 11: stable IDs
# ----------------------------------------------------------------------

def inst(cluster_id, members, url=None):
    return {"cluster_id": cluster_id, "members": members, "name": cluster_id, "official_url": url}


def test_ids_are_stable_across_runs():
    registry = IdRegistry()
    first = registry.assign([inst("a", ["DE-BB|HSD Hochschule Döpfer GmbH"])], "2026-10-01")
    registry_id = first["a"]["registry_id"]
    assert REGISTRY_ID_RE.match(registry_id)

    # Next run: a second state lists it too, and the cluster id changed.
    again = IdRegistry(registry.to_dict()).assign(
        [inst("b", ["DE-BB|HSD Hochschule Döpfer GmbH", "DE-NW|HSD Hochschule Döpfer"])],
        "2026-11-01",
    )
    assert again["b"]["registry_id"] == registry_id


def test_renamed_source_record_keeps_id_through_its_website():
    registry = IdRegistry()
    old = registry.assign([inst("a", ["DE-NW|Fachhochschule Bielefeld"], "https://www.hsbi.de")], "2026-10-01")
    new = registry.assign([inst("b", ["DE-NW|Hochschule Bielefeld"], "https://www.hsbi.de")], "2026-11-01")
    assert new["b"]["registry_id"] == old["a"]["registry_id"]


def test_merging_two_institutions_keeps_the_older_id():
    registry = IdRegistry()
    first = registry.assign(
        [inst("cbs", ["DE-NW|CBS International Business School"]), inst("eufh", ["DE-NW|EUFH"])],
        "2026-10-01",
    )
    registry.ids[first["eufh"]["registry_id"]]["created_at"] = "2026-12-01"

    merged = registry.assign(
        [inst("both", ["DE-NW|CBS International Business School", "DE-NW|EUFH"])],
        "2027-01-01",
    )
    assert merged["both"]["registry_id"] == first["cbs"]["registry_id"]
    assert merged["both"]["former_ids"] == [first["eufh"]["registry_id"]]


# ----------------------------------------------------------------------
# Step 13: Supabase SQL
# ----------------------------------------------------------------------

def payload(**overrides):
    base = {
        "universities": [{
            "registry_id": "PTH-DE-0000000A",
            "name": "O'Reilly Hochschule",
            "name_variants": [],
            "institution_type": "unknown",
            "ownership": "unknown",
            "recognition_status": "unknown",
            "lifecycle_status": "unknown",
            "official_url": None,
            "listed_by": ["DE-BE"],
        }],
        "id_aliases": [],
        "locations": [],
        "sources": [],
        "flags": [],
        "counts": {"universities": 1, "locations": 0, "sources": 0, "flags": 0},
    }
    base.update(overrides)
    return base


def test_sql_is_one_transaction_with_quoted_payload():
    sql = render_sql(payload(), "data/master/universities_de_master.json", "abc123")
    assert sql.count("begin;") == 1 and sql.rstrip().endswith("commit;")
    # The payload sits in a dollar-quoted literal, so quotes need no escaping.
    assert f"{DOLLAR_TAG}{{" in sql and "O'Reilly" in sql
    assert "'abc123'" in sql


def test_sql_refuses_payload_containing_the_quote_tag():
    bad = payload()
    bad["universities"][0]["name"] = f"x{DOLLAR_TAG}x"
    with pytest.raises(ValueError):
        render_sql(bad, "x", None)
