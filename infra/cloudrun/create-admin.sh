#!/usr/bin/env bash
# Creates the first administrator of the admin panel, after the first deploy.
# Run it in Google Cloud Shell; the password is typed in the terminal and never stored.
#
#   bash infra/cloudrun/create-admin.sh admin@example.com "Nome Cognome"
set -euo pipefail

[ $# -eq 2 ] || { echo "Uso: bash infra/cloudrun/create-admin.sh <email> \"Nome Cognome\"" >&2; exit 2; }
REGION="${REGION:-europe-west1}"

image="$(gcloud run services describe taraborrelli-auth --region "$REGION" \
  --format 'value(spec.template.spec.containers[0].image)')"
[ -n "$image" ] || { echo "Il servizio auth non è ancora pubblicato: lancia prima il Deploy." >&2; exit 1; }
gcloud auth configure-docker "$REGION-docker.pkg.dev" --quiet >/dev/null 2>&1

docker run -it --rm \
  -e DATABASE_URL="$(gcloud secrets versions access latest --secret auth-database-url)" \
  "$image" python -m app.cli create-admin --email "$1" --name "$2"
