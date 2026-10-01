import pytest

from conftest import wait_idle
from scraper_ui import registry_import as ri
from scraper_ui.runner import Conflict, Runner, pair_id

PAIR = ("DE-AA|Alpha Uni", "DE-BB|Alpha Universität Campus B")


def master(rid="PTH-DE-0000000A", **over):
    base = {
        "university_id": rid, "name": "Test Hochschule", "name_variants": ["TH"],
        "country": "DE", "institution_type": "university", "ownership": "public",
        "recognition_status": "public_by_law", "lifecycle_status": "unknown",
        "official_url": "https://th.example", "listed_by": ["DE-NW", "DE-BB"],
        "locations": [
            {"name": None, "street": "Weg 1", "postal_code": "01069", "city": "Dresden",
             "state": "DE-SN", "location_type": "main", "source_state": "DE-SN", "source_url": None},
            {"name": "Campus Süd", "street": None, "postal_code": None, "city": "Köln",
             "state": "DE-NW", "location_type": "campus", "source_state": "DE-NW", "source_url": None},
        ],
        "sources": [{"state": "DE-NW", "authority": "Ministerium", "url": "https://m.example",
                     "category": "c", "source_type": "csv", "retrieved_at": None}],
        "validation_flags": [{"code": "website_unreachable", "severity": "high", "detail": 404}],
    }
    return {**base, **over}


# ------------------------------------------------------------- preparing rows

def test_prepare_maps_registry_to_table_rows():
    rows = ri.prepare([master()])
    assert rows["universities"][0]["registry_id"] == "PTH-DE-0000000A"
    assert rows["universities"][0]["listed_by"] == ["DE-BB", "DE-NW"]
    # The table only knows main/branch/unknown.
    assert [l["location_type"] for l in rows["locations"]] == ["main", "branch"]
    assert rows["locations"][0]["postal_code"] == "01069"          # leading zero survives
    assert rows["flags"][0]["detail"] == "404"                     # always text
    assert rows["sources"][0]["retrieved_at"] is None


def test_prepare_reports_everything_the_tables_would_reject():
    bad = master("ROW-00001", institution_type="quatsch")
    bad["locations"][0]["postal_code"] = "1234"
    bad["locations"][1]["state"] = "NRW"
    with pytest.raises(ri.ImportProblem) as exc:
        ri.prepare([bad, master("PTH-DE-0000000B"), master("PTH-DE-0000000B")])
    text = str(exc.value)
    for expected in ("ungültige ID 'ROW-00001'", "unbekannter Typ 'quatsch'", "ungültiger PLZ '1234'",
                     "ungültigem Land 'NRW'", "kommt doppelt vor"):
        assert expected in text


def test_prepare_refuses_an_empty_registry():
    with pytest.raises(ri.ImportProblem):
        ri.prepare([])


def test_same_address_twice_is_one_location():
    m = master()
    m["locations"].append(dict(m["locations"][0], street=" weg 1 "))
    assert len(ri.prepare([m])["locations"]) == 2


def test_aliases_from_id_registry():
    registry = {"entries": {"PTH-DE-0000000A": {"aliases": ["PTH-DE-0000000C", "kaputt"]},
                            "PTH-DE-0000000B": {}}}
    assert ri.aliases_from_id_registry(registry) == [
        {"alias": "PTH-DE-0000000C", "registry_id": "PTH-DE-0000000A"}]
    assert ri.aliases_from_id_registry(None) == []


# -------------------------------------------------------------- configuration

def test_dsn_comes_from_environment_or_env_file(tmp_path, monkeypatch):
    monkeypatch.delenv(ri.DSN_ENV, raising=False)
    monkeypatch.setattr(ri, "UI_DIR", tmp_path)
    assert ri.load_dsn() is None

    (tmp_path / ".env").write_text('# Kommentar\nSUPABASE_DB_URL="postgresql://u:geheim@db.example:5432/postgres"\n')
    assert ri.load_dsn() == "postgresql://u:geheim@db.example:5432/postgres"

    monkeypatch.setenv(ri.DSN_ENV, "postgresql://u:x@other.example/postgres")
    assert ri.load_dsn().endswith("@other.example/postgres")


def test_target_description_never_contains_the_password():
    shown = ri.describe_target("postgresql://postgres.abc:sehr-geheim@pooler.example.com:5432/postgres")
    assert shown == "pooler.example.com / postgres"
    assert ri.describe_target(None) is None


# ------------------------------------------------------- gating in the runner

@pytest.fixture
def saved_runner(bridge, monkeypatch):
    calls = []

    def fake_import(dsn, masters, id_registry=None, source_file=None, repo_dir=None):
        calls.append({"dsn": dsn, "n": len(masters)})
        return {"universities": len(masters), "universities_new": len(masters),
                "universities_changed": 0, "universities_unlisted": 0, "locations": 0}

    monkeypatch.setattr(ri, "load_dsn", lambda: "postgresql://u:p@db.example/postgres")
    monkeypatch.setattr(ri, "import_registry", fake_import)
    runner = Runner(bridge)
    runner.start()
    wait_idle(runner)
    return runner, calls


def test_push_needs_a_saved_state(saved_runner):
    runner, calls = saved_runner
    with pytest.raises(Conflict, match="zuerst speichern"):
        runner.push_to_db()                       # duplicates still open
    runner.decide(pair_id(*PAIR), "merge")
    with pytest.raises(Conflict, match="zuerst speichern"):
        runner.push_to_db()                       # ready, but not saved
    assert calls == []

    runner.save()
    result = runner.push_to_db()
    assert calls == [{"dsn": "postgresql://u:p@db.example/postgres", "n": 3}]
    assert result["counts"]["universities"] == 3
    assert runner.snapshot()["db"]["last"]["target"] == "db.example / postgres"

    runner.decide(pair_id(*PAIR), None)           # data changed -> push info is stale
    assert runner.snapshot()["db"]["last"] is None


def test_push_refuses_incomplete_runs(bridge, monkeypatch):
    monkeypatch.setattr(ri, "load_dsn", lambda: "postgresql://u:p@db.example/postgres")
    monkeypatch.setattr(ri, "import_registry", lambda *a, **k: pytest.fail("must not be called"))
    runner = Runner(bridge)
    runner.start(states=["DE-AA", "DE-CC"])
    wait_idle(runner)
    runner.save()
    with pytest.raises(Conflict, match="vollständiger Abruf"):
        runner.push_to_db()


def test_push_without_configuration_explains_what_to_do(saved_runner, monkeypatch):
    runner, _ = saved_runner
    runner.decide(pair_id(*PAIR), "merge")
    runner.save()
    monkeypatch.setattr(ri, "load_dsn", lambda: None)
    assert runner.snapshot()["db"]["configured"] is False
    with pytest.raises(Conflict, match="SUPABASE_DB_URL"):
        runner.push_to_db()


def test_failed_import_is_reported_and_leaves_runner_usable(saved_runner, monkeypatch):
    runner, _ = saved_runner
    runner.decide(pair_id(*PAIR), "merge")
    runner.save()

    def broken(*args, **kwargs):
        raise ri.ImportProblem("Keine Verbindung zur Datenbank: timeout")

    monkeypatch.setattr(ri, "import_registry", broken)
    with pytest.raises(Conflict, match="Keine Verbindung"):
        runner.push_to_db()
    snap = runner.snapshot()
    assert snap["db"]["pushing"] is False and snap["db"]["last"] is None and snap["busy"] is False
