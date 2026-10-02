"""
Build overview for the UI, read from the pipeline's own reports.

The scraper's report files are the source of truth (registry_run.json,
build_status.json, international_build_status.json, url_resolution*.json,
agent_resolution*.json, dedup_report.json, presence_validation.json,
online_de_validation.json, validation_report.json, supabase_export.json).
This module only reads and arranges them: no status is computed here that
the CLI does not state itself. Missing files mean "not run yet".
"""
from __future__ import annotations

import json
from pathlib import Path

REPORTS = {
    "registry_run": "data/reports/registry_run.json",
    "build_status": "data/reports/build_status.json",
    "intl_status": "data/reports/international_build_status.json",
    "intl_discovery": "data/reports/international_online_discovery.json",
    "url_de": "data/reports/url_resolution.json",
    "url_intl": "data/reports/url_resolution_intl.json",
    "agent_de": "data/reports/agent_resolution.json",
    "agent_intl": "data/reports/agent_resolution_intl.json",
    "dedup": "data/reports/dedup_report.json",
    "presence": "data/reports/presence_validation.json",
    "online_de": "data/reports/online_de_validation.json",
    "validation": "data/reports/validation_report.json",
    "supabase": "data/reports/supabase_export.json",
}

# The nine steps shown in the UI and the reports each one is built from.
STEPS = [
    ("german_discovery", "Deutsche Discovery", ["registry_run", "build_status"]),
    ("international_discovery", "Internationale Discovery", ["intl_status", "intl_discovery"]),
    ("websites", "Website-Prüfung", ["url_de", "url_intl"]),
    ("agent", "Agent-Auflösung", ["agent_de", "agent_intl"]),
    ("dedup", "Deduplizierung", ["dedup"]),
    ("presence", "Präsenz in Deutschland", ["presence"]),
    ("online_de", "Online aus Deutschland", ["online_de"]),
    ("master", "Master-Register", ["validation"]),
    ("supabase", "Supabase-Export", ["supabase"]),
]

# Which CLI pipeline step (registry.pipeline) produces which UI step.
CLI_STEP_TO_UI = {
    "discovery": ["german_discovery"],
    "international": ["international_discovery"],
    "websites": ["websites"],
    "websites_intl": ["websites"],
    "agent": ["agent"],
    "agent_intl": ["agent"],
    "dedup": ["dedup"],
    "master": ["presence", "online_de", "master"],
    "supabase": ["supabase"],
}

STATUS_RANK = {"failed": 0, "degraded": 1, "review": 2, "complete": 3}


class ReportCache:
    """Parsed report files, re-read only when a file changes."""

    def __init__(self, scraper_dir: Path):
        self.dir = Path(scraper_dir)
        self._cache: dict[str, tuple[float, object]] = {}

    def load(self) -> dict:
        out = {}
        for key, rel in REPORTS.items():
            path = self.dir / rel
            try:
                mtime = path.stat().st_mtime
            except FileNotFoundError:
                out[key] = None
                continue
            cached = self._cache.get(key)
            if cached and cached[0] == mtime:
                out[key] = cached[1]
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = None
            self._cache[key] = (mtime, data)
            out[key] = data
        return out


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------

def _generated(report) -> str | None:
    return report.get("generated_at") if isinstance(report, dict) else None


def _state_entries(r: dict) -> list[dict]:
    """German state entries: v1.3 fields from build_status.json, v1.2 fallback from registry_run.json."""
    status = r.get("build_status") or {}
    if status.get("states"):
        return status["states"]
    out = []
    for e in r.get("registry_run") or []:
        ok = e.get("status") == "OK" and (e.get("universities") or 0) > 0
        out.append({**e, "source_status": e.get("source_status") or ("success" if ok else "failed"),
                    "current_count": e.get("current_count", e.get("universities"))})
    return out


def _intl_entries(r: dict) -> list[dict]:
    return (r.get("intl_status") or {}).get("states") or []


