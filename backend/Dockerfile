# Production image for the Community Roots backend, built for deploying to
# Railway. Local development never uses this image — it keeps running
# against a venv (see the root README's setup steps), so this Dockerfile
# only needs to satisfy one audience: a container that boots against an
# external Postgres. Full deploy walkthrough: docs/architecture.md §13.
#
# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:0.12.5 AS uv

FROM python:3.11-slim-bookworm AS builder

# uv is copied in as a static binary rather than installed via pip, so the
# builder stage never needs its own package manager bootstrap.
COPY --from=uv /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# `pyproject.toml`/`uv.lock` copied and synced before the rest of the source
# tree, so editing application code doesn't invalidate the dependency layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts


FROM python:3.11-slim-bookworm AS runtime

# Runs as a dedicated non-root user — this image only ever serves the API,
# it never needs root inside the container.
RUN groupadd --system app && useradd --system --gid app --create-home --home-dir /app app

WORKDIR /app
COPY --from=builder --chown=app:app /app /app

ENV PATH="/app/.venv/bin:$PATH"

# Default for `LOCAL_STORAGE_PATH` (see app/core/config.py). In production
# this directory must be a Railway volume mount, not container-local disk —
# see docs/architecture.md §13.1 "Storage persistente" — otherwise every
# redeploy wipes uploaded photos, since the container filesystem doesn't
# survive redeploys.
RUN mkdir -p /app/storage && chown app:app /app/storage

USER app

# Documents the app's own listening convention; it does not fix the port at
# runtime. Railway assigns the real port via $PORT at container start, and
# the CMD below binds uvicorn to it — a hardcoded port here would make
# Railway unable to route traffic to the container.
EXPOSE 8000

# Migrations run on every boot rather than as a separate release step:
# `alembic upgrade head` is idempotent, and Railway has no built-in release
# phase for a plain Docker deploy (see docs/architecture.md §13.1
# "Migrations" for the rationale and the manual `railway run` alternative).
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
