# hatch-sync

A small **FastAPI** API that talks to **Hatch Rest** devices (sound machines) using the unofficial Python library [hatch-rest-api](https://github.com/dahlb/hatch_rest_api). Use it to list devices, set volume, and change sounds from scripts or other apps. It also syncs **Hatch Grow** data (diapers, feedings, sleep, weight) to a Google Calendar.

## Requirements

- Python 3.10+
- A Hatch account with at least one Rest (or Rest Mini / Rest+) device
- **PostgreSQL** for storing Grow data (diapers, feedings, sleep, weight, photos). The app runs without it but `/grow/data` and `/grow/photos` will return empty until a DB is configured and the background job has run.
- For Grow → Calendar sync: a Google Cloud service account with Calendar API enabled

## Setup

```bash
cd hatch-sync
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: HATCH_EMAIL, HATCH_PASSWORD; for sync add GOOGLE_SERVICE_ACCOUNT_FILE, GOOGLE_CALENDAR_SHARE_EMAIL
# For Grow data: set DATABASE_URL to your PostgreSQL connection string (e.g. postgresql://user:pass@localhost:5432/hatch)
```

### PostgreSQL (Grow data)

Grow data (and calendar sync state) is stored in PostgreSQL. Set `DATABASE_URL` in `.env` (e.g. `postgresql://user:pass@localhost:5432/hatch`). On startup the app runs migrations from `migrations/001_initial.sql` to create the tables. You can also run them manually:

```bash
psql "$DATABASE_URL" -f migrations/001_initial.sql
```

The background job (every 15 minutes) fetches from the Hatch Grow API and upserts into the DB; `/grow/data` and `/grow/photos` read only from the database.

### Google Calendar sync (optional)

1. Go to [Google Cloud Console](https://console.cloud.google.com), create or select a project.
2. Enable **Google Calendar API**: APIs & Services → Library → search “Google Calendar API” → Enable.
3. Create a **Service Account**: IAM & Admin → Service Accounts → Create. No special roles needed.
4. Create a key: open the service account → Keys → Add Key → Create new key → JSON. Save the file as `service_account.json` in the project root (do not commit it).
5. In `.env` set:
   - `GOOGLE_SERVICE_ACCOUNT_FILE=service_account.json`
   - `GOOGLE_CALENDAR_SHARE_EMAIL=your@gmail.com` (the calendar will be shared with this address so it appears in your Google Calendar).
   - All times are interpreted and displayed in **PST** (America/Los_Angeles) by default. Set `HATCH_TIMEZONE` to another IANA timezone (e.g. `America/New_York`) to use that for synced events and API responses.

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
- Sync state is stored in the database (`synced_to_calendar_at` on each row) so only new diapers/feedings/sleep/weight entries become calendar events.