def _drift(entries: list[dict]) -> list[dict]:
    return [e for e in entries if e.get("count_status") == "suspicious" and not e.get("drift_accepted")]


# ----------------------------------------------------------------------
# header
# ----------------------------------------------------------------------

def header(r: dict) -> dict:
    statuses = [s for s in (r.get("build_status"), r.get("intl_status")) if s]
    if statuses:
        worst = min(statuses, key=lambda s: STATUS_RANK.get(s.get("build_status"), -1))
        build_status = worst.get("build_status", "unknown")
        # Without the German status (data from before v1.3) safety is unknown.
        safe = all(s.get("production_safe") for s in statuses) if r.get("build_status") else None
    else:
        build_status, safe = "unknown", None

    german, intl = _state_entries(r), _intl_entries(r)
    sources = german + intl
    ok = sum(1 for e in sources if e.get("source_status") == "success")
    expected = ((r.get("build_status") or {}).get("states_expected") or len(german)) + \
               ((r.get("intl_status") or {}).get("states_expected") or len(intl))

    reviews = review_groups(r)
    decision_needed = sum(len(g["items"]) for g in reviews if g["id"] not in ("online_de", "flags"))
    online = next((g for g in reviews if g["id"] == "online_de"), {"items": []})

    return {
        "build_status": build_status,
        "production_safe": safe,
        "sources_ok": ok,
        "sources_total": expected,
        "institutions": (r.get("validation") or {}).get("master_universities"),
        "review": decision_needed,
        "online_de_candidates": len(online["items"]),
        "drift": len(_drift(sources)),
        "errors": sum(1 for e in sources if e.get("source_status") == "failed"),
        "stable_ids": (r.get("validation") or {}).get("stable_ids"),
    }


# ----------------------------------------------------------------------
# steps
# ----------------------------------------------------------------------

def _step_german(r):
    entries = _state_entries(r)
    if not entries:
        return None
    ok = sum(1 for e in entries if e.get("source_status") == "success")
    failed = [e["state"] for e in entries if e.get("source_status") == "failed"]
    lines = [
        ["Quellen", f"{ok} / {len(entries)}"],
        ["Beobachtungen", sum(e.get("universities") or e.get("current_count") or 0
                              for e in (r.get("registry_run") or entries))],
        ["Standorte", sum(e.get("locations") or 0 for e in (r.get("registry_run") or []))],
    ]
    if failed:
        lines.append(["Fehlgeschlagen", ", ".join(failed)])
    drift = _drift(entries)
    if drift:
        lines.append(["Drift", ", ".join(e["state"] for e in drift)])
    status = "failed" if failed else ("warning" if drift else "done")
    return status, lines


def _step_international(r):
    entries = _intl_entries(r)
    if not entries:
        return None
    lines = []
    for e in entries:
        mark = "✓" if e.get("source_status") == "success" else "✗"
        lines.append([e["state"].replace("INTL-", ""), f"{mark} {e.get('current_count') or 0} Kandidaten"])
    lines.append(["Gesamt", f"{sum(e.get('current_count') or 0 for e in entries)} Kandidaten"])
    failed = any(e.get("source_status") != "success" for e in entries)
    return ("failed" if failed else ("warning" if _drift(entries) else "done")), lines


def _step_websites(r):
    parts = [(lbl, r.get(k)) for lbl, k in (("deutsch", "url_de"), ("international", "url_intl")) if r.get(k)]
    if not parts:
        return None
    lines, open_total = [], 0
    for lbl, rep in parts:
        by = rep.get("by_status") or {}
        resolved, checked = by.get("resolved", 0), rep.get("checked") or 0
        open_n = checked - resolved
        open_total += open_n
        pct = f" ({100 * resolved / checked:.1f} %)".replace(".", ",") if checked else ""
        lines.append([lbl, f"{resolved} / {checked} bestätigt{pct}"])
        if open_n:
            lines.append(["", f"{by.get('review', 0)} Review, {by.get('unresolved', 0)} offen"])
    return ("warning" if open_total else "done"), lines


