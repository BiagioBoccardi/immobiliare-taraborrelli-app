#!/usr/bin/env bash
# Local trial environment for the admin panel, without docker compose.
#
#   scripts/dev-local.sh up     start everything and open http://localhost:5173
#   scripts/dev-local.sh down   stop everything (data is discarded)
#   scripts/dev-local.sh logs   follow the services' logs
#
# What it starts: PostgreSQL in Docker (one database per service), the auth, lead and
# property services with uv, an in-memory S3 for photos (moto, run with uvx) and the admin
# panel with Vite. Events are disabled. Every start begins from empty data, with a test
# administrator and two sample owner requests.
#
# Requirements: Docker, uv, Node.js 20+ and openssl. On Windows use WSL2.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STATE="$ROOT/.dev"
DB_CONTAINER="taraborrelli-dev-db"
DB_PORT="${DEV_DB_PORT:-55432}"
S3_PORT="${DEV_S3_PORT:-9100}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@taraborrelli.test}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-Admin-di-prova-1}"

info() { printf '\033[1;34m›\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; exit 1; }

require() {
  for tool in docker uv node npm openssl curl; do
    command -v "$tool" >/dev/null 2>&1 || fail "Manca '$tool': installalo e riprova."
  done
  docker info >/dev/null 2>&1 || fail "Docker non è in esecuzione."
}

wait_for() {
  local url=$1 name=$2
  for _ in $(seq 1 60); do
    curl -fs "$url" >/dev/null 2>&1 && return 0
    sleep 1
  done
  fail "$name non risponde: guarda $STATE/logs/"
}

# start_bg NAME DIR COMMAND...: runs COMMAND in DIR in the background, logging to .dev/logs.
start_bg() {
  local name=$1 dir=$2; shift 2
  ( cd "$dir" && "$@" >>"$STATE/logs/$name.log" 2>&1 & echo $! >>"$STATE/pids" )
}

down() {
  if [ -f "$STATE/pids" ]; then
    while read -r pid; do
      pkill -P "$pid" 2>/dev/null || true
      kill "$pid" 2>/dev/null || true
    done <"$STATE/pids"
    rm -f "$STATE/pids"
  fi
  docker rm -f "$DB_CONTAINER" >/dev/null 2>&1 || true
  info "Ambiente di prova fermato."
}

up() {
  require
  [ -f "$STATE/pids" ] && down
  mkdir -p "$STATE/logs"

  info "PostgreSQL (porta $DB_PORT)…"
  docker run -d --rm --name "$DB_CONTAINER" -e POSTGRES_USER=dev -e POSTGRES_PASSWORD=dev \
    -e POSTGRES_DB=auth -p "$DB_PORT:5432" postgres:16-alpine >/dev/null
  until docker exec "$DB_CONTAINER" pg_isready -U dev -h localhost >/dev/null 2>&1; do sleep 1; done
  sleep 2
  for db in lead property; do docker exec "$DB_CONTAINER" psql -U dev -d auth -qc "CREATE DATABASE $db"; done

  info "Chiavi JWT di prova…"
  openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "$STATE/jwt-private.pem" 2>/dev/null
  openssl pkey -in "$STATE/jwt-private.pem" -pubout -out "$STATE/jwt-public.pem"

  info "S3 in memoria per le foto (porta $S3_PORT)…"
  start_bg s3 "$STATE" uvx --quiet --from "moto[server]" moto_server -p "$S3_PORT"
  wait_for "http://localhost:$S3_PORT" "S3"

  export EVENTS_ENABLED=false LOG_LEVEL=INFO
  local port=8001
  for service in auth lead property; do
    info "Servizio $service (porta $port)…"
    local db_url="postgresql+asyncpg://dev:dev@localhost:$DB_PORT/$service"
    (cd "$ROOT/services/$service" && DATABASE_URL="$db_url" uv run --quiet alembic upgrade head) \
      >>"$STATE/logs/$service.log" 2>&1 || fail "Migrazioni di $service fallite: $STATE/logs/$service.log"
    if [ "$service" = auth ]; then
      start_bg "$service" "$ROOT/services/$service" env DATABASE_URL="$db_url" \
        JWT_PRIVATE_KEY="$(cat "$STATE/jwt-private.pem")" \
        uv run --quiet uvicorn app.main:app --port "$port"
    else
      start_bg "$service" "$ROOT/services/$service" env DATABASE_URL="$db_url" \
        JWT_PUBLIC_KEY="$(cat "$STATE/jwt-public.pem")" \
        S3_ENDPOINT_URL="http://localhost:$S3_PORT" S3_ACCESS_KEY=dev S3_SECRET_KEY=dev \
        S3_CREATE_BUCKET=true MEDIA_PUBLIC_BASE_URL="http://localhost:$S3_PORT/property-media" \
        uv run --quiet uvicorn app.main:app --port "$port"
    fi
    wait_for "http://localhost:$port/health" "$service"
    port=$((port + 1))
  done

  info "Amministratore di prova…"
  (cd "$ROOT/services/auth" && DATABASE_URL="postgresql+asyncpg://dev:dev@localhost:$DB_PORT/auth" \
    ADMIN_PASSWORD="$ADMIN_PASSWORD" uv run --quiet python -c "
import os, sys
import app.cli as cli
cli.getpass.getpass = lambda _prompt: os.environ['ADMIN_PASSWORD']
sys.exit(cli.main(['create-admin', '--email', '$ADMIN_EMAIL', '--name', 'Amministratore Prova']))
") >>"$STATE/logs/auth.log" 2>&1 || fail "Creazione amministratore fallita: $STATE/logs/auth.log"

  info "Richieste di esempio dai moduli pubblici…"
  curl -fs -o /dev/null -X POST "http://localhost:8002/api/v1/lead/valuations" \
    -H 'Content-Type: application/json' -d '{"full_name":"Mario Rossi","phone":"333 000 0000","municipality":"Chieti","property_type":"apartment","surface_sqm":95,"rooms":4,"condition":"good","intention":"decided","consent":{"privacy_accepted":true,"privacy_policy_version":"2026-01","marketing_accepted":true}}'
  curl -fs -o /dev/null -X POST "http://localhost:8002/api/v1/lead/owner-requests" \
    -H 'Content-Type: application/json' -d '{"kind":"rent","full_name":"Anna Bianchi","phone":"333 111 2222","municipality":"Chieti Scalo","property_type":"apartment","intention":"planning","message":"Bilocale vicino all università","consent":{"privacy_accepted":true,"privacy_policy_version":"2026-01"}}'

  info "Pannello di amministrazione…"
  [ -d "$ROOT/node_modules" ] || (cd "$ROOT" && npm install --no-audit --no-fund >>"$STATE/logs/npm.log" 2>&1)
  start_bg admin "$ROOT" env VITE_LOCAL_SERVICES=1 npm run dev --workspace @taraborrelli/admin
  wait_for "http://localhost:5173" "Pannello"

  cat <<MSG

  Pronto: http://localhost:5173

    Email:     $ADMIN_EMAIL
    Password:  $ADMIN_PASSWORD

  Log:   scripts/dev-local.sh logs
  Stop:  scripts/dev-local.sh down   (i dati di prova vengono eliminati)

MSG
}

case "${1:-up}" in
  up) up ;;
  down) down ;;
  logs) tail -f "$STATE"/logs/*.log ;;
  *) fail "Uso: scripts/dev-local.sh [up|down|logs]" ;;
esac
