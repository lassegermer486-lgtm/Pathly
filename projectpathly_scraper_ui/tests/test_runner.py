import json

import pytest
import yaml

from conftest import FakeBridge, wait_idle
from scraper_ui.runner import Conflict, Runner, pair_id

PAIR = ("DE-AA|Alpha Uni", "DE-BB|Alpha Universität Campus B")


def run(bridge, **kwargs):
    runner = Runner(bridge)
    runner.start(**kwargs)
    wait_idle(runner)
    return runner


def test_run_ends_in_review_and_reports_kpis(bridge):
    runner = run(bridge)
    assert runner.phase == "review"
    k = runner.kpis()
    assert (k["states_ok"], k["states_total"]) == (3, 3)
    assert k["state_records"] == 4 and k["institutions"] == 4
    assert k["review_open"] == 1 and k["missing_url"] == 1
    assert bridge.scrape_calls == ["DE-AA", "DE-BB", "DE-CC"]


def test_saving_is_blocked_while_duplicates_are_open(bridge):
    runner = run(bridge)
    with pytest.raises(Conflict):
        runner.save()
    with pytest.raises(Conflict):
        runner.registry()
    assert bridge.saved is None


def test_merge_decision_unblocks_saving_and_is_written_to_overrides(bridge):
    runner = run(bridge)
    runner.decide(pair_id(*PAIR), "merge", "ein Campus")

    assert runner.phase == "ready"
    assert runner.kpis()["institutions"] == 3
    overrides = yaml.safe_load(bridge.overrides_path.read_text(encoding="utf-8"))
    assert overrides["merge"] == [list(PAIR)]
    assert "ein Campus" in bridge.overrides_path.read_text(encoding="utf-8")

    saved = runner.save()
    assert runner.phase == "saved" and saved["complete"] is True
    assert len(bridge.saved["masters"]) == 3 and len(bridge.saved["raw"]) == 4


def test_keep_separate_and_changing_ones_mind(bridge):
    runner = run(bridge)
    pid = pair_id(*PAIR)

    runner.decide(pid, "keep_separate")
    assert runner.phase == "ready" and runner.kpis()["institutions"] == 4
    review = runner.records()["review"]
    assert [(p["id"], p["decision"]) for p in review] == [(pid, "keep_separate")]

    runner.decide(pid, "merge")            # change the decision
    overrides = yaml.safe_load(bridge.overrides_path.read_text(encoding="utf-8"))
    assert overrides["merge"] == [list(PAIR)] and not overrides.get("keep_separate")
    assert runner.kpis()["institutions"] == 3

    runner.decide(pid, None)               # take it back
    overrides = yaml.safe_load(bridge.overrides_path.read_text(encoding="utf-8"))
    assert not overrides.get("merge") and not overrides.get("keep_separate")
    assert runner.phase == "review"


def test_failed_state_needs_confirmation_and_can_be_retried(bridge):
    bridge.failing = {"DE-CC"}
    runner = run(bridge)
    runner.decide(pair_id(*PAIR), "merge")
    assert runner.snapshot()["failed_states"] == ["DE-CC"]

    with pytest.raises(Conflict, match="INCOMPLETE:CC"):
        runner.save()
    assert runner.save(confirm_incomplete=True)["complete"] is False
    assert bridge.saved["codes"] == ["DE-AA", "DE-BB"]

    bridge.failing = set()
    runner.retry_state("DE-CC")
    wait_idle(runner)
    assert runner.snapshot()["failed_states"] == []
    assert runner.phase == "ready" and runner.kpis()["state_records"] == 4
    assert runner.save()["complete"] is True


def test_state_without_records_counts_as_failed(bridge, monkeypatch):
    from scraper_ui import registry_import as ri
    monkeypatch.setattr(ri, "load_dsn", lambda: "postgresql://u:p@db.example/postgres")
    monkeypatch.setattr(ri, "import_registry", lambda *a, **k: pytest.fail("must not be called"))

    bridge.data["DE-CC"] = []              # source answered "OK", but with an outage page
    runner = run(bridge)
    runner.decide(pair_id(*PAIR), "merge")

    assert runner.snapshot()["failed_states"] == ["DE-CC"]
    assert "Keine Hochschulen gelesen" in runner.states["DE-CC"]["error"]
    with pytest.raises(Conflict, match="INCOMPLETE:CC"):
        runner.save()
    assert runner.save(confirm_incomplete=True)["complete"] is False
    with pytest.raises(Conflict, match="vollständiger Abruf"):
        runner.push_to_db()                # the database never sees the gap


def test_partial_selection_is_not_a_complete_dataset(bridge):
    runner = run(bridge, states=["DE-AA", "DE-CC"])
    assert runner.phase == "ready"
    assert runner.save()["complete"] is False


def test_loading_the_last_scrape_from_file(bridge):
    bridge.last_scrape_path.parent.mkdir(parents=True)
    rows = bridge.data["DE-AA"] + bridge.data["DE-BB"]
    bridge.last_scrape_path.write_text(json.dumps(rows), encoding="utf-8")

    runner = run(bridge, source="file")
    assert bridge.scrape_calls == []
    assert runner.kpis()["state_records"] == 3
    assert runner.states["DE-CC"]["status"] == "skipped"
    assert runner.phase == "review"


def test_scraper_version_without_dedup_still_works(tmp_path):
    runner = run(FakeBridge(tmp_path, dedup=False))
    assert runner.phase == "ready"
    assert runner.records()["dedup"] is False and runner.records()["review"] == []
    assert runner.save()["complete"] is True


def test_no_second_run_while_one_is_running(bridge):
    runner = Runner(bridge)
    runner.start()
    try:
        if runner.busy():
            with pytest.raises(Conflict):
                runner.start()
    finally:
        wait_idle(runner)


def test_log_is_served_incrementally(bridge):
    runner = run(bridge)
    first = runner.snapshot(0)
    assert any("[FETCH] DE-AA" in line for line in first["log"])
    assert runner.snapshot(first["log_next"])["log"] == []