def _step_agent(r):
    parts = [(lbl, r.get(k)) for lbl, k in (("deutsch", "agent_de"), ("international", "agent_intl")) if r.get(k)]
    if not parts:
        return None
    lines = [[lbl, f"{rep.get('asked', 0)} gefragt, {rep.get('accepted', 0)} übernommen"] for lbl, rep in parts]
    return "done", lines


def _step_dedup(r):
    d = r.get("dedup")
    if not d:
        return None
    lines = [
        ["Quelldatensätze", d.get("source_records")],
        ["Hochschulen", d.get("institutions")],
        ["Zusammengeführt", f"{d.get('records_merged_away', 0)} Datensätze in {d.get('merged_institutions', 0)} Gruppen"],
        ["Review", d.get("review_cases", 0)],
    ]
    if d.get("conflicts"):
        lines.append(["Konflikte", len(d["conflicts"])])
    return ("warning" if d.get("review_cases") or d.get("conflicts") else "done"), lines


def _step_presence(r):
    p = r.get("presence")
    if not p:
        return None
    c = p.get("counts") or {}
    lines = [
        ["Bestätigt", c.get("confirmed", 0)],
        ["Zu prüfen", c.get("review", 0)],
        ["Nicht mehr in DE (geprüft)", c.get("not_present", 0)],
    ]
    if c.get("no_german_source_listing"):
        lines.append(["Ohne deutsche Quelle (offen)", c["no_german_source_listing"]])
    if p.get("decision_warnings"):
        lines.append(["Warnungen", len(p["decision_warnings"])])
    return ("warning" if c.get("review") or p.get("decision_warnings") else "done"), lines


def _step_online(r):
    o = r.get("online_de")
    if not o:
        return None
    c = o.get("counts") or {}
    discovered = len((r.get("intl_discovery") or {}).get("candidates") or [])
    lines = [
        ["Entdeckt", discovered],
        ["Bestätigt", c.get("confirmed", 0)],
        ["Review", c.get("review", 0)],
        ["Nicht verfügbar", c.get("not_available", 0)],
    ]
    if o.get("decision_warnings"):
        lines.append(["Warnungen", len(o["decision_warnings"])])
    return ("warning" if o.get("decision_warnings") else "done"), lines


def _step_master(r):
    v = r.get("validation")
    if not v:
        return None
    lines = [["Hochschulen", v.get("master_universities")]]
    ids = v.get("stable_ids")
    if ids:
        lines.append(["Bestehende IDs erhalten", f"{ids['kept']} / {ids['existing']}"])
        lines.append(["Neue IDs", ids["new"]])
    if v.get("market_access"):
        a = v["market_access"]
        lines.append(["Marktzugang", f"{a.get('physical_de', 0)} physisch, {a.get('online_de', 0)} online, "
                                     f"{a.get('both', 0)} beides"])
    header_info = header(r)
    lines.append(["Production safe", {True: "ja", False: "nein", None: "–"}[header_info["production_safe"]]])
    if v.get("core_field_violations"):
        lines.append(["Pflichtfelder verletzt", len(v["core_field_violations"])])
    bad = (ids and not ids.get("all_existing_kept")) or v.get("core_field_violations")
    return ("warning" if bad or header_info["production_safe"] is False else "done"), lines


def _step_supabase(r):
    s = r.get("supabase")
    if not s:
        return None
    c = s.get("counts") or {}
    lines = [["Datei", s.get("output")], ["Hochschulen", c.get("universities")],
             ["Standorte", c.get("locations")], ["Quellen", c.get("sources")]]
    return "done", lines


STEP_BUILDERS = {
    "german_discovery": _step_german, "international_discovery": _step_international,
    "websites": _step_websites, "agent": _step_agent, "dedup": _step_dedup,
    "presence": _step_presence, "online_de": _step_online, "master": _step_master,
    "supabase": _step_supabase,
}


