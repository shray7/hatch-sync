#!/usr/bin/env bash
#
# Verify the Azure-deployed hatch-sync API is reachable.
# Uses Azure CLI to show app config and FQDN, then curls /health.
#
# Prerequisites: Azure CLI installed and logged in (az login).
# Usage: ./scripts/verify_azure_api_reachable.sh
#
set -euo pipefail

RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-hatchsync}"
APP_NAME="${AZURE_CONTAINERAPP_NAME:-hatch-sync-api}"

echo "=== Azure Container App: $APP_NAME (resource group: $RESOURCE_GROUP) ==="
if ! command -v az &>/dev/null; then
  echo "Azure CLI (az) is not installed. Install: https://learn.microsoft.com/en-us/cli/azure/install-azure-cli"
  exit 1
fi

echo ""
echo "1. Ingress (should be external, targetPort 8000)"
az containerapp show \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query "properties.configuration.ingress" -o table 2>/dev/null || {
  echo "   Failed to get app. Run 'az login' and check app name/resource group."
  exit 1
}

echo ""
echo "2. FQDN (public URL)"
FQDN=$(az containerapp show \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query "properties.configuration.ingress.fqdn" -o tsv 2>/dev/null)
if [ -z "$FQDN" ]; then
  echo "   No FQDN found. Ingress may be disabled or app not fully created."
  exit 1
fi
echo "   https://${FQDN}"

echo ""
echo "3. Active revision and replicas"
az containerapp revision list \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query "[?properties.active==\`true\`].{Name:name, Active:properties.active, Replicas:properties.replicas}" -o table 2>/dev/null || true

echo ""
echo "4. HTTP GET /health (timeout 30s)"
HEALTH_URL="https://${FQDN}/health"
if curl -sf --connect-timeout 10 --max-time 30 "$HEALTH_URL" >/tmp/hatch_health.json 2>/dev/null; then
  echo "   OK - API is reachable"
  cat /tmp/hatch_health.json | jq . 2>/dev/null || cat /tmp/hatch_health.json
  rm -f /tmp/hatch_health.json
else
  echo "   FAILED - Request timed out or connection refused"
  echo ""
  echo "   Possible causes:"
  echo "   - App is still starting (cold start can take 1–2 min). Wait and try again."
  echo "   - No running replicas: in Portal → Container Apps → $APP_NAME → Revisions, check replicas."
  echo "   - App crashing: Portal → $APP_NAME → Log stream (or Monitoring → Logs) for errors."
  echo "   - Wrong subscription: run 'az account show' and 'az account set --subscription <name>'."
  echo ""
  echo "   Manual test: curl -v $HEALTH_URL"
  exit 1
fi
