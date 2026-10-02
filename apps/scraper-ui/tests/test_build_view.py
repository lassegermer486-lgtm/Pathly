"""Registry-Build view: pipeline output -> feed, reports -> overview (no network)."""
import json
import os
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from scraper_ui.app import create_app
from scraper_ui.build_reports import ReportCache, live_steps, overview
from scraper_ui.pipeline_process import LineParser, PipelineProcess

SCRAPER_DIR = Path(os.environ.get(
    "PATHLY_SCRAPER_DIR", Path(__file__).resolve().parents[3] / "scrapers" / "hochschulen"))


# ----------------------------------------------------------------------
# output lines -> feed (three levels)
# ----------------------------------------------------------------------

def parse_all(lines):
    parser = LineParser()
    return [e for e in (parser.parse(line) for line in lines) if e]


def test_pipeline_output_becomes_step_item_result():
    events = parse_all([
        "",
        "==============================================================",
        "[PIPELINE] discovery: -m registry.run",
        "[FETCH] DE-BW — Baden-Württemberg",
        "[BW] Parsed 79 rows",                      # adapter detail: raw log only
        "[OK] DE-BW: 69 universities / 79 locations",
        "STATES:       16/16 successful",
        "BUILD:        COMPLETE (production safe)",
        "[PIPELINE] websites_intl: -m registry.enrichment.website_resolver --in x",
        "[START] 70 of 70 records",
        "[RESOLVED  ] INTL-ETER University of Nicosia                                   source_direct        0.90 https://www.unic.ac.cy",
        "[REVIEW    ] INTL-ETER Ferdinand Porsche Fern FH-Studiengänge                  -                    0.00 http://www.fernfh.at",
        "[CHECKSUM] INTL-ETER ETER.csv: verified (sha256 d14155ddc56b…, cache)",
        "[WARN] SL: ministry overview unavailable",
        "[BLOCKED] pipeline: discovery build is DEGRADED — failed: DE-NI",
        "[PIPELINE] complete: discovery, websites_intl",
    ])
    levels = [(e["level"], e["text"]) for e in events]

    assert levels[0] == ("step", "Deutsche Discovery gestartet")
    assert ("item", "[DE-BW] Quelle wird abgerufen …") in levels
    assert ("result", "[DE-BW] 69 universities / 79 locations") in levels
    assert ("result", "STATES: 16/16 successful") in levels
    assert ("item", "[1/70] University of Nicosia ✓") in levels
    assert ("item", "[2/70] Ferdinand Porsche Fern FH-Studiengänge ?") in levels
    assert any(l == "warn" for l, _ in levels)
    assert any(l == "error" and "BLOCKED" in t for l, t in levels)
    assert levels[-1] == ("step", "Pipeline abgeschlossen")
    assert not any("Parsed 79" in t for _, t in levels)
    # every event knows its pipeline step
    assert {e["step"] for e in events if e["level"] == "item"} == {"discovery", "websites_intl"}


def test_not_production_safe_build_line_is_a_warning():
    (event,) = parse_all(["BUILD:        DEGRADED (NOT production safe)"])
    assert event["level"] == "warn"


# ----------------------------------------------------------------------
# the process
# ----------------------------------------------------------------------

def fake_pipeline(lines, code=0):
    script = "import sys\n" + "".join(f"print({line!r})\n" for line in lines) + f"sys.exit({code})\n"
    return [sys.executable, "-c", script]


def wait(proc, timeout=10):
    end = time.time() + timeout
    while proc.running and time.time() < end:
        time.sleep(0.05)
    assert not proc.running


