"""
Master registry build (spec steps 9–12): canonical names, minimal
validation and lifecycle, stable registry IDs, master files.

    data/master/universities_dedup.json      deduplicated institutions
    data/enriched/universities_de_urls.json  member details
    data/master/id_registry.json             stable IDs (committed, grows)
        ->
    data/master/universities_de_master.json  one row per institution
    data/master/university_metadata.json
    data/master/locations.json
    data/master/aliases.json
    data/master/sources.json
    data/reports/validation_report.json

Usage (from scrapers/hochschulen/):

    python -m registry.master.build
    python -m registry.master.build --offline   # no website lookups for names
"""

from __future__ import annotations

import argparse
import json
import re
import secrets
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from registry import reliability
from registry.international.base import is_international
from registry.master import online_de, presence
from registry.enrichment.website_resolver import (
    LEGAL_FORM_RE,
    WebsiteResolver,
    explicit_acronyms,
    find_imprint_url,
    fold,
    identity_texts,
    visible_text,
    without_stopwords,
)
from registry.master.dedup import DEFAULT_INPUTS, LOCATION_SUFFIX_RE, load_inputs, record_key
from registry.normalize import normalize_url


REGISTRY_ID_RE = re.compile(r"^PTH-DE-[0-9A-F]{8}$")

# Values the database accepts (supabase/migrations), mapped from the
# adapters' vocabulary. Ambiguous values stay "unknown" (spec §36: unknown
# values are not invented); the raw values remain in university_metadata.
INSTITUTION_TYPES = {
    "university": "university",
    "university_of_applied_sciences": "university_of_applied_sciences",
    "art_music_university": "art_music_university",
    "art_music": "art_music_university",
    "university_of_education": "university_of_education",
    "public_administration": "public_administration",
    "university_of_public_administration": "public_administration",
    "dual_university": "dual_university",
    "theological": "theological_university",
}
OWNERSHIP = {"public": "public", "private": "private", "church": "church", "federal": "federal"}
RECOGNITION = {"state_recognized": "state_recognized", "public": "public_by_law"}
LOCATION_TYPES = {"main": "main", "campus": "branch", "study_location": "branch"}

# Name artifacts from source pages: image titles, footnote marks, campus
# or department labels, slogans after "|".
ARTIFACT_RE = re.compile(
    r"\s*[-–]\s*(?:Außenansicht|Logo|Gebäude|Hauptgebäude|Startseite)\s*$"
    r"|\s+[-–]\s+(?:Fachbereich|Abteilung|Standort|Campus)\b.*$",
    re.IGNORECASE,
)

# Country-code domains that are not German institutions' usual ones.
HOME_TLDS = {"de", "eu"}


# ----------------------------------------------------------------------
# Step 9: canonical name
# ----------------------------------------------------------------------

def clean_name(name: str, known_cities: frozenset[str]) -> str:
    """
    Source name without page artifacts, legal forms, acronym or city
    annotations and campus suffixes:

        "Medizinische Hochschule Brandenburg - Außenansicht" -> "Medizinische Hochschule Brandenburg"
        "HSD Hochschule Döpfer GmbH"                         -> "HSD Hochschule Döpfer"
        "Berliner Hochschule für Technik (BHT)"              -> "Berliner Hochschule für Technik"
        "BTK Hochschule für Gestaltung, Campus Hamburg"      -> "BTK Hochschule für Gestaltung"

    "... in <Stadt>" stays: it can be part of the official name
    ("FernUniversität in Hagen").
    """
    value = unicodedata.normalize("NFC", name).replace("\xad", "")

    # Slogan after "|", unless the head alone is just a brand word:
    # "NORDAKADEMIE Hochschule der Wirtschaft | Graduate School" -> head,
    # "VICTORIA | Internationale Hochschule" stays.
    head = value.split(" | ")[0]
    if len(head.split()) >= 2:
        value = head
    value = re.sub(r"[\s*]+$", "", value)
    value = ARTIFACT_RE.sub("", value)
    value = LEGAL_FORM_RE.sub(" ", value)

    def parenthetical(match):
        inner = match.group(1).strip()
        if explicit_acronyms(f"({inner})") or fold(inner) in known_cities:
            return " "
        return match.group(0)

    value = re.sub(r"\s*\(([^)]*)\)", parenthetical, value)

    match = LOCATION_SUFFIX_RE.search(value)
    if match and not match.group("a"):
        place = match.group("b") or match.group("c")
        if fold(place) in known_cities:
            value = value[: match.start()]

    value = " ".join(value.split()).strip(" ,-–")
    return value or name


