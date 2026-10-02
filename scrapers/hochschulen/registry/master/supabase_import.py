"""
Spec step 13: Supabase import.

Writes one transactional SQL script from the master files, matching the
schema in supabase/migrations. Running it again is safe:

  - universities are matched by registry_id (insert or update),
  - their locations, sources and flags are replaced,
  - universities missing from this build stay, with is_listed = false
    (rows are never deleted),
  - former IDs of merged institutions go to university_aliases,
  - v1.3: German presence (universities.presence_status,
    locations.location_status); needs migration 20261002120000,
  - v1.3: home country, market_access, online_de_* and the discovery
    provenance of international candidates; needs migration 20261003120000,
  - every run is logged in import_runs.

Usage (from scrapers/hochschulen/):

    python -m registry.master.supabase_import
    psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f data/master/supabase_import.sql
    # or paste the file into the Supabase SQL editor
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from registry import reliability


# The database knows no "review" lifecycle; the reason is in university_flags.
LIFECYCLE = {"active": "active", "renamed": "renamed", "merged": "merged", "closed": "closed"}

DOLLAR_TAG = "$pathly_json$"

SQL = """\
-- ProjectPathly university registry import
-- generated {generated_at} from {source}
-- {universities} universities, {locations} locations, {sources} sources, {flags} flags

begin;

create temp table _pathly_import (doc jsonb) on commit drop;
insert into _pathly_import values ({tag}{payload}{tag}::jsonb);

-- 1. Universities, matched by registry_id
insert into public.universities as u (
  registry_id, name, name_variants, country, institution_type, ownership,
  recognition_status, lifecycle_status, official_url, listed_by, is_listed, last_seen_at,
  german_physical_presence, presence_status, presence_basis,
  market_access, online_de_status, online_de_basis, online_de_evidence, external_ids, discovery
)
select
  r.registry_id,
  r.name,
  array(select jsonb_array_elements_text(r.name_variants)),
  coalesce(r.country, 'DE'),
  r.institution_type,
  r.ownership,
  r.recognition_status,
  r.lifecycle_status,
  r.official_url,
  array(select jsonb_array_elements_text(r.listed_by)),
  true,
  now(),
  r.german_physical_presence,
  coalesce(r.presence_status, 'review'),
  r.presence_basis,
  array(select jsonb_array_elements_text(coalesce(r.market_access, '[]'::jsonb))),
  coalesce(r.online_de_status, 'not_assessed'),
  r.online_de_basis,
  coalesce(r.online_de_evidence, '{{}}'::jsonb),
  coalesce(r.external_ids, '{{}}'::jsonb),
  coalesce(r.discovery, '[]'::jsonb)
from _pathly_import i
cross join lateral jsonb_to_recordset(i.doc->'universities') as r(
  registry_id text, name text, name_variants jsonb, institution_type text,
  ownership text, recognition_status text, lifecycle_status text,
  official_url text, listed_by jsonb,
  german_physical_presence boolean, presence_status text, presence_basis text,
  country text, market_access jsonb, online_de_status text, online_de_basis text,
  online_de_evidence jsonb, external_ids jsonb, discovery jsonb
)
on conflict (registry_id) do update set
  name               = excluded.name,
  name_variants      = excluded.name_variants,
  institution_type   = excluded.institution_type,
  ownership          = excluded.ownership,
  recognition_status = excluded.recognition_status,
  lifecycle_status   = excluded.lifecycle_status,
  official_url       = excluded.official_url,
  listed_by          = excluded.listed_by,
  is_listed          = true,
  last_seen_at       = excluded.last_seen_at,
  german_physical_presence = excluded.german_physical_presence,
  presence_status    = excluded.presence_status,
  presence_basis     = excluded.presence_basis,
  country            = excluded.country,
  market_access      = excluded.market_access,
  online_de_status   = excluded.online_de_status,
  online_de_basis    = excluded.online_de_basis,
  online_de_evidence = excluded.online_de_evidence,
  external_ids       = excluded.external_ids,
  discovery          = excluded.discovery;

-- 2. Universities no source lists any more: keep, but mark.
--    Without a current listing their German presence is unknown again.
update public.universities
set is_listed = false,
    german_physical_presence = null,
    presence_status = 'review',
    presence_basis = 'no_longer_listed',
    market_access = '{{}}'
