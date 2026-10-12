# Build context: repository root (needed for packages/py-common).
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv

WORKDIR /srv/services/auth

COPY packages/py-common /srv/packages/py-common
COPY services/auth/pyproject.toml services/auth/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY services/auth/app ./app
COPY services/auth/alembic ./alembic
COPY services/auth/alembic.ini ./

RUN useradd --system --uid 1001 app && chown -R app /srv
USER app

ENV PATH="/srv/services/auth/.venv/bin:$PATH"
EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
