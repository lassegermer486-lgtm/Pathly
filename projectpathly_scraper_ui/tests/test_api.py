from fastapi.testclient import TestClient

from conftest import wait_idle
from scraper_ui.app import create_app
from scraper_ui.runner import pair_id

PAIR = ("DE-AA|Alpha Uni", "DE-BB|Alpha Universität Campus B")


def client_for(bridge):
    app = create_app(bridge)
    return TestClient(app), app.state.runner


def test_page_and_meta(bridge):
    client, _ = client_for(bridge)
    assert "Hochschulregister" in client.get("/").text
    assert client.get("/static/app.js").status_code == 200
    meta = client.get("/api/meta").json()
    assert [s["short"] for s in meta["states"]] == ["AA", "BB", "CC"]
    assert meta["overrides_file"] == "data/master/overrides.yaml"


def test_full_flow_over_http(bridge):
    client, runner = client_for(bridge)
    assert client.post("/api/save", json={}).status_code == 409        # nothing to save yet

    assert client.post("/api/run", json={}).status_code == 200
    wait_idle(runner)

    state = client.get("/api/state").json()
    assert state["phase"] == "review" and state["kpis"]["review_open"] == 1

    records = client.get("/api/records").json()
    assert len(records["rows"]) == 4 and len(records["review"]) == 1
    assert sum(r["_review_open"] for r in records["rows"]) == 2

    assert client.post("/api/save", json={}).status_code == 409        # blocked: duplicate open
    assert client.get("/api/download").status_code == 409

    pid = pair_id(*PAIR)
    assert client.post(f"/api/review/{pid}", json={"decision": "merge", "note": "x"}).status_code == 200
    assert client.post("/api/review/unbekannt", json={"decision": "merge"}).status_code == 404

    saved = client.post("/api/save", json={})
    assert saved.status_code == 200 and saved.json()["files"]
    assert client.get("/api/state").json()["phase"] == "saved"

    download = client.get("/api/download")
    assert download.status_code == 200 and len(download.json()) == 3
    assert "attachment" in download.headers["content-disposition"]


def test_bad_requests(bridge):
    client, _ = client_for(bridge)
    assert client.post("/api/run", json={"source": "irgendwas"}).status_code == 422
    assert client.post("/api/run", json={"states": ["DE-XX"]}).status_code == 409
    assert client.post("/api/run", json={"source": "file"}).status_code == 409    # no saved scrape
    assert client.post("/api/cancel", json={}).status_code == 409
