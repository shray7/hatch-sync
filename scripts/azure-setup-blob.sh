#!/usr/bin/env bash
#
# One-time setup: Create Azure Storage Account and blob containers for hatch-sync.
# Creates hatch-photos (photos) and hatch-videos (videos) containers.
# Used for admin device uploads and Hatch Grow photos/videos.
#
# Prerequisites: Azure CLI installed and logged in (az login).
# Usage: ./scripts/azure-setup-blob.sh [location]
#   location defaults to westus2.
#
# Output: AZURE_BLOB_CONNECTION_STRING, AZURE_BLOB_CONTAINER, AZURE_BLOB_VIDEO_CONTAINER
#   for use with azure-set-secrets.sh.

set -euo pipefail

SUBSCRIPTION_NAME="${AZURE_SUBSCRIPTION:-TaskAgent}"
RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-hatchsync}"
LOCATION="${1:-westus2}"
# Storage account name: 3-24 chars, lowercase alphanumeric, globally unique
STORAGE_ACCOUNT="${AZURE_STORAGE_ACCOUNT:-hatchsyncsa}"
PHOTO_CONTAINER="${AZURE_BLOB_CONTAINER:-hatch-photos}"
VIDEO_CONTAINER="${AZURE_BLOB_VIDEO_CONTAINER:-hatch-videos}"

echo "Using subscription: $SUBSCRIPTION_NAME"
az account set --subscription "$SUBSCRIPTION_NAME"

# Ensure resource group exists (may have been created by azure-setup.sh)
if ! az group show --name "$RESOURCE_GROUP" &>/dev/null; then
  echo "Creating resource group: $RESOURCE_GROUP in $LOCATION"
  az group create --name "$RESOURCE_GROUP" --location "$LOCATION"
fi

echo "Creating Storage Account: $STORAGE_ACCOUNT in $RESOURCE_GROUP ($LOCATION)..."
az storage account create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$STORAGE_ACCOUNT" \
  --location "$LOCATION" \
  --sku Standard_LRS \
  --kind StorageV2 \
  --allow-blob-public-access false

echo "Creating blob containers: $PHOTO_CONTAINER (photos), $VIDEO_CONTAINER (videos)"
az storage container create \
  --account-name "$STORAGE_ACCOUNT" \
  --name "$PHOTO_CONTAINER" \
  --auth-mode login
az storage container create \
  --account-name "$STORAGE_ACCOUNT" \
  --name "$VIDEO_CONTAINER" \
  --auth-mode login

CONN_STR=$(az storage account show-connection-string \
  --resource-group "$RESOURCE_GROUP" \
  --name "$STORAGE_ACCOUNT" \
  --query connectionString -o tsv)

echo ""
echo "Azure Blob Storage is ready."
echo "  Photos: $PHOTO_CONTAINER"
echo "  Videos: $VIDEO_CONTAINER"
echo ""
echo "To set on the API app via azure-set-secrets.sh, run:"
echo "  AZURE_BLOB_CONNECTION_STRING='$CONN_STR' AZURE_BLOB_CONTAINER='$PHOTO_CONTAINER' AZURE_BLOB_VIDEO_CONTAINER='$VIDEO_CONTAINER' \\"
echo "    HATCH_EMAIL=... HATCH_PASSWORD=... GOOGLE_CALENDAR_SHARE_EMAIL=... ./scripts/azure-set-secrets.sh"
echo ""
