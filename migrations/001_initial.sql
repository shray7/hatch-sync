-- Hatch Grow data: babies, feedings, diapers, sleeps, weights, photos.
-- Sync state is encoded as synced_to_calendar_at on each row.

CREATE TABLE IF NOT EXISTS babies (
    id SERIAL PRIMARY KEY,
    hatch_id BIGINT UNIQUE NOT NULL,
    name TEXT,
    birth_date DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS feedings (
    id SERIAL PRIMARY KEY,
    baby_id INTEGER NOT NULL REFERENCES babies(id) ON DELETE CASCADE,
    hatch_id BIGINT UNIQUE NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    amount NUMERIC,
    duration_seconds INTEGER,
    method TEXT,
    source TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    synced_to_calendar_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_feedings_baby_id ON feedings(baby_id);
CREATE INDEX IF NOT EXISTS idx_feedings_synced ON feedings(synced_to_calendar_at) WHERE synced_to_calendar_at IS NULL;

CREATE TABLE IF NOT EXISTS diapers (
    id SERIAL PRIMARY KEY,
    baby_id INTEGER NOT NULL REFERENCES babies(id) ON DELETE CASCADE,
    hatch_id BIGINT UNIQUE NOT NULL,
    diaper_date TIMESTAMPTZ NOT NULL,
    diaper_type TEXT,
    details TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    synced_to_calendar_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_diapers_baby_id ON diapers(baby_id);
CREATE INDEX IF NOT EXISTS idx_diapers_synced ON diapers(synced_to_calendar_at) WHERE synced_to_calendar_at IS NULL;

CREATE TABLE IF NOT EXISTS sleeps (
    id SERIAL PRIMARY KEY,
    baby_id INTEGER NOT NULL REFERENCES babies(id) ON DELETE CASCADE,
    hatch_id BIGINT UNIQUE NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    synced_to_calendar_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_sleeps_baby_id ON sleeps(baby_id);
CREATE INDEX IF NOT EXISTS idx_sleeps_synced ON sleeps(synced_to_calendar_at) WHERE synced_to_calendar_at IS NULL;

CREATE TABLE IF NOT EXISTS weights (
    id SERIAL PRIMARY KEY,
    baby_id INTEGER NOT NULL REFERENCES babies(id) ON DELETE CASCADE,
    hatch_id BIGINT UNIQUE NOT NULL,
    weight_grams NUMERIC NOT NULL,
    weight_date TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    synced_to_calendar_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_weights_baby_id ON weights(baby_id);
CREATE INDEX IF NOT EXISTS idx_weights_synced ON weights(synced_to_calendar_at) WHERE synced_to_calendar_at IS NULL;

CREATE TABLE IF NOT EXISTS photos (
    id SERIAL PRIMARY KEY,
    baby_id INTEGER NOT NULL REFERENCES babies(id) ON DELETE CASCADE,
    photo_key TEXT UNIQUE NOT NULL,
    create_date TIMESTAMPTZ NOT NULL,
    hatch_download_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_photos_baby_id ON photos(baby_id);
