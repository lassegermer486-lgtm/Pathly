"""
The whole registry build, in order (spec §39):

    discovery   16 state sources            registry.run
    websites    verify / resolve URLs        registry.enrichment.website_resolver
    agent       last-resort URL resolution   registry.enrichment.agent_resolver
    dedup       nationwide deduplication     registry.master.dedup
    master      names, lifecycle, IDs        registry.master.build
    supabase    import script                registry.master.supabase_import

Usage (from projectpathly_registry_scraper/):

    python -m registry.pipeline
    python -m registry.pipeline --from dedup        # rebuild from enriched data
    python -m registry.pipeline --agent-cache-only  # no API calls
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

from registry.enrichment.agent_resolver import load_dotenv


STEPS = [
    ("discovery", "registry.run"),
    ("websites", "registry.enrichment.website_resolver"),
    ("agent", "registry.enrichment.agent_resolver"),
    ("dedup", "registry.master.dedup"),
    ("master", "registry.master.build"),
    ("supabase", "registry.master.supabase_import"),
]


def main():
    names = [name for name, _ in STEPS]

    parser = argparse.ArgumentParser(description="ProjectPathly — full registry build")
    parser.add_argument("--from", dest="start", choices=names, default=names[0])
    parser.add_argument("--to", dest="stop", choices=names, default=names[-1])
    parser.add_argument("--agent-cache-only", action="store_true")
    args = parser.parse_args()

    load_dotenv()
    selected = STEPS[names.index(args.start): names.index(args.stop) + 1]

    for name, module in selected:
        command = [sys.executable, "-m", module]

        if name == "agent" and (args.agent_cache_only or "OPENROUTER_API_KEY" not in os.environ):
            if not args.agent_cache_only:
                print("[PIPELINE] OPENROUTER_API_KEY not set: agent uses cached answers only")
            command.append("--cache-only")

        print(f"\n[PIPELINE] {name}: {' '.join(command[1:])}")
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
