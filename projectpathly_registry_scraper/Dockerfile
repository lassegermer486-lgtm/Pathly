FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY registry ./registry
COPY config ./config
COPY tests ./tests

# data/ (SH/SL fallback sources, --save output) and config/ (overrides,
# id registry) are mounted from the host by docker-compose.yml.
ENTRYPOINT ["python", "-m", "registry.run"]