def _agent(member: dict) -> dict:
    return (member.get("website_resolution") or {}).get("agent") or {}


def current_name(member: dict, known_cities: frozenset[str]) -> tuple[str, str]:
    """(name, origin) — a verified agent name beats the cleaned source name."""
    agent = _agent(member)
    canonical = (agent.get("answer") or {}).get("canonical_name")

    if canonical and (agent.get("validation") or {}).get("accepted"):
        return canonical, "agent_verified"

    return clean_name(member["name"], known_cities), "state_source"


def _confirmed_by_resolver(member: dict) -> bool:
    identity = (member.get("website_resolution") or {}).get("identity") or {}
    return bool({"name_in_title", "name_in_imprint"} & set(identity.get("evidence") or []))


def choose_name(
    members: list[dict],
    known_cities: frozenset[str],
    official_url: str | None,
    site_texts=None,
) -> dict:
    """
    Spec §31 priority: 1. name on the institution's website,
    2. name in the state source, 3. source name.

    `site_texts(url) -> (identity_texts, imprint_text)` is only called
    when members disagree.
    """
    named = [current_name(m, known_cities) for m in members]

    groups: dict[str, list[tuple[str, str]]] = {}
    for name, origin in named:
        groups.setdefault(without_stopwords(fold(name)), []).append((name, origin))

    def representative(entries):
        # Most frequent spelling within a group.
        return Counter(name for name, _ in entries).most_common(1)[0][0]

    if len(groups) == 1:
        entries = next(iter(groups.values()))
        origins = {origin for _, origin in entries}
        confirmed = "agent_verified" in origins or any(_confirmed_by_resolver(m) for m in members)
        return {
            "name": representative(entries),
            "origin": "agent_verified" if "agent_verified" in origins else "state_source",
            "confirmed": confirmed,
        }

    fields, imprint = ([], "")
    if official_url and site_texts:
        fields, imprint = site_texts(official_url)

    folded_fields = [without_stopwords(fold(text)) for text in fields]
    folded_imprint = without_stopwords(fold(imprint))

    # The imprint carries the legal name; titles often carry slogans
    # ("FOM Die Hochschule für Berufstätige").
    def site_score(key):
        score = 0
        if folded_imprint and f" {key} " in f" {folded_imprint} ":
            score += 2
        if any(f" {key} " in f" {f} " for f in folded_fields):
            score += 1
        return score

    ranked = sorted(
        groups.items(),
        key=lambda item: (site_score(item[0]), len(item[1]), len(item[0])),
        reverse=True,
    )
    key, entries = ranked[0]

    return {
        "name": representative(entries),
        "origin": "website" if site_score(key) else "state_source",
        "confirmed": site_score(key) > 0,
    }


def make_site_texts(resolver: WebsiteResolver):
    cache = {}

    def site_texts(url):
        if url in cache:
            return cache[url]

        result = resolver.fetch_robust(url)
        if not result.ok:
            cache[url] = ([], "")
            return cache[url]

        soup = BeautifulSoup(result.html, "html.parser")
        fields = identity_texts(soup)
        imprint = ""

        imprint_url = find_imprint_url(soup, result.final_url)
        if imprint_url:
            page = resolver.fetch_once_more(imprint_url)
            if page.ok:
                imprint = visible_text(BeautifulSoup(page.html, "html.parser"))

        cache[url] = (fields, imprint)
        return cache[url]

    return site_texts


# ----------------------------------------------------------------------
# Step 10: minimal validation and lifecycle
# ----------------------------------------------------------------------

def flag(code: str, severity: str, detail: str | None = None) -> dict:
    return {"code": code, "severity": severity, "detail": detail}


