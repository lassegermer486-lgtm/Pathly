"""
Nationwide deduplication of the enriched state records (spec §25–§30).

Several state sources list the same institution ("HSD Hochschule Döpfer
GmbH" in Brandenburg, "HSD Hochschule Döpfer" in NRW). This step groups
records into institutions without losing anything: every source name,
location and source of every member is kept.

Rules, strongest first:

    overrides.yaml        merge / keep_separate, always win
    same verified site
      + related names     AUTO MERGE   (rule 1: same name, rule 2: variant)
      + unrelated names   REVIEW       (portal pages, mergers)
    same name, other or
      unverified site     REVIEW       (rule 3)
    same name apart from
      a location suffix   REVIEW       (rule 5)
    similar names only    KEEP SEPARATE (rule 4)

"Related" means: same name, same name without a location suffix
("... in Gera", ", Campus Hamburg"), a shared acronym written in the
name, or the distinctive words of one name contained in the other.
Generic words (Hochschule, Evangelische, Wirtschaft, ...) and cities
never count as evidence, so "Evangelische Hochschule Berlin" and
"Evangelische Hochschule Dresden" stay apart.

A canonical name confirmed by the agent resolver counts as an alias
(e.g. BTK -> "University of Europe for Applied Sciences").

Usage (from scrapers/hochschulen/):

    python -m registry.master.dedup
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from urllib.parse import urlsplit

import yaml

from registry.enrichment.website_resolver import (
    NAME_SEPARATOR_RE,
    NON_DISTINCTIVE,
    core_name,
    explicit_acronyms,
    fold,
)
from registry.normalize import domain_key
from registry.utils.matching import STOPWORDS


# Explicit location suffixes. A bare trailing city is NOT stripped:
# "Hochschule für Musik und Theater Hamburg" and "... München" are
# different institutions.
LOCATION_SUFFIX_RE = re.compile(
    r"(?:"
    r"\s+in\s+(?P<a>[\w\-. ]+)"
    r"|,?\s+[-–]?\s*(?:Campus|Standort)\s+(?P<b>[\w\-. ]+)"
    r"|,\s*(?P<c>[\w\-. ]+)"
    r")$",
    re.IGNORECASE,
)

MAX_SIMILAR_REPORTED = 50


# ----------------------------------------------------------------------
# Record features
# ----------------------------------------------------------------------

def record_key(record: dict) -> str:
    """Stable reference used in overrides.yaml: "DE-BB|HSD Hochschule Döpfer GmbH"."""
    return f"{record['state']}|{record['name']}"


def name_key(name: str) -> str:
    """Folded core name without filler words."""
    return " ".join(t for t in fold(core_name(name)).split() if t not in STOPWORDS)


def base_name_key(name: str, known_cities: frozenset[str]) -> str | None:
    """
    Name without an explicit location suffix, or None if there is none:
    "SRH University of Applied Sciences Heidelberg in Gera" -> "...Heidelberg".
    """
    core = core_name(name)
    match = LOCATION_SUFFIX_RE.search(core)

    if not match:
        return None

    place = next(group for group in match.groups() if group)

    # ", Polizei und Rechtspflege" is not a location.
    parts = [place, *re.split(r"[\s/]+", place)]
    if not any(fold(part) in known_cities for part in parts):
        return None

    base = core[: match.start()].strip(" ,-–")
    return name_key(base) or None


def distinctive_tokens(name: str, known_cities: frozenset[str]) -> set[str]:
    return {
        token
        for token in name_key(name).split()
        if token not in NON_DISTINCTIVE and token not in known_cities
    }


def is_generic(key: str | None) -> bool:
    return not key or all(t in NON_DISTINCTIVE for t in key.split())


def record_names(record: dict) -> list[str]:
    """Source name plus a canonical name the agent resolver verified."""
    names = [record["name"]]
    agent = (record.get("website_resolution") or {}).get("agent") or {}

    if (agent.get("validation") or {}).get("accepted"):
        canonical = (agent.get("answer") or {}).get("canonical_name")
        if canonical and canonical not in names:
            names.append(canonical)

    return names


def comparison_names(record: dict) -> list[str]:
    """
    record_names plus the parts of a name around a separator:
    "NORDAKADEMIE Hochschule der Wirtschaft | Graduate School"
    -> also "NORDAKADEMIE Hochschule der Wirtschaft", "Graduate School".
    """
    names = []
    for name in record_names(record):
        for variant in (name, *NAME_SEPARATOR_RE.split(core_name(name))):
            if variant not in names:
                names.append(variant)
    return names


def verified_site(record: dict) -> str | None:
    resolution = record.get("website_resolution") or {}

    if resolution.get("status") != "resolved" or not record.get("official_url"):
        return None

    return domain_key(record["official_url"])


# ----------------------------------------------------------------------
# Pair rules
# ----------------------------------------------------------------------

def names_related(a: dict, b: dict, known_cities: frozenset[str]) -> str | None:
    """Evidence that two records name the same institution, or None."""
    for name_a in comparison_names(a):
        for name_b in comparison_names(b):
            key_a, key_b = name_key(name_a), name_key(name_b)

            if is_generic(key_a) or is_generic(key_b):
                continue  # "Graduate School" alone says nothing

            if key_a == key_b:
                return "same_name"

            base_a = base_name_key(name_a, known_cities) or key_a
            base_b = base_name_key(name_b, known_cities) or key_b
            if base_a == base_b and not is_generic(base_a):
                return "same_name_without_location"

            acronyms_a = {fold(x) for x in explicit_acronyms(name_a)}
            acronyms_b = {fold(x) for x in explicit_acronyms(name_b)}
            shared = acronyms_a & acronyms_b
            if shared:
                return f"shared_acronym:{sorted(shared)[0]}"

            tokens_a = distinctive_tokens(name_a, known_cities)
            tokens_b = distinctive_tokens(name_b, known_cities)
            smaller, larger = sorted((tokens_a, tokens_b), key=len)
            if smaller and smaller <= larger:
                return f"distinctive_words:{','.join(sorted(smaller))}"

    return None


def evaluate_pair(a: dict, b: dict, known_cities: frozenset[str]) -> dict | None:
    """Decision for one pair: auto_merge, review, keep_separate or None."""
    site_a, site_b = verified_site(a), verified_site(b)
    key_a, key_b = name_key(a["name"]), name_key(b["name"])

    if site_a and site_a == site_b:
        evidence = names_related(a, b, known_cities)

        if evidence == "same_name":
            return {"decision": "auto_merge", "rule": "rule_1_same_name_same_site", "evidence": evidence}
        if evidence:
            return {"decision": "auto_merge", "rule": "rule_2_name_variant_same_site", "evidence": evidence}
        return {"decision": "review", "rule": "same_site_unrelated_names", "evidence": site_a}

    if key_a == key_b:
        return {
            "decision": "review",
            "rule": "rule_3_same_name_different_site" if site_a and site_b else "rule_3_same_name_unverified_site",
            "evidence": key_a,
        }

    base_a = base_name_key(a["name"], known_cities)
    base_b = base_name_key(b["name"], known_cities)
    if (base_a or key_a) == (base_b or key_b) and not is_generic(base_a or base_b):
        return {"decision": "review", "rule": "rule_5_location_suffix", "evidence": base_a or base_b}

    tokens_a = distinctive_tokens(a["name"], known_cities)
    tokens_b = distinctive_tokens(b["name"], known_cities)

    # A written acronym is a strong signal (spec rule 4: "sofern keine
    # weiteren starken Identitätssignale existieren"), but only together
    # with another shared word: "HTW" alone joins Berlin, Dresden, Saar.
    acronyms = (
        {fold(x) for x in explicit_acronyms(a["name"])}
        & {fold(x) for x in explicit_acronyms(b["name"])}
    )
    if acronyms and (tokens_a & tokens_b) - acronyms:
        return {
            "decision": "review",
            "rule": "shared_acronym_different_site",
            "evidence": sorted(acronyms),
        }

    smaller, larger = sorted((tokens_a, tokens_b), key=len)
    if len(smaller) >= 2 and smaller <= larger:
        return {"decision": "keep_separate", "rule": "rule_4_similar_name_different_site", "evidence": sorted(smaller)}

    return None


# ----------------------------------------------------------------------
# Overrides and clustering
# ----------------------------------------------------------------------

def load_overrides(path: Path) -> dict:
    if not path.exists():
        return {"merge": [], "keep_separate": []}

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    return {
        "merge": [list(group) for group in data.get("merge") or []],
        "keep_separate": [list(group) for group in data.get("keep_separate") or []],
    }


class Clusters:
    """Union-find that refuses unions across a keep_separate pair."""

    def __init__(self, keys: list[str], keep_separate: set[frozenset[str]]):
        self.parent = {key: key for key in keys}
        self.keep_separate = keep_separate

    def find(self, key: str) -> str:
        while self.parent[key] != key:
            self.parent[key] = self.parent[self.parent[key]]
            key = self.parent[key]
        return key

    def members(self, root: str) -> list[str]:
        return [key for key in self.parent if self.find(key) == root]

    def union(self, a: str, b: str) -> bool:
        root_a, root_b = self.find(a), self.find(b)

        if root_a == root_b:
            return True

        for x in self.members(root_a):
            for y in self.members(root_b):
                if frozenset((x, y)) in self.keep_separate:
                    return False

        self.parent[root_b] = root_a
        return True

    def groups(self) -> list[list[str]]:
        result = defaultdict(list)
        for key in self.parent:
            result[self.find(key)].append(key)
        return list(result.values())


def deduplicate(records: list[dict], overrides: dict) -> tuple[list[dict], dict]:
    by_key = {record_key(r): r for r in records}

    known_cities = frozenset(
        fold(location["city"])
        for record in records
        for location in record.get("locations") or []
        if location.get("city")
    )

    keep_separate = set()
    unknown_keys = set()

    for group in overrides["keep_separate"]:
        unknown_keys |= {key for key in group if key not in by_key}
        for x, y in combinations(group, 2):
            keep_separate.add(frozenset((x, y)))

    clusters = Clusters(list(by_key), keep_separate)
    merge_evidence = defaultdict(list)
    review, similar, conflicts = [], [], []
    rule_counts = Counter()

    # 1. Manual merges.
    for group in overrides["merge"]:
        missing = [key for key in group if key not in by_key]
        unknown_keys |= set(missing)
        group = [key for key in group if key in by_key]

        for x, y in zip(group, group[1:]):
            if clusters.union(x, y):
                merge_evidence[x].append({"a": x, "b": y, "rule": "override_merge"})
                rule_counts["override_merge"] += 1
            else:
                conflicts.append({"a": x, "b": y, "reason": "merge_and_keep_separate"})

    # 2. Automatic rules for every pair.
    keys = list(by_key)
    for x, y in combinations(keys, 2):
        if frozenset((x, y)) in keep_separate:
            rule_counts["override_keep_separate"] += 1
            continue

        result = evaluate_pair(by_key[x], by_key[y], known_cities)
        if result is None:
            continue

        pair = {"a": x, "b": y, **result}

        if result["decision"] == "auto_merge":
            if clusters.union(x, y):
                merge_evidence[x].append(pair)
                rule_counts[result["rule"]] += 1
            else:
                conflicts.append({**pair, "reason": "blocked_by_keep_separate"})

        elif result["decision"] == "review":
            review.append(pair)

        elif result["decision"] == "keep_separate":
            similar.append(pair)
            rule_counts[result["rule"]] += 1

    # Review pairs that ended up in one cluster anyway are settled.
    review = [p for p in review if clusters.find(p["a"]) != clusters.find(p["b"])]
    for pair in review:
        rule_counts[pair["rule"]] += 1

    institutions = [
        build_institution([by_key[key] for key in sorted(group)], merge_evidence)
        for group in clusters.groups()
    ]
    institutions.sort(key=lambda inst: inst["members"][0])

    for pair in review:
        pair["a_url"] = by_key[pair["a"]].get("official_url")
        pair["b_url"] = by_key[pair["b"]].get("official_url")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_records": len(records),
        "institutions": len(institutions),
        "merged_institutions": sum(1 for inst in institutions if len(inst["members"]) > 1),
        "records_merged_away": len(records) - len(institutions),
        "rules": dict(rule_counts),
        "review_cases": len(review),
        "conflicts": conflicts,
        "unknown_override_keys": sorted(unknown_keys),
        "merged": [
            {
                "members": inst["members"],
                "official_url": inst["official_url"],
                "evidence": inst["merge_evidence"],
            }
            for inst in institutions
            if len(inst["members"]) > 1
        ],
        "review": review,
        "kept_separate_similar": similar[:MAX_SIMILAR_REPORTED],
    }

    return institutions, report


# ----------------------------------------------------------------------
# Merge (spec §30: nothing gets lost)
# ----------------------------------------------------------------------

def choose_official_url(verified_members: list[dict]) -> str | None:
    """
    The site most members point to; on a tie the institution's own site
    (its imprint names it) beats a portal page about it, e.g.
    isba.eu over studieren-in-schwerin.de/hochschulen/isba.
    """
    if not verified_members:
        return None

    sites = Counter(domain_key(m["official_url"]) for m in verified_members)

    def rank(member):
        resolution = member.get("website_resolution") or {}
        evidence = (resolution.get("identity") or {}).get("evidence") or []
        url = member["official_url"]
        return (
            sites[domain_key(url)],
            "name_in_imprint" in evidence,
            -urlsplit(url).path.count("/"),
            -len(url),
        )

    return max(verified_members, key=rank)["official_url"]


def build_institution(members: list[dict], merge_evidence: dict) -> dict:
    keys = [record_key(m) for m in members]

    verified = [m["official_url"] for m in members if verified_site(m)]
    official_url = choose_official_url([m for m in members if verified_site(m)])

    locations, seen = [], set()
    for member in members:
        for location in member.get("locations") or []:
            identity = (
                location.get("name"), location.get("city"),
                location.get("postal_code"), location.get("street"),
                location.get("state") or member["state"],
            )
            if identity in seen:
                continue
            seen.add(identity)
            locations.append({
                **location,
                "state": location.get("state") or member["state"],
                "source_record": record_key(member),
            })

    names = []
    for member in members:
        for name in record_names(member):
            if name not in names:
                names.append(name)

    return {
        "cluster_id": "dedup-" + hashlib.sha1("\n".join(keys).encode("utf-8")).hexdigest()[:12],
        "members": keys,
        "names": names,
        "official_url": official_url,
        "official_urls": sorted(set(verified)),
        "website_status": "resolved" if verified else "open",
        "source_states": sorted({m["state"] for m in members}),
        "locations": locations,
        "sources": [
            {**(m.get("source") or {}), "state": m["state"], "source_record": record_key(m)}
            for m in members
        ],
        "metadata": [
            {
                "source_record": record_key(m),
                "institution_type": m.get("institution_type"),
                "ownership": m.get("ownership"),
                "recognition_status": m.get("recognition_status"),
            }
            for m in members
        ],
        "lifecycle_hints": [
            {
                "source_record": record_key(m),
                "lifecycle_status": agent["answer"].get("lifecycle_status"),
                "canonical_name": agent["answer"].get("canonical_name"),
                "accepted": agent["validation"].get("accepted"),
            }
            for m in members
            if (agent := (m.get("website_resolution") or {}).get("agent"))
        ],
        "website_flags": sorted({
            flag
            for m in members
            for flag in (m.get("website_resolution") or {}).get("flags") or []
        }),
        "merge_evidence": [e for key in keys for e in merge_evidence.get(key, [])],
    }


# ----------------------------------------------------------------------
# Review list for humans (spec §29: decisions go into overrides.yaml)
# ----------------------------------------------------------------------

def review_markdown(report: dict) -> str:
    lines = [
        "# Dedup review",
        "",
        f"{report['review_cases']} cases. Decide each one by adding the pair to",
        "`data/master/overrides.yaml` under `merge:` or `keep_separate:`,",
        "then run `python -m registry.master.dedup` again.",
        "",
    ]

    for number, pair in enumerate(report["review"], 1):
        lines += [
            f"## {number}. {pair['rule']}",
            "",
            f"- `{pair['a']}` — {pair['a_url'] or 'no URL'}",
            f"- `{pair['b']}` — {pair['b_url'] or 'no URL'}",
            f"- Evidence: {pair['evidence']}",
            "",
            "```yaml",
            f'  - ["{pair["a"]}", "{pair["b"]}"]',
            "```",
            "",
        ]

    if report["conflicts"]:
        lines += ["## Conflicts", ""]
        lines += [f"- `{c['a']}` / `{c['b']}`: {c['reason']}" for c in report["conflicts"]]
        lines.append("")

    if report["unknown_override_keys"]:
        lines += ["## Override keys that match no record", ""]
        lines += [f"- `{key}`" for key in report["unknown_override_keys"]]
        lines.append("")

    return "\n".join(lines)


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="ProjectPathly — nationwide deduplication")
    parser.add_argument("--in", dest="input", default="data/enriched/universities_de_urls.json")
    parser.add_argument("--overrides", default="data/master/overrides.yaml")
    parser.add_argument("--out", default="data/master/universities_dedup.json")
    parser.add_argument("--report", default="data/reports/dedup_report.json")
    parser.add_argument("--review", default="data/reports/review_report.md")
    args = parser.parse_args()

    records = json.loads(Path(args.input).read_text(encoding="utf-8"))
    overrides = load_overrides(Path(args.overrides))

    institutions, report = deduplicate(records, overrides)

    for path, content in (
        (args.out, json.dumps(institutions, ensure_ascii=False, indent=2)),
        (args.report, json.dumps(report, ensure_ascii=False, indent=2)),
        (args.review, review_markdown(report)),
    ):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(content, encoding="utf-8")

    print()
    print("=" * 62)
    print("PROJECTPATHLY — DEDUPLICATION")
    print("=" * 62)
    print(f"SOURCE RECORDS:   {report['source_records']}")
    print(f"INSTITUTIONS:     {report['institutions']}")
    print(f"MERGED GROUPS:    {report['merged_institutions']}")
    print(f"REVIEW CASES:     {report['review_cases']}")
    print(f"CONFLICTS:        {len(report['conflicts'])}")
    for rule, count in sorted(report["rules"].items()):
        print(f"  {rule:40s}{count}")
    print(f"OUTPUT:           {args.out}")
    print(f"REPORT:           {args.report}")
    print(f"REVIEW LIST:      {args.review}")
    print("-" * 62)


if __name__ == "__main__":
    main()
