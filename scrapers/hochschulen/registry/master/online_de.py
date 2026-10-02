"""
v1.3: online availability for students in Germany, and market access.

    online_de_status
        not_assessed    German institution from the state sources; its online
                        programmes belong to the later programme scraper (§C2)
        review          international discovery candidate (ETER/IPEDS); a
                        discovery signal is never a confirmation
        confirmed       reviewed decision with BOTH official evidence URLs:
                        a complete degree can be studied fully online, and a
                        student residing in Germany can enrol
        not_available   reviewed decision: one of the two is officially not met

    market_access   what ProjectPathly may present as available to users
        physical_de     german_physical_presence is true
        online_de       online_de_status is confirmed

Discovery candidates therefore start with market_access = [].
Decisions live in data/master/online_de_decisions.yaml (key: registry_id).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

from registry.international.base import is_international


DECISIONS_PATH = Path("data/master/online_de_decisions.yaml")

STATUSES = ("confirmed", "not_available", "review", "not_assessed")
DECIDABLE = ("confirmed", "not_available", "review")
EVIDENCE_KEYS = ("degree_evidence_url", "eligibility_evidence_url", "recognition_evidence_url")


def _url(value) -> bool:
    return str(value or "").startswith(("http://", "https://"))


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
    status = decision.get("status")
    if status not in DECIDABLE:
        return f"status must be one of {', '.join(DECIDABLE)}"
    if status == "confirmed" and not (
        _url(decision.get("degree_evidence_url")) and _url(decision.get("eligibility_evidence_url"))
    ):
        return "confirmed needs degree_evidence_url AND eligibility_evidence_url (official pages)"
    if status == "not_available" and not (
        _url(decision.get("degree_evidence_url")) or _url(decision.get("eligibility_evidence_url"))
    ):
        return "not_available needs the official page that shows the restriction"
    return None


def discovery_sources(row: dict) -> list[str]:
    return [s for s in row.get("listed_by") or [] if is_international(s)]


def apply(universities: list[dict], decisions: list[dict] | None = None, now: str | None = None) -> dict:
    """
    Adds online_de_status, online_de_basis, online_de_evidence and
    market_access to every row (german_physical_presence must be set
    already). Returns the report.
    """
    now = now or datetime.now(timezone.utc).isoformat()
    known = {row["registry_id"] for row in universities}

    by_id, warnings = {}, []
    for index, decision in enumerate(decisions or []):
        problem = check_decision(decision, known)
        if problem:
            warnings.append({"decision": index, "registry_id": (decision or {}).get("registry_id"),
                             "problem": problem})
        elif decision["registry_id"] in by_id:
            warnings.append({"decision": index, "registry_id": decision["registry_id"],
                             "problem": "more than one decision; the first one is used"})
        else:
            by_id[decision["registry_id"]] = decision

    review, confirmed, not_available = [], [], []

    for row in universities:
        sources = discovery_sources(row)
        decision = by_id.get(row["registry_id"])

        if decision:
            status = decision["status"]
            basis = "manual_review"
            evidence = {k: decision[k] for k in EVIDENCE_KEYS if _url(decision.get(k))}
            evidence.update({k: decision[k] for k in ("checked_at", "note") if decision.get(k)})
        elif sources:
            status = "review"
            basis = "discovery_candidate: " + ", ".join(sources)
            evidence = {}
        else:
            status = "not_assessed"
            basis = "german_state_source"
            evidence = {}

        access = []
        if row.get("german_physical_presence") is True:
            access.append("physical_de")
        if status == "confirmed":
            access.append("online_de")

        row["online_de_status"] = status
        row["online_de_basis"] = basis
        row["online_de_evidence"] = evidence
        row["market_access"] = access

        entry = {
            "registry_id": row["registry_id"],
            "name": row["name"],
            "country": row.get("country"),
            "official_url": row.get("official_url"),
            "discovery_sources": sources,
            "online_de_status": status,
            "evidence": evidence,
        }
        if status == "review":
            review.append(entry)
        elif status == "confirmed":
            confirmed.append(entry)
        elif status == "not_available":
            not_available.append(entry)

    access_counts = {"physical_de": 0, "online_de": 0, "both": 0, "none": 0}
    for row in universities:
        a = set(row["market_access"])
        key = "both" if len(a) == 2 else (next(iter(a)) if a else "none")
        access_counts[key] += 1

    return {
        "generated_at": now,
        "decision_warnings": warnings,
        "counts": {s: sum(1 for r in universities if r["online_de_status"] == s) for s in STATUSES},
        "market_access": access_counts,
        "confirmed": confirmed,
        "not_available": not_available,
        "review": review,
    }


def review_markdown(report: dict) -> str:
    lines = [
        "# Online aus Deutschland — offene Fälle",
        "",
        f"Stand: {report['generated_at']}  ",
        f"Bestätigt: {report['counts']['confirmed']}, nicht verfügbar: "
        f"{report['counts']['not_available']}, zu prüfen: {report['counts']['review']}",
        "",
        "Entscheidungen gehören nach `data/master/online_de_decisions.yaml` (unter "
        "`decisions:`). `confirmed` braucht zwei offizielle Belege: "
        "`degree_evidence_url` (ein vollständiger Abschluss ist komplett online "
        "studierbar) und `eligibility_evidence_url` (Zulassung mit Wohnsitz in "
        "Deutschland möglich). „International students welcome“ allein reicht "
        "nicht, wenn anderswo Länderbeschränkungen stehen.",
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
            f"Land: {entry['country']}  ",
            f"Website: {entry['official_url'] or '—'}  ",
            f"Gefunden über: {', '.join(entry['discovery_sources']) or '—'}",
            "",
            "```yaml",
            f"  - registry_id: {entry['registry_id']}",
            "    status: review              # confirmed | not_available | review",
            "    degree_evidence_url: https://",
            "    eligibility_evidence_url: https://",
            "    recognition_evidence_url: https://   # optional: anabin H+, DAPIP, DEQAR",
            f"    checked_at: {report['generated_at'][:10]}",
            "    note: \"\"",
            "```",
            "",
        ]
    if not report["review"]:
        lines.append("Keine offenen Fälle.")
    return "\n".join(lines) + "\n"
