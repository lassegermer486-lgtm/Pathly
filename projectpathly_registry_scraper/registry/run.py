from __future__ import annotations

import argparse
import json
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


STATE_ORDER = [
    "DE-BW",
    "DE-BY",
    "DE-BE",
    "DE-BB",
    "DE-HB",
    "DE-HH",
    "DE-HE",
    "DE-MV",
    "DE-NI",
    "DE-NW",
    "DE-RP",
    "DE-SL",
    "DE-SN",
    "DE-ST",
    "DE-SH",
    "DE-TH",
]


def normalize_state(state, rows):
    """
    Convert state-specific raw rows into the common
    ProjectPathly university structure.
    """

    if state == "DE-NW":
        return aggregate_nrw_universities(rows)

    return aggregate_university_rows(rows, state)


def main():
    parser = argparse.ArgumentParser(
        description="ProjectPathly German University Registry"
    )

    parser.add_argument(
        "--states",
        nargs="+",
        default=None,
        help="Optional state codes, e.g. DE-NW DE-BW"
    )

    parser.add_argument(
        "--sources",
        default="registry/sources.yaml"
    )

    parser.add_argument(
        "--out",
        default="data/normalized/universities_de.json"
    )

    args = parser.parse_args()

    config = yaml.safe_load(
        Path(args.sources).read_text(encoding="utf-8")
    )

    states = args.states or STATE_ORDER

    all_universities = []
    report = []

    print()
    print("=" * 62)
    print("PROJECTPATHLY — GERMAN UNIVERSITY REGISTRY")
    print("=" * 62)

    for state in states:

        if state not in config:
            print(f"[ERROR] {state}: missing from sources.yaml")
            report.append({
                "state": state,
                "status": "ERROR",
                "error": "missing_config"
            })
            continue

        cfg = dict(config[state])

        if not cfg.get("enabled", True):
            print(f"[SKIP] {state}: disabled")
            report.append({
                "state": state,
                "status": "SKIPPED"
            })
            continue

        adapter_name = cfg.get("adapter", "stub")

        if adapter_name == "stub":
            print(
                f"[TODO] {state} — {cfg['name']}: "
                "adapter not implemented"
            )

            report.append({
                "state": state,
                "status": "TODO"
            })

            continue

        adapter_cls = ADAPTERS.get(adapter_name)

        if adapter_cls is None:
            print(
                f"[ERROR] {state}: unknown adapter "
                f"'{adapter_name}'"
            )

            report.append({
                "state": state,
                "status": "ERROR",
                "error": f"unknown_adapter:{adapter_name}"
            })

            continue

        cfg["_raw_dir"] = "data/raw"

        print()
        print(f"[FETCH] {state} — {cfg['name']}")

        try:
            raw_rows = adapter_cls(
                state,
                cfg
            ).fetch()

            universities = normalize_state(
                state,
                raw_rows
            )

            invalid = validate_registry(
                universities
            )

            locations = sum(
                len(u.get("locations", []))
                for u in universities
            )

            print(
                f"[OK] {state}: "
                f"{len(universities)} universities / "
                f"{locations} locations"
            )

            if invalid:
                print(
                    f"[WARN] {state}: "
                    f"{len(invalid)} validation issues"
                )

            all_universities.extend(
                universities
            )

            report.append({
                "state": state,
                "name": cfg["name"],
                "status": "OK",
                "raw_rows": len(raw_rows),
                "universities": len(universities),
                "locations": locations,
                "validation_issues": len(invalid)
            })

        except NotImplementedError as exc:
            print(f"[TODO] {exc}")

            report.append({
                "state": state,
                "status": "TODO"
            })

        except Exception as exc:
            print(
                f"[ERROR] {state}: "
                f"{type(exc).__name__}: {exc}"
            )

            report.append({
                "state": state,
                "status": "ERROR",
                "error": str(exc)
            })

    # --------------------------------------------------
    # Export university registry
    # --------------------------------------------------

    out = Path(args.out)
    out.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    out.write_text(
        json.dumps(
            all_universities,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    # --------------------------------------------------
    # Export run report
    # --------------------------------------------------

    report_path = Path(
        "data/reports/registry_run.json"
    )

    report_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    report_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    # --------------------------------------------------
    # Summary
    # --------------------------------------------------

    successful_states = sum(
        1
        for r in report
        if r["status"] == "OK"
    )

    total_locations = sum(
        len(u.get("locations", []))
        for u in all_universities
    )

    print()
    print("-" * 62)
    print(
        f"STATES:       "
        f"{successful_states}/{len(states)} successful"
    )
    print(
        f"UNIVERSITIES: "
        f"{len(all_universities)}"
    )
    print(
        f"LOCATIONS:    "
        f"{total_locations}"
    )
    print(
        f"OUTPUT:       "
        f"{out}"
    )
    print(
        f"REPORT:       "
        f"{report_path}"
    )
    print("-" * 62)


if __name__ == "__main__":
    main()
