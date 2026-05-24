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
