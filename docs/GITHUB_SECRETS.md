# GitHub Actions secrets

Add these in your repo: **Settings → Secrets and variables → Actions → New repository secret**.

Do not commit `.env`, `service_account.json`, or the AZURE_CREDENTIALS JSON.

---

## Required secrets

| Secret | How to get the value |
|--------|----------------------|
| **AZURE_CREDENTIALS** | Run `./scripts/azure-create-sp.sh` (with `az login` and subscription TaskAgent). Copy the **entire** JSON output and paste as the secret value. |
| **GOOGLE_SERVICE_ACCOUNT_JSON** | Open your Google Cloud service account JSON key file (the one you use for Calendar). Copy the **entire** file contents and paste as the secret value. |
| **VITE_API_URL** | Your backend URL. For the current Azure deploy use: `https://hatch-sync-api.orangeisland-4b7f6755.westus2.azurecontainerapps.io` (no trailing slash). |

---

## Optional

| Variable | Description |
|----------|-------------|
| **VITE_BASE_URL** | Override base path for GitHub Pages. Default is `/<repo-name>/` (e.g. `/hatch-sync/`). Only set if your repo name or Pages URL differs. |

---

## Remove Companion from Azure (if previously deployed)

To delete the hatch-sync-companion Container App: run `./scripts/azure-delete-companion.sh` or delete it manually in Azure Portal (Container Apps → hatch-sync-companion → Delete).

---

## After adding secrets

1. Enable **GitHub Pages**: Settings → Pages → Source = **GitHub Actions**.
2. Push to `main` (or run the Backend and Frontend workflows manually) to build and deploy.
3. Set Container App secrets for Hatch + Google (and optionally PostgreSQL) so the API can sync: run `./scripts/azure-set-secrets.sh` with `HATCH_EMAIL`, `HATCH_PASSWORD`, `GOOGLE_CALENDAR_SHARE_EMAIL`, and the other required env vars (see script). If you created PostgreSQL with `./scripts/azure-setup-postgres.sh`, also set `DATABASE_URL` in the environment when running set-secrets so Grow data is stored in the database. For admin (Google sign-in, upload from device), also pass `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `ADMIN_ALLOWLIST_EMAILS`, `SESSION_SECRET`, `API_BASE_URL`, and `FRONTEND_URL` (see [deploy-azure.md](deploy-azure.md)).
