# hatch-sync

A small **FastAPI** API that talks to **Hatch Rest** devices (sound machines) using the unofficial Python library [hatch-rest-api](https://github.com/dahlb/hatch_rest_api). Use it to list devices, set volume, and change sounds from scripts or other apps. It also syncs **Hatch Grow** data (diapers, feedings, sleep, weight) to a Google Calendar.

## Requirements

- Python 3.10+
- A Hatch account with at least one Rest (or Rest Mini / Rest+) device
- For Grow → Calendar sync: a Google Cloud service account with Calendar API enabled

## Setup

```bash
cd hatch-sync
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: HATCH_EMAIL, HATCH_PASSWORD; for sync add GOOGLE_SERVICE_ACCOUNT_FILE, GOOGLE_CALENDAR_SHARE_EMAIL
```

### Google Calendar sync (optional)

1. Go to [Google Cloud Console](https://console.cloud.google.com), create or select a project.
2. Enable **Google Calendar API**: APIs & Services → Library → search “Google Calendar API” → Enable.
3. Create a **Service Account**: IAM & Admin → Service Accounts → Create. No special roles needed.
4. Create a key: open the service account → Keys → Add Key → Create new key → JSON. Save the file as `service_account.json` in the project root (do not commit it).
5. In `.env` set:
   - `GOOGLE_SERVICE_ACCOUNT_FILE=service_account.json`
   - `GOOGLE_CALENDAR_SHARE_EMAIL=your@gmail.com` (the calendar will be shared with this address so it appears in your Google Calendar).

On first sync the app creates a calendar named “{Baby name} - Baby Tracker” and shares it with that email.

## Run

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API: http://localhost:8000  
- Docs: http://localhost:8000/docs  

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/devices` | List all Hatch Rest devices |
| GET | `/devices/{device_id}` | Get one device |
| POST | `/devices/{device_id}/volume?volume=0.5` | Set volume (0.0–1.0) |
| POST | `/devices/{device_id}/audio_track?track_name=Ocean` | Set sound (e.g. Ocean, Rain, Wind) |
| POST | `/sync` | Run Hatch Grow → Google Calendar sync once (also runs every 15 min in background) |

## Deployment

To deploy the backend to **Azure Container Apps** and the frontend to **GitHub Pages**, see [docs/deploy-azure.md](docs/deploy-azure.md). Before pushing, add the required repo secrets—see [docs/GITHUB_SECRETS.md](docs/GITHUB_SECRETS.md) for the list and how to get each value. The repo includes GitHub Actions workflows (`.github/workflows/backend.yml` and `.github/workflows/frontend.yml`) for CI/CD.

## Notes

- The underlying **hatch-rest-api** is reverse-engineered and unsupported by Hatch; it can break if Hatch change their cloud API.
- Credentials are read from `.env`. Do not commit `.env` or `service_account.json`.
- Sync state is stored in `sync_state.json` so only new diapers/feedings/sleep/weight entries become calendar events.
