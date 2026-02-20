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
| **VITE_COMPANION_URL** | After deploying Companion (see below), set to `https://hatch-sync-companion.<your-env>.azurecontainerapps.io`. Used with **VITE_GOOGLE_CLIENT_ID** for the Google Photos Picker in Admin. |
| **VITE_GOOGLE_CLIENT_ID** | Google OAuth 2.0 Web client ID for the Picker (add your frontend origin to Authorized JavaScript origins; enable **Google Photos Picker API** in the same project). |

---

## Companion (Google Photos Picker) on Azure

1. **Secrets** (Settings → Secrets and variables → Actions):
   - **COMPANION_UPLOAD_SECRET**: A long random string. Use the **same value** when running `./scripts/azure-set-secrets.sh` so the API accepts uploads from Companion.
   - Optional: **COMPANION_GOOGLE_KEY** and **COMPANION_GOOGLE_SECRET** (Google OAuth for server-side; can leave unset and rely on clientId from frontend).
   - Optional: **COMPANION_SECRET**: Secret for Companion’s own signing (defaults to a placeholder if unset).

2. **API**: Run `azure-set-secrets.sh` with `COMPANION_UPLOAD_SECRET=<same value>` so the API has `COMPANION_UPLOAD_SECRET` set.

3. **Deploy Companion**: Push `companion/` changes or run the **Companion (Azure)** workflow. It builds the Companion image, creates the `hatch-sync-companion` Container App if needed, and deploys.

4. **Repo variables** (Settings → Variables): Set **VITE_COMPANION_URL** = `https://hatch-sync-companion.<env-default-domain>` (see workflow run output for the exact URL) and **VITE_GOOGLE_CLIENT_ID** = your Google OAuth client ID. Then re-run the **Frontend (GitHub Pages)** workflow so the build includes the Picker.

---

## After adding secrets

1. Enable **GitHub Pages**: Settings → Pages → Source = **GitHub Actions**.
2. Push to `main` (or run the Backend and Frontend workflows manually) to build and deploy.
3. Set Container App secrets for Hatch + Google (and optionally PostgreSQL) so the API can sync: run `./scripts/azure-set-secrets.sh` with `HATCH_EMAIL`, `HATCH_PASSWORD`, `GOOGLE_CALENDAR_SHARE_EMAIL`, and the other required env vars (see script). If you created PostgreSQL with `./scripts/azure-setup-postgres.sh`, also set `DATABASE_URL` in the environment when running set-secrets so Grow data is stored in the database. For admin (Google sign-in, upload, Google Photos import), also pass `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `ADMIN_ALLOWLIST_EMAILS`, `SESSION_SECRET`, `API_BASE_URL`, and `FRONTEND_URL` (see [deploy-azure.md](deploy-azure.md)).
