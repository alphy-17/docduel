# DocDuel backend image. GitHub Actions builds it on every push to main and stores it in
# GitHub Container Registry (ghcr.io); Azure Container Apps runs it. Local build:
#   docker build -t docduel-api .
# The frontend is deployed separately (Vercel). No secrets are baked in: Azure injects them.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1

WORKDIR /app/backend
# Dependencies first so code edits do not reinstall them.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/src ./src
COPY backend/prompts ./prompts
RUN uv sync --frozen --no-dev

# Runtime files the API reads: model/price config, benchmark reports, frozen test manifest.
COPY config /app/config
COPY reports /app/reports
COPY data/test/manifest.json /app/data/test/manifest.json

# Production defaults (rule R7: uploads are not kept). SQLite lives in /tmp and is lost when
# the app scales to zero, which is fine: the public site shows replays and the benchmark from
# static files.
ENV LIVE_MODE_ENABLED=true KEEP_UPLOADS=false CORRECTIONS_ENABLED=false \
    DATABASE_URL=sqlite:////tmp/docduel.db PORT=8000

RUN useradd --create-home app && chown -R app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=60s --timeout=5s CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/api/health')"
CMD ["sh", "-c", "uv run --no-sync uvicorn docduel.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
