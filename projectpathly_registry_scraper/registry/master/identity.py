"""
Stable university_id assignment.

An id is created once and then persisted in an id registry file. On later runs
a record keeps its id if it still matches any known source key or website host
(so renames, re-scrapes and merges do not change ids). Ids are never reused.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .names import host, name_key, split_name


def _new_id(seed: str, taken: set[str]) -> str:
    n = 0
    while True:
        digest = hashlib.sha1(f"{seed}#{n}".encode()).hexdigest()[:8].upper()
        uid = f"PTH-DE-{digest}"
        if uid not in taken:
            return uid
        n += 1


def load(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"version": 1, "entries": {}}


def save(path: Path, registry: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True),
                    encoding="utf-8")


def assign_ids(masters: list[dict], registry: dict) -> list[str]:
    """Set `university_id` on every master record. Returns warnings."""
    entries = registry["entries"]
    by_key: dict[str, str] = {}
    by_host: dict[str, str] = {}
    for uid, e in entries.items():
        for k in e["source_keys"]:
            by_key[k] = uid
        for h in e["hosts"]:
            by_host[h] = uid

    warnings, used = [], set()
    for m in masters:
        keys = [x["source_key"] for x in m["merged_from"]]
        h = host(m.get("official_url"))
        hits = {by_key[k] for k in keys if k in by_key}
        if not hits and h and h in by_host:
            hits = {by_host[h]}

        # Two previously separate ids now describe one record -> keep the
        # oldest, remember the other as an alias so old references resolve.
        hits = sorted(hits, key=lambda u: entries[u]["created"])
        available = [u for u in hits if u not in used]
        if available:
            uid = available[0]
            for other in hits[1:]:
                entries[uid].setdefault("aliases", [])
                if other not in entries[uid]["aliases"]:
                    entries[uid]["aliases"].append(other)
                warnings.append(f"{uid} absorbed previously separate id {other}")
        else:
            seed = f"{name_key(split_name(m['name'])['base'])}|{h or ''}"
            uid = _new_id(seed, set(entries) | used)
            entries[uid] = {"created": len(entries), "source_keys": [], "hosts": []}
            if hits:
                warnings.append(f"{m['name']}: matched id already used by another record; new id {uid}")

        e = entries[uid]
        e["name"] = m["name"]
        e["source_keys"] = sorted(set(e["source_keys"]) | set(keys))
        if h and h not in e["hosts"]:
            e["hosts"] = sorted(set(e["hosts"]) | {h})
        used.add(uid)
        m["university_id"] = uid
    return warnings
