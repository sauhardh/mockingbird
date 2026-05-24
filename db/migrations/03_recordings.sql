CREATE TABLE recordings (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID REFERENCES users(id),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- GPS (from phone, automatic)
  latitude      DOUBLE PRECISION NOT NULL,
  longitude     DOUBLE PRECISION NOT NULL,
  altitude_m    DOUBLE PRECISION NOT NULL,
  altitude_zone TEXT NOT NULL CHECK (altitude_zone IN ('terai','hills','subalpine','himalayan')),

  -- Recording metadata
  duration_sec  INTEGER NOT NULL,
  file_path     TEXT NOT NULL,       -- S3 or local path to WAV
  recorded_at   TIMESTAMPTZ NOT NULL,

  -- Quality gate
  ndsi_anthro   FLOAT,              -- populated after pre-check
  quality_pass  BOOLEAN,            -- false = rejected before ML pipeline

  -- Health Index output
  health_score  INTEGER,            -- 0–100, NULL until processed
  processing_status TEXT DEFAULT 'pending'  -- pending | processing | complete | failed
);
