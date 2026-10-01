"""
Bridge to the scraper — the ONLY module of the UI that touches scraper code.

The UI lives in its own folder and never changes files of the scraper package.
Everything it needs from the scraper is looked up here, by feature detection:

    registry.run.scrape            (v1.2+)   else ADAPTERS/normalize_state (v1.1)
    registry.states.STATES         (v1.2+)   else STATE_ORDER / fallback list
    registry.master.*              (v1.2+)   else: no dedup, raw records are shown

If a later scraper version renames or adds something, this file is the single
place to adapt. Missing optional parts degrade gracefully and are reported in
`capabilities()` so the UI can say what is (not) available.
"""
from __future__ import annotations

import contextlib
import importlib
import inspect
import json
import os
import sys
import threading
from collections import Counter
from pathlib import Path
from typing import Callable

import yaml

Log = Callable[[str], None]

FALLBACK_STATES = [
    ("DE-BW", "BW", "Baden-Württemberg"), ("DE-BY", "BY", "Bayern"),
    ("DE-BE", "BE", "Berlin"), ("DE-BB", "BB", "Brandenburg"),
    ("DE-HB", "HB", "Bremen"), ("DE-HH", "HH", "Hamburg"),
    ("DE-HE", "HE", "Hessen"), ("DE-MV", "MV", "Mecklenburg-Vorpommern"),
    ("DE-NI", "NI", "Niedersachsen"), ("DE-NW", "NRW", "Nordrhein-Westfalen"),
    ("DE-RP", "RP", "Rheinland-Pfalz"), ("DE-SL", "SL", "Saarland"),
    ("DE-SN", "SN", "Sachsen"), ("DE-ST", "ST", "Sachsen-Anhalt"),
    ("DE-SH", "SH", "Schleswig-Holstein"), ("DE-TH", "TH", "Thüringen"),
]


class ScraperNotFound(RuntimeError):
    pass


class _LineWriter:
    """File-like object that forwards complete lines to a log callback."""

    def __init__(self, log: Log):
        self._log = log
        self._buf = ""
        self._lock = threading.Lock()

    def write(self, text: str) -> int:
        with self._lock:
            self._buf += text
            *lines, self._buf = self._buf.split("\n")
        for line in lines:
            if line.strip():
                self._log(line.rstrip())
        return len(text)

    def flush(self) -> None:
        with self._lock:
            rest, self._buf = self._buf, ""
        if rest.strip():
            self._log(rest.rstrip())


@contextlib.contextmanager
def capture_output(log: Log):
    """Adapters print their progress; route that into the UI log."""
    writer = _LineWriter(log)
    with contextlib.redirect_stdout(writer):
        try:
            yield
        finally:
            writer.flush()


def _accepted_kwargs(func, **kwargs) -> dict:
    """Pass only the keyword arguments this version of `func` knows."""
    try:
        params = inspect.signature(func).parameters
    except (TypeError, ValueError):
        return kwargs
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return kwargs
    return {k: v for k, v in kwargs.items() if k in params}


