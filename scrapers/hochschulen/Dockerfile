FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY registry ./registry
COPY tests ./tests

# Ergebnisse (raw, normalized, reports, source_cache) landen in /app/data
# und werden per Volume auf den Host gemappt.
VOLUME ["/app/data"]

ENTRYPOINT ["python", "-m", "registry.run"]