def steps(r: dict) -> list[dict]:
    out, previous_time = [], None
    for number, (sid, title, keys) in enumerate(STEPS, start=1):
        built = STEP_BUILDERS[sid](r)
        times = [t for t in (_generated(r.get(k)) for k in keys) if t]
        generated = max(times) if times else None
        if built is None:
            status, lines = "pending", []
        else:
            status, lines = built
        # A step older than the one before was not re-run after it.
        stale = bool(generated and previous_time and generated < previous_time)
        out.append({"id": sid, "number": number, "title": title, "status": status,
                    "lines": lines, "generated_at": generated, "stale": stale})
        if generated:
            previous_time = generated
    return out


# ----------------------------------------------------------------------
# sources and reviews
# ----------------------------------------------------------------------

SOURCE_KEYS = ("state", "name", "status", "source_status", "failure_reason", "previous_count",
               "current_count", "absolute_delta", "relative_delta", "count_status",
               "drift_accepted", "request_attempts", "request_retries")


def sources(r: dict) -> list[dict]:
    names = {e.get("state"): e.get("name") for e in (r.get("registry_run") or [])}
    names.update({e.get("state"): e.get("name") for e in ((r.get("intl_discovery") or {}).get("sources") or [])})
    out = []
    for kind, entries in (("de", _state_entries(r)), ("international", _intl_entries(r))):
        for e in entries:
            row = {k: e.get(k) for k in SOURCE_KEYS}
            row["name"] = row["name"] or names.get(e.get("state"))
            row["kind"] = kind
            out.append(row)
    return out


WEBSITE_FLAGS = {"missing_website", "website_identity_unconfirmed", "website_unverifiable",
                 "tls_certificate_unverified", "possible_rename_or_merger"}


