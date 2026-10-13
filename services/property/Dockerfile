# Build context: repository root (needed for packages/py-common).
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv

WORKDIR /srv/services/property

COPY packages/py-common /srv/packages/py-common
COPY services/property/pyproject.toml services/property/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY services/property/app ./app
COPY services/property/alembic ./alembic
COPY services/property/alembic.ini ./

RUN useradd --system --uid 1001 app && chown -R app /srv
USER app

ENV PATH="/srv/services/property/.venv/bin:$PATH"
EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
