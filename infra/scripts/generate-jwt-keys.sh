#!/usr/bin/env sh
# Generates an RSA key pair for local development and appends it to the root .env file.
# The auth service signs tokens with JWT_PRIVATE_KEY; every other service verifies them
# with JWT_PUBLIC_KEY. Never commit the generated .env.
set -eu

ENV_FILE="${1:-.env}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

if grep -q '^JWT_PRIVATE_KEY=.\+' "$ENV_FILE" 2>/dev/null; then
  echo "JWT keys already present in $ENV_FILE, nothing to do." >&2
  exit 0
fi

openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "$TMP_DIR/private.pem" 2>/dev/null
openssl pkey -in "$TMP_DIR/private.pem" -pubout -out "$TMP_DIR/public.pem"

# Drop empty placeholders copied from .env.example before appending the real keys.
if [ -f "$ENV_FILE" ]; then
  sed -i.bak '/^JWT_PRIVATE_KEY=$/d; /^JWT_PUBLIC_KEY=$/d' "$ENV_FILE" && rm -f "$ENV_FILE.bak"
fi

{
  printf 'JWT_PRIVATE_KEY="%s"\n' "$(cat "$TMP_DIR/private.pem")"
  printf 'JWT_PUBLIC_KEY="%s"\n' "$(cat "$TMP_DIR/public.pem")"
} >> "$ENV_FILE"

echo "JWT keys written to $ENV_FILE"
