#!/usr/bin/env bash
# Startet die Scraper-UI ohne Docker.
# Legt beim ersten Aufruf eine eigene Python-Umgebung an (.venv in diesem Ordner)
# und installiert die Pakete des Scrapers und der UI.
set -euo pipefail

UI_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRAPER_DIR="${PATHLY_SCRAPER_DIR:-$UI_DIR/../../scrapers/hochschulen}"
VENV="$UI_DIR/.venv"

if [ ! -f "$SCRAPER_DIR/registry/run.py" ]; then
  echo "Scraper nicht gefunden unter: $SCRAPER_DIR" >&2
  echo "Pfad mit PATHLY_SCRAPER_DIR=/pfad/zum/scraper setzen." >&2
  exit 1
fi

if [ ! -x "$VENV/bin/python" ]; then
  echo "Erster Start: Python-Umgebung wird eingerichtet (dauert etwa eine Minute) …"
  python3 -m venv "$VENV"
fi

# Nur neu installieren, wenn sich eine der Paketlisten geändert hat.
STAMP="$VENV/.installed"
if [ ! -f "$STAMP" ] || [ "$SCRAPER_DIR/requirements.txt" -nt "$STAMP" ] || [ "$UI_DIR/requirements.txt" -nt "$STAMP" ]; then
  "$VENV/bin/pip" install --quiet --disable-pip-version-check \
    -r "$SCRAPER_DIR/requirements.txt" -r "$UI_DIR/requirements.txt"
  touch "$STAMP"
fi

export PATHLY_SCRAPER_DIR="$SCRAPER_DIR"
export PYTHONPATH="$UI_DIR${PYTHONPATH:+:$PYTHONPATH}"
exec "$VENV/bin/python" -m scraper_ui
