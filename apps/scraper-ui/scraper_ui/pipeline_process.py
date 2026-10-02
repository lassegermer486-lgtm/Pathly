"""
Runs the scraper's own pipeline (python -m registry.pipeline) as a process
and turns its output into a live feed.

The UI does not run a second pipeline: this is the same command as on the
command line, and everything it shows afterwards comes from the reports the
pipeline writes (build_reports.py). The output lines are only sorted into
three levels for the feed:

    step     a pipeline step starts or ends            [PIPELINE] …
    item     a source or an institution is processed   [FETCH] DE-BW …, [3/70] Name ✓
    result   what came out                             [OK] DE-BW: 69 …, BUILD: COMPLETE
    warn / error

Everything else stays in the raw log only.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
from datetime import datetime, timezone

MAX_EVENTS = 5000
MAX_RAW = 20000

STEP_LABEL = {
    "discovery": "Deutsche Discovery",
    "international": "Internationale Discovery",
    "websites": "Website-Prüfung (deutsch)",
    "websites_intl": "Website-Prüfung (international)",
    "agent": "Agent-Auflösung (deutsch)",
    "agent_intl": "Agent-Auflösung (international)",
    "dedup": "Deduplizierung",
    "master": "Master-Register, Präsenz, Online-DE",
    "supabase": "Supabase-Export",
}

# Pipeline steps in order (registry.pipeline STEPS)
PIPELINE_STEPS = list(STEP_LABEL)

RESOLVER_RE = re.compile(r"^\[(RESOLVED|REVIEW|UNRESOLVED)\s*\]\s+(\S+)\s+(.+?)\s{2,}")
RESOLVER_MARK = {"RESOLVED": "✓", "REVIEW": "?", "UNRESOLVED": "✗"}
SUMMARY_RE = re.compile(
    r"^(STATES|UNIVERSITIES|LOCATIONS|SOURCES|CANDIDATES|BUILD|DRIFT|CHECKED|URL COVERAGE|ASKED|ACCEPTED|"
    r"SOURCE RECORDS|INSTITUTIONS|MERGED GROUPS|REVIEW CASES|CONFLICTS|Master universities|"
    r"German presence|Online from Germany|Market access|Stable IDs|Review required|universities)\s*:?\s+(.*)$"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class LineParser:
    """Turns pipeline output lines into feed events (or None for raw-only lines)."""

    def __init__(self):
        self.step: str | None = None
        self.total = 0
        self.index = 0

    def parse(self, line: str) -> dict | None:
        text = line.rstrip()
        stripped = text.strip()
        if not stripped or set(stripped) <= {"=", "-"}:
            return None

        m = re.match(r"^\[PIPELINE\] (\w+): (.*)$", stripped)
        if m:
            name = m.group(1)
            if name == "complete":
                self.step = None
                return {"level": "step", "step": None, "text": "Pipeline abgeschlossen", "state": "done"}
            self.step, self.total, self.index = name, 0, 0
            return {"level": "step", "step": name, "text": f"{STEP_LABEL.get(name, name)} gestartet",
                    "state": "start"}
        if stripped.startswith("[PIPELINE]"):
            return {"level": "warn", "step": self.step, "text": stripped[len("[PIPELINE] "):]}

        m = re.match(r"^\[START\] (\d+) (?:of \d+ )?records", stripped)
        if m:
            self.total, self.index = int(m.group(1)), 0
            return {"level": "item", "step": self.step, "text": f"{self.total} Einträge zu prüfen"}

        m = RESOLVER_RE.match(stripped)
        if m:
            self.index += 1
            status, source, name = m.groups()
            of = f"/{self.total}" if self.total else ""
            return {"level": "item", "step": self.step, "status": status.lower(),
                    "text": f"[{self.index}{of}] {name} {RESOLVER_MARK[status]}"}

        m = re.match(r"^\[FETCH\] (\S+) — (.*)$", stripped)
        if m:
            return {"level": "item", "step": self.step, "source": m.group(1),
                    "text": f"[{m.group(1)}] Quelle wird abgerufen …"}

        m = re.match(r"^\[OK\] (\S+): (.*)$", stripped)
        if m:
            return {"level": "result", "step": self.step, "source": m.group(1),
                    "text": f"[{m.group(1)}] {m.group(2)}"}

        m = re.match(r"^\[CHECKSUM\] (\S+) (.*)$", stripped)
        if m:
            return {"level": "result", "step": self.step, "source": m.group(1),
                    "text": f"[{m.group(1)}] Prüfsumme {m.group(2)}"}

        if stripped.startswith(("[ERROR]", "[BLOCKED]", "[AGENT ERROR]", "Traceback")):
            return {"level": "error", "step": self.step, "text": stripped}
        if stripped.startswith("[WARN]"):
            return {"level": "warn", "step": self.step, "text": stripped[len("[WARN] "):]}

        m = SUMMARY_RE.match(stripped)
        if m:
            level = "warn" if m.group(1) == "DRIFT" else "result"
            if m.group(1) == "BUILD" and "NOT production safe" in m.group(2):
                level = "warn"
            return {"level": level, "step": self.step, "text": f"{m.group(1)}: {m.group(2)}"}
        return None


class PipelineProcess:
    """One pipeline run at a time; output kept for the feed and the raw log."""

    def __init__(self, scraper_dir, python: str | None = None):
        self.dir = str(scraper_dir)
        self.python = python or sys.executable
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._reset()

    def _reset(self):
        self.running = False
        self.command: list[str] = []
        self.started_at: str | None = None
        self.finished_at: str | None = None
        self.exit_code: int | None = None
        self.cancelled = False
        self.step: str | None = None
        self.steps_done: list[str] = []
        self.events: list[dict] = []
        self.raw: list[str] = []
        self.dropped = 0
        self.raw_dropped = 0

    def command_for(self, start: str, stop: str, agent_api: bool) -> list[str]:
        if start not in PIPELINE_STEPS or stop not in PIPELINE_STEPS:
            raise ValueError("unbekannter Schritt")
        if PIPELINE_STEPS.index(start) > PIPELINE_STEPS.index(stop):
            raise ValueError("Start liegt hinter dem Ende")
        command = [self.python, "-m", "registry.pipeline", "--from", start, "--to", stop]
        if not agent_api:
            command.append("--agent-cache-only")
        return command

    def start(self, start: str = "discovery", stop: str = "supabase", agent_api: bool = False,
              command: list[str] | None = None) -> None:
        with self._lock:
            if self.running:
                raise RuntimeError("Es läuft bereits ein Build.")
            cmd = command or self.command_for(start, stop, agent_api)
            self._reset()
            self.running = True
            self.command = cmd
            self.started_at = _now()
            self._add({"level": "step", "step": None, "state": "start",
                       "text": "Registry-Build gestartet: " + " ".join(cmd[1:])})
            env = {**os.environ, "PYTHONUNBUFFERED": "1"}
            self._proc = subprocess.Popen(
                cmd, cwd=self.dir, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
            )
        threading.Thread(target=self._read, name="pipeline-output", daemon=True).start()

    def cancel(self) -> None:
        with self._lock:
            if not self.running or not self._proc:
                raise RuntimeError("Es läuft kein Build.")
            self.cancelled = True
            self._proc.terminate()

    def _add(self, event: dict) -> None:
        event = {"time": _now(), **event}
        self.events.append(event)
        overflow = len(self.events) - MAX_EVENTS
        if overflow > 0:
            del self.events[:overflow]
            self.dropped += overflow

    def _read(self) -> None:
        parser = LineParser()
        proc = self._proc
        for line in proc.stdout:
            line = line.rstrip("\n")
            event = parser.parse(line)
            with self._lock:
                self.raw.append(line)
                if len(self.raw) > MAX_RAW:
                    del self.raw[: len(self.raw) - MAX_RAW]
                    self.raw_dropped += 1
                if event:
                    if event["level"] == "step" and event.get("state") == "start" and event.get("step"):
                        if self.step:
                            self.steps_done.append(self.step)
                        self.step = event["step"]
                    self._add(event)
        code = proc.wait()
        with self._lock:
            if self.step and code == 0:
                self.steps_done.append(self.step)
            self.exit_code = code
            self.running = False
            self.finished_at = _now()
            if self.cancelled:
                self._add({"level": "error", "step": self.step, "text": "Build abgebrochen."})
            elif code == 2:
                self._add({"level": "error", "step": self.step,
                           "text": "Build angehalten: nicht produktionssicher (siehe Quellen und Reviews)."})
            elif code != 0:
                self._add({"level": "error", "step": self.step, "text": f"Build fehlgeschlagen (Exit-Code {code})."})
            self.step = None

    def snapshot(self, since: int = 0, raw_since: int = 0) -> dict:
        with self._lock:
            start = max(since, self.dropped)
            raw_start = max(raw_since, self.raw_dropped)
            return {
                "running": self.running,
                "command": self.command,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "exit_code": self.exit_code,
                "cancelled": self.cancelled,
                "step": self.step,
                "steps_done": list(self.steps_done),
                "events": self.events[start - self.dropped:],
                "events_next": self.dropped + len(self.events),
                "raw": self.raw[raw_start - self.raw_dropped:],
                "raw_next": self.raw_dropped + len(self.raw),
            }