def validate(institution: dict, members: list[dict], chosen: dict, name: dict) -> tuple[str, list[dict]]:
    """
    Spec §32 in its minimal form. Returns (lifecycle_status, flags).

    Renamed or merged predecessors are already part of their successor
    (dedup), so a master row is "active" once its website is verified.
    """
    flags = []
    url = institution["official_url"]
    lifecycle = "active" if url else "review"

    if not url:
        suggestions = sorted({
            s for m in members
            if (s := (m.get("website_resolution") or {}).get("suggested_url"))
        })
        flags.append(flag(
            "missing_website",
            "high",
            f"suggested: {', '.join(suggestions)}" if suggestions else None,
        ))

    explained = False
    for member in members:
        agent = _agent(member)
        answer = agent.get("answer") or {}
        status = answer.get("lifecycle_status")
        accepted = (agent.get("validation") or {}).get("accepted")

        if accepted and status in ("renamed", "merged"):
            explained = True
            code = "renamed" if status == "renamed" else "merged_predecessor"
            flags.append(flag(code, "low", f"{member['name']} -> {answer.get('canonical_name')}"))

        elif status in ("closed", "merged", "renamed") and not accepted:
            lifecycle = "review"
            flags.append(flag(
                "lifecycle_review",
                "medium",
                f"agent reports '{status}' (not verifiable): {member['name']}",
            ))

    resolution = (chosen.get("website_resolution") or {}) if chosen else {}
    website_flags = set(resolution.get("flags") or [])

    # An accepted agent answer was checked against the site itself; the
    # resolver's earlier doubts about the old URL no longer apply.
    if resolution.get("method") == "agent_verified":
        website_flags -= {"identity_unconfirmed", "possible_rename_or_merger"}

    if "possible_rename_or_merger" in website_flags and not explained:
        flags.append(flag("possible_rename_or_merger", "medium", "source URL forwards to a differently named site"))
    if "identity_unconfirmed" in website_flags:
        flags.append(flag("website_identity_unconfirmed", "medium", "website does not name the institution"))
    if "tls_certificate_unverified" in website_flags:
        flags.append(flag("tls_certificate_unverified", "low"))
    if website_flags & {"bot_challenge", "http_blocked_401", "http_blocked_403", "http_blocked_429", "http_blocked_503"}:
        flags.append(flag("website_unverifiable", "low", "site blocks automated checks"))
    if "site_unavailable" in website_flags:
        flags.append(flag("website_unverifiable", "low", "site was down (outage page) during the check"))

    if not name["confirmed"]:
        flags.append(flag("name_unconfirmed", "low", "canonical name not confirmed by the website"))

    # Is it a Hochschule at all?
    if "berufsakademie" in fold(institution["name"]):
        flags.append(flag("possibly_not_hochschule", "medium", "Berufsakademie"))

    if url:
        tld = (urlsplit(url).hostname or "").rsplit(".", 1)[-1]
        if len(tld) == 2 and tld not in HOME_TLDS:
            flags.append(flag("possibly_foreign_institution", "medium", f".{tld} website"))

    # Is it independent?
    if re.search(r"\ban der (?:Universität|Hochschule)\b", institution["name"]):
        flags.append(flag("possibly_part_of_other_institution", "low", institution["name"]))

    return lifecycle, flags


def resolve_metadata(members: list[dict]) -> dict:
    def pick(field, mapping):
        values = [mapping.get(m.get(field)) for m in members]
        known = [v for v in values if v]
        return Counter(known).most_common(1)[0][0] if known else "unknown"

    return {
        "institution_type": pick("institution_type", INSTITUTION_TYPES),
        "ownership": pick("ownership", OWNERSHIP),
        "recognition_status": pick("recognition_status", RECOGNITION),
        "source_values": [
            {
                "source_record": record_key(m),
                "institution_type": m.get("institution_type"),
                "ownership": m.get("ownership"),
                "recognition_status": m.get("recognition_status"),
            }
            for m in members
        ],
    }


# ----------------------------------------------------------------------
# Step 11: stable registry IDs
# ----------------------------------------------------------------------

