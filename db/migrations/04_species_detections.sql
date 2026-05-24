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
