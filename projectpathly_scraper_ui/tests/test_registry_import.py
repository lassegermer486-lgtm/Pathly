import pytest

from conftest import wait_idle
from scraper_ui import registry_import as ri
from scraper_ui.runner import Conflict, Runner, pair_id

PAIR = ("DE-AA|Alpha Uni", "DE-BB|Alpha Universität Campus B")


def university(rid="PTH-DE-0000000A", **over):
    """A row as registry.master.supabase_import.build_payload writes it."""
    base = {"registry_id": rid, "name": "Test Hochschule", "name_variants": ["TH"],
            "institution_type": "university", "ownership": "public",
            "recognition_status": "public_by_law", "lifecycle_status": "active",
            "official_url": "https://th.example", "listed_by": ["DE-BB", "DE-NW"]}
    return {**base, **over}


def in_db(row, is_listed=True):
    """The same row as it comes back from public.universities."""
    return {"is_listed": is_listed, **{k: v for k, v in row.items() if k != "registry_id"}}


# ------------------------------------------------------------------- counts

def test_counts_new_changed_unchanged_and_unlisted():
    same, renamed = university("PTH-DE-0000000A"), university("PTH-DE-0000000B")
    before = {
        "PTH-DE-0000000A": in_db(same),
        "PTH-DE-0000000B": in_db(renamed),
        "PTH-DE-0000000C": in_db(university("PTH-DE-0000000C")),          # gone from the registry
        "PTH-DE-0000000D": in_db(university("PTH-DE-0000000D"), False),   # already unlisted
    }
    rows = [same, {**renamed, "name": "Neue Hochschule"}, university("PTH-DE-0000000E")]
    assert ri.count_changes(before, rows) == {
        "universities": 3, "universities_new": 1,
        "universities_changed": 1, "universities_unlisted": 1}


def test_a_relisted_university_counts_as_changed():
    row = university()
    assert ri.count_changes({row["registry_id"]: in_db(row, False)}, [row])["universities_changed"] == 1


def test_database_text_with_spaces_is_not_a_change():
    row = university()
    assert ri.count_changes({row["registry_id"]: in_db({**row, "name": " Test Hochschule "})},
                            [row])["universities_changed"] == 0


def test_empty_registry_is_refused_before_connecting(monkeypatch):
    monkeypatch.setattr(ri, "_connect", lambda dsn: pytest.fail("must not connect"))
    with pytest.raises(ri.ImportProblem, match="leer"):
        ri.import_registry("postgresql://u:p@db.example/postgres", {"universities": []}, "begin; commit;")


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

    def fake_import(dsn, payload, sql, source_file=None):
        n = len(payload["universities"])
        calls.append({"dsn": dsn, "n": n, "sql": sql.startswith("begin;")})
        return {"universities": n, "universities_new": n,
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
    assert calls == [{"dsn": "postgresql://u:p@db.example/postgres", "n": 3, "sql": True}]
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
