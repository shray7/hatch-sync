-- Add source and media_type to photos for Hatch vs uploads (device / Google Photos) and video support.
ALTER TABLE photos ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'hatch';
ALTER TABLE photos ADD COLUMN IF NOT EXISTS media_type TEXT DEFAULT 'photo';
