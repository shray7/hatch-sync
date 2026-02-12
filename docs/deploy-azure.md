# Deploying hatch-sync to Azure and GitHub Pages

## Before first push (no secrets in repo)

1. **Confirm these are not staged** (they must be in `.gitignore` and never committed):
   - `.env`
   - `service_account.json`
   - `sync_state.json`
   - `node_modules/` and `frontend/node_modules/`

2. From the repo root:
   ```bash
   git status
   # Ensure .env and service_account.json do NOT appear. Then:
   git add .
   git status   # double-check
   git commit -m "Add Azure deploy, Redis cache, and GitHub Actions"
   ```

3. **Add GitHub secrets** before pushing (so the first run of the backend workflow can build and deploy). See [GITHUB_SECRETS.md](GITHUB_SECRETS.md) for the exact list and how to get each value.

4. Push: `git push origin main` (or your default branch).

If the repo is not yet a git repo: `git init`, then add a remote and follow steps 2–4.

---

## Overview

- **Backend**: FastAPI app runs as a container on **Azure Container Apps** in the **hatchsync** resource group (subscription **TaskAgent**). Images are built and pushed to **Azure Container Registry**; GitHub Actions deploys on push to `main`.
- **Frontend**: Vue SPA is built and deployed to **GitHub Pages** by GitHub Actions; it calls the Azure backend using `VITE_API_URL`.
- **Redis**: Used for caching Hatch API responses. **Phase 1** uses a containerized Redis app in the same Container Apps environment. **Phase 2** (optional) is Azure Cache for Redis.

---

## 1. One-time Azure setup

### 1.1 Create resources (resource group, ACR, Container Apps, Redis)

From the repo root, with [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) installed and logged in (`az login`):

```bash
chmod +x scripts/azure-setup.sh
./scripts/azure-setup.sh westus2
```

You can pass another location (e.g. `eastus`) instead of `westus2`. The script uses subscription **TaskAgent** by default; set `AZURE_SUBSCRIPTION` if your subscription name differs.

This creates:

- Resource group: **hatchsync**
- Azure Container Registry: **hatchsyncacr**
- Container Apps environment: **hatchsync-env**
- Container App: **hatch-sync-redis** (internal Redis for Phase 1)
- Container App: **hatch-sync-api** (placeholder image; first CI deploy replaces it)

The script prints the internal **Redis URL** and stores it as a secret on the API app so `REDIS_URL` is set automatically.

### 1.2 Service principal for GitHub Actions

Create a service principal scoped to the **hatchsync** resource group so the workflow can push images to ACR and update the Container App:

```bash
chmod +x scripts/azure-create-sp.sh
./scripts/azure-create-sp.sh
```

The script prints JSON. Copy the entire output and add it as a **GitHub repository secret** named **`AZURE_CREDENTIALS`** (Settings → Secrets and variables → Actions → New repository secret).

### 1.3 Container App secrets (Hatch and Google)

Set Hatch and Google credentials as **secrets** on the Container App using the helper script (values from environment variables, not written to disk):

```bash
chmod +x scripts/azure-set-secrets.sh
HATCH_EMAIL=your@email.com HATCH_PASSWORD=your_password GOOGLE_CALENDAR_SHARE_EMAIL=you@gmail.com \
  ./scripts/azure-set-secrets.sh
```

This sets the secrets and links them to the app’s environment variables. The script also preserves existing env vars (e.g. `REDIS_URL`, `GOOGLE_SERVICE_ACCOUNT_FILE`).

**Google service account JSON**: The backend workflow bakes the service account file into the image from a GitHub secret. Add your JSON as a repo secret:

1. In Google Cloud Console, create a service account and download its JSON key (as in the main README).
2. In GitHub: **Settings → Secrets and variables → Actions → New repository secret**.
3. Name: **`GOOGLE_SERVICE_ACCOUNT_JSON`**. Value: paste the **entire** contents of the JSON key file.

The workflow writes this into `service_account.json` in the build context; the image is built with that file at `/app/service_account.json`, and the Container App already has `GOOGLE_SERVICE_ACCOUNT_FILE=/app/service_account.json` set by the setup script. If `GOOGLE_SERVICE_ACCOUNT_JSON` is not set, the workflow still builds (with an empty `{}` file); sync will then fail until you add the secret and redeploy.

