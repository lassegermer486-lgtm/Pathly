"""
Agent resolver: last resort for records the deterministic website
resolver could not settle (status "unresolved" or "review").

    enriched record
        -> OpenRouter (LLM with web search) -> structured answer
        -> technical check -> identity check   (same code as website_resolver)
        -> accept as "agent_verified", or keep in review with the suggestion

The agent is a resolver, not a source of truth. Its URL is accepted only
when the website itself confirms the institution. Answers are cached in
data/enriched/agent_cache.json so reruns cost nothing and stay stable.

The API key is read from the environment (OPENROUTER_API_KEY), or from a
local .env file that is never committed.

Usage (from scrapers/hochschulen/):

    python -m registry.enrichment.agent_resolver --dry-run
    python -m registry.enrichment.agent_resolver --limit 1
    python -m registry.enrichment.agent_resolver
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import requests

from registry.enrichment.website_resolver import (
    HIGH_CONFIDENCE,
    WebsiteResolver,
    identity_dict,
    site_key,
)
from registry.normalize import normalize_url


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Cheap default; every answer is checked against the website anyway.
# Stronger, ~25x more expensive: anthropic/claude-opus-5.5
DEFAULT_MODEL = "openai/gpt-4o-mini"
WEB_RESULTS = 5

LIFECYCLE = ["active", "renamed", "merged", "closed", "unknown"]

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "official_url": {"type": ["string", "null"]},
        "canonical_name": {"type": ["string", "null"]},
        "lifecycle_status": {"type": "string", "enum": LIFECYCLE},
        "confidence": {"type": "number"},
        "evidence": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "official_url",
        "canonical_name",
        "lifecycle_status",
        "confidence",
        "evidence",
    ],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """\
You identify the official website of a German higher-education institution
(Hochschule) for a public registry. Use web search.

Rules:
- official_url is the institution's own website, preferably its homepage.
  Never a portal, directory, Wikipedia, Hochschulkompass, a news article,
  a social media profile or a page of a parent company about it.
- If the institution was renamed or merged, set lifecycle_status accordingly,
  give its current official name as canonical_name and its current website.
  If it closed, set lifecycle_status "closed" and official_url null.
- canonical_name is the current official name as the institution writes it.
- Do not guess domains. If you cannot find the website with certainty,
  return official_url null and a low confidence.
- evidence: short statements, each with the URL it comes from.
- The input contains what an automatic check already found
  (source_url, redirect_target, reachable candidate domains). Use it as
  hints only, it can be wrong.

Answer only with JSON that matches the schema."""


class AgentError(Exception):
    pass


# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------

def load_dotenv(path: str | Path = ".env") -> None:
    """
    Minimal .env loader. Variables that are already set (Docker,
    hosting secret store, shell) take precedence over the file.
    """
    path = Path(path)

    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


# ----------------------------------------------------------------------
# Agent request
# ----------------------------------------------------------------------

def agent_input(record: dict) -> dict:
    """What the agent gets (spec §22), plus the resolver's findings."""
    resolution = record.get("website_resolution") or {}

    return {
        "name": record["name"],
        "state": record["state"],
        "cities": sorted({
            location["city"]
            for location in record.get("locations") or []
            if location.get("city")
        }),
        "institution_type": record.get("institution_type"),
        "known_aliases": record.get("aliases") or [],
        "source_url": resolution.get("source_url"),
        "redirect_target": resolution.get("suggested_url"),
        "resolver_flags": resolution.get("flags") or [],
        "candidate_domains": [
            {
                "domain": candidate["domain"],
                "final_url": candidate.get("final_url"),
                "identity_score": (candidate.get("identity") or {}).get("score"),
            }
            for candidate in resolution.get("candidates") or []
            if candidate.get("outcome") == "reachable"
        ],
    }


def parse_answer(content: str) -> dict:
    """JSON answer, tolerating a surrounding code fence."""
    text = (content or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)

    try:
        answer = json.loads(text)
    except ValueError as exc:
        raise AgentError(f"unparseable answer: {text[:200]!r}") from exc

    missing = [key for key in ANSWER_SCHEMA["required"] if key not in answer]
    if missing:
        raise AgentError(f"answer misses {missing}")

    if answer["lifecycle_status"] not in LIFECYCLE:
        answer["lifecycle_status"] = "unknown"

    return answer


