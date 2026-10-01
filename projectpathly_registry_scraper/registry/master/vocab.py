"""
Nationwide schema of the ProjectPathly Master University Registry.

The state adapters use different terms. This module defines the unified
vocabulary and maps the adapter values onto it. The original values stay
available per source in `merged_from[].legacy`.

The three dimensions are independent and never derived from each other's
wording: institution_type (what it is), ownership (who runs it) and
recognition_status (on which legal basis it awards degrees).
"""
from __future__ import annotations

INSTITUTION_TYPES = {
    "university",
    "university_of_applied_sciences",
    "art_music_university",
    "university_of_education",
    "public_administration",
    "dual_university",
    "theological_university",
    "other",
    "unknown",
}

OWNERSHIPS = {"public", "private", "church", "federal", "other", "unknown"}

# public_by_law    = established by state/federal law (staatliche Hochschule)
# state_recognized = staatlich anerkannt
# other_recognized = other basis, e.g. church law; only set by review
RECOGNITION_STATUSES = {"state_recognized", "public_by_law", "other_recognized", "unknown"}

LIFECYCLE_STATUSES = {"active", "renamed", "merged", "closed", "unknown"}

_TYPE_MAP = {
    "art_music": "art_music_university",
    "public_administration": "public_administration",
    "university_of_public_administration": "public_administration",
    "theological": "theological_university",
}

# Sources that list "private or church" together do not tell us which one
# applies -> unknown (the combined source value stays in `legacy`).
_OWNERSHIP_MAP = {
    "private_or_church": "unknown",
    "private_or_other": "unknown",
}


def map_institution_type(value: str | None) -> str:
    value = _TYPE_MAP.get(value or "unknown", value or "unknown")
    return value if value in INSTITUTION_TYPES else "unknown"


def map_ownership(value: str | None) -> str:
    value = _OWNERSHIP_MAP.get(value or "unknown", value or "unknown")
    return value if value in OWNERSHIPS else "unknown"


def map_recognition(value: str | None, ownership: str) -> str:
    """
    Only what the source states explicitly: its own recognition value, or
    the category it lists the institution under ("Staatliche Hochschulen").
    Nothing is derived from the name.
    """
    value = value or "unknown"
    by_law = ownership in {"public", "federal"}

    if value == "state_recognized":
        return "state_recognized"
    if value == "state_or_state_recognized":
        # The source lists both kinds; its ownership category decides.
        if by_law:
            return "public_by_law"
        if ownership in {"private", "church"}:
            return "state_recognized"
        return "unknown"
    if by_law:
        return "public_by_law"
    return "unknown"


def normalize_source(source: dict | None, state: str | None) -> dict:
    """Different adapters use different keys; unify them."""
    source = source or {}
    return {
        "state": state,
        "authority": source.get("authority"),
        "url": source.get("url") or source.get("source_url"),
        "category": source.get("category") or source.get("source_category"),
        "source_type": source.get("source_type"),
        "retrieved_at": source.get("retrieved_at"),
    }
