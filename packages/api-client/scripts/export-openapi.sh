#!/usr/bin/env sh
# Exports the OpenAPI document of every backend service into packages/api-client/openapi/.
# Requires uv. Run from anywhere: the script resolves the repository root itself.
set -eu

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
OUT="$ROOT/packages/api-client/openapi"

for service in auth lead property; do
  (
    cd "$ROOT/services/$service"
    uv run --quiet python -c "import json, sys; from app.main import create_app; json.dump(create_app().openapi(), sys.stdout, indent=2, sort_keys=True)"
  ) > "$OUT/$service.json"
  echo "openapi/$service.json"
done
