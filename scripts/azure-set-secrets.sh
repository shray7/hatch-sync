#!/usr/bin/env bash
#
# Set Hatch, Google Calendar, and Redis secrets on the hatch-sync-api Container App.
# Reads values from environment variables so you don't put secrets in the shell history.
# Redis URL is computed from the Container Apps environment (internal hostname).
#
# Prerequisites: Azure CLI installed and logged in (az login).
# Usage:
#   HATCH_EMAIL=your@email.com HATCH_PASSWORD=secret GOOGLE_CALENDAR_SHARE_EMAIL=you@gmail.com \
#     ./scripts/azure-set-secrets.sh

set -euo pipefail

RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-hatchsync}"
APP_NAME="${AZURE_CONTAINERAPP_NAME:-hatch-sync-api}"
ACA_ENV_NAME="${AZURE_CONTAINERAPPS_ENV:-hatchsync-env}"
REDIS_APP_NAME="${AZURE_REDIS_APP_NAME:-hatch-sync-redis}"

missing=()
[ -z "${HATCH_EMAIL:-}" ] && missing+=(HATCH_EMAIL)
[ -z "${HATCH_PASSWORD:-}" ] && missing+=(HATCH_PASSWORD)
[ -z "${GOOGLE_CALENDAR_SHARE_EMAIL:-}" ] && missing+=(GOOGLE_CALENDAR_SHARE_EMAIL)
[ -z "${AZURE_BLOB_CONNECTION_STRING:-}" ] && missing+=(AZURE_BLOB_CONNECTION_STRING)
[ -z "${AZURE_BLOB_CONTAINER:-}" ] && missing+=(AZURE_BLOB_CONTAINER)

if [ ${#missing[@]} -gt 0 ]; then
  echo "Missing required environment variables: ${missing[*]}"
  echo "Example: HATCH_EMAIL=you@email.com HATCH_PASSWORD=secret GOOGLE_CALENDAR_SHARE_EMAIL=you@gmail.com $0"
  exit 1
fi

echo "Getting Redis URL from Container Apps environment..."
ENV_DEFAULT_DOMAIN=$(az containerapp env show \
  --name "$ACA_ENV_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query properties.defaultDomain -o tsv)
REDIS_URL="redis://${REDIS_APP_NAME}.internal.${ENV_DEFAULT_DOMAIN}:6379/0"
echo "Redis URL: $REDIS_URL"

echo "Setting secrets on Container App '$APP_NAME' in resource group '$RESOURCE_GROUP'..."

az containerapp secret set \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --secrets \
    redis-url="$REDIS_URL" \
    hatch-email="$HATCH_EMAIL" \
    hatch-password="$HATCH_PASSWORD" \
    google-calendar-share-email="$GOOGLE_CALENDAR_SHARE_EMAIL" \
    azure-blob-connection-string="$AZURE_BLOB_CONNECTION_STRING"

# Optional: timezone for calendar event times (e.g. America/Los_Angeles)
# Optional: minutes between cache refresh jobs (default 15)
EXTRA_ENV=""
[ -n "${HATCH_TIMEZONE:-}" ] && EXTRA_ENV="${EXTRA_ENV} \"HATCH_TIMEZONE=$HATCH_TIMEZONE\""
[ -n "${HATCH_CACHE_REFRESH_MINUTES:-}" ] && EXTRA_ENV="${EXTRA_ENV} \"HATCH_CACHE_REFRESH_MINUTES=$HATCH_CACHE_REFRESH_MINUTES\""

echo "Linking secrets to environment variables (keeping existing REDIS_URL, etc.)..."
az containerapp update \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --set-env-vars \
    "REDIS_URL=secretref:redis-url" \
    "HATCH_CACHE_TTL_SECONDS=900" \
    "HATCH_CACHE_REFRESH_MINUTES=${HATCH_CACHE_REFRESH_MINUTES:-15}" \
    "AZURE_BLOB_CONNECTION_STRING=secretref:azure-blob-connection-string" \
    "AZURE_BLOB_CONTAINER=$AZURE_BLOB_CONTAINER" \
    "GOOGLE_SERVICE_ACCOUNT_FILE=/app/service_account.json" \
    "HATCH_EMAIL=secretref:hatch-email" \
    "HATCH_PASSWORD=secretref:hatch-password" \
    "GOOGLE_CALENDAR_SHARE_EMAIL=secretref:google-calendar-share-email"${EXTRA_ENV}

echo "Done. Restart or redeploy the app for new revisions to pick up the secrets."
