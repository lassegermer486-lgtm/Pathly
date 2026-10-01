"""
Stage 1 — find duplicate candidates. Nothing is merged or deleted here.

Every pair of records is scored on independent signals. Pairs whose signals are
strong enough are classified `auto_merge`; everything else that shows any
similarity is `review`.
"""
from __future__ import annotations

from .names import (
    GENERIC_TOKENS, core_tokens, head_class, host, name_key, root_domain,
    split_name, tokens,
)


def prepare(records: list[dict]) -> list[dict]:
    """Attach the comparison features to (schema-normalised) records."""
    places = set()
    for r in records:
        for loc in r["locations"]:
            places.update(tokens(loc.get("city") or ""))

    out = []
    for r in records:
        parts = split_name(r["name"])
        out.append({
            **r,
            "_base": parts["base"],
            "_parts": parts,
            "_key": name_key(parts["base"]),
            "_core": core_tokens(parts["base"]),
            "_head": head_class(parts["base"]),
            "_host": host(r.get("official_url")),
            "_root": root_domain(r.get("official_url")),
            "_places": places,
            "_addresses": {
                (loc.get("postal_code"), (loc.get("street") or "").lower())
                for loc in r["locations"]
                if loc.get("postal_code") and loc.get("street")
            },
        })
    return out


def _types_compatible(a: dict, b: dict) -> bool:
    ta, tb = a["institution_type"], b["institution_type"]
    return ta == tb or "unknown" in (ta, tb)


def _name_variant(a: dict, b: dict) -> set[str]:
    """
    One name contains the other plus only place words ("SRH Hochschule
    Heidelberg" / "... in Gera"). Returns the shared distinctive tokens, or an
    empty set. Shared generic words ("Evangelische", "Technik und Wirtschaft")
    are no evidence at all: many unrelated institutions carry them.
    """
    ca, cb = a["_core"], b["_core"]
    if not ca or not cb or a["_head"] != b["_head"]:
        return set()
    small, large = (ca, cb) if len(ca) <= len(cb) else (cb, ca)
    if not small <= large or not (large - small) <= a["_places"]:
        return set()
    return set(small - GENERIC_TOKENS - a["_places"])


def compare(a: dict, b: dict) -> dict | None:
    distinctive = _name_variant(a, b)
    signals = {
        "domain_exact": bool(a["_host"] and a["_host"] == b["_host"]),
        "domain_root": bool(a["_root"] and a["_root"] == b["_root"]),
        "name_identical": a["_key"] == b["_key"],
        "name_variant": bool(distinctive),
        "shared_core_token": bool(a["_core"] & b["_core"]),
        "department_pattern": a["_parts"]["is_department"] or b["_parts"]["is_department"],
        "address_overlap": bool(a["_addresses"] & b["_addresses"]),
        "cross_state": a["state"] != b["state"],
        "types_compatible": _types_compatible(a, b),
        "domain_conflict": bool(a["_root"] and b["_root"] and a["_root"] != b["_root"]),
    }

    s = signals
    if not (s["domain_root"] or s["name_identical"] or s["name_variant"] or s["address_overlap"]):
        return None

    reasons = []
    decision = "review"

    # Identity needs an independent, hard-to-fake signal: the same website.
    # A name alone is only enough when it is literally identical, listed by
    # different states and nothing contradicts it.
    if s["domain_exact"] and (
        s["name_identical"] or s["name_variant"] or s["shared_core_token"] or s["department_pattern"]
    ):
        decision = "auto_merge"
        reasons.append("same website host and related names")
    elif s["name_identical"] and not s["domain_conflict"] and s["cross_state"] and s["types_compatible"]:
        decision = "auto_merge"
        reasons.append("identical name in different state lists, no conflicting website")
    else:
        if s["domain_exact"]:
            reasons.append("same website host but names differ")
        elif s["domain_root"]:
            reasons.append("same root domain, different host")
        if s["name_identical"]:
            reasons.append("identical name but " + (
                "different websites" if s["domain_conflict"]
                else "same state" if not s["cross_state"]
                else "incompatible institution types"))
        elif s["name_variant"]:
            reasons.append(
                "one name contains the other plus place/legal words "
                f"(shared distinctive name: {', '.join(sorted(distinctive))})")
        if s["address_overlap"]:
            reasons.append("shared street address")

    return {
        "a": a["source_key"],
        "b": b["source_key"],
        "decision": decision,
        "reasons": reasons,
        "signals": {k: v for k, v in s.items() if v},
    }


def find_candidates(records: list[dict], overrides: dict | None = None) -> list[dict]:
    overrides = overrides or {}
    forced_merge = {frozenset(p) for p in overrides.get("merge", [])}
    keep_separate = {frozenset(p) for p in overrides.get("keep_separate", [])}

    recs = prepare(records)
    found = []
    for i in range(len(recs)):
        for j in range(i + 1, len(recs)):
            pair = frozenset((recs[i]["source_key"], recs[j]["source_key"]))
            if pair in keep_separate:
                continue
            c = compare(recs[i], recs[j])
            if pair in forced_merge:
                c = c or {"a": recs[i]["source_key"], "b": recs[j]["source_key"],
                          "reasons": [], "signals": {}}
                c["decision"] = "auto_merge"
                c["reasons"].append("confirmed in overrides.yaml")
            if c:
                found.append(c)
    return found
