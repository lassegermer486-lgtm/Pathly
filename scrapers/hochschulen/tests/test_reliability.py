import json
import sys

import pytest
import yaml

from registry import reliability, run
from registry.reliability import (
    accept_drift,
    assess_state,
    build_status,
    count_drift,
    load_state_counts,
    production_gate,
    update_state_counts,
)


STATES = run.STATE_ORDER


def ok(state, count):
    return {"state": state, "status": "OK", "universities": count}


def assessed(counts, previous=None, override=None):
    """All 16 states successful with `counts`; `override` replaces entries."""
    previous = previous or {}
    entries = {s: ok(s, counts.get(s, 10)) for s in STATES}
    entries.update(override or {})
    return [assess_state(entries[s], previous.get(s, counts.get(s, 10))) for s in STATES]


# ----------------------------------------------------------------------
# count drift
# ----------------------------------------------------------------------

def test_small_change_is_normal():
    drift = count_drift(68, 65)
    assert drift["count_status"] == "normal"
    assert drift["absolute_delta"] == -3
    assert drift["relative_delta"] == -0.044


def test_large_absolute_change_is_suspicious():
    # 12 % relative, but more than 10 institutions
    assert count_drift(100, 88)["count_status"] == "suspicious"
    assert count_drift(68, 30)["count_status"] == "suspicious"


def test_large_relative_change_in_a_small_state_is_suspicious():
    drift = count_drift(8, 3)
    assert drift["absolute_delta"] == -5
    assert drift["relative_delta"] == -0.625
    assert drift["count_status"] == "suspicious"


def test_growth_counts_as_drift_too():
    assert count_drift(7, 10)["count_status"] == "suspicious"   # +43 %
    assert count_drift(7, 9)["count_status"] == "normal"        # +29 %


def test_thresholds_are_exclusive():
    assert count_drift(100, 90)["count_status"] == "normal"     # exactly 10
    assert count_drift(10, 13)["count_status"] == "normal"      # exactly 30 %


def test_no_baseline():
    assert count_drift(None, 12)["count_status"] == "no_baseline"


# ----------------------------------------------------------------------
# per state
# ----------------------------------------------------------------------

def test_failed_state_keeps_existing_fields_and_adds_status():
    entry = {"state": "DE-NI", "status": "ERROR", "error": "ConnectionError", "request_attempts": 3}
    result = assess_state(entry, 30)

    assert result["status"] == "ERROR"            # unchanged for existing consumers
    assert result["error"] == "ConnectionError"
    assert result["source_status"] == "failed"
    assert result["previous_count"] == 30
    assert result["current_count"] == 0
    assert result["count_status"] == "source_failed"
    assert result["production_safe"] is False


def test_zero_institutions_count_as_failed_source():
    result = assess_state(ok("DE-HE", 0), 39)
    assert result["source_status"] == "failed"
    assert result["failure_reason"] == "empty_result"
    assert result["production_safe"] is False


def test_successful_state():
    result = assess_state(ok("DE-NI", 31), 30)
    assert result["source_status"] == "success"
    assert result["count_status"] == "normal"
    assert result["production_safe"] is True


# ----------------------------------------------------------------------
# build status
# ----------------------------------------------------------------------

def test_all_states_successful_is_complete():
    status = build_status(assessed({}), STATES)
    assert status["build_status"] == "complete"
    assert status["production_safe"] is True
    assert status["states_successful"] == 16


def test_one_failed_state_makes_the_build_degraded():
    failed = {"DE-NI": {"state": "DE-NI", "status": "ERROR", "error": "timeout"}}
    status = build_status(assessed({}, override=failed), STATES)

    assert status["build_status"] == "degraded"
    assert status["production_safe"] is False
    assert status["failed_states"] == ["DE-NI"]
    assert status["states_successful"] == 15


def test_subset_run_is_not_production_safe():
    entries = [assess_state(ok("DE-NW", 68), 68)]
    status = build_status(entries, STATES)

    assert status["build_status"] == "degraded"
    assert len(status["missing_states"]) == 15


def test_count_drift_needs_review():
    entries = assessed({"DE-SL": 3}, previous={"DE-SL": 8})
    status = build_status(entries, STATES)

    assert status["build_status"] == "review"
    assert status["production_safe"] is False
    assert status["count_drift_states"] == ["DE-SL"]


def test_nothing_successful_is_failed():
    entries = [assess_state({"state": s, "status": "ERROR"}, 10) for s in STATES]
    assert build_status(entries, STATES)["build_status"] == "failed"


# ----------------------------------------------------------------------
# baseline
# ----------------------------------------------------------------------

def test_first_run_uses_the_v12_run_report_as_baseline(tmp_path):
    legacy = tmp_path / "registry_run.json"
    legacy.write_text(json.dumps([ok("DE-NW", 68), {"state": "DE-NI", "status": "ERROR"}]))

    counts = load_state_counts(tmp_path / "missing.json", legacy)
    assert counts == {"DE-NW": 68}


def test_baseline_only_moves_for_unremarkable_successful_states(tmp_path):
    path = tmp_path / "state_counts.json"
    previous = {"DE-NW": 68, "DE-SL": 8, "DE-NI": 30}
    entries = [
        assess_state(ok("DE-NW", 66), 68),                                   # normal
        assess_state(ok("DE-SL", 3), 8),                                     # drift
        assess_state({"state": "DE-NI", "status": "ERROR"}, 30),             # failed
    ]

    update_state_counts(entries, path, previous=previous)

    assert load_state_counts(path) == {"DE-NW": 66, "DE-SL": 8, "DE-NI": 30}