### 1.4 GitHub repository configuration

In **Settings → Secrets and variables → Actions** add:

| Secret / Variable | Description |
|-------------------|-------------|
| **AZURE_CREDENTIALS** | JSON from `./scripts/azure-create-sp.sh` (required for backend workflow). |
| **GOOGLE_SERVICE_ACCOUNT_JSON** | Full contents of your Google service account JSON key (required for Calendar sync in Azure). |
| **VITE_API_URL** | Full URL of the API (e.g. `https://hatch-sync-api.<random>.azurecontainerapps.io`) (required for frontend build). |

Optional:

- **VITE_BASE_URL**: Override base path for GitHub Pages (default is `/<repo-name>/`).

Enable **GitHub Pages**: **Settings → Pages → Source** = **GitHub Actions**.

---

## 2. Redis: Phase 1 vs Phase 2

### Phase 1 (default): Containerized Redis in Container Apps

The setup script creates a second Container App, **hatch-sync-redis**, running `redis:7-alpine` with **internal** ingress. The API app’s `REDIS_URL` is set to that internal host (e.g. `redis://hatch-sync-redis.internal.<env-default-domain>:6379/0`).

- **Pros**: No extra cost, simple, same VNet as the API.
- **Cons**: Not managed; if the Redis app restarts, cache is lost.

### Phase 2 (optional): Azure Cache for Redis

For a managed, persistent cache:

1. Create **Azure Cache for Redis** in the **hatchsync** resource group (e.g. Basic C0).
2. In the Azure portal, open the cache → **Access keys** (or **Connection strings**). Use the host and port (typically **6380** with SSL).
3. Connection string is usually `rediss://<host>:6380,password=<access-key>,ssl=True`.
4. Update the API app’s Redis secret to this value:
   - `az containerapp secret set --name hatch-sync-api --resource-group hatchsync --secrets redis-url="rediss://..."`.
5. Restart or create a new revision of the API app.

The app’s `app/cache.py` uses `REDIS_URL` as-is; the `redis` client supports `rediss://` for TLS. If you use a different format (e.g. comma-separated options), ensure it matches what `redis.from_url()` expects.

---

## 3. After the first deploy

1. **Backend**: Push to `main` (or run the **Backend (Azure)** workflow). It builds the image, pushes to **hatchsyncacr**, and updates the **hatch-sync-api** Container App. Get the API URL from the Azure portal (Container Apps → hatch-sync-api → Application Url) or from the workflow’s “Get API URL and smoke test” step.
2. **Frontend**: Set **VITE_API_URL** to that API URL, then push changes under `frontend/` (or run the **Frontend (GitHub Pages)** workflow). The site will be at `https://<owner>.github.io/<repo>/`.
3. **Smoke test**: Open `/health` on the API URL; you should see `{"status":"ok","redis":"ok"}` (or `"disabled"` if Redis is not used). Then open the GitHub Pages site and confirm the dashboard loads and calls the API.

---

## 4. Troubleshooting

- **403 / ACR pull**: The API app’s managed identity has **AcrPull** on the registry; if you recreated the app, run the role assignment again (see end of `scripts/azure-setup.sh`).
- **Redis connection refused**: Ensure **hatch-sync-redis** is running and that `REDIS_URL` uses the internal hostname (e.g. `*.internal.*`). For Azure Cache for Redis, use the correct port (6380) and `rediss://` with SSL.
- **CORS**: The FastAPI app allows all origins; if you restrict them later, add your GitHub Pages origin (e.g. `https://<owner>.github.io`).

### 4.1 API not reachable (timeout / connection refused)

1. **Verify from your machine** (with Azure CLI and `az login`):
   ```bash
   ./scripts/verify_azure_api_reachable.sh
   ```
   This prints the app’s FQDN, ingress config, active revision/replicas, and tries `GET /health`. If the HTTP request fails, the script suggests next steps.

2. **In Azure Portal**: **Container Apps** → **hatch-sync-api** → **Revisions** — confirm an active revision has **Replicas** &gt; 0. If replicas are 0 or the revision is not receiving traffic, check **Log stream** (or **Monitoring** → **Logs**) for startup or runtime errors (e.g. missing env vars, Redis unreachable, crash on import).

3. **First request after idle** can take 1–2 minutes (cold start). Retry after a short wait.
