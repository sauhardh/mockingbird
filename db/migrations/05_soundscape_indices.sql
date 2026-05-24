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
