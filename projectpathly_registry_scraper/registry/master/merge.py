"""
Stage 2 — unify the schema of the state records and merge duplicate clusters.

Merging never drops information: every location, source and name variant of a
merged record is carried over, and `merged_from` lists the original records.
"""
from __future__ import annotations

from collections import Counter

import re

from .names import name_key, split_name
from .vocab import (
    map_institution_type, map_ownership, map_recognition, normalize_source,
)


_HOCHSCHULE_TERM = re.compile(r"hochschule|universit|university|fachhochschule", re.I)


def source_key(raw: dict) -> str:
    return f"{raw.get('state')}|{raw.get('name')}"


def unify_record(raw: dict) -> dict:
    """One state record -> record in the nationwide vocabulary."""
    state = raw.get("state")
    ownership = map_ownership(raw.get("ownership"))
    source = normalize_source(raw.get("source"), state)

    locations = []
    for loc in raw.get("locations", []):
        locations.append({
            "name": loc.get("name"),
            "city": loc.get("city"),
            "state": loc.get("state") or state,
            "postal_code": loc.get("postal_code"),
            "street": loc.get("street"),
            "location_type": loc.get("location_type") or "main",
            "source_state": state,
            "source_url": loc.get("source_url") or source["url"],
        })

    return {
        "source_key": source_key(raw),
        "name": raw["name"],
        "state": state,
        "institution_type": map_institution_type(raw.get("institution_type")),
        "ownership": ownership,
        "recognition_status": map_recognition(raw.get("recognition_status"), ownership),
        "official_url": raw.get("official_url"),
        "locations": locations,
        "sources": [source],
        "legacy": {
            "institution_type": raw.get("institution_type"),
            "ownership": raw.get("ownership"),
            "recognition_status": raw.get("recognition_status"),
        },
    }


def _is_placeholder(loc: dict) -> bool:
    return not any(loc.get(k) for k in ("name", "city", "postal_code", "street"))


def _loc_key(loc: dict) -> tuple:
    norm = lambda v: (v or "").strip().lower()
    return (norm(loc["name"]), norm(loc["city"]), norm(loc["postal_code"]),
            norm(loc["street"]), norm(loc["state"]))


def merge_locations(members: list[dict]) -> list[dict]:
    seen, out = {}, []
    for m in members:
        for loc in m["locations"]:
            k = _loc_key(loc)
            if k in seen:
                # Same place from two sources: keep both attributions.
                seen[k].setdefault("also_listed_by", [])
                if loc["source_state"] not in seen[k]["also_listed_by"] \
                        and loc["source_state"] != seen[k]["source_state"]:
                    seen[k]["also_listed_by"].append(loc["source_state"])
                continue
            loc = dict(loc)
            seen[k] = loc
            out.append(loc)

    # A placeholder ("state only", no address) is redundant once a real
    # location exists in the same state; otherwise it is kept.
    real_states = {l["state"] for l in out if not _is_placeholder(l)}
    return [l for l in out if not (_is_placeholder(l) and l["state"] in real_states)]


def _pick(members: list[dict], field: str, flags: list[str]) -> str:
    """Most frequently stated value; disagreement between sources is flagged."""
    values = Counter(m[field] for m in members if m[field] != "unknown")
    if not values:
        return "unknown"
    if len(values) > 1:
        flags.append(f"{field}_conflict: " + ", ".join(sorted(values)))
    return sorted(values, key=lambda v: (-values[v], v))[0]


def _information(m: dict) -> int:
    return sum([
        m["institution_type"] != "unknown",
        m["ownership"] != "unknown",
        m["recognition_status"] != "unknown",
        bool(m.get("official_url")),
    ])


def merge_cluster(members: list[dict]) -> dict:
    flags: list[str] = []

    # Canonical name: the cleaned name most sources agree on; then names that
    # say Hochschule/Universität; then the best-documented record.
    bases = Counter(name_key(split_name(m["name"])["base"]) for m in members)
    ranked = sorted(members, key=lambda m: (
        -bases[name_key(split_name(m["name"])["base"])],
        not _HOCHSCHULE_TERM.search(split_name(m["name"])["base"]),
        -_information(m),
        len(split_name(m["name"])["base"]),
        m["source_key"],
    ))
    name = split_name(ranked[0]["name"])["base"]

    variants = []
    for m in members:
        p = split_name(m["name"])
        for v in [m["name"], p["base"], *p["hints"]]:
            if v and v != name and v not in variants:
                variants.append(v)

    # "X - Fachbereich Y in Z" entries are departments of one institution:
    # the department becomes the name of that entry's location.
    located = []
    for m in members:
        p = split_name(m["name"])
        locs = [dict(l) for l in m["locations"]]
        if p["is_department"]:
            for loc in locs:
                loc["name"] = loc["name"] or p["tail"]
                loc["location_type"] = "department"
        located.append({**m, "locations": locs})
    locations = merge_locations(located)

    urls = Counter(m["official_url"] for m in members if m.get("official_url"))
    official_url = None
    if urls:
        # Prefer https, then the most frequently listed variant.
        official_url = sorted(urls, key=lambda u: (-urls[u], not u.startswith("https"), len(u)))[0]

    sources, seen = [], set()
    for m in members:
        for src in m["sources"]:
            k = (src["state"], src["url"], src["category"])
            if k not in seen:
                seen.add(k)
                sources.append(src)

    # A state belongs to a location, not to the institution: a multi-campus
    # Hochschule has no single state. `states` is derived from the locations,
    # `listed_by` says which state sources list the institution.
    return {
        "name": name,
        "name_variants": variants,
        "country": "DE",
        "institution_type": _pick(members, "institution_type", flags),
        "ownership": _pick(members, "ownership", flags),
        "recognition_status": _pick(members, "recognition_status", flags),
        "official_url": official_url,
        "states": sorted({l["state"] for l in locations if l["state"]}),
        "listed_by": sorted({m["state"] for m in members if m["state"]}),
        "locations": locations,
        "sources": sources,
        "merged_from": [
            {"source_key": m["source_key"], "name": m["name"], "state": m["state"],
             "legacy": m["legacy"]}
            for m in members
        ],
        "merge_flags": flags,
    }


def cluster(records: list[dict], candidates: list[dict]) -> list[list[dict]]:
    """Union-find over `auto_merge` pairs only."""
    parent = {r["source_key"]: r["source_key"] for r in records}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for c in candidates:
        if c["decision"] == "auto_merge":
            parent[find(c["a"])] = find(c["b"])

    groups: dict[str, list[dict]] = {}
    for r in records:
        groups.setdefault(find(r["source_key"]), []).append(r)
    return list(groups.values())
