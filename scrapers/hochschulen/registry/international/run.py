"""
International online discovery.

    python -m registry.international.run
    python -m registry.international.run --sources INTL-ETER

Writes
    data/normalized/universities_intl.json              candidates (normalized records)
    data/reports/international_online_discovery.json    per source: filter counts, candidates, signals
    data/reports/international_build_status.json        like build_status.json (reliability)

The German discovery output (universities_de.json) is not touched.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from registry import http_client, reliability

from . import eter, ipeds
from .base import now, validate


ADAPTERS = {"eter": eter.discover, "ipeds": ipeds.discover}

SOURCES_PATH = Path("registry/international_sources.yaml")
OUTPUT_PATH = reliability.INTL_NORMALIZED_PATH
REPORT_PATH = Path("data/reports/international_online_discovery.json")


def run(config: dict, sources: list[str], out: Path = OUTPUT_PATH, report_path: Path = REPORT_PATH,
        status_path: Path = reliability.INTL_BUILD_STATUS_PATH, cache_root=None) -> dict:
    previous_counts = reliability.load_state_counts()
    expected = [s for s, c in config.items() if c.get("enabled", True)]

    records, entries, details = [], [], {}

    for source in sources:
        cfg = config.get(source)
        if cfg is None:
            entries.append({"state": source, "status": "ERROR", "error": "missing_config"})
            continue
        if not cfg.get("enabled", True):
            entries.append({"state": source, "status": "SKIPPED"})
            continue

        print(f"\n[FETCH] {source} — {cfg['name']}")
        http_client.STATS.reset()

        try:
            found, detail = ADAPTERS[cfg["adapter"]](source, cfg, cache_root=cache_root)
            invalid = validate(found)
            records.extend(found)
            details[source] = {**detail, "validation_issues": invalid}
            print(f"[OK] {source}: {len(found)} candidates ({detail.get('obtained')})")
            entries.append({
                "state": source,
                "name": cfg["name"],
                "status": "OK",
                "raw_rows": detail.get("rows_scanned"),
                "universities": len(found),
                "locations": sum(len(r["locations"]) for r in found),
                "validation_issues": len(invalid),
                **http_client.STATS.snapshot(),
            })
        except Exception as exc:
            print(f"[ERROR] {source}: {type(exc).__name__}: {exc}")
            entries.append({
                "state": source,
                "status": "ERROR",
                "error": f"{type(exc).__name__}: {exc}",
                **http_client.STATS.snapshot(),
            })

    entries = [reliability.assess_state(e, previous_counts.get(e["state"])) for e in entries]

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    build = reliability.build_status(entries, expected, normalized_path=out)
    reliability.write_json(status_path, build)
    reliability.update_state_counts(entries, previous=previous_counts)

    report = {
        "generated_at": now(),
        "sources": entries,
        "details": details,
        "candidates": [
            {
                "source": r["state"],
                "record_id": r["source"]["record_id"],
                "name": r["name"],
                "country": r["country"],
                "official_url": r["official_url"],
                "signals": r["discovery"]["signals"],
                "online_de_status": "review",
            }
            for r in records
        ],
    }
    reliability.write_json(report_path, report)

    print()
    print("-" * 62)
    print(f"SOURCES:      {sum(1 for e in entries if e['source_status'] == 'success')}/{len(sources)} successful")
    print(f"CANDIDATES:   {len(records)}  (all online_de_status = review)")
    print(f"OUTPUT:       {out}")
    print(f"REPORT:       {report_path}")
    reliability.print_status(build)
    print("-" * 62)
    return build


def main():
    parser = argparse.ArgumentParser(description="ProjectPathly — international online discovery")
    parser.add_argument("--sources", nargs="+", default=None, help="e.g. INTL-ETER INTL-IPEDS")
    parser.add_argument("--config", default=str(SOURCES_PATH))
    parser.add_argument("--out", default=str(OUTPUT_PATH))
    args = parser.parse_args()

    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    sources = args.sources or [s for s, c in config.items() if c.get("enabled", True)]

    print()
    print("=" * 62)
    print("PROJECTPATHLY — INTERNATIONAL ONLINE DISCOVERY")
    print("=" * 62)
    run(config, sources, out=Path(args.out))


if __name__ == "__main__":
    main()
