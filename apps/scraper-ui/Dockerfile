# Build context is the repository root (see docker-compose.yml in this folder).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PATHLY_SCRAPER_DIR=/app/scraper \
    PATHLY_UI_HOST=0.0.0.0 \
    PATHLY_UI_PORT=8000

WORKDIR /app/ui

# Packages of the scraper and of the UI.
COPY scrapers/hochschulen/requirements.txt /tmp/scraper-requirements.txt
COPY apps/scraper-ui/requirements.txt /tmp/ui-requirements.txt
RUN pip install -r /tmp/scraper-requirements.txt -r /tmp/ui-requirements.txt

COPY apps/scraper-ui/scraper_ui ./scraper_ui

# The scraper itself is mounted from the host at /app/scraper, so the UI always
# runs against the scraper version that is checked out.
EXPOSE 8000
CMD ["python", "-m", "scraper_ui"]
