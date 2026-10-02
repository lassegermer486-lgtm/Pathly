"""
Bridge to the scraper — the ONLY module of the UI that touches scraper code.

The UI lives in its own folder and never changes files of the scraper package.
Everything it needs from the scraper is looked up here.

Scraper v1.2 builds the registry in steps (registry/pipeline.py). The UI runs
the same steps in memory and writes the same files when saving:

    discovery   registry.run                          per state, live
    websites    registry.enrichment.website_resolver  "Websites prüfen": live check,
                                                      otherwise the results already in
                                                      data/enriched/universities_de_urls.json
    dedup       registry.master.dedup                 decisions: data/master/overrides.yaml
    master      registry.master.build                 names, lifecycle, stable IDs; reads
                                                      the websites of the few institutions
                                                      whose source names disagree
    supabase    registry.master.supabase_import       SQL for "In Datenbank laden"

The agent resolver (paid API) is not run from the UI; its cached answers are
part of data/enriched/ and are used from there.

If a later scraper version renames or adds something, this file is the single
place to adapt. Without the v1.2 pipeline the UI still shows the raw records
(no dedup), reported in `capabilities()`.
"""
from __future__ import annotations

import contextlib
import functools
import importlib
import inspect
import json
import os
import sys
import threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
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

# Review rules of registry.master.dedup, as the UI explains them.
RULE_TEXT = {
    "rule_1_same_name_same_site": "gleicher Name, gleiche Website",
    "rule_2_name_variant_same_site": "Namensvariante, gleiche Website",
    "rule_3_same_name_different_site": "gleicher Name, verschiedene Websites",
    "rule_3_same_name_unverified_site": "gleicher Name, Website nicht bestätigt",
    "rule_5_location_suffix": "Name bis auf Ortszusatz gleich",
    "same_site_unrelated_names": "gleiche Website, verschiedene Namen",
    "shared_acronym_different_site": "gleiches Kürzel, verschiedene Websites",
}

WEBSITE_WORKERS = 8


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


def _speed_up_dedup(dedup) -> None:
    """
    dedup compares every pair of records (about 100,000) and normalises both
    names again for each pair: about 10 s per run, too slow for a decision
    click. These helpers are pure string functions, so caching them changes
    nothing but the speed (about 0.3 s). Only dedup's own references are
    replaced; the scraper's files stay untouched.
    """
    for name in ("fold", "core_name", "name_key", "base_name_key",
                 "distinctive_tokens", "is_generic", "domain_key"):
        func = getattr(dedup, name, None)
        if func is not None and not hasattr(func, "cache_info"):
            setattr(dedup, name, functools.lru_cache(maxsize=None)(func))

    acronyms = getattr(dedup, "explicit_acronyms", None)
    if acronyms is not None and not hasattr(acronyms, "cache_info"):
        # Returns a list; cached as a tuple so no caller can change the cache.
        cached = functools.lru_cache(maxsize=None)(lambda name: tuple(acronyms(name)))
        dedup.explicit_acronyms = cached


def _record_key(record: dict) -> str:
    """Same key as registry.master.dedup.record_key and overrides.yaml."""
    return f"{record.get('state')}|{record.get('name')}"


def _is_international(record: dict) -> bool:
    """v1.3 international candidates carry a source namespace, not a state."""
    return str(record.get("state") or "").startswith("INTL-")


def _not_checked(record: dict) -> dict:
    """website_resolution of a record nobody has checked (as the resolver writes it)."""
    return {
        "status": "not_checked", "method": None, "confidence": None,
        "official_url": record.get("official_url"), "source_url": record.get("official_url"),
        "http_status": None, "identity": None, "flags": [], "candidates": [], "checked_at": None,
    }