def test_accepted_drift_becomes_baseline_and_build_production_safe(tmp_path):
    counts = tmp_path / "state_counts.json"
    status_path = tmp_path / "build_status.json"
    entries = assessed({"DE-SL": 3}, previous={"DE-SL": 8})
    status_path.write_text(json.dumps(build_status(entries, STATES)))
    update_state_counts(entries, counts, previous={"DE-SL": 8})

    new = accept_drift(["DE-SL"], status_path, counts, expected_states=STATES)

    assert new["build_status"] == "complete"
    assert new["production_safe"] is True
    assert new["accepted_drift"] == ["DE-SL"]
    assert load_state_counts(counts)["DE-SL"] == 3


def test_accepting_drift_does_not_repair_a_failed_state(tmp_path):
    status_path = tmp_path / "build_status.json"
    entries = assessed(
        {"DE-SL": 3},
        previous={"DE-SL": 8},
        override={"DE-NI": {"state": "DE-NI", "status": "ERROR"}},
    )
    status_path.write_text(json.dumps(build_status(entries, STATES)))

    new = accept_drift(["all"], status_path, tmp_path / "c.json", expected_states=STATES)

    assert new["build_status"] == "degraded"
    assert new["production_safe"] is False


# ----------------------------------------------------------------------
# publishing gate
# ----------------------------------------------------------------------

@pytest.fixture
def written_build(tmp_path):
    normalized = tmp_path / "universities_de.json"
    normalized.write_text("[]")
    status_path = tmp_path / "build_status.json"

    def write(entries):
        status_path.write_text(json.dumps(build_status(entries, STATES, normalized)))
        return dict(status_path=status_path, normalized_path=normalized)

    return write


def test_gate_blocks_degraded_build(written_build, capsys):
    paths = written_build(assessed({}, override={"DE-NI": {"state": "DE-NI", "status": "ERROR"}}))

    assert production_gate("master build", **paths) is False
    assert "BLOCKED" in capsys.readouterr().out
    assert production_gate("master build", allow_degraded=True, **paths) is True


def test_gate_passes_complete_build(written_build):
    assert production_gate("master build", **written_build(assessed({}))) is True


def test_gate_ignores_status_of_another_discovery_output(written_build):
    paths = written_build(assessed({}, override={"DE-NI": {"state": "DE-NI", "status": "ERROR"}}))
    paths["normalized_path"].write_text('[{"name": "restored"}]')

    assert production_gate("master build", **paths) is True


def test_gate_without_status_file_keeps_v12_behaviour(tmp_path):
    assert production_gate("master build", status_path=tmp_path / "none.json") is True


# ----------------------------------------------------------------------
# registry.run end to end, with fake adapters
# ----------------------------------------------------------------------

class FakeAdapter:
    counts = {}

    def __init__(self, state, cfg):
        self.state = state

    def fetch(self):
        count = self.counts[self.state]
        if count is None:
            raise ConnectionError("source down")
        return [{"name": f"Hochschule {i} {self.state}", "state": self.state} for i in range(count)]


def run_registry(tmp_path, monkeypatch, counts):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "registry").mkdir(exist_ok=True)
    (tmp_path / "registry" / "sources.yaml").write_text(
        yaml.safe_dump({s: {"name": s, "adapter": "fake"} for s in STATES})
    )
    monkeypatch.setattr(run, "ADAPTERS", {"fake": FakeAdapter})
    monkeypatch.setattr(
        run, "normalize_state",
        lambda state, rows: [{**r, "locations": [{"city": "X"}]} for r in rows],
    )
    monkeypatch.setattr(FakeAdapter, "counts", counts)
    monkeypatch.setattr(sys, "argv", ["registry.run"])
    run.main()
    return (
        json.loads((tmp_path / "data/reports/registry_run.json").read_text()),
        json.loads((tmp_path / "data/reports/build_status.json").read_text()),
    )


def test_run_with_one_failed_state_is_marked_degraded(tmp_path, monkeypatch):
    counts = {s: 5 for s in STATES}
    report, status = run_registry(tmp_path, monkeypatch, counts)
    assert status["build_status"] == "complete"
    assert all(e["count_status"] == "no_baseline" for e in report)

    counts["DE-NI"] = None
    report, status = run_registry(tmp_path, monkeypatch, counts)

    ni = next(e for e in report if e["state"] == "DE-NI")
    assert ni["status"] == "ERROR"
    assert ni["source_status"] == "failed"
    assert ni["previous_count"] == 5
    assert status["build_status"] == "degraded"
    assert status["production_safe"] is False

    # The failed state keeps its last good count.
    assert load_state_counts(tmp_path / "data/master/state_counts.json")["DE-NI"] == 5

    # master build / supabase import would now refuse to publish.
    assert production_gate("supabase import") is False


def test_run_reports_count_drift(tmp_path, monkeypatch):
    counts = {s: 8 for s in STATES}
    run_registry(tmp_path, monkeypatch, counts)

    counts["DE-SL"] = 3
    report, status = run_registry(tmp_path, monkeypatch, counts)

    sl = next(e for e in report if e["state"] == "DE-SL")
    assert sl["count_status"] == "suspicious"
    assert sl["relative_delta"] == -0.625
    assert status["build_status"] == "review"
    assert status["count_drift_states"] == ["DE-SL"]
