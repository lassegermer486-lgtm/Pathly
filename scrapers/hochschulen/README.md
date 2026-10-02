# ProjectPathly — German University Registry Scraper

Reproducible register of German higher-education institutions, built from
official state sources: every institution once, with its official website and
a permanent ProjectPathly ID (`PTH-DE-XXXXXXXX`).

## Pipeline (v1.2)

```text
16 state sources   registry.run                         data/normalized/
URL check/resolve  registry.enrichment.website_resolver data/enriched/
agent (last resort)registry.enrichment.agent_resolver   data/enriched/
deduplication      registry.master.dedup                data/master/universities_dedup.json
master registry    registry.master.build                data/master/*.json
Supabase import    registry.master.supabase_import      data/master/supabase_import.sql
```

```bash
python -m registry.pipeline                     # everything
python -m registry.pipeline --from dedup        # rebuild from enriched data
python -m registry.pipeline --agent-cache-only  # no API calls
```

Discovery data (`data/raw`, `data/normalized`) is never overwritten by later
steps. Reports for every step are in `data/reports/`.

## Reliability (v1.3)

- **Retries:** state sources are fetched through `registry/http_client.py`.
  A request is tried at most 3 times (waits 2 s, then 5 s) on connection
  errors, timeouts, 429 and 5xx; 4xx answers and POSTs are not retried.
  Hamburg and Schleswig-Holstein keep their own retry loops (and the
  Schleswig-Holstein / Saarland source caches); their requests are only counted.
- **Source status and count drift:** `data/reports/registry_run.json` keeps
  its fields and adds `source_status`, `previous_count`, `current_count`,
  `absolute_delta`, `relative_delta`, `count_status`, `production_safe`,
  `request_attempts` per state. A state with 0 institutions counts as failed.
  Count drift = more than ±10 institutions or more than ±30 % against the last
  accepted count (`data/master/state_counts.json`, commit this file).
- **Build status:** `data/reports/build_status.json`: `complete` (production
  safe), `review` (count drift to check), `degraded` (a state failed, was
  skipped or not requested), `failed`.
- **Safe publishing:** while the build is not production safe, the pipeline
  stops after discovery, and `registry.master.build` / `supabase_import`
  refuse to replace the published files. Debugging only: `--allow-degraded`.

```bash
python -m registry.reliability                        # last build status
python -m registry.reliability --accept-drift DE-SL   # drift checked and correct
```

Count drift never deletes or restores institutions; accepting it makes the
new count the baseline.

## Important design rule

The source page is authoritative for what it explicitly states. We do not infer
recognition, ownership or institutional identity from names alone. The later
Hochschulkompass layer should be a validation report (`MATCH`, `MISSING`,
`CONFLICT`), not a silent overwrite.

## Setup

macOS / Linux:

```bash
cd scrapers/hochschulen
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
cd scrapers/hochschulen
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## First live test — NRW

```bash
python -m registry.run --states DE-NW
```

Expected output shape:

```text
[FETCH] DE-NW — Nordrhein-Westfalen
[OK] DE-NW: <n> parsed records
[DONE] <n> unique records -> data/normalized/universities_de.json
```

Open:

```text
data/normalized/universities_de.json
```

## URL enrichment — verify and resolve official websites

Runs on the discovery output and writes a separate enriched layer:

```bash
python -m registry.enrichment.website_resolver
# only records without a source URL:
python -m registry.enrichment.website_resolver --only-missing
```

```text
data/normalized/universities_de.json  ->  data/enriched/universities_de_urls.json
                                          data/reports/url_resolution.json
