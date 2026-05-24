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