class IdRegistry:
    """
    Permanent IDs: "PTH-DE-" + 8 random hex digits, never derived from a
    name. The file maps every source record key ever seen to its ID, so
    an institution keeps its ID across runs, renames and new sources.

    When two institutions with IDs are merged, the older ID stays and the
    other becomes an alias of it (-> university_aliases in Supabase).
    """

    def __init__(self, data: dict | None = None):
        self.ids: dict[str, dict] = dict((data or {}).get("ids") or {})

    def to_dict(self) -> dict:
        return {"version": 1, "ids": dict(sorted(self.ids.items()))}

    def _active(self, registry_id: str) -> str:
        seen = set()
        while self.ids[registry_id].get("alias_of") and registry_id not in seen:
            seen.add(registry_id)
            registry_id = self.ids[registry_id]["alias_of"]
        return registry_id

    def _new_id(self) -> str:
        while True:
            candidate = "PTH-DE-" + secrets.token_hex(4).upper()
            if candidate not in self.ids:
                return candidate

    def assign(self, institutions: list[dict], now: str) -> dict[str, dict]:
        """Returns {cluster_id: {"registry_id": ..., "former_ids": [...]}}."""
        by_member = {}
        by_url = {}
        for registry_id, entry in self.ids.items():
            for member in entry.get("members") or []:
                by_member[member] = registry_id
            if entry.get("official_url") and not entry.get("alias_of"):
                by_url[entry["official_url"]] = registry_id

        claimed = set()
        result = {}

        # Bigger institutions first: if an old institution was split, the
        # larger part keeps the ID.
        order = sorted(institutions, key=lambda i: (-len(i["members"]), i["members"][0]))

        for institution in order:
            existing = []
            for member in institution["members"]:
                if member in by_member:
                    registry_id = self._active(by_member[member])
                    if registry_id not in existing and registry_id not in claimed:
                        existing.append(registry_id)

            # A renamed source record: same official website, same ID.
            url = normalize_url(institution.get("official_url"))
            if not existing and url and by_url.get(url) and by_url[url] not in claimed:
                existing.append(by_url[url])

            if existing:
                keep = min(existing, key=lambda i: (self.ids[i].get("created_at") or "", i))
            else:
                keep = self._new_id()
                self.ids[keep] = {"created_at": now}

            for other in existing:
                if other != keep:
                    self.ids[other]["alias_of"] = keep

            entry = self.ids[keep]
            entry.update(
                name=institution["name"],
                official_url=url,
                members=sorted(set(entry.get("members") or []) | set(institution["members"])),
                last_seen_at=now,
            )
            claimed.add(keep)

            result[institution["cluster_id"]] = {
                "registry_id": keep,
                "former_ids": sorted(i for i, e in self.ids.items() if e.get("alias_of") == keep),
            }

        return result


# ----------------------------------------------------------------------
# Step 12: master files
# ----------------------------------------------------------------------