class ScraperBridge:
    def __init__(self, scraper_dir: str | os.PathLike):
        self.dir = Path(scraper_dir).resolve()
        if not (self.dir / "registry" / "run.py").is_file():
            raise ScraperNotFound(
                f"Kein Scraper gefunden in {self.dir} (registry/run.py fehlt). "
                "Pfad über die Umgebungsvariable PATHLY_SCRAPER_DIR setzen."
            )

        # The scraper uses paths relative to its own folder
        # (registry/sources.yaml, data/..., config/...).
        os.chdir(self.dir)
        if str(self.dir) not in sys.path:
            sys.path.insert(0, str(self.dir))

        self._run = importlib.import_module("registry.run")
        self._states = self._load_states()
        self._master = self._load_master()

        self.sources_path = self.dir / "registry" / "sources.yaml"
        self.overrides_path = self.dir / "config" / "overrides.yaml"
        self.id_registry_path = self.dir / "config" / "id_registry.json"
        self.last_scrape_path = self.dir / "data" / "normalized" / "universities_de.json"
        self.registry_path = self.dir / "data" / "master" / "university_registry.json"

    # ------------------------------------------------------------------
    # feature detection
    # ------------------------------------------------------------------

    def _load_states(self) -> list[dict]:
        try:
            mod = importlib.import_module("registry.states")
            return [{"code": s.code, "short": s.short, "name": s.name} for s in mod.STATES]
        except Exception:
            pass
        order = getattr(self._run, "STATE_ORDER", None)
        known = {c: (s, n) for c, s, n in FALLBACK_STATES}
        if order:
            return [{"code": c, "short": known.get(c, (c, c))[0], "name": known.get(c, (c, c))[1]}
                    for c in order]
        return [{"code": c, "short": s, "name": n} for c, s, n in FALLBACK_STATES]

    def _load_master(self) -> dict | None:
        """Functions of the dedup pipeline, or None if this version has none."""
        try:
            merge = importlib.import_module("registry.master.merge")
            candidates = importlib.import_module("registry.master.candidates")
            fns = {
                "unify_record": merge.unify_record,
                "cluster": merge.cluster,
                "merge_cluster": merge.merge_cluster,
                "find_candidates": candidates.find_candidates,
            }
        except Exception:
            return None

        # Optional parts: the registry still builds without them.
        try:
            fns["identity"] = importlib.import_module("registry.master.identity")
        except Exception:
            fns["identity"] = None
        try:
            validate = importlib.import_module("registry.master.validate")
            fns["offline_checks"] = getattr(validate, "offline_checks", None)
            fns["cross_checks"] = getattr(validate, "cross_checks", None)
            fns["web_checks"] = getattr(validate, "web_checks", None)
        except Exception:
            fns["offline_checks"] = fns["cross_checks"] = fns["web_checks"] = None
        return fns

    def capabilities(self) -> dict:
        m = self._master
        return {
            "scraper_dir": str(self.dir),
            "scrape_function": hasattr(self._run, "scrape"),
            "dedup": m is not None,
            "stable_ids": bool(m and m.get("identity")),
            "validation": bool(m and m.get("offline_checks")),
            "web_check": bool(m and m.get("web_checks")),
            "last_scrape_available": self.last_scrape_path.is_file(),
        }

    def states(self) -> list[dict]:
        return list(self._states)

    def short(self, code: str | None) -> str:
        for s in self._states:
            if s["code"] == code:
                return s["short"]
        return code or "?"

    # ------------------------------------------------------------------
    # scraping
    # ------------------------------------------------------------------

    def load_config(self) -> dict:
        loader = getattr(self._run, "load_config", None)
        if loader:
            return loader()
        return yaml.safe_load(self.sources_path.read_text(encoding="utf-8"))

    def scrape_state(self, code: str, config: dict, log: Log) -> tuple[list[dict], dict]:
        """
        Scrape one state. Returns (records, report) where report has at least
        {"state", "status"}; status is OK, ERROR, SKIPPED or TODO.
        Never raises for a failing source — that is reported as ERROR.
        """
        with capture_output(log):
            try:
                scrape = getattr(self._run, "scrape", None)
                if scrape:
                    records, report = scrape(
                        [code], config, **_accepted_kwargs(scrape, snapshots=False, log=log))
                    entry = report[0] if report else {"state": code, "status": "ERROR",
                                                       "error": "kein Ergebnis"}
                    return list(records), dict(entry)
                return self._scrape_state_legacy(code, config, log)
            except Exception as exc:  # defensive: a scraper bug must not kill the run
                log(f"[ERROR] {code}: {type(exc).__name__}: {exc}")
                return [], {"state": code, "status": "ERROR",
                            "error": f"{type(exc).__name__}: {exc}"}

    def _scrape_state_legacy(self, code: str, config: dict, log: Log) -> tuple[list[dict], dict]:
        """Scraper versions without `scrape()` (v1.1): same steps as its main()."""
        if code not in config:
            return [], {"state": code, "status": "ERROR", "error": "missing_config"}
        cfg = dict(config[code])
        if not cfg.get("enabled", True):
            return [], {"state": code, "status": "SKIPPED"}
        adapter_cls = self._run.ADAPTERS.get(cfg.get("adapter", "stub"))
        if adapter_cls is None:
            return [], {"state": code, "status": "ERROR",
                        "error": f"unknown_adapter:{cfg.get('adapter')}"}
        cfg.setdefault("_raw_dir", "data/raw")
        log(f"[FETCH] {code} — {cfg.get('name', code)}")
        try:
            rows = adapter_cls(code, cfg).fetch()
            records = self._run.normalize_state(code, rows)
            invalid = self._run.validate_registry(records)
        except NotImplementedError as exc:
            log(f"[TODO] {exc}")
            return [], {"state": code, "status": "TODO"}
        locations = sum(len(u.get("locations", [])) for u in records)
        log(f"[OK] {code}: {len(records)} universities / {locations} locations")
        return records, {
            "state": code, "name": cfg.get("name"), "status": "OK",
            "raw_rows": len(rows), "universities": len(records),
            "locations": locations, "validation_issues": len(invalid),
        }

    def load_last_scrape(self) -> list[dict]:
        return json.loads(self.last_scrape_path.read_text(encoding="utf-8"))

    # ------------------------------------------------------------------
    # dedup / master registry
    # ------------------------------------------------------------------

    def load_overrides(self) -> dict:
        if not self.overrides_path.is_file():
            return {}
        return yaml.safe_load(self.overrides_path.read_text(encoding="utf-8")) or {}

    def build(self, raw: list[dict], log: Log, online: bool = False,
              web_flags: dict | None = None) -> dict:
        """
        Raw state records -> master registry. Mirrors `python -m registry.master`
        (candidates -> merge -> ids -> validation) without writing anything.

        `web_flags` are cached results of an earlier online check, so decisions
        can be recomputed without fetching every website again.
        """
        if self._master is None:
            return self._build_without_dedup(raw)

        m = self._master
        with capture_output(log):
            records = [m["unify_record"](r) for r in raw]
            overrides = self.load_overrides()

            known = {r["source_key"] for r in records}
            override_warnings = []
            for section in ("merge", "keep_separate"):
                for pair in overrides.get(section) or []:
                    for key in pair:
                        if key not in known:
                            override_warnings.append({"section": section, "key": key})

            candidates = m["find_candidates"](records, overrides)
            masters = [m["merge_cluster"](g) for g in m["cluster"](records, candidates)]
            masters.sort(key=lambda x: ((x.get("states") or [""])[:1], x.get("name") or ""))

            id_registry, id_warnings = None, []
            if m.get("identity"):
                id_registry = m["identity"].load(self.id_registry_path)
                id_warnings = m["identity"].assign_ids(masters, id_registry)
            for i, master in enumerate(masters):
                master.setdefault("university_id", f"ROW-{i + 1:05d}")

            extra = m["cross_checks"](masters) if m.get("cross_checks") else {}
            if online and m.get("web_checks"):
                web_flags = m["web_checks"](masters)
            web_flags = web_flags or {}

            per_record = overrides.get("records") or {}
            for master in masters:
                uid = master["university_id"]
                master["lifecycle_status"] = "unknown"
                master.update(per_record.get(uid, {}))
                offline = m["offline_checks"](master) if m.get("offline_checks") else []
                master["validation_flags"] = offline + extra.get(uid, []) + web_flags.get(uid, [])

        return {
            "dedup": True,
            "records": records,
            "candidates": candidates,
            "masters": masters,
            "overrides": overrides,
            "override_warnings": override_warnings,
            "id_registry": id_registry,
            "id_warnings": id_warnings,
            "web_flags": web_flags,
        }

    def _build_without_dedup(self, raw: list[dict]) -> dict:
        masters = []
        for i, r in enumerate(raw):
            state = r.get("state")
            locations = r.get("locations") or []
            masters.append({
                **r,
                "university_id": f"ROW-{i + 1:05d}",
                "states": sorted({l.get("state") or state for l in locations if (l.get("state") or state)})
                          or ([state] if state else []),
                "listed_by": [state] if state else [],
                "merged_from": [],
                "validation_flags": [],
            })
        records = [{**r, "source_key": f"{r.get('state')}|{r.get('name')}"} for r in raw]
        return {
            "dedup": False, "records": records, "candidates": [], "masters": masters,
            "overrides": {}, "override_warnings": [], "id_registry": None,
            "id_warnings": [], "web_flags": {},
        }

    @staticmethod
    def summary(result: dict) -> dict:
        masters = result["masters"]
        candidates = result["candidates"]
        return {
            "input_records": len(result["records"]),
            "master_records": len(masters),
            "auto_merge_pairs": sum(c.get("decision") == "auto_merge" for c in candidates),
            "review_pairs": sum(c.get("decision") == "review" for c in candidates),
            "id_warnings": result.get("id_warnings") or [],
            "flag_counts": dict(Counter(f.get("code") for m in masters
                                        for f in m.get("validation_flags") or [])),
            "by_type": dict(Counter(m.get("institution_type") or "unknown" for m in masters)),
            "by_ownership": dict(Counter(m.get("ownership") or "unknown" for m in masters)),
            "by_recognition": dict(Counter(m.get("recognition_status") or "unknown" for m in masters)),
        }

    # ------------------------------------------------------------------
    # saving — same files as `python -m registry.master --save`
    # ------------------------------------------------------------------

    @staticmethod
    def _write_json(path: Path, data) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    def save(self, result: dict, raw: list[dict], complete: bool, scraped_codes: list[str]) -> list[str]:
        """Write the registry and its reports. Returns the written paths (relative)."""
        written = []

        def rel(p: Path) -> str:
            return str(p.relative_to(self.dir))

        # The raw state scrape, as the CLI scraper stores it. A partial scrape
        # must not overwrite the full dataset.
        if complete:
            scrape_path = self.last_scrape_path
        else:
            suffix = "_".join(self.short(c) for c in scraped_codes) or "teil"
            scrape_path = self.last_scrape_path.with_name(f"universities_{suffix}.json")
        self._write_json(scrape_path, raw)
        written.append(rel(scrape_path))

        if result.get("dedup"):
            self._write_json(self.registry_path, result["masters"])
            written.append(rel(self.registry_path))

            reports = self.dir / "data" / "reports"
            self._write_json(reports / "dedup_candidates.json", result["candidates"])
            self._write_json(reports / "master_summary.json", self.summary(result))
            written += [rel(reports / "dedup_candidates.json"), rel(reports / "master_summary.json")]

            identity = self._master.get("identity") if self._master else None
            if identity and result.get("id_registry") is not None:
                identity.save(self.id_registry_path, result["id_registry"])
                written.append(rel(self.id_registry_path))
        return written
