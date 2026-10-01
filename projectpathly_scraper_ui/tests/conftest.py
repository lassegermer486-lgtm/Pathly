"""
A stand-in for the scraper bridge, so the UI logic is tested without network
and without depending on a particular scraper version.

The fake dedup rule: two records with the same `official_url` are a review
pair, unless overrides.yaml decides otherwise.
"""
import json
import sys
import time
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper_ui.runner import BUSY_PHASES  # noqa: E402

STATES = [{"code": "DE-AA", "short": "AA", "name": "A-Land"},
          {"code": "DE-BB", "short": "BB", "name": "B-Land"},
          {"code": "DE-CC", "short": "CC", "name": "C-Land"}]


def record(name, state, url=None):
    return {"name": name, "state": state, "official_url": url,
            "institution_type": "university", "ownership": "public",
            "recognition_status": "unknown",
            "locations": [{"city": "Stadt", "state": state}]}


class FakeBridge:
    def __init__(self, tmp_path: Path, dedup=True):
        self.dir = tmp_path
        self.dedup = dedup
        self.overrides_path = tmp_path / "data" / "master" / "overrides.yaml"
        self.last_scrape_path = tmp_path / "data" / "normalized" / "universities_de.json"
        self.registry_path = tmp_path / "data" / "master" / "universities_de_master.json"
        self.data = {
            "DE-AA": [record("Alpha Uni", "DE-AA", "https://alpha.example"),
                      record("Solo Hochschule", "DE-AA", "https://solo.example")],
            "DE-BB": [record("Alpha Universität Campus B", "DE-BB", "https://alpha.example")],
            "DE-CC": [record("Gamma Hochschule", "DE-CC", None)],
        }
        self.failing = set()
        self.saved = None
        self.scrape_calls = []

    def states(self):
        return list(STATES)

    def short(self, code):
        return next((s["short"] for s in STATES if s["code"] == code), code)

    def capabilities(self):
        return {"scraper_dir": str(self.dir), "scrape_function": True, "dedup": self.dedup,
                "stable_ids": self.dedup, "validation": self.dedup, "web_check": False,
                "last_scrape_available": self.last_scrape_path.is_file()}

    def load_config(self):
        return {}

    def scrape_state(self, code, config, log):
        self.scrape_calls.append(code)
        log(f"[FETCH] {code}")
        if code in self.failing:
            return [], {"state": code, "status": "ERROR", "error": "ConnectionError: kaputt"}
        rows = self.data[code]
        return list(rows), {"state": code, "status": "OK", "universities": len(rows),
                            "locations": len(rows)}

    def load_last_scrape(self):
        return json.loads(self.last_scrape_path.read_text(encoding="utf-8"))

    def load_overrides(self):
        if not self.overrides_path.is_file():
            return {}
        return yaml.safe_load(self.overrides_path.read_text(encoding="utf-8")) or {}

    def build(self, raw, log, online=False, websites=None, quick=False):
        records = [{**r, "source_key": f"{r['state']}|{r['name']}", "sources": []} for r in raw]
        overrides = self.load_overrides() if self.dedup else {}
        merge = {frozenset(p) for p in overrides.get("merge") or []}
        separate = {frozenset(p) for p in overrides.get("keep_separate") or []}

        candidates, groups = [], {r["source_key"]: [r] for r in records}
        if self.dedup:
            for i, a in enumerate(records):
                for b in records[i + 1:]:
                    if not a["official_url"] or a["official_url"] != b["official_url"]:
                        continue
                    pair = frozenset((a["source_key"], b["source_key"]))
                    if pair in separate:
                        continue
                    decision = "auto_merge" if pair in merge else "review"
                    candidates.append({"a": a["source_key"], "b": b["source_key"],
                                       "decision": decision, "reasons": ["same website"],
                                       "signals": {"domain_exact": True}})
                    if decision == "auto_merge":
                        groups[a["source_key"]] += groups.pop(b["source_key"])
        masters = []
        for i, members in enumerate(groups.values()):
            first = members[0]
            masters.append({
                "university_id": f"ID-{i}", "name": first["name"],
                "institution_type": first["institution_type"], "ownership": first["ownership"],
                "recognition_status": first["recognition_status"],
                "official_url": first["official_url"],
                "states": sorted({m["state"] for m in members}),
                "listed_by": sorted({m["state"] for m in members}),
                "locations": [l for m in members for l in m["locations"]],
                "sources": [],
                "merged_from": [{"source_key": m["source_key"], "name": m["name"]} for m in members],
                "validation_flags": [] if first["official_url"] else
                                    [{"code": "missing_official_url", "severity": "high", "detail": None}],
            })
        return {"dedup": self.dedup, "records": records, "candidates": candidates,
                "masters": masters, "overrides": overrides, "override_warnings": [],
                "id_registry": None, "id_warnings": [], "websites": {}}

    @staticmethod
    def summary(result):
        from scraper_ui.bridge import ScraperBridge
        return ScraperBridge.summary(result)

    def save(self, result, raw, complete, scraped_codes):
        self.saved = {"masters": result["masters"], "raw": raw, "complete": complete,
                      "codes": scraped_codes}
        return ["data/master/universities_de_master.json"]

    def import_script(self):
        universities = [{"registry_id": m["university_id"], "name": m["name"]}
                        for m in self.saved["masters"]]
        payload = {"universities": universities,
                   "counts": {"universities": len(universities), "locations": 0}}
        return payload, "begin; -- fake import\ncommit;"


def wait_idle(runner, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if runner.phase not in BUSY_PHASES and runner.phase != "idle":
            return
        time.sleep(0.01)
    raise AssertionError(f"run did not finish, phase={runner.phase}")


@pytest.fixture
def bridge(tmp_path):
    return FakeBridge(tmp_path)
