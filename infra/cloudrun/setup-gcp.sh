#!/usr/bin/env bash
# One-time preparation of Google Cloud for the deploy workflow (.github/workflows/deploy.yml).
#
# Run it in Google Cloud Shell (https://shell.cloud.google.com), from the repository root,
# after selecting the project: gcloud config set project <PROJECT_ID>
#
#   bash infra/cloudrun/setup-gcp.sh
#
# It is safe to run it again: what already exists is kept. It asks for the values that must
# stay secret (database addresses, storage and email passwords) and stores them in Secret
# Manager: they never end up in the repository or in GitHub. The JWT keys are generated here.
#
# What it creates:
#   - the APIs needed by Cloud Run, Artifact Registry and Secret Manager
#   - the Artifact Registry repository for the images, keeping only the last 2 versions
#   - "taraborrelli-run": the identity the services run with (reads the secrets)
#   - "taraborrelli-deploy": the identity GitHub Actions uses to deploy, reachable only from
#     this repository through Workload Identity Federation (no key files)
#   - the secrets, and a 1 EUR monthly budget alert on the billing account
set -euo pipefail

GITHUB_REPO="${GITHUB_REPO:-BiagioBoccardi/immobiliare-taraborrelli-app}"
REGION="${REGION:-europe-west1}"
REPOSITORY="taraborrelli"
POOL="github"
PROVIDER="github"
RUN_SA_NAME="taraborrelli-run"
DEPLOY_SA_NAME="taraborrelli-deploy"

