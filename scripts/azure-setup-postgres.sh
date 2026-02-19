#!/usr/bin/env bash
#
# One-time setup: Create Azure Database for PostgreSQL Flexible Server for hatch-sync.
# Creates server, database, firewall rule (allow Azure + public for Container Apps).
# Schema is initialized when the API app first starts (migrations run on startup).
#
# Prerequisites: Azure CLI installed and logged in (az login).
# Usage: ./scripts/azure-setup-postgres.sh [location]
#   location defaults to westus2.
#
# Optional: POSTGRES_ADMIN_PASSWORD=... (if unset, you will be prompted or use generate).
# Output: DATABASE_URL to use with azure-set-secrets.sh or Container App env.

set -euo pipefail

SUBSCRIPTION_NAME="${AZURE_SUBSCRIPTION:-TaskAgent}"
RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-hatchsync}"
LOCATION="${1:-westus2}"
# Server name must be globally unique; only lowercase letters, numbers, hyphen. 3-63 chars.
PG_SERVER_NAME="${AZURE_PG_SERVER_NAME:-hatchsync-pg}"
PG_ADMIN_USER="${AZURE_PG_ADMIN_USER:-hatchsync}"
PG_DATABASE="${AZURE_PG_DATABASE:-hatch}"
# Flexible Server requires SSL; use sslmode=require in connection string.
PG_HOST_SUFFIX="postgres.database.azure.com"

echo "Using subscription: $SUBSCRIPTION_NAME"
az account set --subscription "$SUBSCRIPTION_NAME"

if [ -z "${POSTGRES_ADMIN_PASSWORD:-}" ]; then
  echo "POSTGRES_ADMIN_PASSWORD not set. Generating a random password (save it securely)."
  POSTGRES_ADMIN_PASSWORD=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 24)
  echo "Generated password (store this): $POSTGRES_ADMIN_PASSWORD"
fi

echo "Creating PostgreSQL Flexible Server: $PG_SERVER_NAME in $RESOURCE_GROUP ($LOCATION)..."
az postgres flexible-server create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$PG_SERVER_NAME" \
  --location "$LOCATION" \
  --admin-user "$PG_ADMIN_USER" \
  --admin-password "$POSTGRES_ADMIN_PASSWORD" \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --version 16 \
  --storage-size 32 \
  --public-access 0.0.0.0

echo "Adding firewall rule to allow Azure and public access (Container Apps use dynamic IPs)..."
az postgres flexible-server firewall-rule create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$PG_SERVER_NAME" \
  --rule-name AllowAll \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 255.255.255.255

echo "Creating database: $PG_DATABASE"
az postgres flexible-server db create \
  --resource-group "$RESOURCE_GROUP" \
  --server-name "$PG_SERVER_NAME" \
  --database-name "$PG_DATABASE"

# URL-encode password for connection string (replace & with %26, etc.)
PG_PASSWORD_ENC=$(printf '%s' "$POSTGRES_ADMIN_PASSWORD" | jq -sRr @uri)
DATABASE_URL="postgresql://${PG_ADMIN_USER}:${PG_PASSWORD_ENC}@${PG_SERVER_NAME}.${PG_HOST_SUFFIX}:5432/${PG_DATABASE}?sslmode=require"

echo ""
echo "PostgreSQL Flexible Server is ready."
echo "DATABASE_URL (add to Container App via azure-set-secrets.sh):"
echo "$DATABASE_URL"
echo ""
echo "One-time schema init: The API app runs migrations on startup (CREATE TABLE IF NOT EXISTS)."
echo "Deploy or restart the API with DATABASE_URL set; the first start will create the tables."
echo ""
echo "To set DATABASE_URL on the API app, run:"
echo "  DATABASE_URL='<value above>' HATCH_EMAIL=... HATCH_PASSWORD=... ... ./scripts/azure-set-secrets.sh"
echo "(Or add database-url to the Container App secrets and set env DATABASE_URL=secretref:database-url)."
echo ""
echo "Save the admin password somewhere secure; you need it for DATABASE_URL."
