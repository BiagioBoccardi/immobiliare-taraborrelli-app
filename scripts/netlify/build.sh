#!/usr/bin/env sh
# Netlify build for the two sites made from this repository (see netlify.toml):
#   - the admin panel (default);
#   - the web version of the app, when the site sets NETLIFY_APP=mobile.
# The result always goes to netlify-dist, with the rules that proxy /api to Render.
set -eu

TARGET="${NETLIFY_APP:-admin}"
OUT="netlify-dist"

npm ci --no-audit --no-fund
rm -rf "$OUT"

case "$TARGET" in
  admin)
    npm run build --workspace @taraborrelli/admin
    cp -R apps/admin/dist "$OUT"
    ;;
  mobile)
    # The API is on the same site (proxied by Netlify), hence the empty base URL.
    (cd apps/mobile && EXPO_PUBLIC_API_BASE_URL="" EXPO_PUBLIC_WARM_UP_SERVICES=true \
      npx expo export --platform web --output-dir dist)
    cp -R apps/mobile/dist "$OUT"
    ;;
  *)
    echo "Unknown NETLIFY_APP: $TARGET (use admin or mobile)" >&2
    exit 1
    ;;
esac

sh scripts/netlify/api-redirects.sh "$OUT"
