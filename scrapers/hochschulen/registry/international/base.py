"""Shared parts of the international discovery adapters."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from registry import http_client


CACHE_ROOT = Path("data/source_cache")

# Source namespaces. They sit in the record's "state" field so that the
# existing record_key / overrides / listed_by keep working; they are not
# German states (those are "DE-XX").
NAMESPACE_PREFIX = "INTL-"


def is_international(state: str | None) -> bool:
    return bool(state) and state.startswith(NAMESPACE_PREFIX)


class SnapshotError(RuntimeError):
    """A pinned file is missing or its content differs from the pin."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pinned_file(source: str, spec: dict, cache_root: Path = CACHE_ROOT) -> tuple[Path, str]:
    """
    Path of a pinned source file and how it was obtained ("cache" / "download").

    A cached copy is used if its SHA-256 matches the pin; otherwise the file
    is downloaded once (with the shared retries) and must match the pin.
    """
    target = Path(cache_root) / source / spec["filename"]

    if target.exists() and sha256_file(target) == spec["sha256"]:
        print(f"[CHECKSUM] {source} {spec['filename']}: verified (sha256 {spec['sha256'][:12]}…, cache)")
        return target, "cache"

    target.parent.mkdir(parents=True, exist_ok=True)
    response = http_client.get(
        spec["url"],
        timeout=300,
        headers={"User-Agent": "ProjectPathlyRegistry/0.1"},
    )
    response.raise_for_status()

    partial = target.with_name(target.name + ".part")
    partial.write_bytes(response.content)

    actual = sha256_file(partial)
    if actual != spec["sha256"]:
        partial.unlink()
        raise SnapshotError(
            f"{source}: {spec['filename']} does not match the pinned SHA-256 "
            f"(expected {spec['sha256'][:16]}…, got {actual[:16]}…). "
            "The publisher changed the file; adopt a new version by updating "
            "registry/international_sources.yaml on purpose."
        )

    partial.replace(target)
    print(f"[CHECKSUM] {source} {spec['filename']}: verified (sha256 {spec['sha256'][:12]}…, downloaded)")
    return target, "download"


def normalize_url(value: str | None) -> str | None:
    value = (value or "").strip()
    if not value or value.lower() in ("m", "a", "x", "c"):
        return None
    if not urlparse(value).scheme:
        value = "https://" + value.lstrip("/")
    return value


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record(
    *,
    source: str,
    config: dict,
    record_id: str,
    name: str,
    country: str,
    official_url: str | None,
    city: str | None,
    postal_code: str | None = None,
    street: str | None = None,
    ownership: str = "unknown",
    institution_type: str = "unknown",
    reference_year: str | None = None,
    external_ids: dict | None = None,
    signals: dict | None = None,
    extra: dict | None = None,
    retrieved_at: str | None = None,
) -> dict:
    """A normalized record in the shape of the German state records."""
    dataset = config.get("dataset") or {}
    files = config.get("files") or {}

    return {
        "name": name,
        "country": country,
        # source namespace, see NAMESPACE_PREFIX
        "state": source,
        "institution_type": institution_type,
        "ownership": ownership,
        "recognition_status": "unknown",
        "official_url": official_url,
        "official_url_source": dataset.get("landing_page"),
        "locations": [{
            "name": None,
            "city": city,
            "state": None,
            "country": country,
            "postal_code": postal_code,
            "street": street,
            "location_type": "main",
            "location_status": "registered_seat",
            "source_url": dataset.get("landing_page"),
            "source_authority": config.get("authority"),
        }],
        "source": {
            "authority": config.get("authority"),
            "url": dataset.get("landing_page"),
            "source_type": "dataset",
            "source_category": "international_online_discovery",
            "retrieved_at": retrieved_at or now(),
            "dataset_version": dataset.get("version"),
            "dataset_sha256": {key: spec.get("sha256") for key, spec in files.items()},
            "record_id": record_id,
            "reference_year": reference_year,
        },
        "discovery": {
            "source": source,
            "external_ids": {k: v for k, v in (external_ids or {}).items() if v},
            "signals": signals or {},
            **(extra or {}),
        },
    }


def validate(records: list[dict]) -> list[dict]:
    """Minimal checks (the German validate_registry assumes country = DE)."""
    invalid = []
    for r in records:
        errors = []
        if not r.get("name"):
            errors.append("missing_name")
        if not (r.get("country") or "").isalpha() or len(r.get("country") or "") != 2:
            errors.append("invalid_country")
        if r.get("country") == "DE":
            errors.append("german_institution")
        if not r.get("official_url"):
            errors.append("missing_website")
        if not is_international(r.get("state")):
            errors.append("invalid_source_namespace")
        if errors:
            invalid.append({"name": r.get("name"), "errors": errors})
    return invalid
