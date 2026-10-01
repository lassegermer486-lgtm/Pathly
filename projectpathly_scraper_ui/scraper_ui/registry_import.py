"""
Load the master registry into the Supabase/Postgres tables defined in
supabase/migrations (universities, locations, sources, university_flags,
university_aliases, import_runs).

    python -m scraper_ui.registry_import [path/to/university_registry.json]

Rules
  - Everything is written in ONE transaction: either the complete new state
    or nothing.
  - Universities are recognised by `registry_id` (the scraper's stable id), so
    importing again updates instead of duplicating.
  - Nothing is deleted from `universities`: an institution that is missing in
    the file is only marked `is_listed = false`.
  - Locations keep their database id as long as their address is unchanged
    (later tables may point at them); sources and flags are replaced.
  - Every attempt is recorded in `import_runs`, also a failed one.

This module has no dependency on the web UI, so a scheduled pipeline can call
`import_registry()` directly.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

DSN_ENV = "SUPABASE_DB_URL"
UI_DIR = Path(__file__).resolve().parents[1]

# Mirrors the CHECK constraints of the migrations, so problems are reported
# readably before anything is sent to the database.
_ID = re.compile(r"^PTH-DE-[0-9A-F]{8}$")
_STATE = re.compile(r"^DE-[A-Z]{2}$")
_PLZ = re.compile(r"^[0-9]{5}$")
_TYPES = {"university", "university_of_applied_sciences", "art_music_university",
          "university_of_education", "public_administration", "dual_university",
          "theological_university", "other", "unknown"}
_OWNERSHIPS = {"public", "private", "church", "federal", "other", "unknown"}
_RECOGNITIONS = {"state_recognized", "public_by_law", "other_recognized", "unknown"}
_LIFECYCLES = {"active", "renamed", "merged", "closed", "unknown"}
_SEVERITIES = {"high", "medium", "low"}

# The table only knows main / branch / unknown. The scraper is more detailed;
# every kind of secondary site becomes "branch".
_LOCATION_TYPES = {"main": "main", "branch": "branch", "campus": "branch",
                   "study_location": "branch", "department": "branch"}


class ImportProblem(RuntimeError):
    """Configuration or data prevents the import; the message is shown to the user."""


# ----------------------------------------------------------------------
# configuration
# ----------------------------------------------------------------------

def _read_env_file(path: Path) -> dict:
    values = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def load_dsn() -> str | None:
    """Connection string from the environment or from `.env` in the UI folder."""
    return os.environ.get(DSN_ENV) or _read_env_file(UI_DIR / ".env").get(DSN_ENV) or None


def describe_target(dsn: str | None) -> str | None:
    """Host and database for display — never the password."""
    if not dsn:
        return None
    try:
        from psycopg.conninfo import conninfo_to_dict
        info = conninfo_to_dict(dsn)
        return f"{info.get('host', '?')} / {info.get('dbname', 'postgres')}"
    except Exception:
        return "konfiguriert"


# ----------------------------------------------------------------------
# preparing the rows
# ----------------------------------------------------------------------

def _clean(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def prepare(masters: list[dict]) -> dict:
    """Registry records -> rows for the tables. Raises ImportProblem with all findings."""
    problems, seen = [], set()
    universities, locations, sources, flags = [], [], [], []

    def check(ok: bool, text: str) -> None:
        if not ok:
            problems.append(text)

    for m in masters:
        rid, name = m.get("university_id"), _clean(m.get("name"))
        label = name or rid or "?"
        check(isinstance(rid, str) and bool(_ID.match(rid)), f"{label}: ungültige ID '{rid}'")
        check(rid not in seen, f"{label}: ID {rid} kommt doppelt vor")
        seen.add(rid)
        check(bool(name), f"{rid}: Name fehlt")

        row = {
            "registry_id": rid, "name": name,
            "name_variants": [v for v in m.get("name_variants") or [] if v],
            "country": m.get("country") or "DE",
            "institution_type": m.get("institution_type") or "unknown",
            "ownership": m.get("ownership") or "unknown",
            "recognition_status": m.get("recognition_status") or "unknown",
            "lifecycle_status": m.get("lifecycle_status") or "unknown",
            "official_url": _clean(m.get("official_url")),
            "listed_by": sorted(m.get("listed_by") or []),
        }
        check(row["institution_type"] in _TYPES, f"{label}: unbekannter Typ '{row['institution_type']}'")
        check(row["ownership"] in _OWNERSHIPS, f"{label}: unbekannte Trägerschaft '{row['ownership']}'")
        check(row["recognition_status"] in _RECOGNITIONS,
              f"{label}: unbekannte Anerkennung '{row['recognition_status']}'")
        check(row["lifecycle_status"] in _LIFECYCLES, f"{label}: unbekannter Status '{row['lifecycle_status']}'")
        universities.append(row)

        loc_keys = set()
        for loc in m.get("locations") or []:
            l = {
                "registry_id": rid,
                "name": _clean(loc.get("name")), "street": _clean(loc.get("street")),
                "postal_code": _clean(loc.get("postal_code")), "city": _clean(loc.get("city")),
                "state": _clean(loc.get("state")),
                "location_type": _LOCATION_TYPES.get(loc.get("location_type") or "main", "unknown"),
                "source_state": _clean(loc.get("source_state")),
                "source_url": _clean(loc.get("source_url")),
            }
            check(l["state"] is None or bool(_STATE.match(l["state"])),
                  f"{label}: Standort mit ungültigem Land '{l['state']}'")
            check(l["postal_code"] is None or bool(_PLZ.match(l["postal_code"])),
                  f"{label}: Standort mit ungültiger PLZ '{l['postal_code']}'")
            key = location_key(l)
            if key in loc_keys:           # identical address twice: keep one
                continue
            loc_keys.add(key)
            locations.append(l)

        for src in m.get("sources") or []:
            sources.append({
                "registry_id": rid, "state": _clean(src.get("state")),
                "authority": _clean(src.get("authority")),
                "url": _clean(src.get("url") or src.get("source_url")),
                "category": _clean(src.get("category") or src.get("source_category")),
                "source_type": _clean(src.get("source_type")),
                "retrieved_at": _clean(src.get("retrieved_at")),
            })

        for flag in m.get("validation_flags") or []:
            severity = flag.get("severity")
            check(severity in _SEVERITIES, f"{label}: Hinweis mit unbekannter Stufe '{severity}'")
            detail = flag.get("detail")
            flags.append({"registry_id": rid, "code": str(flag.get("code") or "unknown"),
                          "severity": severity, "detail": None if detail is None else str(detail)})

    if not universities:
        problems.append("Das Register ist leer.")
    if problems:
        shown = "; ".join(problems[:8]) + (f" … und {len(problems) - 8} weitere" if len(problems) > 8 else "")
        raise ImportProblem(f"Die Daten passen nicht zu den Tabellen ({len(problems)} Probleme): {shown}")
    return {"universities": universities, "locations": locations, "sources": sources, "flags": flags}


def location_key(loc: dict) -> tuple:
    """A location is the same place if name and address are unchanged."""
    return tuple((loc.get(k) or "").strip().lower()
                 for k in ("name", "street", "postal_code", "city", "state"))


def aliases_from_id_registry(id_registry: dict | None) -> list[dict]:
    """Earlier ids that were absorbed into another institution (config/id_registry.json)."""
    out = []
    for rid, entry in ((id_registry or {}).get("entries") or {}).items():
        for alias in entry.get("aliases") or []:
            if _ID.match(alias) and _ID.match(rid):
                out.append({"alias": alias, "registry_id": rid})
    return out


# ----------------------------------------------------------------------
# database
# ----------------------------------------------------------------------

_UNI_COLUMNS = ("name", "name_variants", "country", "institution_type", "ownership",
                "recognition_status", "lifecycle_status", "official_url", "listed_by")

_SQL_UPSERT_UNIVERSITIES = """
insert into public.universities
  (registry_id, name, name_variants, country, institution_type, ownership,
   recognition_status, lifecycle_status, official_url, listed_by, is_listed, last_seen_at)