def test_process_collects_events_and_steps(tmp_path):
    proc = PipelineProcess(tmp_path)
    proc.start(command=fake_pipeline([
        "[PIPELINE] discovery: -m registry.run",
        "[OK] DE-BW: 69 universities / 79 locations",
        "[PIPELINE] international: -m registry.international.run",
        "[OK] INTL-ETER: 25 candidates (cache)",
        "[PIPELINE] complete: discovery, international",
    ]))
    with pytest.raises(RuntimeError):
        proc.start(command=fake_pipeline([]))         # one build at a time
    wait(proc)

    snap = proc.snapshot()
    assert snap["exit_code"] == 0
    assert snap["steps_done"] == ["discovery", "international"]
    assert any(e["text"] == "[INTL-ETER] 25 candidates (cache)" for e in snap["events"])
    assert len(snap["raw"]) == 5
    # incremental polling
    again = proc.snapshot(since=snap["events_next"], raw_since=snap["raw_next"])
    assert again["events"] == [] and again["raw"] == []


def test_blocked_build_is_reported(tmp_path):
    proc = PipelineProcess(tmp_path)
    proc.start(command=fake_pipeline(["[PIPELINE] dedup: -m registry.master.dedup",
                                      "[BLOCKED] pipeline: discovery build is DEGRADED"], code=2))
    wait(proc)
    snap = proc.snapshot()
    assert snap["exit_code"] == 2 and "dedup" not in snap["steps_done"]
    assert "nicht produktionssicher" in snap["events"][-1]["text"]


def test_command_is_the_cli_command(tmp_path):
    proc = PipelineProcess(tmp_path, python="python")
    assert proc.command_for("dedup", "supabase", agent_api=False) == [
        "python", "-m", "registry.pipeline", "--from", "dedup", "--to", "supabase", "--agent-cache-only"]
    with pytest.raises(ValueError):
        proc.command_for("supabase", "dedup", agent_api=False)


def test_live_steps_follow_the_cli_steps():
    process = {"command": ["python", "-m", "registry.pipeline", "--from", "websites", "--to", "master"],
               "running": True, "step": "dedup", "steps_done": ["websites", "websites_intl", "agent", "agent_intl"]}
    live = live_steps(process)
    assert live["websites"] == "done" and live["agent"] == "done"
    assert live["dedup"] == "running"
    assert live["presence"] == live["online_de"] == live["master"] == "waiting"
    assert "german_discovery" not in live and "supabase" not in live


# ----------------------------------------------------------------------
# reports -> overview (the UI computes no status of its own)
# ----------------------------------------------------------------------

def write(base, rel, data):
    path = base / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def state(code, count, status="success", **extra):
    return {"state": code, "source_status": status, "current_count": count, "previous_count": count,
            "count_status": "normal", **extra}


@pytest.fixture
def reports(tmp_path):
    t = "2026-10-02T10:00:00+00:00"
    german = [state(f"DE-{i:02d}", 10) for i in range(15)] + [
        state("DE-SL", 3, count_status="suspicious", previous_count=8, absolute_delta=-5, relative_delta=-0.625)]
    write(tmp_path, "data/reports/registry_run.json",
          [{"state": s["state"], "status": "OK", "universities": s["current_count"], "locations": 1} for s in german])
    write(tmp_path, "data/reports/build_status.json", {
        "generated_at": t, "build_status": "review", "production_safe": False, "states_expected": 16, "states": german})
    write(tmp_path, "data/reports/international_build_status.json", {
        "generated_at": t, "build_status": "complete", "production_safe": True, "states_expected": 2,
        "states": [state("INTL-ETER", 25), state("INTL-IPEDS", 45)]})
    write(tmp_path, "data/reports/international_online_discovery.json", {"generated_at": t, "candidates": [{}] * 70})
    write(tmp_path, "data/reports/url_resolution_intl.json", {
        "generated_at": "2026-10-02T10:05:00+00:00", "checked": 70, "by_status": {"resolved": 66, "review": 4},
        "review": [{"state": "INTL-ETER", "name": "FernFH", "status": "review", "flags": ["x", "x"]}], "unresolved": []})
    write(tmp_path, "data/reports/dedup_report.json", {
        "generated_at": "2026-10-02T10:06:00+00:00", "source_records": 528, "institutions": 505,
        "merged_institutions": 16, "records_merged_away": 23, "review_cases": 0, "review": [], "conflicts": []})
    write(tmp_path, "data/reports/presence_validation.json", {
        "generated_at": "2026-10-02T10:07:00+00:00", "counts": {"confirmed": 431, "review": 4, "not_present": 0,
                                                              "no_german_source_listing": 70},
        "review": [{"registry_id": "PTH-DE-1", "name": "Akademie", "doubts": [{"code": "no_verified_website",
                                                                              "detail": "no verified official website"}]}],
        "decision_warnings": []})
    write(tmp_path, "data/reports/online_de_validation.json", {
        "generated_at": "2026-10-02T10:07:00+00:00", "counts": {"confirmed": 0, "review": 70, "not_available": 0},
        "review": [{"registry_id": "PTH-DE-2", "name": "UOC", "country": "ES", "discovery_sources": ["INTL-ETER"]}],
        "decision_warnings": []})
    # master report older than dedup: not re-run after dedup
    write(tmp_path, "data/reports/validation_report.json", {
        "generated_at": "2026-10-02T09:00:00+00:00", "master_universities": 505,
        "stable_ids": {"existing": 435, "kept": 435, "new": 70, "merged": 0, "unlisted": [], "all_existing_kept": True},
        "review_required": []})
    return tmp_path


