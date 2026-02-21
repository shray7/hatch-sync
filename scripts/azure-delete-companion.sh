#!/usr/bin/env bash
#
# Delete the hatch-sync-companion Container App from Azure (Google Photos Picker).
# Run with: ./scripts/azure-delete-companion.sh
#
# Prerequisites: Azure CLI installed and logged in (az login).

set -euo pipefail

RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-hatchsync}"
APP_NAME="${COMPANION_APP_NAME:-hatch-sync-companion}"

echo "Deleting Container App '$APP_NAME' from resource group '$RESOURCE_GROUP'..."
az containerapp delete \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --yes

echo "Done. Companion app deleted."