select x.registry_id, x.name,
       array(select jsonb_array_elements_text(x.name_variants)),
       x.country, x.institution_type, x.ownership, x.recognition_status,
       x.lifecycle_status, x.official_url,
       array(select jsonb_array_elements_text(x.listed_by)),
       true, now()
from jsonb_to_recordset(%s::jsonb) as x(
  registry_id text, name text, name_variants jsonb, country text, institution_type text,
  ownership text, recognition_status text, lifecycle_status text, official_url text,
  listed_by jsonb)
on conflict (registry_id) do update set
  name = excluded.name, name_variants = excluded.name_variants, country = excluded.country,
  institution_type = excluded.institution_type, ownership = excluded.ownership,
  recognition_status = excluded.recognition_status, lifecycle_status = excluded.lifecycle_status,
  official_url = excluded.official_url, listed_by = excluded.listed_by,
  is_listed = true, last_seen_at = excluded.last_seen_at
returning id, registry_id
"""

_SQL_INSERT_LOCATIONS = """
insert into public.locations
  (university_id, name, street, postal_code, city, state, location_type, source_state, source_url)
select x.university_id, x.name, x.street, x.postal_code, x.city, x.state,
       x.location_type, x.source_state, x.source_url
from jsonb_to_recordset(%s::jsonb) as x(
  university_id bigint, name text, street text, postal_code text, city text, state text,
  location_type text, source_state text, source_url text)
