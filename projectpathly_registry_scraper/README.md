# ProjectPathly — German University Registry Scraper

First technical spike for a reproducible German university registry built from
official state/authority sources.

## Current scope

- 16 German state sources are configured in `registry/sources.yaml`.
- NRW has the first executable HTML adapter.
- Baden-Württemberg and Sachsen-Anhalt are configured as the next two parser types:
  multi-page HTML and official PDF discovery.
- Every request is snapshotted to `data/raw/<STATE>/`.
- Normalized records are written to `data/normalized/universities.json`.
- Institutions and locations/campuses are separate concepts.
- Source authority, URL, source category and retrieval timestamp are retained.

## Important design rule

The source page is authoritative for what it explicitly states. We do not infer
recognition, ownership or institutional identity from names alone. The later
Hochschulkompass layer should be a validation report (`MATCH`, `MISSING`,
`CONFLICT`), not a silent overwrite.

## Setup

macOS / Linux:

```bash
cd projectpathly_registry_scraper
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
cd projectpathly_registry_scraper
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
[DONE] <n> unique records -> data/normalized/universities.json
```

Open:

```text
data/normalized/universities.json
```

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

## Next implementation order

1. Harden NRW after the first live run.
2. Implement Baden-Württemberg multi-page adapter.
3. Implement Sachsen-Anhalt PDF adapter.
4. Add automated source-count validation.
5. Implement remaining 13 state adapters.
6. Add cross-state deduplication and external-campus handling.
7. Add Hochschulkompass validation report.
8. Only then start the program/master crawler.
