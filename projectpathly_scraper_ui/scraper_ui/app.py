"""HTTP API and static page of the scraper UI."""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .bridge import ScraperBridge
from .runner import Conflict, NotFound, Runner

STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_SCRAPER_DIR = Path(__file__).resolve().parents[2] / "projectpathly_registry_scraper"


class RunRequest(BaseModel):
    states: list[str] | None = None
    online: bool = False
    source: str = "live"


class DecisionRequest(BaseModel):
    decision: str | None = None
    note: str = ""


class SaveRequest(BaseModel):
    confirm_incomplete: bool = False


def create_app(bridge: ScraperBridge | None = None) -> FastAPI:
    if bridge is None:
        bridge = ScraperBridge(os.environ.get("PATHLY_SCRAPER_DIR") or DEFAULT_SCRAPER_DIR)
    runner = Runner(bridge)

    app = FastAPI(title="ProjectPathly Scraper UI", docs_url=None, redoc_url=None)
    app.state.runner = runner
    app.state.bridge = bridge

    def guarded(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Conflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except NotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/meta")
    def meta():
        return {"states": bridge.states(), "capabilities": bridge.capabilities(),
                "overrides_file": bridge.overrides_path.relative_to(bridge.dir).as_posix(),
                "registry_file": bridge.registry_path.relative_to(bridge.dir).as_posix()}

    @app.get("/api/state")
    def state(log_since: int = 0):
        return runner.snapshot(log_since)

    @app.get("/api/records")
    def records():
        return runner.records()

    @app.post("/api/run")
    def run(body: RunRequest):
        if body.source not in ("live", "file"):
            raise HTTPException(status_code=422, detail="source muss 'live' oder 'file' sein.")
        guarded(runner.start, body.states, body.online, body.source)
        return {"ok": True}

    @app.post("/api/cancel")
    def cancel():
        guarded(runner.cancel)
        return {"ok": True}

    @app.post("/api/states/{code}/retry")
    def retry(code: str):
        guarded(runner.retry_state, code)
        return {"ok": True}

    @app.post("/api/review/{pair_id}")
    def decide(pair_id: str, body: DecisionRequest):
        guarded(runner.decide, pair_id, body.decision, body.note)
        return {"ok": True}

    @app.post("/api/save")
    def save(body: SaveRequest):
        return guarded(runner.save, body.confirm_incomplete)

    @app.post("/api/db/push")
    def db_push():
        return guarded(runner.push_to_db)

    @app.get("/api/download")
    def download():
        data = guarded(runner.registry)
        return Response(
            content=json.dumps(data, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="universities_de_master.json"'},
        )

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-store"})

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app
