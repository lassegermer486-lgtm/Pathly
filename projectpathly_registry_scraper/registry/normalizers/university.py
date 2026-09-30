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