where is_listed
  and registry_id not in (
    select r->>'registry_id'
    from _pathly_import i, jsonb_array_elements(i.doc->'universities') r
  );

-- 3. Former IDs of merged institutions
insert into public.university_aliases (alias_registry_id, university_id)
select a.alias_registry_id, u.id
from _pathly_import i
cross join lateral jsonb_to_recordset(i.doc->'id_aliases') as a(alias_registry_id text, registry_id text)
join public.universities u on u.registry_id = a.registry_id
on conflict (alias_registry_id) do update set university_id = excluded.university_id;

-- 4. Replace locations, sources and flags of the imported universities
create temp table _pathly_ids on commit drop as
select u.id
from public.universities u
join (
  select r->>'registry_id' as registry_id
  from _pathly_import i, jsonb_array_elements(i.doc->'universities') r
) imported using (registry_id);

delete from public.locations        where university_id in (select id from _pathly_ids);
delete from public.sources          where university_id in (select id from _pathly_ids);
delete from public.university_flags where university_id in (select id from _pathly_ids);

insert into public.locations (
  university_id, name, street, postal_code, city, state, location_type, source_state, source_url,
  country, location_status, location_status_basis, location_status_evidence_url
)
select u.id, l.name, l.street, l.postal_code, l.city, l.state, l.location_type, l.source_state, l.source_url,
  coalesce(l.country, 'DE'), coalesce(l.location_status, 'uncertain'),
  l.location_status_basis, l.location_status_evidence_url
from _pathly_import i
cross join lateral jsonb_to_recordset(i.doc->'locations') as l(
  registry_id text, name text, street text, postal_code text, city text,
  state text, location_type text, source_state text, source_url text,
  country text, location_status text, location_status_basis text,
  location_status_evidence_url text
)
join public.universities u on u.registry_id = l.registry_id;

insert into public.sources (
  university_id, state, authority, url, category, source_type, retrieved_at, dataset_version, record_id
)
select u.id, s.state, s.authority, s.url, s.category, s.source_type, s.retrieved_at,
  s.dataset_version, s.record_id
from _pathly_import i
cross join lateral jsonb_to_recordset(i.doc->'sources') as s(
  registry_id text, state text, authority text, url text, category text,
  source_type text, retrieved_at timestamptz, dataset_version text, record_id text
)
join public.universities u on u.registry_id = s.registry_id;

insert into public.university_flags (university_id, code, severity, detail)
select u.id, f.code, f.severity, f.detail
from _pathly_import i
cross join lateral jsonb_to_recordset(i.doc->'flags') as f(
  registry_id text, code text, severity text, detail text
)
join public.universities u on u.registry_id = f.registry_id;

-- 5. Log
insert into public.import_runs (finished_at, status, source_file, git_commit, counts, message)
select now(), 'succeeded', {source_literal}, {commit_literal}, i.doc->'counts', 'ProjectPathly registry v1.3'
from _pathly_import i;

