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

if [ ${#missing[@]} -gt 0 ]; then
  echo "Missing required environment variables: ${missing[*]}"
  echo "Example: HATCH_EMAIL=you@email.com HATCH_PASSWORD=secret GOOGLE_CALENDAR_SHARE_EMAIL=you@gmail.com $0"
  exit 1
fi

# Optional: Azure Blob for photo storage (if unset, use placeholder so secret set succeeds; replace later in portal)
AZURE_BLOB_CONNECTION_STRING="${AZURE_BLOB_CONNECTION_STRING:-DefaultEndpointsProtocol=https;AccountName=placeholder;AccountKey=placeholder;EndpointSuffix=core.windows.net}"
AZURE_BLOB_CONTAINER="${AZURE_BLOB_CONTAINER:-hatch-photos}"

echo "Getting Redis URL from Container Apps environment..."
ENV_DEFAULT_DOMAIN=$(az containerapp env show \
  --name "$ACA_ENV_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query properties.defaultDomain -o tsv)
REDIS_URL="redis://${REDIS_APP_NAME}.internal.${ENV_DEFAULT_DOMAIN}:6379/0"
echo "Redis URL: $REDIS_URL"

# Build secrets list (required + optional DATABASE_URL + optional Google OAuth)
SECRETS_ARR=(
  "redis-url=$REDIS_URL"
  "hatch-email=$HATCH_EMAIL"
  "hatch-password=$HATCH_PASSWORD"
  "google-calendar-share-email=$GOOGLE_CALENDAR_SHARE_EMAIL"
  "azure-blob-connection-string=$AZURE_BLOB_CONNECTION_STRING"
)
if [ -n "${DATABASE_URL:-}" ]; then
  SECRETS_ARR+=("database-url=$DATABASE_URL")
  echo "Including DATABASE_URL in secrets (Grow data stored in PostgreSQL)."
fi
if [ -n "${GOOGLE_CLIENT_ID:-}" ]; then
  SECRETS_ARR+=("google-client-id=$GOOGLE_CLIENT_ID")
fi
if [ -n "${GOOGLE_CLIENT_SECRET:-}" ]; then
  SECRETS_ARR+=("google-client-secret=$GOOGLE_CLIENT_SECRET")
fi
if [ -n "${ADMIN_ALLOWLIST_EMAILS:-}" ]; then
  SECRETS_ARR+=("admin-allowlist-emails=$ADMIN_ALLOWLIST_EMAILS")
fi
if [ -n "${SESSION_SECRET:-}" ]; then
  SECRETS_ARR+=("session-secret=$SESSION_SECRET")
fi

echo "Setting secrets on Container App '$APP_NAME' in resource group '$RESOURCE_GROUP'..."
az containerapp secret set \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --secrets "${SECRETS_ARR[@]}"

# Optional: timezone for calendar event times (e.g. America/Los_Angeles)
# Optional: minutes between cache refresh jobs (default 15)
echo "Linking secrets to environment variables (keeping existing REDIS_URL, etc.)..."
env_vars=(
  "REDIS_URL=secretref:redis-url"
  "HATCH_CACHE_TTL_SECONDS=900"
  "HATCH_CACHE_REFRESH_MINUTES=${HATCH_CACHE_REFRESH_MINUTES:-15}"
  "AZURE_BLOB_CONNECTION_STRING=secretref:azure-blob-connection-string"
  "AZURE_BLOB_CONTAINER=$AZURE_BLOB_CONTAINER"
  "GOOGLE_SERVICE_ACCOUNT_FILE=/app/service_account.json"
  "HATCH_EMAIL=secretref:hatch-email"
  "HATCH_PASSWORD=secretref:hatch-password"
  "GOOGLE_CALENDAR_SHARE_EMAIL=secretref:google-calendar-share-email"
)
if [ -n "${DATABASE_URL:-}" ]; then
  env_vars+=("DATABASE_URL=secretref:database-url")
fi

if [ -n "${HATCH_TIMEZONE:-}" ]; then
  env_vars+=("HATCH_TIMEZONE=$HATCH_TIMEZONE")
elif [ -n "${DATABASE_URL:-}" ]; then
  env_vars+=("HATCH_TIMEZONE=America/Los_Angeles")
fi

if [ -n "${HATCH_CACHE_REFRESH_MINUTES:-}" ]; then
  env_vars+=("HATCH_CACHE_REFRESH_MINUTES=$HATCH_CACHE_REFRESH_MINUTES")
fi

if [ -n "${GOOGLE_CLIENT_ID:-}" ]; then
  env_vars+=("GOOGLE_CLIENT_ID=secretref:google-client-id")
fi
if [ -n "${GOOGLE_CLIENT_SECRET:-}" ]; then
  env_vars+=("GOOGLE_CLIENT_SECRET=secretref:google-client-secret")
fi
if [ -n "${ADMIN_ALLOWLIST_EMAILS:-}" ]; then
  env_vars+=("ADMIN_ALLOWLIST_EMAILS=secretref:admin-allowlist-emails")
fi
if [ -n "${SESSION_SECRET:-}" ]; then
  env_vars+=("SESSION_SECRET=secretref:session-secret")
fi
if [ -n "${API_BASE_URL:-}" ]; then
  env_vars+=("API_BASE_URL=$API_BASE_URL")
fi
if [ -n "${FRONTEND_URL:-}" ]; then
  env_vars+=("FRONTEND_URL=$FRONTEND_URL")
fi

az containerapp update \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --set-env-vars "${env_vars[@]}"

echo "Done. Restart or redeploy the app for new revisions to pick up the secrets."