def ask_agent(payload: dict, model: str, api_key: str, timeout: int = 180) -> dict:
    body = {
        "model": model,
        "temperature": 0,
        "max_tokens": 1500,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "university_website",
                "strict": True,
                "schema": ANSWER_SCHEMA,
            },
        },
        "plugins": [{"id": "web", "max_results": WEB_RESULTS}],
        "usage": {"include": True},
    }

    try:
        response = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "X-Title": "ProjectPathly Registry",
            },
            json=body,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise AgentError(f"request failed: {type(exc).__name__}") from exc

    if response.status_code != 200:
        # The error body never contains the key; the request headers do.
        raise AgentError(f"HTTP {response.status_code}: {response.text[:300]}")

    data = response.json()

    try:
        message = data["choices"][0]["message"]
    except (KeyError, IndexError) as exc:
        raise AgentError(f"unexpected response: {str(data)[:300]}") from exc

    citations = [
        annotation["url_citation"]["url"]
        for annotation in message.get("annotations") or []
        if annotation.get("type") == "url_citation"
        and annotation.get("url_citation", {}).get("url")
    ]

    return {
        "answer": parse_answer(message.get("content")),
        "citations": list(dict.fromkeys(citations)),
        "requested_model": model,
        "model": data.get("model", model),
        "usage": data.get("usage"),
        "asked_at": datetime.now(timezone.utc).isoformat(),
    }


# ----------------------------------------------------------------------
# Validation (spec §23)
# ----------------------------------------------------------------------

def validate_answer(record: dict, answer: dict, resolver: WebsiteResolver) -> dict:
    """
    Accept the agent's URL only if the website confirms it:

      1. the site names the institution under its source name
         (same identity rule as for generated candidates), or
      2. the agent reports a rename, the site names the new name, AND
         the URL listed by the state source forwards to this very site.

    Everything else stays in review with the agent's suggestion.
    """
    url = answer.get("official_url")

    if not url:
        return {"accepted": False, "reason": "agent_no_url"}

    result = resolver.fetch_robust(url)

    if result.blocked:
        return {"accepted": False, "reason": "agent_url_blocked", "url": url}

    if not result.ok:
        return {"accepted": False, "reason": f"agent_url_{result.outcome}", "url": url}

    identity, result = resolver.verify(record, result, imprint_below=HIGH_CONFIDENCE)
    final_url = normalize_url(result.final_url)

    if identity.score >= HIGH_CONFIDENCE:
        return {
            "accepted": True,
            "reason": "identity_confirmed",
            "final_url": final_url,
            "confidence": identity.score,
            "identity": identity_dict(identity),
            "tls_unverified": result.tls_unverified,
        }

    canonical = answer.get("canonical_name")
    redirect_target = (record.get("website_resolution") or {}).get("suggested_url")

    if canonical and canonical != record["name"]:
        renamed, _ = resolver.verify(
            {**record, "name": canonical},
            result,
            imprint_below=HIGH_CONFIDENCE,
        )

        if (
            renamed.score >= HIGH_CONFIDENCE
            and redirect_target
            and site_key(redirect_target) == site_key(final_url)
        ):
            return {
                "accepted": True,
                "reason": "rename_confirmed_by_source_redirect",
                "final_url": final_url,
                "confidence": renamed.score,
                "identity": identity_dict(renamed),
                "tls_unverified": result.tls_unverified,
            }

    return {
        "accepted": False,
        "reason": "agent_identity_unconfirmed",
        "final_url": final_url,
        "identity": identity_dict(identity),
    }


def apply_result(record: dict, agent: dict, validation: dict) -> dict:
    record = dict(record)
    resolution = dict(record.get("website_resolution") or {})
    resolution["flags"] = list(resolution.get("flags") or [])

    resolution["agent"] = {
        "model": agent["model"],
        "answer": agent["answer"],
        "citations": agent["citations"],
        "validation": validation,
        "asked_at": agent["asked_at"],
    }

    if validation["accepted"]:
        resolution.update(
            status="resolved",
            method="agent_verified",
            confidence=validation["confidence"],
            official_url=validation["final_url"],
        )
        resolution.pop("suggested_url", None)
        resolution["flags"] = [
            f for f in resolution["flags"]
            if f not in ("identity_unconfirmed", "possible_rename_or_merger")
        ]

        if validation["reason"] == "rename_confirmed_by_source_redirect":
            resolution["flags"].append("renamed_per_agent")
        if validation.get("tls_unverified"):
            resolution["flags"].append("tls_certificate_unverified")

        record["official_url"] = validation["final_url"]

    else:
        resolution["flags"].append(validation["reason"])

        suggestion = validation.get("final_url") or validation.get("url")
        if suggestion and not resolution.get("suggested_url"):
            resolution["suggested_url"] = suggestion

        # Agent-only evidence never fills official_url.
        if resolution.get("status") == "unresolved" and suggestion:
            resolution["status"] = "review"

    record["website_resolution"] = resolution
    return record


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

def cache_key(record: dict, model: str) -> str:
    return f"{model}|{record['state']}|{record['name']}"


