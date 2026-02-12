#!/usr/bin/env bash
#
# Verify the Azure-deployed API has HATCH_EMAIL and HATCH_PASSWORD set.
# Uses GET /health and checks the "hatch_configured" field (no credentials exposed).
#
# Option 1 - With Azure CLI (gets API URL automatically):
#   az login   # if needed
#   ./scripts/verify_azure_hatch_credentials.sh
#
# Option 2 - With API URL in env (no Azure CLI needed):
#   API_URL=https://hatch-sync-api.orangeisland-4b7f6755.westus2.azurecontainerapps.io ./scripts/verify_azure_hatch_credentials.sh
#
set -euo pipefail

RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-hatchsync}"
APP_NAME="${AZURE_CONTAINERAPP_NAME:-hatch-sync-api}"
# From docs/GITHUB_SECRETS.md if API_URL not set and az not available
DEFAULT_URL="https://hatch-sync-api.orangeisland-4b7f6755.westus2.azurecontainerapps.io"

if [ -n "${API_URL:-}" ]; then
  BASE_URL="${API_URL%/}"
elif command -v az &>/dev/null; then
  echo "Getting API URL from Azure..."
  FQDN=$(az containerapp show \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query "properties.configuration.ingress.fqdn" -o tsv 2>/dev/null || true)
  if [ -z "$FQDN" ]; then
    echo "Could not get Container App FQDN. Check 'az login' and resource group '$RESOURCE_GROUP', app '$APP_NAME'."
    exit 1
  fi
  BASE_URL="https://${FQDN}"
else
  BASE_URL="$DEFAULT_URL"
  echo "Using default API URL (set API_URL to override): $BASE_URL"
fi

HEALTH_URL="${BASE_URL}/health"
echo "Checking: $HEALTH_URL"

RESP=$(curl -sS --connect-timeout 15 --max-time 45 "$HEALTH_URL" 2>/dev/null) || true
if [ -z "$RESP" ]; then
  echo "Request failed or timed out. Is the API reachable?"
  exit 1
fi

if echo "$RESP" | grep -q '"hatch_configured"'; then
  HATCH=$(echo "$RESP" | sed -n 's/.*"hatch_configured": *\(true\|false\).*/\1/p')
  if [ "$HATCH" = "true" ]; then
    echo "OK: Hatch credentials are set on the Azure API (hatch_configured: true)."
    echo "$RESP" | jq . 2>/dev/null || echo "$RESP"
    exit 0
  else
    echo "Hatch credentials are NOT set on the Azure API (hatch_configured: false)."
    echo "Run: HATCH_EMAIL=... HATCH_PASSWORD=... GOOGLE_CALENDAR_SHARE_EMAIL=... ./scripts/azure-set-secrets.sh"
    echo "$RESP" | jq . 2>/dev/null || echo "$RESP"
    exit 1
  fi
fi

# Old health response without hatch_configured
echo "API responded but health endpoint may not include hatch_configured yet (redeploy backend to get it):"
echo "$RESP" | jq . 2>/dev/null || echo "$RESP"
echo ""
echo "To verify credentials anyway: curl -s ${BASE_URL}/grow/data | jq ."
echo "  - 503 with 'HATCH_EMAIL and HATCH_PASSWORD required' or 'Login failed' => not set or wrong."
echo "  - 200 with babies/feedings/etc. => credentials OK."
