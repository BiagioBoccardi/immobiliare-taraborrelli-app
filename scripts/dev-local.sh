#!/usr/bin/env bash
# Local trial environment for the admin panel, without docker compose.
#
#   scripts/dev-local.sh up     start everything: admin on :5173, mobile app (web) on :8081
#   scripts/dev-local.sh up --lan   same, reachable from a phone on the same Wi-Fi (Expo Go)
#   scripts/dev-local.sh up --tunnel   same, reachable from a phone on any network through a
#                                      Cloudflare tunnel; with "npx expo login" the app is
#                                      listed in Expo Go (needs cloudflared)
#   scripts/dev-local.sh down   stop everything (data is discarded)
#   scripts/dev-local.sh logs   follow the services' logs
#   scripts/dev-local.sh email  show the last email saved (e.g. a password reset code)
#
# What it starts: PostgreSQL in Docker (one database per service), the auth, lead and
# property services with uv, an in-memory S3 for photos (moto, run with uvx), the admin
# panel with Vite and the mobile app in the browser (Expo web). Events are disabled. Every
# start begins from empty data, with a test administrator, two sample owner requests and
# five fictional sample properties.
#
# Requirements: Docker, uv, Node.js 20+ and openssl (cloudflared for --tunnel). On Windows use WSL2.
# Ports: 5173 (admin), 8081 (app), 8001-8003 (services), 9100 (S3), 8090 (tunnel proxy),
# 55432 (PostgreSQL).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STATE="$ROOT/.dev"
# Optional local settings, never committed (e.g. SMTP to really send emails):
# copy scripts/dev-local.env.example to .dev-local.env and fill it in.
# Read as plain KEY=value lines (never executed), surrounding quotes removed.
if [ -f "$ROOT/.dev-local.env" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"
    case "$line" in ''|'#'*) continue ;; esac
    key="${line%%=*}"
    value="${line#*=}"
    value="${value#\"}"; value="${value%\"}"
    value="${value#\'}"; value="${value%\'}"
    case "$key" in
      SMTP_HOST|SMTP_PORT|SMTP_SSL|SMTP_USERNAME|SMTP_PASSWORD|EMAIL_FROM) export "$key=$value" ;;
    esac
  done <"$ROOT/.dev-local.env"
fi
DB_CONTAINER="taraborrelli-dev-db"
DB_PORT="${DEV_DB_PORT:-55432}"
S3_PORT="${DEV_S3_PORT:-9100}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@taraborrelli.test}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-Admin-di-prova-1}"
USER_EMAIL="${USER_EMAIL:-utente@taraborrelli.test}"
USER_PASSWORD="${USER_PASSWORD:-Utente-di-prova-1}"

# How other devices reach this computer: local (this computer only), lan or tunnel.
MODE=local
PUBLIC_HOST=localhost
LAN=false
PROXY_PORT="${DEV_PROXY_PORT:-8090}"
# Addresses the app uses for the API and the photos; they change with --lan and --tunnel.
API_BASE="http://localhost:5173"
MEDIA_BASE="http://localhost:$S3_PORT/property-media"
TUNNEL_URL="${TUNNEL_URL:-}"

# LAN address of this computer (on WSL2 it needs networkingMode=mirrored). LAN_HOST overrides it.
detect_lan_host() {
  if [ -n "${LAN_HOST:-}" ]; then echo "$LAN_HOST"; return; fi
  if command -v ip >/dev/null 2>&1; then
    ip route get 1.1.1.1 2>/dev/null | sed -n 's/.* src \([0-9.]*\).*/\1/p' | head -1
  else
    hostname -I 2>/dev/null | awk '{print $1}'
  fi
  return 0
}

