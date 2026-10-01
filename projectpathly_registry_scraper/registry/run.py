from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path

import yaml

from .adapters.nrw import NRWAdapter
from .adapters.bw import BadenWuerttembergAdapter
from .adapters.by import BayernAdapter
from .adapters.be import BerlinAdapter
from .adapters.bb import BrandenburgAdapter
from .adapters.hb import BremenAdapter
from .adapters.hh import HamburgAdapter
from .adapters.he import HessenAdapter
from .adapters.mv import MecklenburgVorpommernAdapter
from .adapters.ni import NiedersachsenAdapter
from .adapters.rp import RheinlandPfalzAdapter
from .adapters.sl import SaarlandAdapter
from .adapters.sn import SachsenAdapter
from .adapters.st import SachsenAnhaltAdapter
from .adapters.sh import SchleswigHolsteinAdapter
from .adapters.th import ThueringenAdapter

from .normalize import aggregate_nrw_universities
from .normalizers.university import aggregate_university_rows
from .utils.validation import validate_registry
from .states import BY_CODE, STATES, resolve, short


ADAPTERS = {
    "bw": BadenWuerttembergAdapter,
    "by": BayernAdapter,
    "be": BerlinAdapter,
    "bb": BrandenburgAdapter,
    "hb": BremenAdapter,
    "hh": HamburgAdapter,
    "he": HessenAdapter,
    "mv": MecklenburgVorpommernAdapter,
    "ni": NiedersachsenAdapter,
    "nrw": NRWAdapter,
    "rp": RheinlandPfalzAdapter,
    "sl": SaarlandAdapter,
    "sn": SachsenAdapter,
    "st": SachsenAnhaltAdapter,
    "sh": SchleswigHolsteinAdapter,
    "th": ThueringenAdapter,
}


def normalize_state(state, rows):
    """
    Convert state-specific raw rows into the common
    ProjectPathly university structure.
    """

    if state == "DE-NW":
        return aggregate_nrw_universities(rows)

    return aggregate_university_rows(rows, state)


def scrape(states, config, snapshots=False, log=print):
    """
    Run the adapters for the given state codes and return the records.

    Only with snapshots=True raw copies of the sources are written and the
    SH fallback cache is refreshed.
    """
    all_universities = []
    report = []

    for state in states:
        label = BY_CODE[state].label

        if state not in config:
            log(f"[ERROR] {label}: missing from sources.yaml")
            report.append({"state": state, "status": "ERROR", "error": "missing_config"})
            continue

        cfg = dict(config[state])

        if not cfg.get("enabled", True):
            log(f"[SKIP]  {label}: disabled")
            report.append({"state": state, "status": "SKIPPED"})
            continue

        adapter_name = cfg.get("adapter", "stub")
        adapter_cls = ADAPTERS.get(adapter_name)

        if adapter_cls is None:
            log(f"[ERROR] {label}: unknown adapter '{adapter_name}'")
            report.append({"state": state, "status": "ERROR",
                           "error": f"unknown_adapter:{adapter_name}"})
            continue

        if snapshots:
            cfg["_raw_dir"] = "data/raw"
            cfg["_refresh_cache"] = True

        log(f"[FETCH] {label}")

        try:
            raw_rows = adapter_cls(state, cfg).fetch()
            universities = normalize_state(state, raw_rows)
            invalid = validate_registry(universities)
            locations = sum(len(u.get("locations", [])) for u in universities)

            log(f"[OK]    {BY_CODE[state].short}: {len(universities)} universities / "
                f"{locations} locations")
            if invalid:
                log(f"[WARN]  {BY_CODE[state].short}: {len(invalid)} validation issues")

            all_universities.extend(universities)
            report.append({
                "state": state,
                "name": cfg["name"],
                "status": "OK",
                "raw_rows": len(raw_rows),
                "universities": len(universities),
                "locations": locations,
                "validation_issues": len(invalid),
            })

        except NotImplementedError as exc:
            log(f"[TODO]  {exc}")
            report.append({"state": state, "status": "TODO"})

        except Exception as exc:
            log(f"[ERROR] {label}: {type(exc).__name__}: {exc}")
            report.append({"state": state, "status": "ERROR", "error": str(exc)})

    return all_universities, report


def parse_states(tokens):
    if not tokens:
        return [s.code for s in STATES]
    return [resolve(t).code for t in tokens]


def load_config(path="registry/sources.yaml"):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="ProjectPathly German University Registry — state scrape"
    )
    parser.add_argument(
        "--states", nargs="+", default=None,
        help="States to scrape, e.g. NRW BW BY (also DE-NW). Default: all 16",
    )
    parser.add_argument("--sources", default="registry/sources.yaml")
    parser.add_argument(
        "--out", default=None,
        help="JSON output file (default: data/normalized/universities_de.json, "
             "or universities_<STATES>.json when --states is given)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="only print, do not write the JSON file",
    )
    parser.add_argument(
        "--snapshots", action="store_true",
        help="also store raw copies of the sources in data/raw/ and "
             "refresh the SH fallback cache",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="print every scraped institution",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="print the full result as JSON to stdout (log goes to stderr)",
    )
    args = parser.parse_args()

    try:
        states = parse_states(args.states)
    except ValueError as exc:
        parser.error(str(exc))

    log = (lambda msg: print(msg, file=sys.stderr)) if args.json else print

    # A partial scrape must not overwrite the full dataset.
    out = args.out or (
        "data/normalized/universities_de.json" if not args.states
        else f"data/normalized/universities_{'_'.join(short(s) for s in states)}.json"
    )

    log("")
    log("=" * 62)
    log("PROJECTPATHLY — GERMAN UNIVERSITY REGISTRY")
    log("=" * 62)

    # Adapters print progress; with --json that must not end up in stdout.
    with contextlib.redirect_stdout(sys.stderr) if args.json else contextlib.nullcontext():
        universities, report = scrape(states, load_config(args.sources), args.snapshots, log)

    if args.json:
        print(json.dumps(universities, ensure_ascii=False, indent=2))

    if args.list:
        log("")
        for u in sorted(universities, key=lambda u: (u["state"], u["name"])):
            cities = sorted({l.get("city") for l in u.get("locations", []) if l.get("city")})
            log(f"{short(u['state']):<3} {u['name'][:60]:<60} {u['institution_type']:<31} "
                f"{', '.join(cities)[:40]}")

    ok = sum(1 for r in report if r["status"] == "OK")
    locations = sum(len(u.get("locations", [])) for u in universities)

    log("")
    log("-" * 62)
    log(f"STATES:       {ok}/{len(states)} successful")
    log(f"UNIVERSITIES: {len(universities)}")
    log(f"LOCATIONS:    {locations}")

    if args.dry_run:
        log("OUTPUT:       nothing written (--dry-run)")
    else:
        _write_json(out, universities)
        log(f"OUTPUT:       {out}")
    if args.snapshots:
        log("RAW:          data/raw/")

    failed = [r for r in report if r["status"] == "ERROR"]
    if failed:
        log(f"[WARN]  incomplete: failed states "
            f"{', '.join(short(r['state']) for r in failed)}")
    log("-" * 62)

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