def build_report(rows: list[dict], model: str) -> dict:
    cost = sum(
        (row.get("usage") or {}).get("cost") or 0
        for row in rows
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "asked": len(rows),
        "accepted": sum(1 for row in rows if row["accepted"]),
        "by_reason": dict(Counter(row["reason"] for row in rows)),
        "cost_usd": round(cost, 4),
        "records": rows,
    }


def main():
    parser = argparse.ArgumentParser(
        description="ProjectPathly — agent resolver for unresolved websites (OpenRouter)"
    )
    parser.add_argument("--in", dest="input", default="data/enriched/universities_de_urls.json")
    parser.add_argument("--out", default=None, help="Default: overwrite --in")
    parser.add_argument("--report", default="data/reports/agent_resolution.json")
    parser.add_argument("--cache", default="data/enriched/agent_cache.json")
    parser.add_argument("--statuses", nargs="+", default=["unresolved", "review"])
    parser.add_argument("--model", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--refresh", action="store_true", help="Ignore cached answers")
    parser.add_argument(
        "--cache-only",
        action="store_true",
        help="Use cached answers only, never call the API (reproducible rebuild)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show the agent input, call nothing")
    args = parser.parse_args()

    load_dotenv()
    model = args.model or os.environ.get("OPENROUTER_MODEL") or DEFAULT_MODEL

    records = json.loads(Path(args.input).read_text(encoding="utf-8"))
    todo = [
        index
        for index, record in enumerate(records)
        if (record.get("website_resolution") or {}).get("status") in args.statuses
    ][: args.limit]

    print()
    print("=" * 62)
    print("PROJECTPATHLY — AGENT RESOLVER")
    print("=" * 62)
    print(f"[START] {len(todo)} records | model {model}")

    if args.dry_run:
        for index in todo:
            print(json.dumps(agent_input(records[index]), ensure_ascii=False, indent=2))
        return

    if "OPENROUTER_API_KEY" not in os.environ and not args.cache_only:
        raise SystemExit(
            "OPENROUTER_API_KEY is not set. Put it into .env "
            "(see .env.example) or the environment."
        )
    api_key = os.environ.get("OPENROUTER_API_KEY")

    cache_path = Path(args.cache)
    cache = (
        json.loads(cache_path.read_text(encoding="utf-8"))
        if cache_path.exists()
        else {}
    )

    resolver = WebsiteResolver()

    def handle(index):
        record = records[index]
        key = cache_key(record, model)
        cached = cache.get(key)

        if cached and not args.refresh:
            agent = cached
            from_cache = True
        elif args.cache_only:
            return index, key, None, None, False
        else:
            agent = ask_agent(agent_input(record), model, api_key)
            from_cache = False

        validation = validate_answer(record, agent["answer"], resolver)
        return index, key, agent, validation, from_cache

    rows = []

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(handle, index) for index in todo]

        for future in futures:
            try:
                index, key, agent, validation, from_cache = future.result()
            except AgentError as exc:
                print(f"[AGENT ERROR] {exc}")
                continue

            if agent is None:  # --cache-only and nothing cached
                continue

            cache[key] = agent
            record = records[index]
            records[index] = apply_result(record, agent, validation)

            answer = agent["answer"]
            rows.append({
                "state": record["state"],
                "name": record["name"],
                "previous_status": record["website_resolution"]["status"],
                "agent_url": answer["official_url"],
                "canonical_name": answer["canonical_name"],
                "lifecycle_status": answer["lifecycle_status"],
                "agent_confidence": answer["confidence"],
                "evidence": answer["evidence"],
                "citations": agent["citations"],
                "accepted": validation["accepted"],
                "reason": validation["reason"],
                "official_url": records[index]["official_url"],
                "from_cache": from_cache,
                "usage": None if from_cache else agent.get("usage"),
            })

            print(
                f"[{'ACCEPTED' if validation['accepted'] else 'REVIEW':8s}] "
                f"{record['state']} {record['name'][:50]:50s} "
                f"{answer['official_url'] or '-'} "
                f"({validation['reason']}{', cached' if from_cache else ''})"
            )

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

    out = Path(args.out or args.input)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    report = build_report(rows, model)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    with_url = sum(1 for record in records if record.get("official_url"))

    print()
    print("-" * 62)
    print(f"ASKED:        {report['asked']}")
    print(f"ACCEPTED:     {report['accepted']}")
    print(f"COST:         ${report['cost_usd']}")
    print(f"URL COVERAGE: {with_url}/{len(records)} = {100 * with_url / len(records):.1f} %")
    print(f"OUTPUT:       {out}")
    print(f"REPORT:       {report_path}")
    print("-" * 62)


if __name__ == "__main__":
    main()
