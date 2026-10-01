"""
Run state of the UI: one scrape at a time, phases, decisions, saving.

Phases
    idle      nothing loaded yet
    fetching  state sources are being scraped
    matching  schema unification, duplicate detection, merging
    checking  validation (optionally with website check)
    review    finished, but duplicate pairs need a human decision
    ready     finished, can be saved
    saved     written to disk, nothing changed since
    error     the run itself broke (not: a single state failed)
"""
from __future__ import annotations

import hashlib
import threading
import time
from datetime import datetime, timezone

from . import overrides_file, registry_import
from .bridge import ScraperBridge

BUSY_PHASES = {"fetching", "matching", "checking"}
MAX_LOG_LINES = 2000


class Conflict(Exception):
    """The request does not fit the current state (HTTP 409)."""


class NotFound(Exception):
    pass


def pair_id(a: str, b: str) -> str:
    return hashlib.sha1("\n".join(sorted((a, b))).encode("utf-8")).hexdigest()[:12]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Runner:
    def __init__(self, bridge: ScraperBridge):
        self.bridge = bridge
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._cancel = threading.Event()

        self.phase = "idle"
        self.message = ""
        self.error: str | None = None
        self.started_at: str | None = None
        self.finished_at: str | None = None
        self.duration: float | None = None
        self.source: str | None = None          # "live" | "file"
        self.online = False
        self.selected: list[str] = []            # state codes of this run
        self.states: dict[str, dict] = {}
        self.raw: dict[str, list[dict]] = {}
        self.result: dict | None = None
        self.decisions: dict[str, dict] = {}     # decided in this session
        self.saved: dict | None = None
        self.db_pushing = False
        self.db_last: dict | None = None         # last successful push of this state
        self.log: list[str] = []
        self.log_dropped = 0
        self.version = 0                          # bumps whenever data changes

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _log(self, line: str) -> None:
        with self._lock:
            self.log.append(line)
            overflow = len(self.log) - MAX_LOG_LINES
            if overflow > 0:
                del self.log[:overflow]
                self.log_dropped += overflow

    def busy(self) -> bool:
        return self.phase in BUSY_PHASES or self.db_pushing

    def _require_idle(self) -> None:
        if self.db_pushing:
            raise Conflict("Die Daten werden gerade in die Datenbank geladen. Bitte kurz warten.")
        if self.busy():
            raise Conflict("Es läuft gerade ein Abruf. Bitte warten, bis er fertig ist.")

    def _all_raw(self) -> list[dict]:
        out = []
        for code in self.selected:
            out.extend(self.raw.get(code, []))
        return out

    def _open_pairs(self) -> list[dict]:
        if not self.result:
            return []
        return [c for c in self.result["candidates"] if c.get("decision") == "review"]

    def _conflicts(self) -> list[dict]:
        """keep_separate pairs that still end up in one institution (via other merges)."""
        if not self.result or not self.result.get("dedup"):
            return []
        home = {}
        for m in self.result["masters"]:
            for src in m.get("merged_from") or []:
                home[src.get("source_key")] = m
        out = []
        for pair in (self.result.get("overrides") or {}).get("keep_separate") or []:
            if len(pair) != 2:
                continue
            a, b = pair
            if a in home and b in home and home[a] is home[b]:
                out.append({"a": a, "b": b, "name": home[a].get("name")})
        return out

    def _failed_states(self) -> list[str]:
        return [c for c in self.selected if self.states.get(c, {}).get("status") == "error"]

    def _settle(self) -> None:
        """Set the resting phase after data changed."""
        open_n = len(self._open_pairs())
        if open_n:
            self.phase = "review"
            self.message = (f"{open_n} mögliche{'s' if open_n == 1 else ''} Duplikat"
                            f"{'' if open_n == 1 else 'e'} "
                            f"{'braucht' if open_n == 1 else 'brauchen'} eine Entscheidung. "
                            "Danach lässt sich speichern.")
        else:
            self.phase = "ready"
            failed = self._failed_states()
            if failed:
                names = ", ".join(self.bridge.short(c) for c in failed)
                self.message = f"Fertig, aber unvollständig: {names} fehlgeschlagen."
            else:
                self.message = "Fertig. Der Stand kann gespeichert werden."

    def _rebuild(self, online: bool = False, quick: bool = False) -> None:
        cached = self.result.get("websites") if self.result else None
        result = self.bridge.build(self._all_raw(), self._log, online=online,
                                   websites=cached, quick=quick)
        with self._lock:
            self.result = result
            self.saved = None
            self.db_last = None
            self.version += 1

    # ------------------------------------------------------------------
    # running
    # ------------------------------------------------------------------

    def start(self, states: list[str] | None = None, online: bool = False,
              source: str = "live") -> None:
        with self._lock:
            self._require_idle()
            known = [s["code"] for s in self.bridge.states()]
            selected = [c for c in known if not states or c in states]
            if not selected:
                raise Conflict("Kein gültiges Bundesland ausgewählt.")
            if source == "file" and not self.bridge.last_scrape_path.is_file():
                raise Conflict("Es gibt noch keinen gespeicherten Abruf.")

            self._cancel.clear()
            self.phase = "fetching"
            self.message = "Abruf startet …"
            self.error = None
            self.started_at = _now()
            self.finished_at = None
            self.duration = None
            self.source = source
            self.online = online
            self.selected = selected
            self.states = {c: {"status": "waiting"} for c in selected}
            self.raw = {}
            self.result = None
            self.decisions = {}
            self.saved = None
            self.db_last = None
            self.log = []
            self.log_dropped = 0
            self.version += 1

            self._thread = threading.Thread(target=self._run, name="scrape-run", daemon=True)
            self._thread.start()

    def cancel(self) -> None:
        if self.phase != "fetching":
            raise Conflict("Es läuft kein Abruf, der sich abbrechen lässt.")
        self._cancel.set()
        self._log("[UI] Abbruch angefordert – das laufende Land wird noch beendet.")

    def _fetch_state(self, code: str, config: dict) -> None:
        short = self.bridge.short(code)
        with self._lock:
            self.states[code] = {"status": "running"}
            self.message = f"Rufe {short} ab …"
        log_start = len(self.log) + self.log_dropped
        t0 = time.monotonic()
        records, report = self.bridge.scrape_state(code, config, self._log)
        seconds = round(time.monotonic() - t0, 1)

        status = {"OK": "ok", "ERROR": "error"}.get(report.get("status"), "skipped")
        entry = {
            "status": status,
            "seconds": seconds,
            "universities": report.get("universities", len(records)),
            "locations": report.get("locations",
                                    sum(len(r.get("locations") or []) for r in records)),
            "validation_issues": report.get("validation_issues", 0),
            "error": report.get("error"),
            "detail": report.get("status"),
        }
        # Adapters say so in their output when they fall back to a stored copy.
        own_lines = self.log[max(0, log_start - self.log_dropped):]
        if status == "ok" and any("cache" in l.lower() for l in own_lines):
            entry["note"] = "gespeicherte Kopie der Quelle verwendet"
        with self._lock:
            self.states[code] = entry
            self.raw[code] = records if status == "ok" else []

    def _run(self) -> None:
        t0 = time.monotonic()
        try:
            if self.source == "file":
                self._load_from_file()
            else:
                config = self.bridge.load_config()
                for i, code in enumerate(self.selected):
                    if self._cancel.is_set():
                        with self._lock:
                            for rest in self.selected[i:]:
                                self.states[rest] = {"status": "skipped", "detail": "abgebrochen"}
                        break
                    self._fetch_state(code, config)
                    # Live preview: counts and tables grow while the run goes on.
                    # Without dedup; that runs once all states are in.
                    try:
                        self._rebuild(quick=True)
                    except Exception as exc:
                        self._log(f"[UI] Zwischenstand nicht berechenbar: {exc}")

            with self._lock:
                self.phase = "matching"
                self.message = "Gleiche Einträge ab und führe Duplikate zusammen …"
            if self.online and self.bridge.capabilities()["web_check"]:
                with self._lock:
                    self.phase = "checking"
                    self.message = "Prüfe die Websites aller Hochschulen …"
            self._rebuild(online=self.online)

            with self._lock:
                self.phase = "checking"
            for w in self.result.get("override_warnings") or []:
                self._log(f"[WARN] overrides.yaml {w['section']}: '{w['key']}' "
                          "passt zu keinem abgerufenen Eintrag")
            for w in self.result.get("id_warnings") or []:
                self._log(f"[ID] {w}")

            with self._lock:
                self.duration = round(time.monotonic() - t0, 1)
                self.finished_at = _now()
                self._settle()
                self._log(f"[UI] Fertig nach {self.duration} s: "
                          f"{len(self.result['records'])} Landeseinträge, "
                          f"{len(self.result['masters'])} Hochschulen, "
                          f"{len(self._open_pairs())} offene Duplikat-Paare")
        except Exception as exc:
            with self._lock:
                self.phase = "error"
                self.error = f"{type(exc).__name__}: {exc}"
                self.message = "Der Lauf ist abgebrochen."
                self.finished_at = _now()
                self.duration = round(time.monotonic() - t0, 1)
            self._log(f"[ERROR] {self.error}")

    def _load_from_file(self) -> None:
        self._log(f"[UI] Lade gespeicherten Abruf: {self.bridge.last_scrape_path}")
        records = self.bridge.load_last_scrape()
        by_state: dict[str, list[dict]] = {}
        for r in records:
            by_state.setdefault(r.get("state"), []).append(r)
        with self._lock:
            for code in self.selected:
                rows = by_state.get(code, [])
                self.raw[code] = rows
                self.states[code] = {
                    "status": "ok" if rows else "skipped",
                    "universities": len(rows),
                    "locations": sum(len(r.get("locations") or []) for r in rows),
                    "detail": "aus Datei" if rows else "nicht in der Datei",
                }

    def retry_state(self, code: str) -> None:
        with self._lock:
            self._require_idle()
            if code not in self.states:
                raise NotFound("Dieses Bundesland gehört nicht zum aktuellen Lauf.")
            self._cancel.clear()
            self.phase = "fetching"
            self.error = None
            self.saved = None

            def work():
                try:
                    self._fetch_state(code, self.bridge.load_config())
                    with self._lock:
                        self.phase = "matching"
                    self._rebuild()
                    with self._lock:
                        self._settle()
                except Exception as exc:
                    with self._lock:
                        self.phase = "error"
                        self.error = f"{type(exc).__name__}: {exc}"
                        self.message = "Der erneute Abruf ist abgebrochen."
                    self._log(f"[ERROR] {self.error}")

            self._thread = threading.Thread(target=work, name="scrape-retry", daemon=True)
            self._thread.start()

    # ------------------------------------------------------------------
    # duplicate decisions
    # ------------------------------------------------------------------

    def decide(self, pid: str, decision: str | None, note: str = "") -> None:
        """decision: 'merge', 'keep_separate' or None (take the decision back)."""
        if decision not in ("merge", "keep_separate", None):
            raise Conflict("Unbekannte Entscheidung.")
        with self._lock:
            self._require_idle()
            if not self.result:
                raise Conflict("Es gibt noch keinen Abruf.")

            pair = next((c for c in self._open_pairs() if pair_id(c["a"], c["b"]) == pid), None)
            previous = self.decisions.get(pid)
            if pair is None and previous is None:
                raise NotFound("Dieses Paar gibt es im aktuellen Stand nicht.")
            base = previous or {"a": pair["a"], "b": pair["b"],
                                "reasons": pair.get("reasons") or [],
                                "signals": pair.get("signals") or {}}
            a, b = base["a"], base["b"]
            path = self.bridge.overrides_path

            try:
                if previous:
                    overrides_file.remove_pair(path, previous["decision"], a, b)
                if decision:
                    overrides_file.add_pair(path, decision, a, b, note)
            except overrides_file.OverridesError as exc:
                raise Conflict(str(exc)) from exc

            if decision:
                self.decisions[pid] = {**base, "decision": decision,
                                       "note": " ".join((note or "").split()),
                                       "decided_at": _now()}
                self._log(f"[UI] Entscheidung: {decision} – {a} ↔ {b}")
            else:
                self.decisions.pop(pid, None)
                self._log(f"[UI] Entscheidung zurückgenommen – {a} ↔ {b}")

            self._rebuild()
            self._settle()

    # ------------------------------------------------------------------
    # saving
    # ------------------------------------------------------------------

    def save(self, confirm_incomplete: bool = False) -> dict:
        with self._lock:
            self._require_idle()
            if not self.result:
                raise Conflict("Es gibt noch nichts zu speichern. Bitte zuerst einen Abruf starten.")
            open_n = len(self._open_pairs())
            if open_n:
                raise Conflict(f"Noch {open_n} Duplikat-Paar{'' if open_n == 1 else 'e'} offen. "
                               "Bitte zuerst entscheiden.")
            conflicts = self._conflicts()
            if conflicts:
                raise Conflict("Entscheidungen widersprechen sich: "
                               + "; ".join(f"{c['a']} und {c['b']}" for c in conflicts)
                               + " sollen getrennt bleiben, werden aber über andere "
                                 "Zusammenführungen vereint.")
            failed = self._failed_states()
            if failed and not confirm_incomplete:
                raise Conflict("INCOMPLETE:" + ", ".join(self.bridge.short(c) for c in failed))

            all_codes = [s["code"] for s in self.bridge.states()]
            complete = self.selected == all_codes and not failed and not any(
                self.states[c].get("status") == "skipped" for c in self.selected)
            scraped = [c for c in self.selected if self.states[c].get("status") == "ok"]
            written = self.bridge.save(self.result, self._all_raw(), complete, scraped)

            self.saved = {"at": _now(), "files": written, "complete": complete}
            self.phase = "saved"
            self.message = "Gespeichert."
            self._log("[UI] Gespeichert: " + ", ".join(written))
            return self.saved

    # ------------------------------------------------------------------
    # database
    # ------------------------------------------------------------------

    def db_status(self) -> dict:
        dsn = registry_import.load_dsn()
        return {"configured": bool(dsn), "target": registry_import.describe_target(dsn),
                "pushing": self.db_pushing, "last": self.db_last}

    def push_to_db(self) -> dict:
        """Load the saved registry into the database. Only a saved, complete state."""
        with self._lock:
            self._require_idle()
            if not self.result or self.phase != "saved" or not self.saved:
                raise Conflict("Bitte zuerst speichern. In die Datenbank kommt nur ein gespeicherter Stand.")
            if not self.result.get("dedup"):
                raise Conflict("Diese Scraper-Version liefert kein bereinigtes Register mit festen IDs. "
                               "Ohne das ist kein Import möglich.")
            if not self.saved.get("complete"):
                raise Conflict("Nur ein vollständiger Abruf aller Bundesländer darf in die Datenbank. "
                               "Sonst würden die fehlenden Hochschulen dort als nicht mehr gelistet markiert.")
            dsn = registry_import.load_dsn()
            if not dsn:
                raise Conflict("Die Datenbank ist noch nicht eingerichtet: In projectpathly_scraper_ui/.env "
                               "fehlt SUPABASE_DB_URL (Vorlage: .env.example).")
            self.db_pushing = True
            self._log(f"[DB] Import startet → {registry_import.describe_target(dsn)}")

        try:
            payload, sql = self.bridge.import_script()
            counts = registry_import.import_registry(
                dsn, payload, sql, source_file=self.bridge.registry_path.name)
        except registry_import.ImportProblem as exc:
            self._log(f"[DB] {exc}")
            raise Conflict(str(exc)) from exc
        except Exception as exc:
            self._log(f"[DB] {type(exc).__name__}: {exc}")
            raise Conflict(f"Import fehlgeschlagen: {type(exc).__name__}: {exc}") from exc
        finally:
            self.db_pushing = False

        with self._lock:
            self.db_last = {"at": _now(), "target": registry_import.describe_target(dsn), "counts": counts}
            self._log("[DB] Import fertig: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
            return self.db_last

    # ------------------------------------------------------------------
    # views for the API
    # ------------------------------------------------------------------

    def kpis(self) -> dict | None:
        if not self.result:
            return None
        masters = self.result["masters"]
        summary = self.bridge.summary(self.result)
        flags = [f for m in masters for f in m.get("validation_flags") or []]
        return {
            "states_ok": sum(1 for c in self.selected if self.states[c].get("status") == "ok"),
            "states_total": len(self.selected),
            "state_records": summary["input_records"],
            "institutions": summary["master_records"],
            "merged_away": summary["input_records"] - summary["master_records"],
            "multi_state": sum(1 for m in masters if len(m.get("states") or []) > 1),
            "locations": sum(len(m.get("locations") or []) for m in masters),
            "auto_merge_pairs": summary["auto_merge_pairs"],
            "review_open": summary["review_pairs"],
            "review_decided": len(self.decisions),
            "missing_url": sum(1 for m in masters if not m.get("official_url")),
            "with_flags": sum(1 for m in masters if m.get("validation_flags")),
            "flags_high": sum(1 for f in flags if f.get("severity") == "high"),
            "flag_counts": summary["flag_counts"],
            "by_type": summary["by_type"],
            "by_ownership": summary["by_ownership"],
            "by_recognition": summary["by_recognition"],
        }

    def snapshot(self, log_since: int = 0) -> dict:
        with self._lock:
            first = self.log_dropped
            start = max(log_since, first)
            return {
                "phase": self.phase,
                "busy": self.busy(),
                "message": self.message,
                "error": self.error,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "duration": self.duration,
                "source": self.source,
                "online": self.online,
                "selected": self.selected,
                "states": {c: dict(v) for c, v in self.states.items()},
                "failed_states": self._failed_states(),
                "kpis": self.kpis(),
                "conflicts": self._conflicts(),
                "saved": self.saved,
                "db": self.db_status(),
                "version": self.version,
                "log": self.log[start - first:],
                "log_next": first + len(self.log),
            }

    def records(self) -> dict:
        with self._lock:
            if not self.result:
                return {"version": self.version, "dedup": None, "rows": [], "review": []}

            open_keys = set()
            for c in self._open_pairs():
                open_keys.update((c["a"], c["b"]))

            rows = []
            for m in self.result["masters"]:
                keys = [s.get("source_key") for s in m.get("merged_from") or []]
                rows.append({**m, "_review_open": any(k in open_keys for k in keys)})

            by_key = {r["source_key"]: r for r in self.result["records"]}

            def side(key: str) -> dict:
                r = by_key.get(key) or {}
                return {
                    "source_key": key,
                    "name": r.get("name") or key.split("|", 1)[-1],
                    "state": r.get("state") or key.split("|", 1)[0],
                    "institution_type": r.get("institution_type"),
                    "ownership": r.get("ownership"),
                    "recognition_status": r.get("recognition_status"),
                    "official_url": r.get("official_url"),
                    "locations": r.get("locations") or [],
                    "sources": r.get("sources") or ([r["source"]] if r.get("source") else []),
                    "missing": key not in by_key,
                }

            review = []
            for c in self._open_pairs():
                review.append({"id": pair_id(c["a"], c["b"]), "decision": None, "note": "",
                               "reasons": c.get("reasons") or [],
                               "signals": c.get("signals") or {},
                               "a": side(c["a"]), "b": side(c["b"])})
            for pid, d in self.decisions.items():
                review.append({"id": pid, "decision": d["decision"], "note": d.get("note", ""),
                               "reasons": d.get("reasons") or [],
                               "signals": d.get("signals") or {},
                               "a": side(d["a"]), "b": side(d["b"])})

            return {"version": self.version, "dedup": self.result.get("dedup"),
                    "rows": rows, "review": review}

    def registry(self) -> list[dict]:
        with self._lock:
            if not self.result or self.busy():
                raise Conflict("Es gibt noch keinen fertigen Stand zum Herunterladen.")
            if self._open_pairs():
                raise Conflict("Es sind noch Duplikat-Paare offen. Bitte zuerst entscheiden.")
            return self.result["masters"]