def test_overview_from_reports(reports):
    o = overview(ReportCache(reports))
    h = o["header"]
    assert h["build_status"] == "review" and h["production_safe"] is False   # worst of both status files
    assert (h["sources_ok"], h["sources_total"]) == (18, 18)
    assert h["drift"] == 1 and h["errors"] == 0
    assert h["institutions"] == 505 and h["stable_ids"]["kept"] == 435
    assert h["online_de_candidates"] == 1
    assert h["review"] == 3                       # drift + website + presence (online_de separate)

    steps = {s["id"]: s for s in o["steps"]}
    assert len(o["steps"]) == 9
    assert steps["german_discovery"]["status"] == "warning"          # drift
    assert ["Gesamt", "70 Kandidaten"] in steps["international_discovery"]["lines"]
    assert steps["websites"]["lines"][0] == ["international", "66 / 70 bestätigt (94,3 %)"]
    assert steps["agent"]["status"] == "pending"                     # no report
    assert steps["master"]["stale"] is True
    assert ["Bestehende IDs erhalten", "435 / 435"] in steps["master"]["lines"]

    groups = {g["id"]: g for g in o["reviews"]}
    assert groups["drift"]["items"][0]["reasons"] == ["8 → 3 (-5, -62.5 %)"]
    assert groups["website"]["items"][0]["reasons"] == ["review", "x"]   # duplicates removed
    assert groups["presence"]["items"][0]["reasons"] == ["no verified official website"]
    assert groups["online_de"]["items"][0]["subtitle"].startswith("ES")
    assert {s["state"] for s in o["sources"]} >= {"DE-SL", "INTL-ETER"}


def test_overview_without_reports(tmp_path):
    o = overview(ReportCache(tmp_path))
    assert o["header"]["build_status"] == "unknown"
    assert {s["status"] for s in o["steps"]} == {"pending"}


@pytest.mark.skipif(not (SCRAPER_DIR / "registry" / "run.py").is_file(), reason="scraper not checked out")
def test_overview_of_the_real_scraper_reports():
    o = overview(ReportCache(SCRAPER_DIR))
    assert len(o["steps"]) == 9 and o["header"]["sources_total"] >= 16


# ----------------------------------------------------------------------
# API
# ----------------------------------------------------------------------

def test_build_api(bridge, reports):
    bridge.dir = reports
    client = TestClient(create_app(bridge, pipeline=PipelineProcess(reports)))

    s = client.get("/api/build/state").json()
    assert set(s) == {"overview", "process", "live"}
    assert s["overview"]["header"]["institutions"] == 505
    assert client.get("/build").status_code == 200
    assert client.post("/api/build/start", json={"start": "supabase", "stop": "dedup"}).status_code == 422
    assert client.post("/api/build/cancel").status_code == 409
