"""
Load the saved master registry into the Supabase/Postgres tables defined in
supabase/migrations.

    python -m scraper_ui.registry_import

The SQL itself comes from the scraper (registry.master.supabase_import, via
the bridge), so the UI and `psql -f data/master/supabase_import.sql` load the
database in exactly the same way:

  - one transaction: either the complete new state or nothing,
  - universities are recognised by `registry_id`, importing again updates,
  - nothing is deleted from `universities`; missing ones get is_listed = false,
  - locations, sources and flags of the imported universities are replaced,
  - a successful run is recorded in `import_runs`.

This module adds what the script cannot do on its own: the connection, a
check that the tables exist, the counts shown in the UI (new / changed /
no longer listed) and an `import_runs` entry for a failed attempt.

It has no dependency on the web UI, so a scheduled pipeline can call
`import_registry()` directly.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

DSN_ENV = "SUPABASE_DB_URL"
UI_DIR = Path(__file__).resolve().parents[1]

# Columns of public.universities that the import sets and the UI compares.
_UNI_COLUMNS = ("name", "name_variants", "institution_type", "ownership",
                "recognition_status", "lifecycle_status", "official_url", "listed_by")


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
# counts for the UI
# ----------------------------------------------------------------------

def _same(old, new) -> bool:
    if isinstance(old, str):
        old = old.strip()
    if isinstance(old, (list, tuple)) or isinstance(new, (list, tuple)):
        return list(old or []) == list(new or [])
    return old == new


def count_changes(before: dict[str, dict], universities: list[dict]) -> dict:
    """
    `before`: registry_id -> current row (is_listed and _UNI_COLUMNS).
    `universities`: the rows the import will write.
    """
    new = changed = 0
    for u in universities:
        old = before.get(u["registry_id"])
        if old is None:
            new += 1
        elif not old["is_listed"] or not all(_same(old.get(c), u.get(c)) for c in _UNI_COLUMNS):
            changed += 1
    imported = {u["registry_id"] for u in universities}
    unlisted = sum(1 for rid, old in before.items() if old["is_listed"] and rid not in imported)
    return {"universities": len(universities), "universities_new": new,
            "universities_changed": changed, "universities_unlisted": unlisted}


# ----------------------------------------------------------------------
# database
# ----------------------------------------------------------------------

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


def import_registry(dsn: str, payload: dict, sql: str, source_file: str | None = None) -> dict:
    """
    Run the import script. `payload` and `sql` come from
    registry.master.supabase_import (build_payload / render_sql).
    Returns the counts for the UI.
    """
    if not payload.get("universities"):
        raise ImportProblem("Das Register ist leer.")

    conn = _connect(dsn)
    try:
        with conn.cursor() as cur:
            _require_schema(cur)
            cur.execute(f"select registry_id, is_listed, {', '.join(_UNI_COLUMNS)} from public.universities")
            before = {r[0]: {"is_listed": r[1], **dict(zip(_UNI_COLUMNS, r[2:]))} for r in cur.fetchall()}
        counts = count_changes(before, payload["universities"])

        try:
            # The script has its own begin ... commit. Without parameters,
            # psycopg sends it as one simple query, several statements allowed.
            conn.execute(sql)
        except Exception as exc:
            message = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
            try:
                conn.execute("rollback")
                conn.execute(
                    "insert into public.import_runs (finished_at, status, source_file, message) "
                    "values (now(), 'failed', %s, %s)", (source_file, message[:2000]))
            except Exception:
                pass  # the original error is what matters
            raise ImportProblem(f"Import abgebrochen, nichts wurde geändert: {message}") from exc

        script = payload.get("counts") or {}
        return {**counts,
                "locations": script.get("locations", 0),
                "sources": script.get("sources", 0),
                "flags": script.get("flags", 0),
                "aliases": script.get("id_aliases", 0)}
    finally:
        conn.close()


# ----------------------------------------------------------------------
# command line
# ----------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    from .bridge import ScraperBridge

    argv = sys.argv[1:] if argv is None else argv
    scraper = Path(argv[0] if argv else os.environ.get("PATHLY_SCRAPER_DIR")
                   or UI_DIR.parent / "projectpathly_registry_scraper")

    dsn = load_dsn()
    if not dsn:
        print(f"{DSN_ENV} ist nicht gesetzt (Umgebung oder {UI_DIR / '.env'}).", file=sys.stderr)
        return 2

    bridge = ScraperBridge(scraper)
    if not bridge.registry_path.is_file():
        print(f"Kein gespeichertes Register: {bridge.registry_path}", file=sys.stderr)
        return 2

    payload, sql = bridge.import_script()
    try:
        counts = import_registry(dsn, payload, sql, source_file=bridge.registry_path.name)
    except ImportProblem as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Importiert nach {describe_target(dsn)}: " + json.dumps(counts, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
