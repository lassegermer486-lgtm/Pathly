"""
python -m registry.master [--states NRW HH] [--input FILE] [--candidates-only]
                          [--online] [--list] [--json] [--save]

Builds the ProjectPathly Master University Registry: bundesweite Dedup,
einheitliches Schema, Validierung, stabile university_id.

By default everything runs in memory and is printed to the terminal:
the states are scraped live (or read from --input) and nothing is written.
--save writes the registry, the reports and the id registry.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

from registry.states import short

from . import identity
from .candidates import find_candidates
from .merge import cluster, merge_cluster, unify_record
from .validate import cross_checks, offline_checks, web_checks

CONFIG_DIR = Path("config")
OVERRIDES = CONFIG_DIR / "overrides.yaml"
ID_REGISTRY = CONFIG_DIR / "id_registry.json"


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _review_markdown(review: list[dict], names: dict[str, str]) -> str:
    lines = [
        "# Dedup review report", "",
        f"{len(review)} pairs need a human decision. Resolve them in "
        f"`{OVERRIDES}` (`merge` / `keep_separate`).", "",
    ]
    for c in review:
        lines += [
            f"## {names[c['a']]}  ↔  {names[c['b']]}",
            f"- `{c['a']}`", f"- `{c['b']}`",
            f"- why: {'; '.join(c['reasons'])}", "",
        ]
    return "\n".join(lines)


def load_state_records(args, log) -> list[dict]:
    if args.input:
        log(f"[INPUT] {args.input}")
        return json.loads(Path(args.input).read_text(encoding="utf-8"))

    from registry.run import load_config, parse_states, scrape

    log("[INPUT] live scrape")
    # Adapter progress goes to stderr so stdout stays clean for --json.
    with contextlib.redirect_stdout(sys.stderr):
        rows, report = scrape(parse_states(args.states), load_config(), log=log)
    failed = [r["state"] for r in report if r["status"] == "ERROR"]
    if failed:
        log(f"[WARN]  scrape failed for: {', '.join(short(s) for s in failed)} — "
            "registry is incomplete")
    return rows


def _states_label(codes: list[str]) -> str:
    return ",".join(short(c) for c in codes)


def print_candidates(candidates: list[dict], names: dict[str, str], log) -> None:
    review = [c for c in candidates if c["decision"] == "review"]
    log("")
    log(f"REVIEW ({len(review)}) — decide in {OVERRIDES}")
    for c in review:
        log(f"  {c['a']}")
        log(f"  {c['b']}")
        log(f"    → {'; '.join(c['reasons'])}")


def print_merges(masters: list[dict], log) -> None:
    merged = [m for m in masters if len(m["merged_from"]) > 1]
    log("")
    log(f"MERGED ({len(merged)} institutions from "
        f"{sum(len(m['merged_from']) for m in merged)} state records)")
    for m in merged:
        log(f"  {m['university_id']}  {m['name']}  [{_states_label(m['states'])}]  "
            f"{len(m['locations'])} locations")
        for x in m["merged_from"]:
            log(f"      ← {x['source_key']}")


def print_table(masters: list[dict], log) -> None:
    log("")
    log(f"{'ID':<16} {'NAME':<55} {'TYPE':<30} {'OWNER':<8} {'RECOGNITION':<16} STATES")
    for m in masters:
        log(f"{m['university_id']:<16} {m['name'][:55]:<55} {m['institution_type']:<30} "
            f"{m['ownership']:<8} {m['recognition_status']:<16} {_states_label(m['states'])}")


def main():
    p = argparse.ArgumentParser(description="Build the ProjectPathly master registry")
    p.add_argument("--states", nargs="+", default=None,
                   help="only these states, e.g. NRW HH (default: all 16)")
    p.add_argument("--input", help="use a saved state scrape instead of scraping live")
    p.add_argument("--candidates-only", action="store_true",
                   help="detect duplicate candidates only; merge nothing")
    p.add_argument("--online", action="store_true",
                   help="also fetch every official website as validation evidence")
    p.add_argument("--list", action="store_true", help="print every master record")
    p.add_argument("--json", action="store_true",
                   help="print the full registry as JSON to stdout (log goes to stderr)")
    p.add_argument("--save", action="store_true",
                   help="write registry, reports and id registry")
    args = p.parse_args()

    log = (lambda msg: print(msg, file=sys.stderr)) if args.json else print

    raw = load_state_records(args, log)
    records = [unify_record(r) for r in raw]
    names = {r["source_key"]: r["name"] for r in records}

    overrides = (yaml.safe_load(OVERRIDES.read_text(encoding="utf-8")) or {}) \
        if OVERRIDES.exists() else {}

    # Overrides refer to names as scraped; a renamed source entry would make
    # a decision silently ineffective, so report every key that matches nothing.
    known = set(names)
    for section in ("merge", "keep_separate"):
        for pair in overrides.get(section) or []:
            for key in pair:
                if key not in known and (args.states is None or args.input):
                    log(f"[WARN]  {OVERRIDES} {section}: '{key}' matches no scraped record")

    # ---- 1. candidates -------------------------------------------------
    candidates = find_candidates(records, overrides)
    n_auto = sum(c["decision"] == "auto_merge" for c in candidates)
    review = [c for c in candidates if c["decision"] == "review"]
    log("")
    log(f"[CANDIDATES] {len(candidates)} pairs: {n_auto} auto_merge, {len(review)} review")
    print_candidates(candidates, names, log)

    if args.candidates_only:
        if args.json:
            print(json.dumps(candidates, ensure_ascii=False, indent=2))
        if args.save:
            _write_json(Path("data/reports/dedup_candidates.json"), candidates)
            log("[SAVED] data/reports/dedup_candidates.json")
        return

    # ---- 2. merge + schema --------------------------------------------
    masters = [merge_cluster(g) for g in cluster(records, candidates)]
    masters.sort(key=lambda m: (m["states"][:1], m["name"]))

    id_registry = identity.load(ID_REGISTRY)
    id_warnings = identity.assign_ids(masters, id_registry)

    # ---- 3. validation --------------------------------------------------
    extra = cross_checks(masters)
    web = web_checks(masters) if args.online else {}
    per_record = overrides.get("records") or {}
    for m in masters:
        m["lifecycle_status"] = "unknown"
        m.update(per_record.get(m["university_id"], {}))
        m["validation_flags"] = (offline_checks(m)
                                 + extra.get(m["university_id"], [])
                                 + web.get(m["university_id"], []))

    print_merges(masters, log)
    if args.list:
        print_table(masters, log)

    summary = {
        "input_records": len(records),
        "master_records": len(masters),
        "auto_merge_pairs": n_auto,
        "review_pairs": len(review),
        "id_warnings": id_warnings,
        "flag_counts": dict(Counter(f["code"] for m in masters for f in m["validation_flags"])),
        "by_type": dict(Counter(m["institution_type"] for m in masters)),
        "by_ownership": dict(Counter(m["ownership"] for m in masters)),
        "by_recognition": dict(Counter(m["recognition_status"] for m in masters)),
    }

    log("")
    log("-" * 62)
    log(f"STATE RECORDS:  {len(records)}")
    log(f"INSTITUTIONS:   {len(masters)}  ({len(records) - len(masters)} merged)")
    log(f"REVIEW PAIRS:   {len(review)}")
    for key in ("by_type", "by_ownership", "by_recognition"):
        log(f"{key.upper().replace('BY_', '') + ':':<16}"
            + ", ".join(f"{k} {v}" for k, v in sorted(summary[key].items(), key=lambda kv: -kv[1])))
    log("FLAGS:          " + ", ".join(
        f"{k} {v}" for k, v in sorted(summary["flag_counts"].items(), key=lambda kv: -kv[1])))
    for w in id_warnings:
        log(f"[ID]  {w}")

    if args.json:
        print(json.dumps(masters, ensure_ascii=False, indent=2))

    if args.save:
        _write_json(Path("data/master/university_registry.json"), masters)
        _write_json(Path("data/reports/dedup_candidates.json"), candidates)
        Path("data/reports/dedup_review.md").write_text(
            _review_markdown(review, names), encoding="utf-8")
        _write_json(Path("data/reports/master_summary.json"), summary)
        identity.save(ID_REGISTRY, id_registry)
        log("SAVED:          data/master/university_registry.json, data/reports/, "
            f"{ID_REGISTRY}")
    else:
        log("SAVED:          nothing (use --save)")
    log("-" * 62)


if __name__ == "__main__":
    main()
