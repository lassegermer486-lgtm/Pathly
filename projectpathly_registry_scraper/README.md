# ProjectPathly — German University Registry Scraper

Reproducible German university registry built from official state/authority
sources, deduplicated nationwide into the ProjectPathly Master University Registry.

## Current scope

- All 16 German states have an adapter (`registry/adapters/`), configured in
  `registry/sources.yaml`.
- The scraper saves its result as JSON (`data/normalized/`). Raw source copies
  are only stored with `--snapshots`; the master registry only with `--save`.
- Institutions and locations/campuses are separate concepts; the state belongs
  to the location.
- Source authority, URL, source category and retrieval timestamp are retained.

## Important design rule

The source page is authoritative for what it explicitly states. We do not infer
recognition, ownership or institutional identity from names alone. The later
Hochschulkompass layer should be a validation report (`MATCH`, `MISSING`,
`CONFLICT`), not a silent overwrite.

## States

Data uses the official ISO 3166-2 code (`DE-NW`); display and command line use
the common abbreviation. `--states` accepts both (`NRW`, `nw`, `DE-NW`).

| Kürzel | Code | Land | Kürzel | Code | Land |
| --- | --- | --- | --- | --- | --- |
| BW | DE-BW | Baden-Württemberg | NI | DE-NI | Niedersachsen |
| BY | DE-BY | Bayern | NRW | DE-NW | Nordrhein-Westfalen |
| BE | DE-BE | Berlin | RP | DE-RP | Rheinland-Pfalz |
| BB | DE-BB | Brandenburg | SL | DE-SL | Saarland |
| HB | DE-HB | Bremen | SN | DE-SN | Sachsen |
| HH | DE-HH | Hamburg | ST | DE-ST | Sachsen-Anhalt |
| HE | DE-HE | Hessen | SH | DE-SH | Schleswig-Holstein |
| MV | DE-MV | Mecklenburg-Vorpommern | TH | DE-TH | Thüringen |

## Usage (Docker)

```bash
docker compose build
docker compose run --rm scraper                     # alle 16 Länder -> data/normalized/universities_de.json
docker compose run --rm scraper --states NRW HH --list   # -> data/normalized/universities_NRW_HH.json
docker compose run --rm master                      # live scrapen + Master-Registry bauen
docker compose run --rm master --candidates-only    # nur Dedup-Kandidaten, nichts mergen
docker compose run --rm master --online --list      # + Website-Check, alle Einträge anzeigen
docker compose run --rm tests
```

Local without Docker: `pip install -r requirements.txt`, then
`python -m registry.run …` / `python -m registry.master …` / `python -m pytest tests`.

Scraper flags: `--list` (print every record), `--json` (full result to stdout,
log to stderr), `--dry-run` (write nothing), `--snapshots` (also store raw
source copies), `--out FILE`. A run with `--states` writes its own file, so a
partial scrape never overwrites the full dataset.

Master flags: `--list`, `--json`, `--input FILE`, `--candidates-only`,
`--online`, `--save`.

## What is stored where

| Path | Committed | Content |
| --- | --- | --- |
| `data/source_cache/DE-SH/`, `DE-SL/` | yes | Fallback copies of official sources; read only when the live source fails, refreshed by `scraper --snapshots` |
| `config/overrides.yaml` | yes | Manual dedup decisions and per-record corrections |
| `config/id_registry.json` | yes | Stable `university_id` assignment, updated by `master --save` |
| `data/normalized/` | no | Scraper result as JSON (every run without `--dry-run`) |
| `data/raw/` | no | `scraper --snapshots`: raw source copies |
| `data/master/`, `data/reports/` | no | `master --save`: registry, dedup candidates, review report, summary |

`master --input data/normalized/universities_de.json` builds the registry from a
saved scrape instead of scraping live.

## Master University Registry

### Deduplication

1. **Candidates** — every pair of state records is compared (website host, root
   domain, names, street address). Nothing is merged at this stage.
2. **auto_merge** only with an independent signal: same website host with
   related names (incl. departments like „… – Fachbereich X in Y“), or an
   identical name listed by different states without a conflicting website.
3. **review** for everything else. A name that only adds place words is a
   candidate, never an identity. Generic subject words („Evangelische“,
   „Technik und Wirtschaft“) are no evidence at all; state portals
   (`hessen.de`, `hamburg.de`, …) never count as a shared website.
4. Decisions go into `config/overrides.yaml` (`merge`, `keep_separate`); each run
   prints the open review pairs and warns about override keys that no longer
   match a scraped record.

Merging never drops locations, sources or name variants (`locations`,
`sources`, `name_variants`, `merged_from`).

### Schema

- `institution_type`: `university`, `university_of_applied_sciences`,
  `art_music_university`, `university_of_education`, `public_administration`,
  `dual_university`, `theological_university`, `other`, `unknown`
- `ownership`: `public`, `private`, `church`, `federal`, `other`, `unknown` —
  a source listing „private or church“ together yields `unknown`
- `recognition_status`: `state_recognized`, `public_by_law`,
  `other_recognized` (only via review), `unknown` — independent of ownership
- State lives on each location (`locations[].state`). The institution has
  `states` (derived from its locations) and `listed_by` (state sources that list
  it); there is no single "home state".
- `lifecycle_status`: `active`, `renamed`, `merged`, `closed`, `unknown` — never
  set automatically, only via `config/overrides.yaml` after review.
- Original adapter values per source: `merged_from[].legacy`.

### Validation

`validation_flags` per institution (severity `high`/`medium`/`low`): missing
website, unknown type/ownership/recognition, possible department or
non-Hochschule, shared root domain; with `--online` also reachability, redirects
to another domain and rename/merger wording on the website. Flags are evidence
for review and never change data.

## Next steps

1. Resolve the remaining review pairs.
2. Fill missing official websites (mainly NI, BB, TH, BE, SL adapters).
3. Hochschulkompass validation report.
4. Only then start the program/master crawler.
