ALTER TABLE recordings
  ADD COLUMN IF NOT EXISTS feature_vector JSONB,
  ADD COLUMN IF NOT EXISTS feature_schema_v TEXT DEFAULT 'v1',
  ADD COLUMN IF NOT EXISTS model_version TEXT,
  ADD COLUMN IF NOT EXISTS confidence_margin INTEGER;
