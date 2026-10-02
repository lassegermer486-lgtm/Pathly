"""
v1.3: German physical presence.

Question: does the institution currently have at least one active physical
educational location in Germany? Not: does the organisation still exist
somewhere, and not: does it teach online.

Every German observation of an institution gets a status:

    active      the current official state source lists it and the
                institution's website is verified, no doubt signal
    uncertain   listed, but the evidence is not enough (see DOUBTS)
    closed      only by a reviewed decision with an evidence URL
    moved       only by a reviewed decision with an evidence URL

Observations are the city-level rows of locations.json and, for a state
that lists the institution without a city, the state listing itself.
Nothing is deleted: closed and moved locations stay in locations.json.

    german_physical_presence = any observation active        -> true
                               all closed or moved           -> false
                               otherwise                     -> null (review)

The automatic rules never conclude "no presence": negative statements need a
person and an official source (data/master/presence_decisions.yaml).

This is the registry's preliminary classification. The basis of every status
says where it comes from, so the later site scraper (Scraper 2) can confirm
or correct it with campus data without losing this provenance:

    state_source_and_verified_website                 city-level location from a state source
    state_listing_without_city_and_verified_website   only the state listing, no address
    insufficient_evidence: <doubts>                   automatic, uncertain
    manual_review                                     presence_decisions.yaml
    no_german_source_listing                          no German state source lists it (an
                                                      international discovery candidate);
                                                      a signal, NOT evidence of absence

Only German observations count: locations in Germany and listings by German
state sources ("DE-XX"). International discovery namespaces in listed_by
("INTL-ETER", "INTL-IPEDS") and locations abroad are not German observations.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

from registry.enrichment.website_resolver import fold


DECISIONS_PATH = Path("data/master/presence_decisions.yaml")

LOCATION_STATUSES = ("active", "closed", "moved", "uncertain")

# Institution-level signals that the state listing alone is not enough.
DOUBTS = {
    "no_verified_website": "no verified official website",
    "agent_reports_closed": "agent reports the institution as closed (not authoritative)",
    "agent_reports_merger_unverified": "agent reports a merger that could not be verified",
    "merged_into_other_institution": "only known as predecessor of another institution",
    "possibly_foreign_institution": "website of a foreign institution",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ----------------------------------------------------------------------
# Decisions (human review)
# ----------------------------------------------------------------------

def load_decisions(path: Path = DECISIONS_PATH) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return list(data.get("decisions") or [])


def check_decision(decision: dict, known_ids: set[str]) -> str | None:
    """Reason why a decision cannot be used, or None."""
    if not isinstance(decision, dict):
        return "not a mapping"
    if decision.get("registry_id") not in known_ids:
        return f"unknown registry_id {decision.get('registry_id')!r}"
    if decision.get("status") not in LOCATION_STATUSES:
        return f"status must be one of {', '.join(LOCATION_STATUSES)}"
    if not str(decision.get("evidence_url") or "").startswith(("http://", "https://")):
        return "evidence_url (official source) is required"
    return None


def _matches(decision: dict, state: str | None, city: str | None) -> bool:
    if decision.get("state") and decision["state"] != state:
        return False
    if decision.get("city"):
        return bool(city) and fold(decision["city"]) == fold(city)
    return True


# ----------------------------------------------------------------------
# Automatic evidence
# ----------------------------------------------------------------------

def doubts(row: dict, members: list[dict]) -> list[str]:
    """Doubt signals of one master row (row["flags"] already computed)."""
    found = []

    if not row.get("official_url"):
        found.append("no_verified_website")

    statuses = []
    for member in members:
        agent = (member.get("website_resolution") or {}).get("agent") or {}
        answer = agent.get("answer") or {}
        accepted = bool((agent.get("validation") or {}).get("accepted"))
        statuses.append((answer.get("lifecycle_status"), accepted))

    if any(status == "closed" for status, _ in statuses):
        found.append("agent_reports_closed")
    if any(status == "merged" and not accepted for status, accepted in statuses):
        found.append("agent_reports_merger_unverified")
    # Successor and predecessor in one cluster is the normal case (dedup);
    # a cluster of predecessors only means the successor is elsewhere.
    if members and all(status == "merged" and accepted for status, accepted in statuses):
        found.append("merged_into_other_institution")

    if any(f.get("code") == "possibly_foreign_institution" for f in row.get("flags") or []):
        found.append("possibly_foreign_institution")

    return found


def is_german_state(state: str | None) -> bool:
    return bool(state) and re.fullmatch(r"DE-[A-Z]{2}", state) is not None


def _automatic(row_doubts: list[str]) -> tuple[str, str]:
    if row_doubts:
        return "uncertain", "insufficient_evidence: " + ", ".join(row_doubts)
    return "active", "state_source_and_verified_website"


# ----------------------------------------------------------------------
# Apply
# ----------------------------------------------------------------------

def derive(statuses: list[str]) -> tuple[bool | None, str]:
    """(german_physical_presence, presence_status) from observation statuses."""
    if "active" in statuses:
        return True, "confirmed"
    if statuses and all(s in ("closed", "moved") for s in statuses):
        return False, "not_present"
    return None, "review"


def apply(
    universities: list[dict],
    locations: list[dict],
    sources: list[dict],
    row_doubts: dict[str, list[str]],
    decisions: list[dict] | None = None,
    now: str | None = None,
) -> dict:
    """
    Adds to every location row: country, location_status,
    location_status_basis, location_status_evidence_url; to every
    university row: german_physical_presence, presence_status,
    presence_basis. Returns the presence report.
    """
    now = now or _now()
    known = {row["registry_id"] for row in universities}

    usable, warnings = [], []
    for index, decision in enumerate(decisions or []):
        problem = check_decision(decision, known)
        if problem:
            warnings.append({"decision": index, "registry_id": (decision or {}).get("registry_id"),
                             "problem": problem})
        else:
            usable.append(decision)

    by_id: dict[str, list[dict]] = {}
    for decision in usable:
        by_id.setdefault(decision["registry_id"], []).append(decision)

    locations_by_id: dict[str, list[dict]] = {}
    for location in locations:
        locations_by_id.setdefault(location["registry_id"], []).append(location)

    source_by_state: dict[tuple[str, str], dict] = {}
    for source in sources:
        source_by_state.setdefault((source["registry_id"], source.get("source_state")), source)

    used = set()
    review, not_present, no_german_listing = [], [], []

    def decide(registry_id, state, city):
        # The most specific matching decision wins (city > state > institution).
        candidates = [d for d in by_id.get(registry_id, []) if _matches(d, state, city)]
        if not candidates:
            return None
        decision = max(candidates, key=lambda d: (bool(d.get("city")), bool(d.get("state"))))
        used.add(id(decision))
        return decision

    for row in universities:
        registry_id = row["registry_id"]
        auto_status, auto_basis = _automatic(row_doubts.get(registry_id, []))
        observations = []

        def observe(kind, state, city, evidence_url):
            decision = decide(registry_id, state, city)
            if decision:
                status, basis = decision["status"], "manual_review"
                evidence_url = decision["evidence_url"]
            else:
                status, basis = auto_status, auto_basis
                if kind == "state_listing" and status == "active":
                    basis = "state_listing_without_city_and_verified_website"
            observation = {
                "kind": kind, "state": state, "city": city,
                "location_status": status, "basis": basis, "evidence_url": evidence_url,
            }
            if decision:
                observation.update({k: decision[k] for k in ("note", "moved_to", "checked_at") if decision.get(k)})
            observations.append(observation)
            return observation

        covered = set()
        for location in locations_by_id.get(registry_id, []):
            location.setdefault("country", "DE")
            if location["country"] != "DE" or not is_german_state(location.get("source_state")):
                # A seat abroad (international discovery): not a German observation.
                location["location_status"] = "uncertain"
                location["location_status_basis"] = "outside_germany_not_validated"
                location["location_status_evidence_url"] = None
                continue
            covered.add(location.get("source_state"))
            observation = observe("location", location.get("state") or location.get("source_state"),
                                  location.get("city"), location.get("source_url"))
            location["location_status"] = observation["location_status"]
            location["location_status_basis"] = observation["basis"]
            location["location_status_evidence_url"] = observation["evidence_url"]

        # States that list the institution without a city: the listing itself.
        for state in row.get("listed_by") or []:
            if state in covered or not is_german_state(state):
                continue
            source = source_by_state.get((registry_id, state)) or {}
            observe("state_listing", state, None, source.get("source_url"))

        presence, status = derive([o["location_status"] for o in observations])
        if status == "confirmed":
            active = [o for o in observations if o["location_status"] == "active"]
            basis = "manual_review" if all(o["basis"] == "manual_review" for o in active) else active[0]["basis"]
        elif status == "not_present":
            basis = "manual_review"
        elif not observations:
            # Absence from the German sources is not evidence of absence.
            basis = "no_german_source_listing"
        else:
            basis = "uncertain_locations"

        row["german_physical_presence"] = presence
        row["presence_status"] = status
        row["presence_basis"] = basis

        entry = {
            "registry_id": registry_id,
            "name": row["name"],
            "official_url": row.get("official_url"),
            "listed_by": row.get("listed_by") or [],
            "doubts": [{"code": d, "detail": DOUBTS.get(d, d)} for d in row_doubts.get(registry_id, [])],
            "observations": observations,
        }
        if basis == "no_german_source_listing":
            no_german_listing.append(row["registry_id"])
        elif status == "review":
            review.append(entry)
        elif status == "not_present":
            not_present.append(entry)

    unused = [d for d in usable if id(d) not in used]
    for decision in unused:
        warnings.append({"registry_id": decision["registry_id"],
                         "problem": "matches no German location of this institution",
                         "city": decision.get("city"), "state": decision.get("state")})

    location_counts = {s: 0 for s in LOCATION_STATUSES}
    abroad = 0
    for location in locations:
        if location.get("location_status_basis") == "outside_germany_not_validated":
            abroad += 1
        else:
            location_counts[location["location_status"]] += 1

    return {
        "generated_at": now,
        "decisions_used": len(usable) - len(unused),
        "decision_warnings": warnings,
        "counts": {
            "institutions": len(universities),
            "confirmed": sum(1 for r in universities if r["presence_status"] == "confirmed"),
            "not_present": len(not_present),
            # German observations that need a decision
            "review": len(review),
            # international candidates, presence not assessed (null / review)
            "no_german_source_listing": len(no_german_listing),
        },
        "location_status": location_counts,
        "locations_outside_germany": abroad,
        "not_present": not_present,
        "review": review,
        "no_german_source_listing": no_german_listing,
    }


# ----------------------------------------------------------------------
# Review list with ready-made entries
# ----------------------------------------------------------------------

def review_markdown(report: dict) -> str:
    lines = [
        "# Präsenz in Deutschland — offene Fälle",
        "",
        f"Stand: {report['generated_at']}  ",
        f"Bestätigt: {report['counts']['confirmed']}, "
        f"nicht mehr in Deutschland: {report['counts']['not_present']}, "
        f"zu prüfen: {report['counts']['review']}",
        "",
        "Entscheidungen gehören nach `data/master/presence_decisions.yaml` "
        "(unter `decisions:`). `evidence_url` ist Pflicht: eine offizielle Seite, "
        "die den Status belegt (Standortseite, Impressum, Schließungs- oder "
        "Umzugsmitteilung). Eine erreichbare Website allein belegt nichts.",
        "",
    ]

    for problem in report["decision_warnings"]:
        lines.append(f"- WARNUNG Entscheidung {problem.get('registry_id')}: {problem['problem']}")
    if report["decision_warnings"]:
        lines.append("")

    for entry in report["review"]:
        lines += [
            f"## {entry['name']} ({entry['registry_id']})",
            "",
            f"Website: {entry['official_url'] or '—'}  ",
            f"Gelistet von: {', '.join(entry['listed_by']) or '—'}",
            "",
        ]
        for doubt in entry["doubts"]:
            lines.append(f"- {doubt['detail']}")
        lines += ["", "```yaml"]
        for observation in entry["observations"]:
            place = f"city: {observation['city']}" if observation["city"] else f"state: {observation['state']}"
            lines += [
                f"  - registry_id: {entry['registry_id']}",
                f"    {place}",
                "    status: active        # active | closed | moved | uncertain",
                "    evidence_url: https://",
                "    note: \"\"",
                f"    checked_at: {report['generated_at'][:10]}",
            ]
        lines += ["```", ""]

    if not report["review"]:
        lines.append("Keine offenen Fälle.")

    return "\n".join(lines) + "\n"
