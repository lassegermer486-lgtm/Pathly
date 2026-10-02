"""
IPEDS (U.S. Department of Education, NCES) — USA.

Candidates must satisfy both online signals plus basic eligibility:

    HD   CYACTIVE = 1, PSET4FLG = 1 (Title IV), DEGGRANT = 1, HLOFFER >= 5
    IC   DISTNCED = 1  "Are all the programs at your institution offered
                        completely via distance education?"
    EFFY EFYDEEXC / EFYDETOT >= 0.90 (all students, 12 months), EFYDETOT >= 100

EF2023A_DIST EFDEEX4 (exclusively online students residing outside the
U.S.) is kept as a ranking signal and never excludes anyone: WGU reports 0.

Title IV is a filter, not the recognition evidence shown to users. The
institution's accreditation is looked up in DAPIP by OPEID (kept in
discovery.recognition).
"""

from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

from .base import normalize_url, pinned_file, record


# HD2024 CONTROL: 1 public, 2 private not-for-profit, 3 private for-profit
OWNERSHIP = {"1": "public", "2": "private", "3": "private"}

DAPIP_URL = "https://ope.ed.gov/dapip/"


def read_zip_csv(path: Path) -> list[dict]:
    """The single CSV of an IPEDS zip; keys upper-case, values stripped."""
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist() if n.lower().endswith(".csv")]
        # Final releases ship an additional *_rv.csv; prefer it if present.
        names.sort(key=lambda n: ("_rv" not in n.lower(), n))
        raw = archive.read(names[0])

    text = raw.decode("utf-8-sig") if raw[:3] == b"\xef\xbb\xbf" else raw.decode("latin-1")
    return [
        {k.strip().lstrip("﻿").upper(): (v or "").strip() for k, v in row.items()}
        for row in csv.DictReader(io.StringIO(text))
    ]


def _int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def select(hd: list[dict], ic: list[dict], effy: list[dict], ef: list[dict], filters: dict):
    """(candidates as (hd_row, signals), counts for the report)."""
    ic_by = {r["UNITID"]: r for r in ic}
    effy_by = {r["UNITID"]: r for r in effy if r.get("EFFYDLEV") == "1"}
    ef_by = {r["UNITID"]: r for r in ef if r.get("EFDELEV") == "1"}

    min_share = float(filters.get("min_exclusive_distance_share", 0.9))
    min_enrollment = int(filters.get("min_enrollment", 100))
    min_hloffer = int(filters.get("min_hloffer", 5))

    counts = {"institutions": len(hd), "eligible": 0, "distnced": 0, "selected": 0}
    selected = []

    for row in hd:
        unitid = row["UNITID"]
        if not (
            row.get("CYACTIVE") == filters.get("cyactive", "1")
            and row.get("PSET4FLG") == filters.get("pset4flg", "1")
            and row.get("DEGGRANT") == filters.get("deggrant", "1")
            and _int(row.get("HLOFFER")) >= min_hloffer
        ):
            continue
        counts["eligible"] += 1

        if (ic_by.get(unitid) or {}).get("DISTNCED") != filters.get("distnced", "1"):
            continue
        counts["distnced"] += 1

        enrollment = effy_by.get(unitid) or {}
        total = _int(enrollment.get("EFYDETOT"))
        exclusive = _int(enrollment.get("EFYDEEXC"))
        if total < min_enrollment or exclusive / total < min_share:
            continue

        fall = ef_by.get(unitid) or {}
        selected.append((row, {
            "all_programs_fully_online": True,                     # IC DISTNCED = 1
            "exclusive_distance_share_12m": round(exclusive / total, 3),
            "enrollment_12m": total,
            "students_outside_us_fall": _int(fall.get("EFDEEX4")) if fall else None,
            "title_iv": True,
            "highest_offering": _int(row.get("HLOFFER")),
        }))

    counts["selected"] = len(selected)
    # Ranking only: institutions with online students abroad first.
    selected.sort(key=lambda item: (-(item[1]["students_outside_us_fall"] or 0), item[0]["INSTNM"]))
    return selected, counts


def to_record(row: dict, signals: dict, source: str, config: dict, retrieved_at: str | None = None) -> dict:
    opeid = row.get("OPEID") or None
    return record(
        source=source,
        config=config,
        record_id=row["UNITID"],
        name=row["INSTNM"],
        country="US",
        official_url=normalize_url(row.get("WEBADDR")),
        city=row.get("CITY") or None,
        postal_code=row.get("ZIP") or None,
        street=row.get("ADDR") or None,
        ownership=OWNERSHIP.get(row.get("CONTROL"), "unknown"),
        reference_year="2024-25",
        external_ids={"ipeds_unitid": row["UNITID"], "opeid": opeid},
        signals=signals,
        extra={
            "us_state": row.get("STABBR") or None,
            "recognition": {
                "title_iv": True,
                "accreditation_source": "DAPIP",
                "accreditation_lookup": {"opeid": opeid, "url": DAPIP_URL},
                # Checked per institution (online_de_decisions.yaml
                # recognition_evidence_url); Title IV alone is not shown as
                # recognition.
                "accreditation_status": "not_checked",
            },
        },
        retrieved_at=retrieved_at,
    )


def discover(source: str, config: dict, cache_root=None) -> tuple[list[dict], dict]:
    kwargs = {"cache_root": cache_root} if cache_root else {}
    files = config["files"]
    paths, obtained = {}, {}
    for key in ("hd", "ic", "effy_dist", "ef_dist"):
        paths[key], obtained[key] = pinned_file(source, files[key], **kwargs)

    tables = {key: read_zip_csv(path) for key, path in paths.items()}
    selected, counts = select(tables["hd"], tables["ic"], tables["effy_dist"], tables["ef_dist"],
                              config.get("filter") or {})

    records = [to_record(row, signals, source, config) for row, signals in selected]
    report = {"rows_scanned": len(tables["hd"]), "obtained": obtained, **counts}
    return records, report