"""

_SQL_UPDATE_LOCATIONS = """
update public.locations l
set location_type = x.location_type, source_state = x.source_state, source_url = x.source_url
from jsonb_to_recordset(%s::jsonb) as x(
  id bigint, location_type text, source_state text, source_url text)
where l.id = x.id
"""

_SQL_INSERT_SOURCES = """
insert into public.sources (university_id, state, authority, url, category, source_type, retrieved_at)
select x.university_id, x.state, x.authority, x.url, x.category, x.source_type, x.retrieved_at
from jsonb_to_recordset(%s::jsonb) as x(
  university_id bigint, state text, authority text, url text, category text,
  source_type text, retrieved_at timestamptz)
"""

_SQL_INSERT_FLAGS = """
insert into public.university_flags (university_id, code, severity, detail)
select x.university_id, x.code, x.severity, x.detail
from jsonb_to_recordset(%s::jsonb) as x(university_id bigint, code text, severity text, detail text)
"""

_SQL_UPSERT_ALIASES = """
insert into public.university_aliases (alias_registry_id, university_id)
select x.alias, x.university_id
from jsonb_to_recordset(%s::jsonb) as x(alias text, university_id bigint)
on conflict (alias_registry_id) do update set university_id = excluded.university_id
"""


def _connect(dsn: str):
    try:
        import psycopg
    except ImportError as exc:
        raise ImportProblem("Das Paket 'psycopg' fehlt. Bitte die UI einmal neu starten "
                            "(start.sh installiert es) oder requirements.txt installieren.") from exc
    try:
        # prepare_threshold=None: also works through Supabase's transaction pooler.
        return psycopg.connect(dsn, autocommit=True, connect_timeout=15, prepare_threshold=None)
    except psycopg.Error as exc:
        first = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
        raise ImportProblem(f"Keine Verbindung zur Datenbank: {first}") from exc


def _require_schema(cur) -> None:
    cur.execute("""
        select count(*) from information_schema.columns
        where table_schema = 'public'
          and ((table_name = 'universities' and column_name = 'registry_id')
            or (table_name = 'import_runs' and column_name = 'counts')
            or (table_name = 'locations' and column_name = 'university_id')
            or (table_name = 'university_flags' and column_name = 'severity'))
    """)
    if cur.fetchone()[0] < 4:
        raise ImportProblem(
            "Die Tabellen des Hochschulregisters fehlen oder haben einen älteren Stand. "
            "Bitte zuerst die Migrationen einspielen (supabase db push).")


def _git_commit(directory: Path | None) -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=directory or UI_DIR,
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or None
    except Exception:
        return None


def import_registry(dsn: str, masters: list[dict], id_registry: dict | None = None,
                    source_file: str | None = None, repo_dir: Path | None = None) -> dict:
    """Write the registry. Returns the counts that are also stored in import_runs."""
    rows = prepare(masters)                      # raises before any connection is opened
    aliases = aliases_from_id_registry(id_registry)
    dumps = lambda value: json.dumps(value, ensure_ascii=False)

    conn = _connect(dsn)
    try:
        with conn.cursor() as cur:
            _require_schema(cur)
            cur.execute(
                "insert into public.import_runs (status, source_file, git_commit) "
                "values ('running', %s, %s) returning id",
                (source_file, _git_commit(repo_dir)))
            run_id = cur.fetchone()[0]

        try:
            with conn.transaction(), conn.cursor() as cur:
                counts = _write(cur, rows, aliases, dumps)
        except Exception as exc:
            message = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
            with conn.cursor() as cur:
                cur.execute("update public.import_runs set status = 'failed', finished_at = now(), "
                            "message = %s where id = %s", (message[:2000], run_id))
            if isinstance(exc, ImportProblem):
                raise
            raise ImportProblem(f"Import abgebrochen, nichts wurde geändert: {message}") from exc

        with conn.cursor() as cur:
            cur.execute("update public.import_runs set status = 'succeeded', finished_at = now(), "
                        "counts = %s::jsonb where id = %s", (dumps(counts), run_id))
        return {**counts, "import_run": run_id}
    finally:
        conn.close()


def _write(cur, rows: dict, aliases: list[dict], dumps) -> dict:
    # --- universities ---------------------------------------------------
    cur.execute(f"select registry_id, is_listed, {', '.join(_UNI_COLUMNS)} from public.universities")
    before = {r[0]: {"is_listed": r[1], **dict(zip(_UNI_COLUMNS, r[2:]))} for r in cur.fetchall()}

    new = changed = 0
    for u in rows["universities"]:
        old = before.get(u["registry_id"])
        if old is None:
            new += 1
        elif not old["is_listed"] or any(
                (old[c].strip() if isinstance(old[c], str) else old[c]) != u[c] for c in _UNI_COLUMNS):
            changed += 1

    cur.execute(_SQL_UPSERT_UNIVERSITIES, (dumps(rows["universities"]),))
    db_id = {registry_id: uid for uid, registry_id in cur.fetchall()}
    ids = list(db_id.values())

    cur.execute("update public.universities set is_listed = false "
                "where is_listed and not (id = any(%s))", (ids,))
    unlisted = cur.rowcount

    # --- locations: keep ids of unchanged places ------------------------
    cur.execute("select id, university_id, name, street, postal_code, city, state, "
                "location_type, source_state, source_url from public.locations "
                "where university_id = any(%s)", (ids,))
    existing = {}
    for r in cur.fetchall():
        loc = dict(zip(("id", "university_id", "name", "street", "postal_code", "city", "state",
                        "location_type", "source_state", "source_url"), r))
        existing[(loc["university_id"], location_key(loc))] = loc

    to_insert, to_update, kept = [], [], set()
    for l in rows["locations"]:
        uid = db_id[l["registry_id"]]
        key = (uid, location_key(l))
        old = existing.get(key)
        if old is None:
            to_insert.append({**l, "university_id": uid})
            continue
        kept.add(key)
        if any(old[c] != l[c] for c in ("location_type", "source_state", "source_url")):
            to_update.append({"id": old["id"], "location_type": l["location_type"],
                              "source_state": l["source_state"], "source_url": l["source_url"]})
    to_delete = [loc["id"] for key, loc in existing.items() if key not in kept]

    if to_delete:
        cur.execute("delete from public.locations where id = any(%s)", (to_delete,))
    if to_update:
        cur.execute(_SQL_UPDATE_LOCATIONS, (dumps(to_update),))
    if to_insert:
        cur.execute(_SQL_INSERT_LOCATIONS, (dumps(to_insert),))

    # --- sources and flags: replaced ------------------------------------
    cur.execute("delete from public.sources where university_id = any(%s)", (ids,))
    cur.execute("delete from public.university_flags where university_id = any(%s)", (ids,))
    with_id = lambda items: [{**x, "university_id": db_id[x["registry_id"]]} for x in items]
    if rows["sources"]:
        cur.execute(_SQL_INSERT_SOURCES, (dumps(with_id(rows["sources"])),))
    if rows["flags"]:
        cur.execute(_SQL_INSERT_FLAGS, (dumps(with_id(rows["flags"])),))

    # --- earlier ids ----------------------------------------------------
    known_aliases = [{"alias": a["alias"], "university_id": db_id[a["registry_id"]]}
                     for a in aliases if a["registry_id"] in db_id]
    if known_aliases:
        cur.execute(_SQL_UPSERT_ALIASES, (dumps(known_aliases),))

    return {
        "universities": len(rows["universities"]),
        "universities_new": new,
        "universities_changed": changed,
        "universities_unlisted": unlisted,
        "locations": len(rows["locations"]),
        "locations_new": len(to_insert),
        "locations_removed": len(to_delete),
        "sources": len(rows["sources"]),
        "flags": len(rows["flags"]),
        "aliases": len(known_aliases),
    }


# ----------------------------------------------------------------------
# command line
# ----------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    scraper = Path(os.environ.get("PATHLY_SCRAPER_DIR") or UI_DIR.parent / "projectpathly_registry_scraper")
    path = Path(argv[0]) if argv else scraper / "data" / "master" / "university_registry.json"

    dsn = load_dsn()
    if not dsn:
        print(f"{DSN_ENV} ist nicht gesetzt (Umgebung oder {UI_DIR / '.env'}).", file=sys.stderr)
        return 2
    if not path.is_file():
        print(f"Datei nicht gefunden: {path}", file=sys.stderr)
        return 2

    id_path = scraper / "config" / "id_registry.json"
    id_registry = json.loads(id_path.read_text(encoding="utf-8")) if id_path.is_file() else None
    try:
        counts = import_registry(dsn, json.loads(path.read_text(encoding="utf-8")),
                                 id_registry, source_file=str(path.name), repo_dir=scraper)
    except ImportProblem as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Importiert nach {describe_target(dsn)}: " + json.dumps(counts, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
