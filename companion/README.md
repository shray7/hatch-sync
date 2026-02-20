# Uppy Companion for Google Photos Picker

This server powers the **Import from Google Photos** flow in the Admin UI. It handles OAuth and streams selected files from Google Photos to your hatch-sync API.

## Setup

1. **Google Cloud**
   - In the same project as your hatch-sync OAuth client (or a new one), enable **Google Photos Picker API** (Library → search "Photos Picker").
   - Use the same OAuth 2.0 Web client ID (or create one) and add your frontend origin to **Authorized JavaScript origins** (e.g. `https://shray7.github.io`).

2. **Environment**
   - Copy `.env.example` to `.env` and set:
     - `COMPANION_CLIENT_ORIGINS`: frontend origin(s), e.g. `https://shray7.github.io`
     - `COMPANION_UPLOAD_URLS`: your API upload-companion URL, e.g. `https://hatch-sync-api..../admin/upload-companion`
     - `COMPANION_UPLOAD_HEADERS`: `{"X-Companion-Secret":"<same as COMPANION_UPLOAD_SECRET on API>"}`
     - `COMPANION_SECRET`: long random string
     - In production: `COMPANION_DOMAIN`, `COMPANION_PROTOCOL=https`

3. **Backend**
   - Set `COMPANION_UPLOAD_SECRET` on the hatch-sync API (same value as in `COMPANION_UPLOAD_HEADERS`).

4. **Frontend**
   - Set `VITE_COMPANION_URL` (Companion’s public URL) and `VITE_GOOGLE_CLIENT_ID` (Google OAuth client ID) so the Admin UI can show the Uppy picker.

## Run locally

```bash
npm install
npm start
```

Then set `VITE_COMPANION_URL=http://localhost:3020` and ensure your frontend origin is in `COMPANION_CLIENT_ORIGINS`. For production, run Companion behind HTTPS and set `COMPANION_DOMAIN` and `COMPANION_PROTOCOL=https`.
