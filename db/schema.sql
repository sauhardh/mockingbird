-- MokingBird Unified PostgreSQL Schema

CREATE TABLE users (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  username    TEXT UNIQUE NOT NULL,
  email       TEXT UNIQUE,
  total_recordings INTEGER DEFAULT 0,
  badges      TEXT[] DEFAULT '{}'
);

CREATE TABLE nepal_species_reference (
  species_code    TEXT PRIMARY KEY,
  common_name     TEXT NOT NULL,
  scientific_name TEXT NOT NULL,
  is_endemic      BOOLEAN DEFAULT FALSE,
  is_threatened   BOOLEAN DEFAULT FALSE,
  threat_category TEXT,
  altitude_min_m  INTEGER,
  altitude_max_m  INTEGER,
  season_present  TEXT[]   -- ['monsoon','winter','resident']
);

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

CREATE TABLE species_detections (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  recording_id    UUID REFERENCES recordings(id) ON DELETE CASCADE,
  species_code    TEXT NOT NULL,     -- BirdNET species code
  common_name     TEXT NOT NULL,
  scientific_name TEXT NOT NULL,
  confidence_raw  FLOAT NOT NULL,    -- BirdNET raw score 0–1
  confidence_cal  FLOAT,             -- calibrated score (post logistic regression)
  start_sec       FLOAT NOT NULL,    -- segment start in recording
  end_sec         FLOAT NOT NULL,
  is_endemic      BOOLEAN DEFAULT FALSE,
  is_threatened   BOOLEAN DEFAULT FALSE,
  threat_category TEXT               -- IUCN: CR, EN, VU, NT
);

CREATE TABLE soundscape_indices (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  recording_id   UUID REFERENCES recordings(id) ON DELETE CASCADE,
  computed_at    TIMESTAMPTZ DEFAULT NOW(),

  -- Core indices (from scikit-maad)
  aci            FLOAT,   -- Acoustic Complexity Index
  bi             FLOAT,   -- Bioacoustic Index
  ndsi_bio       FLOAT,   -- NDSI biophony component (separate from anthrophony)
  ndsi_anth      FLOAT,   -- NDSI anthrophony component
  h_temporal     FLOAT,   -- Temporal Entropy (H)
  h_spectral     FLOAT,   -- Spectral Entropy
  m_median       FLOAT,   -- Median of amplitude envelope (M)
  adi            FLOAT    -- Acoustic Diversity Index
);

CREATE TABLE health_score_components (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  recording_id    UUID REFERENCES recordings(id) ON DELETE CASCADE,

  -- Component sub-scores (each 0–100, weighted into final)
  species_score   INTEGER,   -- species richness sub-score
  endemic_bonus   INTEGER,   -- +points for endemic/threatened species
  aci_score       INTEGER,
  ndsi_score      INTEGER,   -- derived from ndsi_bio
  disturbance_pen INTEGER,   -- penalty from ndsi_anth / detected noise events
  seasonal_adj    INTEGER,   -- seasonal anomaly adjustment

  -- Weights used (store for audit)
  w_species       FLOAT DEFAULT 0.35,
  w_aci           FLOAT DEFAULT 0.25,
  w_ndsi          FLOAT DEFAULT 0.20,
  w_disturbance   FLOAT DEFAULT 0.15,
  w_seasonal      FLOAT DEFAULT 0.05,

  -- Explanation text (human-readable for the breakdown card)
  explanation     JSONB   -- {"species": "High (↑)", "aci": "Low (↓)", ...}
);