info() { printf '\033[1;34m›\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; exit 1; }

require() {
  for tool in docker uv node npm openssl curl; do
    command -v "$tool" >/dev/null 2>&1 || fail "Manca '$tool': installalo e riprova."
  done
  docker info >/dev/null 2>&1 || fail "Docker non è in esecuzione."
}

wait_for() {
  local url=$1 name=$2 seconds=${3:-60}
  for _ in $(seq 1 "$seconds"); do
    curl -fs "$url" >/dev/null 2>&1 && return 0
    sleep 1
  done
  fail "$name non risponde: guarda $STATE/logs/"
}

# start_bg NAME DIR COMMAND...: runs COMMAND in DIR in the background, logging to .dev/logs.
start_bg() {
  local name=$1 dir=$2; shift 2
  (cd "$dir" && exec "$@") >>"$STATE/logs/$name.log" 2>&1 </dev/null &
  echo $! >>"$STATE/pids"
}

# Stops a process and all its descendants (npm, uv and uvx start child processes).
kill_tree() {
  local child
  for child in $(pgrep -P "$1" 2>/dev/null); do kill_tree "$child"; done
  kill "$1" 2>/dev/null || true
}

down() {
  if [ -f "$STATE/pids" ]; then
    while read -r pid; do kill_tree "$pid"; done <"$STATE/pids"
    rm -f "$STATE/pids"
  fi
  docker rm -f "$DB_CONTAINER" >/dev/null 2>&1 || true
  info "Ambiente di prova fermato."
}

# Starts the single entry point and a Cloudflare quick tunnel to it; sets TUNNEL_URL.
# A TUNNEL_URL given from outside is used as is (another tunnel already pointing at the proxy).
start_tunnel() {
  info "Collegamento pubblico per il telefono…"
  start_bg proxy "$ROOT" node scripts/dev-proxy.mjs "$PROXY_PORT" "$S3_PORT"
  if [ -n "$TUNNEL_URL" ]; then return; fi
  command -v cloudflared >/dev/null 2>&1 \
    || fail "Manca cloudflared: installalo (vedi istruzioni) e riprova."
  start_bg tunnel "$ROOT" cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:$PROXY_PORT"
  for _ in $(seq 1 60); do
    # Quick tunnels get a random address like https://word-word-word.trycloudflare.com.
    TUNNEL_URL=$(grep -oE 'https://[a-z0-9]+(-[a-z0-9]+)+\.trycloudflare\.com' "$STATE/logs/tunnel.log" 2>/dev/null | head -1 || true)
    [ -n "$TUNNEL_URL" ] && return
    grep -q "failed to request quick Tunnel" "$STATE/logs/tunnel.log" 2>/dev/null \
      && fail "Cloudflare non ha aperto il collegamento (controlla la connessione a Internet): $STATE/logs/tunnel.log"
    sleep 1
  done
  fail "Il collegamento pubblico non è partito: guarda $STATE/logs/tunnel.log"
}

up() {
  require
  if [ "${1:-}" = "--tunnel" ]; then
    MODE=tunnel
  elif [ "${1:-}" = "--lan" ]; then
    MODE=lan
    LAN=true
    PUBLIC_HOST="$(detect_lan_host)"
    [ -n "$PUBLIC_HOST" ] || fail "Indirizzo di rete non trovato: avvia con LAN_HOST=<ip del PC> scripts/dev-local.sh up --lan"
    case "$PUBLIC_HOST" in
      172.*) info "Attenzione: $PUBLIC_HOST sembra l'indirizzo interno di WSL, il telefono non lo raggiunge. Attiva networkingMode=mirrored oppure indica LAN_HOST." ;;
    esac
    API_BASE="http://$PUBLIC_HOST:5173"
    MEDIA_BASE="http://$PUBLIC_HOST:$S3_PORT/property-media"
  fi
  [ -f "$STATE/pids" ] && down
  mkdir -p "$STATE/logs"
  rm -rf "$STATE/outbox"  # every start begins from empty data, emails included
  : >"$STATE/logs/tunnel.log"
  if [ "$MODE" = tunnel ]; then
    start_tunnel
    API_BASE="$TUNNEL_URL"
    MEDIA_BASE="$TUNNEL_URL/property-media"
  fi

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
  # With --lan the phone loads the photos directly from here.
  local s3_bind=127.0.0.1
  $LAN && s3_bind=0.0.0.0
  start_bg s3 "$STATE" uvx --quiet --from "moto[server]" moto_server -H "$s3_bind" -p "$S3_PORT"
  wait_for "http://localhost:$S3_PORT" "S3"

  export EVENTS_ENABLED=false LOG_LEVEL=INFO
  local email_backend=outbox  # emails saved in .dev/outbox
  [ -n "${SMTP_HOST:-}" ] && email_backend=smtp  # really sent (.dev-local.env)
  local port=8001
  for service in auth lead property; do
    info "Servizio $service (porta $port)…"
    local db_url="postgresql+asyncpg://dev:dev@localhost:$DB_PORT/$service"
    (cd "$ROOT/services/$service" && DATABASE_URL="$db_url" uv run --quiet alembic upgrade head) \
      >>"$STATE/logs/$service.log" 2>&1 || fail "Migrazioni di $service fallite: $STATE/logs/$service.log"
    if [ "$service" = auth ]; then
      start_bg "$service" "$ROOT/services/$service" env DATABASE_URL="$db_url" \
        JWT_PRIVATE_KEY="$(cat "$STATE/jwt-private.pem")" \
        EMAIL_BACKEND="$email_backend" EMAIL_OUTBOX_DIR="$STATE/outbox" \
        uv run --quiet uvicorn app.main:app --port "$port"
    else
      start_bg "$service" "$ROOT/services/$service" env DATABASE_URL="$db_url" \
        JWT_PUBLIC_KEY="$(cat "$STATE/jwt-public.pem")" \
        S3_ENDPOINT_URL="http://localhost:$S3_PORT" S3_ACCESS_KEY=dev S3_SECRET_KEY=dev \
        S3_CREATE_BUCKET=true MEDIA_PUBLIC_BASE_URL="$MEDIA_BASE" \
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

  info "Utente dell'app di prova…"
  user_token=$(curl -fs -X POST "http://localhost:8001/api/v1/auth/register" \
    -H 'Content-Type: application/json' \
    -d '{"full_name":"Giulia Utente","email":"'"$USER_EMAIL"'","password":"'"$USER_PASSWORD"'","source":"app","consent":{"privacy_accepted":true,"privacy_policy_version":"2026-01","marketing_accepted":false}}' \
    | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p') \
    || fail "Creazione utente di prova fallita"
  # A request linked to the account, visible in the app's Profilo.
  curl -fs -o /dev/null -X POST "http://localhost:8002/api/v1/lead/owner-requests" \
    -H 'Content-Type: application/json' -H "Authorization: Bearer $user_token" \
    -d '{"kind":"sell","full_name":"Giulia Utente","phone":"333 222 3333","municipality":"Chieti","property_type":"house","intention":"know_value","consent":{"privacy_accepted":true,"privacy_policy_version":"2026-01"}}'

  info "Richieste di esempio dai moduli pubblici…"
  curl -fs -o /dev/null -X POST "http://localhost:8002/api/v1/lead/valuations" \
    -H 'Content-Type: application/json' -d '{"full_name":"Mario Rossi","phone":"333 000 0000","municipality":"Chieti","property_type":"apartment","surface_sqm":95,"rooms":4,"condition":"good","intention":"decided","consent":{"privacy_accepted":true,"privacy_policy_version":"2026-01","marketing_accepted":true}}'
  curl -fs -o /dev/null -X POST "http://localhost:8002/api/v1/lead/owner-requests" \
    -H 'Content-Type: application/json' -d '{"kind":"rent","full_name":"Anna Bianchi","phone":"333 111 2222","municipality":"Chieti Scalo","property_type":"apartment","intention":"planning","message":"Bilocale vicino all università","consent":{"privacy_accepted":true,"privacy_policy_version":"2026-01"}}'

  info "Pannello di amministrazione…"
  # Install exactly what package-lock.json lists, only when it changed (e.g. after a git pull).
  # npm ci never rewrites the lockfile, so git pull is never blocked by local changes.
  if [ ! -f "$ROOT/node_modules/.package-lock.json" ] \
    || [ "$ROOT/package-lock.json" -nt "$ROOT/node_modules/.package-lock.json" ]; then
    info "Installazione dei pacchetti npm (qualche minuto)…"
    (cd "$ROOT" && npm ci --no-audit --no-fund >>"$STATE/logs/npm.log" 2>&1) \
      || fail "Installazione dei pacchetti npm fallita: $STATE/logs/npm.log"
  fi
  # With --lan, Vite also answers the phone and lets the app call the API from another origin.
  start_bg admin "$ROOT" env VITE_LOCAL_SERVICES=1 VITE_DEV_LAN="$LAN" \
    npm run dev --workspace @taraborrelli/admin
  wait_for "http://localhost:5173" "Pannello"

  info "Immobili di esempio…"
  node "$ROOT/scripts/demo/seed.mjs" "http://localhost:5173" "$ADMIN_EMAIL" "$ADMIN_PASSWORD" \
    >>"$STATE/logs/seed.log" 2>&1 || fail "Creazione immobili di esempio fallita: $STATE/logs/seed.log"

  info "App mobile nel browser (porta 8081)…"
  if [ "$MODE" = tunnel ]; then
    # Not offline and not CI, so Expo lists the app in Expo Go for the logged-in account;
    # the proxy URL makes Expo Go load everything through the tunnel.
    (cd "$ROOT/apps/mobile" && timeout 30 npx expo whoami >/dev/null 2>&1) \
      || info "Non hai fatto l'accesso a Expo: l'app non comparirà da sola in Expo Go (vedi istruzioni)."
    start_bg mobile "$ROOT/apps/mobile" env EXPO_NO_TELEMETRY=1 \
      EXPO_PACKAGER_PROXY_URL="$TUNNEL_URL" EXPO_PUBLIC_API_BASE_URL="$API_BASE" \
      npx expo start --web --port 8081
  else
    start_bg mobile "$ROOT/apps/mobile" env CI=1 EXPO_OFFLINE=1 \
      REACT_NATIVE_PACKAGER_HOSTNAME="$PUBLIC_HOST" \
      EXPO_PUBLIC_API_BASE_URL="$API_BASE" npx expo start --web --port 8081
  fi
  wait_for "http://localhost:8081" "App mobile" 180

  cat <<MSG

  Pronto!

    Pannello admin:  http://localhost:5173
      Email:         $ADMIN_EMAIL
      Password:      $ADMIN_PASSWORD

    App (anteprima nel browser):  http://localhost:8081
      Email:         $USER_EMAIL
      Password:      $USER_PASSWORD
      La prima apertura può richiedere un minuto mentre l'app viene preparata.

MSG
  if $LAN; then
    cat <<MSG
    Sul telefono (stessa rete Wi-Fi del PC):
      App nativa:    apri Expo Go, oppure scrivi in Safari  exp://$PUBLIC_HOST:8081
      Nel browser:   http://$PUBLIC_HOST:8081

MSG
  fi
  if [ "$MODE" = tunnel ]; then
    local expo_url="${TUNNEL_URL/https:/exps:}"
    expo_url="${expo_url/http:/exp:}"
    cat <<MSG
    Sul telefono (qualsiasi rete):
      Nel browser (Safari o Chrome):  $TUNNEL_URL
      App nativa: apri Expo Go, l'app compare in "Development servers" (stesso account
      Expo del PC); se non compare, scrivi in Safari:  $expo_url

MSG
  fi
  if [ -n "${SMTP_HOST:-}" ]; then
    cat <<MSG
  Email (es. codici "password dimenticata"): spedite davvero tramite $SMTP_HOST
MSG
  else
    cat <<MSG
  Email di prova (es. codici "password dimenticata"): non vengono spedite ma salvate in
    $STATE/outbox    (leggile con: scripts/dev-local.sh email)
MSG
  fi
  cat <<MSG

  Log:   scripts/dev-local.sh logs
  Stop:  scripts/dev-local.sh down   (i dati di prova vengono eliminati)

MSG
}

case "${1:-up}" in
  up) up "${2:-}" ;;
  down) down ;;
  logs) tail -f "$STATE"/logs/*.log ;;
  email)
    # Shows the most recent email saved by the auth service (local trial only).
    latest=$(ls -t "$STATE"/outbox/*.eml 2>/dev/null | head -1 || true)
    [ -n "$latest" ] || fail "Nessuna email salvata finora."
    python3 -c 'import sys, email; m = email.message_from_binary_file(open(sys.argv[1], "rb")); print("A:", m["To"]); print("Oggetto:", m["Subject"]); print(); print(m.get_payload(decode=True).decode())' "$latest"
    ;;
  *) fail "Uso: scripts/dev-local.sh [up|down|logs|email]" ;;
esac
