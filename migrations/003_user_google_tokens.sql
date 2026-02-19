-- Store Google OAuth refresh tokens per admin user for Google Photos API access.
CREATE TABLE IF NOT EXISTS user_google_tokens (
    email TEXT PRIMARY KEY,
    refresh_token TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
