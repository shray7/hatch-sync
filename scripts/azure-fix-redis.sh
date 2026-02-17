#!/usr/bin/env bash
#
# Fix Redis for hatch-sync-api: ensure the Redis Container App is running and the API
# has the redis-url secret so /health shows "redis": "ok".
#
# Option A - Restore Redis URL and other secrets (recommended):
#   HATCH_EMAIL=your@email.com HATCH_PASSWORD=secret GOOGLE_CALENDAR_SHARE_EMAIL=you@gmail.com \
#     ./scripts/azure-fix-redis.sh
#   This runs azure-set-secrets.sh (which now includes redis-url).
#
# Option B - Only ensure Redis app is running (if redis-url was already set):
#   ./scripts/azure-fix-redis.sh --check-only
#
set -euo pipefail

RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-hatchsync}"
REDIS_APP_NAME="${AZURE_REDIS_APP_NAME:-hatch-sync-redis}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CHECK_ONLY=false
for arg in "$@"; do
  if [ "$arg" = "--check-only" ]; then
    CHECK_ONLY=true
    break
  fi
done

echo "=== Redis Container App: $REDIS_APP_NAME ==="
REPLICAS=$(az containerapp show \
  --name "$REDIS_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query "properties.template.scale.minReplicas" -o tsv 2>/dev/null || echo "0")
if [ "${REPLICAS:-0}" = "0" ]; then
  echo "Scaling Redis app to 1 replica..."
  az containerapp update \
    --name "$REDIS_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --min-replicas 1 \
    --max-replicas 1
  echo "Scaled. Wait ~30s for the replica to be ready."
else
  echo "Redis app has min replicas: $REPLICAS"
fi

if [ "$CHECK_ONLY" = true ]; then
  echo "Done (check-only). To restore redis-url on the API app, run:"
  echo "  HATCH_EMAIL=... HATCH_PASSWORD=... GOOGLE_CALENDAR_SHARE_EMAIL=... $SCRIPT_DIR/azure-set-secrets.sh"
  exit 0
fi

if [ -z "${HATCH_EMAIL:-}" ] || [ -z "${HATCH_PASSWORD:-}" ] || [ -z "${GOOGLE_CALENDAR_SHARE_EMAIL:-}" ]; then
  echo ""
  echo "To restore the API's Redis URL (secret redis-url), re-run set-secrets with your env vars:"
  echo "  HATCH_EMAIL=your@email.com HATCH_PASSWORD=secret GOOGLE_CALENDAR_SHARE_EMAIL=you@gmail.com $SCRIPT_DIR/azure-set-secrets.sh"
  echo "Set-secrets now includes redis-url so the API can connect to Redis."
  exit 0
fi

echo ""
echo "Restoring all secrets on the API app (including redis-url)..."
exec "$SCRIPT_DIR/azure-set-secrets.sh"
