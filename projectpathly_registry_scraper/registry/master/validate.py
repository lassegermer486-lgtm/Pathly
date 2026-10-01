"""
Stage 3 — validation of the merged registry.

Offline checks only flag; they never change facts. The optional web check
fetches each official website and records evidence (final URL, title,
lifecycle keywords) for a human to review.
"""
from __future__ import annotations

import re
import warnings
from concurrent.futures import ThreadPoolExecutor

from .names import root_domain

_DEPENDENT_UNIT = re.compile(
    r"\b(fachbereich|abteilung|außenstelle|aussenstelle|zweigstelle|studienzentrum|"
    r"studienort|standort|campus)\b", re.I)
_HOCHSCHULE_TERM = re.compile(
    r"hochschule|universit|university|fachhochschule|\bfh\b|\bhs\b|college|"
    r"business school|institut für technologie", re.I)
_NOT_A_HOCHSCHULE = re.compile(
    r"berufsakademie|fachschule|studienkolleg|\bkolleg\b|seminar\b|"
    r"berufsschule|volkshochschule", re.I)
# Deliberately phrase-based: single words like "geschlossen" appear on almost
# every site ("Bibliothek geschlossen") and would drown the real signals.
_LIFECYCLE_TEXT = re.compile(
    r"(wurde[n]? (in\s+\S+\s+)?umbenannt|umbenannt (in|zu)|neuer name|"
    r"hat sich (in|zu) .{0,40} umbenannt|"
    r"(fusion|fusioniert|verschmolzen|zusammengeschlossen) (mit|zur|zum|zu)|"
    r"studienbetrieb (wurde |wird )?(zum .{0,30})?eingestellt|"
    r"(hochschule|universität|fachhochschule) (wurde|wird) (geschlossen|aufgelöst|abgewickelt)|"
    r"(nachfolge(einrichtung|institution)|rechtsnachfolger)|"
    r"insolvenzverfahren|in liquidation|(closed|merged) (down )?(with|into)|has been renamed)",
    re.I)

def offline_checks(m: dict) -> list[dict]:
    flags = []

    def add(code, severity, detail=None):
        flags.append({"code": code, "severity": severity, "detail": detail})

    if not m.get("official_url"):
        add("missing_official_url", "high")
    if m["institution_type"] == "unknown":
        add("institution_type_unknown", "medium")
    if m["ownership"] == "unknown":
        stated = sorted({x["legacy"]["ownership"] for x in m["merged_from"]
                         if x["legacy"]["ownership"] not in (None, "unknown")})
        add("ownership_unresolved", "low",
            "source says: " + ", ".join(stated) if stated else "not stated by source")
    if m["recognition_status"] == "unknown":
        add("recognition_unverified", "medium")

    names = [m["name"], *m["name_variants"]]
    if any(_DEPENDENT_UNIT.search(n) for n in names):
        add("possibly_dependent_unit", "high", "name suggests a department/branch")
    if any(_NOT_A_HOCHSCHULE.search(n) for n in names):
        add("possibly_not_a_hochschule", "high", m["name"])
    elif not _HOCHSCHULE_TERM.search(m["name"]):
        add("name_without_hochschule_term", "low", m["name"])
    if re.search(r"\b(ehem\.?|ehemals|vormals|i\.\s?L\.)\b|in liquidation", " ".join(names), re.I):
        add("lifecycle_hint_in_name", "high", m["name"])

    for f in m.get("merge_flags", []):
        add("merge_" + f.split(":")[0], "medium", f)
    return flags


def cross_checks(masters: list[dict]) -> dict[str, list[dict]]:
    """Checks that need the whole registry (returned per university_id)."""
    out: dict[str, list[dict]] = {}
    by_root: dict[str, list[dict]] = {}
    for m in masters:
        r = root_domain(m.get("official_url"))
        if r:
            by_root.setdefault(r, []).append(m)
    for r, group in by_root.items():
        if len(group) > 1:
            for m in group:
                others = ", ".join(g["university_id"] for g in group if g is not m)
                out.setdefault(m["university_id"], []).append({
                    "code": "root_domain_shared", "severity": "medium",
                    "detail": f"{r} also used by {others}"})
    return out


# --------------------------------------------------------------------------
# Optional online check
# --------------------------------------------------------------------------

def fetch_evidence(url: str, timeout: int = 15) -> dict:
    import requests
    from bs4 import BeautifulSoup

    try:
        resp = requests.get(url, timeout=timeout, allow_redirects=True,
                            headers={"User-Agent": "ProjectPathlyRegistry/1.0 (+validation)"})
    except requests.RequestException as exc:
        return {"url": url, "error": type(exc).__name__}

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        soup = BeautifulSoup(resp.text[:400_000], "lxml")
    text = soup.get_text(" ", strip=True)
    snippets = []
    for hit in _LIFECYCLE_TEXT.finditer(text):
        snippet = text[max(0, hit.start() - 80): hit.end() + 80]
        if snippet not in snippets:
            snippets.append(snippet)
    return {
        "url": url,
        "status_code": resp.status_code,
        "final_url": resp.url,
        "title": (soup.title.string or "").strip() if soup.title else None,
        "lifecycle_snippets": snippets[:3],
    }


def web_checks(masters: list[dict], workers: int = 6) -> dict[str, list[dict]]:
    """Fetch every official website live (nothing is cached on disk)."""
    todo = [m for m in masters if m.get("official_url")]
    flags: dict[str, list[dict]] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for m, ev in zip(todo, pool.map(lambda m: fetch_evidence(m["official_url"]), todo)):
            m["web_evidence"] = ev
            f = flags.setdefault(m["university_id"], [])
            status = ev.get("status_code") or 0
            if ev.get("error") == "SSLError":
                f.append({"code": "website_tls_error", "severity": "medium", "detail": "SSLError"})
                continue
            if "error" in ev or status >= 500 or status in {404, 410}:
                f.append({"code": "website_unreachable", "severity": "high",
                          "detail": ev.get("error") or status})
                continue
            if status in {400, 401, 403, 429}:
                f.append({"code": "website_blocked_bot_protection", "severity": "low", "detail": status})
                continue
            if root_domain(ev["final_url"]) != root_domain(m["official_url"]):
                f.append({"code": "website_redirects_to_other_domain", "severity": "high",
                          "detail": ev["final_url"]})
            if ev["lifecycle_snippets"]:
                f.append({"code": "lifecycle_text_on_website", "severity": "medium",
                          "detail": " … ".join(ev["lifecycle_snippets"][:2])})
    return flags
