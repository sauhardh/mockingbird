CREATE TABLE IF NOT EXISTS species_enrichment (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  recording_id UUID REFERENCES recordings(id) ON DELETE CASCADE,
  species_code TEXT NOT NULL,
  context_json JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_species_enrichment_recording
  ON species_enrichment(recording_id);
