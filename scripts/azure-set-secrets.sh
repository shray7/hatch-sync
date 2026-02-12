#!/usr/bin/env bash
#
# Set Hatch and Google Calendar secrets on the hatch-sync-api Container App.
# Reads values from environment variables so you don't put secrets in the shell history.
#
# Prerequisites: Azure CLI installed and logged in (az login).
# Usage:
#   HATCH_EMAIL=your@email.com HATCH_PASSWORD=secret GOOGLE_CALENDAR_SHARE_EMAIL=you@gmail.com \
#     ./scripts/azure-set-secrets.sh

set -euo pipefail

RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-hatchsync}"
APP_NAME="${AZURE_CONTAINERAPP_NAME:-hatch-sync-api}"

missing=()
[ -z "${HATCH_EMAIL:-}" ] && missing+=(HATCH_EMAIL)
[ -z "${HATCH_PASSWORD:-}" ] && missing+=(HATCH_PASSWORD)
[ -z "${GOOGLE_CALENDAR_SHARE_EMAIL:-}" ] && missing+=(GOOGLE_CALENDAR_SHARE_EMAIL)

if [ ${#missing[@]} -gt 0 ]; then
  echo "Missing required environment variables: ${missing[*]}"
  echo "Example: HATCH_EMAIL=you@email.com HATCH_PASSWORD=secret GOOGLE_CALENDAR_SHARE_EMAIL=you@gmail.com $0"
  exit 1
fi

echo "Setting secrets on Container App '$APP_NAME' in resource group '$RESOURCE_GROUP'..."

az containerapp secret set \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --secrets \
    hatch-email="$HATCH_EMAIL" \
    hatch-password="$HATCH_PASSWORD" \
    google-calendar-share-email="$GOOGLE_CALENDAR_SHARE_EMAIL"

echo "Linking secrets to environment variables (keeping existing REDIS_URL, etc.)..."
az containerapp update \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --set-env-vars \
    "REDIS_URL=secretref:redis-url" \
    "HATCH_CACHE_TTL_SECONDS=900" \
    "GOOGLE_SERVICE_ACCOUNT_FILE=/app/service_account.json" \
    "HATCH_EMAIL=secretref:hatch-email" \
    "HATCH_PASSWORD=secretref:hatch-password" \
    "GOOGLE_CALENDAR_SHARE_EMAIL=secretref:google-calendar-share-email"

echo "Done. Restart or redeploy the app for new revisions to pick up the secrets."