class ScraperBridge:
    def __init__(self, scraper_dir: str | os.PathLike):
        self.dir = Path(scraper_dir).resolve()
        if not (self.dir / "registry" / "run.py").is_file():
            raise ScraperNotFound(
                f"Kein Scraper gefunden in {self.dir} (registry/run.py fehlt). "
                "Pfad über die Umgebungsvariable PATHLY_SCRAPER_DIR setzen."
            )

        # The scraper uses paths relative to its own folder
        # (registry/sources.yaml, data/...).
        os.chdir(self.dir)
        if str(self.dir) not in sys.path:
            sys.path.insert(0, str(self.dir))

        self._run = importlib.import_module("registry.run")
        self._states = self._load_states()
        self._pipeline = self._load_pipeline()
        self._site_texts = None   # website texts for name choice, cached per session

        self.sources_path = self.dir / "registry" / "sources.yaml"
        self.master_dir = self.dir / "data" / "master"
        self.reports_dir = self.dir / "data" / "reports"
        self.overrides_path = self.master_dir / "overrides.yaml"
        self.id_registry_path = self.master_dir / "id_registry.json"
        self.last_scrape_path = self.dir / "data" / "normalized" / "universities_de.json"
        self.enriched_path = self.dir / "data" / "enriched" / "universities_de_urls.json"
        # v1.3: international candidates (registry.international + website check
        # on the command line); the UI does not fetch them, it keeps them.
        self.intl_enriched_path = self.dir / "data" / "enriched" / "universities_intl_urls.json"
        self.registry_path = self.master_dir / "universities_de_master.json"

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

    def _load_pipeline(self) -> SimpleNamespace | None:
        """Modules of the v1.2 registry build, or None if this version has none."""
        try:
            pipeline = SimpleNamespace(
                website=importlib.import_module("registry.enrichment.website_resolver"),
                dedup=importlib.import_module("registry.master.dedup"),
                build=importlib.import_module("registry.master.build"),
                supabase=importlib.import_module("registry.master.supabase_import"),
            )
        except Exception:
            return None
        _speed_up_dedup(pipeline.dedup)
        return pipeline

    def capabilities(self) -> dict:
        has = self._pipeline is not None
        return {
            "scraper_dir": str(self.dir),
            "scrape_function": hasattr(self._run, "scrape"),
            "dedup": has,
            "stable_ids": has,
            "validation": has,
            "web_check": has,
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
                return self._scrape_state_adapters(code, config, log)
            except Exception as exc:  # defensive: a scraper bug must not kill the run
                log(f"[ERROR] {code}: {type(exc).__name__}: {exc}")
                return [], {"state": code, "status": "ERROR",
                            "error": f"{type(exc).__name__}: {exc}"}

    def _scrape_state_adapters(self, code: str, config: dict, log: Log) -> tuple[list[dict], dict]:
        """Scraper versions without `scrape()`: the same steps as registry.run.main()."""
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

    def _international_records(self) -> list[dict]:
        """Website-checked international candidates (v1.3), as the CLI wrote them."""
        if not self.intl_enriched_path.is_file():
            return []
        return json.loads(self.intl_enriched_path.read_text(encoding="utf-8"))

    def load_last_scrape(self) -> list[dict]:
        return json.loads(self.last_scrape_path.read_text(encoding="utf-8"))

    # ------------------------------------------------------------------
    # websites (registry.enrichment.website_resolver)
    # ------------------------------------------------------------------

    def _stored_websites(self) -> dict[str, dict]:
        """Website results of the last saved run, by record key."""
        if not self.enriched_path.is_file():
            return {}
        records = json.loads(self.enriched_path.read_text(encoding="utf-8"))
        return {_record_key(r): r["website_resolution"]
                for r in records if r.get("website_resolution")}

    def _check_websites(self, raw: list[dict], log: Log) -> dict[str, dict]:
        """Live check of every record, as `python -m registry.enrichment.website_resolver`."""
        w = self._pipeline.website
        known_cities = frozenset(
            w.fold(location["city"])
            for record in raw
            for location in record.get("locations") or []
            if location.get("city")
        )
        resolver = w.WebsiteResolver(known_cities=known_cities)
        results = {}
        log(f"[WEB] Prüfe {len(raw)} Websites …")

        with ThreadPoolExecutor(max_workers=WEBSITE_WORKERS) as pool:
            futures = {pool.submit(resolver.resolve, record): record for record in raw}
            for future in as_completed(futures):
                record = futures[future]
                try:
                    res = future.result()
                except Exception as exc:  # one broken site must not stop the run
                    res = {**_not_checked(record), "status": "review", "confidence": 0.0,
                           "flags": [f"resolver_error_{type(exc).__name__}"],
                           "checked_at": datetime.now(timezone.utc).isoformat()}
                results[_record_key(record)] = res
                log(f"[WEB] {res['status']:10s} {record.get('state')} {record.get('name')} "
                    f"{res.get('official_url') or res.get('suggested_url') or ''}")
        return results

    def _with_websites(self, raw: list[dict], log: Log, online: bool,
                       websites: dict | None) -> tuple[list[dict], dict]:
        """Raw records -> enriched records (official_url + website_resolution)."""
        known = self._stored_websites()
        known.update(websites or {})
        if online:
            known.update(self._check_websites(raw, log))

        enriched, used = [], {}
        for record in raw:
            key = _record_key(record)
            record = dict(record)
            resolution = known.get(key)
            if resolution:
                record["official_url"] = resolution.get("official_url")
                record["website_resolution"] = resolution
                used[key] = resolution
            else:
                record["website_resolution"] = _not_checked(record)
            enriched.append(record)
        return enriched, used

    # ------------------------------------------------------------------
    # dedup / master registry
    # ------------------------------------------------------------------

    def load_overrides(self) -> dict:
        if not self.overrides_path.is_file():
            return {}
        return yaml.safe_load(self.overrides_path.read_text(encoding="utf-8")) or {}

    def _load_id_registry(self):
        data = (json.loads(self.id_registry_path.read_text(encoding="utf-8"))
                if self.id_registry_path.is_file() else None)
        return self._pipeline.build.IdRegistry(data)

    def _name_check(self):
        """
        registry.master.build reads an institution's website when its source
        names disagree (only those, about 15). As in the CLI default this
        always happens; the texts are kept, so a rebuild after a decision
        fetches nothing again.
        """
        if self._site_texts is None:
            p = self._pipeline
            self._site_texts = p.build.make_site_texts(p.website.WebsiteResolver())
        return self._site_texts

    def build(self, raw: list[dict], log: Log, online: bool = False,
              websites: dict | None = None, quick: bool = False) -> dict:
        """
        Raw state records -> master registry, as `python -m registry.pipeline
        --from websites` without the agent, and without writing anything.

        `websites` are website results of an earlier build in this session, so
        decisions can be recomputed without checking every site again.
        `quick` skips dedup: a preview while states are still being fetched.
        """
        if self._pipeline is None or quick:
            return self._build_without_dedup(raw, preview=quick)

        p = self._pipeline
        with capture_output(log):
            records, used = self._with_websites(raw, log, online, websites)
            # Without them a save would drop the international institutions
            # from the master files (and the import would unlist them).
            records = records + self._international_records()
            overrides = p.dedup.load_overrides(self.overrides_path)
            institutions, report = p.dedup.deduplicate(records, overrides)

            id_registry = self._load_id_registry()
            built = p.build.build(institutions, records, id_registry, self._name_check())

        return {
            "dedup": True,
            "records": [{**r, "source_key": _record_key(r)} for r in records],
            "candidates": self._candidates(institutions, report),
            "masters": self._masters(built),
            "overrides": overrides,
            "override_warnings": [{"section": "merge/keep_separate", "key": key}
                                  for key in report.get("unknown_override_keys") or []],
            "id_registry": id_registry,
            "id_warnings": [f"{c['a']} / {c['b']}: {c['reason']}" for c in report.get("conflicts") or []],
            "websites": used,
            # what save() writes, in the scraper's own formats
            "pipeline": {"records": records, "institutions": institutions,
                         "dedup_report": report, "built": built},
        }

    @staticmethod
    def _candidates(institutions: list[dict], report: dict) -> list[dict]:
        """Automatic merges and open review pairs, in the shape the UI reads."""
        out = []
        for institution in institutions:
            for evidence in institution.get("merge_evidence") or []:
                if evidence.get("decision") == "auto_merge":
                    out.append({"a": evidence["a"], "b": evidence["b"], "decision": "auto_merge",
                                "rule": evidence.get("rule"),
                                "reasons": [RULE_TEXT.get(evidence.get("rule"), evidence.get("rule"))]})
        for pair in report.get("review") or []:
            text = RULE_TEXT.get(pair["rule"], pair["rule"])
            evidence = pair.get("evidence")
            if isinstance(evidence, list):
                evidence = ", ".join(evidence)
            out.append({"a": pair["a"], "b": pair["b"], "decision": "review", "rule": pair["rule"],
                        "reasons": [f"{text} ({evidence})" if evidence else text]})
        return out

    @staticmethod
    def _masters(built: dict) -> list[dict]:
        """registry.master.build output -> one row per institution for the UI."""
        def by_id(items):
            grouped = defaultdict(list)
            for item in items:
                grouped[item["registry_id"]].append(
                    {k: v for k, v in item.items() if k != "registry_id"})
            return grouped

        metadata = {m["registry_id"]: m for m in built["metadata"]}
        locations = by_id(built["locations"])
        aliases = by_id(built["aliases"])
        sources = by_id(built["sources"])

        masters = []
        for row in built["universities"]:
            rid = row["registry_id"]
            meta = metadata.get(rid, {})
            locs = locations.get(rid, [])
            masters.append({
                "university_id": rid,
                "name": row["name"],
                "name_variants": [a["alias"] for a in aliases.get(rid, [])],
                "country": row.get("country"),
                "institution_type": meta.get("institution_type", "unknown"),
                "ownership": meta.get("ownership", "unknown"),
                "recognition_status": meta.get("recognition_status", "unknown"),
                "lifecycle_status": row.get("lifecycle_status"),
                "official_url": row.get("official_url"),
                "states": sorted(set(row.get("listed_by") or [])
                                 | {l["state"] for l in locs if l.get("state")}),
                "listed_by": row.get("listed_by") or [],
                "locations": locs,
                "sources": [{"authority": s.get("authority"), "url": s.get("source_url"),
                             "state": s.get("source_state"), "category": s.get("source_category"),
                             "source_type": s.get("source_type"), "retrieved_at": s.get("retrieved_at")}
                            for s in sources.get(rid, [])],
                "merged_from": [{"source_key": key, "name": key.split("|", 1)[-1]}
                                for key in row.get("members") or []],
                "validation_flags": row.get("flags") or [],
                "website": row.get("website"),
                "name_origin": row.get("name_origin"),
                "name_confirmed": row.get("name_confirmed"),
                "former_registry_ids": row.get("former_registry_ids") or [],
            })
        return masters

    def _build_without_dedup(self, raw: list[dict], preview: bool = False) -> dict:
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
        records = [{**r, "source_key": _record_key(r)} for r in raw]
        return {
            # None: not decided yet (preview); False: this scraper version has no dedup
            "dedup": None if preview else False,
            "records": records, "candidates": [], "masters": masters,
            "overrides": {}, "override_warnings": [], "id_registry": None,
            "id_warnings": [], "websites": {},
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
    # saving — the same files as `python -m registry.pipeline`
    # ------------------------------------------------------------------

    @staticmethod
    def _write(path: Path, data) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, indent=2)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)

    def save(self, result: dict, raw: list[dict], complete: bool, scraped_codes: list[str]) -> list[str]:
        """
        Write the registry and its reports. Returns the written paths (relative).

        A partial scrape only writes its own raw file: it must neither
        overwrite the full dataset nor replace the master files.
        """
        written = []

        def write(path: Path, data) -> None:
            self._write(path, data)
            written.append(path.relative_to(self.dir).as_posix())

        if not complete:
            suffix = "_".join(self.short(c) for c in scraped_codes) or "teil"
            write(self.last_scrape_path.with_name(f"universities_{suffix}.json"), raw)
            return written

        write(self.last_scrape_path, raw)
        if not result.get("dedup"):
            return written

        p, run = self._pipeline, result["pipeline"]
        built, report = run["built"], run["dedup_report"]

        write(self.enriched_path, [r for r in run["records"] if not _is_international(r)])
        write(self.master_dir / "universities_dedup.json", run["institutions"])
        write(self.reports_dir / "dedup_report.json", report)
        write(self.reports_dir / "review_report.md", p.dedup.review_markdown(report))

        write(self.registry_path, built["universities"])
        write(self.master_dir / "university_metadata.json", built["metadata"])
        write(self.master_dir / "locations.json", built["locations"])
        write(self.master_dir / "aliases.json", built["aliases"])
        write(self.master_dir / "sources.json", built["sources"])
        write(self.id_registry_path, result["id_registry"].to_dict())
        write(self.reports_dir / "validation_report.json",
              p.build.quality_report(built, len(run["records"]), report))

        _, sql = self.import_script()
        write(self.master_dir / "supabase_import.sql", sql)
        return written

    # ------------------------------------------------------------------
    # database (registry.master.supabase_import)
    # ------------------------------------------------------------------

    def import_script(self) -> tuple[dict, str]:
        """(payload, SQL) of the saved master files, as the scraper's own import writes them."""
        if self._pipeline is None:
            raise RuntimeError("Diese Scraper-Version hat keinen Supabase-Import.")
        s = self._pipeline.supabase
        payload = s.build_payload(self.master_dir)
        source = self.registry_path.relative_to(self.dir).as_posix()
        return payload, s.render_sql(payload, source, s.git_commit())
