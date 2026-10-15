#!/bin/sh
set -eu
umask 077
: "${GBRAIN_DATABASE_URL:?missing database connection}"
: "${GBRAIN_DB_CA_BASE64:?missing database trust certificate}"
: "${GBRAIN_ADMIN_BOOTSTRAP_TOKEN:?missing owner credential}"
export GBRAIN_HOME="${GBRAIN_HOME:-/data}"
mkdir -p "$GBRAIN_HOME/.gbrain" /tmp/gbrain
printf '%s' "$GBRAIN_DB_CA_BASE64" | base64 --decode > /tmp/gbrain/database-ca.pem
export NODE_EXTRA_CA_CERTS=/tmp/gbrain/database-ca.pem
if [ ! -f "$GBRAIN_HOME/.gbrain/config.json" ]; then
  gbrain init --non-interactive --no-embedding --content-root "$GBRAIN_HOME/brain" --search-mode conservative
else
  gbrain apply-migrations --force-schema --yes --require-db
fi
gbrain config set self_upgrade.mode off
gbrain config set memory.auto_writeback off
public_url="${GBRAIN_PUBLIC_URL:-https://${RAILWAY_PUBLIC_DOMAIN:?missing public origin}}"
exec gbrain serve --http --bind 0.0.0.0 --port "${PORT:-3131}" \
  --public-url "$public_url" --surface full --suppress-bootstrap-token --fail-fast