commit;
"""


def sql_literal(value: str | None) -> str:
    if value is None:
        return "null"
    return "'" + value.replace("'", "''") + "'"


def git_commit() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def build_payload(master_dir: Path) -> dict:
    def load(name):
        return json.loads((master_dir / name).read_text(encoding="utf-8"))

    universities = load("universities_de_master.json")
    metadata = {m["registry_id"]: m for m in load("university_metadata.json")}
    aliases = load("aliases.json")
    locations = load("locations.json")
    sources = load("sources.json")

    name_variants: dict[str, list[str]] = {}
    for alias in aliases:
        name_variants.setdefault(alias["registry_id"], []).append(alias["alias"])

    rows, id_aliases, flags = [], [], []
    for u in universities:
        meta = metadata.get(u["registry_id"], {})
        rows.append({
            "registry_id": u["registry_id"],
            "name": u["name"],
            "name_variants": name_variants.get(u["registry_id"], []),
            "institution_type": meta.get("institution_type", "unknown"),
            "ownership": meta.get("ownership", "unknown"),
            "recognition_status": meta.get("recognition_status", "unknown"),
            "lifecycle_status": LIFECYCLE.get(u["lifecycle_status"], "unknown"),
            "official_url": u["official_url"],
            "listed_by": u["listed_by"],
            # v1.3; absent in master files built before it
            "german_physical_presence": u.get("german_physical_presence"),
            "presence_status": u.get("presence_status", "review"),
            "presence_basis": u.get("presence_basis"),
            "country": u.get("country", "DE"),
            "market_access": u.get("market_access", []),
            "online_de_status": u.get("online_de_status", "not_assessed"),
            "online_de_basis": u.get("online_de_basis"),
            "online_de_evidence": u.get("online_de_evidence", {}),
            "external_ids": u.get("external_ids", {}),
            "discovery": u.get("discovery", []),
        })
        id_aliases += [
            {"alias_registry_id": former, "registry_id": u["registry_id"]}
            for former in u.get("former_registry_ids") or []
        ]
        flags += [{"registry_id": u["registry_id"], **f} for f in u["flags"]]

    return {
        "universities": rows,
        "id_aliases": id_aliases,
        "locations": locations,
        "sources": [
            {
                "registry_id": s["registry_id"],
                "state": s["source_state"],
                "authority": s["authority"],
                "url": s["source_url"],
                "category": s["source_category"],
                "source_type": s["source_type"],
                "retrieved_at": s["retrieved_at"],
                "dataset_version": s.get("dataset_version"),
                "record_id": s.get("record_id"),
            }
            for s in sources
        ],
        "flags": flags,
        "counts": {
            "universities": len(rows),
            "with_official_url": sum(1 for r in rows if r["official_url"]),
            "locations": len(locations),
            "sources": len(sources),
            "flags": len(flags),
            "id_aliases": len(id_aliases),
            "presence_confirmed": sum(1 for r in rows if r["presence_status"] == "confirmed"),
            "presence_not_present": sum(1 for r in rows if r["presence_status"] == "not_present"),
            "presence_review": sum(1 for r in rows if r["presence_status"] == "review"),
            "international": sum(1 for r in rows if r["country"] != "DE"),
            "online_de_confirmed": sum(1 for r in rows if r["online_de_status"] == "confirmed"),
            "online_de_review": sum(1 for r in rows if r["online_de_status"] == "review"),
        },
    }


def render_sql(payload: dict, source: str, commit: str | None) -> str:
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    if DOLLAR_TAG in text:
        raise ValueError(f"payload contains the quoting tag {DOLLAR_TAG}")

    counts = payload["counts"]
    return SQL.format(
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        source=source,
        universities=counts["universities"],
        locations=counts["locations"],
        sources=counts["sources"],
        flags=counts["flags"],
        tag=DOLLAR_TAG,
        payload=text,
        source_literal=sql_literal(source),
        commit_literal=sql_literal(commit),
    )


def main():
    parser = argparse.ArgumentParser(description="ProjectPathly — Supabase import script")
    parser.add_argument("--master-dir", default="data/master")
    parser.add_argument("--out", default="data/master/supabase_import.sql")
    parser.add_argument("--allow-degraded", action="store_true",
                        help="Write even if the discovery build is not production safe")
    args = parser.parse_args()

    # Institutions missing from an incomplete build would be set is_listed = false.
    if not reliability.production_gate("supabase import", args.allow_degraded):
        raise SystemExit(2)

    master_dir = Path(args.master_dir)
    payload = build_payload(master_dir)
    sql = render_sql(payload, str(master_dir / "universities_de_master.json"), git_commit())

    Path(args.out).write_text(sql, encoding="utf-8")

    # what was exported, for reports and the UI
    report_path = Path("data/reports/supabase_export.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "output": args.out,
        "master_dir": str(master_dir),
        "git_commit": git_commit(),
        "counts": payload["counts"],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    counts = payload["counts"]
    print()
    print("=" * 62)
    print("PROJECTPATHLY — SUPABASE IMPORT SCRIPT")
    print("=" * 62)
    for key, value in counts.items():
        print(f"{key:22s}{value}")
    print(f"OUTPUT:               {args.out}")
    print('RUN:                  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f ' + args.out)
    print("-" * 62)


if __name__ == "__main__":
    main()
