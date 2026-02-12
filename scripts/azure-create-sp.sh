#!/usr/bin/env bash
#
# Create an Azure AD service principal for GitHub Actions (backend workflow).
# Output is JSON to paste into GitHub repo secret AZURE_CREDENTIALS.
#
# Prerequisites: Azure CLI installed and logged in (az login).
# Usage: ./scripts/azure-create-sp.sh

set -euo pipefail

SUBSCRIPTION_NAME="${AZURE_SUBSCRIPTION:-TaskAgent}"
RESOURCE_GROUP="hatchsync"
SP_NAME="hatch-sync-github"

echo "Using subscription: $SUBSCRIPTION_NAME"
az account set --subscription "$SUBSCRIPTION_NAME"

SUBSCRIPTION_ID=$(az account show --query id -o tsv)
SCOPE="/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}"

echo "Creating service principal '$SP_NAME' with Contributor on resource group '${RESOURCE_GROUP}'..."
echo ""

JSON=$(az ad sp create-for-rbac \
  --name "$SP_NAME" \
  --role contributor \
  --scopes "$SCOPE" \
  --sdk-auth)

echo "Add the following JSON as a GitHub repository secret named AZURE_CREDENTIALS:"
echo "  Settings → Secrets and variables → Actions → New repository secret"
echo ""
echo "--- Copy below this line ---"
echo "$JSON"
echo "--- Copy above this line ---"
echo ""
echo "Do not commit this output or share it; it contains credentials."
