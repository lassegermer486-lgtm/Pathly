"""
v1.3 reliability: source failures, count drift, build status, safe publishing.

registry.run adds to every state entry of data/reports/registry_run.json:

    source_status      success | failed | skipped
    failure_reason     only when not success (error text, "empty_result", ...)
    previous_count     last accepted count of this state (data/master/state_counts.json)
    current_count      institutions found now
    absolute_delta     current - previous
    relative_delta     (current - previous) / previous, 3 decimals
    count_status       normal | suspicious | no_baseline | source_failed
    production_safe    this state may replace the published state
    request_attempts   HTTP attempts of this state, retries included
    request_retries

and writes the whole build to data/reports/build_status.json:

    complete   all 16 states successful, no count drift  -> production safe
    review     all 16 successful, count drift in a state -> not production safe
               until a person looked at it and accepted it (--accept-drift)
    degraded   a state failed, was skipped or not requested
    failed     no state successful

Count drift is a quality signal, not proof of an error: nothing is deleted or
restored because of it. It only holds back publishing until someone checked
the state. The accepted count becomes the new baseline.

registry.master.build and registry.master.supabase_import refuse to replace
the published master files / import script while the discovery output they
would be built from is not production safe (--allow-degraded overrides).

    python -m registry.reliability                        # show last build status
    python -m registry.reliability --accept-drift DE-NW   # after checking DE-NW
    python -m registry.reliability --accept-drift all
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


DRIFT_ABSOLUTE = 10
DRIFT_RELATIVE = 0.30

BUILD_STATUS_PATH = Path("data/reports/build_status.json")
STATE_COUNTS_PATH = Path("data/master/state_counts.json")
RUN_REPORT_PATH = Path("data/reports/registry_run.json")
NORMALIZED_PATH = Path("data/normalized/universities_de.json")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_json(path: Path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def write_json(path: Path, data) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def file_sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except FileNotFoundError:
        return None


# ----------------------------------------------------------------------
# Count drift
# ----------------------------------------------------------------------

def count_drift(previous: int | None, current: int) -> dict:
    """
    suspicious if |current - previous| > 10 or |relative change| > 30 %.
    The relative rule catches small states (Saarland 8 -> 3).
    """
    if not previous:
        return {
            "previous_count": previous,
            "current_count": current,
            "absolute_delta": None,
            "relative_delta": None,
            "count_status": "no_baseline",
        }

    delta = current - previous
    relative = delta / previous
    suspicious = abs(delta) > DRIFT_ABSOLUTE or abs(relative) > DRIFT_RELATIVE

    return {
        "previous_count": previous,
        "current_count": current,
        "absolute_delta": delta,
        "relative_delta": round(relative, 3),
        "count_status": "suspicious" if suspicious else "normal",
    }


# ----------------------------------------------------------------------
# Per state
# ----------------------------------------------------------------------

def source_status(entry: dict) -> tuple[str, str | None]:
    status = entry.get("status")

    if status == "OK":
        if entry.get("universities"):
            return "success", None
        # A state page showing a maintenance notice parses to nothing.
        return "failed", "empty_result"

    if status in ("SKIPPED", "TODO"):
        return "skipped", status.lower()

    return "failed", entry.get("error") or str(status or "unknown")


def assess_state(entry: dict, previous_count: int | None) -> dict:
    """The registry_run.json entry plus the v1.3 fields (existing fields unchanged)."""
    status, reason = source_status(entry)
    current = entry.get("universities") or 0

    added = {"source_status": status}
    if reason:
        added["failure_reason"] = reason

    if status == "success":
        added.update(count_drift(previous_count, current))
        added["production_safe"] = added["count_status"] != "suspicious"
    else:
        added.update(
            previous_count=previous_count,
            current_count=current,
            absolute_delta=None,
            relative_delta=None,
            count_status="source_failed" if status == "failed" else "not_run",
            production_safe=False,
        )

    return {**entry, **added}


# ----------------------------------------------------------------------
# Whole build
# ----------------------------------------------------------------------

def build_status(
    entries: list[dict],
    expected_states: list[str],
    normalized_path: Path | None = None,
    now: str | None = None,
) -> dict:
    requested = [e["state"] for e in entries]
    successful = [e["state"] for e in entries if e.get("source_status") == "success"]
    failed = [e["state"] for e in entries if e.get("source_status") == "failed"]
    skipped = [e["state"] for e in entries if e.get("source_status") == "skipped"]
    missing = [s for s in expected_states if s not in requested]
    drift = [
        e["state"]
        for e in entries
        if e.get("count_status") == "suspicious" and not e.get("drift_accepted")
    ]

    if not successful:
        status = "failed"
    elif failed or skipped or missing:
        status = "degraded"
    elif drift:
        status = "review"
    else:
        status = "complete"

    reasons = []
    if failed:
        reasons.append(f"failed: {', '.join(failed)}")
    if skipped:
        reasons.append(f"skipped: {', '.join(skipped)}")
    if missing:
        reasons.append(f"not requested: {', '.join(missing)}")
    if drift:
        reasons.append(f"count drift to review: {', '.join(drift)}")

    return {
        "generated_at": now or _now(),
        "build_status": status,
        "production_safe": status == "complete",
        "reasons": reasons,
        "states_expected": len(expected_states),
        "states_successful": len(successful),
        "failed_states": failed,
        "skipped_states": skipped,
        "missing_states": missing,
        "count_drift_states": drift,
        "normalized_output": str(normalized_path) if normalized_path else None,
        "normalized_sha256": file_sha256(normalized_path) if normalized_path else None,
        "states": [
            {
                key: e.get(key)
                for key in (
                    "state", "status", "source_status", "failure_reason",
                    "previous_count", "current_count", "absolute_delta",
                    "relative_delta", "count_status", "drift_accepted",
                    "production_safe", "request_attempts", "request_retries",
                )
                if key in e
            }
            for e in entries
        ],
    }


# ----------------------------------------------------------------------
# Baseline: last accepted count per state
# ----------------------------------------------------------------------

def load_state_counts(
    path: Path = STATE_COUNTS_PATH,
    legacy_report: Path = RUN_REPORT_PATH,
) -> dict[str, int]:
    """
    {state: count}. Before the first v1.3 run there is no state_counts.json;
    then the last registry_run.json (v1.2) is the baseline. Read it before
    registry.run overwrites it.
    """
    data = _read_json(path)
    if data is not None:
        return {s: v["count"] for s, v in (data.get("states") or {}).items()}

    counts = {}
    for entry in _read_json(legacy_report) or []:
        if entry.get("status") == "OK" and entry.get("universities"):
            counts[entry["state"]] = entry["universities"]
    return counts


def update_state_counts(
    entries: list[dict],
    path: Path = STATE_COUNTS_PATH,
    previous: dict[str, int] | None = None,
    now: str | None = None,
) -> dict:
    """
    Only successful states with an unremarkable (or accepted) count become
    the new baseline. Failed states and unaccepted drift keep the old one.
    """
    now = now or _now()
    data = _read_json(path) or {"version": 1, "states": {}}
    states = data.setdefault("states", {})

    # First v1.3 run: keep the v1.2 baseline for states not updated now.
    for state, count in (previous or {}).items():
        states.setdefault(state, {"count": count, "updated_at": None, "origin": "registry_run_v1.2"})

    for e in entries:
        if e.get("source_status") != "success":
            continue
        if e.get("count_status") == "suspicious" and not e.get("drift_accepted"):
            continue
        states[e["state"]] = {
            "count": e["current_count"],
            "updated_at": now,
            "origin": "accepted_drift" if e.get("drift_accepted") else "run",
        }

    data["states"] = dict(sorted(states.items()))
    write_json(path, data)
    return data


def accept_drift(
    states: list[str],
    status_path: Path = BUILD_STATUS_PATH,
    counts_path: Path = STATE_COUNTS_PATH,
    expected_states: list[str] | None = None,
) -> dict:
    """A person checked the drifted states: their counts become the baseline."""
    status = _read_json(status_path)
    if status is None:
        raise SystemExit(f"No build status at {status_path}. Run python -m registry.run first.")

    accept_all = [s.lower() for s in states] == ["all"]
    accepted = []
    entries = status["states"]

    for e in entries:
        if e.get("count_status") != "suspicious":
            continue
        if accept_all or e["state"] in states:
            e["drift_accepted"] = True
            e["production_safe"] = True
            accepted.append(e["state"])

    unknown = [] if accept_all else [s for s in states if s not in accepted]
    if unknown:
        print(f"[WARN] no count drift to accept for: {', '.join(unknown)}")

    update_state_counts([e for e in entries if e["state"] in accepted], counts_path)

    if expected_states is None:
        expected_states = [e["state"] for e in entries] + status.get("missing_states", [])

    # Recompute from the stored per-state entries; the hash still refers to
    # the discovery output this status was written for.
    sha = status.get("normalized_sha256")
    new = build_status(entries, expected_states)
    new.update(
        normalized_output=status.get("normalized_output"),
        normalized_sha256=sha,
        accepted_drift=sorted(set(status.get("accepted_drift", []) + accepted)),
        accepted_at=_now(),
    )
    write_json(status_path, new)
    return new


# ----------------------------------------------------------------------
# Publishing gate
# ----------------------------------------------------------------------

def production_gate(
    step: str,
    allow_degraded: bool = False,
    status_path: Path = BUILD_STATUS_PATH,
    normalized_path: Path = NORMALIZED_PATH,
) -> bool:
    """
    True if `step` may replace the published registry files. Prints why not.

    The status only counts for the discovery output it was written for: data
    from before v1.3, or a normalized file written elsewhere (scraper UI,
    git checkout), is not judged here.
    """
    status = _read_json(status_path)

    if status is None:
        print(f"[BUILD] {step}: no discovery build status ({status_path}); not checked")
        return True

    if status.get("normalized_sha256") != file_sha256(normalized_path):
        print(
            f"[BUILD] {step}: {normalized_path} is not the output the build status "
            "was written for; not checked"
        )
        return True

    if status.get("production_safe"):
        return True

    summary = f"{status.get('build_status', '?').upper()} — " + "; ".join(status.get("reasons") or [])

    if allow_degraded:
        print(f"[WARN] {step}: build is {summary}. Writing anyway (--allow-degraded).")
        return True

    print(f"[BLOCKED] {step}: discovery build is {summary}")
    print("          The published registry files stay unchanged.")
    print("          Inspect data/reports/build_status.json; after checking a count drift:")
    print("            python -m registry.reliability --accept-drift <STATE>")
    print("          To write anyway (debugging only): --allow-degraded")
    return False


def build_summary(status_path: Path = BUILD_STATUS_PATH) -> dict | None:
    """Short form for other reports (validation_report.json)."""
    status = _read_json(status_path)
    if status is None:
        return None
    return {
        key: status.get(key)
        for key in (
            "generated_at", "build_status", "production_safe", "reasons",
            "failed_states", "count_drift_states", "accepted_drift",
        )
        if key in status
    }


def print_status(status: dict) -> None:
    print(
        f"BUILD:        {status['build_status'].upper()}"
        f" ({'production safe' if status['production_safe'] else 'NOT production safe'})"
    )
    for reason in status.get("reasons") or []:
        print(f"              {reason}")
    for e in status.get("states") or []:
        if e.get("count_status") == "suspicious":
            accepted = " (accepted)" if e.get("drift_accepted") else ""
            print(
                f"DRIFT:        {e['state']}: {e['previous_count']} -> {e['current_count']}"
                f" ({e['absolute_delta']:+d}, {e['relative_delta']:+.1%}){accepted}"
            )


def main():
    parser = argparse.ArgumentParser(description="ProjectPathly — discovery build status")
    parser.add_argument(
        "--accept-drift",
        nargs="+",
        metavar="STATE",
        help="State codes (or 'all') whose count drift was checked and is correct",
    )
    args = parser.parse_args()

    if args.accept_drift:
        status = accept_drift(args.accept_drift)
    else:
        status = _read_json(BUILD_STATUS_PATH)
        if status is None:
            sys.exit(f"No build status at {BUILD_STATUS_PATH}. Run python -m registry.run first.")

    print_status(status)


if __name__ == "__main__":
    main()
