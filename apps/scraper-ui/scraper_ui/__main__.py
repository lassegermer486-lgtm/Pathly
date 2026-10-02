"""python -m scraper_ui  — start the scraper UI on http://127.0.0.1:8000"""
from __future__ import annotations

import os
import sys

import uvicorn

from .app import create_app
from .bridge import ScraperNotFound


def main() -> None:
    host = os.environ.get("PATHLY_UI_HOST", "127.0.0.1")
    port = int(os.environ.get("PATHLY_UI_PORT", "8000"))
    try:
        app = create_app()
    except ScraperNotFound as exc:
        sys.exit(str(exc))

    shown = "localhost" if host in ("127.0.0.1", "0.0.0.0") else host
    print(f"\n  Scraper-UI läuft:  http://{shown}:{port}\n  Beenden mit Strg+C\n", file=sys.stderr)
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