def build(
    institutions: list[dict],
    records: list[dict],
    id_registry: IdRegistry,
    site_texts=None,
    now: str | None = None,
    presence_decisions: list[dict] | None = None,
    online_de_decisions: list[dict] | None = None,
) -> dict:
    """
    presence_decisions / online_de_decisions: reviewed decisions; None reads
    data/master/presence_decisions.yaml / online_de_decisions.yaml (as the
    scraper UI relies on).
    """
    now = now or datetime.now(timezone.utc).isoformat()
    if presence_decisions is None:
        presence_decisions = presence.load_decisions()
    if online_de_decisions is None:
        online_de_decisions = online_de.load_decisions()
    by_key = {record_key(r): r for r in records}

    # Cities of the German sources only (name cleaning); international seats
    # must not change how German names are read.
    known_cities = frozenset(
        fold(location["city"])
        for record in records
        if not is_international(record.get("state"))
        for location in record.get("locations") or []
        if location.get("city")
    )

    prepared = []
    for institution in institutions:
        members = [by_key[key] for key in institution["members"] if key in by_key]
        url = institution.get("official_url")
        chosen = next((m for m in members if m.get("official_url") == url), None) if url else None
        name = choose_name(members, known_cities, url, site_texts)
        prepared.append((institution, members, chosen, name))

    ids = id_registry.assign(
        [{**inst, "name": name["name"]} for inst, _, _, name in prepared],
        now,
    )

    master, metadata, locations, aliases, sources = [], [], [], [], []
    presence_doubts = {}

    for institution, members, chosen, name in prepared:
        registry_id = ids[institution["cluster_id"]]["registry_id"]
        url = institution.get("official_url")
        resolution = (chosen or {}).get("website_resolution") or {}

        row = {
            "registry_id": registry_id,
            "name": name["name"],
            "official_url": url,
            "country": home_country(members),
            "lifecycle_status": None,
            "name_origin": name["origin"],
            "name_confirmed": name["confirmed"],
            "listed_by": institution["source_states"],
            "former_registry_ids": ids[institution["cluster_id"]]["former_ids"],
            "website": {
                "method": resolution.get("method"),
                "confidence": resolution.get("confidence"),
                "last_verified_at": resolution.get("checked_at"),
            },
            "members": institution["members"],
            "flags": [],
        }
        row["lifecycle_status"], row["flags"] = validate(row, members, chosen, name)
        if row["country"] != "DE":
            # Found as a foreign institution on purpose (international discovery).
            row["flags"] = [f for f in row["flags"] if f["code"] != "possibly_foreign_institution"]
        row["external_ids"], row["discovery"] = discovery_provenance(members)
        master.append(row)
        presence_doubts[registry_id] = presence.doubts(row, members)

        meta = resolve_metadata(members)
        metadata.append({"registry_id": registry_id, **meta})

        for location in institution["locations"]:
            if not any(location.get(k) for k in ("name", "city", "street", "postal_code")):
                continue  # only the state, which listed_by already holds
            postal = location.get("postal_code")
            state = location.get("state")
            locations.append({
                "registry_id": registry_id,
                "name": location.get("name"),
                "city": location.get("city"),
                "state": state if state and re.fullmatch(r"DE-[A-Z]{2}", state) else None,
                "postal_code": postal if postal and re.fullmatch(r"\d{5}", postal) else None,
                "street": location.get("street"),
                "location_type": LOCATION_TYPES.get(location.get("location_type"), "unknown"),
                "source_state": location["source_record"].split("|", 1)[0],
                "source_url": location.get("source_url"),
                # confirmed / candidate / structural, as the state source says
                "source_location_status": location.get("location_status"),
                "country": location.get("country") or "DE",
            })

        for alias in institution["names"]:
            if alias != name["name"]:
                aliases.append({"registry_id": registry_id, "alias": alias})

        for source in institution["sources"]:
            sources.append({
                "registry_id": registry_id,
                "authority": source.get("authority"),
                "source_url": source.get("url") or source.get("source_url"),
                "source_state": source.get("state"),
                "retrieved_at": source.get("retrieved_at"),
                "source_category": source.get("category") or source.get("source_category"),
                "source_type": source.get("source_type"),
                # international datasets: pinned version and the record in it
                "dataset_version": source.get("dataset_version"),
                "record_id": source.get("record_id"),
            })

    master.sort(key=lambda row: row["name"].lower())

    # v1.3: adds location_status / german_physical_presence (nothing removed).
    presence_report = presence.apply(
        master, locations, sources, presence_doubts, presence_decisions, now
    )
    # after presence: market_access needs german_physical_presence
    online_de_report = online_de.apply(master, online_de_decisions, now)

    return {
        "universities": master,
        "metadata": metadata,
        "locations": locations,
        "aliases": aliases,
        "sources": sources,
        "built_at": now,
        "presence": presence_report,
        "online_de": online_de_report,
    }


def stable_id_summary(existing: set[str], rows: list[dict], id_registry: IdRegistry) -> dict:
    """
    existing  active IDs before this build
    kept      still the ID of an institution in this build
    new       assigned in this build
    merged    became an alias of another ID (kept as former_registry_ids)
    unlisted  no institution in this build (Supabase: is_listed = false)
    """
    current = {row["registry_id"] for row in rows}
    merged = {rid for rid in existing if id_registry.ids.get(rid, {}).get("alias_of")}
    return {
        "existing": len(existing),
        "kept": len(existing & current),
        "new": len(current - existing),
        "merged": len(merged),
        "unlisted": sorted(existing - current - merged),
        "all_existing_kept": existing <= current,
    }


