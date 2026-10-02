"""
The whole registry build, in order (spec §39):

    discovery      16 state sources            registry.run
    international  ETER + IPEDS candidates     registry.international.run      (v1.3)
    websites       verify / resolve URLs        registry.enrichment.website_resolver
    websites_intl  the same for the candidates  (separate in/out files)
    agent          last-resort URL resolution   registry.enrichment.agent_resolver
    agent_intl     the same for the candidates  (separate in/out files)
    dedup          German + international       registry.master.dedup
    master      names, lifecycle, IDs        registry.master.build
    supabase    import script                registry.master.supabase_import

Usage (from scrapers/hochschulen/):

    python -m registry.pipeline
    python -m registry.pipeline --from dedup        # rebuild from enriched data
    python -m registry.pipeline --agent-cache-only  # no API calls

v1.3: after discovery the pipeline stops if the build is not production safe
(a state failed, or a count drift needs review; see registry.reliability).
--allow-degraded runs on anyway and lets master/supabase write.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

from registry import reliability
from registry.enrichment.agent_resolver import load_dotenv


STEPS = [
    ("discovery", "registry.run"),
    ("international", "registry.international.run"),
    ("websites", "registry.enrichment.website_resolver"),
    ("websites_intl", "registry.enrichment.website_resolver"),
    ("agent", "registry.enrichment.agent_resolver"),
    ("agent_intl", "registry.enrichment.agent_resolver"),
    ("dedup", "registry.master.dedup"),
    ("master", "registry.master.build"),
    ("supabase", "registry.master.supabase_import"),
]

# The international candidates run through the unchanged resolvers with
# their own files, so the German enriched data stays as it is.
STEP_ARGS = {
    "websites_intl": [
        "--in", "data/normalized/universities_intl.json",
        "--out", "data/enriched/universities_intl_urls.json",
        "--report", "data/reports/url_resolution_intl.json",
    ],
    "agent_intl": [
        "--in", "data/enriched/universities_intl_urls.json",
        "--report", "data/reports/agent_resolution_intl.json",
    ],
}

DISCOVERY_STEPS = {"discovery", "international"}


def main():
    names = [name for name, _ in STEPS]

    parser = argparse.ArgumentParser(description="ProjectPathly — full registry build")
    parser.add_argument("--from", dest="start", choices=names, default=names[0])
    parser.add_argument("--to", dest="stop", choices=names, default=names[-1])
    parser.add_argument("--agent-cache-only", action="store_true")
    parser.add_argument("--allow-degraded", action="store_true",
                        help="Continue and publish although the discovery build is not production safe")
    args = parser.parse_args()

    load_dotenv()
    selected = STEPS[names.index(args.start): names.index(args.stop) + 1]
    gate_checked = False

    for name, module in selected:
        # Everything after discovery builds on its output: check it once, early.
        if name not in DISCOVERY_STEPS and not gate_checked:
            gate_checked = True
            if not reliability.production_gate("pipeline", args.allow_degraded):
                sys.exit(2)

        command = [sys.executable, "-m", module, *STEP_ARGS.get(name, [])]

        if name in ("master", "supabase") and args.allow_degraded:
            command.append("--allow-degraded")

        if name in ("agent", "agent_intl") and (args.agent_cache_only or "OPENROUTER_API_KEY" not in os.environ):
            if not args.agent_cache_only:
                print("[PIPELINE] OPENROUTER_API_KEY not set: agent uses cached answers only")
            command.append("--cache-only")

        print(f"\n[PIPELINE] {name}: {' '.join(command[1:])}")
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
