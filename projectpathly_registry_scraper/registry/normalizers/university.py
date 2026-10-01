from datetime import datetime, timezone

from registry.normalize import (
    clean_text,
    normalize_url,
    university_name_key,
)


def aggregate_university_rows(rows, state_code):
    """
    Generic aggregation:

    multiple source/location rows
        ->
    one university with multiple locations

    State-specific transformations should happen
    before calling this function.
    """

    universities = {}

    # Some adapters do not stamp their sources. They were fetched
    # moments ago in this same run.
    retrieved_at = datetime.now(timezone.utc).isoformat()

    for row in rows:
        source = row.get("source")
        if isinstance(source, dict) and not source.get("retrieved_at"):
            row["source"] = {**source, "retrieved_at": retrieved_at}

    for row in rows:
        name = clean_text(row.get("name"))

        if not name:
            continue

        key = university_name_key(name)

        if key not in universities:
            universities[key] = {
                "name": name,
                "country": "DE",
                "state": state_code,
                "institution_type": row.get(
                    "institution_type",
                    "unknown"
                ),
                "ownership": row.get(
                    "ownership",
                    "unknown"
                ),
                "recognition_status": row.get(
                    "recognition_status",
                    "unknown"
                ),
                "official_url": normalize_url(
                    row.get("official_url")
                ),
                # Page on which the official URL was found, if the
                # adapter knows it (may differ from the discovery source).
                "official_url_source": row.get(
                    "official_url_source"
                ),
                "locations": [],
                "source": row.get("source"),
            }

        # A later source row may contain the canonical university URL
        # even if the first row only represented a campus/location.
        if (
            not universities[key].get("official_url")
            and row.get("official_url")
        ):
            universities[key]["official_url"] = normalize_url(
                row.get("official_url")
            )
            universities[key]["official_url_source"] = row.get(
                "official_url_source"
            )

        universities[key]["locations"].append({
            "name": clean_text(
                row.get("location_name")
            ),
            "city": clean_text(
                row.get("city")
            ),
            "state": row.get(
                "location_state",
                state_code
            ),
            "postal_code": clean_text(
                row.get("postal_code")
            ),
            "street": clean_text(
                row.get("street")
            ),
            "location_type": row.get(
                "location_type",
                "main"
                if not row.get("location_name")
                else "campus"
            ),
            "location_status": row.get(
                "location_status",
                "confirmed"
            ),
            "source_url": row.get(
                "location_source_url"
            ),
            "source_authority": row.get(
                "location_source_authority"
            ),
        })

    return list(universities.values())
