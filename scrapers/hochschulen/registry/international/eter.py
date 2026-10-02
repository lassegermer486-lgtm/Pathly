"""
ETER (European Tertiary Education Register) — Europe.

Candidates: institutions outside Germany whose latest answered
"Distance education institution" value is in the configured set (2 = mostly
distance education, >90 % of the students) and whose reference year is
recent enough. The flag is a discovery signal only (Cyprus, for example,
reports every university as 2).
"""

from __future__ import annotations

import csv
from pathlib import Path

from .base import normalize_url, pinned_file, record


DISTANCE = "Distance education institution"

# ETER uses "UK" for the United Kingdom; everything else is ISO 3166-1.
COUNTRY = {"UK": "GB"}

# ETER "Legal status": 0 = public, 1 = private, 2 = private government-dependent
OWNERSHIP = {"0": "public", "1": "private", "2": "private"}

# ETER "Institution Category standardized": 0 = other, 1 = university, 2 = UAS
INSTITUTION_TYPE = {"0": "other", "1": "university", "2": "university_of_applied_sciences"}

ANSWERED = {"0", "1", "2"}


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    # ETER special codes: m (missing), a (not applicable), x, c (confidential) …
    return None if not value or value in ("m", "a", "x", "xc", "xr", "c", "s", "nc") else value


def latest_answers(rows) -> dict[str, dict]:
    """ETER ID -> row of the latest reference year with an answered distance value."""
    latest: dict[str, dict] = {}
    for row in rows:
        if row.get(DISTANCE) not in ANSWERED:
            continue
        current = latest.get(row["ETER ID"])
        if current is None or int(row["Reference year"]) > int(current["Reference year"]):
            latest[row["ETER ID"]] = row
    return latest


def select(rows, filters: dict) -> tuple[list[dict], dict]:
    """(candidate rows, counts for the report)."""
    wanted = {str(v) for v in filters.get("distance_education_institution", ["2"])}
    min_year = int(filters.get("min_reference_year", 0))
    excluded = set(filters.get("exclude_countries", ["DE"]))

    latest = latest_answers(rows)
    counts = {"institutions_with_answer": len(latest), "flagged": 0, "too_old": 0,
              "excluded_country": 0, "no_website": 0}
    selected = []

    for row in latest.values():
        if row[DISTANCE] not in wanted:
            continue
        counts["flagged"] += 1
        if row["Country Code"] in excluded:
            counts["excluded_country"] += 1
            continue
        if int(row["Reference year"]) < min_year:
            counts["too_old"] += 1
            continue
        if not normalize_url(_clean(row.get("Institutional website"))):
            counts["no_website"] += 1
            continue
        selected.append(row)

    selected.sort(key=lambda r: (r["Country Code"], r["ETER ID"]))
    return selected, counts


def to_record(row: dict, source: str, config: dict, retrieved_at: str | None = None) -> dict:
    country = COUNTRY.get(row["Country Code"], row["Country Code"])
    english = _clean(row.get("English Institution Name"))
    national = _clean(row.get("Institution Name"))

    return record(
        source=source,
        config=config,
        record_id=row["ETER ID"],
        # English name: national names are partly legal entities or non-Latin
        # script; the national name stays in discovery.name_national.
        name=english or national,
        country=country,
        official_url=normalize_url(_clean(row.get("Institutional website"))),
        city=_clean(row.get("Name of the city")),
        postal_code=_clean(row.get("Postcode")),
        ownership=OWNERSHIP.get(row.get("Legal status"), "unknown"),
        institution_type=INSTITUTION_TYPE.get(row.get("Institution Category standardized"), "unknown"),
        reference_year=row["Reference year"],
        external_ids={
            "eter": row["ETER ID"],
            "ror": _clean(row.get("ROR ID")),
            "whed": _clean(row.get("WHED ID")),
        },
        signals={
            "distance_education_institution": int(row[DISTANCE]),
            "distance_education_reference_year": int(row["Reference year"]),
        },
        extra={"name_national": national, "eter_country_code": row["Country Code"]},
        retrieved_at=retrieved_at,
    )


def read_rows(path: Path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f, delimiter=";")


def discover(source: str, config: dict, cache_root=None) -> tuple[list[dict], dict]:
    kwargs = {"cache_root": cache_root} if cache_root else {}
    path, obtained = pinned_file(source, config["files"]["dump"], **kwargs)

    rows = list(read_rows(path))
    selected, counts = select(rows, config.get("filter") or {})

    records = [to_record(row, source, config) for row in selected]
    report = {"rows_scanned": len(rows), "file": str(path), "obtained": obtained, **counts}
    return records, report