```

- A URL from the state source has priority. It is checked technically
  (DNS, HTTP, redirects); the final URL is stored.
- Missing URLs: domain candidates are generated from the name (acronyms,
  `fh-<city>`, umlaut variants `muenchen`/`münchen` as IDN, initials).
  These are only candidates.
- A candidate is accepted (`deterministic_high`) only when the website's
  imprint names the institution, and no second, different website does
  the same. A matching title alone goes to `review`; HTTP 200 alone counts
  for nothing.
- `possible_rename_or_merger`: the source URL redirects to a site that no
  longer carries the source name (e.g. FH Bielefeld -> HSBI).

## Agent resolver — last resort for unresolved and review cases

Only for records the website resolver left as `unresolved` or `review`.
An LLM with web search (via OpenRouter) suggests the website, canonical
name and lifecycle status; the suggestion then passes the same technical
and identity checks. The agent is a resolver, not a source of truth.

```bash
cp .env.example .env          # then set OPENROUTER_API_KEY (never committed)
python -m registry.enrichment.agent_resolver --dry-run   # what would be asked
python -m registry.enrichment.agent_resolver
```

- Accepted (`agent_verified`) only if the site's imprint names the
  institution, or — for renames — the site names the new name *and* the URL
  from the state source forwards to it. Otherwise the suggestion stays in
  `review` and `official_url` is not filled.
- Answers are cached in `data/enriched/agent_cache.json`; reruns are free.
  `--refresh` asks again. Default model `openai/gpt-4o-mini` (a few cents
  per record, mostly web search); `OPENROUTER_MODEL` or `--model` changes it.
- The agent's `canonical_name` and `lifecycle_status` (renamed/merged/closed)
  are kept in `website_resolution.agent` for the later naming and lifecycle steps.

## Deduplication — one entry per institution

```bash
python -m registry.master.dedup
```

```text
data/enriched/universities_de_urls.json  ->  data/master/universities_dedup.json
data/master/overrides.yaml                   data/reports/dedup_report.json
                                             data/reports/review_report.md
```

- Same verified website + related name -> merged automatically. Related:
  same name, same name without a location suffix ("... in Gera"), an
  acronym written in both names, or the distinctive words of one name
  inside the other. Generic words and cities never count.
- Same name on different or unverified websites, a location-suffix
  variant, or a shared acronym across different websites -> review.
- Merging keeps every source name, location and source.
- Review cases are decided in `data/master/overrides.yaml` (`merge` /
  `keep_separate`); `review_report.md` lists them with ready-made lines.

## Why the NRW adapter is intentionally defensive

The official NRW page currently publishes category totals and contains university
names, addresses, websites and, for some institutions, multiple campuses/study
locations. Website/DOM structures can change. The parser therefore:

1. snapshots raw HTML;
2. uses official category headings as boundaries;
3. parses postal-code/city pairs;
4. retains multiple locations;
5. fails loudly instead of returning an apparently successful empty registry.

After the first real run, inspect the output count and several records. We should
then harden the selectors against the exact live DOM rather than pretending a
generic parser is guaranteed to be correct forever.

## Master registry — names, lifecycle, stable IDs

```bash
python -m registry.master.build
```

```text
data/master/universities_de_master.json   registry_id, name, official_url, country, lifecycle_status, flags
data/master/university_metadata.json      institution_type, ownership, recognition_status (+ raw source values)
data/master/locations.json  aliases.json  sources.json
data/master/id_registry.json              stable IDs — commit this file
data/reports/validation_report.json       quality report (coverage, review list)
```

- Canonical name: a name the website confirms (imprint before title) or a
  verified rename beats the cleaned source name; source names stay as aliases.
- `lifecycle_status`: `active` with a verified website, otherwise `review`.
  Doubts become flags (`missing_website`, `possibly_not_hochschule`, ...).
- IDs are random, never derived from names, and kept in `id_registry.json`
  across runs, renames and merges (the older ID wins, the other becomes an alias).

## Supabase import

```bash
python -m registry.master.supabase_import
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f data/master/supabase_import.sql
```

One transaction, safe to repeat: universities are matched by `registry_id`,
their locations/sources/flags replaced; institutions no longer listed stay
with `is_listed = false`.