def review_groups(r: dict) -> list[dict]:
    """Every open review case, grouped by the reason it is open."""
    groups = []

    def add(gid, title, explanation, items):
        groups.append({"id": gid, "title": title, "explanation": explanation, "items": items})

    srcs = _state_entries(r) + _intl_entries(r)
    add("drift", "Count-Drift", "Anzahl einer Quelle weicht stark vom letzten bestätigten Stand ab "
        "(mehr als ±10 oder ±30 %). Prüfen, dann python -m registry.reliability --accept-drift <QUELLE>.",
        [{"key": e["state"], "title": e["state"],
          "reasons": [f"{e.get('previous_count')} → {e.get('current_count')} "
                      f"({e.get('absolute_delta'):+d}, {(e.get('relative_delta') or 0) * 100:+.1f} %)"]}
         for e in _drift(srcs)])

    add("source", "Quelle fehlgeschlagen", "Ohne diese Quelle ist der Build nicht produktionssicher.",
        [{"key": e["state"], "title": e["state"], "reasons": [e.get("failure_reason") or "fehlgeschlagen"]}
         for e in srcs if e.get("source_status") == "failed"])

    website = []
    for kind, key in (("deutsch", "url_de"), ("international", "url_intl")):
        rep = r.get(key) or {}
        for item in (rep.get("review") or []) + (rep.get("unresolved") or []):
            reasons = item.get("flags") or item.get("reasons") or []
            website.append({"key": f"{item.get('state')}|{item.get('name')}",
                            "title": item.get("name"), "subtitle": f"{item.get('state')} · {kind}",
                            "url": item.get("official_url") or item.get("suggested_url") or item.get("source_url"),
                            "reasons": list(dict.fromkeys([item.get("status") or "review", *reasons]))})
    add("website", "Website", "Die offizielle Website ist nicht bestätigt (Impressum oder Titel nennt "
        "die Hochschule nicht, Seite blockiert oder nicht erreichbar).", website)

    d = r.get("dedup") or {}
    add("dedup", "Duplikate", "Mögliche Dubletten; Entscheidung in overrides.yaml "
        "(Ansicht „Bundesländer & Duplikate“).",
        [{"key": f"{p.get('a')}↔{p.get('b')}", "title": f"{p.get('a')} ↔ {p.get('b')}",
          "reasons": [p.get("rule")] + ([", ".join(p["evidence"]) if isinstance(p.get("evidence"), list)
                                        else p["evidence"]] if p.get("evidence") else [])}
         for p in d.get("review") or []]
        + [{"key": f"conflict:{c.get('a')}↔{c.get('b')}", "title": f"{c.get('a')} ↔ {c.get('b')}",
            "reasons": ["Konflikt: " + str(c.get("reason"))]} for c in d.get("conflicts") or []])

    p = r.get("presence") or {}
    add("presence", "Präsenz in Deutschland", "Deutsche Beobachtungen ohne ausreichenden Beleg; "
        "Entscheidung in presence_decisions.yaml (mit evidence_url).",
        [{"key": e["registry_id"], "title": e["name"], "subtitle": e["registry_id"], "url": e.get("official_url"),
          "reasons": [x.get("detail") or x.get("code") for x in e.get("doubts") or []]
          or [o.get("basis") for o in e.get("observations") or []]}
         for e in p.get("review") or []]
        + [{"key": f"warn:{w.get('registry_id')}", "title": str(w.get("registry_id")),
            "reasons": ["Entscheidung ungültig: " + w["problem"]]} for w in p.get("decision_warnings") or []])

    o = r.get("online_de") or {}
    add("online_de", "Online aus Deutschland", "Discovery-Kandidaten (ETER/IPEDS). Bestätigt wird nur "
        "mit zwei offiziellen Belegen in online_de_decisions.yaml.",
        [{"key": e["registry_id"], "title": e["name"], "subtitle": f"{e.get('country')} · {e['registry_id']}",
          "url": e.get("official_url"), "reasons": [", ".join(e.get("discovery_sources") or []) or "review"]}
         for e in o.get("review") or []]
        + [{"key": f"warn:{w.get('registry_id')}", "title": str(w.get("registry_id")),
            "reasons": ["Entscheidung ungültig: " + w["problem"]]} for w in o.get("decision_warnings") or []])

    v = r.get("validation") or {}
    add("flags", "Hinweise im Register", "Hochschulen mit Hinweisen mittlerer oder hoher Schwere "
        "(validation_report.json); keine Entscheidung zwingend.",
        [{"key": e["registry_id"], "title": e["name"], "subtitle": e["registry_id"], "url": e.get("official_url"),
          "reasons": [f"{f.get('code')}" + (f": {f['detail']}" if f.get("detail") else "") for f in e.get("flags") or []]}
         for e in v.get("review_required") or []])
    return groups


def overview(cache: ReportCache) -> dict:
    r = cache.load()
    return {
        "header": header(r),
        "steps": steps(r),
        "sources": sources(r),
        "reviews": review_groups(r),
        "reports": {k: _generated(v) if isinstance(v, dict) else (bool(v) or None) for k, v in r.items()},
    }


def live_steps(process: dict) -> dict:
    """
    UI step -> "running" / "waiting" / "done" for the pipeline process that
    runs now or ran last (from its command and the steps it reported).
    """
    command = process.get("command") or []
    if "registry.pipeline" not in command:
        return {}
    cli = list(CLI_STEP_TO_UI)

    def arg(flag, default):
        return command[command.index(flag) + 1] if flag in command else default

    start, stop = arg("--from", cli[0]), arg("--to", cli[-1])
    if start not in cli or stop not in cli:
        return {}
    planned = cli[cli.index(start): cli.index(stop) + 1]

    out = {}
    for name in planned:
        for ui in CLI_STEP_TO_UI[name]:
            out.setdefault(ui, "waiting" if process.get("running") else "not_reached")
    for name in process.get("steps_done") or []:
        for ui in CLI_STEP_TO_UI.get(name, []):
            out[ui] = "done"
    current = process.get("step")
    if current:
        for ui in CLI_STEP_TO_UI.get(current, []):
            out[ui] = "running"
    return out