info() { printf '\033[1;34m›\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; exit 1; }

PROJECT_ID="$(gcloud config get-value project 2>/dev/null)"
[ -n "$PROJECT_ID" ] || fail "Nessun progetto selezionato: gcloud config set project <PROJECT_ID>"
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
RUN_SA="$RUN_SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
DEPLOY_SA="$DEPLOY_SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
info "Progetto $PROJECT_ID ($PROJECT_NUMBER), regione $REGION, repository GitHub $GITHUB_REPO"

info "Attivazione delle API…"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com iamcredentials.googleapis.com sts.googleapis.com \
  cloudresourcemanager.googleapis.com billingbudgets.googleapis.com --quiet

info "Archivio delle immagini (Artifact Registry)…"
if ! gcloud artifacts repositories describe "$REPOSITORY" --location "$REGION" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$REPOSITORY" --repository-format docker \
    --location "$REGION" --description "Immagini dei servizi Taraborrelli" --quiet
fi
# Keeps the archive inside the free 0.5 GB: only the last 2 versions of each image.
policy="$(mktemp)"
cat >"$policy" <<'JSON'
[
  {"name": "keep-last-2", "action": {"type": "Keep"}, "mostRecentVersions": {"keepCount": 2}},
  {"name": "delete-older", "action": {"type": "Delete"}, "condition": {"tagState": "any"}}
]
JSON
gcloud artifacts repositories set-cleanup-policies "$REPOSITORY" --location "$REGION" \
  --policy "$policy" --no-dry-run --quiet >/dev/null
rm -f "$policy"

info "Identità dei servizi e della pubblicazione…"
for name in "$RUN_SA_NAME" "$DEPLOY_SA_NAME"; do
  gcloud iam service-accounts describe "$name@$PROJECT_ID.iam.gserviceaccount.com" >/dev/null 2>&1 \
    || gcloud iam service-accounts create "$name" --display-name "$name" --quiet
done
for role in roles/run.admin roles/artifactregistry.writer roles/secretmanager.secretAccessor; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" --member "serviceAccount:$DEPLOY_SA" \
    --role "$role" --condition None --quiet >/dev/null
done
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member "serviceAccount:$RUN_SA" \
  --role roles/secretmanager.secretAccessor --condition None --quiet >/dev/null
# The deploy identity may start services that run as the runtime identity.
gcloud iam service-accounts add-iam-policy-binding "$RUN_SA" \
  --member "serviceAccount:$DEPLOY_SA" --role roles/iam.serviceAccountUser --quiet >/dev/null

info "Accesso da GitHub Actions senza chiavi (Workload Identity Federation)…"
if ! gcloud iam workload-identity-pools describe "$POOL" --location global >/dev/null 2>&1; then
  gcloud iam workload-identity-pools create "$POOL" --location global \
    --display-name "GitHub Actions" --quiet
fi
if ! gcloud iam workload-identity-pools providers describe "$PROVIDER" --location global \
  --workload-identity-pool "$POOL" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER" --location global \
    --workload-identity-pool "$POOL" --display-name "GitHub" \
    --issuer-uri "https://token.actions.githubusercontent.com" \
    --attribute-mapping "google.subject=assertion.sub,attribute.repository=assertion.repository" \
    --attribute-condition "assertion.repository == '$GITHUB_REPO'" --quiet
fi
gcloud iam service-accounts add-iam-policy-binding "$DEPLOY_SA" \
  --role roles/iam.workloadIdentityUser \
  --member "principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$POOL/attribute.repository/$GITHUB_REPO" \
  --quiet >/dev/null
WIF_PROVIDER="projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$POOL/providers/$PROVIDER"

# put_secret NAME VALUE: creates the secret if needed and stores VALUE as its latest version.
put_secret() {
  gcloud secrets describe "$1" >/dev/null 2>&1 \
    || gcloud secrets create "$1" --replication-policy automatic --quiet >/dev/null
  printf '%s' "$2" | gcloud secrets versions add "$1" --data-file - --quiet >/dev/null
  # Old versions cost money once there are more than 6: keep only the latest one enabled.
  for old in $(gcloud secrets versions list "$1" --filter 'state=ENABLED' \
    --sort-by '~createTime' --format 'value(name)' | tail -n +2); do
    gcloud secrets versions destroy "$old" --secret "$1" --quiet >/dev/null
  done
}

# ask_secret NAME PROMPT: asks for a value without showing it; Enter keeps the stored one.
ask_secret() {
  local value
  if gcloud secrets versions access latest --secret "$1" >/dev/null 2>&1; then
    read -r -s -p "$2 (Invio per lasciare quello salvato): " value; echo
    [ -z "$value" ] && return 0
  else
    read -r -s -p "$2: " value; echo
    [ -n "$value" ] || fail "Valore obbligatorio."
  fi
  put_secret "$1" "$value"
}

info "Database (Neon)…"
# Neon gives addresses like postgresql://user:password@ep-xxx-pooler.region.aws.neon.tech/
# neondb?sslmode=require&channel_binding=require. The services need the direct (non-pooled)
# host, the asyncpg driver and ?ssl=require; each one has its own database.
if gcloud secrets versions access latest --secret auth-database-url >/dev/null 2>&1; then
  read -r -s -p "Indirizzo di connessione di Neon (Invio per lasciare quelli salvati): " neon; echo
else
  read -r -s -p "Indirizzo di connessione di Neon (inizia con postgresql://): " neon; echo
  [ -n "$neon" ] || fail "Valore obbligatorio."
fi
if [ -n "${neon:-}" ]; then
  base="$(printf '%s' "$neon" | sed -E 's#^postgres(ql)?(\+[a-z]+)?://#postgresql+asyncpg://#; s#\?.*$##; s#-pooler\.#.#; s#/[^/]*$##')"
  case "$base" in postgresql+asyncpg://*@*) ;; *) fail "Indirizzo di Neon non riconosciuto." ;; esac
  if command -v psql >/dev/null 2>&1; then
    admin_url="$(printf '%s' "$base" | sed 's#postgresql+asyncpg://#postgresql://#')/neondb?sslmode=require"
    for db in auth lead property; do
      psql "$admin_url" -tAc "SELECT 1 FROM pg_database WHERE datname = '$db'" | grep -q 1 \
        || psql "$admin_url" -qc "CREATE DATABASE $db"
    done
  else
    info "psql non disponibile: crea a mano su Neon i database auth, lead e property."
  fi
  for db in auth lead property; do
    put_secret "$db-database-url" "$base/$db?ssl=require"
  done
fi

info "Chiavi per i token di accesso (JWT)…"
if ! gcloud secrets versions access latest --secret jwt-private-key >/dev/null 2>&1; then
  keydir="$(mktemp -d)"
  openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "$keydir/private.pem" 2>/dev/null
  openssl pkey -in "$keydir/private.pem" -pubout -out "$keydir/public.pem"
  put_secret jwt-private-key "$(cat "$keydir/private.pem")"
  put_secret jwt-public-key "$(cat "$keydir/public.pem")"
  rm -rf "$keydir"
fi

info "Archivio foto (Cloudflare R2)…"
ask_secret s3-access-key "Access Key ID del token R2"
ask_secret s3-secret-key "Secret Access Key del token R2"

info "Email (avvisi all'agenzia e codici «password dimenticata»)…"
ask_secret smtp-password "Password per le app dell'account email che invia"

info "Avviso di spesa (1 EUR al mese)…"
billing="$(gcloud billing projects describe "$PROJECT_ID" --format 'value(billingAccountName)' | sed 's#billingAccounts/##')"
if [ -n "$billing" ]; then
  if ! gcloud billing budgets list --billing-account "$billing" --format 'value(displayName)' \
    | grep -qx "Taraborrelli"; then
    gcloud billing budgets create --billing-account "$billing" --display-name "Taraborrelli" \
      --budget-amount 1 --threshold-rule percent=0.5 --threshold-rule percent=1.0 --quiet \
      >/dev/null || info "Avviso di spesa non creato: aggiungilo da Fatturazione → Budget e avvisi."
  fi
else
  info "Nessun account di fatturazione collegato: collegalo, poi rilancia lo script."
fi

cat <<MSG

  Fatto. Nel file infra/cloudrun/config.env del repository scrivi questi valori:

    GCP_PROJECT_ID=$PROJECT_ID
    GCP_REGION=$REGION
    GCP_WIF_PROVIDER=$WIF_PROVIDER
    GCP_DEPLOY_SA=$DEPLOY_SA
    GCP_RUN_SA=$RUN_SA

  Poi su GitHub: Actions → Deploy → Run workflow.

MSG
