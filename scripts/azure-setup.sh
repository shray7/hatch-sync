#!/usr/bin/env bash
#
# Create Azure resources for hatch-sync in the TaskAgent subscription:
#   - Resource group: hatchsync
#   - Azure Container Registry: hatchsyncacr
#   - Container Apps environment: hatchsync-env
#   - Container App: hatch-sync-api (placeholder image; first CI deploy will replace it)
#   - Container App: hatch-sync-redis (Phase 1 internal Redis)
#
# Prerequisites: Azure CLI installed and logged in (az login).
# Usage: ./scripts/azure-setup.sh [location]
#   location defaults to westus2.

set -euo pipefail

SUBSCRIPTION_NAME="${AZURE_SUBSCRIPTION:-TaskAgent}"
RESOURCE_GROUP="hatchsync"
LOCATION="${1:-westus2}"
ACR_NAME="hatchsyncacr"
ACA_ENV_NAME="hatchsync-env"
API_APP_NAME="hatch-sync-api"
REDIS_APP_NAME="hatch-sync-redis"

echo "Using subscription: $SUBSCRIPTION_NAME"
az account set --subscription "$SUBSCRIPTION_NAME"

echo "Creating resource group: $RESOURCE_GROUP in $LOCATION"
az group create --name "$RESOURCE_GROUP" --location "$LOCATION"

echo "Creating Azure Container Registry: $ACR_NAME"
az acr create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$ACR_NAME" \
  --sku Basic \
  --admin-enabled true

echo "Creating Container Apps environment: $ACA_ENV_NAME"
az containerapp env create \
  --name "$ACA_ENV_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION"

# Redis (Phase 1): internal-only container app so the API can use REDIS_URL pointing at it.
# Internal ingress hostname will be something like hatch-sync-redis.internal.<env-default-domain>.
echo "Creating Redis Container App (internal): $REDIS_APP_NAME"
REDIS_APP_ID=$(az containerapp create \
  --name "$REDIS_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --environment "$ACA_ENV_NAME" \
  --image "redis:7-alpine" \
  --target-port 6379 \
  --ingress internal \
  --min-replicas 1 \
  --max-replicas 1 \
  --cpu 0.25 \
  --memory 0.5Gi \
  --query id -o tsv)

# Get the default domain for the environment so we can build REDIS_URL for the API app.
ENV_DEFAULT_DOMAIN=$(az containerapp env show \
  --name "$ACA_ENV_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query properties.defaultDomain -o tsv)
# Internal hostname for container apps in the same environment: <app-name>.internal.<defaultDomain>
REDIS_HOST="${REDIS_APP_NAME}.internal.${ENV_DEFAULT_DOMAIN}"
REDIS_URL="redis://${REDIS_HOST}:6379/0"
echo "Redis internal URL (use for API app REDIS_URL): $REDIS_URL"

# API app: start with a placeholder image; GitHub Actions will build and deploy the real image.
echo "Creating API Container App: $API_APP_NAME"
az containerapp create \
  --name "$API_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --environment "$ACA_ENV_NAME" \
  --image "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest" \
  --target-port 8000 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 2 \
  --cpu 0.5 \
  --memory 1Gi \
  --registry-server "$ACR_NAME.azurecr.io" \
  --env-vars "REDIS_URL=secretref:redis-url" "HATCH_CACHE_TTL_SECONDS=900" "GOOGLE_SERVICE_ACCOUNT_FILE=/app/service_account.json" \
  --secrets "redis-url=$REDIS_URL"

echo "Enabling ACR pull for the API app managed identity..."
# Assign AcrPull to the API app's system-assigned identity so it can pull from ACR.
API_PRINCIPAL_ID=$(az containerapp show \
  --name "$API_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query identity.principalId -o tsv)
ACR_ID=$(az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query id -o tsv)
az role assignment create \
  --assignee "$API_PRINCIPAL_ID" \
  --role AcrPull \
  --scope "$ACR_ID"

echo ""
echo "Done. Next steps:"
echo "1. Run ./scripts/azure-create-sp.sh and add the printed JSON as GitHub secret AZURE_CREDENTIALS."
echo "2. Run ./scripts/azure-set-secrets.sh with HATCH_EMAIL, HATCH_PASSWORD, GOOGLE_CALENDAR_SHARE_EMAIL set (see docs/deploy-azure.md)."
echo "3. Add GitHub secret GOOGLE_SERVICE_ACCOUNT_JSON (full contents of your Google service account JSON key)."
echo "4. Add GitHub secret VITE_API_URL after first deploy (API URL from portal or workflow output)."
echo "5. Push to main to trigger the backend workflow; it will build, push, and update $API_APP_NAME with the real image."