def home_country(members: list[dict]) -> str:
    """
    The institution's home country. German state sources record the campus
    in Germany as DE; an international source states the home country, which
    wins (§C12). Without an international member: DE, as before.
    """
    for member in members:
        if is_international(member.get("state")) and member.get("country"):
            return member["country"]
    return "DE"


def discovery_provenance(members: list[dict]) -> tuple[dict, list[dict]]:
    """external_ids and the discovery signals of international members."""
    external_ids, discovery = {}, []
    for member in members:
        found = member.get("discovery")
        if not found:
            continue
        external_ids.update(found.get("external_ids") or {})
        discovery.append({
            "source": found.get("source"),
            "record_id": (member.get("source") or {}).get("record_id"),
            "signals": found.get("signals") or {},
            **({"recognition": found["recognition"]} if found.get("recognition") else {}),
        })
    return external_ids, discovery


def quality_report(result: dict, source_records: int, dedup_report: dict | None) -> dict:
    """Spec §37."""
    rows = result["universities"]
    total = len(rows) or 1
    flags = Counter(f["code"] for row in rows for f in row["flags"])
    lifecycle = Counter(row["lifecycle_status"] for row in rows)

    core_violations = [
        row["registry_id"]
        for row in rows
        if row["lifecycle_status"] == "active"
        and not all(row.get(k) for k in ("registry_id", "name", "official_url", "country"))
    ]

    return {
        "generated_at": result["built_at"],
        "source_observations": source_records,
        "master_universities": len(rows),
        "official_url_coverage": round(sum(1 for r in rows if r["official_url"]) / total, 4),
        "canonical_name_coverage": round(sum(1 for r in rows if r["name"]) / total, 4),
        "canonical_name_confirmed": round(sum(1 for r in rows if r["name_confirmed"]) / total, 4),
        "stable_id_coverage": round(
            sum(1 for r in rows if REGISTRY_ID_RE.match(r["registry_id"])) / total, 4
        ),
        "lifecycle": dict(lifecycle),
        "merged_source_records": source_records - len(rows),
        "renamed": flags.get("renamed", 0),
        "merged_predecessors": flags.get("merged_predecessor", 0),
        "unresolved_websites": sum(1 for r in rows if not r["official_url"]),
        "dedup_review_cases": (dedup_report or {}).get("review_cases"),
        "core_field_violations": core_violations,
        "flags": dict(flags),
        "review_required": [
            {
                "registry_id": r["registry_id"],
                "name": r["name"],
                "official_url": r["official_url"],
                "flags": [f for f in r["flags"] if f["severity"] in ("high", "medium")],
            }
            for r in rows
            if r["lifecycle_status"] != "active"
            or any(f["severity"] in ("high", "medium") for f in r["flags"])
        ],
    }


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="ProjectPathly — master registry build")
    parser.add_argument("--dedup", default="data/master/universities_dedup.json")
    # the same inputs as registry.master.dedup (German + international)
    parser.add_argument("--records", nargs="+", default=list(DEFAULT_INPUTS))
    parser.add_argument("--ids", default="data/master/id_registry.json")
    parser.add_argument("--dedup-report", default="data/reports/dedup_report.json")
    parser.add_argument("--out-dir", default="data/master")
    parser.add_argument("--report", default="data/reports/validation_report.json")
    parser.add_argument("--offline", action="store_true", help="No website lookups for names")
    parser.add_argument("--allow-degraded", action="store_true",
                        help="Write even if the discovery build is not production safe")
    args = parser.parse_args()

    if not reliability.production_gate("master build", args.allow_degraded):
        raise SystemExit(2)

    institutions = json.loads(Path(args.dedup).read_text(encoding="utf-8"))
    records = load_inputs(args.records)

    ids_path = Path(args.ids)
    id_registry = IdRegistry(
        json.loads(ids_path.read_text(encoding="utf-8")) if ids_path.exists() else None
    )

    site_texts = None if args.offline else make_site_texts(WebsiteResolver())
    # Stable IDs (§D5): which active IDs existed before this build
    existing_ids = {rid for rid, entry in id_registry.ids.items() if not entry.get("alias_of")}
    result = build(institutions, records, id_registry, site_texts)

    dedup_report_path = Path(args.dedup_report)
    dedup_report = (
        json.loads(dedup_report_path.read_text(encoding="utf-8"))
        if dedup_report_path.exists()
        else None
    )
    report = quality_report(result, len(records), dedup_report)
    report["discovery_build"] = reliability.build_summary()
    report["german_presence"] = result["presence"]["counts"]
    report["international_discovery_build"] = reliability.build_summary(reliability.INTL_BUILD_STATUS_PATH)
    report["online_de"] = result["online_de"]["counts"]
    report["market_access"] = result["online_de"]["market_access"]
    report["countries"] = dict(Counter(row["country"] for row in result["universities"]))
    report["stable_ids"] = stable_id_summary(existing_ids, result["universities"], id_registry)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    files = {
        "universities_de_master.json": result["universities"],
        "university_metadata.json": result["metadata"],
        "locations.json": result["locations"],
        "aliases.json": result["aliases"],
        "sources.json": result["sources"],
    }
    for filename, content in files.items():
        (out / filename).write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")

    ids_path.parent.mkdir(parents=True, exist_ok=True)
    ids_path.write_text(json.dumps(id_registry.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    presence_path = Path(args.report).parent / "presence_validation.json"
    presence_path.write_text(json.dumps(result["presence"], ensure_ascii=False, indent=2), encoding="utf-8")
    presence_path.with_name("presence_review.md").write_text(
        presence.review_markdown(result["presence"]), encoding="utf-8"
    )
    online_path = presence_path.with_name("online_de_validation.json")
    online_path.write_text(json.dumps(result["online_de"], ensure_ascii=False, indent=2), encoding="utf-8")
    online_path.with_name("online_de_review.md").write_text(
        online_de.review_markdown(result["online_de"]), encoding="utf-8"
    )

    print()
    print("=" * 62)
    print("PROJECTPATHLY MASTER REGISTRY")
    print("=" * 62)
    print(f"Source observations:      {report['source_observations']}")
    print(f"Master universities:      {report['master_universities']}")
    print(f"Official URL coverage:    {report['official_url_coverage'] * 100:.1f} %")
    print(f"Canonical name coverage:  {report['canonical_name_coverage'] * 100:.1f} %"
          f"  (confirmed by website: {report['canonical_name_confirmed'] * 100:.1f} %)")
    print(f"Stable ID coverage:       {report['stable_id_coverage'] * 100:.1f} %")
    for status, count in sorted(report["lifecycle"].items()):
        print(f"  {status:22s}  {count}")
    print(f"Merged source records:    {report['merged_source_records']}")
    print(f"Unresolved websites:      {report['unresolved_websites']}")
    print(f"Dedup review cases:       {report['dedup_review_cases']}")
    print(f"Review required:          {len(report['review_required'])}")
    print(f"Core field violations:    {len(report['core_field_violations'])}")
    ids = report["stable_ids"]
    print(f"Stable IDs:               {ids['kept']}/{ids['existing']} existing kept, {ids['new']} new, "
          f"{ids['merged']} merged, {len(ids['unlisted'])} unlisted")
    counts = result["presence"]["counts"]
    print(f"German presence:          {counts['confirmed']} confirmed, "
          f"{counts['not_present']} not present, {counts['review']} review")
    for warning in result["presence"]["decision_warnings"]:
        print(f"[WARN] presence decision {warning.get('registry_id')}: {warning['problem']}")
    online = result["online_de"]["counts"]
    access = result["online_de"]["market_access"]
    print(f"Online from Germany:      {online['confirmed']} confirmed, {online['review']} review, "
          f"{online['not_available']} not available, {online['not_assessed']} not assessed")
    print(f"Market access:            {access['physical_de']} physical_de, {access['online_de']} online_de, "
          f"{access['both']} both, {access['none']} none")
    for warning in result["online_de"]["decision_warnings"]:
        print(f"[WARN] online_de decision {warning.get('registry_id')}: {warning['problem']}")
    print("-" * 62)


if __name__ == "__main__":
    main()
